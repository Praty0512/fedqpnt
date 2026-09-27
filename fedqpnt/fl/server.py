"""SS8 Server process: collects one message per live node per round
(node-id order, never arrival order), aggregates (SS4.5), draws downlink
delay/loss (SS4.6), and replies with ``GlobalModel`` or ``Lost``.
"""
from __future__ import annotations

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")

from dataclasses import dataclass, field

import numpy as np
import torch

torch.set_num_threads(1)

from fedqpnt.core.types import ModelUpdate, GlobalModel
from fedqpnt.fl.transport import Lost, RoundSkipped, enforce_leakage_guard
from fedqpnt.fl.aggregator import fedavg, trim_nb_r_aggregate, TrimNbRState, TrimNbRConfig
from fedqpnt.fl.comms import downlink_channel, CommsConfig


@dataclass
class ServerConfig:
    aggregator: str = "trim_nb_r"      # "fedavg" | "fedprox" | "trim_nb_r"
    max_staleness: int = 3             # SS4.6: discard if s > 3
    quorum_frac: float = 0.5           # SS4.6: >= ceil(0.5 * N_live)
    seed: int = 500
    comms: CommsConfig = field(default_factory=CommsConfig)
    trim_cfg: TrimNbRConfig = field(default_factory=TrimNbRConfig)
    msg_bytes: float = 4096.0          # SS8: ~4kB pickled dataclasses


