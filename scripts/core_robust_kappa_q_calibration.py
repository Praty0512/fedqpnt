"""D-078 (2): coast-consistency calibration of kappa_Q (ESKF process-noise inflation), per IMU grade, PRE-REGISTERED rule:
forced 180 s GNSS outage (t in [120, 300)) on CLEAN missions, tuning seeds 530-549; method=undefended (w=1, no attack, GNSS
simply absent in the window); CAI (field) ON. Statistic: position NEES e^T P^-1 e with the 3-D position block of P, at the
60/120/179 s outage checkpoints (t = 180, 240, 299), pooled over seeds and checkpoints; ANEES = mean NEES / 3 (ideal 1).
Choose the smallest kappa_Q on the grid {1,2,3,5,8,12,20,30,50} with pooled ANEES <= 1.5. Report the whole curve; if none
reaches <= 1.5, report it and stop. Clean data only.

Usage: python scripts/core_robust_kappa_q_calibration.py --grade industrial_mems --workers 3 --out results/m1/kappa_q_<grade>.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GRID = [1, 2, 3, 5, 8, 12, 20, 30, 50]
SEEDS = list(range(530, 550))
OUT_ON, OUT_LEN = 120.0, 180.0
CHECK = (60.0, 120.0, 179.0)


def _git() -> str:
    h = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    s = subprocess.run(["git", "status", "--porcelain", "fedqpnt/"], capture_output=True, text=True,
                       cwd=ROOT).stdout.strip().replace("\n", "; ")
    return f"HEAD={h} status[fedqpnt/]={s or 'clean'}"


def run_one(args):
    kq, seed, grade = args
    from fedqpnt.node.agent import Agent
    from fedqpnt.node.environment import EnvConfig, NodeEnvironment
    from fedqpnt.node.methods import make_agent_config
    env = NodeEnvironment(EnvConfig(platform="ground", world="flat", imu_grade=grade, quantum_grade="field",
                                    gnss_rate_hz=1.0, hold_s=30.0, heading_noise_deg=2.0, attacks=[]),
                          seed=seed, node_id="kq", dt=0.01, duration_s=OUT_ON + OUT_LEN)
    cfg = make_agent_config("undefended", world="flat", imu_grade=grade, quantum_grade="field", kappa_Q=float(kq))
    ag = Agent(cfg, env.imu.config(), node_id="kq")
    hold, init = [], False
    marks = {round(OUT_ON + c, 3): c for c in CHECK}
    out = {}
    for k in range(len(env)):
        tk = env.tick(k)
        t = tk.t
        if not init:
            if t < env.hold_s:
                if tk.imu is not None:
                    hold.append(tk.imu.f_b)
                continue
            fx, fy, fz = np.mean(hold, axis=0)
            ag.initialize_static(t, tk.truth.pos.copy(), np.array(
                [np.arctan2(fy, fz), np.arctan2(-fx, np.hypot(fy, fz)),
                 float(tk.truth.att[2]) + env.initial_heading_noise()]))
            init = True
            continue
        ge = tk.gnss_epoch
        if OUT_ON <= t < OUT_ON + OUT_LEN:
            ge = None
        a = ag.step(t, tk.imu, tk.quantum, ge)
        key = round(t, 3)
        if key in marks:
            e = a.nav.pos - tk.truth.pos
            P = ag.eskf.P[0:3, 0:3]
            out[marks[key]] = float(e @ np.linalg.solve(P, e))
    return dict(kq=kq, seed=seed, nees=out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grade", required=True)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--grid", type=float, nargs="+", default=GRID)
    ap.add_argument("--seeds", type=int, nargs="+", default=SEEDS)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    print("git at launch:", _git(), flush=True)
    tasks = [(kq, s, a.grade) for kq in a.grid for s in a.seeds]
    with ProcessPoolExecutor(max_workers=min(a.workers, 4)) as ex:
        res = list(ex.map(run_one, tasks))
    Path(a.out).write_text(json.dumps(res), encoding="utf8")
    print(f"=== kappa_Q coast-consistency curve, grade={a.grade}, seeds {a.seeds[0]}-{a.seeds[-1]} (n={len(a.seeds)}), CAI on ===")
    print(f"{'kappa_Q':>8} {'ANEES@60':>10} {'ANEES@120':>10} {'ANEES@179':>10} {'pooled':>9} {'<=1.5':>6}")
    chosen = None
    for kq in a.grid:
        rows = [r for r in res if r["kq"] == kq]
        per = [np.mean([r["nees"][str(c)] if str(c) in r["nees"] else r["nees"][c] for r in rows]) / 3.0 for c in CHECK]
        pooled = float(np.mean(per))
        ok = pooled <= 1.5
        if ok and chosen is None:
            chosen = kq
        print(f"{kq:8.0f} {per[0]:10.2f} {per[1]:10.2f} {per[2]:10.2f} {pooled:9.2f} {str(ok):>6}")
    print("CHOSEN kappa_Q =", chosen if chosen is not None else "NONE reaches <= 1.5 (stop and report)")
    print("git at end:", _git(), flush=True)


if __name__ == "__main__":
    main()
