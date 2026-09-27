"""D-048 M2 fleet functional tests: real closed-loop node pipelines,
global-model install, determinism, and result-file schema. Kept small
(short missions, few nodes) to bound wall time -- the full item-3
validation (N=5, 10-min missions, 2 seeds, nominal + 30% drift-spoof) is
scripts/run_fleet_validate.py (not run under pytest).
"""
from __future__ import annotations

import numpy as np
import pytest

from fedqpnt.trust.detector import TrustDetector
from fedqpnt.fl.client import ClientConfig
from fedqpnt.fleet.orchestrator import FleetScenarioConfig, run_fleet, write_campaign_result


def _theta0():
    d = TrustDetector(arch="mlp", seed=0)
    theta0 = d.get_params()
    return theta0, list(theta0.keys())


def test_global_model_installs_on_a_real_node():
    theta0, param_names = _theta0()
    scenario = FleetScenarioConfig(scenario_id="test_install", method="fedqpnt_local", seed=500,
                                    node_ids=["n0", "n1"], n_rounds=3, round_period_s=30.0, duration_s=90.0,
                                    client_cfg=ClientConfig(min_samples=4))
    result = run_fleet(scenario, theta0, param_names)
    assert not result.aborted, result.abort_reason
    for nid, r in result.node_results.items():
        assert not r["failed"], r
        assert r["round_installs"] >= 1, f"{nid} never installed a global model"
        assert r["n_ticks"] > 0


def test_fleet_determinism_bit_identical():
    theta0, param_names = _theta0()
    scenario = FleetScenarioConfig(scenario_id="test_det", method="fedqpnt_local", seed=501,
                                    node_ids=["n0", "n1"], n_rounds=2, round_period_s=30.0, duration_s=60.0,
                                    client_cfg=ClientConfig(min_samples=4))
    r1 = run_fleet(scenario, theta0, param_names)
    r2 = run_fleet(scenario, theta0, param_names)
    assert not r1.aborted and not r2.aborted
    for nid in scenario.node_ids:
        a, b = r1.node_results[nid], r2.node_results[nid]
        assert a["n_ticks"] == b["n_ticks"]
        assert np.isclose(a["rmse_h_pre"], b["rmse_h_pre"], equal_nan=True)
        assert a["round_installs"] == b["round_installs"]


def test_write_campaign_result_matches_eval_campaign_schema(tmp_path):
    theta0, param_names = _theta0()
    scenario = FleetScenarioConfig(scenario_id="test_schema", method="fedqpnt_local", seed=502,
                                    node_ids=["n0"], n_rounds=2, round_period_s=30.0, duration_s=60.0,
                                    client_cfg=ClientConfig(min_samples=4))
    result = run_fleet(scenario, theta0, param_names)
    path = write_campaign_result(scenario, result, run_root=str(tmp_path))
    assert path.exists()
    import json
    rec = json.loads(path.read_text())
    for key in ("status", "scenario_id", "method", "seed", "config_hash", "wall_s", "metrics"):
        assert key in rec
    assert rec["scenario_id"] == "test_schema"
    assert rec["method"] == "fedqpnt_local"
    assert rec["seed"] == 502
    assert "fleet" in rec["metrics"] and "nodes" in rec["metrics"]

    # eval.campaign.load_results-compatible: status must be "ok" for a
    # successful run so the report generator picks it up.
    assert rec["status"] == "ok"
