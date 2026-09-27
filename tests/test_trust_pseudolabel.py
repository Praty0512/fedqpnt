"""§4.3 pseudo-label unit tests. Uses the SURROGATE ``surrogate_s_cusum``
(nis_pos Page CUSUM) in place of the real CAI-aided-INS hindsight reference,
which needs the fusion filter (M1). This is a synthetic-signal unit test of
the labelling RULES themselves, not an end-to-end validation (that lives in
tests/test_trust_detector.py, on real GNSS+attack runtime data)."""
from __future__ import annotations

import numpy as np

from fedqpnt.trust.pseudolabel import (
    PseudoLabelConfig, label_epochs, surrogate_s_cusum, pseudolabel_precision_recall,
)


def _synthetic_clean_features(n: int, rng: np.random.Generator) -> np.ndarray:
    feats = np.zeros((n, 13))
    feats[:, 0] = np.abs(rng.normal(1.0, 0.2, n))    # x1 nis_pos ~ chi2_3/3 mean 1
    feats[:, 1] = np.abs(rng.normal(1.0, 0.2, n))    # x2 nis_vel
    feats[:, 2] = np.abs(rng.normal(0.0, 0.3, n))    # x3 raim
    feats[:, 3] = rng.normal(0.0, 1.0, n)             # x4 cn0_mean (centred on ref)
    feats[:, 4] = np.abs(rng.normal(1.0, 0.3, n))    # x5 cn0_std
    feats[:, 5] = rng.normal(0.0, 0.5, n)             # x6 cn0_rate
    feats[:, 6] = rng.normal(0.0, 0.5, n)             # x7 agc (well below 6 dB)
    feats[:, 7] = np.abs(rng.normal(0.0, 0.5, n))    # x8 clk_jump
    feats[:, 8] = np.abs(rng.normal(0.0, 0.2, n))    # x9 drift_jump
    feats[:, 9] = np.abs(rng.normal(0.5, 0.2, n))    # x10 resid_rms
    feats[:, 10] = rng.integers(-1, 2, n).astype(float)  # x11 nsat_delta
    feats[:, 11] = surrogate_s_cusum(feats[:, :12])       # x12 (recomputed below anyway)
    feats[:, 12] = 0.0                                     # x13 outage
    return feats


def test_clean_signal_yields_negative_labels():
    rng = np.random.default_rng(1)
    n = 200
    t = np.arange(n) * 1.0
    feats = _synthetic_clean_features(n, rng)
    raim_stat = np.abs(rng.normal(0.0, 0.3, n))
    num_sats = np.full(n, 8)
    s_cusum = surrogate_s_cusum(feats)

    y = label_epochs(t, feats, raim_stat, num_sats, s_cusum)
    frac_neg = np.mean(y == 0.0)
    frac_pos = np.mean(y == 1.0)
    assert frac_pos == 0.0, "clean synthetic data must never get a positive pseudo-label"
    assert frac_neg > 0.3, f"clean data produced almost no negatives (frac_neg={frac_neg})"


def test_sustained_agc_jump_triggers_positive_label():
    rng = np.random.default_rng(2)
    n = 200
    t = np.arange(n) * 1.0
    feats = _synthetic_clean_features(n, rng)
    onset = 100
    feats[onset:onset + 20, 6] = 10.0  # x7 agc >= 6 dB for 20 epochs (>> 2s dwell)
    raim_stat = np.abs(rng.normal(0.0, 0.3, n))
    num_sats = np.full(n, 8)
    s_cusum = surrogate_s_cusum(feats)

    y = label_epochs(t, feats, raim_stat, num_sats, s_cusum)
    L = 30
    # epochs whose [t_j, t_j+L] window reaches the agc dwell condition (which
    # itself only fires 2s into the run, at index 102) must be positive.
    dwell_start = onset + 2
    window_epochs = np.arange(max(0, dwell_start - L), onset + 1)
    assert np.all(y[window_epochs] == 1.0)


def test_raim_alarm_triggers_positive_label():
    rng = np.random.default_rng(3)
    n = 150
    t = np.arange(n) * 1.0
    feats = _synthetic_clean_features(n, rng)
    num_sats = np.full(n, 8)
    raim_stat = np.abs(rng.normal(0.0, 0.3, n))
    from scipy.stats import chi2
    onset = 80
    raim_stat[onset] = chi2.ppf(1 - 1e-7, 4)  # well above the 1-1e-6 alarm threshold
    s_cusum = surrogate_s_cusum(feats)

    y = label_epochs(t, feats, raim_stat, num_sats, s_cusum)
    assert y[onset] == 1.0 or y[max(onset - 30, 0)] == 1.0


def test_abstain_when_neither_rule_fires():
    """A single epoch with one feature moderately elevated (not enough to
    trigger any y=1 rule) inside an otherwise-clean run should push its
    window's clean-fraction below 0.9, so nearby epochs abstain rather than
    being forced to y=0 (conservative: 'not used for training')."""
    rng = np.random.default_rng(4)
    n = 60
    t = np.arange(n) * 1.0
    feats = _synthetic_clean_features(n, rng)
    # a fixed, well-calibrated reference (as a real federated normalizer
    # would provide) -- computed BEFORE injecting the lone excursion, so the
    # excursion itself cannot inflate its own reference sigma.
    ref_mu = np.zeros(13)
    ref_sd = np.ones(13)
    ref_mu[0:11] = feats[:, 0:11].mean(axis=0)
    ref_sd[0:11] = feats[:, 0:11].std(axis=0)
    # x5 (cn0_std, index 4): does not feed any y=1 rule (those are driven by
    # s_cusum/x1, agc/x7, raim, clk_jump/x8), so it can only affect the
    # negative-rule's joint-nominal test, isolating the abstain path.
    feats[30, 4] = 50.0
    raim_stat = np.abs(rng.normal(0.0, 0.3, n))
    num_sats = np.full(n, 8)
    s_cusum = surrogate_s_cusum(feats)

    y = label_epochs(t, feats, raim_stat, num_sats, s_cusum,
                      cfg=PseudoLabelConfig(window_clean_fraction=0.99),
                      quantile_mu=ref_mu, quantile_sd=ref_sd)
    assert np.any(np.isnan(y[10:50])), "expected at least one abstain near the lone excursion"


def test_precision_recall_against_oracle():
    y_pred = np.array([1.0, 1.0, 0.0, 0.0, np.nan, 1.0, 0.0])
    oracle = np.array([True, False, False, False, True, True, True])
    m = pseudolabel_precision_recall(y_pred, oracle)
    # TP: idx0, idx5 ; FP: idx1 ; FN: idx4 (abstain, oracle True), idx6 (pred 0, oracle True)
    assert m["precision"] == 2 / 3
    assert m["recall"] == 2 / 4
