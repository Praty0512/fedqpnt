"""Rotation utilities (WP-1.2, ARCHITECTURE.md section 11.1).

Convention (contract v0.2, ``fedqpnt.core.types`` docstring; ARCHITECTURE.md
section 0): Euler angles ``att = [phi, theta, psi]`` (roll, pitch, yaw), strict
ZYX composition, right-handed elementary rotations::

    C = Rz(psi) @ Ry(theta) @ Rx(phi)

``C`` maps a body-frame (FLU) vector to the nav frame (ENU): ``v_n = C @ v_b``
(i.e. ``C = C_nb``). With this convention: psi = 0 => nose East, psi
increases counter-clockwise (towards North); theta > 0 => nose DOWN; phi > 0
=> left wing up. Body rates <-> Euler rates (frame-name-free algebra of the
Z-Y-X composition):

    p = phi_dot - psi_dot * sin(theta)
    q = theta_dot * cos(phi) + psi_dot * cos(theta) * sin(phi)
    r = -theta_dot * sin(phi) + psi_dot * cos(theta) * cos(phi)

Quaternions use the Hamilton convention, ``q = [w, x, y, z]``, with the same
body->nav sense as ``C`` (``dcm_from_quat(quat_from_dcm(C)) == C``).

All functions accept a single sample or a batch (leading ``N`` axis) except
``skew``/``vee``, which are single-sample per the WP-1.2 brief signature.
"""
from __future__ import annotations

import numpy as np

_EPS_SMALL_ANGLE = 1e-8
_EPS_LOG_SMALL = 1e-7
_EPS_LOG_PI = 1e-4


# ---------------------------------------------------------------------------
# skew / vee (single sample, per brief signature)
# ---------------------------------------------------------------------------
def skew(v: np.ndarray) -> np.ndarray:
    """(3,) -> (3,3) skew-symmetric matrix such that ``skew(v) @ x == v x x``."""
    v = np.asarray(v, dtype=float)
    x, y, z = v[0], v[1], v[2]
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def vee(M: np.ndarray) -> np.ndarray:
    """(3,3) -> (3,), uses the antisymmetric part 1/2 (M - M^T)."""
    M = np.asarray(M, dtype=float)
    A = 0.5 * (M - M.T)
    return np.array([A[2, 1], A[0, 2], A[1, 0]])


def _skew_batch(v: np.ndarray) -> np.ndarray:
    """(N,3) -> (N,3,3), vectorised ``skew``."""
    N = v.shape[0]
    K = np.zeros((N, 3, 3))
    x, y, z = v[:, 0], v[:, 1], v[:, 2]
    K[:, 0, 1] = -z
    K[:, 0, 2] = y
    K[:, 1, 0] = z
    K[:, 1, 2] = -x
    K[:, 2, 0] = -y
    K[:, 2, 1] = x
    return K


def _vee_batch(M: np.ndarray) -> np.ndarray:
    """(N,3,3) -> (N,3), vectorised ``vee`` (antisymmetric part)."""
    A = 0.5 * (M - np.transpose(M, (0, 2, 1)))
    return np.stack([A[:, 2, 1], A[:, 0, 2], A[:, 1, 0]], axis=-1)


# ---------------------------------------------------------------------------
# Euler <-> DCM
# ---------------------------------------------------------------------------
def euler_to_dcm(att: np.ndarray) -> np.ndarray:
    """(3,) or (N,3) roll/pitch/yaw -> (3,3) or (N,3,3). C = Rz(psi) Ry(theta) Rx(phi)."""
    att = np.asarray(att, dtype=float)
    single = att.ndim == 1
    a = att.reshape(1, 3) if single else att.reshape(-1, 3)
    phi, theta, psi = a[:, 0], a[:, 1], a[:, 2]
    cphi, sphi = np.cos(phi), np.sin(phi)
    cth, sth = np.cos(theta), np.sin(theta)
    cpsi, spsi = np.cos(psi), np.sin(psi)

    N = a.shape[0]
    C = np.empty((N, 3, 3))
    C[:, 0, 0] = cpsi * cth
    C[:, 0, 1] = cpsi * sth * sphi - spsi * cphi
    C[:, 0, 2] = cpsi * sth * cphi + spsi * sphi
    C[:, 1, 0] = spsi * cth
    C[:, 1, 1] = spsi * sth * sphi + cpsi * cphi
    C[:, 1, 2] = spsi * sth * cphi - cpsi * sphi
    C[:, 2, 0] = -sth
    C[:, 2, 1] = cth * sphi
    C[:, 2, 2] = cth * cphi

    return C[0] if single else C.reshape(att.shape[:-1] + (3, 3))


