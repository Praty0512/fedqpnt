"""D-066/D-067 empirical check of the gnss_shadow NIS (un-inflated receiver covariance) as a probe
acceptance statistic. Clean missions, forced 60 s GNSS outages (as in the coasting script), then the
mean shadow NIS over the FIRST T_probe=10 s of returning fixes, evaluated with NO GNSS update applied
(exactly what the shadow probe does). Optional position offset on the returning fixes (detection power).
Also per-epoch shadow NIS on a clean mission with no outage (updates applied).

Usage: python scripts/core_robust_shadow_nis_check.py --seeds 500 ... --offsets 0 10 26 50 --workers 4 --out X.json
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WINDOWS = (100.0, 260.0, 420.0)     # outage start times
OUTAGE_S, PROBE_S = 60.0, 10.0
DURATION_S = 520.0
KAPPA_R = 60.0


def _git() -> str:
    h = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    s = subprocess.run(["git", "status", "--porcelain", "fedqpnt/"], capture_output=True, text=True,
                       cwd=ROOT).stdout.strip().replace("\n", "; ")
    return f"HEAD={h} status[fedqpnt/]={s or 'clean'}"


def run_one(args):
    seed, grade, offset, no_outage = args
    from fedqpnt.node.agent import Agent
    from fedqpnt.node.environment import EnvConfig, NodeEnvironment
    from fedqpnt.node.methods import make_agent_config

    env = NodeEnvironment(EnvConfig(platform="ground", world="flat", imu_grade=grade, quantum_grade="field",
                                    gnss_rate_hz=1.0, hold_s=30.0, heading_noise_deg=2.0, attacks=[]),
                          seed=seed, node_id="shadowchk", dt=0.01, duration_s=DURATION_S)
    cfg = make_agent_config("undefended", kappa_R=KAPPA_R, kappa_Q=1.0, world="flat", quantum_enabled=True)
    agent = Agent(cfg, env.imu.config(), node_id="shadowchk")

    state = {"in_shadow": False, "offset_on": False, "last_shadow": None}
    orig_innov = agent.eskf.innovations
    orig_correct = agent.eskf.correct
    orig_solve = agent.receiver.solve

    def innov_wrap(t, fix, q):
        out = orig_innov(t, fix, q)
        sh = next((i for i in out if i.sensor == "gnss_shadow"), None)
        state["last_shadow"] = (t, float(sh.nis)) if sh is not None else None
        return out

    def correct_wrap(t, innovations, trust):
        if state["in_shadow"]:
            trust = dataclasses.replace(trust, probe_shadow=True)   # evaluate, apply NO gnss update
        return orig_correct(t, innovations, trust)

    def solve_wrap(epoch):
        fix = orig_solve(epoch)
        if state["offset_on"] and fix.valid:
            fix = dataclasses.replace(fix, pos=fix.pos + np.array([offset, 0.0, 0.0]))
        return fix

    agent.eskf.innovations, agent.eskf.correct, agent.receiver.solve = innov_wrap, correct_wrap, solve_wrap

    f_b_hold, initialized = [], False
    win_vals = {w: [] for w in WINDOWS}
    clean_epoch = []
    for k in range(len(env)):
        tick = env.tick(k)
        t = tick.t
        if not initialized:
            if t < env.hold_s:
                if tick.imu is not None:
                    f_b_hold.append(tick.imu.f_b)
                continue
            f_mean = np.mean(f_b_hold, axis=0) if f_b_hold else np.array([0.0, 0.0, 9.80665])
            fx, fy, fz = f_mean
            phi0 = float(np.arctan2(fy, fz))
            theta0 = float(np.arctan2(-fx, np.sqrt(fy ** 2 + fz ** 2)))
            psi0 = float(tick.truth.att[2]) + env.initial_heading_noise()
            agent.initialize_static(t, tick.truth.pos.copy(), np.array([phi0, theta0, psi0]))
            initialized = True
            continue
        gnss_epoch = tick.gnss_epoch
        cur_win = None
        if not no_outage:
            for w0 in WINDOWS:
                if w0 <= t < w0 + OUTAGE_S:
                    gnss_epoch = None
                if w0 + OUTAGE_S <= t < w0 + OUTAGE_S + PROBE_S:
                    cur_win = w0
        state["in_shadow"] = cur_win is not None
        state["offset_on"] = cur_win is not None and offset != 0.0
        state["last_shadow"] = None
        agent.step(t, tick.imu, tick.quantum, gnss_epoch)
        if state["last_shadow"] is not None:
            if cur_win is not None:
                win_vals[cur_win].append(state["last_shadow"][1])
            elif no_outage and t > 60.0:
                clean_epoch.append(state["last_shadow"][1])
    means = [float(np.mean(v)) for v in win_vals.values() if len(v) >= 8]
    return dict(seed=seed, grade=grade, offset=offset, no_outage=no_outage, window_means=means,
                clean_epoch=clean_epoch)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(500, 510)))
    ap.add_argument("--grades", nargs="+", default=["industrial_mems", "tactical"])
    ap.add_argument("--offsets", type=float, nargs="+", default=[0.0, 10.0, 26.0, 50.0])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--with-clean-epochs", action="store_true")
    ap.add_argument("--out", default="results/m1/shadow_nis_check.json")
    a = ap.parse_args()
    print("git at launch:", _git(), flush=True)
    tasks = [(s, g, o, False) for g in a.grades for o in a.offsets for s in a.seeds]
    if a.with_clean_epochs:
        tasks += [(s, g, 0.0, True) for g in a.grades for s in a.seeds]
    with ProcessPoolExecutor(max_workers=min(a.workers, 4)) as ex:
        res = list(ex.map(run_one, tasks))
    Path(a.out).write_text(json.dumps(res), encoding="utf8")
    thr = 16.81
    for g in a.grades:
        for o in a.offsets:
            v = np.array([m for r in res if r["grade"] == g and r["offset"] == o and not r["no_outage"]
                          for m in r["window_means"]])
            if len(v):
                print(f"{g:16s} offset={o:5.1f} n={len(v):3d} median={np.median(v):9.2f} p95={np.percentile(v, 95):9.2f} "
                      f"p99={np.percentile(v, 99):9.2f} max={v.max():9.2f} frac>{thr}={np.mean(v > thr):.3f}")
        e = np.array([x for r in res if r["grade"] == g and r["no_outage"] for x in r["clean_epoch"]])
        if len(e):
            print(f"{g:16s} clean per-epoch shadow NIS (no outage) n={len(e)} median={np.median(e):.2f} "
                  f"p95={np.percentile(e, 95):.2f} p99={np.percentile(e, 99):.2f} frac>{thr}={np.mean(e > thr):.4f}")
    print("git at end:", _git(), flush=True)


if __name__ == "__main__":
    main()
