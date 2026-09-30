"""D-068 P1-P3: lowest-level seed gate, runner outputs, offset channel, attacks schedule, noise_scale."""
import numpy as np
import pytest

from fedqpnt.core import seed_gate as CG
from fedqpnt.eval import seed_gate as EG
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.runner import RunSpec, run_single


def test_seed_gate_single_source_of_truth():
    assert EG.enforce_seed is CG.enforce_seed and EG.classify_seed is CG.classify_seed


@pytest.mark.parametrize("seed,final", [(10001, False), (10001, True), (25000, True), (-3, False)])
def test_run_single_refuses_gated_seeds(seed, final, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)          # no results/GATE_D047.json here: gate is closed
    with pytest.raises(CG.SeedGateError):
        run_single(RunSpec(name="g", master_seed=seed, method="fedqpnt_local", duration_s=40.0, final=final))


def test_run_fleet_refuses_test_seed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from fedqpnt.fleet.orchestrator import FleetScenarioConfig, run_fleet
    cfg = FleetScenarioConfig(scenario_id="S5", seed=10003, node_ids=["node0"])
    with pytest.raises(CG.SeedGateError):
        run_fleet(cfg, {}, [])
    cfg = FleetScenarioConfig(scenario_id="S5", seed=10003, node_ids=["node0"], final=True)
    with pytest.raises(CG.SeedGateError):        # final alone is not enough: gate file closed
        run_fleet(cfg, {}, [])


def test_build_spec_final_only_when_requested():
    from fedqpnt.eval import campaign as CP, scenarios as SC
    assert "final" not in CP.build_spec_dict(SC.get("S1"), "fedqpnt_local", 500)
    assert CP.build_spec_dict(SC.get("S1"), "fedqpnt_local", 500, final=True)["final"] is True
    RunSpec(**CP.build_spec_dict(SC.get("S10-r2-c0.73"), "fedqpnt_local", 500))     # spec fields accepted
    RunSpec(**CP.build_spec_dict(SC.get("S4"), "fedqpnt_local", 500))
    RunSpec(**CP.build_spec_dict(SC.get("S11"), "fedqpnt_local", 500))


def test_env_injected_offset_channel_truth_side():
    atk = dict(kind="abrupt_spoof", onset_s=32.0, duration_s=6.0, severity=0.5)
    env = NodeEnvironment(EnvConfig(attacks=[atk], hold_s=30.0), seed=500, dt=0.01, duration_s=15.0)
    ticks = [env.tick(k) for k in range(len(env))]
    ep = [t for t in ticks if t.gnss_epoch is not None]
    assert all(np.isnan(t.injected_offset_m) for t in ticks if t.gnss_epoch is None)
    off = np.array([t.injected_offset_m for t in ep])
    tt = np.array([t.t for t in ep])
    assert np.all(off[tt < 32.0] == 0.0)
    assert np.all(off[(tt > 33.0) & (tt < 37.0)] > 0.0)
    # never visible to the agent
    assert not hasattr(ep[0].gnss_epoch, "injected_offset_m") and "injected_offset_m" not in ep[0].gnss_epoch.meta


def test_run_single_new_outputs_and_two_segment_schedule():
    a1 = dict(kind="abrupt_spoof", onset_s=40.0, duration_s=6.0, severity=0.5)
    a2 = dict(kind="abrupt_spoof", onset_s=55.0, duration_s=6.0, severity=0.5)
    r = run_single(RunSpec(name="n", master_seed=500, method="fedqpnt_local", duration_s=70.0, attack=a1,
                           attacks=[a1, a2]))
    for k in ("detected_on", "window_s", "t_det", "t_on_s", "t_off_s", "offset_t_s", "offset_m",
              "anees_pos_pre_full", "anees_pos_all_full", "frac_e_le_3sigma_att", "p_spd_finite"):
        assert k in r, k
    assert isinstance(r["detected_on"], bool) and len(r["offset_t_s"]) == len(r["offset_m"]) > 10
    off, t = np.array(r["offset_m"]), np.array(r["offset_t_s"])
    assert np.any(off[(t >= 41) & (t < 46)] > 0) and np.any(off[(t >= 56) & (t < 61)] > 0)   # both segments
    assert np.all(off[(t > 48) & (t < 54)] == 0.0)                                            # gap between them
    assert r["t_on_s"] == pytest.approx(40.0, abs=0.2) and r["t_off_s"] > 60.0
    assert r["p_spd_finite"] == 1.0
    # single-attack spec: 'attacks' schedule ignored when None
    r1 = run_single(RunSpec(name="n", master_seed=500, method="fedqpnt_local", duration_s=70.0, attack=a1))
    assert r1["t_off_s"] < 50.0


def test_noise_scale_environment_only_and_default_untouched():
    def imu_std(ns):
        env = NodeEnvironment(EnvConfig(noise_scale=ns), seed=7, dt=0.01, duration_s=20.0)
        f = np.array([env.tick(k).imu.f_b for k in range(2000) if env.tick(k).imu is not None])
        return float(np.std(np.diff(f, axis=0)))
    base, scaled = imu_std(None), imu_std({"imu": 10.0})
    assert scaled > 5.0 * base
    # the filter is NOT told: imu.config() is identical with and without scaling
    e0 = NodeEnvironment(EnvConfig(), seed=7, dt=0.01, duration_s=20.0)
    e1 = NodeEnvironment(EnvConfig(noise_scale={"imu": 10.0}), seed=7, dt=0.01, duration_s=20.0)
    assert e0.imu.config()["accel_noise_SI"] == e1.imu.config()["accel_noise_SI"]

    def pr(ns):
        env = NodeEnvironment(EnvConfig(noise_scale=ns), seed=7, dt=0.01, duration_s=40.0)
        return [o.pseudorange for k in range(len(env)) if (e := env.tick(k).gnss_epoch) is not None for o in e.obs]
    p0, p5 = pr(None), pr({"gnss": 5.0})
    assert len(p0) == len(p5) and np.std(np.array(p5) - np.array(p0)) > 2.0     # extra ~ sqrt(24) x sigma_UERE
    assert pr(None) == p0                                     # deterministic and default path unchanged
