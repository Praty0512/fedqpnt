"""Evaluation metrics, ARCHITECTURE.md section 6 (+ D-025 timing metrics).
WP-8.1, TESTING/INTEGRATION agent. EVALUATOR-ONLY: reads truth/labels
alongside nav/trust series; never imported by ``fedqpnt.node`` (Agent side).

All functions take plain numpy arrays (already extracted from a recorded
run, e.g. via ``fedqpnt.sim.recorder.load_run``) rather than ``RunData``
objects directly, so they are trivially unit-testable on synthetic inputs
with known answers.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

T_ALIGN_S = 60.0     # section 6: alignment transient excluded from P_pre
T_SUS_S = 1.0        # detection "sustained" window
T_HOLD_S = 10.0      # recovery "held below threshold" window
N_CYC_BOUND_PER_HOUR = 3600.0 / 26.1   # section 3.3 formal bound, ~138/h


# --------------------------------------------------------------------------
# Phases (section 6): P_pre = [t_align, t_on), P_att = [t_on, t_off), P_post = [t_off, T]
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Phases:
    t_on: float | None
    t_off: float | None
    pre: np.ndarray     # bool mask into the caller's t array
    att: np.ndarray
    post: np.ndarray


def compute_phases(t: np.ndarray, attack_active: np.ndarray, t_align: float = T_ALIGN_S) -> Phases:
    """``attack_active``: bool array, True where ``AttackLabel.spoofing or
    .jamming`` at that sample. ``t_on`` = first True; ``t_off`` = one epoch
    (one sample of ``t``) after the last True. All-False input -> the whole
    (post-alignment) run is P_pre, and P_att/P_post are empty."""
    t = np.asarray(t, dtype=float)
    active = np.asarray(attack_active, dtype=bool)
    idx_active = np.flatnonzero(active)
    if idx_active.size == 0:
        pre = t >= t_align
        empty = np.zeros_like(t, dtype=bool)
        return Phases(t_on=None, t_off=None, pre=pre, att=empty, post=empty)

    t_on = float(t[idx_active[0]])
    last_idx = int(idx_active[-1])
    t_off = float(t[min(last_idx + 1, len(t) - 1)]) if last_idx + 1 < len(t) else float(t[last_idx]) + 1e-9

    pre = (t >= t_align) & (t < t_on)
    att = (t >= t_on) & (t < t_off)
    post = t >= t_off
    return Phases(t_on=t_on, t_off=t_off, pre=pre, att=att, post=post)


# --------------------------------------------------------------------------
# Position/velocity error metrics
# --------------------------------------------------------------------------
def horizontal_error(pos_est: np.ndarray, pos_true: np.ndarray) -> np.ndarray:
    return np.linalg.norm(pos_est[:, 0:2] - pos_true[:, 0:2], axis=1)


def full3d_error(pos_est: np.ndarray, pos_true: np.ndarray) -> np.ndarray:
    return np.linalg.norm(pos_est - pos_true, axis=1)


def velocity_error(vel_est: np.ndarray, vel_true: np.ndarray) -> np.ndarray:
    return np.linalg.norm(vel_est - vel_true, axis=1)


def _select(e: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    """Applies the phase mask (if any), then drops non-finite samples.
    Non-finite entries arise legitimately, e.g. a clock-error series sampled
    at the (agent) tick rate but only defined at GNSS-epoch ticks (D-025) --
    they must never poison a RMSE/MAX/P95 reduction via NaN propagation."""
    e = e if mask is None else e[mask]
    return e[np.isfinite(e)]


def rmse(e: np.ndarray, mask: np.ndarray | None = None) -> float:
    e = _select(e, mask)
    if e.size == 0:
        return float("nan")
    return float(np.sqrt(np.mean(e ** 2)))


def max_err(e: np.ndarray, mask: np.ndarray | None = None) -> float:
    e = _select(e, mask)
    if e.size == 0:
        return float("nan")
    return float(np.max(e))


def p95_err(e: np.ndarray, mask: np.ndarray | None = None) -> float:
    e = _select(e, mask)
    if e.size == 0:
        return float("nan")
    return float(np.percentile(e, 95))


def anees_pos(pos_est: np.ndarray, pos_true: np.ndarray, cov_pos: np.ndarray,
              mask: np.ndarray | None = None) -> float:
    """section 6: ANEES(P) = mean_{t in P} delta_p^T P_pos^-1 delta_p / 3.
    D-068: ``cov_pos`` is the FULL (N,3,3) position covariance block; the
    quadratic form uses the full inverse (off-diagonals included). A legacy
    (N,3) diagonal-only input is still accepted for old result files but is
    an approximation (see ``anees_pos_diag``); new runs must log (N,3,3)."""
    cov = np.asarray(cov_pos, dtype=float)
    if cov.ndim == 2:
        return anees_pos_diag(pos_est, pos_true, cov, mask)
    err = np.asarray(pos_est, dtype=float) - np.asarray(pos_true, dtype=float)
    if mask is not None:
        err, cov = err[mask], cov[mask]
    if err.shape[0] == 0:
        return float("nan")
    cov = 0.5 * (cov + np.swapaxes(cov, 1, 2))
    cov = cov + 1e-9 * np.eye(3)[None]
    sol = np.linalg.solve(cov, err[:, :, None])[:, :, 0]
    nees = np.sum(err * sol, axis=1) / 3.0
    return float(np.mean(nees))


def anees_pos_diag(pos_est: np.ndarray, pos_true: np.ndarray, cov_pos_diag: np.ndarray,
                   mask: np.ndarray | None = None) -> float:
    """Legacy diagonal-only ANEES (pre-D-068). Kept only to read old files."""
    err = pos_est - pos_true
    nees = np.sum(err ** 2 / np.clip(cov_pos_diag, 1e-9, None), axis=1) / 3.0
    nees = nees if mask is None else nees[mask]
    if nees.size == 0:
        return float("nan")
    return float(np.mean(nees))


# --------------------------------------------------------------------------
# Detection / latency (section 6)
# --------------------------------------------------------------------------
def _sustained_true(t: np.ndarray, flag: np.ndarray, start_idx: int, t_sus: float) -> int | None:
    """First index k >= start_idx such that flag[k'] is True for every
    sample with t in [t[k], t[k]+t_sus]. Returns None if never sustained."""
    n = len(t)
    for k in range(start_idx, n):
        if not flag[k]:
            continue
        end_t = t[k] + t_sus
        j = k
        ok = True
        while j < n and t[j] <= end_t:
            if not flag[j]:
                ok = False
                break
            j += 1
        if ok:
            return k
    return None


def detection_latency(t: np.ndarray, attack_detected: np.ndarray, phases: Phases,
                       t_sus: float = T_SUS_S) -> float:
    """``latency_on = t_det - t_on``; miss (censored) -> ``t_off - t_on``
    (section 6). NaN if there is no attack phase at all."""
    if phases.t_on is None or phases.t_off is None:
        return float("nan")
    start_idx = int(np.searchsorted(t, phases.t_on, side="left"))
    off_idx = int(np.searchsorted(t, phases.t_off, side="left"))
    k_det = _sustained_true(t, np.asarray(attack_detected, dtype=bool), start_idx, t_sus)
    if k_det is None or k_det >= off_idx:
        return float(phases.t_off - phases.t_on)   # miss, censored at t_off
    return float(t[k_det] - phases.t_on)


def detection_probability(latencies: list[float], phases_list: list[Phases]) -> float:
    hits = sum(1 for lat, ph in zip(latencies, phases_list)
               if ph.t_on is not None and ph.t_off is not None and lat < (ph.t_off - ph.t_on))
    n = sum(1 for ph in phases_list if ph.t_on is not None)
    return float(hits / n) if n > 0 else float("nan")


EVENT_CENSOR_S = 60.0   # D-064/D-068: event-level metrics (P_D@10 s, onset latency) censored at 60 s


def detection_outcome(t: np.ndarray, attack_detected: np.ndarray, phases: Phases,
                      t_sus: float = T_SUS_S) -> dict:
    """Explicit detection outcome (D-068: S2 P_D bug -- a censored latency is
    finite, so ``isfinite(latency)`` is always True). Returns
    ``detected`` (bool), ``t_det`` (absolute time of the first sustained
    detection inside the attack window, NaN if none), ``window_s`` (t_off - t_on,
    NaN if no attack) and ``latency_on`` (t_det - t_on, or ``window_s`` if missed)."""
    if phases.t_on is None or phases.t_off is None:
        return dict(detected=False, t_det=float("nan"), window_s=float("nan"), latency_on=float("nan"))
    start_idx = int(np.searchsorted(t, phases.t_on, side="left"))
    off_idx = int(np.searchsorted(t, phases.t_off, side="left"))
    k = _sustained_true(t, np.asarray(attack_detected, dtype=bool), start_idx, t_sus)
    window = float(phases.t_off - phases.t_on)
    if k is None or k >= off_idx:
        return dict(detected=False, t_det=float("nan"), window_s=window, latency_on=window)
    return dict(detected=True, t_det=float(t[k]), window_s=window, latency_on=float(t[k] - phases.t_on))


def censor_event(latency_s: float, detected: bool, censor_s: float = EVENT_CENSOR_S) -> float:
    """Event-level latency (D-064): misses -> ``censor_s`` (60 s); hits are
    capped at ``censor_s``. Never data-dependent."""
    if not detected or not np.isfinite(latency_s):
        return float(censor_s)
    return float(min(latency_s, censor_s))


def censor_window(latency_s: float, detected: bool, window_s: float) -> float:
    """Non-event latency: misses -> ``window_s`` = t_off - t_on."""
    if not detected or not np.isfinite(latency_s):
        return float(window_s)
    return float(latency_s)


def detected_from_record(rec: dict, attack_duration_s: float | None = None, tol_s: float = 0.05) -> bool:
    """Reads the explicit ``detected_on`` flag from a run record. Old records
    (before the runner emits it) fall back to ``latency_on < window - tol``
    where window is ``window_s`` if recorded, else the scenario's
    ``attack.duration_s``; with neither available raises (never guesses)."""
    if rec.get("detected_on") is not None:
        return bool(rec["detected_on"])
    lat = rec.get("latency_on", float("nan"))
    if not np.isfinite(lat):
        return False
    window = rec.get("window_s", attack_duration_s)
    if window is None:
        raise ValueError("record has no detected_on flag and no attack window to infer it from")
    return bool(lat < float(window) - tol_s)


def load_sigma_nom(path: str = "results/sigma_nom.json") -> dict:
    """D-068: sigma_nom is read from a FROZEN file (per IMU grade, metres),
    never computed on the fly. Expected: ``{"industrial_mems": x, "tactical": y}``
    (optionally nested under ``"sigma_nom_m"``). Fails loudly if absent."""
    import json
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"{p} not found: sigma_nom must be frozen (D-068) before latency_eff is computed")
    d = json.loads(p.read_text())
    d = d.get("sigma_nom_m", d)
    out = {k: float(v) for k, v in d.items() if isinstance(v, (int, float))}
    if not out or not all(np.isfinite(v) and v > 0 for v in out.values()):
        raise ValueError(f"{p}: no valid positive sigma_nom values")
    return out


def latency_eff(t: np.ndarray, injected_offset_m: np.ndarray, t_det: float, phases: Phases,
                sigma_nom_m: float, k_sigma: float = 3.0) -> dict:
    """D-068 latency_eff. ``t_eff`` = first epoch in the attack window where
    the truth-side injected offset exceeds ``k_sigma * sigma_nom``. If the
    attack never becomes effective the run is EXCLUDED (``excluded=True``,
    latency NaN). Otherwise ``latency_eff = t_det - t_eff`` (may be negative:
    detected before it became effective); a miss (``t_det`` NaN or >= t_off)
    is censored at ``t_off - t_eff``."""
    if phases.t_on is None or phases.t_off is None:
        return dict(excluded=True, t_eff=float("nan"), latency_eff=float("nan"), detected=False)
    t = np.asarray(t, dtype=float)
    off = np.asarray(injected_offset_m, dtype=float)
    in_att = (t >= phases.t_on) & (t < phases.t_off) & np.isfinite(off)
    idx = np.flatnonzero(in_att & (off > k_sigma * sigma_nom_m))
    if idx.size == 0:
        return dict(excluded=True, t_eff=float("nan"), latency_eff=float("nan"), detected=False)
    t_eff = float(t[idx[0]])
    if not np.isfinite(t_det) or t_det >= phases.t_off:
        return dict(excluded=False, t_eff=t_eff, latency_eff=float(phases.t_off - t_eff), detected=False)
    return dict(excluded=False, t_eff=t_eff, latency_eff=float(t_det - t_eff), detected=True)


def sigma_h_from_cov(cov_pos: np.ndarray) -> np.ndarray:
    """sigma_h(P_pos) per epoch: sqrt of the largest eigenvalue of the 2x2 horizontal (E,N) covariance
    block, i.e. the 1-sigma radius along the worst horizontal direction (conservative; D-068 S3 definition).
    ``cov_pos``: (N,3,3)."""
    c = np.asarray(cov_pos, dtype=float)[:, :2, :2]
    c = 0.5 * (c + np.swapaxes(c, 1, 2))
    return np.sqrt(np.clip(np.linalg.eigvalsh(c)[:, -1], 0.0, None))


def consistency_fraction(e_h: np.ndarray, cov_pos: np.ndarray, mask: np.ndarray | None = None,
                         k_sigma: float = 3.0) -> float:
    """S3 (ARCH 6.1): fraction of samples with ``e_h <= k_sigma * sigma_h(P_pos)`` in the phase ``mask``."""
    e = np.asarray(e_h, dtype=float)
    sig = sigma_h_from_cov(cov_pos)
    if mask is not None:
        e, sig = e[mask], sig[mask]
    ok = np.isfinite(e) & np.isfinite(sig)
    if not np.any(ok):
        return float("nan")
    return float(np.mean(e[ok] <= k_sigma * sig[ok]))


def window_rmse(t: np.ndarray, e_h: np.ndarray, t_lo: float, t_hi: float) -> float:
    """RMSE_h over [t_lo, t_hi) (S14 first/last hour)."""
    t = np.asarray(t, dtype=float)
    return rmse(np.asarray(e_h, dtype=float), (t >= t_lo) & (t < t_hi))


def latency_eff_from_record(rec: dict, sigma_nom_m: float, k_sigma: float = 3.0) -> dict:
    """``latency_eff`` for one run record. Required record fields (emitted by
    the runner, see SCENARIO-FIX checkpoint P2): ``offset_t_s`` and
    ``offset_m`` (truth-side ``meta["injected_offset_m"]`` per GNSS epoch),
    ``t_on_s``, ``t_off_s`` and ``t_det`` (NaN/None if never detected).
    Raises KeyError if the offset channel is missing (never guessed)."""
    for k in ("offset_t_s", "offset_m", "t_on_s", "t_off_s"):
        if rec.get(k) is None:
            raise KeyError(f"record lacks '{k}': no truth-side injected-offset channel, latency_eff not computable")
    ph = Phases(t_on=float(rec["t_on_s"]), t_off=float(rec["t_off_s"]),
                pre=np.zeros(0, bool), att=np.zeros(0, bool), post=np.zeros(0, bool))
    t_det = rec.get("t_det")
    t_det = float("nan") if t_det is None else float(t_det)
    return latency_eff(np.asarray(rec["offset_t_s"], float), np.asarray(rec["offset_m"], float), t_det, ph,
                       sigma_nom_m, k_sigma)


def false_alarm_rate(t: np.ndarray, attack_detected: np.ndarray, attack_active: np.ndarray,
                      t_sus: float = T_SUS_S) -> dict[str, float]:
    """FA events = rising edges of ``attack_detected`` with no label active
    within +-t_sus; FAR = events / clean hours. Also per-epoch FPR."""
    t = np.asarray(t, dtype=float)
    det = np.asarray(attack_detected, dtype=bool)
    active = np.asarray(attack_active, dtype=bool)
    rising = np.flatnonzero(det[1:] & ~det[:-1]) + 1
    if det.size and det[0]:
        rising = np.concatenate([[0], rising])

    fa_events = 0
    for k in rising:
        lo = np.searchsorted(t, t[k] - t_sus, side="left")
        hi = np.searchsorted(t, t[k] + t_sus, side="right")
        if not np.any(active[lo:hi]):
            fa_events += 1

    clean_mask = ~active
    clean_hours = (np.sum(clean_mask) * _dt(t)) / 3600.0 if clean_mask.size else 0.0
    far = float(fa_events / clean_hours) if clean_hours > 0 else float("nan")

    clean_det = det[clean_mask]
    fpr = float(np.mean(clean_det)) if clean_det.size else float("nan")
    return dict(fa_events=float(fa_events), far_per_hour=far, fpr=fpr)


def _dt(t: np.ndarray) -> float:
    if len(t) < 2:
        return 0.0
    return float(np.median(np.diff(t)))


def time_to_distrust(t: np.ndarray, w_gnss: np.ndarray, phases: Phases) -> float:
    if phases.t_on is None:
        return float("nan")
    idx = np.flatnonzero((t >= phases.t_on) & (w_gnss < 0.5))
    if idx.size == 0:
        return float("nan")
    return float(t[idx[0]] - phases.t_on)


def recovery_time(t: np.ndarray, e_h: np.ndarray, phases: Phases, rmse_pre: float,
                   e_thr_floor: float = 3.0, t_hold: float = T_HOLD_S) -> float:
    """t_rec = inf{tau >= 0 : e_h(t) < E_thr for all t in [t_off+tau, t_off+tau+T_hold]},
    E_thr = max(2*RMSE_h(P_pre), 3 m). NaN ("no recovery") if none before T."""
    if phases.t_off is None:
        return float("nan")
    e_thr = max(2.0 * rmse_pre, e_thr_floor) if np.isfinite(rmse_pre) else e_thr_floor
    post_idx = np.flatnonzero(t >= phases.t_off)
    if post_idx.size == 0:
        return float("nan")
    dt = _dt(t)
    hold_n = max(int(round(t_hold / dt)), 1) if dt > 0 else 1
    ok = e_h < e_thr
    for start in post_idx:
        end = start + hold_n
        if end > len(t):
            break
        if np.all(ok[start:end]):
            return float(t[start] - phases.t_off)
    return float("nan")


# --------------------------------------------------------------------------
# Trust chattering (section 3.3 / section 6)
# --------------------------------------------------------------------------
def trust_cycles(t: np.ndarray, w: np.ndarray) -> int:
    """A trust cycle = a downward crossing of w=0.5 followed by an upward
    crossing of w=0.9."""
    w = np.asarray(w, dtype=float)
    n_cyc = 0
    state = "above"   # "above" (>=0.5) | "waiting_low" (crossed below 0.5, waiting for 0.9)
    for k in range(1, len(w)):
        if state == "above" and w[k - 1] >= 0.5 > w[k]:
            state = "waiting_low"
        elif state == "waiting_low" and w[k - 1] < 0.9 <= w[k]:
            n_cyc += 1
            state = "above"
    return n_cyc


def trust_cycles_per_hour(t: np.ndarray, w: np.ndarray) -> float:
    dur_h = (t[-1] - t[0]) / 3600.0 if len(t) > 1 else 0.0
    return float(trust_cycles(t, w) / dur_h) if dur_h > 0 else float("nan")


def total_variation_per_hour(t: np.ndarray, w: np.ndarray) -> float:
    w = np.asarray(w, dtype=float)
    tv = float(np.sum(np.abs(np.diff(w))))
    dur_h = (t[-1] - t[0]) / 3600.0 if len(t) > 1 else 0.0
    return float(tv / dur_h) if dur_h > 0 else float("nan")


# --------------------------------------------------------------------------
# Timing metrics (D-025): clock-bias error in ns. GnssFix.clk_bias is in
# metres (range-equivalent, includes c*bias); convert with C_LIGHT.
# --------------------------------------------------------------------------
C_LIGHT = 299_792_458.0


def clock_bias_error_ns(clk_bias_est_m: np.ndarray, clk_bias_true_m: np.ndarray) -> np.ndarray:
    return np.abs(np.asarray(clk_bias_est_m) - np.asarray(clk_bias_true_m)) / C_LIGHT * 1e9


def clock_drift_error_ns_per_s(clk_drift_est_mps: np.ndarray, clk_drift_true_mps: np.ndarray) -> np.ndarray:
    return np.abs(np.asarray(clk_drift_est_mps) - np.asarray(clk_drift_true_mps)) / C_LIGHT * 1e9


def rmse_t_ns(e_t_ns: np.ndarray, mask: np.ndarray | None = None) -> float:
    return rmse(e_t_ns, mask)


def max_t_ns(e_t_ns: np.ndarray, mask: np.ndarray | None = None) -> float:
    return max_err(e_t_ns, mask)


# --------------------------------------------------------------------------
# Detector quality (evaluator only)
# --------------------------------------------------------------------------
def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Mann-Whitney-U based ROC-AUC; no sklearn dependency. NaN if only one
    class is present."""
    scores = np.asarray(scores, dtype=float)
    labels = np.asarray(labels, dtype=bool)
    n_pos, n_neg = int(np.sum(labels)), int(np.sum(~labels))
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty_like(order, dtype=float)
    sorted_scores = scores[order]
    # average ranks for ties
    i = 0
    r = 1
    while i < len(sorted_scores):
        j = i
        while j + 1 < len(sorted_scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        avg_rank = (r + (r + (j - i))) / 2.0
        ranks[order[i:j + 1]] = avg_rank
        r += (j - i + 1)
        i = j + 1
    sum_ranks_pos = float(np.sum(ranks[labels]))
    auc = (sum_ranks_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return float(auc)
