"""D-052/D-050 (M2 completion): round-boundary slicer for a fleet node's
PRE-BUILT local FL training dataset.

The rejected surrogate path (D-050: ``innovations=[]`` + ``surrogate_s_cusum``
+ hindsight pseudo-labels, computed live inside the node's own mission tick
loop) is gone. The node's local dataset is now built OFFLINE, before the
node process is spawned, from real labelled TRAINING missions -- see
``fedqpnt.fleet.local_data.build_node_local_dataset``, which reuses
``fedqpnt.training.build_supervised_dataset`` (the same real-feature path /
oracle-label join the supervised detector is trained on, D-052). That
builder module is orchestrator-side only.

This module holds only the plain-numpy round-slicing logic that runs INSIDE
the node process, so ``fedqpnt/fleet/node_runner.py`` never has to import
``fedqpnt.training`` or ``fedqpnt.trust.features``/``fedqpnt.trust.detector``
to consume its own pre-built dataset -- the label join never reaches a live
node Agent process (tests/test_fleet_leakage_guard.py).
"""
from __future__ import annotations

from typing import Callable

import numpy as np

LocalDatasetProvider = Callable[[str, int], "tuple[np.ndarray, np.ndarray]"]


def make_round_provider(X: np.ndarray, y: np.ndarray, n_rounds: int) -> LocalDatasetProvider:
    """Splits a pre-built ``(X, y)`` dataset (D-052 offline-built, oracle-
    labelled) into ``n_rounds`` contiguous chunks and returns a
    ``local_dataset_provider(node_id, round_idx) -> (X, y)`` callable --
    ``fedqpnt.fl.client.FLClient``'s existing contract. Each call emits
    everything newly reachable up to ``round_idx`` that hasn't been emitted
    yet (cumulative-since-last-call semantics, same as the tracker this
    replaces), so a node that joins late or skips rounds still sees its
    whole assigned share once it catches up."""
    X = np.asarray(X, dtype=np.float64) if X is not None else np.zeros((0, 15))
    y = np.asarray(y, dtype=np.float64) if y is not None else np.zeros((0, 2))
    n = len(X)
    n_dims = X.shape[1] if X.ndim == 2 and X.shape[1] > 0 else 15
    if n == 0 or n_rounds <= 0:
        edges = np.array([0])
    else:
        edges = np.linspace(0, n, n_rounds + 1).round().astype(int)
    state = dict(emitted_upto=0)

    def _provider(node_id: str, round_idx: int) -> tuple[np.ndarray, np.ndarray]:
        idx = min(round_idx + 1, len(edges) - 1)
        upto = int(edges[idx]) if len(edges) > 1 else n
        emitted = state["emitted_upto"]
        if upto <= emitted:
            return np.zeros((0, n_dims)), np.zeros((0, 2))
        state["emitted_upto"] = upto
        return X[emitted:upto], y[emitted:upto]

    return _provider
