"""Test-local local_dataset_provider for fedqpnt.fl, built on the existing
trust test harness (tests/_trust_harness.py: real fedqpnt.gnss + fedqpnt.attacks
streams with synthetic innovations, per the FEDERATED agent's task brief).

This is deliberately NOT part of fedqpnt/fl/ (which must stay independent of
any concrete data source, per its docstring) -- real closed-loop features
are wired in at M2 integration; this class is the swappable M0/M1 stand-in,
matching the ``local_dataset_provider(node_id, round) -> (X, y)`` interface
``fedqpnt.fl.client.FLClient`` expects.

Deterministic: which (seed, attack family) each (node_id, round) uses is
drawn from ``fedqpnt.core.seeding.stream`` (never Python's salted ``hash``),
so it survives multiprocessing spawn and repeats bit-for-bit across runs.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from fedqpnt.core.seeding import stream
from fedqpnt.trust.pseudolabel import label_epochs, surrogate_s_cusum, PseudoLabelConfig
from tests._trust_harness import generate_run, FAMILIES

CALIB_CLEAN_SEEDS = range(500, 506)   # small + fast: FL tests care about the protocol, not detector SOTA


def clean_reference(seeds=CALIB_CLEAN_SEEDS):
    feats = np.concatenate([generate_run(s, "clean").raw_features for s in seeds])
    mu = feats.mean(axis=0)
    sd = feats.std(axis=0)
    sd = np.where(sd < 1e-9, 1.0, sd)
    return mu, sd


@dataclass
class TrustHarnessProvider:
    """Callable ``(node_id, round_idx) -> (X (n,13), y (n,2))``. Each call
    deterministically picks a (run_seed in [500,600), family) pair via
    ``stream(base_seed, node_id, "fl_harness", str(round_idx))`` and runs the
    hindsight pseudo-labeller (SS4.3) on it -- never ``AttackLabel``."""

    base_seed: int
    mu: np.ndarray
    sd: np.ndarray
    families: tuple = field(default_factory=lambda: ("clean",) + FAMILIES)   # clean weighted like the others
    duration_s: float = 20.0   # shorter than the 60s trust-detector tests: FL rounds need many of these

    def _pick(self, node_id: str, round_idx: int):
        # D-039: the round-0 forced-"clean" warm-start (added under D-037 to
        # work around chronically-zero-delta nodes) is REVERTED here now that
        # the real fix landed at the source: TrustDetector.train_local's
        # balance-rule dead zone (n_neg < n_min -> train on everything
        # instead of subsampling to ~0). Random family draws again, so this
        # harness exercises the fixed rule under the SAME conditions that
        # originally exposed the bug.
        rng = stream(self.base_seed, node_id, "fl_harness", str(round_idx))
        run_seed = int(rng.integers(500, 600))
        family = self.families[int(rng.integers(0, len(self.families)))]
        return run_seed, family

    def __call__(self, node_id: str, round_idx: int):
        run_seed, family = self._pick(node_id, round_idx)
        run = generate_run(run_seed, family, duration_s=self.duration_s)
        if len(run.t) == 0:
            return np.zeros((0, self.mu.shape[0])), np.zeros((0, 2))
        s_cusum = surrogate_s_cusum(run.raw_features)
        y = label_epochs(run.t, run.raw_features, run.raim_stat, run.num_sats, s_cusum,
                          cfg=PseudoLabelConfig(), quantile_mu=self.mu, quantile_sd=self.sd)
        y2 = np.stack([y, y], axis=1)
        return run.raw_features, y2


def make_provider(base_seed: int = 500, duration_s: float = 20.0) -> TrustHarnessProvider:
    mu, sd = clean_reference()
    return TrustHarnessProvider(base_seed=base_seed, mu=mu, sd=sd, duration_s=duration_s)


def held_out_eval_set(seed_base: int = 590, n_per_family: int = 2, duration_s: float = 45.0):
    """A FIXED held-out evaluation set for the evaluator-only global-model
    AUC-per-round report. Per the task brief, validation uses seeds 500-599
    only; this uses the top of that range (590-599 by default), disjoint
    from the ``TrustHarnessProvider`` calibration seeds (500-505) -- some
    overlap with the per-round TRAINING draws (which sample uniformly over
    500-599) is possible and harmless here since these AUC numbers are
    already labelled PROVISIONAL (pre-M1 synthetic-innovation features)."""
    runs = []
    for fam in ("clean",) + FAMILIES:
        for i in range(n_per_family):
            runs.append(generate_run(seed_base + i, fam, duration_s=duration_s))
    return runs
