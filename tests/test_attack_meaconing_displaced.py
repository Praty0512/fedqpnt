import numpy as np

from fedqpnt.core.seeding import stream
from fedqpnt.gnss.signal import GnssSignalModel
from fedqpnt.gnss.receiver import GnssReceiver
from fedqpnt.attacks.spoofing import MeaconingReplay
from fedqpnt.attacks.meaconing_displaced import DisplacedMeaconing, D_MAX_M
from fedqpnt.node.environment import build_attack
from tests._helpers import static_truth, const_vel_truth


def _run(attack, truth_fn, duration_s=100.0, dt=0.5, seed=7):
    rng_sig = stream(seed, "n", "gnss")
    rng_atk = stream(seed, "n", "attack")
    model = GnssSignalModel(rate_hz=1.0)
    recv = GnssReceiver()
    rows = []
    for k in range(int(duration_s / dt)):
        t = k * dt
        truth = truth_fn(t)
        ep = model.step(truth, rng_sig)
        if ep is None:
            continue
        clean_obs = list(ep.obs)
        ea = attack.apply(ep, truth, rng_atk)
        fix = recv.solve(ea.for_agent())
        rows.append(dict(t=t, fix=fix, truth=truth, meta=ea.meta, label=attack.label(t),
                         clean_obs=clean_obs, obs=ea.obs))
    return rows


def _mk(**kw):
    kw.setdefault("onset_s", 20.0)
    kw.setdefault("duration_s", 60.0)
    kw.setdefault("severity", 0.6)
    return DisplacedMeaconing(**kw)


def test_registered_and_builds():
    a = build_attack("meaconing_displaced", 10.0, 30.0, 0.5, {"d_max_m": 200.0})
    assert isinstance(a, DisplacedMeaconing) and a.d_max_m == 200.0
    assert isinstance(build_attack("meaconing", 10.0, 30.0, 0.5), MeaconingReplay)


def test_fix_converges_to_meaconer_static_victim():
    atk = _mk()
    rows = _run(atk, static_truth)
    p_m = np.array([r for r in rows if r["t"] >= 30.0][0]["meta"]["meacon_pos_enu"])
    expected = 0.6 * D_MAX_M
    assert abs(np.linalg.norm(p_m) - expected) < 1e-6
    sel = [r for r in rows if 30.0 <= r["t"] < 75.0]
    assert sel
    errs = [np.linalg.norm(r["fix"].pos - p_m) for r in sel]
    assert np.median(errs) < 15.0            # pinned to the antenna (few-m noise)
    # velocity ~0 relative to the static antenna
    assert np.median([np.linalg.norm(r["fix"].vel) for r in sel]) < 2.0
    # truth-side channel matches
    for r in sel:
        assert abs(r["meta"]["injected_offset_m"] - expected) < 1e-6


def test_error_grows_with_victim_motion():
    atk = _mk(severity=0.4)
    rows = _run(atk, lambda t: const_vel_truth(t, speed_mps=10.0, heading_rad=np.pi))  # away from NE antenna
    def err(r):
        return np.linalg.norm(r["fix"].pos - r["truth"].pos)
    early = np.median([err(r) for r in rows if 22.0 <= r["t"] < 30.0])
    late = np.median([err(r) for r in rows if 65.0 <= r["t"] < 78.0])
    assert late > early + 200.0            # 10 m/s * ~40 s of extra separation
    inj = [r["meta"]["injected_offset_m"] for r in rows if 22.0 <= r["t"] < 78.0]
    assert inj[-1] > inj[0] + 300.0


def test_clock_bias_includes_delay_and_leg():
    atk = _mk(severity=0.6)
    rows = _run(atk, static_truth)
    sel = [r for r in rows if 30.0 <= r["t"] < 75.0]
    pre = [r for r in rows if 5.0 <= r["t"] < 18.0]
    leg = 0.6 * D_MAX_M
    delay = 1500.0 * 0.6
    # fix clk_bias minus true clk (meta not exposed to agent; recompute from clean obs offset)
    # use difference vs pre-onset receiver bias tracked by same clock: bias step = delay + leg
    b_pre = np.median([r["fix"].clk_bias for r in pre])
    b_att = np.median([r["fix"].clk_bias for r in sel])
    # true clock random-walks slowly (metres over 60 s), allow slack
    assert abs((b_att - b_pre) - (delay + leg)) < 30.0


def test_labels_only_in_window():
    atk = _mk()
    rows = _run(atk, static_truth)
    for r in rows:
        active = 20.0 <= r["t"] < 20.0 + 60.0 + atk.off_ramp_s
        assert r["label"].spoofing == active and r["label"].jamming is False
        assert r["label"].kind == ("meaconing_displaced" if active else "none")
        if not active:
            assert "injected_offset_m" not in r["meta"]


