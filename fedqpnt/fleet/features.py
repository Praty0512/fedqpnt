"""Real hindsight-pseudo-label feature tracker for one fleet node.

Mirrors ``fedqpnt.node.methods.pretrain_detector``'s existing, already-
approved pattern (own ``GnssFeatureExtractor``, ``innovations=[]``,
``surrogate_s_cusum`` + ``label_epochs``) rather than reconstructing
``Innovation`` objects from the live ESKF -- x1/x2 (innovation-NIS features)
are therefore unavailable here, same as in that precedent; PROPOSED-DECISION,
out of scope without touching ``fedqpnt/fusion/eskf.py``.

Implements the ``local_dataset_provider(node_id, round) -> (X, y)`` contract
fedqpnt.fl.client.FLClient expects (SS4.2/SS4.3), fed by REAL per-tick
``GnssFix`` objects from a live ``fedqpnt.node.agent.Agent``.
"""
from __future__ import annotations

import numpy as np

from fedqpnt.core.types import GnssFix
from fedqpnt.trust.features import GnssFeatureExtractor
from fedqpnt.trust.pseudolabel import PseudoLabelConfig, label_epochs, surrogate_s_cusum


class FleetFeatureTracker:
    """One instance per node. Call ``observe(t, fix)`` every GNSS epoch the
    node's real Agent processes; call ``provider(node_id, round_idx)`` at
    each FL round boundary (matches ``LocalDatasetProvider``)."""

    def __init__(self, cfg: PseudoLabelConfig | None = None):
        self.cfg = cfg or PseudoLabelConfig()
        self.extractor = GnssFeatureExtractor()
        self._t: list[float] = []
        self._raw: list[np.ndarray] = []
        self._raim: list[float] = []
        self._nsat: list[float] = []
        self._last_emitted = 0

    def observe(self, t: float, fix: GnssFix | None) -> None:
        if fix is None:
            return
        raw = self.extractor.step(fix, [])   # x1/x2 unavailable, see module docstring
        if raw is None:
            return
        self._t.append(t)
        self._raw.append(raw)
        self._raim.append(float(fix.raim_stat) if np.isfinite(fix.raim_stat) else 0.0)
        self._nsat.append(float(fix.num_sats))

    def n_observed(self) -> int:
        return len(self._t)

    def provider(self, node_id: str, round_idx: int) -> tuple[np.ndarray, np.ndarray]:
        """Returns raw features/pseudo-labels observed since the LAST call
        (SS4.2's replay buffer is cumulative on the FLClient side, so this
        provider only needs to emit what's NEW each round)."""
        n_dims = self._raw[0].shape[0] if self._raw else 15
        if len(self._t) <= self._last_emitted:
            return np.zeros((0, n_dims)), np.zeros((0, 2))
        t_arr = np.asarray(self._t, dtype=float)
        raw_arr = np.asarray(self._raw, dtype=float)
        s_cusum = surrogate_s_cusum(raw_arr)
        y = label_epochs(t_arr, raw_arr, np.asarray(self._raim, dtype=float),
                          np.asarray(self._nsat, dtype=float), s_cusum, cfg=self.cfg)
        start = self._last_emitted
        self._last_emitted = len(t_arr)
        X_new = raw_arr[start:]
        y_new = y[start:]
        return X_new, np.stack([y_new, y_new], axis=1)
