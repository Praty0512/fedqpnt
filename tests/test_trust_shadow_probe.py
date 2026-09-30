"""D-066 (ii): shadow probe + shadow-consistent reacquisition. INTENDED behaviour, written before
the implementation (fails until it lands).

Intended interface (may be adapted at implementation; the behaviour is the contract):
- SensorTrustLaw.step(..., nis_value=<joint gnss NIS vs coasting state, chi2_6 scale>,
  es_evidence=<clk/xsat/cn0 event only>, es_position=<position jump-test event>)
- SensorTrustLaw.probe_shadow (bool): True while in PROBE; the filter must then compute the GNSS
  innovation/NIS but apply NO update (no state or P change).
- PROBE exit: success iff mean NIS over the T_probe window <= chi2_6 99% bound (16.81) AND no
  clk/xsat/cn0 event in the window. es_position is SUPERSEDED during PROBE (ignored).
- Engine-level: on the first valid fix after a gap > T_gap, skip apply_reacquisition_cap when the
  first-fix NIS vs the coast is <= chi2_6 99% AND E_s is silent; otherwise keep the cap.
"""
from __future__ import annotations

import pytest
from scipy.stats import chi2

from fedqpnt.trust.trust_law import SensorTrustLaw, TrustLawConfig



CHI2_6_99 = float(chi2.ppf(0.99, 6))


def _to_probe(law):
    t = 0.0
    while law._core_v2.state != "PROBE" and t < 500:
        law.step(t, 1.0, nis_ok=False, features_nominal=False, nis_value=50.0,
                 es_evidence=True, es_position=False)
        t += 1.0
    assert law._core_v2.state == "PROBE"
    return t


def _run_probe(nis, es_evidence, es_position):
    law = SensorTrustLaw(cfg=TrustLawConfig(), law_mode="continuous", trust_law_version="v2")
    t = _to_probe(law)
    assert law.probe_shadow is True
    for _ in range(int(law.cfg.T_probe)):
        law.step(t, 0.0, nis_ok=True, features_nominal=True, nis_value=nis,
                 es_evidence=es_evidence, es_position=es_position)
        t += 1.0
    return law


def test_probe_is_shadow_only():
    law = SensorTrustLaw(cfg=TrustLawConfig(), law_mode="continuous", trust_law_version="v2")
    _to_probe(law)
    assert law.probe_shadow is True


def test_probe_passes_when_nis_consistent_even_if_position_jump_fires():
    law = _run_probe(nis=CHI2_6_99 * 0.3, es_evidence=False, es_position=True)
    assert law._core_v2.state == "TRUST"


def test_probe_fails_when_nis_inconsistent_with_coast():
    law = _run_probe(nis=CHI2_6_99 * 5.0, es_evidence=False, es_position=False)
    assert law._core_v2.state == "DISTRUST"


def test_probe_fails_on_clk_xsat_cn0_event_even_with_clean_nis():
    law = _run_probe(nis=1.0, es_evidence=True, es_position=False)
    assert law._core_v2.state == "DISTRUST"


# ---- engine-level: shadow-consistent reacquisition (D-066) --------------------------------
import numpy as np  # noqa: E402

from fedqpnt.core.types import GnssFix, Innovation, TrustState  # noqa: E402
from fedqpnt.trust.trust_law import TrustEngineImpl, make_method_config  # noqa: E402


def _gfix(t):
    return GnssFix(t=t, pos=np.zeros(3), vel=np.zeros(3), clk_bias=0.0, clk_drift=0.0, cov_pos=np.eye(3),
                   cov_vel=np.eye(3), residual_rms=0.5, num_sats=8, mean_cn0=45.0, std_cn0=1.0, agc_db=0.0,
                   valid=True, raim_stat=1.0, pdop=2.0)


def _shadow(nis):
    return Innovation(t=0.0, sensor="gnss_shadow", nu=np.zeros(6), S=np.eye(6), nis=float(nis), dof=6, accepted=True)


def _post_outage_weight(shadow_nis):
    eng = TrustEngineImpl(make_method_config("fedqpnt"))
    eng.update(0.0, _gfix(0.0), None, None, None, [])
    eng.gnss_law.force_w(1.0)
    for t in [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]:
        eng.update(t, None, None, None, None, [])
    inn = [] if shadow_nis is None else [_shadow(shadow_nis)]
    return eng.update(10.0, _gfix(10.0), None, None, None, inn).weights["gnss_pos"], eng.gnss_law.cfg.w_reacq


