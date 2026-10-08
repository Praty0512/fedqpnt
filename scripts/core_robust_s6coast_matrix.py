"""Master diagnosis (post-freeze-4, tuning seed only, NO fedqpnt edits): S6-coast max_h_att for
fedqpnt_local / fixed_trust / undefended, CAI on vs off, both grades, seed 530. Single process.
Run: python scripts/core_robust_s6coast_matrix.py [seed]"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fedqpnt.eval import campaign as C, scenarios as SC
from fedqpnt.node.runner import RunSpec, run_single

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 530
assert 500 <= SEED <= 599 or 9500 <= SEED <= 9699
sc = SC.get("S6-coast")
out = {}
for grade in ("industrial_mems", "tactical"):
    for method in ("fedqpnt_local", "fixed_trust", "undefended"):
        for cai in (True, False):
            spec = C.build_spec_dict(sc, method, SEED, imu_grade=grade, detector_weights_path="results/m1/detector_weights_sup_v3.npz")
            if not cai:
                spec["quantum_grade"] = None
            r = run_single(RunSpec(**spec))
            key = f"{grade}|{method}|CAI={'on' if cai else 'off'}"
            out[key] = dict(max_h_att=r["max_h_att"], rmse_h_att=r["rmse_h_att"], max_h_post=r["max_h_post"],
                            mean_w_gnss_att=r.get("mean_w_gnss_att"), t_det=r.get("t_det"))
            print(key, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out[key].items()}, flush=True)
Path(ROOT / "results/m1/diag").mkdir(parents=True, exist_ok=True)
(ROOT / f"results/m1/diag/s6coast_matrix_seed{SEED}.json").write_text(json.dumps(out, indent=1))
