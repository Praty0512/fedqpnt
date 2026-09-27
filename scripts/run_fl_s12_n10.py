"""SS6.1 S12 full sweep at the SPEC fleet size (D-039 follow-up): N=10 nodes
(11 processes per run -- OK per Master, but federations run STRICTLY
SEQUENTIALLY, never concurrent), 4 SS4.5 poisoning types x f in {0.2,0.4} x
{FedAvg, TRIM-NB-R}, 10 seeds (500-509). Reports mean AUC drop vs clean with
a 95% percentile bootstrap CI over the 10 per-seed drops. Acceptance
criterion is TRIM-NB-R at f=0.2 (<=0.05), reported whatever the outcome.

All AUC numbers PROVISIONAL (synthetic-innovation features, pre-M1).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from sklearn.metrics import roc_auc_score

from fedqpnt.trust.detector import TrustDetector
from fedqpnt.fl.orchestrator import ScenarioConfig, run_federation
from fedqpnt.fl.client import ClientConfig
from tests._fl_harness import make_provider, held_out_eval_set

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "fl"
DURATION_S = 45.0
N_NODES = 10
N_ROUNDS = 4
SEEDS = range(500, 510)
POISON_TYPES = ("sign_flip", "label_flip", "gaussian_noise", "alie")
FRACTIONS = (0.2, 0.4)


def _theta0():
    d = TrustDetector(arch="mlp", seed=0)
    theta0 = d.get_params()
    return theta0, list(theta0.keys())


def _score(theta, eval_runs):
    detector = TrustDetector(arch="mlp", seed=0)
    detector.set_params(theta)
    scores, oracle = [], []
    for run in eval_runs:
        detector.reset_stream()
        for k in range(len(run.t)):
            p_spoof, p_jam, _u = detector.score(run.t[k], run.raw_features[k])
            scores.append(max(p_spoof, p_jam))
            oracle.append(run.oracle_active[k])
    oracle = np.asarray(oracle, dtype=bool)
    if len(np.unique(oracle)) < 2:
        return float("nan")
    return float(roc_auc_score(oracle, scores))


def _bootstrap_ci(drops, n_boot=2000, seed=0):
    drops = np.asarray(drops, dtype=float)
    drops = drops[np.isfinite(drops)]
    if len(drops) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    boots = [np.mean(rng.choice(drops, size=len(drops), replace=True)) for _ in range(n_boot)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(lo), float(hi)


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    theta0, param_names = _theta0()
    eval_runs = held_out_eval_set(duration_s=DURATION_S)
    node_ids = [f"n{i}" for i in range(N_NODES)]

    clean_auc = {}
    for seed in SEEDS:
        provider = make_provider(base_seed=seed, duration_s=DURATION_S)
        for agg in ("fedavg", "trim_nb_r"):
            scenario = ScenarioConfig(node_ids=node_ids, n_rounds=N_ROUNDS, seed=seed, aggregator=agg,
                                       client_cfg=ClientConfig(min_samples=16))
            result = run_federation(scenario, provider, theta0, param_names)
            clean_auc[(seed, agg)] = _score(result.final_theta, eval_runs) if not result.aborted else float("nan")
            print(f"[clean] seed={seed} agg={agg} auc={clean_auc[(seed, agg)]:.4f} aborted={result.aborted}")

    report = {"n_nodes": N_NODES, "n_rounds": N_ROUNDS, "seeds": list(SEEDS),
              "clean_auc": {f"{s}_{a}": v for (s, a), v in clean_auc.items()}, "sweep": {}}

    for f in FRACTIONS:
        n_mal = round(f * N_NODES)
        for kind in POISON_TYPES:
            for agg in ("fedavg", "trim_nb_r"):
                drops = []
                for seed in SEEDS:
                    provider = make_provider(base_seed=seed, duration_s=DURATION_S)
                    poison = {node_ids[i]: kind for i in range(n_mal)}
                    scenario = ScenarioConfig(node_ids=node_ids, n_rounds=N_ROUNDS, seed=seed, aggregator=agg,
                                               client_cfg=ClientConfig(min_samples=16), poison_kind=poison)
                    server_mal_ids, _k = scenario.server_poison_kind()
                    actual_mal = len(poison) if kind in ("sign_flip", "label_flip") else len(server_mal_ids)
                    assert actual_mal == n_mal, f"f={f} kind={kind}: configured {actual_mal}, expected {n_mal}"
                    result = run_federation(scenario, provider, theta0, param_names)
                    auc = _score(result.final_theta, eval_runs) if not result.aborted else float("nan")
                    drop = clean_auc[(seed, agg)] - auc
                    drops.append(drop)
                    print(f"[f={f} kind={kind} agg={agg} seed={seed}] n_malicious={actual_mal} "
                          f"auc={auc:.4f} drop={drop:.4f} aborted={result.aborted}")
                lo, hi = _bootstrap_ci(drops)
                key = f"f{f}_{kind}_{agg}"
                report["sweep"][key] = {"mean_drop": float(np.nanmean(drops)), "ci95": [lo, hi],
                                         "n_malicious": n_mal, "drops_per_seed": drops}
                print(f"  -> mean_drop={report['sweep'][key]['mean_drop']:.4f} 95% CI=[{lo:.4f}, {hi:.4f}]")

    with open(RESULTS_DIR / "fl_s12_n10_sweep.json", "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nWrote {RESULTS_DIR / 'fl_s12_n10_sweep.json'}")

    key = "f0.2_sign_flip_trim_nb_r"
    md = report["sweep"][key]["mean_drop"]
    lo, hi = report["sweep"][key]["ci95"]
    print(f"\n[S12 acceptance @ N=10] TRIM-NB-R f=20% sign_flip mean drop={md:.4f} "
          f"95% CI=[{lo:.4f},{hi:.4f}] -> {'PASS' if md <= 0.05 else 'FAIL'} (threshold 0.05)")


if __name__ == "__main__":
    main()
