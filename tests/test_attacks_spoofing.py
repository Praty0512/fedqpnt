import numpy as np

from fedqpnt.core.seeding import stream
from fedqpnt.gnss.signal import GnssSignalModel
from fedqpnt.gnss.receiver import GnssReceiver
from fedqpnt.attacks.spoofing import DriftInSpoof, MeaconingReplay, AbruptSpoof
from tests._helpers import static_truth


def _run_with_attack(attack, duration_s=120.0, dt=0.01, seed=21):
    rng_sig = stream(seed, "n", "gnss")
    rng_atk = stream(seed, "n", "attack")
    model = GnssSignalModel(rate_hz=1.0)
    recv = GnssReceiver()
    n = int(duration_s / dt)
    rows = []
    for k in range(n):
        t = k * dt
        truth = static_truth(t)
        ep = model.step(truth, rng_sig)
        if ep is None:
            continue
        ep_atk = attack.apply(ep, truth, rng_atk)
        fix = recv.solve(ep_atk.for_agent())
        label = attack.label(t)
        rows.append((t, fix, label, truth))
    return rows


def test_drift_spoof_labels_align_with_schedule():
    atk = DriftInSpoof(onset_s=20.0, align_s=5.0, duration_s=60.0, severity=0.8)
    rows = _run_with_attack(atk, duration_s=120.0)
    for t, fix, label, truth in rows:
        expect_active = 20.0 <= t < 20.0 + 60.0 + atk.off_ramp_s
        assert label.spoofing == expect_active
        assert label.jamming is False
        if expect_active:
            assert label.kind == "drift_spoof"
        else:
            assert label.kind == "none"


def test_drift_spoof_pvt_offset_follows_drag_profile_within_3sigma():
    """Tightened per Master WP-3.x review round 2, decision 3: compare the
    ATTACK-INDUCED offset (attacked fix minus a parallel clean-receiver fix
    solved from the SAME underlying clean epoch) against the attack's own
    closed-form ``expected_offset(t)``, normalised by the attacked fix's
    reported position sigma. This isolates the drag-profile-tracking error
    from the (unrelated, naturally-occurring) correlated atmospheric bias
    that affects clean and attacked fixes identically."""
    atk = DriftInSpoof(onset_s=10.0, align_s=5.0, duration_s=80.0, severity=1.0,
                        max_drift_accel_mps2=0.2, max_drift_vel_mps=3.0)
    rng_sig = stream(21, "n", "gnss")
    rng_atk = stream(21, "n", "attack")
    model = GnssSignalModel(rate_hz=1.0)
    recv_clean = GnssReceiver()
    recv_atk = GnssReceiver()
    n = int(88.0 / 0.01)  # stop before duration_s=80 + off_ramp ends (attack window is [10, 92))
    normalized_errs = []
    for k in range(n):
        t = k * 0.01
        truth = static_truth(t)
        ep = model.step(truth, rng_sig)
        if ep is None:
            continue
        ep_atk = atk.apply(ep, truth, rng_atk)
        fc = recv_clean.solve(ep.for_agent())
        fa = recv_atk.solve(ep_atk.for_agent())
        if t < 20.0 or not (fc.valid and fa.valid):
            continue
        off, _ = atk.expected_offset(t)
        err = (fa.pos - fc.pos) - off
        sigma = np.sqrt(np.diag(fa.cov_pos))
        normalized_errs.append(np.max(np.abs(err) / np.maximum(sigma, 1e-6)))
    assert len(normalized_errs) > 20
    normalized_errs = np.array(normalized_errs)
    assert normalized_errs.max() < 3.0, f"max normalised drag-offset error {normalized_errs.max():.2f} sigma >= 3"


def test_drift_spoof_cn0_bump_during_alignment():
    atk = DriftInSpoof(onset_s=10.0, align_s=8.0, duration_s=60.0, severity=1.0)
    rows_clean = _run_with_attack(DriftInSpoof(onset_s=1e9), duration_s=25.0)  # never fires -> clean baseline
    rows_atk = _run_with_attack(atk, duration_s=25.0)
    cn0_clean = np.mean([fix.mean_cn0 for t, fix, l, tr in rows_clean if 12 <= t <= 16])
    cn0_atk = np.mean([fix.mean_cn0 for t, fix, l, tr in rows_atk if 12 <= t <= 16])
    assert cn0_atk > cn0_clean + 1.0  # power-advantage bump visible


def test_meaconing_common_mode_clock_jump():
    atk = MeaconingReplay(onset_s=15.0, duration_s=40.0, replay_delay_m=1200.0, severity=1.0, ramp_s=0.1)
    rows = _run_with_attack(atk, duration_s=60.0)
    bias_before = np.mean([fix.clk_bias for t, fix, l, tr in rows if 13.0 <= t < 15.0 and fix.valid])
    bias_during = np.mean([fix.clk_bias for t, fix, l, tr in rows if 20.0 <= t < 25.0 and fix.valid])
    target = atk.replay_delay_m * atk.severity
    assert abs((bias_during - bias_before) - target) < 5.0, (
        f"clock jump {bias_during - bias_before:.2f} m vs target {target:.2f} m, outside +-5 m")


