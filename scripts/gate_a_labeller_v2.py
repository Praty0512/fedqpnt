"""D-051 sec A acceptance gate ONLY (labeller v2 sigma floors), run before
any retrain. Hard stop if it fails -- no iteration without the Master.

Pipeline (real closed-loop runs, method=fixed_trust, kappa_R=40 PROVISIONAL):
  1. seeds 500-519, CLEAN, 1800s -> reference mu/sd for the joint chi2_11
     negative rule (sigma floors are applied INSIDE label_epochs itself,
     fedqpnt/trust/pseudolabel.py::apply_sigma_floor, so this script does
     not need to floor anything explicitly).
  2. seeds 520-529, CLEAN, HELD OUT from the reference set, 600s ->
     clean-run positive-label rate (target <= 1%).
     PROPOSED-DECISION: the D-051 spec does not fix a duration for this
     check; 600s matches this project's existing pool-duration convention
     (scripts/recalibrate_and_retrain_v2.py POOL_DURATION_S).
  3. seeds 530-549, ATTACKED tuning missions ("mixed" pool -- 1-in-5 clean,
     else cycling the 4 attack families, same helper as the existing
     recalibration script), 600s -> pseudo-label precision vs oracle
     (target >= 0.8).
     PROPOSED-DECISION: seed range chosen disjoint from the held-out clean
     rate-check seeds (520-529) so the two gate numbers are never computed
     from the same epochs.

Reuses fedqpnt.node.agent/environment plumbing via
scripts/recalibrate_and_retrain_v2.py's collect_one/run_pool (no
duplication of the simulation-collection code).

Usage: python scripts/gate_a_labeller_v2.py [--workers 8]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from scripts.recalibrate_and_retrain_v2 import collect_one, run_pool, ref_stats  # noqa: E402

REF_SEEDS = list(range(500, 520))
REF_DURATION_S = 1800.0
RATE_SEEDS = list(range(520, 530))
RATE_DURATION_S = 600.0
PRECISION_SEEDS = list(range(530, 550))
PRECISION_DURATION_S = 600.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    n_workers = min(args.workers, 8)

    from fedqpnt.trust.pseudolabel import (
        PseudoLabelConfig, label_epochs, surrogate_s_cusum, pseudolabel_precision_recall,
    )

    t0 = time.time()

    jobs_ref = [(s, "clean", REF_DURATION_S) for s in REF_SEEDS]
    by_ref = run_pool(jobs_ref, n_workers)
    mu_new, sd_new = ref_stats(by_ref, REF_SEEDS)
    print(f"[{time.time()-t0:.0f}s] reference stats done (seeds {REF_SEEDS[0]}-{REF_SEEDS[-1]}, {REF_DURATION_S:.0f}s each)")

    jobs_rate = [(s, "clean", RATE_DURATION_S) for s in RATE_SEEDS]
    by_rate = run_pool(jobs_rate, n_workers)
    clean_pos_rates = []
    for s in RATE_SEEDS:
        c = by_rate[s]
        t = np.array(c["t"]); raw = np.array(c["raw"])
        raim = np.array(c["raim"]); nsat = np.array(c["nsat"])
        s_cusum = surrogate_s_cusum(raw)
        y = label_epochs(t, raw, raim, nsat, s_cusum, cfg=PseudoLabelConfig(),
                          quantile_mu=mu_new, quantile_sd=sd_new)
        clean_pos_rates.append(float(np.mean(y == 1.0)))
    clean_pos_rate = float(np.mean(clean_pos_rates))
    print(f"[{time.time()-t0:.0f}s] held-out clean rate done: {clean_pos_rate:.4f} "
          f"(per-seed {['%.4f' % r for r in clean_pos_rates]})")

    jobs_prec = [(s, "mixed", PRECISION_DURATION_S) for s in PRECISION_SEEDS]
    by_prec = run_pool(jobs_prec, n_workers)
    all_y, all_oracle = [], []
    for s in PRECISION_SEEDS:
        c = by_prec[s]
        t = np.array(c["t"]); raw = np.array(c["raw"])
        raim = np.array(c["raim"]); nsat = np.array(c["nsat"]); oracle = np.array(c["oracle"], dtype=bool)
        s_cusum = surrogate_s_cusum(raw)
        y = label_epochs(t, raw, raim, nsat, s_cusum, cfg=PseudoLabelConfig(),
                          quantile_mu=mu_new, quantile_sd=sd_new)
        keep = ~np.isnan(y)
        all_y.append(y[keep]); all_oracle.append(oracle[keep])
    pl_pr = pseudolabel_precision_recall(np.concatenate(all_y), np.concatenate(all_oracle))
    print(f"[{time.time()-t0:.0f}s] precision/recall done: {pl_pr}")

    gate_rate_pass = clean_pos_rate <= 0.01
    gate_precision_pass = (not np.isnan(pl_pr["precision"])) and pl_pr["precision"] >= 0.8
    gate_pass = gate_rate_pass and gate_precision_pass

    report = dict(
        label="D-051 sec A acceptance gate; tuning seeds; kappa_R PROVISIONAL (D-046/D-047)",
        seeds_ref=REF_SEEDS, seeds_rate=RATE_SEEDS, seeds_precision=PRECISION_SEEDS,
        ref_duration_s=REF_DURATION_S, rate_duration_s=RATE_DURATION_S,
        precision_duration_s=PRECISION_DURATION_S,
        reference_mu=mu_new.tolist(), reference_sd=sd_new.tolist(),
        clean_run_positive_label_rate=clean_pos_rate,
        clean_run_positive_label_rate_per_seed=clean_pos_rates,
        pseudolabel_precision_recall_vs_oracle=pl_pr,
        gate_rate_pass=bool(gate_rate_pass),
        gate_precision_pass=bool(gate_precision_pass),
        gate_pass=bool(gate_pass),
        wall_s=time.time() - t0,
    )
    out_path = ROOT / "results" / "m1" / "gate_a_labeller_v2.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf8")
    print(json.dumps({k: v for k, v in report.items() if k not in
                       ("reference_mu", "reference_sd")}, indent=2))
    print(f"GATE_PASS={gate_pass}")
    print(f"report -> {out_path}")


if __name__ == "__main__":
    main()
