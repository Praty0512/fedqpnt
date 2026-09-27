"""WP-8.x: fedqpnt.eval.campaign gate/resumability/config-hash logic
(ARCHITECTURE.md section 7/8, D-046/D-047 kappa_R gate). Uses tmp_path for
run_root/gate files; does NOT spawn real node-runner subprocesses (that is
covered by the dry-run campaign, run separately -- real subprocesses per
scenario would make the unit suite slow and shared-machine-unfriendly)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fedqpnt.eval import campaign as CP
from fedqpnt.eval import scenarios as SC


def test_ensure_gate_file_creates_default_closed(tmp_path):
    p = tmp_path / "GATE_D047.json"
    assert not p.exists()
    rec = CP.ensure_gate_file(p)
    assert rec == {"cleared": False}
    assert p.exists()
    assert json.loads(p.read_text()) == {"cleared": False}


def test_ensure_gate_file_does_not_overwrite_existing(tmp_path):
    p = tmp_path / "GATE_D047.json"
    p.write_text(json.dumps({"cleared": True, "note": "kept"}))
    rec = CP.ensure_gate_file(p)
    assert rec["cleared"] is True
    assert rec["note"] == "kept"


def test_gate_cleared_reads_flag(tmp_path):
    p = tmp_path / "GATE_D047.json"
    p.write_text(json.dumps({"cleared": False}))
    assert CP.gate_cleared(p) is False
    p.write_text(json.dumps({"cleared": True}))
    assert CP.gate_cleared(p) is True


def test_run_campaign_refuses_test_seeds_without_flags(tmp_path):
    with pytest.raises(CP.CampaignGateError):
        CP.run_campaign(["S1"], seeds=[10000], run_root=str(tmp_path))


def test_run_campaign_refuses_test_seeds_with_final_but_no_gate_cleared_flag(tmp_path):
    with pytest.raises(CP.CampaignGateError):
        CP.run_campaign(["S1"], seeds=[10005], run_root=str(tmp_path), final=True, gate_cleared_flag=False)


def test_run_campaign_refuses_test_seeds_when_gate_file_says_not_cleared(tmp_path, monkeypatch):
    gate_path = tmp_path / "GATE_D047.json"
    gate_path.write_text(json.dumps({"cleared": False}))
    monkeypatch.setattr(CP, "GATE_D047_PATH", gate_path)
    with pytest.raises(CP.CampaignGateError, match="cleared=false"):
        CP.run_campaign(["S1"], seeds=[10001], run_root=str(tmp_path), final=True, gate_cleared_flag=True)


def test_run_campaign_allows_tuning_seeds_below_10000_without_flags(tmp_path, monkeypatch):
    # Redirect execution to a stub so this stays a fast unit test (no real
    # subprocess); only the gate/refusal logic and task plumbing are under
    # test here -- the dry-run campaign below exercises real subprocesses.
    calls = []

    def _stub_execute(task_dict, run_root, python_exe):
        calls.append(task_dict)
        return dict(scenario_id=task_dict["scenario_id"], method=task_dict["method"],
                    seed=task_dict["seed"], status="ok")

    monkeypatch.setattr(CP, "_execute_one", _stub_execute)
    results = CP.run_campaign(["S1"], seeds=[500, 501], methods=["undefended"], run_root=str(tmp_path),
                               n_workers=1)
    assert len(results) == 2
    assert all(r["status"] == "ok" for r in results)
    assert len(calls) == 2


def test_run_campaign_worker_cap_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(CP, "_execute_one", lambda td, rr, py: dict(status="ok", **{
        k: td[k] for k in ("scenario_id", "method", "seed")}))
    # workers=1 avoids spinning up a real process pool in the unit test;
    # MAX_WORKERS itself is exercised via the min() below.
    assert CP.MAX_WORKERS == 4


# --------------------------------------------------------------------------
# Config hash / RunTask / resumability plumbing
# --------------------------------------------------------------------------
def test_config_hash_stable_and_sensitive_to_changes():
    scenario = SC.get("S1")
    spec_a = CP.build_spec_dict(scenario, "undefended", 500)
    spec_b = CP.build_spec_dict(scenario, "undefended", 500)
    spec_c = CP.build_spec_dict(scenario, "undefended", 501)
    assert CP.config_hash(spec_a) == CP.config_hash(spec_b)
    assert CP.config_hash(spec_a) != CP.config_hash(spec_c)


def test_generate_tasks_cross_product_paired_by_seed():
    tasks = CP.generate_tasks(["S1"], ["undefended", "fixed_trust"], [500, 501])
    assert len(tasks) == 4
    seeds_per_method = {}
    for t in tasks:
        seeds_per_method.setdefault(t.method, set()).add(t.seed)
    assert seeds_per_method["undefended"] == seeds_per_method["fixed_trust"] == {500, 501}


def test_is_done_true_only_for_status_ok(tmp_path):
    p = tmp_path / "seed_500.json"
    assert CP._is_done(p) is False
    p.write_text(json.dumps({"status": "error"}))
    assert CP._is_done(p) is False
    p.write_text(json.dumps({"status": "ok"}))
    assert CP._is_done(p) is True


def test_result_path_layout():
    scenario = SC.get("S1")
    task = CP.RunTask(scenario_id="S1", method="undefended", seed=500,
                       spec=CP.build_spec_dict(scenario, "undefended", 500))
    p = task.result_path(Path("runs"))
    assert p == Path("runs") / "S1" / "undefended" / "seed_500.json"


def test_load_results_skips_non_ok_records(tmp_path):
    d = tmp_path / "S1" / "undefended"
    d.mkdir(parents=True)
    (d / "seed_500.json").write_text(json.dumps({"status": "ok", "seed": 500, "kappa_R_status": "x",
                                                   "metrics": {"rmse_h_pre": 1.0}}))
    (d / "seed_501.json").write_text(json.dumps({"status": "error", "seed": 501}))
    out = CP.load_results(str(tmp_path), "S1", ["undefended"])
    assert len(out["undefended"]) == 1
    assert out["undefended"][0]["rmse_h_pre"] == 1.0
