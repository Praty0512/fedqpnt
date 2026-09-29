"""Unit tests for fedqpnt.fusion.eskf.ESKF (WP-4.1).

Uses a constant TrustState (weights={"gnss":1,"imu":1,"quantum":1}) or
explicit weight overrides per test -- fedqpnt.trust is being built by a
parallel agent and is not a dependency here.
"""
from __future__ import annotations

import numpy as np
import pytest

from fedqpnt.core.types import GnssFix, ImuSample, QuantumSample, TrustState, TruthState
from fedqpnt.fusion import ESKF, ESKFConfig
from fedqpnt.sensors.imu import ClassicalImu

G = 9.80665


def _trust(w_gnss=1.0, w_imu=1.0, w_quantum=1.0):
    return TrustState(t=0.0, weights={"gnss": w_gnss, "imu": w_imu, "quantum": w_quantum},
                       anomaly_scores={}, attack_detected=False)


def _fresh_eskf(grade="industrial_mems", seed=0, config=None):
    rng = np.random.default_rng(seed)
    imu = ClassicalImu(grade=grade, rng=rng)
    eskf = ESKF(imu.config(), config=config)
    eskf.initialize_static(0.0, np.zeros(3), np.zeros(3))
    return eskf, imu, rng


def _still_truth(t):
    return TruthState(t=t, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                       att=np.zeros(3), omega_b=np.zeros(3), f_b=np.array([0.0, 0.0, G]))


def _fix(pos, cov_pos=None, cov_vel=None, t=0.0, valid=True):
    return GnssFix(t=t, pos=np.asarray(pos, dtype=float), vel=np.zeros(3), clk_bias=0.0,
                   clk_drift=0.0, cov_pos=cov_pos if cov_pos is not None else np.diag([9.0, 9.0, 25.0]),
                   cov_vel=cov_vel if cov_vel is not None else np.diag([0.01, 0.01, 0.01]),
                   residual_rms=0.0, num_sats=6, mean_cn0=45.0, std_cn0=1.0, agc_db=0.0,
                   valid=valid, raim_stat=0.0)


# --------------------------------------------------------------------------
def test_never_imports_forbidden_modules():
    import fedqpnt.fusion.eskf as mod
    lines = [l for l in open(mod.__file__).read().splitlines()
             if l.strip().startswith(("import ", "from ")) and "fedqpnt" in l]
    assert not any("sim.trajectory" in l or "fedqpnt.sim " in l or l.strip() == "import fedqpnt.sim" for l in lines)
    assert not any("attacks" in l for l in lines)


def test_propagate_static_keeps_p_small_and_symmetric():
    eskf, imu, rng = _fresh_eskf()
    t = 0.0
    for _ in range(500):
        t += 0.01
        s = imu.step(_still_truth(t), rng)
        eskf.propagate(t, s)
    assert np.allclose(eskf.P, eskf.P.T)
    assert np.linalg.eigvalsh(eskf.P).min() > 0
    assert np.linalg.norm(eskf.p) < 5.0  # 5 s of stationary industrial-MEMS drift, loose bound


def test_gnss_exclusion_w_zero_no_effect_on_100m_jump():
    eskf, imu, rng = _fresh_eskf()
    fix = _fix([100.0, 0.0, 0.0])
    innov = eskf.innovations(0.0, fix, None)
    nav = eskf.correct(0.0, innov, _trust(w_gnss=0.0))
    assert np.allclose(nav.pos, 0.0, atol=1e-6)


def test_gnss_partial_trust_intermediate_update():
    fix = _fix([2.0, 0.0, 0.0])

    eskf_full, _, _ = _fresh_eskf()
    innov_full = eskf_full.innovations(0.0, fix, None)
    nav_full = eskf_full.correct(0.0, innov_full, _trust(w_gnss=1.0))

    eskf_partial, _, _ = _fresh_eskf()
    innov_partial = eskf_partial.innovations(0.0, fix, None)
    nav_partial = eskf_partial.correct(0.0, innov_partial, _trust(w_gnss=0.3))

    assert 0.0 < nav_partial.pos[0] < nav_full.pos[0] < 2.0