def test_reacquisition_cap_waived_when_first_fix_consistent_with_coast():
    w, w_reacq = _post_outage_weight(2.0)
    assert w > w_reacq + 1e-6   # cap not applied (w set only by the law itself, untrained detector)


def test_reacquisition_cap_kept_when_first_fix_inconsistent():
    w, w_reacq = _post_outage_weight(CHI2_6_99 * 5.0)
    assert w <= w_reacq + 1e-9


def test_reacquisition_cap_kept_without_shadow_information():
    w, w_reacq = _post_outage_weight(None)
    assert w <= w_reacq + 1e-9


def test_trust_state_reports_probe_shadow():
    eng = TrustEngineImpl(make_method_config("fedqpnt"))
    st = eng.update(0.0, _gfix(0.0), None, None, None, [])
    assert st.probe_shadow is False
    assert TrustState(t=0.0, weights={}, anomaly_scores={}, attack_detected=False).probe_shadow is False


# ---- filter-level: no update during shadow probe; shadow NIS is honest-covariance chi2_6 -----
def test_eskf_applies_no_gnss_update_during_probe_and_reports_shadow_nis():
    from fedqpnt.fusion import ESKF
    from fedqpnt.sensors.imu import ClassicalImu
    imu = ClassicalImu(grade="industrial_mems", rng=np.random.default_rng(0))
    kf = ESKF(imu.config())
    kf.initialize_static(0.0, np.zeros(3), np.zeros(3))
    fix = GnssFix(t=0.0, pos=np.array([26.0, 0.0, 0.0]), vel=np.zeros(3), clk_bias=0.0, clk_drift=0.0,
                  cov_pos=np.diag([9.0, 9.0, 25.0]), cov_vel=np.diag([0.01] * 3), residual_rms=0.0,
                  num_sats=6, mean_cn0=45.0, std_cn0=1.0, agc_db=0.0, valid=True, raim_stat=0.0)
    innov = kf.innovations(0.0, fix, None)
    shadow = next(i for i in innov if i.sensor == "gnss_shadow")
    assert shadow.dof == 6 and shadow.nis > CHI2_6_99   # 26 m vs ~sqrt(9+9) m: inconsistent
    p0, P0 = kf.p.copy(), kf.P.copy()
    probe = TrustState(t=0.0, weights={"gnss": 0.3, "imu": 1.0, "quantum": 1.0}, anomaly_scores={},
                       attack_detected=True, probe_shadow=True)
    kf.correct(0.0, innov, probe)
    assert np.array_equal(kf.p, p0) and np.array_equal(kf.P, P0)
    innov2 = kf.innovations(0.0, fix, None)
    live = TrustState(t=0.0, weights={"gnss": 1.0, "imu": 1.0, "quantum": 1.0}, anomaly_scores={},
                      attack_detected=False)
    kf.correct(0.0, innov2, live)
    assert kf.p[0] > 0.0


# ---- per-IMU-grade frozen acceptance bound (D-067 pre-registered calibration) ---------------
def test_per_grade_probe_nis_bound_applied_by_methods_layer():
    from fedqpnt.node.methods import PROBE_NIS_BOUND_BY_GRADE, make_agent_config
    assert PROBE_NIS_BOUND_BY_GRADE == {"industrial_mems": 25.07, "tactical": 6.74}
    for grade, bound in PROBE_NIS_BOUND_BY_GRADE.items():
        cfg = make_agent_config("fedqpnt_local", imu_grade=grade)
        assert cfg.trust.gnss_law_cfg.probe_nis_bound == bound
    assert make_agent_config("fedqpnt_local").trust.gnss_law_cfg.probe_nis_bound is None  # -> chi2_6(0.99)


def test_probe_uses_configured_bound():
    cfg = TrustLawConfig(probe_nis_bound=6.74)
    law = SensorTrustLaw(cfg=cfg, law_mode="continuous", trust_law_version="v2")
    t = _to_probe(law)
    for _ in range(int(cfg.T_probe)):
        law.step(t, 0.0, nis_ok=True, features_nominal=True, nis_value=10.0, es_evidence=False, es_position=False)
        t += 1.0
    assert law._core_v2.state == "DISTRUST"   # 10 > 6.74 although < chi2_6(0.99)=16.81
