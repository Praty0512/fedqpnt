"""Unit tests for scripts/h2_abrupt_metrics.py (D-064 pre-registered metric
code). Synthetic arrays only -- no fedqpnt/ internals touched beyond the
read-only fedqpnt.eval.metrics imports the module itself already uses.
Run with: python -m pytest tests/test_h2_abrupt_metrics.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from h2_abrupt_metrics import (  # noqa: E402
    calibrate_tau, onset_detection, onset_window_auc, full_window_auc,
    recovery_alarm_rate, epochs_from_tick_trace, paired_wilcoxon_summary,
)


def _clean_mission(n_epochs=3600, seed=0, spike_every=None, spike_height=2.0):
    """1 Hz clean mission: n_epochs seconds, low-level noise scores, no
    attack. Optional periodic spikes to test FAR calibration precisely."""
    rng = np.random.default_rng(seed)
    t = np.arange(n_epochs, dtype=float)
    scores = rng.normal(0.05, 0.02, size=n_epochs).clip(min=0.0)
    if spike_every:
        scores[::spike_every] += spike_height
    return t, scores


def test_calibrate_tau_hits_target_far_on_synthetic_spikes():
    # 1 spike every 3600s (1 hour) of clean data -> exactly 1 crossing/hour
    # at a tau just below the spike height, so calibration should land tau
    # between the noise floor and the spike height.
    t, scores = _clean_mission(n_epochs=3 * 3600, spike_every=3600, spike_height=5.0)
    out = calibrate_tau(scores, t, target_far_per_hour=1.0)
    assert out["clean_hours"] == pytest.approx(3.0, rel=0.05)
    assert out["achieved_far_per_hour"] <= 1.0 + 1e-9
    # tau should sit below the spike height (5.05) but above ordinary noise
    # (~0.05-0.15) so ONLY the spikes cross it.
    assert 0.15 < out["tau"] < 5.2


def test_calibrate_tau_raises_on_too_few_epochs():
    with pytest.raises(ValueError):
        calibrate_tau(np.array([0.1]), np.array([0.0]))


def test_onset_detection_detects_within_window():
    # 200s mission: onset at t=100, raw_p crosses tau=0.5 at t=103 (3s
    # latency) and stays high through the rest of the (labelled) attack.
    t = np.arange(200, dtype=float)
    active = (t >= 100) & (t < 150)
    raw_p = np.full(200, 0.05)
    raw_p[103:150] = 0.9
    res = onset_detection(t, active, raw_p, tau=0.5, pd_window_s=10.0, censor_s=60.0)
    assert res.detected_at_10s is True
    assert res.censored is False
    assert res.latency_s == pytest.approx(3.0)
    assert res.t_on == pytest.approx(100.0)


def test_onset_detection_censored_when_no_crossing():
    t = np.arange(200, dtype=float)
    active = (t >= 100) & (t < 150)
    raw_p = np.full(200, 0.05)   # never crosses tau
    res = onset_detection(t, active, raw_p, tau=0.5, pd_window_s=10.0, censor_s=60.0)
    assert res.detected_at_10s is False
    assert res.censored is True
    assert res.latency_s == pytest.approx(60.0)


def test_onset_detection_late_crossing_not_detected_at_10s_but_not_censored():
    t = np.arange(200, dtype=float)
    active = (t >= 100) & (t < 150)
    raw_p = np.full(200, 0.05)
    raw_p[130:150] = 0.9   # crosses at t=130 -> latency 30s, > 10s window
    res = onset_detection(t, active, raw_p, tau=0.5, pd_window_s=10.0, censor_s=60.0)
    assert res.detected_at_10s is False
    assert res.censored is False
    assert res.latency_s == pytest.approx(30.0)


def test_onset_window_auc_separates_clean_onset_signal():
    t = np.arange(200, dtype=float)
    active = (t >= 100) & (t < 150)
    raw_p = np.full(200, 0.05)
    raw_p[100:110] = 0.9   # onset window (first 10s) clearly elevated
    out = onset_window_auc(t, active, raw_p, window_s=10.0)
    assert out["auc"] == pytest.approx(1.0)
    assert out["n_pos"] == 10
    # compute_phases excludes the first T_ALIGN_S=60s as an alignment
    # transient, so pre-onset = [60,100) = 40 epochs, not the full [0,100).
    assert out["n_neg"] == 40


def test_full_window_auc_can_go_below_chance_like_the_live_finding():
    # replicate the qualitative D-062 finding: attack window scores LOWER
    # than baseline -> AUC < 0.5.
    t = np.arange(200, dtype=float)
    active = (t >= 100) & (t < 150)
    raw_p = np.full(200, 0.5)
    raw_p[active] = 0.1   # attack epochs score LOWER than nominal
    out = full_window_auc(t, active, raw_p)
    assert out["auc"] < 0.5


def test_recovery_alarm_rate_isolated_from_auc_negatives():
    t = np.arange(200, dtype=float)
    active = (t >= 100) & (t < 150)
    raw_p = np.full(200, 0.05)
    raw_p[150:] = 0.9   # every post-attack epoch alarms
    out = recovery_alarm_rate(t, active, raw_p, tau=0.5)
    assert out["recovery_alarm_rate"] == pytest.approx(1.0)
    assert out["n_post"] == 50
    # and confirm full_window_auc / onset_window_auc never touch post at all
    # (pre-onset-only negatives for onset_window_auc):
    onset_out = onset_window_auc(t, active, raw_p, window_s=10.0)
    assert onset_out["n_neg"] == 40  # pre-onset only ([60,100), T_ALIGN_S excluded), post excluded


def test_epochs_from_tick_trace_downselects_to_gnss_epochs():
    t = np.arange(10, dtype=float)
    active = np.zeros(10, dtype=bool)
    raw_p = np.arange(10, dtype=float)
    has_gnss = np.array([True, False, False, True, False, False, True, False, False, True])
    t2, active2, raw_p2 = epochs_from_tick_trace(t, active, raw_p, has_gnss)
    assert list(t2) == [0.0, 3.0, 6.0, 9.0]
    assert list(raw_p2) == [0.0, 3.0, 6.0, 9.0]


def test_paired_wilcoxon_summary_smoke():
    x = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
    y = np.array([0.15, 0.18, 0.35, 0.38, 0.52])
    out = paired_wilcoxon_summary(x, y)
    assert out["n"] == 5
    assert "wilcoxon_p" in out
