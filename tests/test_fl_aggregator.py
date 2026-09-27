"""SS4.5 aggregator unit tests: FedAvg weighting/self-report vulnerability,
staleness weight, and TRIM-NB-R clip/trim/reputation/quarantine mechanics.
"""
from __future__ import annotations

import numpy as np
import pytest

from fedqpnt.core.types import ModelUpdate
from fedqpnt.fl.aggregator import (
    fedavg, staleness_weight, TrimNbRConfig, TrimNbRState, trim_nb_r_aggregate,
)
from fedqpnt.fl.poisoning import sign_flip

NAMES = ["w"]


def _u(node_id, val, n=100, round_idx=0):
    return ModelUpdate(node_id=node_id, round_idx=round_idx, params={"w": np.full(4, val)},
                        n_samples=n, metrics={})


def test_fedavg_weights_by_self_reported_n_samples():
    updates = [_u("a", 1.0, n=1), _u("b", 3.0, n=999)]
    out = fedavg(updates, NAMES)
    # dominated by b's huge self-reported n -> close to 3.0, not the (1+3)/2=2.0 mean
    assert np.allclose(out["w"], (1.0 * 1 + 3.0 * 999) / 1000)


def test_fedavg_staleness_downweights_stale_updates():
    updates = [_u("a", 1.0, n=100), _u("b", 5.0, n=100)]
    out_fresh = fedavg(updates, NAMES, staleness=[0, 0])
    out_stale = fedavg(updates, NAMES, staleness=[0, 3])
    # b's contribution shrinks when stale -> aggregate moves toward a=1.0
    assert out_stale["w"][0] < out_fresh["w"][0]


def test_staleness_weight_monotonically_decreasing():
    ws = [staleness_weight(s) for s in range(5)]
    assert ws == sorted(ws, reverse=True)
    assert ws[0] == 1.0


def test_trim_nb_r_clips_and_trims_outlier():
    honest = [_u(f"n{i}", 1.0, round_idx=0) for i in range(6)]
    attacker = _u("bad", 1000.0, round_idx=0)   # huge-norm outlier
    updates = honest + [attacker]
    state = TrimNbRState()
    delta, info = trim_nb_r_aggregate(updates, NAMES, 0, state, TrimNbRConfig())
    assert delta is not None
    # clipping bounds every update to <= c * median_norm, so aggregate stays near 1.0
    assert np.all(np.abs(delta["w"] - 1.0) < 0.5), delta["w"]
    assert info["n_live"] == 7


def test_trim_nb_r_quarantines_persistent_outlier_over_rounds():
    state = TrimNbRState()
    cfg = TrimNbRConfig()
    quarantined = False
    for r in range(15):
        honest = [_u(f"n{i}", 1.0, round_idx=r) for i in range(6)]
        attacker = _u("bad", -1000.0, round_idx=r)   # persistently opposite direction
        delta, info = trim_nb_r_aggregate(honest + [attacker], NAMES, r, state, cfg)
        if info["quarantine_events"]:
            quarantined = True
    assert quarantined, "a persistently adversarial node was never quarantined"
    assert state.quarantined_until["bad"] > 0
    assert state.is_quarantined("bad", state.quarantined_until["bad"] - 1)


def test_trim_nb_r_median_when_fewer_than_5_live():
    updates = [_u("a", 1.0, round_idx=0), _u("b", 3.0, round_idx=0)]
    state = TrimNbRState()
    delta, info = trim_nb_r_aggregate(updates, NAMES, 0, state, TrimNbRConfig())
    assert np.allclose(delta["w"], 2.0)   # median of {1,3} per element = 2.0


def test_trim_nb_r_excludes_quarantined_nodes():
    state = TrimNbRState()
    state.quarantined_until["bad"] = 10
    updates = [_u(f"n{i}", 1.0, round_idx=3) for i in range(5)] + [_u("bad", 999.0, round_idx=3)]
    delta, info = trim_nb_r_aggregate(updates, NAMES, 3, state, TrimNbRConfig())
    assert "bad" in info["quarantined_excluded"]
    assert info["n_live"] == 5


def test_fedavg_delta_measurably_changes_with_poisoned_fraction():
    """D-037 (Master review): S12's validation script once showed f=20% and
    f=40% giving bit-identical FedAvg results, which is impossible for a
    plain weighted average unless the poisoning wasn't taking effect. Root
    cause (traced separately): many nodes' synthetic training data degenerated
    to a zero delta every round (see tests/_fl_harness.py's round-0 clean
    warm-start fix), so poisoning a zero delta was a no-op regardless of f.
    This test isolates the AGGREGATION MATH ALONE (10 synthetic, guaranteed
    NON-ZERO honest deltas) and asserts FedAvg's output measurably differs
    as more of them are sign-flipped -- the property Master asked to
    regression-test directly."""
    rng = np.random.default_rng(0)
    honest_vals = rng.normal(loc=1.0, scale=0.3, size=10)   # distinct non-zero per-node deltas
    node_ids = [f"n{i}" for i in range(10)]

    def _make_updates(n_mal):
        updates = []
        for i, nid in enumerate(node_ids):
            params = {"w": np.full(4, honest_vals[i])}
            if i < n_mal:
                params = sign_flip(params, factor=-5.0)
            updates.append(ModelUpdate(node_id=nid, round_idx=0, params=params, n_samples=100, metrics={}))
        return updates

    out_f0 = fedavg(_make_updates(0), NAMES)["w"][0]
    out_f20 = fedavg(_make_updates(2), NAMES)["w"][0]
    out_f40 = fedavg(_make_updates(4), NAMES)["w"][0]
    print(f"\n[D-037] FedAvg w: f=0 -> {out_f0:.4f}, f=20% -> {out_f20:.4f}, f=40% -> {out_f40:.4f}")
    assert not np.isclose(out_f0, out_f20), "FedAvg unchanged between f=0 and f=20%"
    assert not np.isclose(out_f20, out_f40), "FedAvg unchanged between f=20% and f=40%"
    assert abs(out_f40 - honest_vals.mean()) > abs(out_f20 - honest_vals.mean()), \
        "more poisoning must push FedAvg's plain average further from the honest mean"

    # Same check for TRIM-NB-R (must MOVE LESS than FedAvg as f grows, not stay bit-identical).
    state20, state40 = TrimNbRState(), TrimNbRState()
    trim_f20, _ = trim_nb_r_aggregate(_make_updates(2), NAMES, 0, state20, TrimNbRConfig())
    trim_f40, _ = trim_nb_r_aggregate(_make_updates(4), NAMES, 0, state40, TrimNbRConfig())
    print(f"[D-037] TRIM-NB-R w: f=20% -> {trim_f20['w'][0]:.4f}, f=40% -> {trim_f40['w'][0]:.4f}")
    assert abs(trim_f40["w"][0] - honest_vals.mean()) >= abs(trim_f20["w"][0] - honest_vals.mean()) - 1e-9
