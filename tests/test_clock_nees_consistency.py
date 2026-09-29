"""D-066 addendum: model-consistent TCXO clock (truth ClockState and ClockKFConfig share the Brown &
Hwang values q_bias=c^2*h0/2~9e-3 m^2/s, q_drift=c^2*2pi^2*h_-2~3.6e-2 (m/s)^2/s). INTENDED behaviour,
written before the implementation: the clock NEES on a nominal mission must sit inside chi2_2 bounds.
"""
from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import chi2

from fedqpnt.core.types import GnssFix
from fedqpnt.fusion.clock import ClockKF, ClockKFConfig
from fedqpnt.gnss.signal import ClockState

pytestmark = pytest.mark.xfail(reason="D-066 pending implementation (remove when landed)", strict=False)

C = 299_792_458.0


def _fix(t, b, d):
    return GnssFix(t=t, pos=np.zeros(3), vel=np.zeros(3), clk_bias=b, clk_drift=d, cov_pos=np.eye(3),
                   cov_vel=np.eye(3), residual_rms=0.1, num_sats=6, mean_cn0=45.0, std_cn0=1.0,
                   agc_db=0.0, valid=True, raim_stat=1.0)


def test_truth_and_filter_share_tcxo_brown_hwang_values():
    cfg, clk = ClockKFConfig(), ClockState()
    assert cfg.q_bias == pytest.approx(C ** 2 * 2e-19 / 2, rel=0.05)
    assert cfg.q_drift == pytest.approx(C ** 2 * 2 * np.pi ** 2 * 2e-20, rel=0.05)
    assert clk.sigma_bias_rw ** 2 == pytest.approx(cfg.q_bias, rel=1e-6)
    assert clk.sigma_drift_rw ** 2 == pytest.approx(cfg.q_drift, rel=1e-6)


def test_clock_nees_within_chi2_2_bounds_on_nominal_mission():
    cfg = ClockKFConfig()
    n_runs, n_ep = 20, 600
    per_run = []
    for seed in range(500, 500 + n_runs):
        rng = np.random.default_rng(seed)
        truth = ClockState()
        kf = ClockKF(cfg)
        kf.initialize(0.0, bias0=0.0, drift0=0.0)
        nees = []
        for k in range(1, n_ep + 1):
            truth.step(1.0, rng)
            z_b = truth.bias_m + rng.normal(0, np.sqrt(cfg.r_bias))
            z_d = truth.drift_mps + rng.normal(0, np.sqrt(cfg.r_drift))
            sol = kf.step(float(k), _fix(float(k), z_b, z_d), w_gnss=1.0)
            if k > 60:
                e = np.array([sol.bias_m - truth.bias_m, sol.drift_mps - truth.drift_mps])
                nees.append(float(e @ np.linalg.solve(sol.cov, e)))
        per_run.append(np.mean(nees))
    mean_nees = float(np.mean(per_run))
    lo, hi = chi2.ppf([0.025, 0.975], 2 * n_runs) / n_runs
    assert lo <= mean_nees <= hi, f"clock NEES {mean_nees:.2f} outside [{lo:.2f}, {hi:.2f}] (ideal 2)"
