"""Deterministic, hierarchical RNG streams (DECISION_LOG D-005).

Every (node, component) pair gets an independent stream derived from one
master seed, so adding a component never perturbs the noise of another.
"""
from __future__ import annotations

import hashlib

import numpy as np


def _key_to_ints(*keys: str) -> list[int]:
    out = []
    for k in keys:
        h = hashlib.sha256(k.encode("utf8")).digest()
        out.append(int.from_bytes(h[:4], "little"))
    return out


def stream(master_seed: int, *keys: str) -> np.random.Generator:
    """Return the RNG for e.g. ``stream(42, "node3", "quantum")``."""
    ss = np.random.SeedSequence(entropy=master_seed, spawn_key=tuple(_key_to_ints(*keys)))
    return np.random.default_rng(ss)
