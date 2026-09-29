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

pytestmark = pytest.mark.xfail(reason="D-066 pending implementation (remove when landed)", strict=False)

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
    for _ in range(int(law.cfg.T_probe) + 1):
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
