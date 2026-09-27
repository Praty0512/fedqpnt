"""Strapdown inertial mechanisation (WP-1.2, ARCHITECTURE.md section 11.3 / 2.3).

Two integration schemes over point samples of specific force ``f_b(t)`` and
body rate ``omega_b(t)`` (contract v0.2: IMU/truth samples are point samples,
not Delta-v / Delta-theta increments):

* ``"causal"``: :func:`strapdown_step`, the exact 2nd-order (trapezoid +
  coning) scheme of ARCHITECTURE.md section 2.3 -- this is also what the
  online ES-EKF propagation uses. Looping it forward from sample k-1 to k is
  what a real-time filter can do (it only has samples up to k).
* ``"rk4"``: classic 4th-order Runge-Kutta on the (quaternion, v, p) state
  over each tick interval, using the 4-point cubic-interpolated midpoint
  input samples specified in the brief. This is the OFFLINE truth-validation
  scheme (closes the loop to sub-metre accuracy over 600-3600 s); it is not
  causal (needs samples ahead of the current tick) and is not what the
  real-time filter runs.

Gravity: ``gravity_n`` here is a thin, position/world-aware wrapper around
``fedqpnt.core.world.gravity_n`` (contract v0.2, C-5) -- the single place
this module reads gravity from, so switching ``world in {"flat",
"schuler_tangent"}`` is a one-argument change.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fedqpnt.core import world as _world
from fedqpnt.core.types import G0 as _G0

from .rotations import dcm_from_quat, dcm_to_euler, quat_from_dcm, quat_mul, quat_normalize, so3_exp

_FLAT_G = np.array([0.0, 0.0, -_G0])  # precomputed fast path for the (default) flat world


def _gravity_fast(pos: np.ndarray, world: str) -> np.ndarray:
    """Same values as ``gravity_n``/``core.world.gravity_n``, avoids the
    array-broadcasting overhead of the generic (batch-capable) core function
    per call on the RK4/causal hot path (matters at multi-hour scale)."""
    if world == "flat":
        return _FLAT_G
    if world == "schuler_tangent":
        return np.array([
            -_G0 * pos[0] / _world.R_EARTH,
            -_G0 * pos[1] / _world.R_EARTH,
            -_G0 * (1.0 - 2.0 * pos[2] / _world.R_EARTH),
        ])
    return _world.gravity_n(pos, world)  # unknown world -> core's own ValueError


# ---------------------------------------------------------------------------
# Lean single-sample helpers for the RK4 hot loop (avoid the batch-capable
# public rotations.py functions' reshape/broadcast overhead over N-1 calls).
# Numerically identical to the public functions on a single (4,)/(3,3) input.
# ---------------------------------------------------------------------------
def _quat_mul1(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.array([
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    ])


def _quat_normalize1(q: np.ndarray) -> np.ndarray:
    n = np.sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3])
    return q / n if n > 1e-300 else q


def _dcm_from_quat1(q: np.ndarray) -> np.ndarray:
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def _dcm_to_euler1(C: np.ndarray) -> np.ndarray:
    phi = np.arctan2(C[2, 1], C[2, 2])
    theta = -np.arcsin(np.clip(C[2, 0], -1.0, 1.0))
    psi = np.arctan2(C[1, 0], C[0, 0])
    return np.array([phi, theta, psi])


def _so3_exp1(phi: np.ndarray) -> np.ndarray:
    theta = np.sqrt(phi[0] * phi[0] + phi[1] * phi[1] + phi[2] * phi[2])
    x, y, z = phi
    K = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])
    if theta < 1e-8:
        a = 1.0 - theta ** 2 / 6.0
        b = 0.5 - theta ** 2 / 24.0
    else:
        a = np.sin(theta) / theta
        b = (1.0 - np.cos(theta)) / theta ** 2
    return np.eye(3) + a * K + b * (K @ K)


@dataclass
class NavState:
    pos: np.ndarray   # (3,) ENU [m]
    vel: np.ndarray   # (3,) ENU [m/s]
    C: np.ndarray     # (3,3) body->nav DCM


def gravity_n(pos: np.ndarray | None = None, world: str = "flat") -> np.ndarray:
    """Gravity vector g_n(p) in ENU [m/s^2]; delegates to core.world (C-5).

    ``pos`` defaults to the origin, so ``gravity_n()`` (no args) returns the
    familiar ``(0, 0, -G0)`` for the flat world.
    """
    p = np.zeros(3) if pos is None else np.asarray(pos, dtype=float)
    return _world.gravity_n(p, world)


def strapdown_step(state: NavState, f0: np.ndarray, w0: np.ndarray, f1: np.ndarray, w1: np.ndarray,
                    dt: float, world: str = "flat") -> NavState:
    """Causal 2nd-order strapdown update, exactly ARCHITECTURE.md section 2.3::

        C_{k+1} = C_k . Exp( 1/2(w0+w1) dt + 1/12 (w0 x w1) dt^2 )
        v_{k+1} = v_k + ( 1/2(C_k f0 + C_{k+1} f1) + g_n ) dt
        p_{k+1} = p_k + 1/2 (v_k + v_{k+1}) dt

    Gravity is evaluated at the pre-update position ``state.pos``.
    """
    f0 = np.asarray(f0, dtype=float); w0 = np.asarray(w0, dtype=float)
    f1 = np.asarray(f1, dtype=float); w1 = np.asarray(w1, dtype=float)
    C0 = state.C

    coning = 0.5 * (w0 + w1) * dt + (1.0 / 12.0) * np.cross(w0, w1) * dt ** 2
    C1 = C0 @ _so3_exp1(coning)

    g = _gravity_fast(state.pos, world)
    v1 = state.vel + (0.5 * (C0 @ f0 + C1 @ f1) + g) * dt
    p1 = state.pos + 0.5 * (state.vel + v1) * dt

    return NavState(pos=p1, vel=v1, C=C1)


def _midpoint_interp(u: np.ndarray, k: int, N: int) -> np.ndarray:
    """4-point cubic interpolation of ``u`` at index ``k + 1/2`` (brief section 11.3).

    Interior: ``(-u[k-1] + 9u[k] + 9u[k+1] - u[k+2]) / 16``.
    First interval (k=0): one-sided cubic ``(5u0 + 15u1 - 5u2 + u3) / 16``.
    Last interval (k=N-2): the mirror of the one-sided cubic.
    Falls back to the simple average if fewer than 4 samples are available.
    """
    if N < 4:
        return 0.5 * (u[k] + u[k + 1])
    if k == 0:
        return (5.0 * u[0] + 15.0 * u[1] - 5.0 * u[2] + u[3]) / 16.0
    if k == N - 2:
        return (5.0 * u[N - 1] + 15.0 * u[N - 2] - 5.0 * u[N - 3] + u[N - 4]) / 16.0
    return (-u[k - 1] + 9.0 * u[k] + 9.0 * u[k + 1] - u[k + 2]) / 16.0


def _dynamics(q: np.ndarray, v: np.ndarray, p: np.ndarray, f: np.ndarray, w: np.ndarray,
              world: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    C = _dcm_from_quat1(q)
    qdot = 0.5 * _quat_mul1(q, np.array([0.0, w[0], w[1], w[2]]))
    vdot = C @ f + _gravity_fast(p, world)
    pdot = v
    return qdot, vdot, pdot


def integrate(t: np.ndarray, f_b: np.ndarray, omega_b: np.ndarray, init: NavState,
              method: str = "rk4", world: str = "flat") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Integrate a whole (t, f_b, omega_b) mission from ``init``.

    Returns ``(pos (N,3), vel (N,3), att (N,3))``. ``method="rk4"`` is the
    offline validation scheme (section 2.3/11.3); ``method="causal"`` loops
    :func:`strapdown_step` (what the online filter would do).
    """
    t = np.asarray(t, dtype=float)
    f_b = np.asarray(f_b, dtype=float)
    omega_b = np.asarray(omega_b, dtype=float)
    N = t.shape[0]
    if f_b.shape[0] != N or omega_b.shape[0] != N:
        raise ValueError("t, f_b, omega_b must have the same leading length")

    pos = np.empty((N, 3)); vel = np.empty((N, 3)); att = np.empty((N, 3))
    pos[0] = init.pos; vel[0] = init.vel; att[0] = dcm_to_euler(init.C)
    if N < 2:
        return pos, vel, att

    if method == "causal":
        state = init
        for k in range(N - 1):
            dt = float(t[k + 1] - t[k])
            state = strapdown_step(state, f_b[k], omega_b[k], f_b[k + 1], omega_b[k + 1], dt, world)
            pos[k + 1] = state.pos; vel[k + 1] = state.vel; att[k + 1] = _dcm_to_euler1(state.C)
        return pos, vel, att

    if method == "rk4":
        q = quat_from_dcm(init.C)
        p = init.pos.astype(float).copy()
        v = init.vel.astype(float).copy()
        for k in range(N - 1):
            h = float(t[k + 1] - t[k])
            f_mid = _midpoint_interp(f_b, k, N)
            w_mid = _midpoint_interp(omega_b, k, N)
            fk, wk = f_b[k], omega_b[k]
            fk1, wk1 = f_b[k + 1], omega_b[k + 1]

            qd1, vd1, pd1 = _dynamics(q, v, p, fk, wk, world)
            q2 = _quat_normalize1(q + 0.5 * h * qd1); v2 = v + 0.5 * h * vd1; p2 = p + 0.5 * h * pd1
            qd2, vd2, pd2 = _dynamics(q2, v2, p2, f_mid, w_mid, world)
            q3 = _quat_normalize1(q + 0.5 * h * qd2); v3 = v + 0.5 * h * vd2; p3 = p + 0.5 * h * pd2
            qd3, vd3, pd3 = _dynamics(q3, v3, p3, f_mid, w_mid, world)
            q4 = _quat_normalize1(q + h * qd3); v4 = v + h * vd3; p4 = p + h * pd3
            qd4, vd4, pd4 = _dynamics(q4, v4, p4, fk1, wk1, world)

            q = _quat_normalize1(q + (h / 6.0) * (qd1 + 2.0 * qd2 + 2.0 * qd3 + qd4))
            v = v + (h / 6.0) * (vd1 + 2.0 * vd2 + 2.0 * vd3 + vd4)
            p = p + (h / 6.0) * (pd1 + 2.0 * pd2 + 2.0 * pd3 + pd4)

            pos[k + 1] = p; vel[k + 1] = v; att[k + 1] = _dcm_to_euler1(_dcm_from_quat1(q))
        return pos, vel, att

    raise ValueError(f"unknown method {method!r}; expected 'rk4' or 'causal'")