class FLServer:
    """Holds the global model (theta_g) and the TRIM-NB-R reputation state.
    ``aggregate_round`` is transport-agnostic: the orchestrator/Server process
    collects the round's messages (via whatever Transport), sorts them by
    node_id itself and passes the dict in; this class only aggregates and
    computes the SS4.6 downlink outcome per node."""

    def __init__(self, param_names: list[str], theta0: dict[str, np.ndarray], cfg: ServerConfig | None = None):
        self.param_names = list(param_names)
        self.theta = {k: np.asarray(v, dtype=np.float64).copy() for k, v in theta0.items()}
        self.cfg = cfg or ServerConfig()
        self.trim_state = TrimNbRState()
        self._down_channels: dict[str, object] = {}
        self._last_round_seen: dict[str, int] = {}
        self._joined_round: dict[str, int] = {}
        self.log: list[dict] = []

    @staticmethod
    def _poison_fresh_updates(fresh_updates: list[ModelUpdate], model_names: list[str],
                               malicious_ids: "set[str]", poison_kind: str,
                               rng: np.random.Generator) -> list[ModelUpdate]:
        from fedqpnt.fl.poisoning import gaussian_noise, alie
        honest = [u for u in fresh_updates if u.node_id not in malicious_ids]
        if not honest:
            return fresh_updates
        honest_deltas = [{k: u.params[k] for k in model_names} for u in honest]
        n_total, n_mal = len(fresh_updates), sum(1 for u in fresh_updates if u.node_id in malicious_ids)
        if poison_kind == "alie" and n_mal > 0:
            mal_delta = alie(honest_deltas, model_names, n_total, n_mal)
        else:
            norms = [float(np.linalg.norm(np.concatenate([np.asarray(d[k]).ravel() for k in model_names])))
                     for d in honest_deltas]
            target_norm = 10.0 * float(np.median(norms))
            mal_delta = None  # drawn per malicious node below (gaussian_noise needs its own rng draw)
        out = []
        for u in fresh_updates:
            if u.node_id in malicious_ids:
                new_params = dict(u.params)
                if poison_kind == "alie":
                    new_params.update(mal_delta)
                else:
                    new_params.update(gaussian_noise({k: u.params[k] for k in model_names}, rng, target_norm))
                out.append(ModelUpdate(node_id=u.node_id, round_idx=u.round_idx, params=new_params,
                                        n_samples=u.n_samples, metrics=u.metrics, kind=u.kind))
            else:
                out.append(u)
        return out

    def _down(self, node_id: str):
        if node_id not in self._down_channels:
            self._down_channels[node_id] = downlink_channel(self.cfg.seed, node_id, self.cfg.comms)
        return self._down_channels[node_id]

    def global_params(self) -> dict[str, np.ndarray]:
        return {k: v.copy() for k, v in self.theta.items()}

    def aggregate_round(self, round_idx: int, messages: dict[str, object],
                         malicious_ids: "set[str] | None" = None, poison_kind: str | None = None,
                         poison_rng: "np.random.Generator | None" = None) -> dict[str, object]:
        """``messages``: node_id -> ModelUpdate | NoUpdate | Lost | Failed,
        one entry per node the server expects a message from this round
        (already collected by the orchestrator). Returns node_id ->
        (GlobalModel, delay_s) | Lost | RoundSkipped.

        ``malicious_ids``/``poison_kind`` (only ``"gaussian_noise"``/``"alie"``)
        are simulation-only bookkeeping for attacks that need visibility into
        peers' updates (ALIE) or a cross-node norm reference (Gaussian noise);
        sign-flip/label-flip are applied node-locally instead (SS4.5) and need
        no server hook. This models a coordinated attacker's shared
        infrastructure, not a real distributed-collusion channel."""
        ordered_ids = sorted(messages.keys())   # SS8: aggregate in node_id order
        model_names = [k for k in self.param_names if k not in ("norm_mu", "norm_sd", "norm_count")]
        model_shapes = {k: self.theta[k].shape for k in model_names}

        fresh_updates: list[ModelUpdate] = []
        staleness: list[int] = []
        norm_reports = []
        for node_id in ordered_ids:
            msg = messages[node_id]
            if isinstance(msg, ModelUpdate):
                enforce_leakage_guard(msg.params, model_shapes, msg.metrics)
                base_round = int(msg.metrics.get("base_round", msg.round_idx))
                s = max(round_idx - base_round, 0)
                if s > self.cfg.max_staleness:
                    continue
                fresh_updates.append(msg)
                staleness.append(s)
                if "norm_mu" in msg.params and "norm_sd" in msg.params:
                    norm_reports.append((msg.params["norm_mu"], msg.params["norm_sd"]))

        if malicious_ids and poison_kind in ("gaussian_noise", "alie"):
            fresh_updates = self._poison_fresh_updates(fresh_updates, model_names, malicious_ids,
                                                        poison_kind, poison_rng or np.random.default_rng(0))

        n_live = len(messages)
        quorum = int(np.ceil(self.cfg.quorum_frac * n_live)) if n_live else 0
        replies: dict[str, object] = {}

        if n_live == 0 or len(fresh_updates) < max(quorum, 1):
            self.log.append({"round": round_idx, "event": "ROUND_SKIPPED",
                              "n_live": n_live, "n_fresh": len(fresh_updates)})
            skip = RoundSkipped(round_idx=round_idx, n_live=n_live, n_fresh=len(fresh_updates))
            return {node_id: skip for node_id in ordered_ids}

        if self.cfg.aggregator in ("fedavg", "fedprox"):
            delta = fedavg(fresh_updates, model_names, staleness=staleness)
            info: dict = {}
        else:
            delta, info = trim_nb_r_aggregate(fresh_updates, model_names, round_idx, self.trim_state,
                                               self.cfg.trim_cfg, staleness=staleness,
                                               joined_round=self._joined_round)
            if info.get("quarantine_events"):
                self.log.append({"round": round_idx, "event": "QUARANTINE", "nodes": info["quarantine_events"]})

        if delta is not None:
            for k in model_names:
                self.theta[k] = self.theta[k] + delta[k]
        if norm_reports:
            self.theta["norm_mu"] = np.median(np.stack([r[0] for r in norm_reports]), axis=0)
            self.theta["norm_sd"] = np.median(np.stack([r[1] for r in norm_reports]), axis=0)

        for node_id in ordered_ids:
            self._last_round_seen[node_id] = round_idx
            self._joined_round.setdefault(node_id, round_idx)
            outcome = self._down(node_id).send(self.cfg.msg_bytes)
            if outcome.lost:
                replies[node_id] = Lost(node_id=node_id, round_idx=round_idx, direction="down")
            else:
                replies[node_id] = (GlobalModel(round_idx=round_idx, params=self.global_params()),
                                     outcome.delay_s)
        return replies
