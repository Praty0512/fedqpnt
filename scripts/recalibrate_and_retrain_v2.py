"""D-049 (Master ruling): recalibrate the pseudo-labeller's nominal
reference statistics on REAL clean closed-loop runs (data-derived constants,
allowed under the D-026 design freeze), retrain the SAME frozen detector
design on the relabelled data, and add Platt (output) calibration per head.

Pipeline (seeds 500-599 only, ground/industrial_mems/FIELD CAI,
method="fixed_trust", kappa_R=40 PROVISIONAL):
  1. seeds 500-519, CLEAN ONLY, 1800s (>=30 min) -> NEW quantile_mu/sd
     reference for the joint chi2_11 negative rule + the D-024 xsat/cn0
     positive rule. Reports NEW vs OLD (same seeds, 300s, the value used by
     scripts/retrain_detector_real.py) side by side.
  2. seeds 520-549, MIXED (1-in-5 clean, else cycle 4 attack families),
     600s -> relabelled with the NEW reference -> pseudo-label
     precision/recall vs oracle (evaluator-only) + clean-run positive rate.
  3. Retrain the frozen design (xsat rule on, balance on) on the relabelled
     520-549 data.
  4. seeds 550-574, MIXED at the SAME natural (mostly-clean) ratio, 600s ->
     fit per-head Platt scaling (logistic on logit(raw p)) against
     PSEUDO-labels (never the oracle -- the oracle stays evaluator-only).
  5. seeds 575-599, MIXED, 600s, held out -> per-family AUC (bootstrap CI),
     reliability curve + Brier score, evaluated against the ORACLE, for
     both raw and Platt-calibrated scores.
Saves results/m1/detector_weights_real_v2.npz (+ platt_a/platt_b per head)
and results/m1/detector_retrain_v2_report.json.

Usage: python scripts/recalibrate_and_retrain_v2.py [--workers 6]
"""
from __future__ import annotations

import argparse
import json
import subprocess as sp
import sys
import time
from pathlib import Path
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

G0 = 9.80665
HOLD_S = 30.0

FAMILY_ATTACKS = [
    ("drift", dict(kind="drift_spoof", onset_s=60.0, duration_s=180.0, severity=0.5)),
    ("meaconing", dict(kind="meaconing", onset_s=60.0, duration_s=180.0, severity=0.5)),
    ("abrupt", dict(kind="abrupt_spoof", onset_s=60.0, duration_s=180.0, severity=0.5)),
    ("jamming", dict(kind="jam_cw", onset_s=60.0, duration_s=180.0, severity=0.5)),
]

CLEAN_CALIB_SEEDS = list(range(500, 520))   # 20 clean-only, >=30 min, new reference
OLD_CALIB_DURATION_S = 300.0                # matches scripts/retrain_detector_real.py's old reference
NEW_CALIB_DURATION_S = 1800.0               # Master: ">= 30 min each"
TRAIN_SEEDS = list(range(520, 550))         # 30 mixed, relabel + retrain
PLATT_SEEDS = list(range(550, 575))         # 25 mixed (natural ratio), Platt fit
HELDOUT_SEEDS = list(range(575, 600))       # 25 mixed, disjoint, final eval
POOL_DURATION_S = 600.0


def _level_att(f_b_mean: np.ndarray) -> tuple[float, float]:
    fx, fy, fz = f_b_mean
    phi = float(np.arctan2(fy, fz))
    theta = float(np.arctan2(-fx, np.sqrt(fy ** 2 + fz ** 2)))
    return phi, theta


