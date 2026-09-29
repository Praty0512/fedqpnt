"""Standalone 2-state clock Kalman filter (WP-8.1, D-025 timing metrics,
DECISION_LOG D-027: "a standalone 2-state clock KF (fusion/clock.py),
trust-weighted like GNSS, rather than ESKF states 15-16. It keeps the timing
work independent of ESKF edits.").

State x = [b, d]: receiver clock bias b [m] and drift d [m/s] (same units as
``GnssFix.clk_bias`` / ``clk_drift``, i.e. range/range-rate equivalents,
c * true_bias / c * true_drift). Process model: b_{k+1} = b_k + d_k*dt,
d_{k+1} = d_k (random walk on drift). Trust-weighted like GNSS (section 2.7):
``R_eff = R / max(w, w_min)``, so a distrusted or absent GNSS fix makes the
filter coast purely on its drift model (the measurement update is simply
skipped -- an infinitely-inflated R). This module never imports
``fedqpnt.sim``/``fedqpnt.attacks``/``AttackLabel``/``TruthState`` (same
node-boundary rule as ``fedqpnt.fusion.eskf``; the AST leakage guard in
``tests/test_node_leakage_guard.py`` also covers ``fedqpnt/fusion/clock.py``
via ``fedqpnt/node/agent.py``'s import graph).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from fedqpnt.core.types import GnssFix


@dataclass
class ClockKFConfig:
    # Process noise: TCXO two-state model (D-066 addendum). Brown & Hwang, Introduction to Random
    # Signals and Applied Kalman Filtering, 4th ed., Wiley 2012, TCXO h-parameters h0 = 2e-19 s,
    # h_-2 = 2e-20 1/s (h_-1 = 7e-21 not modelled in the two-state model), as cited in Krawinkel &
    # Schon 2021, NAVIGATION, doi:10.1002/navi.444; spectral densities q_b = h0/2 and
    # q_d = 2 pi^2 h_-2 from Qin et al. 2021, Sensors 21:466, doi:10.3390/s21020466, scaled to range
    # units by c^2: q_bias = c^2 h0/2 = 8.99e-3 m^2/s, q_drift = c^2 2 pi^2 h_-2 = 3.55e-2 m^2/s^3.
    # The simulated TRUTH clock (fedqpnt/gnss/signal.py ClockState) uses the same values, so the
    # filter is model-consistent (was q_bias=1.0, q_drift=1e-3 [ASSUMPTION] vs a truth 4000x quieter
    # in drift than a TCXO). Q is oscillator physics and is NOT scaled by trust.
    q_bias: float = 0.5 * (299_792_458.0 ** 2) * 2e-19                  # [m^2/s]
    q_drift: float = (299_792_458.0 ** 2) * 2.0 * np.pi ** 2 * 2e-20    # [(m/s)^2/s]
    # Baseline (w=1) measurement noise -- reuses the same [ASSUMPTION] sigmas
    # trust/features.py uses for x8/x9 (sigma_clk_bias_m=3.0, sigma_clk_drift_mps=0.2),
    # single source of truth for "how noisy is one epoch of clk_bias/clk_drift".
    r_bias: float = 3.0 ** 2
    r_drift: float = 0.2 ** 2
    w_min: float = 0.02           # section 2.7 floor, same trust-weight convention as GNSS/ESKF
    # D-065/D-066: hard-exclusion holdover, ESKF Sec 2.7 convention (fusion/eskf.py w_excl): when
    # w_gnss < w_excl the measurement update is skipped and the filter free-runs on the oscillator
    # model (R-inflation alone let the unconditional process noise re-open the gain during a
    # sustained low-trust period: D-063 task B meaconing trace).
    w_excl: float = 0.05


@dataclass
class ClockSolution:
    t: float
    bias_m: float
    drift_mps: float
    cov: np.ndarray   # (2,2)


class ClockKF:
    """2-state (bias, drift) KF, GNSS-clock-fix-aided, trust-weighted."""

    def __init__(self, cfg: ClockKFConfig | None = None):
        self.cfg = cfg or ClockKFConfig()
        self.t: float | None = None
        self.x = np.zeros(2)
        self.P = np.diag([9.0, 0.04])
        self.initialized = False

    def config(self) -> dict[str, Any]:
        return dict(type="ClockKF", q_bias=self.cfg.q_bias, q_drift=self.cfg.q_drift,
                    r_bias=self.cfg.r_bias, r_drift=self.cfg.r_drift, w_min=self.cfg.w_min)

    def initialize(self, t0: float, bias0: float = 0.0, drift0: float = 0.0) -> None:
        self.t = t0
        self.x = np.array([bias0, drift0], dtype=float)
        self.P = np.diag([9.0, 0.04])
        self.initialized = True

    def _propagate(self, t: float) -> None:
        dt = t - self.t
        if dt <= 0:
            self.t = t
            return
        F = np.array([[1.0, dt], [0.0, 1.0]])
        Q = np.array([[self.cfg.q_bias * dt, 0.0], [0.0, self.cfg.q_drift * dt]])
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + Q
        self.t = t

    def step(self, t: float, fix: GnssFix | None, w_gnss: float) -> ClockSolution | None:
        """One tick. ``fix`` is the (already trust-scored) GNSS fix for this
        tick or None; ``w_gnss`` is the GNSS trust weight from the SAME trust
        engine used by the ESKF (section 2.7 convention). Coasts on the
        drift-only process model whenever there is no valid fix, or when the
        fix is excluded (``w_gnss < w_excl``-style near-zero trust makes
        R_eff huge, which is numerically equivalent to "no update" -- we
        still floor at ``w_min`` per the shared trust convention rather than
        adding a second exclusion threshold)."""
        if not self.initialized:
            return None
        self._propagate(t)

        if (w_gnss >= self.cfg.w_excl and fix is not None and fix.valid
                and np.isfinite(fix.clk_bias) and np.isfinite(fix.clk_drift)):
            z = np.array([fix.clk_bias, fix.clk_drift])
            H = np.eye(2)
            R = np.diag([self.cfg.r_bias, self.cfg.r_drift]) / max(w_gnss, self.cfg.w_min)
            S = H @ self.P @ H.T + R
            K = self.P @ H.T @ np.linalg.inv(S)
            nu = z - H @ self.x
            self.x = self.x + K @ nu
            IKH = np.eye(2) - K @ H
            self.P = IKH @ self.P @ IKH.T + K @ R @ K.T
            self.P = 0.5 * (self.P + self.P.T)

        return ClockSolution(t=t, bias_m=float(self.x[0]), drift_mps=float(self.x[1]), cov=self.P.copy())
