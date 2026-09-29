"""Trust-engine feature vector, ARCHITECTURE.md §3.1 (WP-4.2, TRUST agent).

All features are causal, computed only from Agent-side data: ``GnssFix``
(incl. ``raim_stat``, mean/std C/N0, ``agc_db``, ``pdop``, clock bias/drift),
the fusion filter's pre-correction ``Innovation`` list (contract C-1,
nominal-R / w=1 innovations only -- see module docstring below), and
``QuantumSample``/``NavSolution`` where used by other trust-law pieces
(not by this 13-feature vector itself).

x1/x2 use ``Innovation.nis`` directly (already ``nu^T S^-1 nu`` with the
nominal-R S the Innovation was built with), divided by dof (=3): the spec
formula ``nu_p^T (H_p P^- H_p^T + R_p)^-1 nu_p / 3`` IS that quantity,
provided the innovations handed to the trust engine are pre-correction /
nominal-R (contract C-1 says exactly this -- "nominal-R innovations", never
R_eff, else the feature would depend on its own trust output).

PROPOSED-DECISION (contract gap, not a code edit): §3.1 lists a
cross-satellite C/N0 structure feature (single-antenna spoof signature,
D-018) as part of the CAI's/detector's toolkit ("comes through x1, x2, x12").
``GnssFix`` only carries ``mean_cn0``/``std_cn0`` (post-fit aggregate), not
per-PRN C/N0, so the per-satellite correlation feature described in D-018 is
NOT derivable from Agent-side data and is NOT implemented here. Flagged for
Master: either add ``GnssFix.per_sat_cn0`` (contract v0.3) or accept that
this signature is only visible through std_cn0 (a weaker proxy already
included as x5).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np

from fedqpnt.core.types import GnssFix, Innovation, QuantumSample, NavSolution

FEATURE_NAMES = (
    "nis_pos", "nis_vel", "raim", "cn0_mean", "cn0_std", "cn0_rate", "agc",
    "clk_jump", "drift_jump", "resid_rms", "nsat_delta", "div_cusum", "outage",
    # v0.3 (D-022 / D-018): cross-satellite C/N0 structure, now that
    # GnssFix.cn0_per_sat/elev_per_sat exist. A single-antenna spoofer makes
    # per-PRN C/N0 strongly cross-correlated (x14 rises) and washes out the
    # normal C/N0-vs-elevation dependence (x15 -> ~0), Radoš et al. 2024.
    "cn0_xsat_corr", "cn0_elev_slope",
)
N_FEATURES = len(FEATURE_NAMES)
CORR_WINDOW_EPOCHS = 20     # [ASSUMPTION] sliding window for x14
CORR_MIN_OVERLAP = 5        # min co-present samples for a PRN pair to count
CORR_MIN_PRESENCE_FRAC = 0.6  # a PRN must appear in this fraction of the window to qualify

# [ASSUMPTION] defaults per §3.1 table.
MU_CN0_REF_DBHZ = 45.0
SIGMA_CLK_BIAS_M = 3.0
SIGMA_CLK_DRIFT_MPS = 0.2
K_CUSUM = 1.5
# D-067 (jam recovery): x8/x9 predict the receiver clock forward by dt from the last fix. With a TCXO-class
# oscillator (D-066 addendum: q_drift 3.55e-2 m^2/s^3) the prediction error after a long GNSS outage (jamming,
# tunnel) is ~100+ sigma from ordinary holdover drift, which is NOT spoofing evidence; it false-fired E_s
# clk_event and the detector on the first fix after every outage and locked GNSS out. x8/x9 are therefore
# treated as unavailable (0, like the outage handling) when the gap since the last fix exceeds this bound
# [ASSUMPTION: 3 s = 3 nominal 1 Hz epochs].
CLK_JUMP_MAX_DT_S = 3.0


def _innovation_nis_over_dof(innovations: list[Innovation], sensor: str) -> float:
    for inv in innovations:
        if inv.sensor == sensor:
            return float(inv.nis) / max(inv.dof, 1)
    return 0.0


@dataclass
class GnssFeatureExtractor:
    """Causal, stateful, per-GNSS-epoch feature vector (§3.1, x1..x13).

    Call ``step(fix, innovations)`` once per GNSS epoch (valid or invalid
    fix -- an invalid/outage epoch still advances ``x13`` bookkeeping for
    the *next* epoch). Returns a ``(13,)`` float64 array in ``FEATURE_NAMES``
    order, or ``None`` if there is no fix at all this tick (nothing to
    extract -- callers should not advance the detector on that tick).
    """

    mu_cn0_ref: float = MU_CN0_REF_DBHZ
    sigma_clk_bias: float = SIGMA_CLK_BIAS_M
    sigma_clk_drift: float = SIGMA_CLK_DRIFT_MPS
    k_cusum: float = K_CUSUM

    _last_t: float | None = field(default=None, repr=False)
    _last_mean_cn0: float | None = field(default=None, repr=False)
    _last_clk_bias: float | None = field(default=None, repr=False)
    _last_clk_drift: float | None = field(default=None, repr=False)
    _last_num_sats: int | None = field(default=None, repr=False)
    _cusum: float = field(default=0.0, repr=False)
    _prev_was_outage: bool = field(default=False, repr=False)
    _cn0_window: deque = field(default_factory=lambda: deque(maxlen=CORR_WINDOW_EPOCHS), repr=False)

    def reset(self) -> None:
        self._last_t = None
        self._last_mean_cn0 = None
        self._last_clk_bias = None
        self._last_clk_drift = None
        self._last_num_sats = None
        self._cusum = 0.0
        self._prev_was_outage = False
        self._cn0_window.clear()

    def _cross_sat_corr(self) -> float:
        """x14: mean pairwise Pearson correlation of per-PRN C/N0 over the
        last ``CORR_WINDOW_EPOCHS`` (D-018: a single-antenna spoofer makes
        this go strongly positive; Radoš et al. 2024 report -0.76 clean vs
        0.99 spoofed). 0.0 if too few co-tracked PRNs to evaluate."""
        if len(self._cn0_window) < CORR_MIN_OVERLAP:
            return 0.0
        counts: dict[int, int] = {}
        for snap in self._cn0_window:
            for prn in snap:
                counts[prn] = counts.get(prn, 0) + 1
        min_count = max(int(CORR_MIN_PRESENCE_FRAC * len(self._cn0_window)), CORR_MIN_OVERLAP)
        prns = [p for p, c in counts.items() if c >= min_count]
        if len(prns) < 2:
            return 0.0
        series = {p: np.array([snap[p] for snap in self._cn0_window if p in snap]) for p in prns}
        idx = {p: [i for i, snap in enumerate(self._cn0_window) if p in snap] for p in prns}
        corrs = []
        for i in range(len(prns)):
            for j in range(i + 1, len(prns)):
                pi, pj = prns[i], prns[j]
                common = sorted(set(idx[pi]) & set(idx[pj]))
                if len(common) < CORR_MIN_OVERLAP:
                    continue
                a = np.array([self._cn0_window[k][pi] for k in common])
                b = np.array([self._cn0_window[k][pj] for k in common])
                if np.std(a) < 1e-9 or np.std(b) < 1e-9:
                    continue
                corrs.append(float(np.corrcoef(a, b)[0, 1]))
        return float(np.mean(corrs)) if corrs else 0.0

    @staticmethod
    def _elev_slope(fix: GnssFix) -> float:
        """x15: current-epoch OLS slope of C/N0 vs elevation across tracked
        PRNs (D-018: single-antenna spoofing washes out the normal positive
        elevation dependence, driving this toward 0). 0.0 if <2 sats or no
        elevation spread."""
        if len(fix.cn0_per_sat) < 2:
            return 0.0
        prns = sorted(set(fix.cn0_per_sat) & set(fix.elev_per_sat))
        if len(prns) < 2:
            return 0.0
        elev = np.array([fix.elev_per_sat[p] for p in prns])
        cn0 = np.array([fix.cn0_per_sat[p] for p in prns])
        var_e = np.var(elev)
        if var_e < 1e-9:
            return 0.0
        return float(np.cov(cn0, elev, bias=True)[0, 1] / var_e)

    def step(self, fix: GnssFix, innovations: list[Innovation]) -> np.ndarray | None:
        if fix is None:
            return None
        dt = 1.0 if self._last_t is None else max(fix.t - self._last_t, 1e-6)

        outage_now = (not fix.valid) or (fix.num_sats < 4)
        x13 = 1.0 if self._prev_was_outage else 0.0

        # x4/x5/x6/x7/x11 are ALWAYS computable from GnssFix (mean/std C/N0,
        # agc_db, num_sats are populated even on an invalid/outage fix --
        # see GnssReceiver.solve) and are the STRONGEST jamming evidence
        # (near-zero C/N0, deeply negative AGC, sats dropping to 0). Only
        # x1/x2 (no innovation without a fit), x3/x10 (raim/resid_rms are
        # NaN without >= min_sats), and x8/x9 (clk_bias/drift are NaN on an
        # invalid fix) are genuinely unavailable during outage.
        # PROPOSED-DECISION (bug found & fixed per D-022 review): a prior
        # version zeroed ALL of x1..x11 on any outage, discarding exactly
        # the jamming signal that survives an invalid fix -- this silently
        # trained the detector to treat severe jamming as "nominal".
        if outage_now:
            x1 = x2 = 0.0
            x3 = 0.0
            x8 = x9 = 0.0
            x10 = 0.0
        else:
            x1 = _innovation_nis_over_dof(innovations, "gnss_pos")
            x2 = _innovation_nis_over_dof(innovations, "gnss_vel")
            x3 = (fix.raim_stat / max(fix.num_sats - 4, 1)) if np.isfinite(fix.raim_stat) else 0.0
            if (self._last_clk_bias is None or self._last_clk_drift is None or not np.isfinite(fix.clk_bias)
                    or dt > CLK_JUMP_MAX_DT_S):
                x8 = 0.0
            else:
                pred_b = self._last_clk_bias + self._last_clk_drift * dt
                x8 = abs(fix.clk_bias - pred_b) / self.sigma_clk_bias
            x9 = (0.0 if (self._last_clk_drift is None or not np.isfinite(fix.clk_drift) or dt > CLK_JUMP_MAX_DT_S)
                  else abs(fix.clk_drift - self._last_clk_drift) / self.sigma_clk_drift)
            x10 = fix.residual_rms if np.isfinite(fix.residual_rms) else 0.0

        x4 = fix.mean_cn0 - self.mu_cn0_ref
        x5 = fix.std_cn0
        x6 = 0.0 if self._last_mean_cn0 is None else (fix.mean_cn0 - self._last_mean_cn0) / dt
        x7 = fix.agc_db
        x11 = 0.0 if self._last_num_sats is None else float(fix.num_sats - self._last_num_sats)

        self._cusum = max(0.0, self._cusum + x1 - self.k_cusum)
        x12 = self._cusum

        if fix.cn0_per_sat:
            self._cn0_window.append(dict(fix.cn0_per_sat))
        x14 = self._cross_sat_corr()
        x15 = self._elev_slope(fix)

        vec = np.array([x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12, x13, x14, x15],
                        dtype=np.float64)

        self._last_t = fix.t
        self._last_mean_cn0 = fix.mean_cn0
        self._last_num_sats = fix.num_sats
        if not outage_now:
            self._last_clk_bias = fix.clk_bias
            self._last_clk_drift = fix.clk_drift
        self._prev_was_outage = outage_now
        return vec


@dataclass
class EwmaStack:
    """Turns a causal 13-dim raw-feature stream into the 52-dim detector
    input ``u_j = [x, EWMA_2s(x), EWMA_20s(x), x_j - x_{j-1}]`` (§3.1).

    Operates on WHATEVER vector it is fed (raw or normalised -- the caller
    decides; ``detector.py`` feeds it normalised x-tilde per the spec).
    """

    tau_fast_s: float = 2.0
    tau_slow_s: float = 20.0
    _ewma_fast: np.ndarray | None = field(default=None, repr=False)
    _ewma_slow: np.ndarray | None = field(default=None, repr=False)
    _prev: np.ndarray | None = field(default=None, repr=False)
    _last_t: float | None = field(default=None, repr=False)

    def reset(self) -> None:
        self._ewma_fast = None
        self._ewma_slow = None
        self._prev = None
        self._last_t = None

    def step(self, t: float, x: np.ndarray) -> np.ndarray:
        dt = 1.0 if self._last_t is None else max(t - self._last_t, 1e-6)
        if self._ewma_fast is None:
            self._ewma_fast = x.copy()
            self._ewma_slow = x.copy()
            self._prev = x.copy()
        beta_fast = 1.0 - np.exp(-dt / self.tau_fast_s)
        beta_slow = 1.0 - np.exp(-dt / self.tau_slow_s)
        self._ewma_fast = self._ewma_fast + beta_fast * (x - self._ewma_fast)
        self._ewma_slow = self._ewma_slow + beta_slow * (x - self._ewma_slow)
        diff = x - self._prev
        out = np.concatenate([x, self._ewma_fast, self._ewma_slow, diff])
        self._prev = x.copy()
        self._last_t = t
        return out
