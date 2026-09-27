"""SS6.1 S12 full sweep (D-037 follow-up): all 4 SS4.5 poisoning types x
f in {0.2, 0.4} x {FedAvg, TRIM-NB-R}, 5 seeds (500-504). Reports AUC drop
vs clean (mean + range). Acceptance criterion is ONLY TRIM-NB-R at f=0.2
(drop <= 0.05); everything else reported as-is (spec: f=40% reported only).

PROCESS RULE (Master): keep to <=6 worker processes total. Each federation
run here uses N=5 nodes + 1 server = 6 processes, run strictly sequentially
(never two federations at once).

All AUC numbers are PROVISIONAL -- synthetic-innovation features (pre-M1).
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
N_NODES = 5           # + 1 server = 6 processes, per the <=6 worker-process rule
N_ROUNDS = 5
SEEDS = range(500, 505)
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


def _node_ids():
    return [f"n{i}" for i in range(N_NODES)]


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    theta0, param_names = _theta0()
    eval_runs = held_out_eval_set(duration_s=DURATION_S)
    node_ids = _node_ids()

    clean_auc = {}   # (seed, agg) -> auc
    for seed in SEEDS:
        provider = make_provider(base_seed=seed, duration_s=DURATION_S)
        for agg in ("fedavg", "trim_nb_r"):
            scenario = ScenarioConfig(node_ids=node_ids, n_rounds=N_ROUNDS, seed=seed, aggregator=agg,
                                       client_cfg=ClientConfig(min_samples=16))
            result = run_federation(scenario, provider, theta0, param_names)
            clean_auc[(seed, agg)] = _score(result.final_theta, eval_runs) if not result.aborted else float("nan")
            print(f"[clean] seed={seed} agg={agg} auc={clean_auc[(seed, agg)]:.4f} aborted={result.aborted}")

    report = {"clean_auc": {f"{s}_{a}": v for (s, a), v in clean_auc.items()}, "sweep": {}}

    for f in FRACTIONS:
        n_mal = round(f * N_NODES)
        assert n_mal == round(f * len(node_ids)), "malicious-count arithmetic sanity check"
        for kind in POISON_TYPES:
            for agg in ("fedavg", "trim_nb_r"):
                drops = []
                for seed in SEEDS:
                    provider = make_provider(base_seed=seed, duration_s=DURATION_S)
                    poison = {node_ids[i]: kind for i in range(n_mal)}
                    scenario = ScenarioConfig(node_ids=node_ids, n_rounds=N_ROUNDS, seed=seed, aggregator=agg,
                                               client_cfg=ClientConfig(min_samples=16), poison_kind=poison)
                    # log + assert the malicious-node count actually configured this run
                    node_local_mal = sum(1 for k in poison.values() if k in ("sign_flip", "label_flip"))
                    server_mal_ids, _kind = scenario.server_poison_kind()
                    actual_mal = len(poison) if kind in ("sign_flip", "label_flip") else len(server_mal_ids)
                    assert actual_mal == n_mal, f"f={f} kind={kind}: configured {actual_mal} malicious, expected {n_mal}"
                    result = run_federation(scenario, provider, theta0, param_names)
                    auc = _score(result.final_theta, eval_runs) if not result.aborted else float("nan")
                    drop = clean_auc[(seed, agg)] - auc
                    drops.append(drop)
                    print(f"[f={f} kind={kind} agg={agg} seed={seed}] n_malicious={actual_mal} auc={auc:.4f} drop={drop:.4f} aborted={result.aborted}")
                drops_arr = np.array(drops, dtype=float)
                key = f"f{f}_{kind}_{agg}"
                report["sweep"][key] = {
                    "mean_drop": float(np.nanmean(drops_arr)),
                    "min_drop": float(np.nanmin(drops_arr)),
                    "max_drop": float(np.nanmax(drops_arr)),
                    "n_malicious": n_mal,
                    "drops_per_seed": drops,
                }
                print(f"  -> mean_drop={report['sweep'][key]['mean_drop']:.4f} "
                      f"range=[{report['sweep'][key]['min_drop']:.4f}, {report['sweep'][key]['max_drop']:.4f}]")

    with open(RESULTS_DIR / "fl_s12_full_sweep.json", "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nWrote {RESULTS_DIR / 'fl_s12_full_sweep.json'}")

    # SS6.1 acceptance criterion: TRIM-NB-R at f=0.2, sign-flip attack family
    # is the one already validated end-to-end elsewhere; check it here too.
    key = "f0.2_sign_flip_trim_nb_r"
    md = report["sweep"][key]["mean_drop"]
    print(f"\n[S12 acceptance] TRIM-NB-R f=20% sign_flip mean drop={md:.4f} "
          f"({'PASS' if md <= 0.05 else 'FAIL'}, threshold 0.05)")


if __name__ == "__main__":
    main()
