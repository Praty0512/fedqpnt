"""SS4.5 poisoning attacks (S12/S15), the 4 types listed there: sign-flip
x(-5), Gaussian noise at 10x the median norm, label-flip, and "A Little Is
Enough" (ALIE, Baruch et al. 2019). Applied to a fraction f of nodes.

Model-poisoning attacks (sign-flip, gaussian-noise, ALIE) act on the node's
*trained delta* right before it is sent (a malicious client still trains
normally, then corrupts the outgoing update). Label-flip acts earlier, on
the client's own pseudo-labels before local training.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm


def sign_flip(delta: dict[str, np.ndarray], factor: float = -5.0) -> dict[str, np.ndarray]:
    """Sign-flip x(-5): Delta_i <- -5 * Delta_i."""
    return {k: factor * np.asarray(v) for k, v in delta.items()}


def gaussian_noise(delta: dict[str, np.ndarray], rng: np.random.Generator,
                    target_norm: float) -> dict[str, np.ndarray]:
    """Replace the delta with i.i.d. Gaussian noise rescaled so its L2 norm
    equals ``target_norm`` (SS4.5: "10x the median norm" -- the caller passes
    ``target_norm = 10 * median_honest_norm``, estimated by the scenario)."""
    noise = {k: rng.normal(size=np.asarray(v).shape) for k, v in delta.items()}
    flat = np.concatenate([n.ravel() for n in noise.values()])
    scale = target_norm / (float(np.linalg.norm(flat)) + 1e-12)
    return {k: n * scale for k, n in noise.items()}


def label_flip(y: np.ndarray) -> np.ndarray:
    """Flip pseudo-labels y -> 1-y (abstains, i.e. nan, are left alone).
    ``y`` shape (N,) or (N,2) [y_spoof, y_jam]."""
    y = np.asarray(y, dtype=float)
    out = y.copy()
    mask = ~np.isnan(y)
    out[mask] = 1.0 - out[mask]
    return out


def alie_z(n_total: int, n_malicious: int) -> float:
    """Standard ALIE z (Baruch, Baruch & Yehuda Alon Alon 2019, NeurIPS):
    largest z s.t. Phi(z) <= (n-m-s)/(n-m), s = floor(n/2+1) - m.
    PROPOSED-DECISION: the paper's exact "supporters" bookkeeping for a
    trimmed-mean/median defence is approximated here by this closed-form z
    (the standard simplification used in most open re-implementations);
    exact per-coordinate order-statistics tracking is not implemented."""
    n_total = max(n_total, 1)
    n_malicious = max(min(n_malicious, n_total - 1), 0)
    s = max(np.floor(n_total / 2.0 + 1.0) - n_malicious, 1.0)
    denom = max(n_total - n_malicious, 1)
    target = float(np.clip((n_total - n_malicious - s) / denom, 1e-6, 1 - 1e-6))
    return float(norm.ppf(target))


def alie(honest_deltas: list[dict[str, np.ndarray]], param_names: list[str],
         n_total: int, n_malicious: int) -> dict[str, np.ndarray]:
    """Craft a malicious delta near the honest mean, shifted by z*sigma
    (per-coordinate), using the attacker's (omniscient, simulation-only)
    view of the other honest deltas this round."""
    z = alie_z(n_total, n_malicious)
    out = {}
    for name in param_names:
        stacked = np.stack([np.asarray(d[name], dtype=np.float64) for d in honest_deltas])
        mu = stacked.mean(axis=0)
        sd = stacked.std(axis=0)
        out[name] = mu - z * sd
    return out
