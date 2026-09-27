"""FedQPNT component interfaces (Master-owned, contract v0.2).

The simulation is a stepped, closed loop driven by one global clock with base
tick ``dt`` (default 0.01 s). Every stateful component is stepped once per tick
and returns ``None`` when it has no output at that tick (this is how sampling
rate mismatch is represented).

Every component:
  * takes its randomness ONLY from the ``np.random.Generator`` it is given
    (see ``fedqpnt.core.seeding``),
  * exposes ``config() -> dict`` with every parameter needed to reproduce it
    (logged by the run recorder).
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np

from .types import (
    AttackLabel, GlobalModel, GnssEpoch, GnssFix, ImuSample, Innovation, ModelUpdate,
    NavSolution, QuantumSample, TrustState, TruthState, TruthTrajectory,
)


@runtime_checkable
class Configurable(Protocol):
    def config(self) -> dict[str, Any]: ...


class TrajectoryGenerator(Configurable, Protocol):
    def generate(self, duration_s: float, dt: float, rng: np.random.Generator) -> TruthTrajectory: ...


class ImuModel(Configurable, Protocol):
    rate_hz: float
    def step(self, truth: TruthState, rng: np.random.Generator) -> ImuSample | None: ...


class QuantumSensorModel(Configurable, Protocol):
    rate_hz: float  # nominal output rate = 1 / cycle_time
    def step(self, truth: TruthState, rng: np.random.Generator) -> QuantumSample | None: ...


class GnssSignalModel(Configurable, Protocol):
    """Produces clean raw observables (constellation, atmosphere, multipath, clock)."""
    rate_hz: float
    def step(self, truth: TruthState, rng: np.random.Generator) -> GnssEpoch | None: ...


class GnssAttack(Configurable, Protocol):
    """Transforms a clean epoch into an attacked epoch. Attacks are chainable."""
    def apply(self, epoch: GnssEpoch, truth: TruthState, rng: np.random.Generator) -> GnssEpoch: ...
    def label(self, t: float) -> AttackLabel: ...


class GnssReceiver(Configurable, Protocol):
    """Tracking-lock logic + PVT solver (weighted least squares + RAIM stat)."""
    def solve(self, epoch: GnssEpoch) -> GnssFix: ...


class TrustEngine(Configurable, Protocol):
    """v0.2 (C-1): consumes the filter's pre-correction innovations."""
    def update(self, t: float, fix: GnssFix | None, imu: ImuSample | None,
               quantum: QuantumSample | None, nav_prior: NavSolution | None,
               innovations: list[Innovation]) -> TrustState: ...


class FusionFilter(Configurable, Protocol):
    """v0.2 (C-1): per tick the Agent calls propagate → innovations →
    TrustEngine.update → correct. ``step`` is a convenience wrapper."""
    def propagate(self, t: float, imu: ImuSample | None) -> None: ...
    def innovations(self, t: float, fix: GnssFix | None,
                    quantum: QuantumSample | None) -> list[Innovation]: ...
    def correct(self, t: float, innovations: list[Innovation], trust: TrustState) -> NavSolution: ...
    def step(self, t: float, imu: ImuSample | None, quantum: QuantumSample | None,
             fix: GnssFix | None, trust: TrustState) -> NavSolution: ...


class FederatedClient(Configurable, Protocol):
    node_id: str
    def local_update(self, global_model: GlobalModel) -> ModelUpdate: ...


class Aggregator(Configurable, Protocol):
    def aggregate(self, global_model: GlobalModel, updates: list[ModelUpdate]) -> GlobalModel: ...
