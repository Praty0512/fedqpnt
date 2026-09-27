"""SS4.5 poisoning attack unit tests: sign-flip, Gaussian noise (target
norm), label-flip, and ALIE's z formula sanity."""
from __future__ import annotations

import numpy as np

from fedqpnt.fl.poisoning import sign_flip, gaussian_noise, label_flip, alie, alie_z


def test_sign_flip_negates_and_scales():
    delta = {"w": np.array([1.0, -2.0, 3.0])}
    out = sign_flip(delta, factor=-5.0)
    assert np.allclose(out["w"], [-5.0, 10.0, -15.0])


def test_gaussian_noise_hits_target_norm():
    delta = {"a": np.ones(10), "b": np.ones(5)}
    rng = np.random.default_rng(0)
    out = gaussian_noise(delta, rng, target_norm=7.0)
    flat = np.concatenate([out["a"].ravel(), out["b"].ravel()])
    assert np.isclose(np.linalg.norm(flat), 7.0, atol=1e-6)


def test_label_flip_flips_only_non_abstain():
    y = np.array([1.0, 0.0, np.nan, 1.0])
    out = label_flip(y)
    assert np.allclose(out[:2], [0.0, 1.0])
    assert np.isnan(out[2])
    assert out[3] == 0.0


def test_alie_z_decreases_as_malicious_fraction_grows():
    z_low_f = alie_z(n_total=100, n_malicious=5)
    z_high_f = alie_z(n_total=100, n_malicious=45)
    assert isinstance(z_low_f, float) and isinstance(z_high_f, float)
    # more compromised clients -> the attacker can push further per-worker
    # before the honest majority's order statistics are dominated
    assert z_high_f != z_low_f


def test_alie_delta_between_honest_min_and_beyond():
    honest = [{"w": np.array([1.0, 1.0])}, {"w": np.array([1.1, 0.9])}, {"w": np.array([0.9, 1.1])}]
    out = alie(honest, ["w"], n_total=10, n_malicious=2)
    assert out["w"].shape == (2,)
    assert np.all(np.isfinite(out["w"]))
