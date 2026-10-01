"""D-076: the epoch in which a PROBE FAILS must not apply the failed fix (w = w_min, shadow reported). A probe SUCCESS
epoch is unchanged. Both laws (position and clock)."""
from __future__ import annotations

import numpy as np
import pytest

from fedqpnt.core.types import GnssFix, Innovation
from fedqpnt.trust.trust_law import SensorTrustLaw, TrustEngineImpl, TrustLawConfig, make_method_config

CFG = TrustLawConfig()


def _to_probe(law):
    t = 0.0
    while law._core_v2.state != "PROBE" and t < 500:
        law.step(t, 1.0, nis_ok=False, features_nominal=False, nis_value=50.0, es_evidence=True)
        t += 1.0
    return t


def _run_probe(nis):
    law = SensorTrustLaw(cfg=CFG, law_mode="continuous", trust_law_version="v2")
    t = _to_probe(law)
    out = []
    for _ in range(int(CFG.T_probe)):
        w = law.step(t, 0.0, nis_ok=True, features_nominal=True, nis_value=nis, es_evidence=False)
        out.append((law._core_v2.state, w, law.probe_shadow))
        t += 1.0
    return law, out, t


def test_failing_probe_exit_epoch_reports_w_min_and_shadow():
    law, out, t = _run_probe(nis=500.0)
    state, w, shadow = out[-1]
    assert state == "DISTRUST"                       # the probe failed on the last epoch
    assert w == pytest.approx(CFG.w_min)             # NOT w_probe (0.3)
    assert shadow is True                            # the failed fix is not applied
    w2 = law.step(t, 0.0, nis_ok=True, features_nominal=True, nis_value=0.1, es_evidence=False)
    assert w2 == pytest.approx(CFG.w_min) and law.probe_shadow is False   # next epoch: ordinary pinned DISTRUST


def test_probe_epochs_before_exit_unchanged():
    _, out, _ = _run_probe(nis=500.0)
    for state, w, shadow in out[:-1]:
        assert state == "PROBE" and shadow is True


def test_success_epoch_unchanged():
    law, out, _ = _run_probe(nis=0.5)
    state, w, shadow = out[-1]
    assert state == "TRUST" and shadow is False
    assert w == pytest.approx(CFG.w_probe)           # admitted fix keeps the probe set-point (ramp starts here)


def _fix(t):
    return GnssFix(t=t, pos=np.zeros(3), vel=np.zeros(3), clk_bias=0.0, clk_drift=0.0, cov_pos=np.eye(3),
                   cov_vel=np.eye(3), residual_rms=0.5, num_sats=8, mean_cn0=45.0, std_cn0=1.0, agc_db=0.0,
                   valid=True, raim_stat=1.0, pdop=2.0)


def _shadow(nis):
    return Innovation(t=0.0, sensor="gnss_shadow", nu=np.zeros(6), S=np.eye(6), nis=float(nis), dof=6, accepted=True)


def _engine_at_last_probe_epoch(which):
    eng = TrustEngineImpl(make_method_config("fedqpnt"))
    eng._gnss_p = lambda raw: 0.0
    law = eng.gnss_law if which == "pos" else eng.clk_law
    core = law._core_v2
    core.state = "PROBE"
    core._probe_timer = CFG.T_probe - 1.0            # this update completes the probe
    core._probe_nis_sum = 1e4 * 9
    core._probe_nis_n = 9                             # mean NIS far above any bound -> FAIL
    core.w = CFG.w_probe
    core.core._initialised = True                     # not the first call (dt would be 0)
    core.core._last_t = -0.5
    core.core.p_bar = 0.0
    eng._last_valid_gnss_t = -0.5                     # normal 1 s cadence (no gap logic)
    return eng


@pytest.mark.parametrize("which", ["pos", "clk"])
def test_engine_failing_probe_epoch_weights_and_shadow(which):
    eng = _engine_at_last_probe_epoch(which)
    st = eng.update(0.5, _fix(0.5), None, None, None, [_shadow(1e4)])
    key, flag = ("gnss_pos", st.probe_shadow) if which == "pos" else ("gnss_clk", st.clk_probe_shadow)
    assert st.weights[key] == pytest.approx(CFG.w_min)
    assert flag is True


def test_clockkf_and_eskf_apply_nothing_at_failing_probe_epoch():
    from fedqpnt.fusion import ESKF
    from fedqpnt.fusion.clock import ClockKF, ClockKFConfig
    from fedqpnt.sensors.imu import ClassicalImu
    from fedqpnt.core.types import TrustState
    # clock: w_min < w_excl -> holdover, spoofed bias ignored
    kf = ClockKF(ClockKFConfig())
    kf.initialize(0.0, bias0=0.0, drift0=0.0)
    kf.step(1.0, _fix(1.0), w_gnss=1.0)
    bad = GnssFix(t=2.0, pos=np.zeros(3), vel=np.zeros(3), clk_bias=760.0, clk_drift=0.0, cov_pos=np.eye(3),
                  cov_vel=np.eye(3), residual_rms=0.5, num_sats=8, mean_cn0=45.0, std_cn0=1.0, agc_db=0.0,
                  valid=True, raim_stat=1.0)
    sol = kf.step(2.0, bad, w_gnss=CFG.w_min)
    assert abs(sol.bias_m) < 1.0
    # eskf: probe_shadow -> no GNSS update
    e = ESKF(ClassicalImu(grade="industrial_mems", rng=np.random.default_rng(0)).config())
    e.initialize_static(0.0, np.zeros(3), np.zeros(3))
    gf = GnssFix(t=0.0, pos=np.array([26.0, 0.0, 0.0]), vel=np.zeros(3), clk_bias=0.0, clk_drift=0.0,
                 cov_pos=np.diag([9.0, 9.0, 25.0]), cov_vel=np.diag([0.01] * 3), residual_rms=0.0, num_sats=6,
                 mean_cn0=45.0, std_cn0=1.0, agc_db=0.0, valid=True, raim_stat=0.0)
    inn = e.innovations(0.0, gf, None)
    e.correct(0.0, inn, TrustState(t=0.0, weights={"gnss": 0.02, "gnss_pos": CFG.w_min, "imu": 1.0, "quantum": 1.0},
                                   anomaly_scores={}, attack_detected=True, probe_shadow=True))
    assert np.allclose(e.p, 0.0)
