"""D-082 freeze-5 sanity (tuning seeds 530-534 + seed-9604 clean): fedqpnt_local / undefended / abl_minus_quantum on
nominal, drift, meaconing, jam (600 s, schuler_tangent) and S6-coast (CAI on/off), both grades. Per-run JSON persisted to
<raw-dir>/<grade>/<scenario>_<arm>_<seed>.json (resumable). Also records w_q (mean/min over CAI epochs) and the
CAI-applied fraction (CAI innovation present and w_q >= w_excl, i.e. exactly eskf.correct's apply condition).
Usage: python scripts/core_robust_freeze5_sanity.py --raw-dir DIR --workers 3 [--report-only]"""
import argparse, json, subprocess, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
W = "results/m1/detector_weights_sup_v3.npz"
ATK = dict(onset_s=120.0, duration_s=180.0, severity=0.5)
SCEN = {"nominal": (None, 600.0), "drift_spoof": (dict(kind="drift_spoof", **ATK), 600.0),
        "meaconing": (dict(kind="meaconing", **ATK), 600.0), "jam_cw": (dict(kind="jam_cw", **ATK), 600.0),
        "s6coast": (dict(kind="jam_wideband", onset_s=600.0, duration_s=180.0, severity=1.0), 1200.0),
        "clean9604": (None, 600.0)}
ARMS = {"fedqpnt_local": ("fedqpnt_local", "field"), "undefended": ("undefended", "field"),
        "abl_minus_quantum": ("fedqpnt_local", None),
        "undefended_nocai": ("undefended", None)}            # only for s6coast
SMOKE_ARMS = ("fedqpnt_local", "undefended", "abl_minus_quantum")
S6_ARMS = ("fedqpnt_local", "abl_minus_quantum", "undefended", "undefended_nocai")

def _worker(args):
    spec_d, path = args
    import fedqpnt.fusion.eskf as E
    from fedqpnt.node.runner import _run_worker
    stats = dict(n=0, app=0, wq=[], nis=[])
    orig = E.ESKF.correct
    def correct(self, t, innovations, trust):
        if "quantum" in self._pending:
            w = trust.weights.get("quantum", 1.0)
            stats["n"] += 1; stats["wq"].append(w); stats["app"] += int(w >= self.cfg.w_excl)
            iv = next((x for x in innovations if x.sensor == "quantum"), None)
            if iv is not None: stats["nis"].append(iv.nis / max(iv.dof, 1))
        return orig(self, t, innovations, trust)
    E.ESKF.correct = correct
    res = _run_worker(spec_d)
    clean = {k: (v if isinstance(v, (int, float, str, bool)) or v is None else None) for k, v in res.items()}
    clean.update(n_cai=stats["n"], cai_applied_frac=(stats["app"] / stats["n"] if stats["n"] else None),
                 wq_mean=(float(np.mean(stats["wq"])) if stats["wq"] else None),
                 wq_min=(float(np.min(stats["wq"])) if stats["wq"] else None),
                 nis3_mean=(float(np.mean(stats["nis"])) if stats["nis"] else None),
                 nis3_frac_gt_clean=(float(np.mean(np.array(stats["nis"]) > 2.6049093)) if stats["nis"] else None))
    Path(path).write_text(json.dumps(clean), encoding="utf8")
    return path

def jobs(raw_dir):
    out, meta = [], []
    for grade in ("industrial_mems", "tactical"):
        d = Path(raw_dir) / grade; d.mkdir(parents=True, exist_ok=True)
        plan = []
        for s in ("nominal", "drift_spoof", "meaconing", "jam_cw"):
            plan += [(s, a, sd) for a in SMOKE_ARMS for sd in range(530, 535)]
        plan += [("s6coast", a, sd) for a in S6_ARMS for sd in range(530, 535)]
        plan += [("clean9604", a, 9604) for a in SMOKE_ARMS]
        for s, a, sd in plan:
            atk, dur = SCEN[s]; method, qg = ARMS[a]
            path = d / f"{s}_{a}_{sd}.json"; meta.append((grade, s, a, sd, path))
            if path.exists(): continue
            spec = dict(name=f"f5_{grade}_{s}_{a}_{sd}", master_seed=sd, method=method, duration_s=dur, dt=0.01,
                        platform="ground", world="schuler_tangent", imu_grade=grade, quantum_grade=qg, gnss_rate_hz=1.0,
                        hold_s=30.0, heading_noise_deg=2.0, attack=atk, kappa_R=60.0, kappa_Q=1.0,
                        detector_weights_path=W, record=False, node_id="node0")
            out.append((spec, str(path)))
    return out, meta

def report(meta):
    rows = [dict(json.loads(p.read_text()), grade=g, scen=s, arm=a, seed=sd) for g, s, a, sd, p in meta if p.exists()]
    def mean(g, s, a, k):
        v = [r.get(k) for r in rows if r["grade"] == g and r["scen"] == s and r["arm"] == a and r.get(k) is not None]
        v = [x for x in v if not (isinstance(x, float) and np.isnan(x))]
        return (float(np.mean(v)), len(v)) if v else (float("nan"), 0)
    for g in ("industrial_mems", "tactical"):
        print(f"\n=== {g}  (mean over seeds 530-534; n in brackets) ===")
        for s, keys in (("nominal", ("rmse_h_pre", "mean_w_gnss")), ("drift_spoof", ("rmse_h_att", "max_h_att", "rmse_h_post", "mean_w_gnss_att")),
                        ("meaconing", ("rmse_h_att", "max_h_att", "rmse_h_post", "mean_w_gnss_att")),
                        ("jam_cw", ("rmse_h_att", "max_h_att", "rmse_h_post", "mean_w_gnss_att")),
                        ("s6coast", ("max_h_att", "rmse_h_att", "max_h_post")), ("clean9604", ("rmse_h_pre", "max_h_pre", "mean_w_gnss", "far_per_hour"))):
            print(f"[{s}]")
            for a in (S6_ARMS if s == "s6coast" else SMOKE_ARMS):
                cells = []
                for k in keys + ("wq_mean", "wq_min", "cai_applied_frac", "nis3_mean", "nis3_frac_gt_clean"):
                    m, n = mean(g, s, a, k); cells.append(f"{k}={m:.3f}" if n else f"{k}=na")
                print(f"  {a:18s} " + "  ".join(cells))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--raw-dir", required=True); ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--report-only", action="store_true"); a = ap.parse_args()
    h = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    st = subprocess.run(["git", "status", "--porcelain", "fedqpnt/"], capture_output=True, text=True, cwd=ROOT).stdout.strip().replace("\n", "; ")
    print(f"git at launch: HEAD={h} branch+uncommitted fedqpnt/: [{st or 'clean'}]", flush=True)
    jl, meta = jobs(a.raw_dir)
    if not a.report_only and jl:
        import multiprocessing as mp
        from concurrent.futures import ProcessPoolExecutor, as_completed
        print(f"{len(meta)} runs, {len(jl)} to compute", flush=True)
        with ProcessPoolExecutor(max_workers=min(a.workers, 4), mp_context=mp.get_context("spawn")) as ex:
            futs = [ex.submit(_worker, j) for j in jl]
            for n, f in enumerate(as_completed(futs), 1):
                f.result()
                if n % 10 == 0: print(f"  {n}/{len(jl)}", flush=True)
    report(meta)
