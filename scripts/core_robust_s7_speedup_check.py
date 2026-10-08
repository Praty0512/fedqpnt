"""D-082 perf: seeded S7-p2 tuning run, old (linear-scan label) vs new (indexed): every output key identical + timing."""
import sys, time, json
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fedqpnt.eval import campaign as C, scenarios as SC
from fedqpnt.node.environment import NodeEnvironment
from fedqpnt.node.runner import RunSpec, run_single
sid = sys.argv[1]; dur = float(sys.argv[2]); grade = sys.argv[3]
sc = SC.get(sid)
sp = C.build_spec_dict(sc, "fedqpnt_local", 530, duration_s=dur, imu_grade=grade, detector_weights_path="results/m1/detector_weights_sup_v3.npz")
t0 = time.time(); new = run_single(RunSpec(**sp)); t_new = time.time() - t0
orig = NodeEnvironment._label; NodeEnvironment._label = NodeEnvironment._label_reference
t0 = time.time(); old = run_single(RunSpec(**sp)); t_old = time.time() - t0
NodeEnvironment._label = orig
new.pop("wall_s"); old.pop("wall_s")
def same(a, b):
    if isinstance(a, float) and isinstance(b, float): return (a == b) or (np.isnan(a) and np.isnan(b))
    if isinstance(a, (list, tuple, np.ndarray)): return np.array_equal(np.asarray(a, dtype=float), np.asarray(b, dtype=float), equal_nan=True) if len(a) and isinstance(np.asarray(a).flat[0], (int, float, np.floating)) else a == b
    return a == b
diff = [k for k in set(new) | set(old) if not same(new.get(k), old.get(k))]
print(f"{sid} {grade} dur={dur}s n_attacks={len(sc.attacks)} keys={len(new)} DIFFERING_KEYS={diff}")
print(f"old {t_old:.1f}s  new {t_new:.1f}s  speedup x{t_old/t_new:.1f}")
