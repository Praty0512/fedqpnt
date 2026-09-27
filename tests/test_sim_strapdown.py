"""Tests for fedqpnt.sim.strapdown (WP-1.2, ARCHITECTURE.md section 11.3)."""
from __future__ import annotations

import time

import numpy as np
import pytest

from fedqpnt.sim.rotations import dcm_to_euler, euler_to_dcm, so3_log
from fedqpnt.sim.strapdown import NavState, gravity_n, integrate, strapdown_step
from fedqpnt.sim.trajectory import GroundVehicleTrajectory, UavTrajectory, make_trajectory

G0 = 9.80665


def test_gravity_n_default():
    assert np.allclose(gravity_n(), [0.0, 0.0, -G0])


def test_gravity_n_schuler_matches_core_world():
    from fedqpnt.core import world as core_world
    pos = np.array([100.0, -200.0, 50.0])
    assert np.allclose(gravity_n(pos, "schuler_tangent"), core_world.gravity_n(pos, "schuler_tangent"))


def _closure_case(traj, method, world="flat"):
    N = len(traj)
    init = NavState(pos=traj.pos[0].copy(), vel=traj.vel[0].copy(), C=euler_to_dcm(traj.att[0]))
    pos, vel, att = integrate(traj.t, traj.f_b, traj.omega_b, init, method=method, world=world)
    pos_err = np.linalg.norm(pos - traj.pos, axis=1)
    C_true = euler_to_dcm(traj.att)
    C_est = euler_to_dcm(att)
    att_err = np.array([np.linalg.norm(so3_log(C_est[k].T @ C_true[k])) for k in range(N)])
    return pos_err, att_err


@pytest.mark.parametrize("platform", ["ground", "uav"])
@pytest.mark.parametrize("seed", [600, 601, 602, 603, 604])
def test_rk4_closure_600s(platform, seed):
    rng = np.random.default_rng(seed)
    traj_gen = make_trajectory(platform)
    traj = traj_gen.generate(600.0, 0.01, rng)
    pos_err, att_err = _closure_case(traj, "rk4")
    assert np.max(pos_err) < 1.0, f"rk4 pos error {np.max(pos_err):.4f} m (seed {seed}, {platform})"
    assert np.max(att_err) < 1e-5, f"rk4 att error {np.max(att_err):.3e} rad (seed {seed}, {platform})"


@pytest.mark.parametrize("platform", ["ground", "uav"])
def test_causal_closure_600s_report_only(platform, capsys):
    rng = np.random.default_rng(700)
    traj_gen = make_trajectory(platform)
    traj = traj_gen.generate(600.0, 0.01, rng)
    pos_err, att_err = _closure_case(traj, "causal")
    print(f"\n[causal closure, {platform}, 600s] max pos err = {np.max(pos_err):.4f} m, "
          f"max att err = {np.max(att_err):.3e} rad (report only, no threshold)")


@pytest.mark.parametrize("platform", ["ground", "uav"])
def test_rk4_closure_3600s_report_only(platform, capsys):
    rng = np.random.default_rng(800)
    traj_gen = make_trajectory(platform)
    traj = traj_gen.generate(3600.0, 0.01, rng)
    pos_err, att_err = _closure_case(traj, "rk4")
    print(f"\n[rk4 closure, {platform}, 3600s] max pos err = {np.max(pos_err):.4f} m, "
          f"max att err = {np.max(att_err):.3e} rad (report only)")


@pytest.mark.parametrize("platform", ["ground", "uav"])
def test_strapdown_closure_schuler_world_report_only(platform, capsys):
    """Master's extra request: run the closure test with world='schuler_tangent'
    (self-consistent: truth is generated with schuler gravity too -- see the
    PROPOSED-DECISION docstring in trajectory.py). No hard bound: the point is
    to exercise the position-dependent-gravity code path end to end and report
    the numbers honestly."""
    rng = np.random.default_rng(900)
    traj_gen = make_trajectory(platform)
    traj = traj_gen.generate(600.0, 0.01, rng, world="schuler_tangent")
    pos_err, att_err = _closure_case(traj, "rk4", world="schuler_tangent")
    print(f"\n[rk4 closure, {platform}, 600s, schuler_tangent] max pos err = {np.max(pos_err):.4f} m, "
          f"max att err = {np.max(att_err):.3e} rad (report only)")
    assert np.all(np.isfinite(pos_err)) and np.all(np.isfinite(att_err))


def test_strapdown_step_matches_integrate_causal():
    rng = np.random.default_rng(11)
    traj = GroundVehicleTrajectory().generate(60.0, 0.01, rng)
    init = NavState(pos=traj.pos[0].copy(), vel=traj.vel[0].copy(), C=euler_to_dcm(traj.att[0]))
    pos, vel, att = integrate(traj.t, traj.f_b, traj.omega_b, init, method="causal")
    # manual loop must match integrate()'s causal path exactly
    state = init
    for k in range(len(traj) - 1):
        dt = float(traj.t[k + 1] - traj.t[k])
        state = strapdown_step(state, traj.f_b[k], traj.omega_b[k], traj.f_b[k + 1], traj.omega_b[k + 1], dt)
    assert np.allclose(state.pos, pos[-1])
    assert np.allclose(state.vel, vel[-1])


def test_integrate_runtime_600s():
    rng = np.random.default_rng(12)
    traj = GroundVehicleTrajectory().generate(600.0, 0.01, rng)
    init = NavState(pos=traj.pos[0].copy(), vel=traj.vel[0].copy(), C=euler_to_dcm(traj.att[0]))
    t0 = time.perf_counter()
    integrate(traj.t, traj.f_b, traj.omega_b, init, method="rk4")
    dt_rk4 = time.perf_counter() - t0
    t0 = time.perf_counter()
    integrate(traj.t, traj.f_b, traj.omega_b, init, method="causal")
    dt_causal = time.perf_counter() - t0
    per_hour_rk4 = dt_rk4 * 3600.0 / 600.0
    per_hour_causal = dt_causal * 3600.0 / 600.0
    print(f"\n[strapdown runtime] rk4: {per_hour_rk4:.2f} s/simulated-hour; "
          f"causal: {per_hour_causal:.2f} s/simulated-hour")