def dcm_to_euler(C: np.ndarray) -> np.ndarray:
    """(3,3) or (N,3,3) -> (3,) or (N,3) roll/pitch/yaw.

    phi = atan2(C[2,1], C[2,2]); theta = -asin(clip(C[2,0])); psi = atan2(C[1,0], C[0,0]).
    Valid away from the |theta| = 90 deg gimbal-lock singularity.
    """
    C = np.asarray(C, dtype=float)
    single = C.ndim == 2
    Cb = C.reshape(1, 3, 3) if single else C.reshape(-1, 3, 3)
    phi = np.arctan2(Cb[:, 2, 1], Cb[:, 2, 2])
    theta = -np.arcsin(np.clip(Cb[:, 2, 0], -1.0, 1.0))
    psi = np.arctan2(Cb[:, 1, 0], Cb[:, 0, 0])
    att = np.stack([phi, theta, psi], axis=-1)
    return att[0] if single else att.reshape(C.shape[:-2] + (3,))


# ---------------------------------------------------------------------------
# SO(3) exponential / logarithm (Rodrigues), batch-capable
# ---------------------------------------------------------------------------
def so3_exp(phi: np.ndarray) -> np.ndarray:
    """(3,) or (N,3) rotation vector -> (3,3) or (N,3,3) DCM. Taylor series for |phi| < 1e-8."""
    phi = np.asarray(phi, dtype=float)
    single = phi.ndim == 1
    p = phi.reshape(1, 3) if single else phi.reshape(-1, 3)
    theta = np.linalg.norm(p, axis=1)
    K = _skew_batch(p)
    K2 = K @ K

    small = theta < _EPS_SMALL_ANGLE
    theta_safe = np.where(small, 1.0, theta)
    a = np.where(small, 1.0 - theta ** 2 / 6.0, np.sin(theta_safe) / theta_safe)
    b = np.where(small, 0.5 - theta ** 2 / 24.0, (1.0 - np.cos(theta_safe)) / (theta_safe ** 2))

    N = p.shape[0]
    I = np.broadcast_to(np.eye(3), (N, 3, 3))
    R = I + a[:, None, None] * K + b[:, None, None] * K2
    return R[0] if single else R.reshape(phi.shape[:-1] + (3, 3))


def so3_log(C: np.ndarray) -> np.ndarray:
    """(3,3) or (N,3,3) DCM -> (3,) or (N,3) rotation vector. Robust near 0 and near pi."""
    C = np.asarray(C, dtype=float)
    single = C.ndim == 2
    Cs = C.reshape(1, 3, 3) if single else C.reshape(-1, 3, 3)
    N = Cs.shape[0]

    tr = np.trace(Cs, axis1=1, axis2=2)
    cos_theta = np.clip((tr - 1.0) / 2.0, -1.0, 1.0)
    theta = np.arccos(cos_theta)

    out = np.zeros((N, 3))
    near_pi = theta > (np.pi - _EPS_LOG_PI)
    small = theta < _EPS_LOG_SMALL
    mid = ~near_pi & ~small

    if np.any(mid) or np.any(small):
        reg = mid | small
        Cm = Cs[reg]
        thm = theta[reg]
        antisym = _vee_batch(Cm - np.transpose(Cm, (0, 2, 1)))
        # theta / (2 sin theta), Taylor for small theta: 1/2 (1 + theta^2/6 + 7 theta^4/360)
        thm_safe = np.where(thm < _EPS_LOG_SMALL, 1.0, thm)
        scale = np.where(
            thm < _EPS_LOG_SMALL,
            0.5 * (1.0 + thm ** 2 / 6.0 + 7.0 * thm ** 4 / 360.0),
            thm_safe / (2.0 * np.sin(thm_safe)),
        )
        out[reg] = scale[:, None] * antisym

    if np.any(near_pi):
        idxs = np.nonzero(near_pi)[0]
        for i in idxs:
            Ci = Cs[i]
            thi = theta[i]
            diagR = np.diag(Ci)
            n2 = np.clip((diagR + 1.0) / 2.0, 0.0, None)
            n = np.sqrt(n2)
            k = int(np.argmax(n))
            if n[k] < 1e-12:
                # theta ~ pi but C ~ -I is impossible for a rotation; fall back to zero axis
                out[i] = np.zeros(3)
                continue
            for j in range(3):
                if j == k:
                    continue
                # off-diagonal R[k,j] = 2 n_k n_j (k != j) at theta = pi
                s = Ci[k, j]
                n[j] = np.sign(s) * n[j] if s != 0 else n[j]
            out[i] = thi * n

    result = out[0] if single else out.reshape(C.shape[:-2] + (3,))
    return result


