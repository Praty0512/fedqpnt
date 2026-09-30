"""D-074: the trust-side assumed CAI cycle time follows the configured quantum sensor grade."""
from __future__ import annotations

import pytest

from fedqpnt.node.methods import default_quantum_cycle_time_s, make_agent_config
from fedqpnt.sensors.quantum import JARLAUD_CYCLE_TIME_S


def _tc(cfg):
    return cfg.trust.quantum_cycle_time_s


def test_grade_defaults_from_sensor_preset():
    assert _tc(make_agent_config("fedqpnt_local", quantum_grade="field")) == pytest.approx(1.548)
    assert _tc(make_agent_config("fedqpnt_local", quantum_grade="field")) == pytest.approx(JARLAUD_CYCLE_TIME_S)
    assert _tc(make_agent_config("fedqpnt_local", quantum_grade="lab")) == pytest.approx(1.0)
    assert _tc(make_agent_config("fedqpnt_local", quantum_grade="near_future")) == pytest.approx(0.1)


def test_no_grade_keeps_legacy_1s_and_explicit_override_wins():
    assert _tc(make_agent_config("fedqpnt_local")) == 1.0
    assert _tc(make_agent_config("fedqpnt_local", quantum_grade="field", quantum_cycle_time_s=2.5)) == 2.5
    assert default_quantum_cycle_time_s(None) == 1.0


def test_runner_default_agent_with_field_grade_uses_1_548(monkeypatch):
    import fedqpnt.node.runner as R
    seen = {}

    def fake(method, **kw):
        seen.update(kw)
        raise RuntimeError("stop")
    monkeypatch.setattr(R, "make_agent_config", fake)
    with pytest.raises(RuntimeError):
        R.run_single(R.RunSpec(name="x", master_seed=500, method="fedqpnt_local", duration_s=40.0, hold_s=5.0,
                               quantum_grade="field"))
    assert seen["quantum_grade"] == "field" and "quantum_cycle_time_s" not in seen
    assert _tc(make_agent_config("fedqpnt_local", **seen)) == pytest.approx(1.548)
