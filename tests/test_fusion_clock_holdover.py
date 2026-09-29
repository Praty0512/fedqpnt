"""D-065/D-066 (i): ClockKF hard-exclusion holdover. INTENDED behaviour, written before
the implementation (fails until ClockKFConfig.w_excl + the skip land).

Ruling: when w_gnss < w_excl (ESKF convention, 0.05), skip the measurement update and free-run
on the oscillator model. Q is NOT scaled by trust (Q is oscillator physics).
"""
from __future__ import annotations

import numpy as np
import pytest

from fedqpnt.core.types import GnssFix
from fedqpnt.fusion.clock import ClockKF, ClockKFConfig





def _fix(t, clk_bias, clk_drift):
    return GnssFix(t=t, pos=np.zeros(3), vel=np.zeros(3), clk_bias=clk_bias, clk_drift=clk_drift,
                   cov_pos=np.eye(3), cov_vel=np.eye(3), residual_rms=0.1, num_sats=6,
                   mean_cn0=45.0, std_cn0=1.0, agc_db=0.0, valid=True, raim_stat=1.0)


def _warm(kf, n=60, bias0=5.0, drift0=0.02):
    for k in range(1, n + 1):
        t = float(k)
        kf.step(t, _fix(t, bias0 + drift0 * t, drift0), w_gnss=1.0)
    return float(n)


def test_default_w_excl_matches_eskf_convention():
    assert ClockKFConfig().w_excl == 0.05


def test_meaconed_fix_below_w_excl_is_ignored_and_clock_free_runs():
    kf = ClockKF(ClockKFConfig())
    kf.initialize(0.0, bias0=5.0, drift0=0.02)
    t0 = _warm(kf)
    x_before = kf.x.copy()
    # 180 epochs of a +753 m meaconed clock bias, trust pinned at w_min (0.02 < w_excl)
    for k in range(1, 181):
        t = t0 + k
        sol = kf.step(t, _fix(t, 753.0 + 5.0 + 0.02 * t, 0.02), w_gnss=0.02)
    coast_bias = x_before[0] + x_before[1] * 180.0
    assert abs(sol.bias_m - coast_bias) < 1e-6, "estimate must equal pure oscillator-model coast"
    assert abs(sol.drift_mps - x_before[1]) < 1e-9


def test_covariance_still_grows_in_holdover_q_not_trust_scaled():
    kf = ClockKF(ClockKFConfig())
    kf.initialize(0.0, bias0=0.0, drift0=0.0)
    t0 = _warm(kf, n=30, bias0=0.0, drift0=0.0)
    p_before = float(np.trace(kf.P))
    kf_ref = ClockKF(ClockKFConfig())
    kf_ref.initialize(0.0, bias0=0.0, drift0=0.0)
    _warm(kf_ref, n=30, bias0=0.0, drift0=0.0)
    for k in range(1, 61):
        t = t0 + k
        kf.step(t, _fix(t, 999.0, 0.0), w_gnss=0.0)   # excluded
        kf_ref.step(t, None, w_gnss=1.0)              # no fix at all
    assert float(np.trace(kf.P)) > p_before
    assert np.allclose(kf.P, kf_ref.P), "holdover P must equal the no-fix coast P (Q unscaled)"


def test_above_w_excl_still_updates():
    kf = ClockKF(ClockKFConfig())
    kf.initialize(0.0, bias0=0.0, drift0=0.0)
    kf.step(1.0, _fix(1.0, 50.0, 0.0), w_gnss=1.0)
    assert kf.x[0] > 10.0
