"""SS8 federation execution model: real multiprocessing (spawn) + mp.Queue,
bulk-synchronous in sim time, one Server process + N Node processes + a
watchdog, per the determinism protocol.

This module does NOT depend on fedqpnt.node/fedqpnt.fusion/fedqpnt.trust
internals beyond TrustDetector's public API; a node's actual mission
simulation is provided externally via ``local_dataset_provider`` (SS8's
"ticks until t>=t_r" is delegated to that provider, which stands in for the
per-round data window until the closed-loop integration at M2).
"""
from __future__ import annotations

import multiprocessing as mp
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import torch

torch.set_num_threads(1)

from fedqpnt.core.types import ModelUpdate
from fedqpnt.core.seeding import stream
from fedqpnt.fl.transport import NoUpdate, Lost, Failed, RoundSkipped
from fedqpnt.fl.comms import CommsConfig, uplink_channel
from fedqpnt.fl.aggregator import TrimNbRConfig
from fedqpnt.fl.client import ClientConfig, FLClient
from fedqpnt.fl.server import ServerConfig, FLServer
from fedqpnt.fl.poisoning import sign_flip, label_flip


def _seed_from_node_id(seed: int, node_id: str) -> int:
    rng = stream(seed, node_id, "detector_init")
    return int(rng.integers(0, 2**31 - 1))


@dataclass
class ScenarioConfig:
    node_ids: list[str]
    n_rounds: int
    seed: int = 500
    aggregator: str = "trim_nb_r"
    server_cfg: ServerConfig | None = None
    client_cfg: ClientConfig = field(default_factory=ClientConfig)
    comms_cfg: CommsConfig = field(default_factory=CommsConfig)
    join_round: dict[str, int] = field(default_factory=dict)       # SS4.7 cold start (default 0)
    failure_round: dict[str, int] = field(default_factory=dict)    # scheduled node failure (S5)
    delay_window: dict[str, tuple[int, int]] = field(default_factory=dict)   # scripted delay [lo,hi] rounds (S5)
    poison_kind: dict[str, str] = field(default_factory=dict)      # node_id -> "sign_flip"|"label_flip"|"gaussian_noise"|"alie"
    detector_arch: str = "mlp"

    def server_poison_kind(self) -> "tuple[set[str], str | None]":
        """gaussian_noise/alie need server-side coordination (see server.py's
        _poison_fresh_updates); returns (malicious_ids, kind) for those two,
        else (set(), None) since sign_flip/label_flip are node-local."""
        ids = {nid for nid, k in self.poison_kind.items() if k in ("gaussian_noise", "alie")}
        if not ids:
            return set(), None
        kinds = {self.poison_kind[nid] for nid in ids}
        return ids, next(iter(kinds))

    def expected_ids(self, round_idx: int) -> list[str]:
        out = []
        for nid in self.node_ids:
            if round_idx < self.join_round.get(nid, 0):
                continue
            fr = self.failure_round.get(nid)
            if fr is not None and round_idx > fr:
                continue
            out.append(nid)
        return sorted(out)


@dataclass
class FederationResult:
    final_theta: dict[str, np.ndarray]
    server_log: list[dict]
    reputation: dict[str, float]
    quarantined_until: dict[str, int]
    round_wall_s: list[float]
    aborted: bool = False
    abort_reason: str = ""


def _apply_local_poison(kind: Optional[str], update: ModelUpdate) -> ModelUpdate:
    if kind is None:
        return update
    model_keys = [k for k in update.params if k not in ("norm_mu", "norm_sd", "norm_count")]
    if kind == "sign_flip":
        model_params = {k: update.params[k] for k in model_keys}
        flipped = sign_flip(model_params, factor=-5.0)
        new_params = dict(update.params)
        new_params.update(flipped)
        update.params = new_params
    # "label_flip" is applied earlier, inside the node loop, to y before
    # train_local -- nothing to do here.
    return update


