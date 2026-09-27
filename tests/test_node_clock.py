"""WP-8.1 clock-KF consistency tests (fedqpnt/fusion/clock.py, D-025/D-027)."""
from __future__ import annotations

import numpy as np

from fedqpnt.core.types import GnssFix
from fedqpnt.fusion.clock import ClockKF, ClockKFConfig


def _fix(t: float, clk_bias: float, clk_drift: float, valid: bool = True) -> GnssFix:
    return GnssFix(t=t, pos=np.zeros(3), vel=np.zeros(3), clk_bias=clk_bias, clk_drift=clk_drift,
                    cov_pos=np.eye(3), cov_vel=np.eye(3), residual_rms=0.1, num_sats=6,
                    mean_cn0=45.0, std_cn0=1.0, agc_db=0.0, valid=valid, raim_stat=1.0)


def test_clock_kf_converges_to_constant_bias_drift():
    rng = np.random.default_rng(0)
    true_bias, true_drift = 1000.0, 0.5
    kf = ClockKF(ClockKFConfig())
    kf.initialize(0.0, bias0=0.0, drift0=0.0)
    dt = 1.0
    t = 0.0
    for k in range(1, 200):
        t = k * dt
        true_bias_k = true_bias + true_drift * t
        z_bias = true_bias_k + rng.normal(0, 0.5)
        z_drift = true_drift + rng.normal(0, 0.02)
        sol = kf.step(t, _fix(t, z_bias, z_drift), w_gnss=1.0)
    assert sol is not None
    true_bias_final = true_bias + true_drift * t
    assert abs(sol.bias_m - true_bias_final) / true_bias_final < 0.05
    assert abs(sol.drift_mps - true_drift) < 0.05


def test_clock_kf_coasts_with_no_fix_and_covariance_grows():
    kf = ClockKF(ClockKFConfig())
    kf.initialize(0.0, bias0=10.0, drift0=1.0)
    t = 0.0
    trace_before = float(np.trace(kf.P))
    sol = None
    for k in range(1, 50):
        t = k * 1.0
        sol = kf.step(t, None, w_gnss=1.0)
    assert sol is not None
    # pure drift-model coast: bias should have advanced by ~drift * elapsed
    assert abs(sol.bias_m - (10.0 + 1.0 * t)) < 1e-6
    assert np.trace(sol.cov) > trace_before  # uncertainty grows with no aiding


def test_clock_kf_low_trust_inflates_effective_r_and_slows_convergence():
    """R_eff = R / max(w, w_min): a low-trust GNSS fix should pull the
    estimate toward a bad measurement much less than a fully-trusted one."""
    cfg = ClockKFConfig()

    kf_trusted = ClockKF(ClockKFConfig(**cfg.__dict__))
    kf_trusted.initialize(0.0, bias0=0.0, drift0=0.0)
    kf_distrusted = ClockKF(ClockKFConfig(**cfg.__dict__))
    kf_distrusted.initialize(0.0, bias0=0.0, drift0=0.0)

    bad_bias = 5000.0  # a wild single-epoch outlier
    sol_trusted = kf_trusted.step(1.0, _fix(1.0, bad_bias, 0.0), w_gnss=1.0)
    sol_distrusted = kf_distrusted.step(1.0, _fix(1.0, bad_bias, 0.0), w_gnss=0.02)

    assert abs(sol_distrusted.bias_m) < abs(sol_trusted.bias_m)


def test_clock_kf_ignores_invalid_fix():
    kf = ClockKF(ClockKFConfig())
    kf.initialize(0.0, bias0=3.0, drift0=0.1)
    sol = kf.step(1.0, _fix(1.0, 9999.0, 9999.0, valid=False), w_gnss=1.0)
    assert abs(sol.bias_m - (3.0 + 0.1 * 1.0)) < 1e-6  # pure coast, fix ignored
