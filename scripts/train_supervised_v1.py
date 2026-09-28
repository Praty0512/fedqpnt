"""D-052: supervised detector training (primary path; pseudo-labelling
becomes an ablation). Labels = oracle AttackLabel, joined OFFLINE by
fedqpnt.training.build_supervised_dataset (see that module + the
tests/test_training_leakage_guard.py guard -- never inside Agent/
TrustEngineImpl at runtime).

Pipeline (real closed-loop runs, method=fixed_trust, kappa_R=40 PROVISIONAL):
  1. seeds 500-549, MIXED (1-in-5 clean, else cycling the 4 attack families),
     600s -> TRAIN pool. Retrain the frozen design (MLP, class-weight cap
     10x, D-050) directly on oracle labels.
  2. seeds 550-574, MIXED, natural ratio, 600s -> per-head Platt fit
     (logistic on logit(raw p)) against ORACLE labels.
  3. seeds 575-599, MIXED, disjoint, 600s -> per-family AUC (bootstrap CI),
     reliability curve + Brier, raw vs Platt-calibrated, vs ORACLE.
Saves results/m1/detector_weights_sup_v1.npz (+ platt_a/platt_b per head,
loaded by TrustDetector.set_params, applied at runtime by TrustDetector.score)
and results/m1/detector_train_sup_v1_report.json.

Usage: python scripts/train_supervised_v1.py [--workers 8]
"""
from __future__ import annotations

import argparse
import json
import subprocess as sp
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from fedqpnt.training.build_supervised_dataset import collect_run, run_pool, stack_dataset  # noqa: E402

TRAIN_SEEDS = list(range(500, 550))
PLATT_SEEDS = list(range(550, 575))
HELDOUT_SEEDS = list(range(575, 600))
POOL_DURATION_S = 600.0


