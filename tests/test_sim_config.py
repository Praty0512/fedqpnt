"""Tests for fedqpnt.sim.config (WP-1.2, ARCHITECTURE.md section 11.4)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from fedqpnt.sim.config import AttackSpec, CommsConfig, FLConfig, NodeConfig, RunConfig


def _sample_config() -> RunConfig:
    return RunConfig(
        name="unit_test_run",
        master_seed=12345,
        duration_s=600.0,
        nodes=[
            NodeConfig(node_id="n0", platform="ground",
                       attacks=[AttackSpec(kind="drift_spoof", t_start=100.0, t_end=200.0, severity=0.5)]),
            NodeConfig(node_id="n1", platform="uav", join_time_s=30.0),
        ],
    )


def test_round_trip_to_dict_from_dict():
    c = _sample_config()
    c2 = RunConfig.from_dict(c.to_dict())
    assert c2 == c


def test_round_trip_json_file(tmp_path: Path):
    c = _sample_config()
    p = tmp_path / "run.json"
    c.to_json(p)
    c2 = RunConfig.from_json(p)
    assert c2 == c


def test_hash_stable_hardcoded():
    c = RunConfig(name="hash_fixture", master_seed=7, duration_s=100.0)
    h = c.config_hash()
    # hard-coded expected value (computed once with this RunConfig schema, then frozen).
    # contract_version is part of the hash BY DESIGN: v0.2.0 -> 93c840ad1694850f;
    # v0.3.0 (D-022, Master) -> 13a07ebe9d321c02. Update only on a contract bump.
    assert h == "13a07ebe9d321c02"


def test_hash_stable_across_processes(tmp_path: Path):
    c = RunConfig(name="hash_fixture_proc", master_seed=7, duration_s=100.0)
    h_here = c.config_hash()
    cfg_path = tmp_path / "cfg.json"
    c.to_json(cfg_path)
    script = (
        "import sys; sys.path.insert(0, r'" + str(Path(__file__).resolve().parents[1]) + "');"
        "from fedqpnt.sim.config import RunConfig;"
        f"c = RunConfig.from_json(r'{cfg_path}');"
        "print(c.config_hash())"
    )
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    h_subprocess = out.stdout.strip()
    assert h_subprocess == h_here


def test_hash_excludes_name():
    c1 = RunConfig(name="a", master_seed=1, duration_s=10.0)
    c2 = RunConfig(name="b", master_seed=1, duration_s=10.0)
    assert c1.config_hash() == c2.config_hash()


def test_hash_changes_on_leaf_change():
    c1 = RunConfig(name="x", master_seed=1, duration_s=10.0)
    c2 = RunConfig(name="x", master_seed=1, duration_s=10.0)
    c2.fl.lr = 0.06
    assert c1.config_hash() != c2.config_hash()

    c3 = RunConfig(name="x", master_seed=1, duration_s=10.0)
    c3.comms.loss_b = 0.5
    assert c1.config_hash() != c3.config_hash()

    c4 = RunConfig(name="x", master_seed=1, duration_s=10.0,
                    nodes=[NodeConfig(node_id="n0")])
    c5 = RunConfig(name="x", master_seed=1, duration_s=10.0,
                    nodes=[NodeConfig(node_id="n0", join_time_s=1.0)])
    assert c4.config_hash() != c5.config_hash()


def test_unknown_key_raises():
    d = _sample_config().to_dict()
    d["bogus_field"] = 1
    with pytest.raises(ValueError):
        RunConfig.from_dict(d)

    d2 = _sample_config().to_dict()
    d2["fl"]["bogus"] = 1
    with pytest.raises(ValueError):
        RunConfig.from_dict(d2)

    d3 = _sample_config().to_dict()
    d3["nodes"][0]["bogus"] = 1
    with pytest.raises(ValueError):
        RunConfig.from_dict(d3)


def test_validate():
    c = _sample_config()
    c.validate()  # should not raise

    bad = RunConfig(name="bad", master_seed=1, duration_s=10.0, dt=0.0)
    with pytest.raises(ValueError):
        bad.validate()

    bad2 = RunConfig(name="bad2", master_seed=1, duration_s=-1.0)
    with pytest.raises(ValueError):
        bad2.validate()

    dup = RunConfig(name="dup", master_seed=1, duration_s=10.0,
                     nodes=[NodeConfig(node_id="n0"), NodeConfig(node_id="n0")])
    with pytest.raises(ValueError):
        dup.validate()

    bad_attack = RunConfig(name="bad_attack", master_seed=1, duration_s=10.0,
                            nodes=[NodeConfig(node_id="n0", attacks=[
                                AttackSpec(kind="jam", t_start=10.0, t_end=5.0)])])
    with pytest.raises(ValueError):
        bad_attack.validate()


def test_yaml_round_trip(tmp_path: Path):
    c = _sample_config()
    p = tmp_path / "run.yaml"
    c.to_yaml(p)
    c2 = RunConfig.from_yaml(p)
    assert c2 == c
