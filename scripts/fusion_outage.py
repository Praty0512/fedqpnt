"""GNSS-outage characterisation for the ESKF (WP-4.1, Master D-023 item 1).

Not a test; run manually. Uses seeds 500-599 (tuning/characterisation range,
NOT test-seed results per ARCHITECTURE.md Sec 7.6). Reports, strictly INSIDE
the withheld window [t0, t0+T]:
  * horizontal error at t0+T,
  * max horizontal error over the window,
  * the filter's own 3-sigma (horizontal) at t0+T, for a consistency check.
Also verifies (assertion, not just a print) that ZERO GNSS innovations were
processed while withheld.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from tests._fusion_helpers import run_scenario, index_at

T0 = 60.0  # outage onset, in truth.t (i.e. 50 s of real driving after the 10 s hold)
N_SEEDS = 10
SEEDS = list(range(500, 500 + N_SEEDS))
KAPPA_R = 40.0  # PROVISIONAL, see FUSION_NOTES.md item 2 (Master D-023)


def one_run(grade, use_cai, outlier_channel, T, seed):
    quantum_grade = "field" if use_cai else None
    res = run_scenario(platform="ground", imu_grade=grade, quantum_grade=quantum_grade,
                        duration_s=T0 + T + 30.0, dt=0.01, seed=seed, hold_s=10.0,
                        kappa_R=KAPPA_R, gnss_outage=(T0, T0 + T),
                        quantum_outlier_channel=outlier_channel)
    assert res["gnss_innovations_in_outage"] == 0, (
        f"GNSS innovation processed inside the withheld window! seed={seed}, grade={grade}, T={T}")
    t = res["t"]
    i0 = index_at(t, T0)
    i1 = index_at(t, T0 + T)
    err_h = np.linalg.norm(res["err"][:, :2], axis=1)
    err_at_T = float(err_h[i1])
    max_err_in_window = float(err_h[i0:i1 + 1].max())
    sigma3_at_T = float(3.0 * np.sqrt(res["cov_diag"][i1, 0] + res["cov_diag"][i1, 1]))
    return err_at_T, max_err_in_window, sigma3_at_T, res


def sweep():
    configs = [
        ("industrial_mems", False, True, "no CAI"),
        ("industrial_mems", True, False, "CAI FIELD, outlier OFF (pure hybridisation)"),
        ("industrial_mems", True, True, "CAI FIELD, outlier ON (fixed trust)"),
        ("tactical", False, True, "no CAI"),
        ("tactical", True, False, "CAI FIELD, outlier OFF (pure hybridisation)"),
        ("tactical", True, True, "CAI FIELD, outlier ON (fixed trust)"),
    ]
    out = {}
    for grade, use_cai, outlier_ch, label in configs:
        for T in (60.0, 300.0):
            key = f"{grade}|{label}|T={int(T)}s"
            errs, maxes, sig3s = [], [], []
            for seed in SEEDS:
                e, m, s3, _ = one_run(grade, use_cai, outlier_ch, T, seed)
                errs.append(e); maxes.append(m); sig3s.append(s3)
            print(f"{key}: err@T mean={np.mean(errs):.2f} median={np.median(errs):.2f} "
                  f"max={np.max(errs):.2f} | max-in-window mean={np.mean(maxes):.2f} "
                  f"max={np.max(maxes):.2f} | 3sigma@T mean={np.mean(sig3s):.2f}", flush=True)
            out[key] = {"err_at_T": errs, "max_in_window": maxes, "sigma3_at_T": sig3s}
    return out


def sanity_check_tactical_no_cai():
    """0.5*b*T^2 expected vs measured, tactical, no CAI, T=300s, seed=500.
    Two expectations are reported: the NAIVE one (full configured turn-on
    bias, as if never corrected) and the REALISTIC one (the filter's own
    residual bias ERROR at the moment the outage begins, since 50s of
    GNSS-aided flight precedes it and partially observes b_a)."""
    T = 300.0
    e, m, s3, res = one_run("tactical", False, True, T, 500)
    t = res["t"]
    i0 = index_at(t, T0)
    b_true_t0 = res["acc_bias_true"][i0]
    b_est_t0 = res["acc_bias_est"][i0]
    residual_at_t0 = float(np.linalg.norm((b_est_t0 - b_true_t0)[:2]))  # horizontal-plane
    turn_on_std_axis = float(res["imu"].config()["accel"]["turn_on_bias_std"])
    turn_on_std = turn_on_std_axis * np.sqrt(2.0)  # combined horizontal-plane (x,y) magnitude
    expected_naive = 0.5 * turn_on_std * T ** 2
    expected_realistic = 0.5 * residual_at_t0 * T ** 2
    print(f"sanity(tactical,no-CAI,T=300s,seed=500): configured turn_on_bias_std={turn_on_std:.4e} m/s^2 -> "
          f"naive 0.5*b*T^2={expected_naive:.1f} m (assumes b_a NEVER corrected)")
    print(f"  filter's residual |b_a_est - b_a_true| at outage onset (t={T0}s, after 50s GNSS-aided "
          f"flight) = {residual_at_t0:.4e} m/s^2 -> realistic 0.5*b_resid*T^2={expected_realistic:.1f} m")
    print(f"  measured horizontal error @ t0+T = {e:.2f} m (max in window = {m:.2f} m)")
    return turn_on_std, expected_naive, residual_at_t0, expected_realistic, e


if __name__ == "__main__":
    sanity_check_tactical_no_cai()
    sweep()
