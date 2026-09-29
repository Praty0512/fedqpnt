"""D-068 seed gate: classification and enforcement."""
import json
import pytest

from fedqpnt.eval import seed_gate as SG
from fedqpnt.eval import campaign as CP


def test_classify_boundaries():
    assert SG.classify_seed(0) == SG.TUNING
    assert SG.classify_seed(9999) == SG.TUNING
    assert SG.classify_seed(10000) == SG.TEST
    assert SG.classify_seed(19999) == SG.TEST
    assert SG.classify_seed(20000) == SG.UNREGISTERED
    assert SG.classify_seed(99999) == SG.UNREGISTERED
    assert SG.classify_seed(100000) == SG.FLEET_DERIVED
    assert SG.classify_seed(100_000 + 560 * 100 + 10) == SG.FLEET_DERIVED
    assert SG.classify_seed(-1) == SG.INVALID


def test_tuning_and_fleet_derived_pass(tmp_path):
    g = tmp_path / "g.json"
    assert SG.enforce_seed(500, gate_path=g) == SG.TUNING
    assert SG.enforce_seed(100_000 + 50000, gate_path=g) == SG.FLEET_DERIVED


def test_test_seed_refused_while_gate_closed(tmp_path):
    g = tmp_path / "g.json"
    with pytest.raises(SG.SeedGateError):
        SG.enforce_seed(10000, final=True, gate_path=g)          # file missing = closed
    g.write_text(json.dumps({"cleared": False}))
    with pytest.raises(SG.SeedGateError):
        SG.enforce_seed(10000, final=True, gate_path=g)
    with pytest.raises(SG.SeedGateError):
        SG.enforce_seed(10000, final=False, gate_path=g)
    g.write_text(json.dumps({"cleared": True}))
    assert SG.enforce_seed(10000, final=True, gate_path=g) == SG.TEST
    with pytest.raises(SG.SeedGateError):
        SG.enforce_seed(10000, final=False, gate_path=g)


def test_unregistered_always_refused(tmp_path):
    g = tmp_path / "g.json"
    g.write_text(json.dumps({"cleared": True}))
    for s in (20000, 50000, 99999, -5):
        with pytest.raises(SG.SeedGateError):
            SG.enforce_seed(s, final=True, gate_path=g)


def test_real_gate_file_is_closed():
    assert json.loads(open("results/GATE_D047.json").read())["cleared"] is False


def test_run_campaign_refuses_unregistered(tmp_path):
    with pytest.raises(CP.CampaignGateError):
        CP.run_campaign(["S1"], seeds=[25000], run_root=str(tmp_path), final=True, gate_cleared_flag=True)


def test_lowest_level_execute_refuses_test_seed(tmp_path):
    task = CP.generate_tasks(["S1"], ["fedqpnt_local"], [10001])[0]
    from dataclasses import asdict
    with pytest.raises(CP.CampaignGateError):
        CP._execute_one(asdict(task), str(tmp_path), "python")      # bypassing run_campaign
    with pytest.raises(CP.CampaignGateError):
        CP._execute_one_fleet(task, str(tmp_path))


def test_fleet_task_refuses_test_seed(tmp_path):
    from fedqpnt.eval import fleet_adapter as FA
    from fedqpnt.eval import scenarios as SC
    with pytest.raises(SG.SeedGateError):
        FA.run_fleet_task(SC.get("S5"), "fedqpnt_fl", 10002, run_root=str(tmp_path))


def test_no_registered_default_seed_in_test_range():
    for seed in range(0, 1000):
        for idx in range(0, 20):
            base = 100_000 + seed * 100 + idx * 10
            assert SG.classify_seed(base) == SG.FLEET_DERIVED


def test_s2_pd_zero_when_no_detection():
    """D-068: latency_on is censored (finite) on a miss; P_D must still be 0."""
    from fedqpnt.eval import scenarios as SC
    sc = SC.get("S2-med")
    crit = [c for c in sc.criteria if c.name == "detection_prob"][0]
    miss = dict(latency_on=300.0, detected_on=False)
    res = crit.check({"fedqpnt_local": [dict(miss), dict(miss)]})
    assert res["value"] == 0.0 and res["passed"] is False
    # fallback path for old records (no flag): latency == attack window -> miss
    res = crit.check({"fedqpnt_local": [dict(latency_on=300.0), dict(latency_on=12.0)]})
    assert res["value"] == 0.5
    res = crit.check({"fedqpnt_local": [dict(latency_on=12.0, detected_on=True)]})
    assert res["value"] == 1.0
