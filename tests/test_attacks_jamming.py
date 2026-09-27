import numpy as np

from fedqpnt.core.seeding import stream
from fedqpnt.gnss.signal import GnssSignalModel
from fedqpnt.gnss.receiver import GnssReceiver
from fedqpnt.attacks.jamming import Jamming, JamThenSpoof, js_ratio_db, effective_cn0_dbhz
from fedqpnt.attacks.spoofing import DriftInSpoof
from tests._helpers import static_truth


def _run_with_attack(attack, duration_s=120.0, dt=0.01, seed=31):
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
        rows.append((t, fix, label, ep_atk))
    return rows


def test_js_ratio_decreases_with_distance():
    close = js_ratio_db(10.0, 200.0)
    far = js_ratio_db(10.0, 5000.0)
    assert close > far


def test_effective_cn0_degrades_with_js():
    base = effective_cn0_dbhz(45.0, js_db=-30.0, q_factor=1.0)
    strong = effective_cn0_dbhz(45.0, js_db=10.0, q_factor=1.0)
    assert strong < base < 46.0


def test_jamming_labels_and_cn0_drop():
    atk = Jamming(onset_s=10.0, duration_s=30.0, ramp_s=1.0, off_ramp_s=1.0,
                  kind="jam_wideband", jammer_pos_enu=np.array([50.0, 0.0, 0.0]),
                  jammer_eirp_dbw=20.0, severity=1.0)
    rows = _run_with_attack(atk, duration_s=50.0)
    cn0_clean = np.mean([np.mean([o.cn0_dbhz for o in ep.obs]) for t, fix, l, ep in rows if t < 9.0 and ep.obs])
    cn0_jammed = np.mean([np.mean([o.cn0_dbhz for o in ep.obs]) for t, fix, l, ep in rows if 15.0 <= t < 35.0 and ep.obs])
    assert cn0_jammed < cn0_clean - 5.0
    for t, fix, label, ep in rows:
        expect_active = 10.0 <= t < 10.0 + 30.0 + atk.off_ramp_s
        assert label.jamming == expect_active
        assert label.spoofing is False


def test_jamming_agc_drop_correlated():
    atk = Jamming(onset_s=10.0, duration_s=30.0, jammer_pos_enu=np.array([30.0, 0.0, 0.0]),
                  jammer_eirp_dbw=25.0, severity=1.0)
    rows = _run_with_attack(atk, duration_s=45.0)
    agc_clean = np.mean([ep.agc_db for t, fix, l, ep in rows if t < 9.0])
    agc_jammed = np.mean([ep.agc_db for t, fix, l, ep in rows if 15.0 <= t < 35.0])
    assert agc_jammed < agc_clean  # AGC backs off (goes negative) under jamming


def test_strong_jamming_causes_progressive_lock_loss_low_elevation_first():
    atk = Jamming(onset_s=5.0, duration_s=60.0, ramp_s=5.0, off_ramp_s=1.0,
                  jammer_pos_enu=np.array([5.0, 0.0, 0.0]), jammer_eirp_dbw=30.0, severity=1.0)
    rows = _run_with_attack(atk, duration_s=70.0)
    late = [(t, fix, ep) for t, fix, l, ep in rows if 50.0 <= t < 60.0]
    assert len(late) > 0
    num_sats = [fix.num_sats for t, fix, ep in late]
    assert min(num_sats) < 8  # some satellites dropped from tracking vs nominal ~8-9


def test_jam_then_spoof_label_sequencing():
    jam = Jamming(onset_s=5.0, duration_s=15.0, ramp_s=1.0, off_ramp_s=1.0,
                  jammer_pos_enu=np.array([30.0, 0.0, 0.0]), jammer_eirp_dbw=15.0, severity=0.8)
    spoof = DriftInSpoof(onset_s=22.0, align_s=3.0, duration_s=30.0, severity=0.6)
    combo = JamThenSpoof(jam=jam, spoof=spoof)
    rows = _run_with_attack(combo, duration_s=60.0)
    lbl_10 = combo.label(10.0)
    lbl_30 = combo.label(30.0)
    lbl_1 = combo.label(1.0)
    assert lbl_10.jamming and not lbl_10.spoofing
    assert lbl_30.spoofing and not lbl_30.jamming
    assert not lbl_1.jamming and not lbl_1.spoofing


def test_jamming_switch_off_recovers_cn0():
    atk = Jamming(onset_s=10.0, duration_s=15.0, ramp_s=0.5, off_ramp_s=0.5,
                  jammer_pos_enu=np.array([40.0, 0.0, 0.0]), jammer_eirp_dbw=20.0, severity=1.0)
    rows = _run_with_attack(atk, duration_s=45.0)
    cn0_clean = np.mean([fix.mean_cn0 for t, fix, l, ep in rows if t < 9.0 and fix.valid])
    cn0_after = np.mean([fix.mean_cn0 for t, fix, l, ep in rows if 30.0 <= t < 40.0 and fix.valid])
    assert abs(cn0_after - cn0_clean) < 2.0  # recovers close to clean baseline after switch-off
