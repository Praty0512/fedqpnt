"""World model shared by truth, sensor models and the filter (contract v0.2, C-5).

``"flat"``: uniform gravity on a non-rotating tangent plane (default, S1–S13, S15).
``"schuler_tangent"``: first-order position-dependent gravity that restores
Schuler (84.4 min) horizontal dynamics and the vertical-channel instability;
used for long-duration scenarios S6 and S14 (ARCHITECTURE.md §2.6).
Earth rate and Coriolis are deliberately omitted (compensable; DECISION_LOG D-009).
"""
from __future__ import annotations

import numpy as np

from .types import G0

R_EARTH = 6.371e6  # m, mean radius
WORLDS = ("flat", "schuler_tangent")


def gravity_n(pos: np.ndarray, world: str = "flat") -> np.ndarray:
    """Gravity vector g_n(p) in ENU [m/s^2]. ``pos`` is (3,) or (N,3)."""
    pos = np.asarray(pos, dtype=float)
    if world == "flat":
        return np.broadcast_to(np.array([0.0, 0.0, -G0]), pos.shape).copy()
    if world == "schuler_tangent":
        g = np.empty_like(pos)
        g[..., 0] = -G0 * pos[..., 0] / R_EARTH
        g[..., 1] = -G0 * pos[..., 1] / R_EARTH
        g[..., 2] = -G0 * (1.0 - 2.0 * pos[..., 2] / R_EARTH)
        return g
    raise ValueError(f"unknown world {world!r}; expected one of {WORLDS}")


def gravity_gradient(world: str = "flat") -> np.ndarray:
    """∂g_n/∂p (3,3), the F-matrix block ∂δv̇/∂δp for the error-state EKF."""
    if world == "flat":
        return np.zeros((3, 3))
    if world == "schuler_tangent":
        k = G0 / R_EARTH
        return np.diag([-k, -k, 2.0 * k])
    raise ValueError(f"unknown world {world!r}; expected one of {WORLDS}")