def test_abrupt_spoof_causes_lock_loss_then_jump():
    atk = AbruptSpoof(onset_s=15.0, duration_s=40.0, jump_vector_enu=np.array([100.0, 0.0, 0.0]), severity=1.0)
    rows = _run_with_attack(atk, duration_s=60.0)
    # first epoch(s) at/after onset should show invalid fix (lock loss) or reduced num_sats
    onset_rows = [(t, fix) for t, fix, l, tr in rows if 15.0 <= t < 17.0]
    assert any((not fix.valid) or fix.num_sats < 6 for t, fix in onset_rows)
    later_rows = [(t, fix) for t, fix, l, tr in rows if 25.0 <= t < 30.0 and fix.valid]
    assert len(later_rows) > 0
    jump_err = np.mean([np.linalg.norm(fix.pos[:2]) for t, fix in later_rows])
    assert jump_err > 50.0  # PVT reflects the jumped fake position


def test_single_antenna_cn0_correlation_and_elevation_slope_collapse():
    """Master D-018 item 2: all spoofed PRNs come off one antenna/one signal
    chain (Radoš, Brkić & Begušić 2024, Sensors 24(13):4210, Fig. 5: field
    C/N0 cross-satellite correlation -0.76 clean vs 0.99 spoofed). After
    capture, spoofed-PRN C/N0 should be strongly cross-correlated (mean
    pairwise corr > 0.7) vs ~0 clean, and the C/N0-vs-elevation slope should
    collapse (attacker's power doesn't track real per-satellite geometry)."""
    atk = DriftInSpoof(onset_s=10.0, align_s=5.0, duration_s=200.0, severity=1.0)
    rng_sig_atk = stream(21, "n", "gnss")
    rng_atk = stream(21, "n", "attack")
    model_atk = GnssSignalModel(rate_hz=1.0)
    rng_sig_clean = stream(22, "n", "gnss")
    model_clean = GnssSignalModel(rate_hz=1.0)

    series_clean, els_clean, cn0_clean = {}, [], []
    for k in range(300):
        truth = static_truth(float(k))
        ep = model_clean.step(truth, rng_sig_clean)
        if ep is None:
            continue
        for o in ep.obs:
            series_clean.setdefault(o.prn, []).append(o.cn0_dbhz)
            els_clean.append(np.degrees(o.elevation))
            cn0_clean.append(o.cn0_dbhz)

    series_atk, els_atk, cn0_atk = {}, [], []
    n = int(200.0 / 0.01)
    for k in range(n):
        t = k * 0.01
        truth = static_truth(t)
        ep = model_atk.step(truth, rng_sig_atk)
        if ep is None:
            continue
        ep2 = atk.apply(ep, truth, rng_atk)
        if 30.0 <= t < 190.0:  # well past capture (drag_start=15) and past cn0 convergence (tau=5s)
            for o in ep2.obs:
                series_atk.setdefault(o.prn, []).append(o.cn0_dbhz)
                els_atk.append(np.degrees(o.elevation))
                cn0_atk.append(o.cn0_dbhz)

    def mean_pairwise_corr(series, min_len=50):
        prns = [p for p, v in series.items() if len(v) > min_len]
        n_common = min(len(series[p]) for p in prns)
        M = np.array([series[p][:n_common] for p in prns])
        C = np.corrcoef(M)
        iu = np.triu_indices(len(prns), 1)
        return C[iu].mean()

    corr_clean = mean_pairwise_corr(series_clean)
    corr_atk = mean_pairwise_corr(series_atk)
    assert abs(corr_clean) < 0.3, f"clean cross-PRN C/N0 correlation {corr_clean:.3f} not near 0"
    assert corr_atk > 0.7, f"spoofed cross-PRN C/N0 correlation {corr_atk:.3f} not > 0.7"

    slope_clean = np.polyfit(els_clean, cn0_clean, 1)[0]
    slope_atk = np.polyfit(els_atk, cn0_atk, 1)[0]
    assert abs(slope_clean) > 0.05, f"clean C/N0-vs-elevation slope {slope_clean:.4f} unexpectedly flat"
    assert abs(slope_atk) < 0.3 * abs(slope_clean), (
        f"spoofed slope {slope_atk:.4f} did not collapse relative to clean {slope_clean:.4f}")


def test_determinism_of_attack_chain():
    def run():
        atk = DriftInSpoof(onset_s=5.0, align_s=2.0, duration_s=20.0, severity=0.5)
        return _run_with_attack(atk, duration_s=30.0, seed=99)
    r1, r2 = run(), run()
    for (t1, f1, l1, _), (t2, f2, l2, _) in zip(r1, r2):
        assert t1 == t2
        assert l1.kind == l2.kind
        if f1.valid and f2.valid:
            assert np.allclose(f1.pos, f2.pos)
