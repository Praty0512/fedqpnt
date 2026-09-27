"""Tests for fedqpnt.sim.rotations (WP-1.2, ARCHITECTURE.md section 11.1)."""
from __future__ import annotations

import numpy as np
import pytest

from fedqpnt.sim.rotations import (
    body_rates_from_euler_rates, dcm_from_quat, dcm_to_euler, euler_rates_from_body_rates,
    euler_to_dcm, quat_from_dcm, quat_mul, quat_normalize, skew, so3_exp, so3_log, vee,
)


def test_skew_vee_roundtrip():
    rng = np.random.default_rng(0)
    for _ in range(1000):
        v = rng.normal(size=3)
        assert np.allclose(vee(skew(v)), v, atol=1e-13)


def test_skew_cross_product_identity():
    rng = np.random.default_rng(1)
    for _ in range(200):
        a = rng.normal(size=3)
        b = rng.normal(size=3)
        assert np.allclose(skew(a) @ b, np.cross(a, b), atol=1e-12)


def test_euler_dcm_roundtrip_1e4_samples():
    rng = np.random.default_rng(2)
    N = 10_000
    phi = rng.uniform(-np.pi, np.pi, N)
    theta = rng.uniform(-89 * np.pi / 180, 89 * np.pi / 180, N)
    psi = rng.uniform(-np.pi, np.pi, N)
    att = np.stack([phi, theta, psi], axis=-1)
    C = euler_to_dcm(att)
    att2 = dcm_to_euler(C)
    assert np.max(np.abs(att2 - att)) < 1e-12


def test_euler_to_dcm_east_convention():
    for psi in np.linspace(-np.pi, np.pi, 37):
        C = euler_to_dcm(np.array([0.0, 0.0, psi]))
        got = C @ np.array([1.0, 0.0, 0.0])
        expected = np.array([np.cos(psi), np.sin(psi), 0.0])
        assert np.allclose(got, expected, atol=1e-12)


def test_euler_to_dcm_pitch_down_convention():
    for theta in np.linspace(-1.5, 1.5, 31):
        C = euler_to_dcm(np.array([0.0, theta, 0.0]))
        got = C @ np.array([1.0, 0.0, 0.0])
        assert np.isclose(got[2], -np.sin(theta), atol=1e-12)


def test_exp_log_roundtrip():
    rng = np.random.default_rng(3)
    N = 10_000
    axis = rng.normal(size=(N, 3))
    axis /= np.linalg.norm(axis, axis=1, keepdims=True)
    theta = rng.uniform(0, np.pi - 1e-3, N)  # avoid the theta=pi sign-ambiguous boundary
    phi = axis * theta[:, None]
    C = so3_exp(phi)
    phi2 = so3_log(C)
    assert np.max(np.abs(phi2 - phi)) < 1e-9


def test_exp_log_small_angle():
    rng = np.random.default_rng(4)
    for _ in range(1000):
        phi = rng.normal(size=3) * 1e-10
        C = so3_exp(phi)
        assert np.allclose(C, np.eye(3), atol=1e-9)
        phi2 = so3_log(C)
        assert np.allclose(phi2, phi, atol=1e-9)


def test_exp_log_near_pi():
    rng = np.random.default_rng(5)
    for _ in range(200):
        axis = rng.normal(size=3)
        axis /= np.linalg.norm(axis)
        theta = np.pi - 1e-6
        phi = axis * theta
        C = so3_exp(phi)
        phi2 = so3_log(C)
        # near pi, phi and -phi (same axis flipped) represent the same rotation
        err = min(np.linalg.norm(phi2 - phi), np.linalg.norm(phi2 + phi))
        assert err < 1e-4


def test_so3_exp_is_orthonormal():
    rng = np.random.default_rng(6)
    phi = rng.normal(size=(500, 3)) * 2.0
    C = so3_exp(phi)
    I = np.eye(3)
    for k in range(0, 500, 25):
        assert np.allclose(C[k] @ C[k].T, I, atol=1e-10)
        assert np.isclose(np.linalg.det(C[k]), 1.0, atol=1e-10)


def test_quat_dcm_roundtrip():
    rng = np.random.default_rng(7)
    N = 2000
    axis = rng.normal(size=(N, 3))
    axis /= np.linalg.norm(axis, axis=1, keepdims=True)
    theta = rng.uniform(0, np.pi - 1e-3, N)
    C = so3_exp(axis * theta[:, None])
    q = quat_from_dcm(C)
    C2 = dcm_from_quat(q)
    assert np.max(np.abs(C2 - C)) < 1e-10


def test_quat_mul_identity():
    rng = np.random.default_rng(8)
    for _ in range(200):
        v = rng.normal(size=3)
        C = so3_exp(v)
        q = quat_from_dcm(C)
        ident = np.array([1.0, 0.0, 0.0, 0.0])
        assert np.allclose(quat_mul(q, ident), q, atol=1e-12)
        assert np.allclose(quat_mul(ident, q), q, atol=1e-12)


def test_quat_mul_matches_dcm_composition():
    rng = np.random.default_rng(9)
    for _ in range(200):
        Ca = so3_exp(rng.normal(size=3) * 0.5)
        Cb = so3_exp(rng.normal(size=3) * 0.5)
        qa = quat_from_dcm(Ca)
        qb = quat_from_dcm(Cb)
        q_ab = quat_mul(qa, qb)
        C_ab = dcm_from_quat(q_ab)
        assert np.allclose(C_ab, Ca @ Cb, atol=1e-9)


def test_quat_normalize():
    q = np.array([2.0, 0.0, 0.0, 0.0])
    qn = quat_normalize(q)
    assert np.isclose(np.linalg.norm(qn), 1.0)


def test_body_euler_rate_roundtrip():
    rng = np.random.default_rng(10)
    N = 5000
    phi = rng.uniform(-1.0, 1.0, N)
    theta = rng.uniform(-1.0, 1.0, N)
    psi = rng.uniform(-np.pi, np.pi, N)
    att = np.stack([phi, theta, psi], axis=-1)
    att_dot = rng.normal(size=(N, 3))
    omega_b = body_rates_from_euler_rates(att, att_dot)
    att_dot2 = euler_rates_from_body_rates(att, omega_b)
    assert np.max(np.abs(att_dot2 - att_dot)) < 1e-9


def test_body_rates_single_sample_matches_batch():
    att = np.array([0.1, 0.2, 0.3])
    att_dot = np.array([0.01, -0.02, 0.03])
    single = body_rates_from_euler_rates(att, att_dot)
    batch = body_rates_from_euler_rates(att[None, :], att_dot[None, :])
    assert np.allclose(single, batch[0])
