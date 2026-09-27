"""WP-8.1: one short end-to-end run per method, executed as a REAL
subprocess (not an in-process call), per the WP-8.1 brief's runtime
requirement (ARCHITECTURE.md section 8: runs execute as real processes)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from fedqpnt.node.methods import METHOD_NAMES

ROOT = Path(__file__).resolve().parent.parent
DETECTOR_WEIGHTS = ROOT / "results" / "m1" / "detector_weights.npz"


def _run_subprocess(method: str, seed: int = 500, duration_s: float = 20.0) -> dict:
    spec = dict(
        name=f"e2e_{method}", master_seed=seed, method=method, duration_s=duration_s,
        dt=0.01, platform="ground", world="flat", imu_grade="industrial_mems",
        quantum_grade="field", gnss_rate_hz=1.0, hold_s=5.0, heading_noise_deg=2.0,
        attack=None, kappa_R=40.0, kappa_Q=1.0,
        detector_weights_path=str(DETECTOR_WEIGHTS) if DETECTOR_WEIGHTS.exists() else None,
        record=False, record_root="runs", node_id="node0",
    )
    proc = subprocess.run(
        [sys.executable, "-m", "fedqpnt.node.runner", json.dumps(spec)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, f"{method} subprocess failed:\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}"
    lines = [l for l in proc.stdout.strip().splitlines() if l.strip()]
    return json.loads(lines[-1])


@pytest.mark.parametrize("method", METHOD_NAMES)
def test_one_short_run_per_method_via_subprocess(method):
    result = _run_subprocess(method)
    assert result["method"] == method
    assert result["n_ticks"] > 0
    # 20 s at 100 Hz with a 5 s hold => ~1500 post-init ticks
    assert result["n_ticks"] > 1000
    assert result["wall_s"] > 0.0
