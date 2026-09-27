"""SS8 real multi-process validation (multiprocessing spawn + mp.Queue),
seeds 500-599 only. Determinism + S5/S8/S9/S12/S15 acceptance criteria of
ARCHITECTURE.md SS6.1, scoped down (N, n_rounds, duration_s) to keep wall
time bounded for CI while still exercising the real protocol end to end.
Bigger N=5/N=10 wall-time numbers are reported by
scripts/run_fl_validate.py (not run under pytest).
"""
from __future__ import annotations

import numpy as np
import pytest

from fedqpnt.trust.detector import TrustDetector
from fedqpnt.fl.orchestrator import ScenarioConfig, run_federation
from fedqpnt.fl.server import ServerConfig
from fedqpnt.fl.client import ClientConfig
from fedqpnt.fl.comms import CommsConfig
from tests._fl_harness import make_provider

DURATION_S = 15.0   # short synthetic missions -> fast rounds
N_ROUNDS = 5


def _theta0():
    d = TrustDetector(arch="mlp", seed=0)
    theta0 = d.get_params()
    return theta0, list(theta0.keys())


def _base_scenario(node_ids, n_rounds=N_ROUNDS, seed=500, aggregator="trim_nb_r", **kw):
    return ScenarioConfig(node_ids=node_ids, n_rounds=n_rounds, seed=seed, aggregator=aggregator,
                           client_cfg=ClientConfig(min_samples=16), **kw)


def test_determinism_bit_identical_across_runs():
    node_ids = [f"n{i}" for i in range(5)]
    theta0, param_names = _theta0()
    provider = make_provider(base_seed=500, duration_s=DURATION_S)
    scenario = _base_scenario(node_ids, seed=501)

    r1 = run_federation(scenario, provider, theta0, param_names)
    r2 = run_federation(scenario, provider, theta0, param_names)

    assert not r1.aborted and not r2.aborted
    for k in r1.final_theta:
        assert np.array_equal(r1.final_theta[k], r2.final_theta[k]), f"mismatch in {k}"


def test_clients_install_global_model_after_successful_rounds():
    """Regression test for a real bug: FLServer.aggregate_round replies with
    a ``(GlobalModel, delay_s)`` TUPLE on success, but ``_node_main`` used to
    check ``isinstance(reply, GlobalModel)`` directly (always False for the
    tuple) -- so ``install_global`` was never called, ``base_round`` stayed
    at -1 forever, and staleness s=round-(-1) silently exceeded
    max_staleness=3 from round 3 onward, wrongly ROUND_SKIPPED-ing every
    later round. Over enough rounds with nominal comms, staleness must NOT
    creep up round after round (it would if models were never installed)."""
    node_ids = [f"n{i}" for i in range(6)]
    theta0, param_names = _theta0()
    provider = make_provider(base_seed=512, duration_s=20.0)
    n_rounds = 6
    scenario = ScenarioConfig(node_ids=node_ids, n_rounds=n_rounds, seed=513, aggregator="trim_nb_r",
                               client_cfg=ClientConfig(min_samples=8))
    result = run_federation(scenario, provider, theta0, param_names)
    assert not result.aborted, result.abort_reason
    n_skipped = [e for e in result.server_log if e["event"] == "ROUND_SKIPPED"]
    print(f"\n[install-regression] server_log={result.server_log}")
    # under nominal comms/no failures, staleness-driven ROUND_SKIPPED must
    # not appear at all across 6 rounds (it appeared at round 3+ every time
    # under the bug, since s = round_idx + 1 there regardless of node count).
    assert not any(r >= 3 for r in (e["round"] for e in n_skipped)), \
        "a round >=3 was skipped -- suggests staleness never resets (install_global not firing)"
    assert not np.allclose(result.final_theta["fc1.weight"], theta0["fc1.weight"]), \
        "global model never changed from theta0 -- FL made no progress"


