"""D-074 item 2: clean false-veto rate of the CLOCK-law probe statistic (D-069 rule applied to the clock law).
Statistic = mean over the first T_probe=10 valid fixes after a 60 s GNSS outage of (x8^2 + x9^2) (the clock-jump /
drift-jump features, normalised by the TCXO holdover std over the gap, D-071/D-073). During each outage a realistic
1 Hz INVALID fix is fed to the trust extractor every epoch (the agent path drops invalid fixes; feeding them here
checks the D-073 clock-gap handling). Clean missions (no attack). Undefended method, nominal, 3 windows/seed.
Bound under test: chi2_2(0.99) = 9.21.

Usage: python scripts/core_robust_clock_probe_check.py --seeds 500 ... 509 --workers 4 --out X.json
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

WINDOWS = (100.0, 260.0, 420.0)
OUTAGE_S, PROBE_S = 60.0, 10.0
DURATION_S = 520.0


def _git() -> str:
    h = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    s = subprocess.run(["git", "status", "--porcelain", "fedqpnt/"], capture_output=True, text=True,
                       cwd=ROOT).stdout.strip().replace("\n", "; ")
    return f"HEAD={h} status[fedqpnt/]={s or 'clean'}"


def run_one(args):
    seed, grade = args
    from fedqpnt.core.types import GnssFix
    from fedqpnt.node.agent import Agent
    from fedqpnt.node.environment import EnvConfig, NodeEnvironment
    from fedqpnt.node.methods import make_agent_config

    env = NodeEnvironment(EnvConfig(platform="ground", world="flat", imu_grade=grade, quantum_grade="field",
                                    gnss_rate_hz=1.0, hold_s=30.0, heading_noise_deg=2.0, attacks=[]),
                          seed=seed, node_id="clkprobe", dt=0.01, duration_s=DURATION_S)
    cfg = make_agent_config("undefended", world="flat", quantum_enabled=True, imu_grade=grade)
    agent = Agent(cfg, env.imu.config(), node_id="clkprobe")
    ext = agent.trust.extractor
    orig_step = ext.step
    last = {"x": None}

    def step_wrap(fix, inn):
        r = orig_step(fix, inn)
        last["x"] = None if r is None else (float(r[7]), float(r[8]))
        return r
    ext.step = step_wrap

    def invalid(t):
        return GnssFix(t=t, pos=np.full(3, np.nan), vel=np.full(3, np.nan), clk_bias=np.nan, clk_drift=np.nan,
                       cov_pos=np.eye(3), cov_vel=np.eye(3), residual_rms=np.nan, num_sats=2, mean_cn0=25.0,
                       std_cn0=3.0, agc_db=-10.0, valid=False, raim_stat=np.nan)

    f_b_hold, initialized = [], False
    win = {w: [] for w in WINDOWS}
    next_inv = {w: None for w in WINDOWS}
    for k in range(len(env)):
        tick = env.tick(k)
        t = tick.t
        if not initialized:
            if t < env.hold_s:
                if tick.imu is not None:
                    f_b_hold.append(tick.imu.f_b)
                continue
            fx, fy, fz = np.mean(f_b_hold, axis=0)
            agent.initialize_static(t, tick.truth.pos.copy(),
                                    np.array([np.arctan2(fy, fz), np.arctan2(-fx, np.hypot(fy, fz)),
                                              float(tick.truth.att[2]) + env.initial_heading_noise()]))
            initialized = True
            continue
        gnss_epoch = tick.gnss_epoch
        cur = None
        for w0 in WINDOWS:
            if w0 <= t < w0 + OUTAGE_S:
                if gnss_epoch is not None:
                    ext.step(invalid(t), [])        # realistic 1 Hz invalid fix during the outage
                gnss_epoch = None
            if w0 + OUTAGE_S <= t < w0 + OUTAGE_S + PROBE_S:
                cur = w0
        last["x"] = None
        agent.step(t, tick.imu, tick.quantum, gnss_epoch)
        if cur is not None and last["x"] is not None:
            win[cur].append(last["x"][0] ** 2 + last["x"][1] ** 2)
    means = [float(np.mean(v)) for v in win.values() if len(v) >= 8]
    return dict(seed=seed, grade=grade, window_means=means)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(500, 510)))
    ap.add_argument("--grades", nargs="+", default=["industrial_mems", "tactical"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="results/m1/clock_probe_check_500_509.json")
    a = ap.parse_args()
    print("git at launch:", _git(), flush=True)
    tasks = [(s, g) for g in a.grades for s in a.seeds]
    with ProcessPoolExecutor(max_workers=min(a.workers, 4)) as ex:
        res = list(ex.map(run_one, tasks))
    Path(a.out).write_text(json.dumps(res), encoding="utf8")
    thr = 9.21
    for g in a.grades:
        v = np.array([m for r in res if r["grade"] == g for m in r["window_means"]])
        print(f"{g:16s} n={len(v):3d} median={np.median(v):7.2f} p95={np.percentile(v, 95):7.2f} "
              f"p99={np.percentile(v, 99):7.2f} max={v.max():7.2f} frac>{thr}={np.mean(v > thr):.3f}")
    print("git at end:", _git(), flush=True)


if __name__ == "__main__":
    main()