def test_nis_gate_rejects_50m_jump_hard_gating_ablation():
    # D-057: "hard" gating is the old drop-on-gate behaviour, kept only for
    # ablation (default is now "soft" -- see the soft-gating tests below).
    eskf, _, _ = _fresh_eskf(config=ESKFConfig(gating="hard"))
    fix = _fix([50.0, 0.0, 0.0])
    innov = eskf.innovations(0.0, fix, None)
    assert innov[0].accepted is False
    nav = eskf.correct(0.0, innov, _trust())
    assert np.allclose(nav.pos, 0.0, atol=1e-6)


def test_soft_gating_default_never_fully_rejects_abrupt_50m_jump():
    # D-057: default gating="soft" keeps the measurement (inflating R_eff so
    # the effective NIS == the chi2 gate) instead of dropping it outright.
    # The state is pulled by a bounded amount, never the full 50 m, and
    # never zero either.
    eskf, _, _ = _fresh_eskf()
    assert eskf.cfg.gating == "soft"
    fix = _fix([50.0, 0.0, 0.0])
    innov = eskf.innovations(0.0, fix, None)
    assert innov[0].accepted is False  # still flagged as gate-exceeding...
    nav = eskf.correct(0.0, innov, _trust())
    assert 0.0 < nav.pos[0] < 50.0  # ...but not fully rejected, and bounded


def test_soft_gating_slowly_dragged_fix_never_fully_rejected():
    # A fix dragged slowly (small per-epoch innovation, well inside the
    # gate) is accepted normally; even once it eventually exceeds the gate
    # it must still move the state (D-057's regression target: no
    # free-inertial coasting from a hard-rejected slow drag).
    eskf, imu, rng = _fresh_eskf()
    t = 0.0
    drag_rate = 2.0  # m/s of fake GNSS bias drift per second
    pulled_any = False
    for step in range(200):
        t = (step + 1) * 0.1
        s = imu.step(_still_truth(t), rng)
        eskf.propagate(t, s)
        drifted_pos = np.array([drag_rate * t, 0.0, 0.0])
        fix = _fix(drifted_pos, t=t)
        innov = eskf.innovations(t, fix, None)
        pos_before = eskf.p.copy()
        eskf.correct(t, innov, _trust())
        if not innov[0].accepted:
            # gate-exceeding epoch: soft gating must still move p toward the fix
            assert eskf.p[0] > pos_before[0]
            pulled_any = True
    assert pulled_any  # sanity: the drag rate did eventually exceed the gate


def test_nis_gate_accepts_small_consistent_fix():
    eskf, _, _ = _fresh_eskf()
    fix = _fix([1.0, 0.0, 0.0])  # well within the 3 m init sigma
    innov = eskf.innovations(0.0, fix, None)
    assert innov[0].accepted is True
    nav = eskf.correct(0.0, innov, _trust())
    assert nav.pos[0] > 0.0


def test_hygiene_eigenvalue_clip_exact_single_source_delta_ba():
    # D-043: _hygiene() must symmetrise + clip only negative eigenvalues to
    # 0, with NO additive floor. Regression: a single-source delta b_a case
    # (P0 nonzero ONLY in one b_a axis, zero IMU noise, static level
    # attitude) must give an exact analytic sqrt(P_v) = sigma_ba * t at
    # 300 s (the old additive-floor bug injected ~3x the real per-step
    # gyro-bias process noise whenever P went near-singular, growing P_v
    # ~1.5x above this exact value via t^4 amplification through psi).
    zero_noise = dict(random_walk_per_sqrt_s=0.0, bias_instability_gm1_sigma=0.0,
                       bias_instability_gm1_tau_c_s=1.0, turn_on_bias_std=0.0,
                       scale_factor_std=0.0, misalignment_std_rad=0.0)
    imu_cfg = dict(accel_noise_SI=dict(zero_noise), gyro_noise_SI=dict(zero_noise))
    sigma_ba = 0.01  # m/s^2
    eskf = ESKF(imu_cfg)
    eskf.initialize_static(0.0, np.zeros(3), np.zeros(3))
    eskf.P = np.zeros((eskf.N, eskf.N))
    eskf.P[9, 9] = sigma_ba ** 2  # single source: b_a x-axis only

    dt = 0.1
    t = 0.0
    for _ in range(3000):  # 300 s
        t += dt
        eskf.propagate(t, ImuSample(t=t, f_b=np.array([0.0, 0.0, G]), omega_b=np.zeros(3)))

    assert np.linalg.eigvalsh(eskf.P).min() >= 0.0
    expected = sigma_ba * t
    assert np.isclose(np.sqrt(eskf.P[3, 3]), expected, rtol=1e-6)