def test_s5_partial_failure_and_delay_no_deadlock():
    node_ids = [f"n{i}" for i in range(10)]
    theta0, param_names = _theta0()
    provider = make_provider(base_seed=502, duration_s=DURATION_S)
    n_rounds = 6
    t_half = n_rounds // 2
    affected = node_ids[: int(0.3 * len(node_ids)) or 1]
    failure_round = {nid: t_half for nid in affected[: len(affected) // 2 or 1]}
    delay_round = {nid: (t_half, t_half + 2) for nid in affected[len(affected) // 2:]}
    scenario = _base_scenario(node_ids, n_rounds=n_rounds, seed=503,
                               failure_round=failure_round, delay_window=delay_round)

    baseline_scenario = _base_scenario(node_ids, n_rounds=n_rounds, seed=503)
    baseline = run_federation(baseline_scenario, provider, theta0, param_names)
    result = run_federation(scenario, provider, theta0, param_names)

    assert not result.aborted, result.abort_reason
    n_skipped = sum(1 for e in result.server_log if e["event"] == "ROUND_SKIPPED")
    print(f"\n[S5] rounds skipped: {n_skipped}/{n_rounds}; log={result.server_log}")
    # "no deadlock" (we got here) + every round either aggregated or was
    # logged ROUND_SKIPPED (never silently hung) is the pass condition;
    # the "final AUC >= AUC(no failure) - 0.02" numeric check is done by
    # scripts/run_fl_validate.py against the held-out evaluator set.
    assert not baseline.aborted


def test_s8_cold_start_receives_model_within_two_rounds():
    """A cold-start node reaches its join round almost instantly (it just
    skips the dormant rounds), so its round-r message can land on the
    server's shared inbox before the server has even finished collecting
    round 0/1 -- the server MUST buffer it for its real round rather than
    drop it (regression test for a real deadlock this caught: an
    out-of-order message silently discarded -> 600s wall-clock ABORT)."""
    node_ids = [f"n{i}" for i in range(5)] + ["cold0"]
    theta0, param_names = _theta0()
    provider = make_provider(base_seed=504, duration_s=30.0)   # more data -> quorum isn't data-starved
    n_rounds = 5
    join_round = {"cold0": 2}
    scenario = ScenarioConfig(node_ids=node_ids, n_rounds=n_rounds, seed=505, aggregator="trim_nb_r",
                               client_cfg=ClientConfig(min_samples=8), join_round=join_round)
    result = run_federation(scenario, provider, theta0, param_names)
    assert not result.aborted, result.abort_reason
    # nominal comms (CommsConfig defaults): no round should be SKIPPED at all
    # in cold0's first 2 active rounds (this is the actual S8 pass criterion
    # -- receives the global model within 2 rounds -- not a data-volume
    # artifact of the short synthetic missions used elsewhere in this file).
    n_skipped_after_join = sum(1 for e in result.server_log
                                if e["event"] == "ROUND_SKIPPED" and join_round["cold0"] <= e["round"] < join_round["cold0"] + 2)
    print(f"\n[S8] server_log={result.server_log}")
    assert n_skipped_after_join == 0, "cold-start node's join window had a skipped round under nominal comms"


def test_s9_comms_dropouts_no_deadlock():
    node_ids = [f"n{i}" for i in range(6)]
    theta0, param_names = _theta0()
    provider = make_provider(base_seed=506, duration_s=DURATION_S)
    for loss_b, p_gb in ((0.5, 0.02), (0.9, 0.1)):
        comms = CommsConfig(p_gb=p_gb, loss_b=loss_b)
        scenario = _base_scenario(node_ids, n_rounds=6, seed=507, comms_cfg=comms)
        result = run_federation(scenario, provider, theta0, param_names)
        assert not result.aborted, f"loss_b={loss_b} p_gb={p_gb}: {result.abort_reason}"


def test_s12_trim_nb_r_survives_20pct_poisoned_sign_flip():
    node_ids = [f"n{i}" for i in range(10)]
    theta0, param_names = _theta0()
    provider = make_provider(base_seed=508, duration_s=DURATION_S)
    n_mal = max(int(0.2 * len(node_ids)), 1)
    poison = {node_ids[i]: "sign_flip" for i in range(n_mal)}
    scenario_trim = _base_scenario(node_ids, n_rounds=6, seed=509, aggregator="trim_nb_r", poison_kind=poison)
    scenario_fedavg = _base_scenario(node_ids, n_rounds=6, seed=509, aggregator="fedavg", poison_kind=poison)
    r_trim = run_federation(scenario_trim, provider, theta0, param_names)
    r_fedavg = run_federation(scenario_fedavg, provider, theta0, param_names)
    assert not r_trim.aborted and not r_fedavg.aborted
    # sanity: TRIM-NB-R's final weights stay much closer to theta0 in norm
    # than FedAvg's do, since FedAvg has no defence against sign-flip x(-5).
    def _dist(theta):
        return float(np.linalg.norm(theta["fc1.weight"] - theta0["fc1.weight"]))
    d_trim, d_fedavg = _dist(r_trim.final_theta), _dist(r_fedavg.final_theta)
    print(f"\n[S12] ||delta_theta|| TRIM-NB-R={d_trim:.4f} FedAvg={d_fedavg:.4f}")
    assert d_trim <= d_fedavg + 1e-6


def test_s15_honest_heterogeneous_nodes_rarely_quarantined():
    """Nodes with different (but honest) attack-family mixes must not be
    quarantined just for looking different from each other."""
    node_ids = [f"n{i}" for i in range(8)]
    theta0, param_names = _theta0()
    provider = make_provider(base_seed=510, duration_s=DURATION_S)
    scenario = _base_scenario(node_ids, n_rounds=8, seed=511, aggregator="trim_nb_r")
    result = run_federation(scenario, provider, theta0, param_names)
    assert not result.aborted, result.abort_reason
    quarantine_events = [e for e in result.server_log if e["event"] == "QUARANTINE"]
    print(f"\n[S15] quarantine events among honest heterogeneous nodes: {quarantine_events}")
    assert len(quarantine_events) == 0, "honest heterogeneity triggered a quarantine"
