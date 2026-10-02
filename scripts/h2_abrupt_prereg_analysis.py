"""H2-ABRUPT steps 3-4 (D-064, docs/specs/raw/H2_PREREG.md): per-(arm, seed) tau calibration + the pre-registered metrics.

Inputs: results/fleet/h2_abrupt_runs/*.json (+ .npz final installed model per run) written by h2_abrupt_h2h4_driver.py.
tau: for each run, that run's FINAL installed model scored on clean-mission 1 Hz features (seeds 580-599, 1000 s each,
first T_ALIGN_S=60 s of each mission excluded -> >=5 h per model), FAR = 1/h. Clean features are collected once in open-loop
`fixed_trust` mode (collect_run; model-independent) and scored offline per model (disclosed in H2_PREREG.md).
Reports raw numbers, no framing.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from fedqpnt.eval.metrics import T_ALIGN_S
from fedqpnt.training.build_supervised_dataset import collect_run, run_pool
from fedqpnt.trust.detector import TrustDetector
from h2_abrupt_metrics import (calibrate_tau, onset_detection, onset_window_auc, full_window_auc,
                               recovery_alarm_rate, paired_wilcoxon_summary)

RUNS = Path("results/fleet/h2_abrupt_runs")
CLOSED_DIR = None   # set by --tau-mode closedloop (D-077 AMENDMENT 2)
CLEAN_CACHE = Path("results/fleet/h2_abrupt_clean_features.npz")
OUT = Path("results/fleet/h2_abrupt_prereg_results.json")
CLEAN_SEEDS = list(range(580, 600))
CLEAN_DURATION_S = 1000.0
ARMS = ("fedqpnt_local", "baseline_b_cont")
PARTS = ("h2_abrupt", "h4_abrupt", "control_drift")
SEEDS = list(range(500, 510))


def collect_clean(workers: int) -> dict:
    if CLEAN_CACHE.exists():
        z = np.load(CLEAN_CACHE)
        return {int(k.split("_")[1]): (z[k], z["raw_" + k.split("_")[1]]) for k in z.files if k.startswith("t_")}
    jobs = [(s, "clean", CLEAN_DURATION_S) for s in CLEAN_SEEDS]
    by = run_pool(jobs, n_workers=workers) if workers > 1 else {s: collect_run(j) for s, j in zip(CLEAN_SEEDS, jobs)}
    d = {s: (np.array(by[s]["t"]), np.array(by[s]["raw"], dtype=float)) for s in CLEAN_SEEDS}
    np.savez(CLEAN_CACHE, **{f"t_{s}": d[s][0] for s in d}, **{f"raw_{s}": d[s][1] for s in d})
    return d


def clean_scores(params: dict, clean: dict):
    det = TrustDetector(arch="mlp", seed=0)
    det.set_params({k: np.asarray(v) for k, v in params.items()})
    ts, ps = [], []
    for i, s in enumerate(sorted(clean)):
        t, raw = clean[s]
        det.reset_stream()
        p = np.array([max(det.score(float(tt), r)[:2]) for tt, r in zip(t, raw)])
        m = t >= T_ALIGN_S
        ts.append(t[m] + i * 5000.0)
        ps.append(p[m])
    return np.concatenate(ps), np.concatenate(ts)


def _ci95(v):
    v = np.asarray([x for x in v if np.isfinite(x)], float)
    if len(v) < 2:
        return dict(mean=float(v.mean()) if len(v) else float("nan"), ci95=float("nan"), n=len(v))
    return dict(mean=float(v.mean()), ci95=float(1.96 * v.std(ddof=1) / np.sqrt(len(v))), n=len(v))


def _wil(x, y):
    try:
        return paired_wilcoxon_summary(np.array(x, float), np.array(y, float))
    except Exception as exc:  # e.g. all-zero differences
        return dict(note=f"wilcoxon failed: {exc!r}", diff_mean=float(np.mean(np.array(x, float) - np.array(y, float))))


def analyse(workers: int) -> dict:
    clean = None if CLOSED_DIR else collect_clean(workers)
    res = dict(tau_mode='closedloop' if CLOSED_DIR else 'openloop', git_head=subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
               git_status_fedqpnt=subprocess.run(["git", "status", "--porcelain", "fedqpnt/"], capture_output=True, text=True).stdout.strip(),
               clean_seeds=CLEAN_SEEDS, clean_duration_s=CLEAN_DURATION_S, parts={}, invalid_runs=[])
    for part in PARTS:
        per = {a: [] for a in ARMS}
        for arm in ARMS:
            for seed in SEEDS:
                jp = RUNS / f"{part}_{arm}_seed{seed}.json"
                if not jp.exists():
                    res["invalid_runs"].append(f"missing {jp.name}")
                    continue
                rec = json.loads(jp.read_text())
                gs, ge = rec["git_start"], rec["git_end"]
                changed = bool(subprocess.run(["git", "diff", "--quiet", gs["head"], ge["head"], "--", "fedqpnt"]).returncode
                               or gs["status_porcelain_fedqpnt"] or ge["status_porcelain_fedqpnt"])   # D-077: git diff start end -- fedqpnt
                if changed or rec.get("aborted"):
                    res["invalid_runs"].append(f"{jp.name}: fedqpnt_changed={changed} aborted={rec.get('aborted')}")
                n0 = rec["n0"]
                if "epoch_t" not in n0:
                    res["invalid_runs"].append(f"{jp.name}: no epoch arrays")
                    continue
                t, act, rp = (np.asarray(n0[k]) for k in ("epoch_t", "epoch_active", "epoch_raw_p"))
                act = act.astype(bool)
                theta = dict(np.load(jp.with_suffix(".npz")))
                if CLOSED_DIR:
                    cal = json.loads((CLOSED_DIR / f"tau_{part}_{arm}.json").read_text())
                else:
                    cs, ct = clean_scores(theta, clean)
                    cal = calibrate_tau(cs, ct, target_far_per_hour=1.0)
                tau = cal["tau"]
                det = onset_detection(t, act, rp, tau)
                per[arm].append(dict(
                    seed=seed, tau=tau, achieved_far=cal["achieved_far_per_hour"], clean_hours=float(cal["clean_hours"]),
                    pd10=int(det.detected_at_10s), latency_s=det.latency_s, censored=int(det.censored),
                    auc_n10=onset_window_auc(t, act, rp, 10.0)["auc"], auc_n5=onset_window_auc(t, act, rp, 5.0)["auc"],
                    full_window_auc=full_window_auc(t, act, rp)["auc"],
                    recovery_alarm_rate=recovery_alarm_rate(t, act, rp, tau)["recovery_alarm_rate"],
                    round_installs=n0.get("round_installs"), final_theta_hash=n0.get("final_theta_hash")))
                print(part, arm, seed, per[arm][-1], flush=True)
        summ = {}
        for arm in ARMS:
            rows = per[arm]
            summ[arm] = dict(
                n=len(rows), P_D_at_10s=_ci95([r["pd10"] for r in rows]), latency_s=_ci95([r["latency_s"] for r in rows]),
                n_censored=int(sum(r["censored"] for r in rows)),
                **{k: _ci95([r[k] for r in rows]) for k in ("auc_n10", "auc_n5", "full_window_auc", "recovery_alarm_rate", "tau")})
        by_seed = {a: {r["seed"]: r for r in per[a]} for a in ARMS}
        common = sorted(set(by_seed[ARMS[0]]) & set(by_seed[ARMS[1]]))
        wil = {k: _wil([by_seed[ARMS[0]][s][k] for s in common], [by_seed[ARMS[1]][s][k] for s in common])
               for k in ("pd10", "latency_s", "auc_n10", "auc_n5", "full_window_auc", "recovery_alarm_rate")}
        res["parts"][part] = dict(per_seed=per, summary=summ, paired_wilcoxon_fedqpnt_vs_bcont=wil, n_paired=len(common))
    OUT.write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--collect-only", action="store_true")
    ap.add_argument("--runs-dir", default=str(RUNS))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--tau-mode", choices=["openloop", "closedloop"], default="openloop")
    ap.add_argument("--clean-dir", default="results/fleet/h2_abrupt_clean_closedloop_freeze3")
    a = ap.parse_args()
    RUNS, OUT = Path(a.runs_dir), Path(a.out)
    if a.tau_mode == "closedloop":
        CLOSED_DIR = Path(a.clean_dir)
    if a.collect_only:
        collect_clean(a.workers)
        print("clean features cached", CLEAN_CACHE)
    else:
        analyse(a.workers)
        print("wrote", OUT)
