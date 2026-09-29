"""Master-directed measurement (D-063 task A): the pure GNSS-coasting error
envelope -- no defense/trust logic involved, GNSS is simply forced absent
(gnss_epoch replaced with None) for an exact 180s window, real ground
motion otherwise nominal. Grid: imu_grade x CAI (quantum on/off), seeds
500-504. Reports RMSE_h, max_h over the outage window, and err_h AT
t_onset+60/120/180.

Not a test; run manually: python scripts/core_robust_coasting_envelope.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config

KAPPA_R = 60.0
SEEDS = list(range(500, 505))
DURATION_S = 400.0
OUTAGE_ONSET_S, OUTAGE_DUR_S = 120.0, 180.0
IMU_GRADES = ["industrial_mems", "tactical"]
CAI_OPTIONS = [True, False]


def run_one(seed: int, imu_grade: str, cai_on: bool) -> dict:
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade=imu_grade,
                         quantum_grade=("field" if cai_on else None), gnss_rate_hz=1.0, hold_s=30.0,
                         heading_noise_deg=2.0, attacks=[])
    env = NodeEnvironment(env_cfg, seed=seed, node_id="coast", dt=0.01, duration_s=DURATION_S)
    agent_cfg = make_agent_config("undefended", kappa_R=KAPPA_R, kappa_Q=1.0, world="flat",
                                   quantum_enabled=cai_on)
    agent = Agent(agent_cfg, env.imu.config(), node_id="coast")

    f_b_hold, initialized = [], False
    err_at = {}
    errs_in_outage = []
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
        in_outage = OUTAGE_ONSET_S <= t < (OUTAGE_ONSET_S + OUTAGE_DUR_S)
        if in_outage:
            gnss_epoch = None  # forced pure outage, regardless of the (attack-free) truth

        atick = agent.step(t, tick.imu, tick.quantum, gnss_epoch)
        err_h = float(np.linalg.norm((atick.nav.pos - tick.truth.pos)[:2]))

        if in_outage:
            errs_in_outage.append(err_h)
        for mark in (60.0, 120.0, 179.0):
            key = round(OUTAGE_ONSET_S + mark, 3)
            if abs(t - key) < 1e-6:
                err_at[mark] = err_h

    errs = np.array(errs_in_outage)
    return dict(rmse=float(np.sqrt(np.mean(errs ** 2))), max=float(np.max(errs)),
                err_at_60=err_at.get(60.0, float("nan")), err_at_120=err_at.get(120.0, float("nan")),
                err_at_180=err_at.get(179.0, float("nan")))


def main() -> None:
    print(f"=== D-063 task A: coasting envelope, {DURATION_S:.0f}s missions, {OUTAGE_DUR_S:.0f}s "
          f"forced outage, tuning seeds {SEEDS} ===\n")
    print(f"{'imu_grade':>16} {'CAI':>5} {'RMSE':>8} {'max':>8} {'@60s':>8} {'@120s':>8} {'@179s':>8}")
    for grade in IMU_GRADES:
        for cai_on in CAI_OPTIONS:
            rows = [run_one(s, grade, cai_on) for s in SEEDS]
            rmse = float(np.mean([r["rmse"] for r in rows]))
            mx = float(np.mean([r["max"] for r in rows]))
            a60 = float(np.mean([r["err_at_60"] for r in rows]))
            a120 = float(np.mean([r["err_at_120"] for r in rows]))
            a180 = float(np.mean([r["err_at_180"] for r in rows]))
            print(f"{grade:>16} {'ON' if cai_on else 'OFF':>5} {rmse:8.2f} {mx:8.2f} "
                  f"{a60:8.2f} {a120:8.2f} {a180:8.2f}")
            print(f"{'':>16} {'':>5}   per-seed @179s: {[round(r['err_at_180'], 2) for r in rows]}")


if __name__ == "__main__":
    main()