def _plan_for(seed: int, pool: str) -> tuple[str, dict | None]:
    if pool == "clean":
        return "clean", None
    idx = seed % 5
    if idx == 0:
        return "clean", None
    return FAMILY_ATTACKS[(seed // 5) % 4]


def collect_one(args: tuple[int, str, float]) -> dict:
    seed, pool, duration_s = args
    from fedqpnt.node.agent import Agent
    from fedqpnt.node.environment import EnvConfig, NodeEnvironment
    from fedqpnt.node.methods import make_agent_config

    family, atk = _plan_for(seed, pool)
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=HOLD_S,
                         heading_noise_deg=2.0, attacks=[atk] if atk else [])
    env = NodeEnvironment(env_cfg, seed=seed, node_id="v2", dt=0.01, duration_s=duration_s)
    agent_cfg = make_agent_config("fixed_trust", kappa_R=40.0, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True, detector_weights_path=None)
    agent = Agent(agent_cfg, env.imu.config(), node_id="v2")

    captured: list[tuple] = []
    orig_step = agent.trust.extractor.step

    def _wrapped(fix, innovations):
        raw = orig_step(fix, innovations)
        if raw is not None:
            captured.append((fix.t, raw.copy(), float(fix.raim_stat) if np.isfinite(fix.raim_stat) else 0.0,
                              float(fix.num_sats)))
        return raw
    agent.trust.extractor.step = _wrapped

    f_b_hold: list[np.ndarray] = []
    initialized = False
    oracle_active: dict[float, bool] = {}
    for k in range(len(env)):
        tick = env.tick(k)
        t = tick.t
        if not initialized:
            if t < env.hold_s:
                if tick.imu is not None:
                    f_b_hold.append(tick.imu.f_b)
                continue
            f_mean = np.mean(f_b_hold, axis=0) if f_b_hold else np.array([0.0, 0.0, G0])
            phi0, theta0 = _level_att(f_mean)
            psi0 = float(tick.truth.att[2]) + env.initial_heading_noise()
            pos0 = tick.truth.pos.copy()
            agent.initialize_static(t, pos0, np.array([phi0, theta0, psi0]))
            initialized = True
            continue
        agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
        oracle_active[round(t, 6)] = bool(tick.label.spoofing or tick.label.jamming)

    if not captured:
        return dict(seed=seed, family=family, t=[], raw=[], raim=[], nsat=[], oracle=[])
    ts = [c[0] for c in captured]
    raws = [c[1].tolist() for c in captured]
    raims = [c[2] for c in captured]
    nsats = [c[3] for c in captured]
    oracle = [oracle_active.get(round(t, 6), False) for t in ts]
    return dict(seed=seed, family=family, t=ts, raw=raws, raim=raims, nsat=nsats, oracle=oracle)


def run_pool(jobs: list[tuple[int, str, float]], n_workers: int) -> dict:
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=n_workers, mp_context=ctx) as ex:
        collected = list(ex.map(collect_one, jobs))
    return {c["seed"]: c for c in collected}


def ref_stats(by_seed: dict, seeds: list[int]) -> tuple[np.ndarray, np.ndarray]:
    raw = []
    for s in seeds:
        raw.extend(by_seed[s]["raw"])
    raw = np.array(raw)
    mu = raw.mean(axis=0)
    sd = raw.std(axis=0)
    sd = np.where(sd < 1e-9, 1.0, sd)
    return mu, sd


