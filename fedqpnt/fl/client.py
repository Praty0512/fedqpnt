"""SS4.2/SS4.3/SS8 FL client (runs inside each Node process): local training
over hindsight pseudo-labels + ``ModelUpdate`` construction.

Data source independence: the client never generates its own training data.
It calls an injected ``local_dataset_provider(node_id, round_idx) -> (X, y)``
where ``X`` is ``(n, 13)`` raw (un-normalised, un-stacked) trust features for
epochs newly available this round and ``y`` is ``(n, 2)`` pseudo-labels
(columns ``[y_spoof, y_jam]``, ``nan`` = abstain). This lets the data source
be swapped later (M2 closed-loop features) with no code change here -- see
``tests/_fl_harness.py`` for the M0/M1 provider built on the trust test
harness (real fedqpnt.gnss + fedqpnt.attacks streams), per the task brief.
"""
from __future__ import annotations

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import torch

torch.set_num_threads(1)

from fedqpnt.core.types import ModelUpdate
from fedqpnt.trust.detector import TrustDetector
from fedqpnt.trust.features import EwmaStack

LocalDatasetProvider = Callable[[str, int], "tuple[np.ndarray, np.ndarray]"]


@dataclass
class ClientConfig:
    local_epochs: int = 2
    lr: float = 0.05
    batch_size: int = 64
    prox_mu: float = 0.01
    max_pos_fraction: float = 0.5
    min_samples: int = 64          # SS4.2: NoUpdate heartbeat below this
    max_replay: int = 20_000       # SS4.2: replay buffer cap


class FLClient:
    """Owns one node's ``TrustDetector`` (the only trained object, SS4.1) and
    the causal normaliser/EWMA-stack pipeline that turns raw features into
    the 52-d stacked input ``train_local`` expects."""

    def __init__(self, node_id: str, provider: LocalDatasetProvider, detector: TrustDetector,
                 cfg: ClientConfig | None = None, rng: np.random.Generator | None = None):
        self.node_id = node_id
        self.provider = provider
        self.detector = detector
        self.cfg = cfg or ClientConfig()
        self.rng = rng or np.random.default_rng(0)
        self._stack = EwmaStack()
        self._replay_U: list[np.ndarray] = []
        self._replay_y: list[np.ndarray] = []
        self.last_installed_round = -1

    def install_global(self, params: dict[str, np.ndarray], round_idx: int) -> None:
        self.detector.set_params(params)
        self.last_installed_round = round_idx

    def _extend_replay(self, X: np.ndarray, y: np.ndarray) -> None:
        for k in range(X.shape[0]):
            yk = y[k]
            if np.all(np.isnan(yk)):
                continue
            if np.all(np.nan_to_num(yk, nan=0.0) <= 0):
                # negative (pseudo-label y=0) sample: update the running
                # normalisation moments BEFORE normalising this sample
                # (SS4.2: stats are updated only on negative samples).
                self.detector.normalizer.update(X[k])
            xtilde = self.detector.normalizer.normalize(X[k])
            u = self._stack.step(float(len(self._replay_U)), xtilde)
            self._replay_U.append(u)
            self._replay_y.append(np.nan_to_num(yk, nan=0.0))
        if len(self._replay_U) > self.cfg.max_replay:
            # PROPOSED-DECISION: SS4.2 calls for a "class-balanced reservoir"
            # over the whole replay history; here the cap is enforced by
            # dropping the oldest samples (FIFO), and the class balance cap
            # itself is enforced by TrustDetector.train_local(balance=True)
            # at train time, not by the reservoir's admission policy.
            self._replay_U = self._replay_U[-self.cfg.max_replay:]
            self._replay_y = self._replay_y[-self.cfg.max_replay:]

    def local_round(self, round_idx: int) -> Optional[ModelUpdate]:
        """Runs one SS4.2 round: ingest new data, train E epochs, build the
        ``ModelUpdate``. Returns ``None`` if there are fewer than
        ``min_samples`` labelled samples (caller sends ``NoUpdate``)."""
        X, y = self.provider(self.node_id, round_idx)
        if X is not None and len(X) > 0:
            self._extend_replay(np.asarray(X, dtype=np.float64), np.asarray(y, dtype=np.float64))

        n = len(self._replay_U)
        if n < self.cfg.min_samples:
            return None

        theta_g = self.detector.get_params()
        U = np.array(self._replay_U)
        y_arr = np.array(self._replay_y)
        metrics = self.detector.train_local(
            U, y_arr[:, 0], y_arr[:, 1],
            epochs=self.cfg.local_epochs, lr=self.cfg.lr, batch_size=self.cfg.batch_size,
            prox_mu=self.cfg.prox_mu, theta_g=theta_g, rng=self.rng,
            max_pos_fraction=self.cfg.max_pos_fraction, balance=True,
        )
        new_params = self.detector.get_params()
        # SS4.1: only the model weights are sent as a DELTA; the
        # normalisation stats are sent as absolute values (server aggregates
        # them by coordinate-wise median, not delta-averaged).
        delta = {k: np.asarray(new_params[k]) - np.asarray(theta_g[k])
                 for k in theta_g if k not in ("norm_mu", "norm_sd", "norm_count")}
        delta["norm_mu"] = new_params["norm_mu"]
        delta["norm_sd"] = new_params["norm_sd"]
        metrics = dict(metrics)
        metrics["base_round"] = float(self.last_installed_round)
        return ModelUpdate(node_id=self.node_id, round_idx=round_idx, params=delta,
                            n_samples=n, metrics=metrics, kind="delta")