def test_gnss_invalid_fix_produces_no_innovation():
    eskf, _, _ = _fresh_eskf()
    fix = _fix([1.0, 0.0, 0.0], valid=False)
    innov = eskf.innovations(0.0, fix, None)
    assert innov == []


def test_nav_solution_fills_cov_vel_and_biases():
    eskf, imu, rng = _fresh_eskf()
    t = 0.0
    s = imu.step(_still_truth(t + 0.01), rng)
    eskf.propagate(0.01, s)
    innov = eskf.innovations(0.01, None, None)
    nav = eskf.correct(0.01, innov, _trust())
    assert nav.cov_vel.shape == (3, 3)
    assert not np.any(np.isnan(nav.cov_vel))
    assert nav.acc_bias.shape == (3,)
    assert nav.gyro_bias.shape == (3,)


def test_quantum_valid_false_skips_update():
    eskf, imu, rng = _fresh_eskf()
    t = 0.0
    s = imu.step(_still_truth(0.01), rng)
    eskf.propagate(0.01, s)
    q = QuantumSample(t=0.01, f_b=np.array([0.0, 0.0, G]), variance=np.full(3, 1e-8),
                       valid=False, cycle_time=1.0, t_interrogation=0.01, response="triangular")
    innov = eskf.innovations(0.01, None, q)
    assert innov == []


def test_quantum_nan_axes_dropped_from_h():
    eskf, imu, rng = _fresh_eskf()
    t = 0.0
    for _ in range(5):
        t += 0.01
        s = imu.step(_still_truth(t), rng)
        eskf.propagate(t, s)
    q = QuantumSample(t=t, f_b=np.array([np.nan, np.nan, G]), variance=np.array([np.nan, np.nan, 1e-10]),
                       valid=True, cycle_time=0.05, t_interrogation=0.01, response="triangular")
    innov = eskf.innovations(t, None, q)
    assert len(innov) == 1
    assert innov[0].dof == 1


def test_determinism_same_seed_same_trajectory():
    def run():
        eskf, imu, rng = _fresh_eskf(seed=7)
        t = 0.0
        for _ in range(200):
            t += 0.01
            s = imu.step(_still_truth(t), rng)
            eskf.propagate(t, s)
        return eskf.p.copy(), eskf.P.copy()

    p1, P1 = run()
    p2, P2 = run()
    assert np.array_equal(p1, p2)
    assert np.array_equal(P1, P2)


def test_world_schuler_tangent_accepted_and_finite():
    eskf, imu, rng = _fresh_eskf(config=ESKFConfig(world="schuler_tangent"))
    t = 0.0
    for _ in range(200):
        t += 0.01
        s = imu.step(_still_truth(t), rng)
        eskf.propagate(t, s)
    assert np.all(np.isfinite(eskf.P))
    assert np.all(np.isfinite(eskf.p))


def test_step_convenience_wrapper_matches_manual_sequence():
    eskf_a, imu, rng = _fresh_eskf(seed=1)
    eskf_b = ESKF(imu.config())
    eskf_b.initialize_static(0.0, np.zeros(3), np.zeros(3))
    t = 0.01
    s = ImuSample(t=t, f_b=np.array([0.0, 0.0, G]), omega_b=np.zeros(3))
    fix = _fix([0.5, 0.0, 0.0], t=t)

    eskf_a.propagate(t, s)
    innov = eskf_a.innovations(t, fix, None)
    nav_a = eskf_a.correct(t, innov, _trust())

    nav_b = eskf_b.step(t, s, None, fix, _trust())

    assert np.allclose(nav_a.pos, nav_b.pos)
    assert np.allclose(nav_a.P if hasattr(nav_a, "P") else eskf_a.P, eskf_b.P)