# ---------------------------------------------------------------------------
# Quaternions (Hamilton, q = [w, x, y, z])
# ---------------------------------------------------------------------------
def quat_from_dcm(C: np.ndarray) -> np.ndarray:
    """(3,3) or (N,3,3) -> (4,) or (N,4), Shepperd's method (numerically robust)."""
    C = np.asarray(C, dtype=float)
    single = C.ndim == 2
    Cs = C.reshape(1, 3, 3) if single else C.reshape(-1, 3, 3)
    N = Cs.shape[0]
    q = np.empty((N, 4))
    tr = np.trace(Cs, axis1=1, axis2=2)

    for i in range(N):
        Ci = Cs[i]
        t = tr[i]
        if t > 0:
            s = np.sqrt(t + 1.0) * 2.0
            w = 0.25 * s
            x = (Ci[2, 1] - Ci[1, 2]) / s
            y = (Ci[0, 2] - Ci[2, 0]) / s
            z = (Ci[1, 0] - Ci[0, 1]) / s
        elif Ci[0, 0] > Ci[1, 1] and Ci[0, 0] > Ci[2, 2]:
            s = np.sqrt(1.0 + Ci[0, 0] - Ci[1, 1] - Ci[2, 2]) * 2.0
            w = (Ci[2, 1] - Ci[1, 2]) / s
            x = 0.25 * s
            y = (Ci[0, 1] + Ci[1, 0]) / s
            z = (Ci[0, 2] + Ci[2, 0]) / s
        elif Ci[1, 1] > Ci[2, 2]:
            s = np.sqrt(1.0 + Ci[1, 1] - Ci[0, 0] - Ci[2, 2]) * 2.0
            w = (Ci[0, 2] - Ci[2, 0]) / s
            x = (Ci[0, 1] + Ci[1, 0]) / s
            y = 0.25 * s
            z = (Ci[1, 2] + Ci[2, 1]) / s
        else:
            s = np.sqrt(1.0 + Ci[2, 2] - Ci[0, 0] - Ci[1, 1]) * 2.0
            w = (Ci[1, 0] - Ci[0, 1]) / s
            x = (Ci[0, 2] + Ci[2, 0]) / s
            y = (Ci[1, 2] + Ci[2, 1]) / s
            z = 0.25 * s
        q[i] = [w, x, y, z]

    q = quat_normalize(q)
    return q[0] if single else q.reshape(C.shape[:-2] + (4,))


def dcm_from_quat(q: np.ndarray) -> np.ndarray:
    """(4,) or (N,4) -> (3,3) or (N,3,3)."""
    q = np.asarray(q, dtype=float)
    single = q.ndim == 1
    qb = quat_normalize(q.reshape(1, 4) if single else q.reshape(-1, 4))
    w, x, y, z = qb[:, 0], qb[:, 1], qb[:, 2], qb[:, 3]
    N = qb.shape[0]
    C = np.empty((N, 3, 3))
    C[:, 0, 0] = 1 - 2 * (y * y + z * z)
    C[:, 0, 1] = 2 * (x * y - w * z)
    C[:, 0, 2] = 2 * (x * z + w * y)
    C[:, 1, 0] = 2 * (x * y + w * z)
    C[:, 1, 1] = 1 - 2 * (x * x + z * z)
    C[:, 1, 2] = 2 * (y * z - w * x)
    C[:, 2, 0] = 2 * (x * z - w * y)
    C[:, 2, 1] = 2 * (y * z + w * x)
    C[:, 2, 2] = 1 - 2 * (x * x + y * y)
    return C[0] if single else C.reshape(q.shape[:-1] + (3, 3))