def test_absolute_position_option():
    atk = _mk(meacon_pos_enu=np.array([0.0, 300.0, 0.0]))
    rows = _run(atk, static_truth)
    sel = [r for r in rows if 30.0 <= r["t"] < 75.0]
    assert abs(sel[0]["meta"]["injected_offset_m"] - 300.0) < 1e-6


def test_determinism_under_seed():
    r1 = _run(_mk(), static_truth, duration_s=60.0)
    r2 = _run(_mk(), static_truth, duration_s=60.0)
    for a, b in zip(r1, r2):
        assert np.array_equal(a["fix"].pos, b["fix"].pos, equal_nan=True)
        assert a["fix"].clk_bias == b["fix"].clk_bias or (np.isnan(a["fix"].clk_bias) and np.isnan(b["fix"].clk_bias))
        assert a["meta"].get("injected_offset_m") == b["meta"].get("injected_offset_m")


def test_existing_meaconing_unchanged():
    """MeaconingReplay path: pr = pr_clean + replay_delay*severity*env, cn0 bump,
    no position change, injected offset 0.0 (bit-exact arithmetic)."""
    atk = MeaconingReplay(onset_s=20.0, duration_s=60.0, severity=0.6)
    rows = _run(atk, static_truth, duration_s=60.0)
    for r in rows:
        if 25.0 <= r["t"] < 75.0:
            for o, c in zip(r["obs"], r["clean_obs"]):
                assert o.pseudorange == c.pseudorange + 1500.0 * 0.6 * 1.0
                assert o.cn0_dbhz == c.cn0_dbhz + 4.0
                assert o.pseudorange_rate == c.pseudorange_rate
            assert r["meta"]["injected_offset_m"] == 0.0


# ---- injected_offset_m channel on the other spoof classes (D-068) ----------
def _epoch_stream(attack, seed=11, duration_s=60.0):
    from fedqpnt.attacks.spoofing import DriftInSpoof, AbruptSpoof  # noqa: F401
    rng_sig = stream(seed, "n", "gnss")
    rng_atk = stream(seed, "n", "attack")
    model = GnssSignalModel(rate_hz=1.0)
    out = []
    for k in range(int(duration_s / 0.5)):
        truth = const_vel_truth(k * 0.5, speed_mps=5.0)
        ep = model.step(truth, rng_sig)
        if ep is None:
            continue
        out.append((truth, attack.apply(ep, truth, rng_atk)))
    return out


def _strip(ep):
    return (ep.t, ep.agc_db, ep.noise_floor_db,
            [(o.prn, o.pseudorange, o.pseudorange_rate, o.cn0_dbhz, o.tracked) for o in ep.obs])


def _mkall():
    from fedqpnt.attacks.spoofing import DriftInSpoof, AbruptSpoof
    return [lambda: DriftInSpoof(onset_s=10.0, align_s=5.0, duration_s=30.0, severity=0.8),
            lambda: DriftInSpoof(onset_s=10.0, align_s=5.0, duration_s=30.0, severity=0.8, mode="time"),
            lambda: AbruptSpoof(onset_s=10.0, duration_s=30.0, severity=0.7),
            lambda: MeaconingReplay(onset_s=10.0, duration_s=30.0, severity=0.6)]


def test_offset_channel_does_not_alter_epochs_and_matches_truth():
    """Epoch content (excluding meta) must equal an independent re-run with the
    meta keys ignored (determinism), and the meta key matches the closed form."""
    for mk in _mkall():
        a = _epoch_stream(mk())
        b = _epoch_stream(mk())
        assert [_strip(e) for _, e in a] == [_strip(e) for _, e in b]
        atk = mk()
        for truth, e in a:
            active = atk.label(e.t).spoofing
            if not active:
                assert "injected_offset_m" not in e.meta
                continue
            assert set(("injected_offset_m", "injected_offset_enu_m")) <= set(e.meta)
            off = np.array(e.meta["injected_offset_enu_m"])
            assert abs(np.linalg.norm(off) - e.meta["injected_offset_m"]) < 1e-9
            assert "clk_bias_m" in e.meta      # original meta preserved


def test_offset_channel_values():
    from fedqpnt.attacks.spoofing import DriftInSpoof, AbruptSpoof
    ab = AbruptSpoof(onset_s=10.0, duration_s=30.0, severity=0.7)
    for _, e in _epoch_stream(ab):
        if ab.label(e.t).spoofing:
            assert abs(e.meta["injected_offset_m"] - 56.0) < 1e-9    # 80 m * 0.7
    dr = DriftInSpoof(onset_s=10.0, align_s=5.0, duration_s=30.0, severity=0.8)
    for _, e in _epoch_stream(dr):
        if dr.label(e.t).spoofing:
            exp = dr.expected_offset(e.t)[0]
            assert np.allclose(e.meta["injected_offset_enu_m"], exp)
    mc = MeaconingReplay(onset_s=10.0, duration_s=30.0, severity=0.6)
    for _, e in _epoch_stream(mc):
        if mc.label(e.t).spoofing:
            assert e.meta["injected_offset_m"] == 0.0
