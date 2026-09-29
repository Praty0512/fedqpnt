"""D-064 item (3): DRY RUN ONLY -- proves scripts/h2_abrupt_metrics.py's
pipeline runs end-to-end on a mission matching the (invalid, pre-D-064)
h2_abrupt run's config. **The numbers this script prints are NOT results**
(no valid frozen-core re-run has happened; tau is calibrated on a tiny,
cheap clean sample, nowhere near the pre-registered >=5h/arm requirement).
This exists only to demonstrate the metric code is correct and runnable
before the real (parked) re-run.

Single node, single process, cheap: one short clean "mission" for a rough
tau (a few simulated minutes, NOT the pre-registered 580-599/>=5h clean
calibration set) + one abrupt-attack mission at the pre-registered
severity=0.15, seed=500, matching h2_abrupt_h2h4_driver.py's NOVEL_ABRUPT
config. Uses the SAME 1Hz-epoch extraction (tick.gnss_epoch is not None)
that scripts/h2_abrupt_metrics.py's docstring specifies.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import load_detector_weights, make_agent_config

from h2_abrupt_metrics import (
    calibrate_tau, onset_detection, onset_window_auc, full_window_auc, recovery_alarm_rate,
)

THETA0_PATH = Path("results/fleet/theta0_noabrupt.npz")
KAPPA_R = 60.0
SEED = 500
DURATION_S = 600.0
ONSET_S, ATK_DUR_S = 120.0, 300.0
SEVERITY = 0.15
CLEAN_DURATION_S = 300.0   # DRY RUN ONLY -- tiny compared to the pre-registered >=5h/arm


def run_mission_1hz_epochs(seed: int, attack: dict | None, duration_s: float):
    weights_path = THETA0_PATH if THETA0_PATH.exists() else None
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=30.0,
                         heading_noise_deg=2.0, attacks=[attack] if attack else [])
    env = NodeEnvironment(env_cfg, seed=seed, node_id="dryrun", dt=0.01, duration_s=duration_s)
    agent_cfg = make_agent_config("fedqpnt_local", kappa_R=KAPPA_R, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True,
                                   detector_weights_path=str(weights_path) if weights_path else None)
    agent = Agent(agent_cfg, env.imu.config(), node_id="dryrun")

    f_b_hold, initialized = [], False
    t_out, active_out, raw_p_out = [], [], []
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
            theta0_ = float(np.arctan2(-fx, np.sqrt(fy ** 2 + fz ** 2)))
            psi0 = float(tick.truth.att[2]) + env.initial_heading_noise()
            agent.initialize_static(t, tick.truth.pos.copy(), np.array([phi0, theta0_, psi0]))
            initialized = True
            continue
        agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
        if tick.gnss_epoch is not None:   # D-064 sampling fix: 1 Hz epochs only
            t_out.append(t)
            active_out.append(bool(tick.label.spoofing or tick.label.jamming))
            raw_p = agent.trust.last_raw_p
            raw_p_out.append(float(raw_p) if raw_p is not None else 0.0)
    return np.array(t_out), np.array(active_out, dtype=bool), np.array(raw_p_out, dtype=float)


def main():
    print("=" * 70)
    print("DRY RUN ONLY -- proving scripts/h2_abrupt_metrics.py runs end-to-end.")
    print("These numbers are NOT results (tau calibrated on a tiny sample,")
    print("not the pre-registered >=5h/arm on seeds 580-599; no frozen-core")
    print("re-run has happened). Do not cite these values. See D-064 / ")
    print("docs/specs/raw/H2_PREREG.md.")
    print("=" * 70)

    print(f"\n[1/3] tiny clean mission (seed=999, {CLEAN_DURATION_S}s) for a rough tau...")
    t_c, active_c, raw_p_c = run_mission_1hz_epochs(999, None, CLEAN_DURATION_S)
    assert not active_c.any(), "clean mission unexpectedly has an active-labelled epoch"
    tau_info = calibrate_tau(raw_p_c, t_c, target_far_per_hour=1.0)
    print(f"  tau_info (DRY RUN, tiny sample): {tau_info}")
    tau = tau_info["tau"]

    print(f"\n[2/3] abrupt attack mission (seed={SEED}, onset={ONSET_S}, dur={ATK_DUR_S}, "
          f"severity={SEVERITY})...")
    attack = dict(kind="abrupt_spoof", onset_s=ONSET_S, duration_s=ATK_DUR_S, severity=SEVERITY)
    t, active, raw_p = run_mission_1hz_epochs(SEED, attack, DURATION_S)
    print(f"  n_epochs={len(t)} n_active={int(active.sum())}")

    print("\n[3/3] running the D-064 metric functions...")
    det = onset_detection(t, active, raw_p, tau=tau, pd_window_s=10.0, censor_s=60.0)
    print(f"  onset_detection (tau={tau:.4f}): {det}")
    for w in (5.0, 10.0):
        out = onset_window_auc(t, active, raw_p, window_s=w)
        print(f"  onset_window_auc(N={w}s): {out}")
    full = full_window_auc(t, active, raw_p)
    print(f"  full_window_auc (tertiary/descriptive): {full}")
    rec = recovery_alarm_rate(t, active, raw_p, tau=tau)
    print(f"  recovery_alarm_rate: {rec}")

    print("\n" + "=" * 70)
    print("DRY RUN COMPLETE -- code runs end-to-end. NOT RESULTS. See above disclaimer.")
    print("=" * 70)


if __name__ == "__main__":
    main()
