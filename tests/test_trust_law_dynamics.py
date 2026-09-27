"""§3.3 continuous trust-law property tests (S7 chattering bound, latency,
recovery, reacquisition cap, floor, boundedness, determinism) + §5 mode
behaviour checks. Pure trust-law unit tests: p-sequences are synthetic
(adversarial by construction), no simulator needed -- this is testing the
LAW itself, exactly what S7 in ARCHITECTURE.md §7 specifies.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from fedqpnt.trust.trust_law import SensorTrustLaw, TrustLawConfig

T_CYC_MIN_S = 26.1  # ARCHITECTURE.md §3.3 "No chattering (formal)"


def _count_trust_cycles(ts: np.ndarray, ws: np.ndarray) -> int:
    """A trust cycle = a downward crossing of w=0.5 followed by an upward
    crossing of w=0.9 (§3.3 definition used by S7)."""
    cycles = 0
    state = "above"  # above 0.5, waiting for a down-cross
    armed = False
    for w in ws:
        if state == "above" and w < 0.5:
            state = "below"
            armed = True
        elif state == "below" and armed and w > 0.9:
            cycles += 1
            state = "above"
            armed = False
    return cycles


@pytest.mark.parametrize("period_s", [2.0, 5.0, 10.0, 20.0, 60.0])
def test_no_chattering_under_adversarial_toggling(period_s):
    """S7: adversarial square-wave toggling of the detector output p at
    1 Hz evidence rate, for several periods, over a 1-hour window. Must
    respect T_cyc >= 26.1 s => at most ceil(3600/26.1) = 138 cycles/hour,
    for EVERY period tested (this is the point of the formal bound: it
    holds regardless of the adversary's chosen toggle rate)."""
    law = SensorTrustLaw(cfg=TrustLawConfig())
    duration_s = 3600.0
    dt = 1.0
    n = int(duration_s / dt)
    ts = np.arange(n) * dt
    ws = np.empty(n)
    on_phase = np.empty(n, dtype=bool)
    for k, t in enumerate(ts):
        phase = (t % period_s) < (period_s / 2.0)  # True = "attack ON" half of the square wave
        on_phase[k] = phase
        p = 1.0 if phase else 0.0
        # nis/features track p: clean (nis_ok/features_nominal=True) only in the OFF half.
        ws[k] = law.step(t, p, nis_ok=not phase, features_nominal=not phase)
    n_cyc = _count_trust_cycles(ts, ws)
    max_allowed = math.ceil(duration_s / T_CYC_MIN_S)
    mean_w_on = float(np.mean(ws[on_phase]))
    print(f"\n[S7 period={period_s}s] n_cycles={n_cyc}, mean w_gnss during ON phase={mean_w_on:.4f}")
    assert n_cyc <= max_allowed, f"period={period_s}s: {n_cyc} cycles > bound {max_allowed}"
    # Master D-022 item 6: "0 cycles" must mean it STAYS distrusted during the
    # attack, not stuck trusting -- check the ON-phase mean directly.
    assert mean_w_on < 0.5, f"period={period_s}s: mean w_gnss during ON phase={mean_w_on:.4f} (not distrusted)"


def test_no_chattering_under_threshold_noise():
    """S7's second case: noise near the detection threshold theta_on/theta_off."""
    rng = np.random.default_rng(7)
    law = SensorTrustLaw(cfg=TrustLawConfig())
    duration_s = 3600.0
    dt = 1.0
    n = int(duration_s / dt)
    ts = np.arange(n) * dt
    ws = np.empty(n)
    for k, t in enumerate(ts):
        p = float(np.clip(0.45 + rng.normal(0, 0.08), 0.0, 1.0))  # hovers near theta_off=0.3 / theta_on=0.6
        ws[k] = law.step(t, p, nis_ok=True, features_nominal=True)
    n_cyc = _count_trust_cycles(ts, ws)
    max_allowed = math.ceil(duration_s / T_CYC_MIN_S)
    assert n_cyc <= max_allowed


def test_design_distrust_latency_one_epoch_at_1hz():
    """§3.3 'Latency from design': a step to p=1 at 1 Hz GNSS drops w below
    0.5 within the first epoch."""
    law = SensorTrustLaw(cfg=TrustLawConfig())
    w0 = law.step(0.0, 1.0, nis_ok=False, features_nominal=False)  # first call initialises p_bar=p
    w1 = law.step(1.0, 1.0, nis_ok=False, features_nominal=False)
    assert w1 < 0.5, f"expected w<0.5 within 1 epoch at 1Hz, got w1={w1}"


def test_recovery_time_matches_design():
    """Design recovery time from w_min to 0.9 is T_clean + tau_r*ln(0.98/0.1)
    ~= 10 + 10*ln(9.8) ~= 32.9 s after the clean-recovery gate opens."""
    cfg = TrustLawConfig()
    law = SensorTrustLaw(cfg=cfg)
    t = 0.0
    dt = 0.1
    # drive to distrust
    for _ in range(20):
        law.step(t, 1.0, nis_ok=False, features_nominal=False)
        t += dt
    assert law.w < 0.5
    t_distrust_end = t
    # now clean signal: p=0, nis always ok, features nominal -> should recover
    w_trace = []
    t_trace = []
    for _ in range(int(80.0 / dt)):
        w = law.step(t, 0.0, nis_ok=True, features_nominal=True)
        w_trace.append(w)
        t_trace.append(t)
        t += dt
    w_trace = np.array(w_trace)
    t_trace = np.array(t_trace) - t_distrust_end
    idx = np.argmax(w_trace >= 0.9)
    assert w_trace[idx] >= 0.9, "never recovered to 0.9 within 80s"
    t_recover = t_trace[idx]
    assert 20.0 <= t_recover <= 45.0, f"recovery time {t_recover:.1f}s far from design ~33s"


def test_reacquisition_cap_direct():
    """§9/§5: first valid fix after an outage > T_gap=5s caps w at w_reacq=0.5,
    tested directly on SensorTrustLaw (the mechanism TrustEngine calls)."""
    cfg = TrustLawConfig()
    law = SensorTrustLaw(cfg=cfg)
    law.step(0.0, 0.0, nis_ok=True, features_nominal=True)
    law._core.w = 1.0  # simulate a fully-trusted pre-outage state
    law.apply_reacquisition_cap()
    assert law.w == pytest.approx(cfg.w_reacq)


def test_reacquisition_cap_via_trust_engine():
    """The same cap, invoked through TrustEngineImpl.update on a real gap."""
    from fedqpnt.trust.trust_law import TrustEngineImpl, make_method_config
    from fedqpnt.core.types import GnssFix

    eng = TrustEngineImpl(make_method_config("fedqpnt"))

    def make_fix(t, valid=True, num_sats=8):
        return GnssFix(t=t, pos=np.zeros(3), vel=np.zeros(3), clk_bias=0.0, clk_drift=0.0,
                       cov_pos=np.eye(3), cov_vel=np.eye(3), residual_rms=0.5, num_sats=num_sats,
                       mean_cn0=45.0, std_cn0=1.0, agc_db=0.0, valid=valid, raim_stat=1.0, pdop=2.0)

    eng.update(0.0, make_fix(0.0), None, None, None, [])
    eng.gnss_law.force_w(1.0)  # force a fully-trusted pre-outage state (detector is untrained here)
    # outage > T_gap (5s): no fix at all for several ticks
    for t in [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]:
        eng.update(t, None, None, None, None, [])
    assert eng.gnss_law.w == pytest.approx(1.0)  # unchanged while no evidence arrives
    # first valid fix after the gap: cap must apply before any new update takes effect
    st = eng.update(10.0, make_fix(10.0), None, None, None, [])
    assert st.weights["gnss"] <= eng.gnss_law.cfg.w_reacq + 1e-9


def test_floor_and_boundedness():
    cfg = TrustLawConfig()
    law = SensorTrustLaw(cfg=cfg)
    rng = np.random.default_rng(3)
    t = 0.0
    for _ in range(5000):
        p = float(rng.uniform(0, 1))
        w = law.step(t, p, nis_ok=bool(rng.uniform() > 0.5), features_nominal=bool(rng.uniform() > 0.5))
        assert cfg.w_min - 1e-9 <= w <= 1.0 + 1e-9
        t += rng.uniform(0.05, 2.0)


def test_determinism():
    def run():
        law = SensorTrustLaw(cfg=TrustLawConfig())
        rng = np.random.default_rng(11)
        t = 0.0
        out = []
        for _ in range(500):
            p = float(rng.uniform(0, 1))
            out.append(law.step(t, p, nis_ok=True, features_nominal=True))
            t += 0.5
        return np.array(out)

    a, b = run(), run()
    np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("mode,expected_values", [
    ("fixed_exclude", {0.0, 1.0}),
    ("w_equals_1", {1.0}),
    ("binary_hysteresis", {0.02, 1.0}),
])
def test_mode_output_ranges(mode, expected_values):
    law = SensorTrustLaw(cfg=TrustLawConfig(), law_mode=mode)
    rng = np.random.default_rng(5)
    t = 0.0
    seen = set()
    for _ in range(400):
        p = float(rng.uniform(0, 1))
        w = law.step(t, p, nis_ok=True, features_nominal=True)
        seen.add(round(w, 6))
        t += 0.7
    assert seen <= {round(v, 6) for v in expected_values}


def test_detect_switch_hard_exclude_and_recovery():
    law = SensorTrustLaw(cfg=TrustLawConfig(), law_mode="detect_switch")
    t = 0.0
    for _ in range(20):
        law.step(t, 1.0, nis_ok=False, features_nominal=False)
        t += 0.1
    assert law.w == pytest.approx(law.cfg.w_excl)
    # clean signal long enough for the recovery gate
    for _ in range(300):
        law.step(t, 0.0, nis_ok=True, features_nominal=True)
        t += 0.1
    assert law.w == 1.0


T_EX_V2 = 60.0
T_PROBE_V2 = 10.0


def test_v2_chronic_false_detector_bounded_exclusion_and_recovers():
    """D-051 sec C unit test (i): a chronically firing detector (p=1
    forever) on otherwise CLEAN data (nis_ok, features_nominal, no physical
    E_s evidence) must never keep w_gnss depressed (DISTRUST or PROBE) for
    longer than T_ex + T_probe = 70s at a stretch, and must actually recover
    (w -> near 1) during the T_sup suppression window that follows a
    successful PROBE exit -- this is exactly the M1-CLOSE anti-lockout bug
    (EXECUTION_LOG #83: v1 had NO bound on time spent with D=1)."""
    cfg = TrustLawConfig()
    law = SensorTrustLaw(cfg=cfg, law_mode="continuous", trust_law_version="v2")
    t = 0.0
    dt = 1.0
    excl_run = 0.0
    max_excl_run = 0.0
    max_w = 0.0
    for _ in range(1200):
        w = law.step(t, 1.0, nis_ok=True, features_nominal=True, nis_value=0.1, es_evidence=False)
        if law._core_v2.state in ("DISTRUST", "PROBE"):
            excl_run += dt
            max_excl_run = max(max_excl_run, excl_run)
        else:
            excl_run = 0.0
        max_w = max(max_w, w)
        t += dt
    assert max_excl_run <= T_EX_V2 + T_PROBE_V2 + 1e-6, (
        f"exclusion (DISTRUST+PROBE) ran continuously for {max_excl_run}s, "
        f"exceeds the T_ex+T_probe={T_EX_V2 + T_PROBE_V2}s bound")
    assert max_w > 0.9, f"never recovered near full trust despite the T_sup suppression window (max w={max_w})"


def test_v2_drift_spoof_xsat_signature_stays_distrusted_through_probes():
    """D-051 sec C unit test (ii): injected drift spoofing carrying a
    physical E_s signature (here: es_evidence=True throughout, standing in
    for a persistent xsat/clock-jump/position-gate signature) must keep the
    PROBE exit test failing every cycle -- w must never rise above w_probe,
    and the system stays flagged as attacked."""
    cfg = TrustLawConfig()
    law = SensorTrustLaw(cfg=cfg, law_mode="continuous", trust_law_version="v2")
    t = 0.0
    max_w_after_transient = 0.0
    for _ in range(600):
        w = law.step(t, 1.0, nis_ok=False, features_nominal=False, nis_value=50.0, es_evidence=True)
        if t > 5.0:  # allow the initial hysteresis-latency ramp to settle
            max_w_after_transient = max(max_w_after_transient, w)
        t += 1.0
    assert max_w_after_transient <= cfg.w_probe + 1e-6, (
        f"w rose above w_probe={cfg.w_probe} despite persistent physical spoof evidence "
        f"(max w after transient={max_w_after_transient})")
    assert law.attack_detected


def test_v2_consistent_partial_jamming_recovers():
    """D-051 sec C unit test (iii): consistent partial jamming -- an
    elevated detector score (p=0.7, enough to trip the p-bar hysteresis)
    but with NIS staying nominal and no physical E_s evidence (jamming
    degrades rather than deceives; the honest receiver covariance already
    down-weights degraded fixes, so jamming alone must never block the
    PROBE recovery). Must recover to TRUST within one T_ex+T_probe cycle."""
    cfg = TrustLawConfig()
    law = SensorTrustLaw(cfg=cfg, law_mode="continuous", trust_law_version="v2")
    t = 0.0
    recovered_at = None
    for _ in range(400):
        w = law.step(t, 0.7, nis_ok=True, features_nominal=True, nis_value=0.1, es_evidence=False)
        if law._core_v2.state == "TRUST" and t > 5.0 and recovered_at is None:
            recovered_at = t
        t += 1.0
    assert recovered_at is not None, "consistent partial jamming never recovered to TRUST"
    assert recovered_at <= T_EX_V2 + T_PROBE_V2 + 10.0, f"recovery took {recovered_at}s, far beyond one T_ex+T_probe cycle"


@pytest.mark.parametrize("period_s", [2.0, 5.0, 10.0, 20.0, 60.0])
def test_v2_no_chattering_under_adversarial_toggling(period_s):
    """D-051 sec C unit test (iv): S7 re-verified for trust_law_version='v2'.
    A cycle here is >= T_ex + T_probe = 70s > the 26.1s §3.3 bound (sec C
    item 7), so the chattering bound holds a fortiori with a tighter
    per-hour cap than v1's."""
    cfg = TrustLawConfig()
    law = SensorTrustLaw(cfg=cfg, law_mode="continuous", trust_law_version="v2")
    duration_s = 3600.0
    dt = 1.0
    n = int(duration_s / dt)
    ts = np.arange(n) * dt
    ws = np.empty(n)
    for k, t in enumerate(ts):
        phase = (t % period_s) < (period_s / 2.0)
        p = 1.0 if phase else 0.0
        ws[k] = law.step(t, p, nis_ok=not phase, features_nominal=not phase,
                          nis_value=(5.0 if phase else 0.1), es_evidence=False)
    n_cyc = _count_trust_cycles(ts, ws)
    max_allowed = math.ceil(duration_s / (T_EX_V2 + T_PROBE_V2))
    assert n_cyc <= max_allowed, f"period={period_s}s: {n_cyc} cycles > v2 bound {max_allowed}"


def test_no_recovery_gate_ablation_recovers_without_clean_dwell():
    """Abl -recovery-gate: G forced True, so recovery starts immediately
    once tau* > w, without needing T_clean of NIS-clean evidence."""
    law = SensorTrustLaw(cfg=TrustLawConfig(), law_mode="no_recovery_gate")
    t = 0.0
    for _ in range(20):
        law.step(t, 1.0, nis_ok=False, features_nominal=False)
        t += 0.1
    w_low = law.w
    assert w_low < 0.5
    # immediately clean, but do NOT wait T_clean=10s -- give it only 2s
    for _ in range(20):
        law.step(t, 0.0, nis_ok=True, features_nominal=True)
        t += 0.1
    assert law.w > w_low  # recovers even though clean-dwell T_clean has not elapsed
