"""D-067 change (0): kappa_R = 60 (D-061) is the single source of truth. INTENDED behaviour, written
before the implementation (remove xfail when landed)."""
from __future__ import annotations

import inspect

import pytest




def test_single_source_is_60():
    from fedqpnt.node.methods import DEFAULT_KAPPA_R
    assert DEFAULT_KAPPA_R == 60.0


def test_status_stamp():
    from fedqpnt.eval import scenarios as SC
    assert SC.KAPPA_R_STATUS == "D-061_kappa_R=60"


def test_eskf_raw_default_unchanged():
    from fedqpnt.fusion.eskf import ESKFConfig
    assert ESKFConfig().kappa_R == 1.0


def test_runner_agent_and_methods_paths_resolve_60():
    from fedqpnt.node.agent import AgentConfig
    from fedqpnt.node.methods import make_agent_config
    from fedqpnt.node.runner import RunSpec
    assert RunSpec(name="x", master_seed=0, method="fixed_trust").kappa_R == 60.0
    assert AgentConfig().kappa_R == 60.0
    assert make_agent_config("fixed_trust").kappa_R == 60.0


def test_campaign_paths_resolve_60():
    from fedqpnt.eval import campaign
    for fn in (campaign.build_spec_dict, campaign.generate_tasks, campaign.run_campaign):
        assert inspect.signature(fn).parameters["kappa_R"].default == 60.0, fn.__name__


def test_fleet_paths_resolve_60():
    from fedqpnt.eval import fleet_adapter
    from fedqpnt.fleet.node_runner import FleetNodeSpec
    from fedqpnt.fleet.orchestrator import FleetScenarioConfig
    assert FleetNodeSpec.__dataclass_fields__["kappa_R"].default == 60.0
    assert FleetScenarioConfig.__dataclass_fields__["kappa_R"].default == 60.0
    for name in ("build_fleet_scenario_config", "run_fleet_task"):
        fn = getattr(fleet_adapter, name)
        assert inspect.signature(fn).parameters["kappa_R"].default == 60.0, name


def test_dataset_builder_uses_default():
    src = open("fedqpnt/training/build_supervised_dataset.py", encoding="utf8").read()
    assert "kappa_R=40.0" not in src
