"""D-052/D-050 (M2 completion): builds each fleet node's OWN local FL
training dataset from real, oracle-labelled TRAINING missions -- the node's
own attack mix -- reusing ``fedqpnt.training.build_supervised_dataset``'s
real-feature collection path (``collect_run``) instead of duplicating the
feature logic. This supersedes the REJECTED surrogate-feature path
(``innovations=[]`` + ``surrogate_s_cusum``, D-050): the deployed detector
sees real x1/x2 innovation-NIS features, so training data must too.

Orchestrator-side ONLY. Called once per node, in the PARENT process, before
any ``fedqpnt.fleet.node_runner.run_fleet_node_process`` is spawned. The
result is a pair of plain numpy arrays handed to ``FleetNodeSpec``.
``fedqpnt/fleet/node_runner.py`` (the node's own process entry point) never
imports this module or ``fedqpnt.training`` -- the label join never happens
inside a live node Agent process
(tests/test_fleet_leakage_guard.py::test_node_runner_never_reaches_the_builder).
"""
from __future__ import annotations

import numpy as np

from fedqpnt.training.build_supervised_dataset import collect_run, run_pool


def build_node_local_dataset(seeds: list[int], pool: str = "mixed", duration_s: float = 310.0,
                              n_workers: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """Runs ``seeds`` real closed-loop TRAINING missions (this node's own
    attack mix, via ``fedqpnt.training.build_supervised_dataset.plan_for``'s
    existing seed convention) and returns ``(X, y)``: ``X`` is ``(n, 15)``
    raw un-normalised trust features (the same ``GnssFeatureExtractor`` path
    the deployed detector uses at runtime), ``y`` is ``(n, 2)``
    ``[y_spoof, y_jam]`` GROUND-TRUTH labels (0.0/1.0, no abstain -- these
    are oracle labels joined OFFLINE by ``collect_run``, strictly outside
    the Agent/node-runner runtime, matching the M1 supervised-detector
    training path, D-052)."""
    if not seeds:
        return np.zeros((0, 15)), np.zeros((0, 2))
    jobs = [(int(s), pool, duration_s) for s in seeds]
    if n_workers > 1:
        by_seed = run_pool(jobs, n_workers=n_workers)
    else:
        by_seed = {s: collect_run((s, pool, duration_s)) for s, _pool, _dur in jobs}
    X_parts, y_parts = [], []
    for s in seeds:
        c = by_seed[int(s)]
        if not c["t"]:
            continue
        X_parts.append(np.asarray(c["raw"], dtype=np.float64))
        y_parts.append(np.stack([np.asarray(c["y_spoof"], dtype=float),
                                  np.asarray(c["y_jam"], dtype=float)], axis=1))
    if not X_parts:
        return np.zeros((0, 15)), np.zeros((0, 2))
    return np.concatenate(X_parts, axis=0), np.concatenate(y_parts, axis=0)
