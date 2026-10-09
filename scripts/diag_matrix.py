"""DIAG (round-2, TUNING seeds only): before/after matrix through the real campaign run path (run_single).
Usage: DIAG_ROOT=<worktree or unset> python scripts/diag_matrix.py <label> <seeds comma> <scenarios comma> <methods comma> [grades comma]
Writes results/diag_r2/matrix_<label>.json (appends/merges keys)."""
import os, sys, json
from pathlib import Path
ROOT = Path(os.environ.get('DIAG_ROOT') or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT))
OUTDIR = Path(__file__).resolve().parent.parent / "results" / "diag_r2"
from fedqpnt.eval import campaign as C, scenarios as SC
from fedqpnt.node.runner import RunSpec, run_single
label = sys.argv[1]
seeds = [int(x) for x in sys.argv[2].split(",")]
assert all(s < 10000 for s in seeds), "tuning seeds only"
scens = sys.argv[3].split(","); methods = sys.argv[4].split(",")
grades = sys.argv[5].split(",") if len(sys.argv) > 5 else ["industrial_mems", "tactical"]
out_path = OUTDIR / f"matrix_{label}__{'-'.join(scens)}__{'-'.join(grades)}__{'-'.join(methods)}.json"
out = json.loads(out_path.read_text()) if out_path.exists() else {}
KEYS = ("rmse_h_pre", "rmse_h_att", "rmse_v_att", "max_h_att", "rmse_h_post", "max_h_post", "t_det", "t_rec", "mean_w_gnss_att", "fpr", "far_per_hour", "latency_on", "anees_pos_pre", "mean_w_pos_att", "mean_w_clk_att")
print("fedqpnt from", sys.modules["fedqpnt"].__file__)
for scn in scens:
    sc = SC.get(scn)
    for grade in grades:
        for method in methods:
            for seed in seeds:
                key = f"{scn}|{grade}|{method}|{seed}"
                if key in out: continue
                spec = C.build_spec_dict(sc, method, seed, imu_grade=grade,
                                         detector_weights_path=str((Path(__file__).resolve().parent.parent / "results/m1/detector_weights_sup_v4.npz")))
                r = run_single(RunSpec(**spec))
                out[key] = {k: r.get(k) for k in KEYS if k in r}
                out[key]["_allkeys"] = sorted(r.keys()) if not out.get("_keys") else None
                if not out.get("_keys"): out["_keys"] = sorted(r.keys())
                out[key].pop("_allkeys", None)
                print(key, {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out[key].items()}, flush=True)
                out_path.write_text(json.dumps(out, indent=1, default=str))
