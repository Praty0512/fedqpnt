"""H2-ABRUPT pre-registered metric code (D-064). See docs/specs/raw/H2_PREREG.md
for the exact, frozen metric definitions this module implements. Pure
functions operating on already-extracted 1 Hz detector-update epoch arrays
(t, active, raw_p) -- NOT on the raw 100 Hz tick arrays node_runner.py
currently logs from (D-064's disclosed sampling fix).

No edits to fedqpnt/ internals; only read-only imports of
fedqpnt.eval.metrics (compute_phases/roc_auc), which are already used
elsewhere in this task (h2_abrupt_theta0_auc_check.py etc.).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fedqpnt.eval import metrics as M


def epochs_from_tick_trace(t: np.ndarray, active: np.ndarray, raw_p: np.ndarray,
                            has_gnss_epoch: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """D-064 sampling fix: down-selects a 100 Hz tick trace to only the
    ticks where a GNSS epoch (and therefore a real detector score update)
    occurred, matching the isolated held-out check's 1 Hz sampling. Callers
    that already log at 1 Hz (e.g. a dedicated epoch-only collector) can
    skip this and pass their arrays straight to the functions below."""
    m = np.asarray(has_gnss_epoch, dtype=bool)
    return np.asarray(t)[m], np.asarray(active, dtype=bool)[m], np.asarray(raw_p, dtype=float)[m]


def calibrate_tau(clean_scores: np.ndarray, clean_t: np.ndarray, target_far_per_hour: float = 1.0,
                   n_grid: int = 2000) -> dict:
    """D-064: tau set so the CLEAN false-alarm rate is target_far_per_hour
    (default 1/h), on 1 Hz epochs from clean missions (no attack_active
    anywhere in ``clean_scores``/``clean_t`` by construction -- callers pass
    only clean-mission data here). FAR is defined the same way as
    ``fedqpnt.eval.metrics.false_alarm_rate`` (rising edges of a threshold
    crossing per clean-hour), but swept over a grid of tau instead of
    reading a pre-thresholded boolean, since tau itself is what we are
    solving for.

    Returns the smallest tau (i.e. most sensitive/lowest threshold) whose
    FAR does not exceed target_far_per_hour; if no tau achieves that
    (FAR always > target even at the max score), returns tau = max(score)+eps
    with the achieved FAR at that point (never exceeds target since FAR=0
    there by construction, as long as scores are finite)."""
    t = np.asarray(clean_t, dtype=float)
    s = np.asarray(clean_scores, dtype=float)
    if len(t) < 2:
        raise ValueError("need >=2 clean epochs to calibrate tau")
    dt = np.median(np.diff(np.sort(np.unique(t))))
    clean_hours = (len(t) * dt) / 3600.0
    if clean_hours <= 0:
        raise ValueError("clean_hours computed as <= 0")

    order = np.argsort(t)
    t_sorted, s_sorted = t[order], s[order]
    grid = np.unique(np.quantile(s_sorted, np.linspace(0.0, 1.0, n_grid)))
    grid = np.concatenate([grid, [grid[-1] + 1e-9]])  # ensure a zero-FAR endpoint exists

    best_tau, best_far = float(grid[-1]), 0.0
    for tau in grid:
        det = s_sorted > tau
        rising = int(np.sum(det[1:] & ~det[:-1])) + (1 if det.size and det[0] else 0)
        far = rising / clean_hours
        if far <= target_far_per_hour:
            best_tau, best_far = float(tau), float(far)
            break  # grid is ascending -> first tau meeting the target is the smallest (most sensitive)
    return dict(tau=best_tau, achieved_far_per_hour=best_far, target_far_per_hour=target_far_per_hour,
                clean_hours=clean_hours, n_clean_epochs=len(t))


@dataclass
class OnsetDetectionResult:
    detected_at_10s: bool
    latency_s: float          # time of first crossing - t_on; censored value if not detected
    censored: bool            # True if no crossing found within the censoring window
    t_on: float
    tau: float


def onset_detection(t: np.ndarray, active: np.ndarray, raw_p: np.ndarray, tau: float,
                     pd_window_s: float = 10.0, censor_s: float = 60.0) -> OnsetDetectionResult:
    """D-064 primary metric, ONE mission (one attack onset): P_D@10s (was
    the first crossing within [t_on, t_on+pd_window_s]?) and onset latency
    (time of first crossing after t_on; censored at censor_s if none found
    within that window, in which case latency_s = censor_s and
    censored=True). Uses ``fedqpnt.eval.metrics.compute_phases`` (read-only)
    to find t_on from the oracle ``active`` label, exactly as node_runner.py
    already does for latency_on/t_dist -- only the CROSSING rule (raw_p vs a
    pre-calibrated FAR-equalised tau, not the trust law's own
    theta_on/theta_off hysteresis) and the epoch sampling (1 Hz, not 100 Hz)
    differ from the existing ``M.detection_latency``."""
    t = np.asarray(t, dtype=float)
    active = np.asarray(active, dtype=bool)
    raw_p = np.asarray(raw_p, dtype=float)
    phases = M.compute_phases(t, active)
    if phases.t_on is None:
        raise ValueError("no attack-active epoch found in this mission")
    t_on = phases.t_on

    window_mask = (t >= t_on) & (t <= t_on + censor_s)
    idx = np.flatnonzero(window_mask & (raw_p > tau))
    if idx.size == 0:
        return OnsetDetectionResult(detected_at_10s=False, latency_s=censor_s, censored=True,
                                     t_on=t_on, tau=tau)
    first_cross_t = float(t[idx[0]])
    latency = first_cross_t - t_on
    return OnsetDetectionResult(detected_at_10s=bool(latency <= pd_window_s), latency_s=latency,
                                 censored=False, t_on=t_on, tau=tau)


def onset_window_auc(t: np.ndarray, active: np.ndarray, raw_p: np.ndarray, window_s: float) -> dict:
    """D-064 secondary metric: AUC with positives = epochs in
    [t_on, t_on+window_s], negatives = PRE-ONSET epochs only (phases.pre) --
    NOT post-attack (D-064 tertiary metric handles the post-attack window
    separately as a recovery alarm rate, never pooled into negatives here)."""
    t = np.asarray(t, dtype=float)
    active = np.asarray(active, dtype=bool)
    raw_p = np.asarray(raw_p, dtype=float)
    phases = M.compute_phases(t, active)
    if phases.t_on is None:
        return dict(auc=float("nan"), n_pos=0, n_neg=int(phases.pre.sum()))
    onset_mask = active & (t < phases.t_on + window_s)
    mask = phases.pre | onset_mask
    labels = onset_mask[mask]
    return dict(auc=M.roc_auc(raw_p[mask], labels), n_pos=int(onset_mask.sum()),
                n_neg=int(phases.pre.sum()), window_s=window_s)


def full_window_auc(t: np.ndarray, active: np.ndarray, raw_p: np.ndarray) -> dict:
    """D-064 tertiary (descriptive) metric: the CURRENT node_runner.py
    definition (full attack window as positives, pre+post as negatives) --
    kept for continuity/comparison, reported with the item-2 explanation
    (docs/specs/raw/progress/H2-ABRUPT.md), not as a primary claim."""
    active = np.asarray(active, dtype=bool)
    return dict(auc=M.roc_auc(np.asarray(raw_p, dtype=float), active),
                n_pos=int(active.sum()), n_neg=int((~active).sum()))


def recovery_alarm_rate(t: np.ndarray, active: np.ndarray, raw_p: np.ndarray, tau: float) -> dict:
    """D-064 tertiary: the post-attack window reported SEPARATELY as a
    'recovery alarm rate' (fraction of post-attack epochs with raw_p > tau),
    never pooled into the AUC negative class."""
    t = np.asarray(t, dtype=float)
    active = np.asarray(active, dtype=bool)
    raw_p = np.asarray(raw_p, dtype=float)
    phases = M.compute_phases(t, active)
    post = phases.post
    if post.sum() == 0:
        return dict(recovery_alarm_rate=float("nan"), n_post=0, tau=tau)
    rate = float(np.mean(raw_p[post] > tau))
    return dict(recovery_alarm_rate=rate, n_post=int(post.sum()), tau=tau)


def paired_wilcoxon_summary(x: np.ndarray, y: np.ndarray):
    """Thin wrapper around fedqpnt.eval.stats.paired_test (already used by
    scripts/h2_abrupt_h2h4_driver.py) so this module has no other
    dependency surface."""
    from fedqpnt.eval.stats import paired_test
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 1:
        return dict(n=0, note="insufficient finite pairs")
    r = paired_test(x[mask], y[mask])
    return dict(n=r.n, diff_mean=r.diff_mean, wilcoxon_stat=r.wilcoxon_stat, wilcoxon_p=r.wilcoxon_p)
