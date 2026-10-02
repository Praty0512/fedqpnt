"""D-078 (1): xsat E_s evidence is suppressed until the cross-satellite C/N0 correlation window is full."""
from __future__ import annotations

import numpy as np
import pytest

from fedqpnt.core.types import GnssFix, Innovation
from fedqpnt.trust.features import CORR_WINDOW_EPOCHS, GnssFeatureExtractor
from fedqpnt.trust.trust_law import TrustEngineImpl, make_method_config

N = 15


def _fix(t, cn0):
    prns = {i: 40.0 + i * 0.1 + cn0 for i in range(1, 8)}
    return GnssFix(t=t, pos=np.zeros(3), vel=np.zeros(3), clk_bias=0.0, clk_drift=0.0, cov_pos=np.eye(3),
                   cov_vel=np.eye(3), residual_rms=0.5, num_sats=7, mean_cn0=45.0, std_cn0=1.0, agc_db=0.0,
                   valid=True, raim_stat=1.0, cn0_per_sat=prns, elev_per_sat={i: 0.3 + 0.1 * i for i in prns})


def test_corr_window_full_flag():
    ex = GnssFeatureExtractor()
    for k in range(CORR_WINDOW_EPOCHS - 1):
        ex.step(_fix(float(k), 0.0), [])
        assert ex.corr_window_full is False
    ex.step(_fix(float(CORR_WINDOW_EPOCHS), 0.0), [])
    assert ex.corr_window_full is True


def test_xsat_event_suppressed_before_window_full_and_live_after():
    eng = TrustEngineImpl(make_method_config("fedqpnt"))
    raw = np.zeros(N)
    raw[13] = 100.0                                # far above any xsat threshold (untrained normalizer)
    fix = _fix(0.0, 0.0)
    inn = [Innovation(t=0.0, sensor="gnss_pos", nu=np.zeros(3), S=np.eye(3), nis=0.0, dof=3, accepted=True)]
    # window empty -> suppressed
    assert eng._physical_spoof_evidence(raw, fix, None, inn, split=True)[2] is False
    for k in range(CORR_WINDOW_EPOCHS):
        eng.extractor.step(_fix(float(k), 0.0), [])
    assert eng.extractor.corr_window_full
    assert eng._physical_spoof_evidence(raw, fix, None, inn, split=True)[2] is True


@pytest.mark.parametrize("grade", ["industrial_mems", "tactical"])
def test_seed_9604_clean_has_no_early_es_event(grade):
    """The clean seed that locked out in the decisive run (xsat false event at t=35, window=5): no E_s event at all
    during the first 60 s of the mission now."""
    from fedqpnt.node.agent import Agent
    from fedqpnt.node.environment import EnvConfig, NodeEnvironment
    from fedqpnt.node.methods import make_agent_config
    env = NodeEnvironment(EnvConfig(platform="ground", world="flat", imu_grade=grade, quantum_grade="field",
                                    gnss_rate_hz=1.0, hold_s=30.0, heading_noise_deg=2.0, attacks=[]),
                          seed=9604, node_id="node0", dt=0.01, duration_s=70.0)
    cfg = make_agent_config("fedqpnt_local", world="flat", imu_grade=grade, quantum_grade="field")
    ag = Agent(cfg, env.imu.config(), node_id="node0")
    events = []
    orig = ag.trust._physical_spoof_evidence

    def wrapped(*a, **k):
        r = orig(*a, **k)
        events.append((a[1].t, r))
        return r
    ag.trust._physical_spoof_evidence = wrapped
    hold, init = [], False
    for k in range(len(env)):
        tk = env.tick(k)
        if not init:
            if tk.t < env.hold_s:
                if tk.imu is not None:
                    hold.append(tk.imu.f_b)
                continue
            fx, fy, fz = np.mean(hold, axis=0)
            ag.initialize_static(tk.t, tk.truth.pos.copy(), np.array(
                [np.arctan2(fy, fz), np.arctan2(-fx, np.hypot(fy, fz)),
                 float(tk.truth.att[2]) + env.initial_heading_noise()]))
            init = True
            continue
        ag.step(tk.t, tk.imu, tk.quantum, tk.gnss_epoch)
    early = [(t, r) for t, r in events if t < 60.0 and (r[1] or r[2])]   # (pos, clk, xc)? -> r is bool tuple
    assert not early, early
