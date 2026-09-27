"""SS6.1 S5/S8/S9/S12/S15 validation runs + AUC-per-round report + wall-time
report for N in {5, 10}. Real multiprocessing (spawn) runs, seeds 500-599
only, per the FEDERATED agent's task brief. Not part of the pytest suite
(too slow for CI); run directly: python scripts/run_fl_validate.py.

All AUC numbers are PROVISIONAL -- synthetic-innovation features (pre-M1
integration), per ARCHITECTURE.md SS4.3.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from sklearn.metrics import roc_auc_score

from fedqpnt.trust.detector import TrustDetector
from fedqpnt.fl.orchestrator import ScenarioConfig, run_federation
from fedqpnt.fl.client import ClientConfig
from fedqpnt.fl.comms import CommsConfig
from tests._fl_harness import make_provider, held_out_eval_set

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "fl"
# NOTE: tests/_trust_harness attacks default onset_s=20.0 -- a mission
# duration_s<=20 ends before any attack ever starts, giving zero positive
# oracle labels (found via a real bug: every AUC below came back NaN until
# this was raised past 20). 45s gives each attacked run ~25s of active
# attack to score against.
DURATION_S = 45.0


def _theta0():
    d = TrustDetector(arch="mlp", seed=0)
    theta0 = d.get_params()
    return theta0, list(theta0.keys())


def _score_theta_on_eval_set(theta: dict, eval_runs) -> dict:
    """Evaluator-only AUC on the fixed held-out set (oracle labels)."""
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
        return {"auc": float("nan"), "n": len(oracle)}
    return {"auc": float(roc_auc_score(oracle, scores)), "n": len(oracle)}


def _run_and_score(scenario, provider, theta0, param_names, eval_runs, label):
    t0 = time.monotonic()
    result = run_federation(scenario, provider, theta0, param_names)
    wall = time.monotonic() - t0
    score = _score_theta_on_eval_set(result.final_theta, eval_runs) if not result.aborted else {"auc": float("nan")}
    print(f"[{label}] aborted={result.aborted} wall_s={wall:.1f} "
          f"rounds_skipped={sum(1 for e in result.server_log if e['event']=='ROUND_SKIPPED')} "
          f"auc={score['auc']:.4f}" if not np.isnan(score.get("auc", float('nan'))) else
          f"[{label}] aborted={result.aborted} wall_s={wall:.1f} auc=nan reason={result.abort_reason}")
    return result, wall, score


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    theta0, param_names = _theta0()
    eval_runs = held_out_eval_set(duration_s=DURATION_S)
    report = {}

    # --- wall time per round for N=5, N=10 -----------------------------
    for n in (5, 10):
        node_ids = [f"n{i}" for i in range(n)]
        provider = make_provider(base_seed=520, duration_s=DURATION_S)
        n_rounds = 6
        scenario = ScenarioConfig(node_ids=node_ids, n_rounds=n_rounds, seed=520 + n,
                                   aggregator="trim_nb_r", client_cfg=ClientConfig(min_samples=16))
        result, wall, score = _run_and_score(scenario, provider, theta0, param_names, eval_runs, f"wall-time N={n}")
        report[f"wall_time_N{n}"] = {"total_s": wall, "per_round_s": wall / n_rounds,
                                      "round_wall_s": result.round_wall_s}

    # --- AUC per round: FedAvg vs TRIM-NB-R vs local-only ----------------
    node_ids = [f"n{i}" for i in range(8)]
    n_rounds = 10
    provider = make_provider(base_seed=530, duration_s=DURATION_S)
    auc_per_round = {"fedavg": [], "trim_nb_r": [], "local_only": []}
    for agg_name in ("fedavg", "trim_nb_r"):
        theta_running = {k: v.copy() for k, v in theta0.items()}
        for r in range(1, n_rounds + 1):
            scenario = ScenarioConfig(node_ids=node_ids, n_rounds=r, seed=530, aggregator=agg_name,
                                       client_cfg=ClientConfig(min_samples=16))
            result = run_federation(scenario, provider, theta0, param_names)
            if result.aborted:
                auc_per_round[agg_name].append(float("nan"))
                continue
            score = _score_theta_on_eval_set(result.final_theta, eval_runs)
            auc_per_round[agg_name].append(score["auc"])
    # local-only baseline: one node trains alone for n_rounds "epochs" (no FL)
    from fedqpnt.fl.client import FLClient
    detector = TrustDetector(arch="mlp", seed=0)
    client = FLClient("solo", provider, detector, ClientConfig(min_samples=16))
    for r in range(n_rounds):
        client.local_round(r)
        score = _score_theta_on_eval_set(client.detector.get_params(), eval_runs)
        auc_per_round["local_only"].append(score["auc"])
    report["auc_per_round"] = auc_per_round
    print("[AUC per round] (PROVISIONAL)", json.dumps(auc_per_round, indent=2))

    # --- S12: poisoning f in {20%, 40%} -----------------------------------
    s12 = {}
    node_ids = [f"n{i}" for i in range(10)]
    provider = make_provider(base_seed=540, duration_s=DURATION_S)
    n_rounds = 8
    clean_scenario = ScenarioConfig(node_ids=node_ids, n_rounds=n_rounds, seed=540, aggregator="trim_nb_r",
                                     client_cfg=ClientConfig(min_samples=16))
    clean_result = run_federation(clean_scenario, provider, theta0, param_names)
    clean_auc = _score_theta_on_eval_set(clean_result.final_theta, eval_runs)["auc"]
    for f in (0.2, 0.4):
        n_mal = max(int(f * len(node_ids)), 1)
        poison = {node_ids[i]: "sign_flip" for i in range(n_mal)}
        for agg_name in ("trim_nb_r", "fedavg"):
            scenario = ScenarioConfig(node_ids=node_ids, n_rounds=n_rounds, seed=540, aggregator=agg_name,
                                       client_cfg=ClientConfig(min_samples=16), poison_kind=poison)
            result = run_federation(scenario, provider, theta0, param_names)
            auc = _score_theta_on_eval_set(result.final_theta, eval_runs)["auc"] if not result.aborted else float("nan")
            s12[f"f{f}_{agg_name}"] = {"auc": auc, "drop_vs_clean": clean_auc - auc}
    s12["clean_auc"] = clean_auc
    report["s12"] = s12
    print("[S12]", json.dumps(s12, indent=2))

    with open(RESULTS_DIR / "fl_validation_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nWrote {RESULTS_DIR / 'fl_validation_report.json'}")


if __name__ == "__main__":
    main()
