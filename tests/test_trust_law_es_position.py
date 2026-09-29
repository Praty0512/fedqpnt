"""D-058: the E_s short-baseline GNSS-vs-INS jump test
(``TrustEngineImpl._physical_spoof_evidence``'s position term).

Direct unit tests on the evidence function -- bypasses the detector/feature
pipeline (not what's under test here) by constructing GnssFix/Innovation
objects and pre-seeding the engine's previous-epoch state
(``_last_gnss_pos``/``_last_gnss_cov``/``_last_p_prior``).

IMPORTANT: the INS-side baseline is the engine's OWN previous-epoch
pre-correction estimate ``_last_p_prior`` (exactly one GNSS epoch old by
construction), NOT ``nav_prior`` (the previous AGENT TICK's corrected
state, which is only one IMU dt -- e.g. 0.01s at 100 Hz -- older, not one
GNSS epoch -- e.g. 1s at 1 Hz -- older). Using nav_prior was tried first and
measured to false-fire on ~80% of clean nominal epochs because it covers a
much shorter span than Delta p_GNSS; see
docs/specs/raw/CORE_ROBUST_NOTES.md and the function's own docstring.
"""
from __future__ import annotations

import numpy as np

from fedqpnt.core.types import GnssFix, Innovation, NavSolution, TrustState
from fedqpnt.trust.trust_law import TrustEngineImpl, make_method_config

N_FEATURES = 15


def _engine():
    cfg = make_method_config("fedqpnt")  # trust_law_version="v2" -> _uses_v2
    return TrustEngineImpl(cfg)


def _raw_clean():
    # all zeros: no clk/xsat/cn0 evidence triggered (mu=0, sd=1 defaults)
    return np.zeros(N_FEATURES)


def _fix(pos, cov_pos=None, t=0.0):
    cov_pos = cov_pos if cov_pos is not None else np.eye(3)
    return GnssFix(t=t, pos=np.asarray(pos, dtype=float), vel=np.zeros(3), clk_bias=0.0,
                   clk_drift=0.0, cov_pos=cov_pos, cov_vel=np.eye(3) * 0.01,
                   residual_rms=0.0, num_sats=6, mean_cn0=45.0, std_cn0=1.0, agc_db=0.0, valid=True)


def _dummy_nav_prior():
    # No longer used by the position term (see module docstring) -- passed
    # only because it's a positional parameter of _physical_spoof_evidence.
    return NavSolution(t=0.0, pos=np.zeros(3), vel=np.zeros(3), att=np.zeros(3),
                        clk_bias=0.0, cov_pos=np.eye(3),
                        trust=TrustState(t=0.0, weights={}, anomaly_scores={}, attack_detected=False))


def _gnss_pos_innov(p_prior, fix_pos):
    nu = np.asarray(p_prior, dtype=float) - np.asarray(fix_pos, dtype=float)
    S = np.eye(3)
    return Innovation(t=0.0, sensor="gnss_pos", nu=nu, S=S, nis=float(nu @ nu), dof=3, accepted=True)


def test_abrupt_jump_fires():
    eng = _engine()
    eng._last_gnss_pos = np.zeros(3)
    eng._last_gnss_cov = np.eye(3)
    eng._last_p_prior = np.zeros(3)         # previous epoch: INS estimate was at 0

    fix = _fix([50.0, 0.0, 0.0])            # GNSS abruptly jumps 50 m this epoch
    p_prior = np.array([0.0, 0.0, 0.0])     # this epoch's INS propagation: still ~0 (no real motion)
    innov = [_gnss_pos_innov(p_prior, fix.pos)]

    assert eng._physical_spoof_evidence(_raw_clean(), fix, _dummy_nav_prior(), innov) is True


def test_slow_drift_does_not_fire():
    eng = _engine()
    eng._last_gnss_pos = np.zeros(3)
    eng._last_gnss_cov = np.eye(3)
    eng._last_p_prior = np.zeros(3)

    fix = _fix([0.1, 0.0, 0.0])             # GNSS drifted 10 cm this epoch
    p_prior = np.array([0.0, 0.0, 0.0])     # INS ~stationary, consistent with real slow motion
    innov = [_gnss_pos_innov(p_prior, fix.pos)]

    assert eng._physical_spoof_evidence(_raw_clean(), fix, _dummy_nav_prior(), innov) is False


def test_real_fast_motion_does_not_fire_when_ins_tracks_it():
    # A genuinely fast-moving vehicle: both GNSS and INS advance by the same
    # ~2 m this epoch (INS correctly tracks real motion) -- must NOT fire.
    # (This is the exact case the nav_prior-based first attempt got wrong.)
    eng = _engine()
    eng._last_gnss_pos = np.zeros(3)
    eng._last_gnss_cov = np.eye(3)
    eng._last_p_prior = np.zeros(3)

    fix = _fix([2.0, 0.0, 0.0])             # GNSS: vehicle moved 2 m this epoch
    p_prior = np.array([2.02, 0.0, 0.0])    # INS: also ~2 m, small honest INS noise
    innov = [_gnss_pos_innov(p_prior, fix.pos)]

    assert eng._physical_spoof_evidence(_raw_clean(), fix, _dummy_nav_prior(), innov) is False


