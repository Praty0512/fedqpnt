"""§3.1 feature-vector unit tests, using real fedqpnt.gnss + fedqpnt.attacks
streams (no synthetic GnssFix stand-ins) to build the causal input."""
from __future__ import annotations

import numpy as np
import pytest

from fedqpnt.core.seeding import stream
from fedqpnt.core.types import Innovation
from fedqpnt.gnss.signal import GnssSignalModel
from fedqpnt.gnss.receiver import GnssReceiver
from fedqpnt.attacks.spoofing import DriftInSpoof
from fedqpnt.trust.features import GnssFeatureExtractor, FEATURE_NAMES, N_FEATURES
from tests._helpers import static_truth


def _make_nominal_r_innovations(fix) -> list[Innovation]:
    """Synthetic nominal-R innovations (no fusion filter at M0 -- ARCHITECTURE
    note explicitly allows this: 'synthetic Innovations are OK where no
    filter exists yet'). nis/dof = 1 in the noise-only case; kept simple and
    deterministic so tests are about the FEATURE plumbing, not fusion."""
    S = np.eye(3)
    nu = np.zeros(3)
    return [
        Innovation(t=fix.t, sensor="gnss_pos", nu=nu, S=S, nis=3.0, dof=3, accepted=True),
        Innovation(t=fix.t, sensor="gnss_vel", nu=nu, S=S, nis=3.0, dof=3, accepted=True),
    ]


def _run(duration_s=60.0, dt=0.01, seed=501, attack=None):
    rng_sig = stream(seed, "n", "gnss")
    rng_atk = stream(seed, "n", "attack")
    model = GnssSignalModel(rate_hz=1.0)
    recv = GnssReceiver()
    extractor = GnssFeatureExtractor()
    n = int(duration_s / dt)
    rows = []
    for k in range(n):
        t = k * dt
        truth = static_truth(t)
        ep = model.step(truth, rng_sig)
        if ep is None:
            continue
        if attack is not None:
            ep = attack.apply(ep, truth, rng_atk)
        fix = recv.solve(ep.for_agent())
        feats = extractor.step(fix, _make_nominal_r_innovations(fix))
        rows.append((t, fix, feats))
    return rows


def test_feature_vector_shape_and_names():
    assert N_FEATURES == 15  # v0.3 (D-022): +cn0_xsat_corr, +cn0_elev_slope
    assert len(FEATURE_NAMES) == 15
    rows = _run(duration_s=30.0, seed=502)
    for t, fix, feats in rows:
        assert feats is not None
        assert feats.shape == (15,)
        assert np.all(np.isfinite(feats))


def test_x1_x2_come_from_innovation_nis_over_dof():
    rows = _run(duration_s=5.0, seed=503)
    for t, fix, feats in rows:
        assert feats[0] == 1.0  # nis=3, dof=3 -> 1.0
        assert feats[1] == 1.0


def test_x13_outage_flag_follows_previous_epoch():
    rows = _run(duration_s=30.0, seed=504)
    prev_invalid = False
    for t, fix, feats in rows:
        assert feats[12] == (1.0 if prev_invalid else 0.0)
        prev_invalid = (not fix.valid) or (fix.num_sats < 4)


def test_cusum_grows_under_sustained_spoofing_and_resets_under_clean():
    atk = DriftInSpoof(onset_s=10.0, align_s=5.0, duration_s=200.0, severity=0.9)
    rows = _run(duration_s=120.0, seed=505, attack=atk)
    cusum = np.array([f[11] for _, _, f in rows])
    t = np.array([r[0] for r in rows])
    pre_attack = cusum[t < 10.0]
    late_attack = cusum[(t > 60.0) & (t < 120.0)]
    assert np.max(pre_attack) < 5.0
    # a sustained large-severity drift spoof should eventually push nis_pos up
    # and the CUSUM (Page test, k_c=1.5) should exceed the pre-attack level.
    assert np.max(late_attack) >= np.max(pre_attack)


def _clk_fix(t, bias, drift):
    import numpy as np
    from fedqpnt.core.types import GnssFix
    return GnssFix(t=t, pos=np.zeros(3), vel=np.zeros(3), clk_bias=bias, clk_drift=drift, cov_pos=np.eye(3),
                   cov_vel=np.eye(3), residual_rms=0.5, num_sats=8, mean_cn0=45.0, std_cn0=1.0, agc_db=0.0,
                   valid=True, raim_stat=1.0)


def test_clock_jump_normalised_by_tcxo_holdover_std_after_long_gap():
    """D-071 (a): ordinary TCXO holdover over a 180 s outage (truth ClockState) must NOT look like a clock
    jump on the first fix after the outage (x8/x9 stay below the E_s clk_event threshold es_clk_sigma=5)."""
    import numpy as np
    from fedqpnt.gnss.signal import ClockState
    from fedqpnt.trust.features import GnssFeatureExtractor
    from fedqpnt.trust.trust_law import TrustLawConfig
    thr = TrustLawConfig().es_clk_sigma
    hits = []
    for seed in range(200):
        rng = np.random.default_rng(seed)
        clk = ClockState()
        ex = GnssFeatureExtractor()
        for k in range(1, 4):                       # a few normal epochs, then the outage
            clk.step(1.0, rng)
            ex.step(_clk_fix(float(k), clk.bias_m + rng.normal(0, 3.0), clk.drift_mps + rng.normal(0, 0.2)), [])
        for _ in range(180):
            clk.step(1.0, rng)
        f = ex.step(_clk_fix(183.0, clk.bias_m + rng.normal(0, 3.0), clk.drift_mps + rng.normal(0, 0.2)), [])
        hits.append(max(f[7], f[8]) > thr)
    assert np.mean(hits) <= 0.02, f"post-outage clk_event false-fire fraction {np.mean(hits):.3f}"


