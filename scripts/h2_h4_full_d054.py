"""D-054 step 4 (gated on step 3 passing -- fl_sanity_check_d054.py showed
FedAvg/TRIM-NB-R both >=0.95x centralised AUC and 0 FAR-proxy across the
whole 2x2x1 grid; chosen hyperparams: local_epochs=2, lr=0.05, prox_mu=0.0,
rounds=10, same for all FL methods). Re-runs H2 (novel family = meaconing,
absent from theta0 AND from n0's own local training data, present in its
4 peers') and H4 (cold-start) with FULL live-evaluation missions (600 s),
>=3 seeds, FedQPNT vs B-cont AUC/latency with a mean +/- 95%-CI (normal
approx, n=3) over seeds. theta0 = results/fleet/theta0_d054.npz
(D-054.1, restricted to clean/abrupt/jam_* -- no drift, no meaconing).

Local-training missions are 120 s (not the full 300-600 s of a from-scratch
M1 retrain) to keep this session's wall time bounded; this is noted
explicitly in the report, not hidden.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from fedqpnt.fl.client import ClientConfig
from fedqpnt.fleet.orchestrator import FleetScenarioConfig, run_fleet
from fedqpnt.node.methods import load_detector_weights
from fedqpnt.training.build_supervised_dataset import plan_for

THETA0_PATH = Path("results/fleet/theta0_d054.npz")
N_NODES = 5
LIVE_DURATION_S = 600.0
LOCAL_TRAIN_DURATION_S = 120.0
ROUND_PERIOD_S = 60.0
N_ROUNDS = 10
CHOSEN = dict(local_epochs=2, lr=0.05, prox_mu=0.0)
LIVE_SEEDS = [500, 501, 502]                      # >=3 seeds for the live mission / CI
MEACONING_LIVE = dict(kind="meaconing", onset_s=120.0, duration_s=300.0, severity=0.6)
COLD_ATTACK = dict(kind="drift_spoof", onset_s=330.0, duration_s=200.0, severity=0.6)


def _theta0():
    p = load_detector_weights(THETA0_PATH)
    if p is None:
        raise SystemExit(f"{THETA0_PATH} missing -- run scripts/pretrain_theta0_d054.py first")
    return p, list(p.keys())


def _seeds_excluding_family(base: int, family_name: str, count: int) -> list[int]:
    out, s = [], base
    while len(out) < count:
        fam, _atk = plan_for(s, "mixed")
        if fam != family_name:
            out.append(s)
        s += 1
    return out


def _seeds_including_family(base: int, family_name: str, count: int) -> list[int]:
    """count seeds, GUARANTEED to include >=1 of family_name (searches ahead
    for the first such seed then fills the rest sequentially)."""
    s = base
    first = None
    while first is None:
        fam, _atk = plan_for(s, "mixed")
        if fam == family_name:
            first = s
        s += 1
    out = [first]
    s = base
    while len(out) < count:
        if s != first:
            out.append(s)
        s += 1
    return sorted(out)


def _ci95(vals: list[float]) -> dict:
    a = np.array([v for v in vals if v is not None and np.isfinite(v)], dtype=float)
    if len(a) == 0:
        return dict(mean=float("nan"), ci95=float("nan"), n=0)
    mean = float(np.mean(a))
    sd = float(np.std(a, ddof=1)) if len(a) > 1 else 0.0
    ci = 1.96 * sd / np.sqrt(len(a)) if len(a) > 1 else 0.0
    return dict(mean=mean, sd=sd, ci95=ci, n=len(a), values=a.tolist())


def run_h2(theta0, param_names) -> dict:
    node_ids = [f"n{i}" for i in range(N_NODES)]
    per_arm = {"fedqpnt_local": {"auc": [], "latency_on": []}, "baseline_b_cont": {"auc": [], "latency_on": []}}
    for seed in LIVE_SEEDS:
        local_seeds = {
            "n0": _seeds_excluding_family(300_000 + seed * 100, "meaconing", 6),
            **{f"n{i}": _seeds_including_family(300_000 + seed * 100 + i * 1000, "meaconing", 6)
               for i in range(1, N_NODES)},
        }
        for method, ids in (("fedqpnt_local", node_ids), ("baseline_b_cont", ["n0"])):
            scenario = FleetScenarioConfig(
                scenario_id=f"h2_full_{method}_seed{seed}", method=method, seed=seed, node_ids=ids,
                n_rounds=N_ROUNDS, round_period_s=ROUND_PERIOD_S, duration_s=LIVE_DURATION_S,
                client_cfg=ClientConfig(min_samples=8, **CHOSEN), attacks={"n0": MEACONING_LIVE},
                local_train_seeds={nid: local_seeds[nid] for nid in ids},
                local_train_pool={nid: "mixed" for nid in ids}, local_train_duration_s=LOCAL_TRAIN_DURATION_S,
            )
            result = run_fleet(scenario, theta0, param_names)
            n0 = result.node_results.get("n0", {})
            print(f"[H2 {method} seed{seed}] aborted={result.aborted} auc={n0.get('auc')} "
                  f"latency_on={n0.get('latency_on')}")
            per_arm[method]["auc"].append(n0.get("auc"))
            per_arm[method]["latency_on"].append(n0.get("latency_on"))
    return {method: dict(auc=_ci95(v["auc"]), latency_on=_ci95(v["latency_on"])) for method, v in per_arm.items()}


def run_h4(theta0, param_names) -> dict:
    node_ids = [f"n{i}" for i in range(N_NODES)]
    per_arm = {"fedqpnt_local": {"auc": [], "latency_on": []}, "baseline_b_cont": {"auc": [], "latency_on": []}}
    for seed in LIVE_SEEDS:
        local_seeds = {nid: _seeds_including_family(400_000 + seed * 100 + i * 1000, "abrupt", 6)
                       for i, nid in enumerate(node_ids)}
        for method, ids, join in (("fedqpnt_local", node_ids, {"n0": 5}), ("baseline_b_cont", ["n0"], {})):
            scenario = FleetScenarioConfig(
                scenario_id=f"h4_full_{method}_seed{seed}", method=method, seed=seed, node_ids=ids,
                n_rounds=N_ROUNDS, round_period_s=ROUND_PERIOD_S, duration_s=LIVE_DURATION_S,
                client_cfg=ClientConfig(min_samples=8, **CHOSEN), attacks={"n0": COLD_ATTACK}, join_round=join,
                local_train_seeds={nid: local_seeds[nid] for nid in ids},
                local_train_pool={nid: "mixed" for nid in ids}, local_train_duration_s=LOCAL_TRAIN_DURATION_S,
            )
            result = run_fleet(scenario, theta0, param_names)
            n0 = result.node_results.get("n0", {})
            print(f"[H4 {method} seed{seed}] aborted={result.aborted} auc={n0.get('auc')} "
                  f"latency_on={n0.get('latency_on')} installs={n0.get('round_installs')}")
            per_arm[method]["auc"].append(n0.get("auc"))
            per_arm[method]["latency_on"].append(n0.get("latency_on"))
    return {method: dict(auc=_ci95(v["auc"]), latency_on=_ci95(v["latency_on"])) for method, v in per_arm.items()}


def main():
    theta0, param_names = _theta0()
    print("=== H2 (novel-family generalisation: meaconing) ===")
    h2 = run_h2(theta0, param_names)
    print("=== H4 (cold-start) ===")
    h4 = run_h4(theta0, param_names)
    report = dict(chosen_hyperparams=CHOSEN, n_rounds=N_ROUNDS, live_seeds=LIVE_SEEDS,
                  live_duration_s=LIVE_DURATION_S, local_train_duration_s=LOCAL_TRAIN_DURATION_S,
                  h2=h2, h4=h4)
    Path("results/fleet/h2_h4_full_d054.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