def _node_main(node_id: str, provider, scenario: ScenarioConfig, theta0: dict[str, np.ndarray],
                server_q, down_q) -> None:
    os.environ["OMP_NUM_THREADS"] = "1"
    torch.set_num_threads(1)
    from fedqpnt.trust.detector import TrustDetector

    node_seed = _seed_from_node_id(scenario.seed, node_id)
    detector = TrustDetector(arch=scenario.detector_arch, seed=node_seed)
    detector.set_params({k: np.asarray(v) for k, v in theta0.items()})
    rng = np.random.default_rng(node_seed)
    poison_kind = scenario.poison_kind.get(node_id)

    def _provider(nid, r):
        X, y = provider(nid, r)
        if X is None:
            return X, y
        if poison_kind == "label_flip":
            y = label_flip(np.asarray(y, dtype=float))
        return X, y

    client = FLClient(node_id, _provider, detector, scenario.client_cfg, rng=rng)
    up = uplink_channel(scenario.seed, node_id, scenario.comms_cfg)
    join_round = scenario.join_round.get(node_id, 0)
    failure_round = scenario.failure_round.get(node_id)
    delay_window = scenario.delay_window.get(node_id)

    for r in range(scenario.n_rounds):
        if r < join_round:
            continue
        if failure_round is not None and r == failure_round:
            server_q.put((node_id, r, Failed(node_id=node_id, round_idx=r)))
            return
        if delay_window is not None and delay_window[0] <= r <= delay_window[1]:
            server_q.put((node_id, r, NoUpdate(node_id=node_id, round_idx=r, reason="scripted_delay")))
        else:
            update = client.local_round(r)
            if update is None:
                server_q.put((node_id, r, NoUpdate(node_id=node_id, round_idx=r)))
            else:
                update = _apply_local_poison(poison_kind, update)
                outcome = up.send()
                if outcome.lost:
                    server_q.put((node_id, r, Lost(node_id=node_id, round_idx=r, direction="up")))
                else:
                    server_q.put((node_id, r, update))
        try:
            recv_round, reply = down_q.get(timeout=600.0)
        except Exception:
            return
        # FLServer.aggregate_round replies with (GlobalModel, delay_s) on a
        # successful downlink (SS4.6's simulated d_down is carried alongside
        # the model, not consumed here since the barrier is logical, not
        # wall-clock -- see orchestrator module docstring); Lost/RoundSkipped
        # arrive bare. A bug here (checking isinstance(reply, GlobalModel)
        # directly, missing the tuple) meant install_global was NEVER called
        # -- base_round stayed at its initial -1 forever, so staleness
        # s=round_idx-(-1) silently exceeded max_staleness=3 by round 3 and
        # every subsequent round was wrongly ROUND_SKIPPED. Regression
        # tests: test_fl_orchestrator.py::test_s8_cold_start_receives_model_within_two_rounds
        # and test_client_installs_after_successful_round below.
        if isinstance(reply, tuple):
            global_model, _delay_s = reply
            client.install_global(global_model.params, global_model.round_idx)
        # Lost / RoundSkipped (bare, not a tuple): keep the currently-installed model.


