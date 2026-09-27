"""Hindsight pseudo-labels, ARCHITECTURE.md §4.3 (WP-4.3, TRUST agent).

Runs offline/hindsight with lag ``L = 30 s`` over one node's recorded epoch
history. Conservative consistency rules:

    y_j = 1   if exists t in [t_j, t_j+L]: S_cusum(t) >= h1=20
              or |agc| >= 6 dB for >= 2 s (within the same window)
              or raim >= chi2_{n-4}(1 - 1e-6)
              or clk_jump (x8) >= 8
              or [D-024] (x14 cn0_xsat_corr above its nominal upper quantile,
                 OR x4 cn0_mean above its nominal band by >= 3 dB) sustained
                 for >= 10 s (single-antenna / replay signature, see the
                 ``_xsat_replay_condition`` docstring)
    y_j = 0   if x1..x11 lie inside their nominal 95% quantiles for EVERY
              epoch in [t_j - L, t_j + L]
    y_j = NaN otherwise (not used for training)

``S_cusum(t)`` is the **INS-GNSS divergence statistic against the CAI-aided
INS solution taken as hindsight reference** (§4.3: "a slowly drifting
CAI-aided INS is a trustworthy hindsight reference"). This module does not
build that statistic itself -- it is a property of the fusion filter, owned
by the FUSION agent, and is not available at M0. Call sites MUST pass an
``s_cusum`` array; for unit tests in ``tests/test_trust_pseudolabel.py`` a
SURROGATE is used (a simple CUSUM computed from x1/nis_pos directly), which
is clearly marked as a surrogate, NOT the real CAI-aided-INS reference.
Real integration happens at M1 once ``fedqpnt.fusion`` exists.

The oracle (``AttackLabel``) is EVALUATOR-ONLY: it must never enter this
module's label computation, only ``evaluate_against_oracle`` below, which
lives in the same file for convenience but is explicitly an evaluation-only
function (mirrors the same restriction the leakage-guard test enforces on
imports -- see ``tests/test_trust_leakage_guard.py``).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import chi2

L_DEFAULT_S = 30.0
H1_DEFAULT = 20.0
AGC_THRESH_DB = 6.0
AGC_DWELL_S = 2.0
CLK_JUMP_THRESH = 8.0
RAIM_PFA = 1e-6
QUANTILE_Z = 1.96  # two-sided 95%

# raw-feature column indices (features.FEATURE_NAMES order)
IDX_NIS_POS, IDX_NIS_VEL, IDX_RAIM, IDX_CN0_MEAN, IDX_CN0_STD, IDX_CN0_RATE, \
    IDX_AGC, IDX_CLK_JUMP, IDX_DRIFT_JUMP, IDX_RESID_RMS, IDX_NSAT_DELTA, \
    IDX_DIV_CUSUM, IDX_OUTAGE, IDX_XSAT_CORR, IDX_ELEV_SLOPE = range(15)

# Labeller v2 (D-051 sec A): sigma floors, sigma_eff,k = max(sigma_ref,k,
# sigma_floor,k), applied to the standardisation sigma BEFORE the joint
# chi2_11 negative rule and the D-024 xsat/cn0 positive rule (both consume
# quantile_sd). Fixes the M1-CLOSE failure mode where a near-degenerate
# feature (nsat_delta, sigma=0.024 on clean converged runs) dominates the
# joint Mahalanobis distance and makes the negative rule vacuous
# (EXECUTION_LOG #80/#83).
#
# PROPOSED-DECISION: x1/x2/x3 (nis_pos, nis_vel, raim) are already divided
# by their dof in this codebase (features.py: _innovation_nis_over_dof
# divides by a fixed dof=3 for nis_pos/nis_vel; raim/dof for x3, dof varying
# per epoch). The D-051 table's "0.5*dof" floor is stated for the RAW chi2
# statistic. Applied to the dof-NORMALISED feature this codebase actually
# carries, the equivalent, dof-invariant floor is 0.5*dof/dof = 0.5 (works
# even though x3's dof varies epoch to epoch, since the floor is on the
# already-normalised quantity, not on dof itself).
# PROPOSED-DECISION: x6 (cn0_rate) gets the same 0.3 floor as the other C/N0
# features -- the D-051 table does not give rate its own floor.
# PROPOSED-DECISION: x10 (resid_rms), x12 (div_cusum) and x13 (outage) are
# not covered by the D-051 table. Rather than invent an unspecified floor,
# they are left un-floored (0.0, a no-op against max()); x12/x13 are not
# consumed by the joint chi2_11 test or the xsat rule in any case.
SIGMA_FLOOR_15 = np.array([
    0.5,   # x1  nis_pos       (NIS/RAIM chi2, dof-normalised; see PROPOSED-DECISION)
    0.5,   # x2  nis_vel
    0.5,   # x3  raim
    0.3,   # x4  cn0_mean      (C/N0, dB-Hz)
    0.3,   # x5  cn0_std       (C/N0, dB-Hz)
    0.3,   # x6  cn0_rate      (C/N0; see PROPOSED-DECISION)
    0.5,   # x7  agc           (dB)
    1.0,   # x8  clk_jump      (already in units of the receiver's reported 1-sigma)
    1.0,   # x9  drift_jump    (ditto)
    0.0,   # x10 resid_rms     -- not in the D-051 table; see PROPOSED-DECISION
    0.5,   # x11 nsat_delta    (integer count)
    0.0,   # x12 div_cusum     -- not in the D-051 table; see PROPOSED-DECISION
    0.0,   # x13 outage        -- not in the D-051 table; see PROPOSED-DECISION
    0.05,  # x14 cn0_xsat_corr (correlation-type)
    0.02,  # x15 cn0_elev_slope (slope, dB/deg)
])


def apply_sigma_floor(quantile_sd: np.ndarray) -> np.ndarray:
    """sigma_eff = max(sigma_ref, sigma_floor), D-051 sec A. Returns a new
    array; ``quantile_sd`` may be 11-, 13- or 15-wide (matches whichever
    slice of FEATURE_NAMES the caller carries)."""
    quantile_sd = np.asarray(quantile_sd, dtype=float).copy()
    n = min(len(quantile_sd), len(SIGMA_FLOOR_15))
    quantile_sd[:n] = np.maximum(quantile_sd[:n], SIGMA_FLOOR_15[:n])
    return quantile_sd


def _dwell(cond: np.ndarray, t: np.ndarray, dwell_s: float) -> np.ndarray:
    """True at index k iff ``cond`` has held continuously for >= dwell_s
    ending at k (causal dwell test, evaluated hindsight over the whole
    array)."""
    n = len(t)
    out = np.zeros(n, dtype=bool)
    run_start = None
    for k in range(n):
        if cond[k]:
            if run_start is None:
                run_start = t[k]
            if t[k] - run_start >= dwell_s:
                out[k] = True
        else:
            run_start = None
    return out


def _agc_dwell_condition(t: np.ndarray, agc: np.ndarray, thresh: float, dwell_s: float) -> np.ndarray:
    """True at index k iff |agc| has been >= thresh continuously for >=
    dwell_s ending at k.

    PROPOSED-DECISION (bug found & fixed per D-022 review): §3.1's rule text
    ("agc >= 6 dB") implicitly assumes AGC RISES under jamming. This
    codebase's ``GnssEpoch.agc_db``/``GnssFix.agc_db`` convention is
    "AGC level relative to nominal" and ``fedqpnt.attacks.jamming.Jamming``
    DECREASES it (front-end gain backs off as total received power rises --
    the physically standard AGC direction, see that module's docstring).
    Under the literal "agc >= +6dB" rule this condition NEVER fired for any
    jamming run (verified: 0/21 epochs across 5 held-out jamming test runs),
    which silently taught the detector "jamming = clean" and produced an
    AUC < 0.5 for the jamming family. Fixed to trigger on |agc| (either
    direction), which also still catches DriftInSpoof/MeaconingReplay's
    small positive power-bump convention.
    """
    return _dwell(np.abs(agc) >= thresh, t, dwell_s)


def _xsat_replay_condition(t: np.ndarray, raw_features: np.ndarray, quantile_mu15: np.ndarray,
                            quantile_sd15: np.ndarray, quantile_z: float, band_excess_db: float,
                            dwell_s: float) -> np.ndarray:
    """D-024: single-antenna / replay signature (Radoš, Brkić & Begušić 2024,
    Sensors 24(13):4210, Fig. 5, D-018): a meaconer/single-antenna spoofer
    re-radiates every PRN from ONE chain, so per-PRN C/N0 values become
    strongly cross-correlated (x14 ``cn0_xsat_corr`` rises well above its
    clean-population value; the paper reports -0.76 clean vs 0.99 spoofed)
    and the replay/re-radiation power bump raises the aggregate C/N0 level
    (x4 ``cn0_mean``) above its clean-population band. Diagnosed in the
    D-022 review: this is the steady-state meaconing signature the original
    §4.3 rule set (h1/agc/raim/clk_jump) does not key on, which mislabelled
    ~95% of active meaconing epochs as negative and taught the detector the
    inverse association (AUC < 0.5). Fires when EITHER sub-condition holds
    continuously for >= dwell_s (default 10s) within the L=30s hindsight
    window -- a physical signature, not a tuned threshold: the reference
    quantiles are the SAME clean-population mu/sd used by the joint chi2_11
    negative rule (calibrated on clean-only runs, never self-referential to
    the run being labelled).
    """
    mu4, sd4 = quantile_mu15[IDX_CN0_MEAN], quantile_sd15[IDX_CN0_MEAN]
    mu14, sd14 = quantile_mu15[IDX_XSAT_CORR], quantile_sd15[IDX_XSAT_CORR]
    cn0_mean = raw_features[:, IDX_CN0_MEAN]
    xsat_corr = raw_features[:, IDX_XSAT_CORR]

    cond_corr = xsat_corr > (mu14 + quantile_z * sd14)           # x14 above nominal upper quantile
    cond_cn0 = cn0_mean > (mu4 + quantile_z * sd4 + band_excess_db)  # x4 above nominal band by >=3dB
    return _dwell(cond_corr, t, dwell_s) | _dwell(cond_cn0, t, dwell_s)


def surrogate_s_cusum(raw_features: np.ndarray, k_c: float = 1.5) -> np.ndarray:
    """A SURROGATE hindsight divergence statistic for unit tests only --
    Page CUSUM of nis_pos (x1), i.e. NOT the CAI-aided-INS reference §4.3
    actually specifies. Real pseudo-labelling must be fed the fusion
    filter's INS-GNSS divergence once ``fedqpnt.fusion`` exists (M1)."""
    x1 = raw_features[:, IDX_NIS_POS]
    s = np.zeros(len(x1))
    acc = 0.0
    for k, v in enumerate(x1):
        acc = max(0.0, acc + v - k_c)
        s[k] = acc
    return s


@dataclass
class PseudoLabelConfig:
    L: float = L_DEFAULT_S
    h1: float = H1_DEFAULT
    agc_thresh_db: float = AGC_THRESH_DB
    agc_dwell_s: float = AGC_DWELL_S
    clk_jump_thresh: float = CLK_JUMP_THRESH
    raim_pfa: float = RAIM_PFA
    quantile_z: float = QUANTILE_Z
    quantile_z_confidence: float = 0.95  # joint chi2_11 quantile (see label_epochs docstring/comment)
    window_clean_fraction: float = 0.9
    xsat_dwell_s: float = 10.0          # D-024 sustained-dwell requirement
    xsat_cn0_band_excess_db: float = 3.0  # D-024 x4 must exceed its nominal band by this much
    enable_xsat_rule: bool = True       # D-026 2x2 diagnostic switch (frozen design: True)


def label_epochs(
    t: np.ndarray,
    raw_features: np.ndarray,   # (N, 13), columns = features.FEATURE_NAMES order
    raim_stat: np.ndarray,      # (N,) fix.raim_stat
    num_sats: np.ndarray,       # (N,) fix.num_sats
    s_cusum: np.ndarray,        # (N,) hindsight INS-GNSS divergence (real: CAI-aided INS; here may be a surrogate)
    cfg: PseudoLabelConfig | None = None,
    quantile_mu: np.ndarray | None = None,
    quantile_sd: np.ndarray | None = None,
) -> np.ndarray:
    """Returns ``(N,)`` float array in {1.0, 0.0, nan} (nan = abstain, ``∅``).

    ``quantile_mu``/``quantile_sd`` are the federated normalisation stats
    (§4.2), length matching ``raw_features.shape[1]`` (13 or 15 -- the D-024
    xsat-replay rule needs the 15-wide v0.3 columns and is a no-op otherwise);
    if omitted, empirical mean/std over the whole passed history is used
    (fine for the offline/hindsight setting this runs in, but per D-024 the
    caller SHOULD pass clean-only-calibrated stats, never self-referential
    ones, for both this rule and the x1..x11 negative rule).
    """
    cfg = cfg or PseudoLabelConfig()
    n = len(t)
    t = np.asarray(t, dtype=float)
    raw_features = np.asarray(raw_features, dtype=float)
    raim_stat = np.asarray(raim_stat, dtype=float)
    num_sats = np.asarray(num_sats, dtype=float)
    s_cusum = np.asarray(s_cusum, dtype=float)

    agc = raw_features[:, IDX_AGC]
    clk_jump = raw_features[:, IDX_CLK_JUMP]
    agc_dwell_ok = _agc_dwell_condition(t, agc, cfg.agc_thresh_db, cfg.agc_dwell_s)

    dof = np.clip(num_sats - 4, 1, None)
    raim_thresh = chi2.ppf(1.0 - cfg.raim_pfa, dof)
    raim_alarm = raim_stat >= raim_thresh

    n_cols = raw_features.shape[1]
    if quantile_mu is None or quantile_sd is None:
        quantile_mu_full = raw_features.mean(axis=0)
        quantile_sd_full = raw_features.std(axis=0)
        quantile_sd_full = np.where(quantile_sd_full < 1e-9, 1.0, quantile_sd_full)
    else:
        quantile_mu_full = np.asarray(quantile_mu, dtype=float)
        quantile_sd_full = np.asarray(quantile_sd, dtype=float)

    # Labeller v2 (D-051 sec A): sigma floors, applied regardless of whether
    # quantile_sd was supplied by the caller or computed above.
    quantile_sd_full = apply_sigma_floor(quantile_sd_full)

    # D-024: single-antenna/replay signature (x14 cn0_xsat_corr, x4 cn0_mean).
    # Only evaluated when the caller's feature matrix / reference actually
    # carries the v0.3 (D-022) columns (15-wide) -- older 13-wide callers
    # (unit tests exercising the original x1..x11 rule set) fall back to no
    # xsat contribution rather than an index error.
    if cfg.enable_xsat_rule and n_cols > IDX_XSAT_CORR and len(quantile_mu_full) > IDX_XSAT_CORR:
        xsat_event = _xsat_replay_condition(
            t, raw_features, quantile_mu_full, quantile_sd_full,
            cfg.quantile_z, cfg.xsat_cn0_band_excess_db, cfg.xsat_dwell_s)
    else:
        xsat_event = np.zeros(n, dtype=bool)

    pos_event = (s_cusum >= cfg.h1) | agc_dwell_ok | raim_alarm | (clk_jump >= cfg.clk_jump_thresh) | xsat_event

    quantile_mu = quantile_mu_full[0:11]
    quantile_sd = quantile_sd_full[0:11]

    # PROPOSED-DECISION: "lie inside their nominal 95% quantiles" is
    # implemented as a JOINT Mahalanobis/chi-square test over the 11-dim
    # (x1..x11) vector (chi2_11(0.95)), not 11 independent per-dimension
    # z<1.96 tests ANDed together. The per-dimension-AND reading makes the
    # negative rule practically vacuous: even on genuinely clean data, each
    # dimension has an independent ~5% marginal excursion rate, so requiring
    # ALL 11 dimensions AND every epoch in a +-30s (61-epoch) window to pass
    # gives a false-negative-almost-always outcome ((0.95)^11 ~= 0.57 per
    # epoch, then ~0.57^61 ~= 0 over the window) -- verified empirically:
    # zero negative pseudo-labels were produced on 25 real clean/attacked
    # calibration runs before this fix. The joint test is a standard
    # multivariate-normal generalisation of "inside the 95% region" and
    # keeps the rule genuinely usable while remaining conservative.
    diff = raw_features[:, 0:11] - quantile_mu
    maha_sq = np.sum((diff / quantile_sd) ** 2, axis=1)
    joint_thresh = chi2.ppf(cfg.quantile_z_confidence, df=11)
    nominal = maha_sq <= joint_thresh  # (N,) per-epoch "x1..x11 jointly nominal"

    y = np.full(n, np.nan)
    for j in range(n):
        fut_lo = np.searchsorted(t, t[j], side="left")
        fut_hi = np.searchsorted(t, t[j] + cfg.L, side="right")
        if np.any(pos_event[fut_lo:fut_hi]):
            y[j] = 1.0
            continue
        both_lo = np.searchsorted(t, t[j] - cfg.L, side="left")
        both_hi = np.searchsorted(t, t[j] + cfg.L, side="right")
        window = nominal[both_lo:both_hi]
        # PROPOSED-DECISION: relaxed from a literal "every epoch" AND to a
        # >=90% clean-fraction dwell test, mirroring the recovery gate's own
        # frac_clean_threshold=0.9 (§3.3 eq 4) -- the same chattering/false-
        # negative-robustness argument applies here (one spurious single-
        # epoch excursion inside an otherwise clean 60s window should not
        # veto the whole window).
        if len(window) > 0 and (np.sum(window) / len(window)) >= cfg.window_clean_fraction:
            y[j] = 0.0
    return y


def pseudolabel_precision_recall(y_pred: np.ndarray, oracle_positive: np.ndarray) -> dict[str, float]:
    """EVALUATOR-ONLY. ``oracle_positive`` is a boolean array built from
    ``AttackLabel`` (never seen by ``label_epochs``/training). Abstains
    (``nan``) count as a miss for recall and are excluded from the
    precision denominator (they never assert positive)."""
    y_pred = np.asarray(y_pred, dtype=float)
    oracle_positive = np.asarray(oracle_positive, dtype=bool)
    pred_pos = y_pred == 1.0
    tp = np.sum(pred_pos & oracle_positive)
    fp = np.sum(pred_pos & ~oracle_positive)
    fn = np.sum(~pred_pos & oracle_positive)
    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else float("nan")
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else float("nan")
    return dict(precision=precision, recall=recall, n_pos_pred=int(np.sum(pred_pos)),
                n_abstain=int(np.sum(np.isnan(y_pred))), n_oracle_pos=int(np.sum(oracle_positive)))
