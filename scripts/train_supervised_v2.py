"""D-053a supervised detector retrain: rebalanced training mix (6 families:
drift, meaconing, abrupt, jam_cw, jam_wideband, jam_then_spoof -- was 4, with
jamming severities now spanning the J/S range via
``fedqpnt.training.build_supervised_dataset.JAM_SEVERITIES``, partial (fix
stays valid) through full denial). Same design as train_supervised_v1.py
(frozen per D-051/D-026: MLP arch, class-weight cap 10x, per-head Platt) --
only the training MISSION MIX changes (D-053a scope). Adds: per-family
positive-epoch counts (train pool, to evidence the >=500/family target) and
a per-head (spoof vs jam) AUC breakdown alongside the combined head.

Pipeline (real closed-loop runs, method=fixed_trust, kappa_R=40 PROVISIONAL):
  1. seeds 500-549 -> TRAIN pool (retrain frozen design on oracle labels).
  2. seeds 550-574 -> PLATT pool (per-head Platt fit against oracle labels).
  3. seeds 575-599 -> HELDOUT pool (per-family AUC w/ bootstrap CI, Brier,
     reliability curve, per-head breakdown).
Saves results/m1/detector_weights_sup_v2.npz and
results/m1/detector_train_sup_v2_report.json.

Usage: python scripts/train_supervised_v2.py [--workers 8]
"""
from __future__ import annotations

