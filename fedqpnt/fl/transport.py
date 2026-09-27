"""SS8 Transport abstraction (multiprocessing spawn + mp.Queue by default,
so a localhost-socket transport can be swapped in later) + the message types
of SS8/SS4.4 + the SS4.4 leakage guard on ``ModelUpdate``.
"""
from __future__ import annotations

import multiprocessing as mp
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


# --------------------------------------------------------------------------
# Message types (SS8). ModelUpdate / GlobalModel live in fedqpnt.core.types
# (Master-owned contract); these four are FL-protocol-local control messages.
# --------------------------------------------------------------------------
@dataclass
class NoUpdate:
    node_id: str
    round_idx: int
    reason: str = "insufficient_samples"   # e.g. < 64 labelled samples (SS4.2)


@dataclass
class Lost:
    node_id: str
    round_idx: int
    direction: str = "up"   # "up" | "down"


@dataclass
class Failed:
    node_id: str
    round_idx: int


@dataclass
class RoundSkipped:
    round_idx: int
    n_live: int
    n_fresh: int


# --------------------------------------------------------------------------
# SS4.4 leakage guard: an update's params must match the detector's parameter
# names/shapes exactly, and metrics must be scalars only.
# --------------------------------------------------------------------------
class LeakageGuardError(ValueError):
    pass


def enforce_leakage_guard(params: dict, reference_shapes: dict, metrics: dict) -> None:
    """Raises ``LeakageGuardError`` if ``params``/``metrics`` smuggle anything
    beyond the SS4.1 contract: model weight arrays with the exact reference
    names/shapes, plus (optionally) ``norm_mu``/``norm_sd``/``norm_count``,
    and metrics that are plain scalars (no arrays, no nested structures)."""
    allowed_extra = {"norm_mu", "norm_sd", "norm_count"}
    for name, arr in params.items():
        if name in allowed_extra:
            continue
        if name not in reference_shapes:
            raise LeakageGuardError(f"ModelUpdate.params has unknown key {name!r} (not a detector parameter)")
        a = np.asarray(arr)
        if a.shape != tuple(reference_shapes[name]):
            raise LeakageGuardError(
                f"ModelUpdate.params[{name!r}] shape {a.shape} != detector shape {tuple(reference_shapes[name])}")
    for name in reference_shapes:
        if name not in params:
            raise LeakageGuardError(f"ModelUpdate.params is missing required key {name!r}")
    for k, v in metrics.items():
        if isinstance(v, (dict, list, tuple, np.ndarray)):
            raise LeakageGuardError(f"ModelUpdate.metrics[{k!r}] is not a scalar (got {type(v)})")
        if not isinstance(v, (int, float, bool)) and v is not None:
            try:
                float(v)
            except (TypeError, ValueError) as e:
                raise LeakageGuardError(f"ModelUpdate.metrics[{k!r}] is not a scalar: {v!r}") from e


# --------------------------------------------------------------------------
# Transport abstraction
# --------------------------------------------------------------------------
class Transport(ABC):
    @abstractmethod
    def send(self, inbox_id: str, msg) -> None: ...

    @abstractmethod
    def recv(self, inbox_id: str, timeout: float | None = None): ...


class MpQueueTransport(Transport):
    """Default transport (SS8): one ``mp.Queue`` per inbox, built from a
    ``spawn`` context so it is portable on Windows and picklable to child
    processes. Swapping in a socket transport later means implementing this
    same two-method interface."""

    def __init__(self, inbox_ids: list[str], ctx: "mp.context.BaseContext | None" = None):
        self._ctx = ctx or mp.get_context("spawn")
        self._queues: dict[str, "mp.queues.Queue"] = {i: self._ctx.Queue() for i in inbox_ids}

    def queue(self, inbox_id: str):
        return self._queues[inbox_id]

    def send(self, inbox_id: str, msg) -> None:
        self._queues[inbox_id].put(msg)

    def recv(self, inbox_id: str, timeout: float | None = None):
        return self._queues[inbox_id].get(timeout=timeout)
