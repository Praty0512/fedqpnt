"""WP-8.1: fedqpnt.eval.metrics formulas on synthetic inputs with known
answers (ARCHITECTURE.md section 6, D-025 timing metrics)."""
from __future__ import annotations

import numpy as np

from fedqpnt.eval import metrics as M


def test_horizontal_and_3d_and_velocity_error_known_values():
    pos_est = np.array([[3.0, 4.0, 0.0], [0.0, 0.0, 5.0]])
    pos_true = np.zeros((2, 3))
    e_h = M.horizontal_error(pos_est, pos_true)
    e_3 = M.full3d_error(pos_est, pos_true)
    assert np.allclose(e_h, [5.0, 0.0])
    assert np.allclose(e_3, [5.0, 5.0])

    vel_est = np.array([[1.0, 0.0, 0.0]])
    vel_true = np.array([[0.0, 0.0, 0.0]])
    assert np.allclose(M.velocity_error(vel_est, vel_true), [1.0])


def test_rmse_max_p95_known_values():
    e = np.array([1.0, 2.0, 3.0, 4.0])
    assert M.rmse(e) == np.sqrt(np.mean(e ** 2))
    assert M.max_err(e) == 4.0
    assert M.p95_err(e) == np.percentile(e, 95)
    assert np.isnan(M.rmse(e, mask=np.zeros(4, dtype=bool)))


def test_anees_pos_ideal_consistency_gives_one():
    """delta_p^2 / sigma^2 averaged over 3 axes = 1 when |delta_p| = sigma
    on every axis -- the textbook ANEES=1 (consistent filter) case."""
    n = 100
    pos_true = np.zeros((n, 3))
    pos_est = np.full((n, 3), 2.0)
    cov_diag = np.full((n, 3), 4.0)  # sigma^2 = 4 = delta_p^2
    assert abs(M.anees_pos(pos_est, pos_true, cov_diag) - 1.0) < 1e-9


def test_anees_pos_overconfident_gives_above_one():
    n = 50
    pos_true = np.zeros((n, 3))
    pos_est = np.full((n, 3), 4.0)
    cov_diag = np.full((n, 3), 4.0)  # delta_p^2=16 >> sigma^2=4
    assert M.anees_pos(pos_est, pos_true, cov_diag) > 1.0


def test_compute_phases_simple_attack_window():
    t = np.arange(0.0, 20.0, 1.0)
    active = (t >= 8.0) & (t < 15.0)
    ph = M.compute_phases(t, active, t_align=5.0)
    assert ph.t_on == 8.0
    assert ph.t_off == 15.0
    assert np.array_equal(ph.pre, (t >= 5.0) & (t < 8.0))
    assert np.array_equal(ph.att, (t >= 8.0) & (t < 15.0))
    assert np.array_equal(ph.post, t >= 15.0)


def test_compute_phases_no_attack_is_all_pre():
    t = np.arange(0.0, 10.0, 1.0)
    active = np.zeros_like(t, dtype=bool)
    ph = M.compute_phases(t, active, t_align=3.0)
    assert ph.t_on is None and ph.t_off is None
    assert np.array_equal(ph.pre, t >= 3.0)
    assert not np.any(ph.att)
    assert not np.any(ph.post)


def test_detection_latency_immediate_and_censored_miss():
    t = np.arange(0.0, 10.0, 1.0)
    active = (t >= 3.0) & (t < 7.0)
    ph = M.compute_phases(t, active, t_align=0.0)

    detected_immediate = active.copy()  # detector fires exactly with the attack
    lat = M.detection_latency(t, detected_immediate, ph, t_sus=0.5)
    assert abs(lat - 0.0) < 1e-9

    detected_never = np.zeros_like(t, dtype=bool)
    lat_miss = M.detection_latency(t, detected_never, ph, t_sus=0.5)
    assert abs(lat_miss - (ph.t_off - ph.t_on)) < 1e-9  # censored at t_off - t_on


def test_false_alarm_rate_counts_only_isolated_clean_rising_edges():
    t = np.arange(0.0, 100.0, 1.0)
    active = np.zeros_like(t, dtype=bool)
    detected = np.zeros_like(t, dtype=bool)
    detected[10] = True  # single isolated false alarm, far from any active window
    res = M.false_alarm_rate(t, detected, active, t_sus=0.5)
    assert res["fa_events"] == 1.0
    # 100 clean samples at dt=1s => 100/3600 h of clean time
    assert abs(res["far_per_hour"] - (1.0 / (100.0 / 3600.0))) < 1e-6


def test_recovery_time_known_recovery_point():
    t = np.arange(0.0, 30.0, 1.0)
    e_h = np.where(t < 20.0, 50.0, 1.0)  # error drops to 1 m at t=20 and stays there
    active = (t >= 5.0) & (t < 10.0)
    ph = M.compute_phases(t, active, t_align=0.0)
    t_rec = M.recovery_time(t, e_h, ph, rmse_pre=1.0, t_hold=5.0)
    assert abs(t_rec - (20.0 - ph.t_off)) < 1e-9


def test_recovery_time_no_recovery_returns_nan():
    t = np.arange(0.0, 30.0, 1.0)
    e_h = np.full_like(t, 100.0)
    active = (t >= 5.0) & (t < 10.0)
    ph = M.compute_phases(t, active, t_align=0.0)
    assert np.isnan(M.recovery_time(t, e_h, ph, rmse_pre=1.0, t_hold=5.0))


def test_trust_cycles_counts_one_full_cycle():
    t = np.arange(0.0, 6.0, 1.0)
    w = np.array([1.0, 0.4, 0.3, 0.95, 1.0, 1.0])  # crosses below .5 then above .9
    assert M.trust_cycles(t, w) == 1


def test_trust_cycles_no_cycle_if_never_recovers_above_09():
    t = np.arange(0.0, 4.0, 1.0)
    w = np.array([1.0, 0.4, 0.3, 0.3])
    assert M.trust_cycles(t, w) == 0


def test_total_variation_per_hour_known_value():
    t = np.array([0.0, 1800.0, 3600.0])  # 1-hour span
    w = np.array([1.0, 0.0, 1.0])        # TV = 1 + 1 = 2
    assert abs(M.total_variation_per_hour(t, w) - 2.0) < 1e-9


def test_clock_bias_error_ns_known_value():
    # 1 m of range-equivalent bias error = 1/C_LIGHT s = 1e9/C_LIGHT ns
    est = np.array([1.0])
    true = np.array([0.0])
    expected = 1e9 / M.C_LIGHT
    assert abs(M.clock_bias_error_ns(est, true)[0] - expected) < 1e-9


def test_roc_auc_perfect_and_chance():
    scores_perfect = np.array([0.1, 0.2, 0.8, 0.9])
    labels = np.array([False, False, True, True])
    assert abs(M.roc_auc(scores_perfect, labels) - 1.0) < 1e-9

    scores_chance = np.array([0.5, 0.5, 0.5, 0.5])
    assert abs(M.roc_auc(scores_chance, labels) - 0.5) < 1e-9

    assert np.isnan(M.roc_auc(np.array([0.1, 0.2]), np.array([False, False])))