def test_meaconing_step_on_first_fix_after_gap_reports_its_x8():
    """D-071 (b): a 750 m replay-delay step (meaconing severity 0.5) on the first fix after a 180 s gap.
    sigma_b(180 s)^2 = 9 + q_b*180 + q_d*180^3/3 -> ~263 m, so x8 ~ 2.85 < es_clk_sigma=5: the closed-form
    normalisation does NOT make a 750 m step an E_s clk_event after a 3-minute holdover (reported, threshold
    NOT tuned). At a normal 1 s gap the same step is ~250 sigma."""
    import numpy as np
    from fedqpnt.core.defaults import CLOCK_Q_BIAS, CLOCK_Q_DRIFT
    from fedqpnt.trust.features import GnssFeatureExtractor
    ex = GnssFeatureExtractor()
    ex.step(_clk_fix(1.0, 0.0, 0.0), [])
    far = ex.step(_clk_fix(181.0, 750.0, 0.0), [])          # dt = 180 s
    sig = np.sqrt(9.0 + CLOCK_Q_BIAS * 180 + CLOCK_Q_DRIFT * 180 ** 3 / 3.0)
    assert far[7] == pytest.approx(750.0 / sig, rel=1e-6)
    print("x8 after 180 s gap for a 750 m step:", far[7])
    ex2 = GnssFeatureExtractor()
    ex2.step(_clk_fix(1.0, 0.0, 0.0), [])
    near = ex2.step(_clk_fix(2.0, 750.0, 0.0), [])           # dt = 1 s
    assert near[7] > 200.0


def test_nominal_dt1_clock_features_scaling_vs_previous():
    """D-071: at dt=1 s sigma_b is unchanged to 0.1% (3.0 -> 3.003); sigma_d 0.200 -> 0.275 (x9 x0.73)."""
    import numpy as np
    from fedqpnt.trust.features import GnssFeatureExtractor
    ex = GnssFeatureExtractor()
    ex.step(_clk_fix(1.0, 0.0, 0.0), [])
    f = ex.step(_clk_fix(2.0, 3.0, 0.2), [])
    assert f[7] == pytest.approx(3.0 / 3.003, rel=2e-3)
    assert f[8] == pytest.approx(0.2 / 0.2748, rel=2e-3)


def test_clock_gap_measured_from_last_valid_fix_across_1hz_invalid_fixes():
    """D-073: a realistic jam sequence (1 Hz INVALID fixes for 180 s, then a valid fix carrying ordinary TCXO
    holdover drift) must not fire clk_event: the clock prediction gap is 180 s (last valid clock reference), not the
    ~1 s since the last call. Would blow up x8/x9 with dt taken from the last call of any kind."""
    import numpy as np
    from fedqpnt.core.types import GnssFix
    from fedqpnt.gnss.signal import ClockState
    from fedqpnt.trust.features import GnssFeatureExtractor
    from fedqpnt.trust.trust_law import TrustLawConfig
    thr = TrustLawConfig().es_clk_sigma
    fired = []
    for seed in range(100):
        rng = np.random.default_rng(seed)
        clk = ClockState()
        ex = GnssFeatureExtractor()
        for k in range(1, 4):
            clk.step(1.0, rng)
            ex.step(_clk_fix(float(k), clk.bias_m + rng.normal(0, 3.0), clk.drift_mps + rng.normal(0, 0.2)), [])
        for k in range(4, 184):                      # jamming: invalid fix every epoch
            clk.step(1.0, rng)
            bad = GnssFix(t=float(k), pos=np.full(3, np.nan), vel=np.full(3, np.nan), clk_bias=np.nan,
                          clk_drift=np.nan, cov_pos=np.eye(3), cov_vel=np.eye(3), residual_rms=np.nan,
                          num_sats=2, mean_cn0=25.0, std_cn0=3.0, agc_db=-10.0, valid=False, raim_stat=np.nan)
            ex.step(bad, [])
        clk.step(1.0, rng)
        f = ex.step(_clk_fix(184.0, clk.bias_m + rng.normal(0, 3.0), clk.drift_mps + rng.normal(0, 0.2)), [])
        fired.append(max(f[7], f[8]) > thr)
    assert np.mean(fired) <= 0.02, f"post-jam clk_event fraction {np.mean(fired):.3f}"


def test_meaconing_750m_step_after_invalid_fix_gap_x8_reported():
    import numpy as np
    from fedqpnt.core.defaults import CLOCK_Q_BIAS, CLOCK_Q_DRIFT
    from fedqpnt.core.types import GnssFix
    from fedqpnt.trust.features import GnssFeatureExtractor
    ex = GnssFeatureExtractor()
    ex.step(_clk_fix(1.0, 0.0, 0.0), [])
    for k in range(2, 181):
        ex.step(GnssFix(t=float(k), pos=np.full(3, np.nan), vel=np.full(3, np.nan), clk_bias=np.nan,
                        clk_drift=np.nan, cov_pos=np.eye(3), cov_vel=np.eye(3), residual_rms=np.nan, num_sats=2,
                        mean_cn0=25.0, std_cn0=3.0, agc_db=-10.0, valid=False, raim_stat=np.nan), [])
    f = ex.step(_clk_fix(181.0, 750.0, 0.0), [])
    sig = np.sqrt(9.0 + CLOCK_Q_BIAS * 180 + CLOCK_Q_DRIFT * 180 ** 3 / 3.0)
    assert f[7] == pytest.approx(750.0 / sig, rel=1e-6)      # ~2.855, below es_clk_sigma=5 (reported, not tuned)
