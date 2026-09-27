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
    # Process noise [ASSUMPTION; not yet swept -- flagged for the sensitivity
    # study]. q_bias absorbs unmodelled short-term receiver-clock jitter beyond
    # the pure b += d*dt kinematic prediction; q_drift lets the drift estimate
    # track a slowly-varying oscillator drift rate.
    q_bias: float = 1.0          # [m^2/s] continuous-time PSD on bias
    q_drift: float = 1e-3        # [(m/s)^2/s] continuous-time PSD on drift
    # Baseline (w=1) measurement noise -- reuses the same [ASSUMPTION] sigmas
    # trust/features.py uses for x8/x9 (sigma_clk_bias_m=3.0, sigma_clk_drift_mps=0.2),
    # single source of truth for "how noisy is one epoch of clk_bias/clk_drift".
    r_bias: float = 3.0 ** 2
    r_drift: float = 0.2 ** 2
    w_min: float = 0.02           # section 2.7 floor, same trust-weight convention as GNSS/ESKF


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

        if (fix is not None and fix.valid and np.isfinite(fix.clk_bias) and np.isfinite(fix.clk_drift)):
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