import argparse
import json
import subprocess as sp
import sys
import time
from collections import Counter
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

    # Per-family positive-epoch counts (evidences the D-053a >=500/family
    # rebalance target BEFORE any normalizer/EWMA stacking).
    family_pos_counts: dict[str, dict[str, int]] = {}
    family_seed_counts: Counter = Counter()
    for s in TRAIN_SEEDS:
        c = by_train[s]
        family_seed_counts[c["family"]] += 1
        d = family_pos_counts.setdefault(c["family"], dict(n_pos_spoof=0, n_pos_jam=0, n_epochs=0))
        d["n_pos_spoof"] += int(sum(c["y_spoof"]))
        d["n_pos_jam"] += int(sum(c["y_jam"]))
        d["n_epochs"] += len(c["t"])
    print("[train pool] per-family positive-epoch counts:", json.dumps(family_pos_counts, indent=2))
    print("[train pool] seeds per family:", dict(family_seed_counts))

    detector = TrustDetector(arch="mlp", seed=0)
    U_train, y_spoof_train, y_jam_train = stack_dataset(by_train, TRAIN_SEEDS, detector)
    n_pos_spoof = int(np.sum(y_spoof_train > 0))
    n_pos_jam = int(np.sum(y_jam_train > 0))
    rng = stream(0, "train_supervised_v2", "sgd")
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
    per_family_p_spoof, per_family_y_spoof = {}, {}
    per_family_p_jam, per_family_y_jam = {}, {}
    for s in HELDOUT_SEEDS:
        r = score_seed(by_ho, s)
        oracle = np.maximum(r["y_spoof"], r["y_jam"]).astype(bool)
        cal_spoof = platt_apply(r["p_spoof"], a_spoof, b_spoof)
        cal_jam = platt_apply(r["p_jam"], a_jam, b_jam)
        raw_score = np.maximum(r["p_spoof"], r["p_jam"])
        cal_score = np.maximum(cal_spoof, cal_jam)
        fam = r["family"]
        per_family_raw.setdefault(fam, []).extend(raw_score.tolist())
        per_family_cal.setdefault(fam, []).extend(cal_score.tolist())
        per_family_oracle.setdefault(fam, []).extend(oracle.astype(float).tolist())
        per_family_p_spoof.setdefault(fam, []).extend(cal_spoof.tolist())
        per_family_y_spoof.setdefault(fam, []).extend(r["y_spoof"].tolist())
        per_family_p_jam.setdefault(fam, []).extend(cal_jam.tolist())
        per_family_y_jam.setdefault(fam, []).extend(r["y_jam"].tolist())

    auc_report = {}
    overall_raw, overall_cal, overall_oracle = [], [], []
    overall_p_spoof, overall_y_spoof, overall_p_jam, overall_y_jam = [], [], [], []
    for family in per_family_raw:
        raw_a, raw_ci = bootstrap_auc(np.array(per_family_raw[family]), np.array(per_family_oracle[family]))
        cal_a, cal_ci = bootstrap_auc(np.array(per_family_cal[family]), np.array(per_family_oracle[family]))
        spoof_a, spoof_ci = bootstrap_auc(np.array(per_family_p_spoof[family]), np.array(per_family_y_spoof[family]))
        jam_a, jam_ci = bootstrap_auc(np.array(per_family_p_jam[family]), np.array(per_family_y_jam[family]))
        auc_report[family] = dict(
            auc_raw=raw_a, ci95_raw=list(raw_ci), auc_calibrated=cal_a, ci95_calibrated=list(cal_ci),
            auc_head_spoof=spoof_a, ci95_head_spoof=list(spoof_ci),
            auc_head_jam=jam_a, ci95_head_jam=list(jam_ci),
            n=len(per_family_raw[family]),
            n_pos_spoof=int(sum(per_family_y_spoof[family])), n_pos_jam=int(sum(per_family_y_jam[family])),
        )
        overall_raw.extend(per_family_raw[family]); overall_cal.extend(per_family_cal[family])
        overall_oracle.extend(per_family_oracle[family])
        overall_p_spoof.extend(per_family_p_spoof[family]); overall_y_spoof.extend(per_family_y_spoof[family])
        overall_p_jam.extend(per_family_p_jam[family]); overall_y_jam.extend(per_family_y_jam[family])
    raw_a, raw_ci = bootstrap_auc(np.array(overall_raw), np.array(overall_oracle))
    cal_a, cal_ci = bootstrap_auc(np.array(overall_cal), np.array(overall_oracle))
    spoof_a, spoof_ci = bootstrap_auc(np.array(overall_p_spoof), np.array(overall_y_spoof))
    jam_a, jam_ci = bootstrap_auc(np.array(overall_p_jam), np.array(overall_y_jam))
    auc_report["overall"] = dict(
        auc_raw=raw_a, ci95_raw=list(raw_ci), auc_calibrated=cal_a, ci95_calibrated=list(cal_ci),
        auc_head_spoof=spoof_a, ci95_head_spoof=list(spoof_ci),
        auc_head_jam=jam_a, ci95_head_jam=list(jam_ci), n=len(overall_raw),
        n_pos_spoof=int(sum(overall_y_spoof)), n_pos_jam=int(sum(overall_y_jam)),
    )

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
    out_path = ROOT / "results" / "m1" / "detector_weights_sup_v2.npz"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out_path, **{k: np.asarray(v) for k, v in params.items()})

    report = dict(
        label="kappa_R PROVISIONAL (D-046/D-047); tuning seeds; D-053a rebalanced-mix "
              "supervised (oracle-labelled) training (frozen design per D-051/D-026)",
        provenance=dict(config_hash=commit, method="fixed_trust", kappa_R=40.0,
                         seeds_train=TRAIN_SEEDS, seeds_platt=PLATT_SEEDS, seeds_heldout=HELDOUT_SEEDS,
                         pool_duration_s=POOL_DURATION_S, label_source="oracle AttackLabel (offline join, "
                         "fedqpnt/training/build_supervised_dataset.py)",
                         families=["drift", "meaconing", "abrupt", "jam_cw", "jam_wideband", "jam_then_spoof"]),
        train_pool_family_positive_counts=family_pos_counts,
        train_pool_family_seed_counts=dict(family_seed_counts),
        train_local_metrics=train_metrics,
        oracle_positive_counts=dict(n_pos_spoof=n_pos_spoof, n_pos_jam=n_pos_jam, n_total=len(y_spoof_train)),
        platt_params=dict(spoof=dict(a=a_spoof, b=b_spoof), jam=dict(a=a_jam, b=b_jam)),
        auc_raw_vs_calibrated=auc_report,
        brier_score_calibrated=brier, brier_score_raw=brier_raw,
        reliability_curve_calibrated=reliability,
        wall_s=time.time() - t0,
    )
    report_path = ROOT / "results" / "m1" / "detector_train_sup_v2_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf8")
    print(json.dumps(auc_report, indent=2))
    print(f"brier_calibrated={brier:.4f} brier_raw={brier_raw:.4f}")
    print(f"weights -> {out_path}")
    print(f"report -> {report_path}")


if __name__ == "__main__":
    main()
