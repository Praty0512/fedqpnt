"""Bit-identical equivalence harness for the PERF agent's optimisation pass
(Master perf task). Runs the full node pipeline (fedqpnt.node.environment +
fedqpnt.node.agent, methods `fedqpnt_local` and `fixed_trust`) for 3 seeds
x 60s and captures every per-tick output (IMU sample, quantum/CAI sample,
GNSS epoch + fix, NavSolution fields, trust weights, clock) into a single
npz "trace". `--save-before <path>` snapshots the reference trace BEFORE
any optimisation edits; `--compare <path>` re-runs and compares against
that snapshot with np.array_equal on every array (no tolerance -- exact
bit match required).

Usage:
    python scripts/perf_bitident_check.py --save-before before.npz
    python scripts/perf_bitident_check.py --compare before.npz
"""
from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config

SEEDS = [101, 202, 303]
METHODS = ["fedqpnt_local", "fixed_trust"]
DURATION_S = 60.0
DT = 0.01


def run_one(seed: int, method: str) -> dict[str, np.ndarray]:
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=5.0,
                         heading_noise_deg=2.0, attacks=[])
    env = NodeEnvironment(env_cfg, seed=seed, node_id="node0", dt=DT, duration_s=DURATION_S)
    agent_cfg = make_agent_config(method, kappa_R=40.0, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True)
    agent = Agent(agent_cfg, env.imu.config(), node_id="node0")

    rows = dict(
        t=[], imu_f_b=[], imu_omega_b=[], q_valid=[], q_f_b=[], nav_pos=[], nav_vel=[],
        nav_att=[], nav_cov_pos=[], nav_cov_vel=[], nav_acc_bias=[], nav_gyro_bias=[],
        clk_bias=[], w_gnss=[], w_quantum=[], attack_detected=[], gnss_n_sat=[],
        fix_pos=[], fix_valid=[],
    )
    f_b_hold: list[np.ndarray] = []
    initialized = False
    for k in range(len(env)):
        tick = env.tick(k)
        t = tick.t
        if not initialized:
            if t < env.hold_s:
                if tick.imu is not None:
                    f_b_hold.append(tick.imu.f_b)
                continue
            f_mean = np.mean(f_b_hold, axis=0) if f_b_hold else np.array([0.0, 0.0, 9.80665])
            phi0 = float(np.arctan2(-f_mean[1], f_mean[2]))
            theta0 = float(np.arctan2(f_mean[0], np.sqrt(f_mean[1] ** 2 + f_mean[2] ** 2)))
            psi0 = float(tick.truth.att[2]) + env.initial_heading_noise()
            pos0 = tick.truth.pos.copy()
            agent.initialize_static(t, pos0, np.array([phi0, theta0, psi0]))
            initialized = True
            continue

        atick = agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)

        rows["t"].append(t)
        rows["imu_f_b"].append(tick.imu.f_b.copy() if tick.imu is not None else np.full(3, np.nan))
        rows["imu_omega_b"].append(tick.imu.omega_b.copy() if tick.imu is not None else np.full(3, np.nan))
        rows["q_valid"].append(bool(tick.quantum.valid) if tick.quantum is not None else False)
        rows["q_f_b"].append(tick.quantum.f_b.copy() if (tick.quantum is not None and tick.quantum.f_b is not None) else np.full(3, np.nan))
        rows["nav_pos"].append(atick.nav.pos.copy())
        rows["nav_vel"].append(atick.nav.vel.copy())
        rows["nav_att"].append(atick.nav.att.copy())
        rows["nav_cov_pos"].append(atick.nav.cov_pos.copy())
        rows["nav_cov_vel"].append(atick.nav.cov_vel.copy())
        rows["nav_acc_bias"].append(atick.nav.acc_bias.copy())
        rows["nav_gyro_bias"].append(atick.nav.gyro_bias.copy())
        rows["clk_bias"].append(atick.clock.bias_m if atick.clock is not None else np.nan)
        rows["w_gnss"].append(atick.trust.weights.get("gnss", 1.0))
        rows["w_quantum"].append(atick.trust.weights.get("quantum", 1.0))
        rows["attack_detected"].append(bool(atick.trust.attack_detected))
        rows["gnss_n_sat"].append(len(tick.gnss_epoch.obs) if tick.gnss_epoch is not None else -1)
        rows["fix_pos"].append(atick.fix.pos.copy() if (atick.fix is not None and atick.fix.valid) else np.full(3, np.nan))
        rows["fix_valid"].append(bool(atick.fix.valid) if atick.fix is not None else False)

    out = {}
    for k, v in rows.items():
        arr = np.asarray(v)
        out[k] = arr
    return out


def run_all() -> dict[str, np.ndarray]:
    trace: dict[str, np.ndarray] = {}
    for seed in SEEDS:
        for method in METHODS:
            prefix = f"s{seed}_{method}_"
            r = run_one(seed, method)
            for k, v in r.items():
                trace[prefix + k] = v
    return trace


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--save-before", type=str)
    g.add_argument("--compare", type=str)
    args = ap.parse_args()

    trace = run_all()

    if args.save_before:
        np.savez(args.save_before, **trace)
        print(f"Saved reference trace ({len(trace)} arrays) to {args.save_before}")
        return

    ref = np.load(args.compare, allow_pickle=False)
    ref_keys = set(ref.files)
    new_keys = set(trace.keys())
    if ref_keys != new_keys:
        print("KEY MISMATCH")
        print("missing:", ref_keys - new_keys)
        print("extra:", new_keys - ref_keys)
        sys.exit(1)

    n_bad = 0
    for k in sorted(ref_keys):
        a, b = ref[k], trace[k]
        if a.dtype.kind == "f" and np.isnan(a).any():
            ok = np.array_equal(a, b, equal_nan=True)
        else:
            ok = np.array_equal(a, b)
        if not ok:
            n_bad += 1
            diff = None
            try:
                diff = np.nanmax(np.abs(a.astype(float) - b.astype(float)))
            except Exception:
                pass
            print(f"MISMATCH: {k}  max_abs_diff={diff}")
    if n_bad == 0:
        print(f"BIT-IDENTICAL: all {len(ref_keys)} arrays match exactly across "
              f"{len(SEEDS)} seeds x {len(METHODS)} methods x {DURATION_S}s.")
    else:
        print(f"FAILED: {n_bad}/{len(ref_keys)} arrays differ.")
        sys.exit(1)


if __name__ == "__main__":
    main()