def quat_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Hamilton product, (4,)/(N,4) x (4,)/(N,4) -> broadcast result."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    single = a.ndim == 1 and b.ndim == 1
    ab = np.broadcast_to(a, np.broadcast_shapes(a.shape, b.shape)).reshape(-1, 4)
    bb = np.broadcast_to(b, np.broadcast_shapes(a.shape, b.shape)).reshape(-1, 4)
    w1, x1, y1, z1 = ab[:, 0], ab[:, 1], ab[:, 2], ab[:, 3]
    w2, x2, y2, z2 = bb[:, 0], bb[:, 1], bb[:, 2], bb[:, 3]
    w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
    x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
    y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
    z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
    out = np.stack([w, x, y, z], axis=-1)
    return out[0] if single else out.reshape(np.broadcast_shapes(a.shape, b.shape))


def quat_normalize(q: np.ndarray) -> np.ndarray:
    q = np.asarray(q, dtype=float)
    single = q.ndim == 1
    qb = q.reshape(1, 4) if single else q.reshape(-1, 4)
    n = np.linalg.norm(qb, axis=1, keepdims=True)
    n = np.where(n < 1e-300, 1.0, n)
    out = qb / n
    return out[0] if single else out.reshape(q.shape)


# ---------------------------------------------------------------------------
# Body rates <-> Euler rates (ARCHITECTURE.md section 0)
# ---------------------------------------------------------------------------
def body_rates_from_euler_rates(att: np.ndarray, att_dot: np.ndarray) -> np.ndarray:
    """(3,)/(N,3) [phi,theta,psi], (3,)/(N,3) [phi_dot,theta_dot,psi_dot] -> (3,)/(N,3) [p,q,r]."""
    att = np.asarray(att, dtype=float)
    att_dot = np.asarray(att_dot, dtype=float)
    single = att.ndim == 1
    a = att.reshape(-1, 3) if not single else att.reshape(1, 3)
    ad = att_dot.reshape(-1, 3) if not single else att_dot.reshape(1, 3)
    phi, theta = a[:, 0], a[:, 1]
    phid, thetad, psid = ad[:, 0], ad[:, 1], ad[:, 2]
    cphi, sphi = np.cos(phi), np.sin(phi)
    cth, sth = np.cos(theta), np.sin(theta)
    p = phid - psid * sth
    q = thetad * cphi + psid * cth * sphi
    r = -thetad * sphi + psid * cth * cphi
    out = np.stack([p, q, r], axis=-1)
    return out[0] if single else out.reshape(att.shape)


def euler_rates_from_body_rates(att: np.ndarray, omega_b: np.ndarray) -> np.ndarray:
    """(3,)/(N,3) [phi,theta,psi], (3,)/(N,3) [p,q,r] -> (3,)/(N,3) [phi_dot,theta_dot,psi_dot]."""
    att = np.asarray(att, dtype=float)
    omega_b = np.asarray(omega_b, dtype=float)
    single = att.ndim == 1
    a = att.reshape(-1, 3) if not single else att.reshape(1, 3)
    ob = omega_b.reshape(-1, 3) if not single else omega_b.reshape(1, 3)
    phi, theta = a[:, 0], a[:, 1]
    p, q, r = ob[:, 0], ob[:, 1], ob[:, 2]
    cphi, sphi = np.cos(phi), np.sin(phi)
    cth, sth = np.cos(theta), np.sin(theta)
    tth = sth / cth
    phid = p + (q * sphi + r * cphi) * tth
    thetad = q * cphi - r * sphi
    psid = (q * sphi + r * cphi) / cth
    out = np.stack([phid, thetad, psid], axis=-1)
    return out[0] if single else out.reshape(att.shape)
