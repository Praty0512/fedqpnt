"""Tests for fedqpnt.sim.trajectory (WP-1.2, ARCHITECTURE.md section 11.2)."""
from __future__ import annotations

import time

import numpy as np
import pytest

from fedqpnt.sim.rotations import euler_to_dcm, so3_log
from fedqpnt.sim.trajectory import (
    GroundVehicleParams, GroundVehicleTrajectory, UavParams, UavTrajectory, make_trajectory,
)

G0 = 9.80665
SEEDS = [1000, 1001, 1002, 1003, 1004]
DURATIONS = [600.0, 3600.0]


def _gen(platform, seed, duration, dt=0.01):
    rng = np.random.default_rng(seed)
    traj = make_trajectory(platform).generate(duration, dt, rng)
    return traj


@pytest.mark.parametrize("platform", ["ground", "uav"])
@pytest.mark.parametrize("duration", DURATIONS)
@pytest.mark.parametrize("seed", SEEDS)
def test_consistency(platform, duration, seed):
    traj = _gen(platform, seed, duration)
    dt = traj.t[1] - traj.t[0]
    h = dt

    # central-difference velocity vs analytic velocity
    dv = (traj.pos[2:] - traj.pos[:-2]) / (2 * h)
    err_v = np.max(np.abs(dv - traj.vel[1:-1]))
    assert err_v <= 1e-3, f"velocity consistency err={err_v:.3e}"

    da = (traj.vel[2:] - traj.vel[:-2]) / (2 * h)
    err_a = np.max(np.abs(da - traj.acc[1:-1]))
    assert err_a <= 1e-3, f"accel consistency err={err_a:.3e}"

    C = euler_to_dcm(traj.att)
    g = np.array([0.0, 0.0, -G0])
    f_expected = np.einsum('kji,kj->ki', C, traj.acc - g)
    err_f = np.max(np.abs(traj.f_b - f_expected))
    assert err_f <= 1e-9, f"f_b consistency err={err_f:.3e}"

    # omega at midpoint k+1/2 = Log(C_k^T C_{k+1})/h, compare to mean of omega_b[k],omega_b[k+1]
    errs = []
    for k in range(0, len(traj) - 1, max(1, (len(traj) - 1) // 2000)):
        phi = so3_log(C[k].T @ C[k + 1])
        w_mid_est = phi / h
        w_mid_true = 0.5 * (traj.omega_b[k] + traj.omega_b[k + 1])
        errs.append(np.linalg.norm(w_mid_est - w_mid_true))
    assert max(errs) <= 1e-4, f"omega consistency err={max(errs):.3e}"


@pytest.mark.parametrize("platform", ["ground", "uav"])
@pytest.mark.parametrize("duration", DURATIONS)
@pytest.mark.parametrize("seed", SEEDS)
def test_c2_smoothness(platform, duration, seed):
    traj = _gen(platform, seed, duration)
    h = traj.t[1] - traj.t[0]
    dadt = np.linalg.norm(np.diff(traj.acc, axis=0), axis=1) / h
    assert np.max(dadt) <= 10.0, f"jerk bound violated: {np.max(dadt):.3f} m/s^3"


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("duration", DURATIONS)
def test_ground_limits(seed, duration):
    traj = _gen("ground", seed, duration)
    p = GroundVehicleParams()
    tol = 1.01
    s = np.linalg.norm(traj.vel[:, :2], axis=1)
    assert np.max(s) <= p.v_max * tol
    assert np.min(s) >= -1e-6
    a_long = traj.acc[:, 0] * np.cos(traj.att[:, 2]) + traj.acc[:, 1] * np.sin(traj.att[:, 2])
    assert np.max(a_long) <= p.a_acc_max * tol
    assert np.min(a_long) >= -p.a_brake_max * tol
    r = traj.omega_b[:, 2] / np.cos(traj.att[:, 0]).clip(min=0.5)  # approx yaw rate scale, coarse
    assert np.max(np.abs(traj.att[:, 0])) <= np.radians(3.0) * tol + 1e-6
    assert np.max(np.abs(traj.att[:, 1])) <= np.radians(5.0) * tol + 1e-6


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("duration", DURATIONS)
def test_uav_limits(seed, duration):
    traj = _gen("uav", seed, duration)
    p = UavParams()
    tol = 1.01
    s = np.linalg.norm(traj.vel[:, :2], axis=1)
    assert np.max(s) <= p.v_max * tol
    assert np.max(np.abs(traj.vel[:, 2])) <= p.vz_max * tol
    C = euler_to_dcm(traj.att)
    z_b = C[:, :, 2]
    tilt = np.arccos(np.clip(z_b[:, 2], -1, 1))
    assert np.max(tilt) <= np.radians(p.tilt_max_deg) * tol + 1e-6
    after_hover = traj.t > p.t_hover0 + 1.0
    assert np.min(traj.pos[after_hover, 2]) >= p.alt_min - 1.0
    assert np.max(traj.pos[after_hover, 2]) <= p.alt_max + 1.0


@pytest.mark.parametrize("platform", ["ground", "uav"])
def test_determinism(platform):
    rng1 = np.random.default_rng(42)
    rng2 = np.random.default_rng(42)
    t1 = make_trajectory(platform).generate(120.0, 0.01, rng1)
    t2 = make_trajectory(platform).generate(120.0, 0.01, rng2)
    assert np.array_equal(t1.pos, t2.pos)
    assert np.array_equal(t1.vel, t2.vel)
    assert np.array_equal(t1.att, t2.att)

    rng3 = np.random.default_rng(43)
    t3 = make_trajectory(platform).generate(120.0, 0.01, rng3)
    assert not np.array_equal(t1.pos, t3.pos)


@pytest.mark.parametrize("platform,kinds", [
    ("ground", {"cruise", "speed_change", "turn", "stop"}),
    ("uav", {"cruise", "speed_change", "turn", "climb", "loiter", "hover"}),
])
def test_coverage_3600s(platform, kinds):
    rng = np.random.default_rng(2024)
    traj = make_trajectory(platform).generate(3600.0, 0.01, rng)
    seen = {m["kind"] for m in traj.meta["maneuvers"]}
    missing = kinds - seen
    assert not missing, f"missing maneuver kinds: {missing}"


def test_runtime_3600s():
    rng = np.random.default_rng(3000)
    t0 = time.perf_counter()
    make_trajectory("ground").generate(3600.0, 0.01, rng)
    dt_ground = time.perf_counter() - t0
    rng = np.random.default_rng(3001)
    t0 = time.perf_counter()
    make_trajectory("uav").generate(3600.0, 0.01, rng)
    dt_uav = time.perf_counter() - t0
    print(f"\n[trajectory runtime] ground 3600s: {dt_ground:.3f} s; uav 3600s: {dt_uav:.3f} s")
    assert dt_ground < 10.0, f"ground generation too slow: {dt_ground:.3f} s"
    assert dt_uav < 10.0, f"uav generation too slow: {dt_uav:.3f} s"
