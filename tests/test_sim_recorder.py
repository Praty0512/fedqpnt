"""Tests for fedqpnt.sim.recorder (WP-1.2, ARCHITECTURE.md section 11.5)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from fedqpnt.sim.config import RunConfig
from fedqpnt.sim.recorder import RunRecorder, code_version, load_run, save_trajectory
from fedqpnt.sim.trajectory import GroundVehicleTrajectory


def _config(name="rec_test") -> RunConfig:
    return RunConfig(name=name, master_seed=1, duration_s=10.0)


def test_log_and_load_round_trip(tmp_path: Path):
    cfg = _config("round_trip")
    rec = RunRecorder(tmp_path, cfg)
    rng = np.random.default_rng(0)

    scalars, vec3s, mat33s = [], [], []
    for i in range(25_000):
        t = i * 0.01
        s = float(rng.normal())
        v = rng.normal(size=3)
        m = rng.normal(size=(3, 3))
        scalars.append(s); vec3s.append(v); mat33s.append(m)
        rec.log("mystream", t, scalar=s, vec3=v, mat33=m)

    for i in range(10):
        rec.log_event(float(i), "test_event", value=i, note="hello")

    rec.close(status="ok")

    data = load_run(rec.run_dir)
    assert data.config == cfg
    assert data.manifest["code_version"] == code_version()
    assert data.manifest["status"] == "ok"
    assert data.manifest["config_hash"] == cfg.config_hash()

    s = data.series["mystream"]
    assert np.array_equal(s["scalar"], np.array(scalars))
    assert np.array_equal(s["vec3"], np.array(vec3s))
    assert np.array_equal(s["mat33"], np.array(mat33s))
    assert np.array_equal(s["t"], np.arange(25_000) * 0.01)

    assert len(data.events) == 10
    for i, ev in enumerate(data.events):
        assert ev["kind"] == "test_event"
        assert ev["value"] == i
        assert ev["note"] == "hello"


def test_context_manager_error_status(tmp_path: Path):
    cfg = _config("error_status")
    run_dir_holder = {}
    with pytest.raises(RuntimeError):
        with RunRecorder(tmp_path, cfg) as rec:
            run_dir_holder["dir"] = rec.run_dir
            rec.log("s", 0.0, x=1.0)
            raise RuntimeError("boom")
    data = load_run(run_dir_holder["dir"])
    assert data.manifest["status"].startswith("error")
    assert "RuntimeError" in data.manifest["status"]


def test_context_manager_ok_status(tmp_path: Path):
    cfg = _config("ok_status")
    with RunRecorder(tmp_path, cfg) as rec:
        rec.log("s", 0.0, x=1.0)
    data = load_run(rec.run_dir)
    assert data.manifest["status"] == "ok"


def test_overwrite_refusal(tmp_path: Path):
    cfg = _config("overwrite_test")
    rec = RunRecorder(tmp_path, cfg, run_id="fixed_run_id")
    rec.close()
    with pytest.raises(FileExistsError):
        RunRecorder(tmp_path, cfg, run_id="fixed_run_id")


def test_save_trajectory_round_trip(tmp_path: Path):
    cfg = _config("traj_test")
    rec = RunRecorder(tmp_path, cfg)
    rng = np.random.default_rng(5)
    traj = GroundVehicleTrajectory().generate(30.0, 0.01, rng)
    save_trajectory(rec, traj, stream="truth")
    rec.close()

    data = load_run(rec.run_dir)
    s = data.series["truth"]
    assert np.array_equal(s["t"], traj.t)
    assert np.array_equal(s["pos"], traj.pos)
    assert np.array_equal(s["vel"], traj.vel)
    assert np.array_equal(s["acc"], traj.acc)
    assert np.array_equal(s["att"], traj.att)
    assert np.array_equal(s["omega_b"], traj.omega_b)
    assert np.array_equal(s["f_b"], traj.f_b)


def test_code_version_deterministic_and_changes():
    v1 = code_version()
    v2 = code_version()
    assert v1 == v2
    assert isinstance(v1, str) and len(v1) == 16