def platt_fit(logits: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    from sklearn.linear_model import LogisticRegression
    keep = ~np.isnan(labels)
    if keep.sum() < 10 or len(np.unique(labels[keep])) < 2:
        return 1.0, 0.0
    lr = LogisticRegression(max_iter=1000)
    lr.fit(logits[keep].reshape(-1, 1), labels[keep])
    return float(lr.coef_[0, 0]), float(lr.intercept_[0])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    n_workers = min(args.workers, 6, mp.cpu_count())

    from fedqpnt.trust.pseudolabel import PseudoLabelConfig, label_epochs, surrogate_s_cusum, \
        pseudolabel_precision_recall
    from fedqpnt.trust.detector import TrustDetector
    from fedqpnt.core.seeding import stream
    import torch

    t0 = time.time()
    # --- Step 1: OLD (300s) + NEW (1800s) clean reference, same seeds ---
    jobs_old = [(s, "clean", OLD_CALIB_DURATION_S) for s in CLEAN_CALIB_SEEDS]
    jobs_new = [(s, "clean", NEW_CALIB_DURATION_S) for s in CLEAN_CALIB_SEEDS]
    by_old = run_pool(jobs_old, n_workers)
    by_new = run_pool(jobs_new, n_workers)
    mu_old, sd_old = ref_stats(by_old, CLEAN_CALIB_SEEDS)
    mu_new, sd_new = ref_stats(by_new, CLEAN_CALIB_SEEDS)
    print(f"[{time.time()-t0:.0f}s] reference stats done")

    # clean-run positive-label rate under the NEW reference (target <=1%)
    clean_pos_rates = []
    for s in CLEAN_CALIB_SEEDS:
        c = by_new[s]
        t = np.array(c["t"]); raw = np.array(c["raw"])
        raim = np.array(c["raim"]); nsat = np.array(c["nsat"])
        s_cusum = surrogate_s_cusum(raw)
        y = label_epochs(t, raw, raim, nsat, s_cusum, cfg=PseudoLabelConfig(),
                          quantile_mu=mu_new, quantile_sd=sd_new)
        clean_pos_rates.append(float(np.mean(y == 1.0)))
    clean_pos_rate = float(np.mean(clean_pos_rates))

    # --- Step 2: TRAIN pool, relabel with NEW reference ---
    jobs_train = [(s, "mixed", POOL_DURATION_S) for s in TRAIN_SEEDS]
    by_train = run_pool(jobs_train, n_workers)
    print(f"[{time.time()-t0:.0f}s] train pool collected")

    all_y, all_oracle, per_seed_labels = [], [], {}
    for s in TRAIN_SEEDS:
        c = by_train[s]
        t = np.array(c["t"]); raw = np.array(c["raw"])
        raim = np.array(c["raim"]); nsat = np.array(c["nsat"]); oracle = np.array(c["oracle"], dtype=bool)
        s_cusum = surrogate_s_cusum(raw)
        y = label_epochs(t, raw, raim, nsat, s_cusum, cfg=PseudoLabelConfig(),
                          quantile_mu=mu_new, quantile_sd=sd_new)
        per_seed_labels[s] = (t, raw, y, oracle)
        keep = ~np.isnan(y)
        all_y.append(y[keep]); all_oracle.append(oracle[keep])
    pl_pr = pseudolabel_precision_recall(np.concatenate(all_y), np.concatenate(all_oracle))

    # --- Step 3: retrain frozen design ---
    detector = TrustDetector(arch="mlp", seed=0)
    train_U, train_y = [], []
    for s in TRAIN_SEEDS:
        t, raw, y, oracle = per_seed_labels[s]
        stack = detector._stack.__class__()
        for j in range(len(t)):
            xtilde = detector.normalizer.normalize(raw[j])
            if not np.isnan(y[j]) and y[j] == 0.0:
                detector.normalizer.update(raw[j])
            u = stack.step(t[j], xtilde)
            if not np.isnan(y[j]):
                train_U.append(u); train_y.append(y[j])
    train_U = np.array(train_U); train_y = np.array(train_y)
    rng = stream(0, "retrain_v2", "sgd")
    train_metrics = detector.train_local(train_U, train_y, train_y.copy(), epochs=2, lr=0.05,
                                          batch_size=64, rng=rng, balance=True, max_pos_fraction=0.5)
    print(f"[{time.time()-t0:.0f}s] retrain done:", train_metrics)

    # --- Step 4: Platt pool, fit per-head logistic on logit(raw p) vs PSEUDO-label ---
    jobs_platt = [(s, "mixed", POOL_DURATION_S) for s in PLATT_SEEDS]
    by_platt = run_pool(jobs_platt, n_workers)
    print(f"[{time.time()-t0:.0f}s] platt pool collected")

    def score_seed(seed_dict, seed):
        c = seed_dict[seed]
        t = np.array(c["t"]); raw = np.array(c["raw"])
        raim = np.array(c["raim"]); nsat = np.array(c["nsat"]); oracle = np.array(c["oracle"], dtype=bool)
        s_cusum = surrogate_s_cusum(raw)
        y = label_epochs(t, raw, raim, nsat, s_cusum, cfg=PseudoLabelConfig(),
                          quantile_mu=mu_new, quantile_sd=sd_new)
        stack = detector._stack.__class__()
        p_spoof, p_jam = [], []
        for j in range(len(t)):
            xtilde = detector.normalizer.normalize(raw[j])
            u = stack.step(t[j], xtilde)
            with torch.no_grad():
                out = detector.model(torch.as_tensor(u, dtype=torch.float32)).numpy()
            p_spoof.append(float(out[0])); p_jam.append(float(out[1]))
        return dict(t=t, y=y, oracle=oracle, p_spoof=np.array(p_spoof), p_jam=np.array(p_jam),
                    family=c["family"])

    platt_p_spoof, platt_y_spoof, platt_p_jam, platt_y_jam = [], [], [], []
    for s in PLATT_SEEDS:
        r = score_seed(by_platt, s)
        keep = ~np.isnan(r["y"])
        platt_p_spoof.append(r["p_spoof"][keep]); platt_y_spoof.append(r["y"][keep])
        platt_p_jam.append(r["p_jam"][keep]); platt_y_jam.append(r["y"][keep])
    ps = np.concatenate(platt_p_spoof); ys = np.concatenate(platt_y_spoof)
    pj = np.concatenate(platt_p_jam); yj = np.concatenate(platt_y_jam)
    eps = 1e-6
    logit_s = np.log(np.clip(ps, eps, 1 - eps) / np.clip(1 - ps, eps, 1 - eps))
    logit_j = np.log(np.clip(pj, eps, 1 - eps) / np.clip(1 - pj, eps, 1 - eps))
    a_spoof, b_spoof = platt_fit(logit_s, ys)
    a_jam, b_jam = platt_fit(logit_j, yj)
    print(f"[{time.time()-t0:.0f}s] platt fit: spoof(a={a_spoof:.3f},b={b_spoof:.3f}) "
          f"jam(a={a_jam:.3f},b={b_jam:.3f})")

    def platt_apply(p_raw, a, b):
        z = np.log(np.clip(p_raw, eps, 1 - eps) / np.clip(1 - p_raw, eps, 1 - eps))
        return 1.0 / (1.0 + np.exp(-(a * z + b)))

    # --- Step 5: HELDOUT eval ---
    jobs_ho = [(s, "mixed", POOL_DURATION_S) for s in HELDOUT_SEEDS]
    by_ho = run_pool(jobs_ho, n_workers)
    print(f"[{time.time()-t0:.0f}s] heldout pool collected")

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

    per_family_raw, per_family_cal, per_family_oracle = {}, {}, {}
    for s in HELDOUT_SEEDS:
        r = score_seed(by_ho, s)
        raw_score = np.maximum(r["p_spoof"], r["p_jam"])
        cal_score = np.maximum(platt_apply(r["p_spoof"], a_spoof, b_spoof),
                                platt_apply(r["p_jam"], a_jam, b_jam))
        per_family_raw.setdefault(r["family"], []).extend(raw_score.tolist())
        per_family_cal.setdefault(r["family"], []).extend(cal_score.tolist())
        per_family_oracle.setdefault(r["family"], []).extend(r["oracle"].astype(float).tolist())

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

    # reliability curve + Brier score (calibrated scores vs oracle, overall)
    overall_cal_arr = np.array(overall_cal); overall_oracle_arr = np.array(overall_oracle)
    brier = float(np.mean((overall_cal_arr - overall_oracle_arr) ** 2))
    bins = np.linspace(0, 1, 11)
    reliability = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (overall_cal_arr >= lo) & (overall_cal_arr < hi)
        if m.sum() > 0:
            reliability.append(dict(bin_lo=float(lo), bin_hi=float(hi), n=int(m.sum()),
                                     mean_predicted=float(overall_cal_arr[m].mean()),
                                     empirical_rate=float(overall_oracle_arr[m].mean())))

    brier_raw = float(np.mean((np.array(overall_raw) - overall_oracle_arr) ** 2))

    try:
        commit = sp.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        commit = "unknown"
    params = detector.get_params()
    params["platt_a_spoof"] = np.array([a_spoof]); params["platt_b_spoof"] = np.array([b_spoof])
    params["platt_a_jam"] = np.array([a_jam]); params["platt_b_jam"] = np.array([b_jam])
    out_path = ROOT / "results" / "m1" / "detector_weights_real_v2.npz"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out_path, **{k: np.asarray(v) for k, v in params.items()})

    report = dict(
        label="tuning seeds, not for publication",
        provenance=dict(config_hash=commit, date="2026-09-27", method="fixed_trust", kappa_R=40.0,
                         seeds_ref=CLEAN_CALIB_SEEDS, seeds_train=TRAIN_SEEDS, seeds_platt=PLATT_SEEDS,
                         seeds_heldout=HELDOUT_SEEDS, ref_duration_old_s=OLD_CALIB_DURATION_S,
                         ref_duration_new_s=NEW_CALIB_DURATION_S, pool_duration_s=POOL_DURATION_S,
                         platt_fit_target="pseudo-label (not oracle; oracle stays evaluator-only)"),
        reference_quantiles=dict(
            feature_names_idx="0=nis_pos,1=nis_vel,2=raim,3=cn0_mean,4=cn0_std,5=cn0_rate,6=agc,"
                               "7=clk_jump,8=drift_jump,9=resid_rms,10=nsat_delta,11=div_cusum,"
                               "12=outage,13=xsat_corr,14=elev_slope",
            mu_old=mu_old.tolist(), sd_old=sd_old.tolist(),
            mu_new=mu_new.tolist(), sd_new=sd_new.tolist(),
        ),
        clean_run_positive_label_rate_new_ref=clean_pos_rate,
        pseudolabel_precision_recall_vs_oracle=pl_pr,
        train_local_metrics=train_metrics,
        platt_params=dict(spoof=dict(a=a_spoof, b=b_spoof), jam=dict(a=a_jam, b=b_jam)),
        auc_raw_vs_calibrated=auc_report,
        brier_score_calibrated=brier, brier_score_raw=brier_raw,
        reliability_curve_calibrated=reliability,
        wall_s=time.time() - t0,
    )
    report_path = ROOT / "results" / "m1" / "detector_retrain_v2_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf8")
    print(json.dumps(auc_report, indent=2))
    print(f"clean_run_positive_label_rate_new_ref={clean_pos_rate:.4f}")
    print(f"weights -> {out_path}")
    print(f"report -> {report_path}")


if __name__ == "__main__":
    main()
