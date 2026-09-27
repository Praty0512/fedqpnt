"""Run configuration (WP-1.2, ARCHITECTURE.md section 11.4 / section 9 defaults).

``RunConfig`` and its nested dataclasses are the single JSON-serialisable
description of one simulation run. ``config_hash`` is the canonical
fingerprint logged by the recorder and used to freeze tuning (ARCHITECTURE.md
section 7.6).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

from fedqpnt.core.types import CONTRACT_VERSION

try:
    import yaml as _yaml
except ImportError:  # pragma: no cover - PyYAML is present in this env, but stay defensive
    _yaml = None


@dataclass
class AttackSpec:
    kind: str
    t_start: float
    t_end: float | None
    severity: float = 0.0
    params: dict = field(default_factory=dict)


@dataclass
class NodeConfig:
    node_id: str
    platform: str = "ground"                    # "ground" | "uav"
    trajectory: dict = field(default_factory=dict)
    imu: dict = field(default_factory=lambda: {"grade": "tactical"})
    quantum: dict = field(default_factory=lambda: {"enabled": True, "cycle_time": 1.0})
    gnss: dict = field(default_factory=lambda: {"rate_hz": 1.0})
    attacks: list = field(default_factory=list)  # list[AttackSpec]
    join_time_s: float = 0.0
    fail_time_s: float | None = None
    byzantine: dict | None = None


@dataclass
class FLConfig:
    enabled: bool = True
    round_period_s: float = 60.0
    local_epochs: int = 2
    lr: float = 0.05
    batch: int = 64
    prox_mu: float = 0.01
    aggregator: str = "trim_nb_r"
    trim_beta: float = 0.2
    clip_c: float = 2.0
    rep_rho: float = 0.8
    rep_q: float = 0.2
    labels: str = "pseudo"
    quorum_frac: float = 0.5


@dataclass
class CommsConfig:
    delay_median_s: float = 0.2
    delay_sigma: float = 0.5
    bandwidth_bps: float = 1e6
    d_max_s: float = 5.0
    p_gb: float = 0.02
    p_bg: float = 0.3
    loss_g: float = 0.01
    loss_b: float = 0.9
    max_staleness: int = 3


@dataclass
class RunConfig:
    name: str
    master_seed: int
    duration_s: float
    dt: float = 0.01
    method: str = "fedqpnt"
    scenario: str = "S1"
    world: dict = field(default_factory=lambda: {"gravity": "flat"})
    nodes: list = field(default_factory=list)     # list[NodeConfig]
    fl: FLConfig = field(default_factory=FLConfig)
    comms: CommsConfig = field(default_factory=CommsConfig)
    fusion: dict = field(default_factory=dict)
    trust: dict = field(default_factory=dict)
    eval: dict = field(default_factory=dict)
    contract_version: str = CONTRACT_VERSION

    # -- serialisation -----------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        return _tuples_to_lists(d)

    @classmethod
    def from_dict(cls, d: dict) -> "RunConfig":
        d = dict(d)  # shallow copy; do not mutate caller's dict
        known = {f.name for f in fields(cls)}
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"unknown RunConfig key(s): {sorted(unknown)}")

        nodes_raw = d.pop("nodes", [])
        nodes = [_node_from_dict(n) for n in nodes_raw]

        fl_raw = d.pop("fl", {})
        fl = _dataclass_from_dict(FLConfig, fl_raw)

        comms_raw = d.pop("comms", {})
        comms = _dataclass_from_dict(CommsConfig, comms_raw)

        kwargs = dict(d)
        kwargs["nodes"] = nodes
        kwargs["fl"] = fl
        kwargs["comms"] = comms
        return cls(**kwargs)

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "RunConfig":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(d)

    def to_yaml(self, path: str | Path) -> None:
        if _yaml is None:
            raise RuntimeError("PyYAML is not installed; JSON is the canonical format")
        Path(path).write_text(_yaml.safe_dump(self.to_dict(), sort_keys=True), encoding="utf-8")

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RunConfig":
        if _yaml is None:
            raise RuntimeError("PyYAML is not installed; JSON is the canonical format")
        d = _yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(d)

    def config_hash(self) -> str:
        """sha256(canonical_json)[:16]; ``name`` is EXCLUDED from the hash."""
        d = self.to_dict()
        d.pop("name", None)
        canonical = json.dumps(d, sort_keys=True, separators=(",", ":"),
                                allow_nan=False, default=_float_repr_default)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def validate(self) -> None:
        if self.dt <= 0:
            raise ValueError("dt must be > 0")
        if self.duration_s <= 0:
            raise ValueError("duration_s must be > 0")
        ids = [n.node_id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("node_ids must be unique")
        valid_platforms = {"ground", "uav"}
        for n in self.nodes:
            if n.platform not in valid_platforms:
                raise ValueError(f"node {n.node_id!r}: unknown platform {n.platform!r}")
            for a in n.attacks:
                if a.t_end is not None and not (a.t_start < a.t_end):
                    raise ValueError(f"node {n.node_id!r}: attack t_start must be < t_end")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _tuples_to_lists(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _tuples_to_lists(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_tuples_to_lists(v) for v in obj]
    return obj


def _float_repr_default(o: Any) -> Any:
    # json.dumps already renders floats via repr(); this is only a safety net
    # for any stray non-JSON-native object (should not normally trigger).
    if isinstance(o, (set,)):
        return sorted(o)
    raise TypeError(f"not JSON serialisable: {type(o)!r}")


def _dataclass_from_dict(cls, d: dict):
    d = dict(d or {})
    known = {f.name for f in fields(cls)}
    unknown = set(d) - known
    if unknown:
        raise ValueError(f"unknown {cls.__name__} key(s): {sorted(unknown)}")
    return cls(**d)


def _node_from_dict(d: dict) -> NodeConfig:
    d = dict(d)
    known = {f.name for f in fields(NodeConfig)}
    unknown = set(d) - known
    if unknown:
        raise ValueError(f"unknown NodeConfig key(s): {sorted(unknown)}")
    attacks_raw = d.pop("attacks", [])
    attacks = [_dataclass_from_dict(AttackSpec, a) for a in attacks_raw]
    d["attacks"] = attacks
    return NodeConfig(**d)