def _server_main(scenario: ScenarioConfig, param_names: list[str], theta0: dict[str, np.ndarray],
                  server_q, down_qs: dict, result_q) -> None:
    os.environ["OMP_NUM_THREADS"] = "1"
    torch.set_num_threads(1)
    server_cfg = scenario.server_cfg or ServerConfig(aggregator=scenario.aggregator, seed=scenario.seed)
    server = FLServer(param_names, theta0, server_cfg)
    round_wall_s = []
    malicious_ids, server_poison_kind = scenario.server_poison_kind()
    poison_rng = np.random.default_rng(scenario.seed)
    # A cold-start node (or any node many rounds "ahead" because it skipped
    # dormant rounds near-instantly) can put its round-r message on
    # ``server_q`` before the server has finished collecting round r-1, r-2,
    # ... . Messages pulled off the queue for a round other than the one
    # currently being collected MUST be buffered, never dropped, or they are
    # lost forever (this was a real deadlock: a cold-start node's message
    # arrived during round 0's collection and vanished, hanging round 2 for
    # the full 600s wall-clock ABORT). ``pending`` persists across rounds.
    pending: dict[tuple[str, int], object] = {}
    for r in range(scenario.n_rounds):
        t0 = time.monotonic()
        expected = scenario.expected_ids(r)
        remaining = set(expected)
        messages: dict[str, object] = {}
        for node_id in list(remaining):
            key = (node_id, r)
            if key in pending:
                messages[node_id] = pending.pop(key)
                remaining.discard(node_id)
        deadline = time.monotonic() + 600.0
        aborted = False
        while remaining:
            timeout = max(deadline - time.monotonic(), 0.001)
            try:
                node_id, round_idx, msg = server_q.get(timeout=timeout)
            except Exception:
                aborted = True
                break
            if round_idx != r or node_id not in remaining:
                pending[(node_id, round_idx)] = msg   # buffer for its real round
                continue
            messages[node_id] = msg
            remaining.discard(node_id)
        if aborted:
            result_q.put({"aborted": True, "abort_reason": f"wall-clock ABORT round {r}, missing {remaining}",
                          "theta": server.global_params(), "log": server.log,
                          "reputation": dict(server.trim_state.reputation),
                          "quarantined_until": dict(server.trim_state.quarantined_until),
                          "round_wall_s": round_wall_s})
            return
        replies = server.aggregate_round(r, messages, malicious_ids=malicious_ids,
                                          poison_kind=server_poison_kind, poison_rng=poison_rng)
        for node_id, reply in replies.items():
            down_qs[node_id].put((r, reply))
        round_wall_s.append(time.monotonic() - t0)
    result_q.put({"aborted": False, "abort_reason": "", "theta": server.global_params(), "log": server.log,
                  "reputation": dict(server.trim_state.reputation),
                  "quarantined_until": dict(server.trim_state.quarantined_until),
                  "round_wall_s": round_wall_s})


def run_federation(scenario: ScenarioConfig, provider: Callable, theta0: dict[str, np.ndarray],
                    param_names: list[str], join_timeout_s: float = 900.0) -> FederationResult:
    """Spawns 1 Server process + len(node_ids) Node processes (SS8), runs the
    full ``n_rounds`` bulk-synchronous protocol, and joins everything. A
    watchdog (``proc.is_alive()`` poll) detects real process crashes, which
    are logged (they flag the run as non-deterministic per SS8)."""
    ctx = mp.get_context("spawn")
    server_q = ctx.Queue()
    down_qs = {nid: ctx.Queue() for nid in scenario.node_ids}
    result_q = ctx.Queue()

    server_proc = ctx.Process(target=_server_main, args=(scenario, param_names, theta0, server_q, down_qs, result_q))
    node_procs = {
        nid: ctx.Process(target=_node_main, args=(nid, provider, scenario, theta0, server_q, down_qs[nid]))
        for nid in scenario.node_ids
    }

    server_proc.start()
    for p in node_procs.values():
        p.start()

    crashed = []
    watchdog_deadline = time.monotonic() + join_timeout_s
    result = None
    while time.monotonic() < watchdog_deadline:
        if not result_q.empty():
            result = result_q.get()
            break
        if not server_proc.is_alive() and result is None:
            crashed.append("server")
            break
        for nid, p in node_procs.items():
            if not p.is_alive() and p.exitcode not in (0, None) and nid not in crashed:
                crashed.append(nid)
        time.sleep(0.05)

    server_proc.join(timeout=30)
    for p in node_procs.values():
        p.join(timeout=30)
        if p.is_alive():
            p.terminate()
    if server_proc.is_alive():
        server_proc.terminate()

    if result is None:
        return FederationResult(final_theta=theta0, server_log=[], reputation={}, quarantined_until={},
                                 round_wall_s=[], aborted=True,
                                 abort_reason=f"watchdog timeout / crash: {crashed}")
    return FederationResult(final_theta=result["theta"], server_log=result["log"],
                             reputation=result["reputation"], quarantined_until=result["quarantined_until"],
                             round_wall_s=result["round_wall_s"], aborted=result["aborted"],
                             abort_reason=result["abort_reason"])
