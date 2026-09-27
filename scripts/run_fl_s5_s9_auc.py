"""SS6.1 S5/S9 missing numeric criteria (Master D-037 follow-up):
S5: final AUC >= AUC(no failure) - 0.02
S9: final AUC >= no-loss AUC - 0.03
5 seeds (500-504), N=5 nodes + 1 server = 6 processes (PROCESS RULE), run
strictly sequentially. All AUC PROVISIONAL (synthetic-innovation features).
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
from fedqpnt.fl.comms import CommsConfig
from tests._fl_harness import make_provider, held_out_eval_set

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "fl"
DURATION_S = 45.0
N_NODES = 5
N_ROUNDS = 6
SEEDS = range(500, 505)


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


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    theta0, param_names = _theta0()
    eval_runs = held_out_eval_set(duration_s=DURATION_S)
    node_ids = [f"n{i}" for i in range(N_NODES)]
    report = {"S5": {}, "S9": {}}

    # --- S5: 30% node failure at T/2 vs no-failure baseline -----------------
    no_fail_aucs, fail_aucs = [], []
    t_half = N_ROUNDS // 2
    failure_round = {node_ids[0]: t_half}   # 1/5 = 20% (nearest to 30% at this N)
    for seed in SEEDS:
        provider = make_provider(base_seed=seed, duration_s=DURATION_S)
        base = ScenarioConfig(node_ids=node_ids, n_rounds=N_ROUNDS, seed=seed, aggregator="trim_nb_r",
                               client_cfg=ClientConfig(min_samples=16))
        fail = ScenarioConfig(node_ids=node_ids, n_rounds=N_ROUNDS, seed=seed, aggregator="trim_nb_r",
                               client_cfg=ClientConfig(min_samples=16), failure_round=failure_round)
        r_base = run_federation(base, provider, theta0, param_names)
        r_fail = run_federation(fail, provider, theta0, param_names)
        a_base = _score(r_base.final_theta, eval_runs) if not r_base.aborted else float("nan")
        a_fail = _score(r_fail.final_theta, eval_runs) if not r_fail.aborted else float("nan")
        no_fail_aucs.append(a_base)
        fail_aucs.append(a_fail)
        print(f"[S5] seed={seed} no_failure_auc={a_base:.4f} failure_auc={a_fail:.4f} "
              f"drop={a_base - a_fail:.4f} aborted(base/fail)={r_base.aborted}/{r_fail.aborted}")
    mean_base, mean_fail = float(np.nanmean(no_fail_aucs)), float(np.nanmean(fail_aucs))
    s5_drop = mean_base - mean_fail
    report["S5"] = {"no_failure_auc_mean": mean_base, "failure_auc_mean": mean_fail, "drop": s5_drop,
                     "pass": bool(s5_drop <= 0.02), "no_failure_aucs": no_fail_aucs, "failure_aucs": fail_aucs}
    print(f"[S5] mean no-failure AUC={mean_base:.4f}, mean failure AUC={mean_fail:.4f}, "
          f"drop={s5_drop:.4f} ({'PASS' if s5_drop <= 0.02 else 'FAIL'}, threshold 0.02)")

    # --- S9: comms loss (loss_B=0.9, P(G->B)=0.1, worse cell) vs no-loss ----
    no_loss_aucs, loss_aucs = [], []
    lossy_comms = CommsConfig(p_gb=0.1, loss_b=0.9)
    for seed in SEEDS:
        provider = make_provider(base_seed=seed, duration_s=DURATION_S)
        base = ScenarioConfig(node_ids=node_ids, n_rounds=N_ROUNDS, seed=seed, aggregator="trim_nb_r",
                               client_cfg=ClientConfig(min_samples=16), comms_cfg=CommsConfig(p_gb=0.0, loss_b=0.0))
        lossy = ScenarioConfig(node_ids=node_ids, n_rounds=N_ROUNDS, seed=seed, aggregator="trim_nb_r",
                                client_cfg=ClientConfig(min_samples=16), comms_cfg=lossy_comms)
        r_base = run_federation(base, provider, theta0, param_names)
        r_loss = run_federation(lossy, provider, theta0, param_names)
        a_base = _score(r_base.final_theta, eval_runs) if not r_base.aborted else float("nan")
        a_loss = _score(r_loss.final_theta, eval_runs) if not r_loss.aborted else float("nan")
        no_loss_aucs.append(a_base)
        loss_aucs.append(a_loss)
        print(f"[S9] seed={seed} no_loss_auc={a_base:.4f} lossy_auc={a_loss:.4f} "
              f"drop={a_base - a_loss:.4f} aborted(base/lossy)={r_base.aborted}/{r_loss.aborted}")
    mean_base, mean_loss = float(np.nanmean(no_loss_aucs)), float(np.nanmean(loss_aucs))
    s9_drop = mean_base - mean_loss
    report["S9"] = {"no_loss_auc_mean": mean_base, "lossy_auc_mean": mean_loss, "drop": s9_drop,
                     "pass": bool(s9_drop <= 0.03), "no_loss_aucs": no_loss_aucs, "lossy_aucs": loss_aucs}
    print(f"[S9] mean no-loss AUC={mean_base:.4f}, mean lossy AUC={mean_loss:.4f}, "
          f"drop={s9_drop:.4f} ({'PASS' if s9_drop <= 0.03 else 'FAIL'}, threshold 0.03)")

    with open(RESULTS_DIR / "fl_s5_s9_auc.json", "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nWrote {RESULTS_DIR / 'fl_s5_s9_auc.json'}")


if __name__ == "__main__":
    main()