def platt_fit(logits: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    from sklearn.linear_model import LogisticRegression
    if len(np.unique(labels)) < 2:
        return 1.0, 0.0
    lr = LogisticRegression(max_iter=1000)
    lr.fit(logits.reshape(-1, 1), labels)
    return float(lr.coef_[0, 0]), float(lr.intercept_[0])


def platt_apply(p_raw: np.ndarray, a: float, b: float) -> np.ndarray:
    eps = 1e-6
    z = np.log(np.clip(p_raw, eps, 1 - eps) / np.clip(1 - p_raw, eps, 1 - eps))
    return 1.0 / (1.0 + np.exp(-(a * z + b)))


def bootstrap_auc(scores, labels, n_boot=1000, seed=0):
    from sklearn.metrics import roc_auc_score
    rng_b = np.random.default_rng(seed)
    if len(np.unique(labels)) < 2:
        return float("nan"), (float("nan"), float("nan"))
    auc = roc_auc_score(labels, scores)
    boots = []
    n = len(labels)
    for _ in range(n_boot):
        idx = rng_b.integers(0, n, n)
        if len(np.unique(labels[idx])) < 2:
            continue
        boots.append(roc_auc_score(labels[idx], scores[idx]))
    lo, hi = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))) if boots else (float("nan"),) * 2
    return float(auc), (lo, hi)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    n_workers = min(args.workers, 8)

    from fedqpnt.trust.detector import TrustDetector
    from fedqpnt.core.seeding import stream

    t0 = time.time()

    # --- Step 1: TRAIN pool, oracle-labelled, retrain the frozen design ---
    jobs_train = [(s, "mixed", POOL_DURATION_S) for s in TRAIN_SEEDS]
    by_train = run_pool(jobs_train, n_workers)
    print(f"[{time.time()-t0:.0f}s] train pool collected")

    detector = TrustDetector(arch="mlp", seed=0)
    U_train, y_spoof_train, y_jam_train = stack_dataset(by_train, TRAIN_SEEDS, detector)
    n_pos_spoof = int(np.sum(y_spoof_train > 0))
    n_pos_jam = int(np.sum(y_jam_train > 0))
    rng = stream(0, "train_supervised_v1", "sgd")
    train_metrics = detector.train_local(U_train, y_spoof_train, y_jam_train, epochs=3, lr=0.05,
                                          batch_size=64, rng=rng, balance=True, max_pos_fraction=0.5)
    print(f"[{time.time()-t0:.0f}s] retrain done:", train_metrics,
          f"(oracle n_pos_spoof={n_pos_spoof}, n_pos_jam={n_pos_jam}, n_total={len(y_spoof_train)})")

    # --- Step 2: PLATT pool, oracle-labelled, natural ratio ---
    jobs_platt = [(s, "mixed", POOL_DURATION_S) for s in PLATT_SEEDS]
    by_platt = run_pool(jobs_platt, n_workers)
    print(f"[{time.time()-t0:.0f}s] platt pool collected")

    import torch

    def score_seed(seed_dict, seed):
        c = seed_dict[seed]
        from fedqpnt.trust.features import EwmaStack
        stack = EwmaStack()
        t = np.array(c["t"])
        p_spoof, p_jam = [], []
        for j in range(len(t)):
            raw = np.asarray(c["raw"][j], dtype=np.float64)
            xtilde = detector.normalizer.normalize(raw)
            u = stack.step(t[j], xtilde)
            with torch.no_grad():
                out = detector.model(torch.as_tensor(u, dtype=torch.float32)).numpy()
            p_spoof.append(float(out[0])); p_jam.append(float(out[1]))
        return dict(t=t, y_spoof=np.array(c["y_spoof"], dtype=float),
                    y_jam=np.array(c["y_jam"], dtype=float),
                    p_spoof=np.array(p_spoof), p_jam=np.array(p_jam), family=c["family"])

    platt_p_spoof, platt_y_spoof, platt_p_jam, platt_y_jam = [], [], [], []
    for s in PLATT_SEEDS:
        r = score_seed(by_platt, s)
        platt_p_spoof.append(r["p_spoof"]); platt_y_spoof.append(r["y_spoof"])
        platt_p_jam.append(r["p_jam"]); platt_y_jam.append(r["y_jam"])
    ps = np.concatenate(platt_p_spoof); ys = np.concatenate(platt_y_spoof)
    pj = np.concatenate(platt_p_jam); yj = np.concatenate(platt_y_jam)
    eps = 1e-6
    logit_s = np.log(np.clip(ps, eps, 1 - eps) / np.clip(1 - ps, eps, 1 - eps))
    logit_j = np.log(np.clip(pj, eps, 1 - eps) / np.clip(1 - pj, eps, 1 - eps))
    a_spoof, b_spoof = platt_fit(logit_s, ys)
    a_jam, b_jam = platt_fit(logit_j, yj)
    detector.platt_a_spoof, detector.platt_b_spoof = a_spoof, b_spoof
    detector.platt_a_jam, detector.platt_b_jam = a_jam, b_jam
    print(f"[{time.time()-t0:.0f}s] platt fit: spoof(a={a_spoof:.3f},b={b_spoof:.3f}) "
          f"jam(a={a_jam:.3f},b={b_jam:.3f})")

    # --- Step 3: HELDOUT eval ---
    jobs_ho = [(s, "mixed", POOL_DURATION_S) for s in HELDOUT_SEEDS]
    by_ho = run_pool(jobs_ho, n_workers)
    print(f"[{time.time()-t0:.0f}s] heldout pool collected")

    per_family_raw, per_family_cal, per_family_oracle = {}, {}, {}
    for s in HELDOUT_SEEDS:
        r = score_seed(by_ho, s)
        oracle = np.maximum(r["y_spoof"], r["y_jam"]).astype(bool)
        raw_score = np.maximum(r["p_spoof"], r["p_jam"])
        cal_score = np.maximum(platt_apply(r["p_spoof"], a_spoof, b_spoof),
                                platt_apply(r["p_jam"], a_jam, b_jam))
        per_family_raw.setdefault(r["family"], []).extend(raw_score.tolist())
        per_family_cal.setdefault(r["family"], []).extend(cal_score.tolist())
        per_family_oracle.setdefault(r["family"], []).extend(oracle.astype(float).tolist())

    auc_report = {}
    overall_raw, overall_cal, overall_oracle = [], [], []
    for family in per_family_raw:
        raw_a, raw_ci = bootstrap_auc(np.array(per_family_raw[family]), np.array(per_family_oracle[family]))
        cal_a, cal_ci = bootstrap_auc(np.array(per_family_cal[family]), np.array(per_family_oracle[family]))
        auc_report[family] = dict(auc_raw=raw_a, ci95_raw=list(raw_ci), auc_calibrated=cal_a,
                                   ci95_calibrated=list(cal_ci), n=len(per_family_raw[family]))
        overall_raw.extend(per_family_raw[family]); overall_cal.extend(per_family_cal[family])
        overall_oracle.extend(per_family_oracle[family])
    raw_a, raw_ci = bootstrap_auc(np.array(overall_raw), np.array(overall_oracle))
    cal_a, cal_ci = bootstrap_auc(np.array(overall_cal), np.array(overall_oracle))
    auc_report["overall"] = dict(auc_raw=raw_a, ci95_raw=list(raw_ci), auc_calibrated=cal_a,
                                  ci95_calibrated=list(cal_ci), n=len(overall_raw))

    overall_cal_arr = np.array(overall_cal); overall_oracle_arr = np.array(overall_oracle)
    brier = float(np.mean((overall_cal_arr - overall_oracle_arr) ** 2))
    brier_raw = float(np.mean((np.array(overall_raw) - overall_oracle_arr) ** 2))
    bins = np.linspace(0, 1, 11)
    reliability = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (overall_cal_arr >= lo) & (overall_cal_arr < hi)
        if m.sum() > 0:
            reliability.append(dict(bin_lo=float(lo), bin_hi=float(hi), n=int(m.sum()),
                                     mean_predicted=float(overall_cal_arr[m].mean()),
                                     empirical_rate=float(overall_oracle_arr[m].mean())))

    try:
        commit = sp.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        commit = "unknown"
    params = detector.get_params()
    out_path = ROOT / "results" / "m1" / "detector_weights_sup_v1.npz"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out_path, **{k: np.asarray(v) for k, v in params.items()})

    report = dict(
        label="kappa_R PROVISIONAL (D-046/D-047); tuning seeds; D-052 supervised (oracle-labelled) training",
        provenance=dict(config_hash=commit, method="fixed_trust", kappa_R=40.0,
                         seeds_train=TRAIN_SEEDS, seeds_platt=PLATT_SEEDS, seeds_heldout=HELDOUT_SEEDS,
                         pool_duration_s=POOL_DURATION_S, label_source="oracle AttackLabel (offline join, "
                         "fedqpnt/training/build_supervised_dataset.py)"),
        train_local_metrics=train_metrics,
        oracle_positive_counts=dict(n_pos_spoof=n_pos_spoof, n_pos_jam=n_pos_jam, n_total=len(y_spoof_train)),
        platt_params=dict(spoof=dict(a=a_spoof, b=b_spoof), jam=dict(a=a_jam, b=b_jam)),
        auc_raw_vs_calibrated=auc_report,
        brier_score_calibrated=brier, brier_score_raw=brier_raw,
        reliability_curve_calibrated=reliability,
        wall_s=time.time() - t0,
    )
    report_path = ROOT / "results" / "m1" / "detector_train_sup_v1_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf8")
    print(json.dumps(auc_report, indent=2))
    print(f"brier_calibrated={brier:.4f} brier_raw={brier_raw:.4f}")
    print(f"weights -> {out_path}")
    print(f"report -> {report_path}")


if __name__ == "__main__":
    main()
