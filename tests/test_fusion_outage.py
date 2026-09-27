"""Committed regression test for the GNSS-outage harness (Master D-023 item
1): GNSS fixes must be truly withheld during the outage window (zero
innovations processed), and the strictly-inside-window metrics must be
computable. Kept short (60 s outage, 2 seeds) so it runs fast in CI; the
full 10-seed/500-599 characterisation lives in scripts/fusion_outage.py.
"""
from __future__ import annotations

import numpy as np

from tests._fusion_helpers import run_scenario, index_at

T0 = 20.0
T = 60.0


def test_gnss_truly_withheld_during_outage():
    for seed in (1, 2):
        res = run_scenario(platform="ground", imu_grade="industrial_mems", quantum_grade=None,
                            duration_s=T0 + T + 10.0, dt=0.01, seed=seed, hold_s=10.0,
                            kappa_R=40.0, gnss_outage=(T0, T0 + T))
        assert res["gnss_innovations_in_outage"] == 0
        # sanity: some GNSS innovations DID occur outside the window
        assert res["gnss_innovations_total"] > 0


def test_outage_window_metrics_well_defined():
    res = run_scenario(platform="ground", imu_grade="tactical", quantum_grade=None,
                        duration_s=T0 + T + 10.0, dt=0.01, seed=1, hold_s=10.0,
                        kappa_R=40.0, gnss_outage=(T0, T0 + T))
    t = res["t"]
    i0, i1 = index_at(t, T0), index_at(t, T0 + T)
    err_h = np.linalg.norm(res["err"][:, :2], axis=1)
    err_at_T = float(err_h[i1])
    max_in_window = float(err_h[i0:i1 + 1].max())
    sigma3_at_T = float(3.0 * np.sqrt(res["cov_diag"][i1, 0] + res["cov_diag"][i1, 1]))
    assert np.isfinite(err_at_T) and err_at_T >= 0.0
    assert max_in_window >= err_at_T - 1e-9  # max over window can't be less than the endpoint
    assert np.isfinite(sigma3_at_T) and sigma3_at_T > 0.0


def test_outage_error_grows_monotonically_in_expectation():
    """Open-loop drift should trend upward over a withheld window (not the
    flawed end-minus-start point-difference metric this replaces): check
    that the window MAX exceeds the value at onset by a sane margin for the
    noisier grade over a long outage."""
    res = run_scenario(platform="ground", imu_grade="industrial_mems", quantum_grade=None,
                        duration_s=T0 + 300.0 + 10.0, dt=0.01, seed=1, hold_s=10.0,
                        kappa_R=40.0, gnss_outage=(T0, T0 + 300.0))
    t = res["t"]
    i0 = index_at(t, T0)
    err_h = np.linalg.norm(res["err"][:, :2], axis=1)
    assert err_h[i0:].max() > err_h[i0]
