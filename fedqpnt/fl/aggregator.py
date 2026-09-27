"""SS4.5 aggregators: FedAvg, FedProx (server side is identical to FedAvg --
the proximal term is client-side, applied inside ``TrustDetector.train_local``)
and TRIM-NB-R (FedQPNT default).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from fedqpnt.core.types import ModelUpdate


def staleness_weight(s: int) -> float:
    """SS4.6 polynomial staleness weight (1+s)^-0.5 (FedAsync, Xie 2019)."""
    return float((1.0 + max(s, 0)) ** -0.5)


def _flat(params: dict, names: list[str]) -> np.ndarray:
    return np.concatenate([np.asarray(params[n], dtype=np.float64).ravel() for n in names])


def _unflat(flat: np.ndarray, names: list[str], shapes: dict) -> dict[str, np.ndarray]:
    out, i = {}, 0
    for n in names:
        sz = int(np.prod(shapes[n])) if shapes[n] else 1
        out[n] = flat[i:i + sz].reshape(shapes[n])
        i += sz
    return out


def fedavg(updates: list[ModelUpdate], param_names: list[str],
           staleness: list[int] | None = None) -> dict[str, np.ndarray] | None:
    """SS4.5 FedAvg: Delta = sum(n_i * Delta_i) / sum(n_i), self-reported n_i
    (a deliberate vulnerability, per SS4.1), times the SS4.6 staleness weight."""
    if not updates:
        return None
    staleness = staleness if staleness is not None else [0] * len(updates)
    weights = np.array([max(u.n_samples, 0) * staleness_weight(s) for u, s in zip(updates, staleness)],
                        dtype=np.float64)
    if weights.sum() <= 0:
        weights = np.ones(len(updates))
    weights = weights / weights.sum()
    out = {}
    for name in param_names:
        stacked = np.stack([np.asarray(u.params[name], dtype=np.float64) for u in updates])
        w = weights.reshape((-1,) + (1,) * (stacked.ndim - 1))
        out[name] = np.sum(stacked * w, axis=0)
    return out


# FedProx's aggregation step is identical to FedAvg (mu=0 gives plain FedAvg,
# per SS4.2); the proximal penalty only changes the client's local loss.
fedprox_aggregate = fedavg


@dataclass
class TrimNbRConfig:
    clip_c: float = 2.0
    trim_beta: float = 0.2
    rep_rho: float = 0.8
    rep_q: float = 0.2
    quarantine_streak: int = 3
    quarantine_rounds: int = 10
    server_lr: float = 1.0
    probation_rounds: int = 2       # SS4.7: first 2 rounds of a cold-start node
    probation_clip_c: float = 1.0   # ... are clipped at c=1x median (tighter)


@dataclass
class TrimNbRState:
    reputation: dict[str, float] = field(default_factory=dict)
    low_rep_streak: dict[str, int] = field(default_factory=dict)
    quarantined_until: dict[str, int] = field(default_factory=dict)  # node_id -> round (exclusive)

    def is_quarantined(self, node_id: str, round_idx: int) -> bool:
        return round_idx < self.quarantined_until.get(node_id, -1)

    def get_rep(self, node_id: str) -> float:
        return self.reputation.get(node_id, 1.0)


def trim_nb_r_aggregate(
    updates: list[ModelUpdate],
    param_names: list[str],
    round_idx: int,
    state: TrimNbRState,
    cfg: TrimNbRConfig | None = None,
    staleness: list[int] | None = None,
    joined_round: dict[str, int] | None = None,
) -> tuple[dict[str, np.ndarray] | None, dict]:
    """SS4.5 TRIM-NB-R: clip -> exclude quarantined -> coordinate-wise trimmed
    mean (median if N_live < 5) -> reputation update -> quarantine. Returns
    ``(delta, info)``; ``delta`` is ``None`` if nothing survived to aggregate."""
    cfg = cfg or TrimNbRConfig()
    joined_round = joined_round or {}
    staleness = staleness if staleness is not None else [0] * len(updates)

    live = [(u, s) for u, s in zip(updates, staleness) if not state.is_quarantined(u.node_id, round_idx)]
    quarantined_nodes = [u.node_id for u, s in zip(updates, staleness) if state.is_quarantined(u.node_id, round_idx)]
    info: dict = {"quarantined_excluded": quarantined_nodes, "quarantine_events": []}
    if not live:
        return None, info

    shapes = {n: np.asarray(live[0][0].params[n]).shape for n in param_names}
    flats = np.stack([_flat(u.params, param_names) for u, _s in live])
    norms = np.linalg.norm(flats, axis=1)
    med_norm = float(np.median(norms))

    clipped = flats.copy()
    for i, (u, _s) in enumerate(live):
        c = cfg.clip_c
        j_round = joined_round.get(u.node_id)
        if j_round is not None and (round_idx - j_round) < cfg.probation_rounds:
            c = cfg.probation_clip_c
        scale = min(1.0, c * med_norm / max(norms[i], 1e-12))
        clipped[i] = flats[i] * scale

    stale_w = np.array([staleness_weight(s) for _u, s in live])
    weighted = clipped * stale_w[:, None]

    n_live = len(live)
    if n_live >= 5:
        k = int(np.floor(cfg.trim_beta * n_live))
        sorted_ = np.sort(weighted, axis=0)
        trimmed = sorted_[k:n_live - k] if n_live - 2 * k > 0 else sorted_
        agg_flat = trimmed.mean(axis=0)
    else:
        agg_flat = np.median(weighted, axis=0)

    denom = float(np.linalg.norm(agg_flat))
    for i, (u, _s) in enumerate(live):
        if denom > 1e-12 and np.linalg.norm(clipped[i]) > 1e-12:
            cos = float(np.dot(clipped[i], agg_flat) / (np.linalg.norm(clipped[i]) * denom))
        else:
            cos = 0.0
        cos = float(np.clip(cos, -1.0, 1.0))
        r_prev = state.get_rep(u.node_id)
        r_new = cfg.rep_rho * r_prev + (1 - cfg.rep_rho) * max(0.0, cos)
        state.reputation[u.node_id] = r_new
        if r_new < cfg.rep_q:
            state.low_rep_streak[u.node_id] = state.low_rep_streak.get(u.node_id, 0) + 1
        else:
            state.low_rep_streak[u.node_id] = 0
        if state.low_rep_streak.get(u.node_id, 0) >= cfg.quarantine_streak:
            state.quarantined_until[u.node_id] = round_idx + 1 + cfg.quarantine_rounds
            state.low_rep_streak[u.node_id] = 0
            info["quarantine_events"].append(u.node_id)

    delta = _unflat(cfg.server_lr * agg_flat, param_names, shapes)
    info["n_live"] = n_live
    info["median_norm"] = med_norm
    return delta, info
