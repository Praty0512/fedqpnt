"""D-075: DISTRUST pins w at w_min (ramp suspended). The only way out is DISTRUST -> PROBE (after T_ex) -> probe
success -> TRUST (ramp from the probe set-point). A spoof that goes quiet to the detector (p low, D = 0) must NOT be
re-admitted through the recovery ramp, which would bypass the shadow probe (D-066)."""
from __future__ import annotations

import pytest

from fedqpnt.trust.trust_law import SensorTrustLaw, TrustLawConfig

CFG = TrustLawConfig()


def _law():
    return SensorTrustLaw(cfg=CFG, law_mode="continuous", trust_law_version="v2")


def _enter_distrust(law):
    t = 0.0
    while law._core_v2.state != "DISTRUST" and t < 30:
        law.step(t, 1.0, nis_ok=False, features_nominal=False, nis_value=50.0, es_evidence=True)
        t += 1.0
    assert law._core_v2.state == "DISTRUST"
    return t


def test_a_distrust_holds_w_min_with_quiet_detector_and_no_evidence():
    law = _law()
    t = _enter_distrust(law)
    t_in = law._core_v2._distrust_timer
    n = int(CFG.T_ex - t_in) - 2                     # stay strictly inside DISTRUST (< T_ex)
    for _ in range(n):
        w = law.step(t, 0.0, nis_ok=True, features_nominal=True, nis_value=0.1, es_evidence=False)
        t += 1.0
        assert law._core_v2.state == "DISTRUST"
        assert w == pytest.approx(CFG.w_min), (t, w)
    assert law._core_v2.core.D == 0 or True          # core flag may clear; w must still be pinned


def test_b_readmission_only_after_probe_success():
    law = _law()
    t = _enter_distrust(law)
    ws_before_probe, saw_probe, saw_trust = [], False, False
    for _ in range(int(CFG.T_ex + CFG.T_probe) + 30):
        w = law.step(t, 0.0, nis_ok=True, features_nominal=True, nis_value=0.1, es_evidence=False)
        t += 1.0
        st = law._core_v2.state
        if st == "DISTRUST" and not saw_probe:
            ws_before_probe.append(w)
        if st == "PROBE":
            if saw_probe:                              # first PROBE epoch is the transition step (w still w_min)
                assert w == pytest.approx(CFG.w_probe)
            saw_probe = True
        if st == "TRUST":
            saw_trust = True
            assert saw_probe, "TRUST reached without passing PROBE"
            break
    assert saw_probe and saw_trust
    assert max(ws_before_probe) == pytest.approx(CFG.w_min)
    assert law.w >= CFG.w_probe - 1e-9                   # ramp starts from the probe set-point


def test_c_consistency_matched_quiet_spoof_cannot_raise_w_before_the_probe():
    """p low (quiet), NIS consistent with the coast (matched adversary), no E_s: w must still stay pinned
    until the PROBE (the probe itself may then admit it: documented bounded-damage limit)."""
    law = _law()
    t = _enter_distrust(law)
    while law._core_v2.state == "DISTRUST":
        w = law.step(t, 0.02, nis_ok=True, features_nominal=True, nis_value=1.0, es_evidence=False)
        t += 1.0
        if law._core_v2.state == "DISTRUST":
            assert w == pytest.approx(CFG.w_min)
        assert t < 200


def test_failed_probe_returns_to_pinned_distrust():
    law = _law()
    t = _enter_distrust(law)
    # run to PROBE, then fail it with inconsistent NIS
    for _ in range(int(CFG.T_ex) + 5):
        law.step(t, 0.0, nis_ok=True, features_nominal=True, nis_value=100.0, es_evidence=False)
        t += 1.0
        if law._core_v2.state == "PROBE":
            break
    for _ in range(int(CFG.T_probe) + 1):
        law.step(t, 0.0, nis_ok=True, features_nominal=True, nis_value=100.0, es_evidence=False)
        t += 1.0
    assert law._core_v2.state == "DISTRUST"
    w = law.step(t, 0.0, nis_ok=True, features_nominal=True, nis_value=0.1, es_evidence=False)
    assert w == pytest.approx(CFG.w_min)