def test_filter_self_divergence_does_not_fire():
    # The filter's ABSOLUTE state is ~1000 m away from the GNSS fix (a huge
    # standing offset from some unrelated filter defect, not spoofing), but
    # GNSS-vs-GNSS and INS-vs-INS deltas over this ONE epoch are both small
    # and mutually consistent -- the short-baseline test must not fire even
    # though the raw filter NIS (nu = p_prior - fix.pos) would be enormous.
    eng = _engine()
    eng._last_gnss_pos = np.array([0.0, 0.0, 0.0])       # previous epoch's real GNSS fix
    eng._last_gnss_cov = np.eye(3)
    eng._last_p_prior = np.array([999.9, 0.0, 0.0])      # previous epoch's INS estimate: diverged

    fix = _fix([0.05, 0.0, 0.0])                          # this epoch's GNSS fix: real, slow motion
    p_prior = np.array([1000.0, 0.0, 0.0])                # this epoch's INS: continued divergence
                                                           # (consistent evolution of the SAME defect)
    innov = [_gnss_pos_innov(p_prior, fix.pos)]           # nu = p_prior - fix.pos is huge: this is
                                                           # what the OLD (self-contaminated) NIS
                                                           # test used directly

    assert eng._physical_spoof_evidence(_raw_clean(), fix, _dummy_nav_prior(), innov) is False


def test_no_history_never_fires_on_position_alone():
    # First epoch ever (no _last_gnss_pos/_last_gnss_cov/_last_p_prior yet):
    # the position term must not fire (insufficient history), not raise or
    # spuriously fire.
    eng = _engine()
    fix = _fix([50.0, 0.0, 0.0])
    p_prior = np.array([0.0, 0.0, 0.0])
    innov = [_gnss_pos_innov(p_prior, fix.pos)]
    assert eng._physical_spoof_evidence(_raw_clean(), fix, _dummy_nav_prior(), innov) is False


def test_post_gap_reset_prevents_jam_recovery_lockout():
    """Master-directed regression test: reproduces the jam-recovery false
    lockout found by scripts/core_robust_jam_recovery_trace.py and confirms
    the fix (TrustLawConfig.es_gap_reset_factor x es_nominal_epoch_s in
    TrustEngineImpl.update).

    Scenario: a normal epoch establishes the position-evidence baseline: a
    ~180s GNSS outage (jamming) follows, during which the filter free-
    inertial-coasts and drifts ~150m; the first fix after the outage
    reports the vehicle back near its true (stationary) position, with a
    huge INS-vs-truth mismatch (nu ~150m) -- exactly what a real jamming
    outage produces, NOT a spoof. Without the gap reset, Delta p_INS would
    span the whole outage while Delta p_GNSS spans one epoch, giving a huge
    false E_s (measured stat=763 vs gate=16.27 in the trace) that locks
    GNSS into DISTRUST right when it should be trusted again. With the
    fix, the position term is skipped on this first post-gap epoch (stale
    baseline reset, not tested) and resumes normally from the next epoch.
    """
    cfg = make_method_config("fedqpnt")
    eng = TrustEngineImpl(cfg)

    # Epoch 1 at t=100s: normal, establishes the baseline (INS tracking truth).
    fix1 = _fix([0.0, 0.0, 0.0], t=100.0)
    innov1 = [_gnss_pos_innov([0.0, 0.0, 0.0], fix1.pos)]
    eng.update(100.0, fix1, None, None, _dummy_nav_prior(), innov1)
    assert eng.last_es_evidence is False
    assert eng._last_gnss_pos is not None

    # Epoch 2 at t=280s (180s gap, e.g. a jamming outage): vehicle truly
    # stationary (fix.pos == 0), but the filter free-inertial-coasted to
    # ~150m off truth during the outage -- nu = p_prior - fix.pos ~ 150m.
    fix2 = _fix([0.0, 0.0, 0.0], t=280.0)
    innov2 = [_gnss_pos_innov([150.0, 0.0, 0.0], fix2.pos)]
    eng.update(280.0, fix2, None, None, _dummy_nav_prior(), innov2)
    assert eng.last_es_evidence is False, "post-gap epoch must skip the position test, not false-fire"

    # Epoch 3 at t=281s (back to normal 1s spacing): still inside the
    # 2-epoch quarantine (see _es_position_quarantine), so this epoch is
    # ALSO skipped even though it's an ordinary one-epoch delta.
    fix3 = _fix([0.02, 0.0, 0.0], t=281.0)
    innov3 = [_gnss_pos_innov([0.0, 0.0, 0.0], fix3.pos)]
    eng.update(281.0, fix3, None, None, _dummy_nav_prior(), innov3)
    assert eng.last_es_evidence is False
    assert eng._es_position_quarantine == 0, "quarantine must have fully decremented by now"

    # Epoch 4 at t=282s: quarantine has expired -- the position test is
    # live again, so a genuine abrupt jump must still fire (the fix must
    # not have disabled E_s permanently).
    fix4 = _fix([0.02, 0.0, 0.0], t=282.0)
    innov4 = [_gnss_pos_innov([50.0, 0.0, 0.0], fix4.pos)]
    eng.update(282.0, fix4, None, None, _dummy_nav_prior(), innov4)
    assert eng.last_es_evidence is True, "quarantine expiry must not disable real detection"
