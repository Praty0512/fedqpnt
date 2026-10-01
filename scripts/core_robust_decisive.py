"""Decisive defended-vs-undefended test on core-freeze-2 + detector v3 (D-068 primary criterion + secondary).
Scenarios (per IMU grade; all 7 methods): smoke group (seeds 500-504): nominal, drift_spoof (default full
signature), meaconing, jam_cw (onset 120, 180 s, severity 0.5, 600 s missions); safety group (seeds 9600-9604):
drift_spoof with cn0_sig_scale s in {0, 0.25, 0.5, 1.0} plus nominal (tuning ranges only).
Primary (D-068): mean_defended <= mean_undefended + 3*sigma_nom (sigma_nom per grade from results/sigma_nom.json,
frozen), per scenario x grade; metric = rmse_h_pre for nominal, rmse_h_att otherwise (rmse_h_post reported).
Secondary: paired (by seed) Hodges-Lehmann difference defended - undefended with 95% BCa bootstrap CI.
Reports raw per-method means incl. post column, mean_w_gnss/pos/clk (whole mission and attack window), rmse_t_ns.

Usage: python scripts/core_robust_decisive.py --weights W --grade industrial_mems --workers 4 --out X.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fedqpnt.eval.metrics import load_sigma_nom  # noqa: E402
from fedqpnt.eval.stats import bca_bootstrap_ci, hodges_lehmann  # noqa: E402
from fedqpnt.node.methods import METHOD_NAMES  # noqa: E402
from fedqpnt.node.runner import RunSpec, run_many  # noqa: E402

SMOKE_SEEDS = [500, 501, 502, 503, 504]
SAFETY_SEEDS = [9600, 9601, 9602, 9603, 9604]
ATK = dict(onset_s=120.0, duration_s=180.0, severity=0.5)
SMOKE = {
    "nominal": None,
    "drift_spoof": dict(kind="drift_spoof", **ATK),
    "meaconing": dict(kind="meaconing", **ATK),
    "jam_cw": dict(kind="jam_cw", **ATK),
}
SAFETY = {"safety_nominal": None}
for s in (0.0, 0.25, 0.5, 1.0):
    SAFETY[f"safety_drift_s{s}"] = dict(kind="drift_spoof", params=dict(cn0_sig_scale=s), **ATK)


def _git() -> str:
    h = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    s = subprocess.run(["git", "status", "--porcelain", "fedqpnt/"], capture_output=True, text=True,
                       cwd=ROOT).stdout.strip().replace("\n", "; ")
    return f"HEAD={h} status[fedqpnt/]={s or 'clean'}"


def _persist_worker(args):
    """Run one spec in a worker process and PERSIST its raw result to disk immediately (crash-safe)."""
    spec_dict, path = args
    from fedqpnt.node.runner import _run_worker
    res = _run_worker(spec_dict)
    clean = {k: (v if isinstance(v, (int, float, str, bool)) or v is None else None) for k, v in res.items()}
    Path(path).write_text(json.dumps(clean), encoding="utf8")
    return path


def main() -> None:
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor, as_completed
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--grade", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    ap.add_argument("--raw-dir", default=str(ROOT / "results" / "m1" / "decisive_v3_raw"))
    ap.add_argument("--scenarios", nargs="+", default=None, help="restrict scenarios (testing)")
    ap.add_argument("--methods", nargs="+", default=None, help="restrict methods (testing)")
    ap.add_argument("--seeds", type=int, nargs="+", default=None, help="override seeds (testing)")
    ap.add_argument("--duration", type=float, default=600.0)
    a = ap.parse_args()
    print("git at launch:", _git(), flush=True)
    sig = load_sigma_nom(str(ROOT / "results" / "sigma_nom.json"))[a.grade]
    raw_dir = Path(a.raw_dir) / a.grade
    raw_dir.mkdir(parents=True, exist_ok=True)
    methods = a.methods or list(METHOD_NAMES)
    jobs, meta = [], []
    for group, seeds in ((SMOKE, SMOKE_SEEDS), (SAFETY, SAFETY_SEEDS)):
        for sname, atk in group.items():
            if a.scenarios and sname not in a.scenarios:
                continue
            for method in methods:
                for seed in (a.seeds or seeds):
                    path = raw_dir / f"{sname}_{method}_{seed}.json"
                    meta.append((sname, method, seed, path))
                    if path.exists():
                        continue                       # already done: skipped on restart
                    spec = RunSpec(name=f"dec_{a.grade}_{sname}_{method}_{seed}", master_seed=seed, method=method,
                                   duration_s=a.duration, hold_s=30.0, platform="ground", world="flat",
                                   imu_grade=a.grade, quantum_grade="field", gnss_rate_hz=1.0,
                                   heading_noise_deg=2.0, attack=atk, detector_weights_path=str(a.weights),
                                   record=False)
                    jobs.append((dict(spec.__dict__), str(path)))
    print(f"{len(meta)} runs total, {len(jobs)} to compute ({len(meta) - len(jobs)} already on disk)", flush=True)
    if jobs:
        with ProcessPoolExecutor(max_workers=min(a.workers, 4), mp_context=mp.get_context("spawn")) as ex:
            futs = [ex.submit(_persist_worker, j) for j in jobs]
            for n, f in enumerate(as_completed(futs), 1):
                f.result()
                if n % 20 == 0:
                    print(f"  {n}/{len(jobs)} done", flush=True)
    # aggregation reads ONLY from the persisted per-run files; result keys can never collide with the row id
    raw = []
    for sname, method, seed, path in meta:
        row = json.loads(path.read_text(encoding="utf8"))
        row.update(scenario=sname, method=method, seed=seed)
        raw.append(row)
    Path(a.out).write_text(json.dumps(dict(grade=a.grade, sigma_nom=sig, weights=str(a.weights), runs=raw)),
                           encoding="utf8")

    def col(sname, method, key):
        rows = sorted([r for r in raw if r["scenario"] == sname and r["method"] == method], key=lambda r: r["seed"])
        return np.array([float(r[key]) if r.get(key) is not None else np.nan for r in rows])

    print(f"\n=== grade={a.grade} sigma_nom={sig:.4f} m (D-068 frozen) weights={a.weights} ===")
    for sname in [x for x in list(SMOKE) + list(SAFETY) if not a.scenarios or x in a.scenarios]:
        key = "rmse_h_pre" if "nominal" in sname else "rmse_h_att"
        und = col(sname, "undefended", key)
        thr = float(np.nanmean(und)) + 3.0 * sig
        print(f"\n[{sname}] primary metric {key}; undefended mean={np.nanmean(und):.3f}  threshold(+3 sigma_nom)={thr:.3f}")
        print(f"  {'method':16s} {'mean':>9s} {'prim<=thr':>9s} {'HL diff':>9s} {'95% BCa CI':>20s} {'post':>9s} "
              f"{'w_gnss':>7s} {'w_pos':>7s} {'w_clk':>7s} {'w_gnss_att':>10s} {'w_pos_att':>9s} {'w_clk_att':>9s} {'rmse_t_ns':>9s}")
        for method in methods:
            x = col(sname, method, key)
            d = x - und
            ok = np.isfinite(d)
            hl = ci = float("nan")
            if method != "undefended" and ok.sum() >= 3:
                hl = float(hodges_lehmann(d[ok]))
                try:
                    lo, hi = bca_bootstrap_ci(d[ok])
                    ci = f"[{lo:8.2f},{hi:8.2f}]"
                except Exception:
                    ci = "n/a"
            else:
                ci = "-"
            post = np.nanmean(col(sname, method, "rmse_h_post")) if "nominal" not in sname else float("nan")
            mw = [np.nanmean(col(sname, method, k)) for k in ("mean_w_gnss", "mean_w_pos", "mean_w_clk",
                                                             "mean_w_gnss_att", "mean_w_pos_att", "mean_w_clk_att")]
            print(f"  {method:16s} {np.nanmean(x):9.3f} {str(bool(np.nanmean(x) <= thr)):>9s} {hl:9.2f} {ci:>20s} "
                  f"{post:9.2f} " + " ".join(f"{v:7.3f}" for v in mw[:3]) + " " +
                  " ".join(f"{v:9.3f}" for v in mw[3:]) + f" {np.nanmean(col(sname, method, 'rmse_t_ns')):9.1f}")
    print("\ngit at end:", _git(), flush=True)


if __name__ == "__main__":
    main()
