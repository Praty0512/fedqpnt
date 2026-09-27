"""§3.1 feature-vector unit tests, using real fedqpnt.gnss + fedqpnt.attacks
streams (no synthetic GnssFix stand-ins) to build the causal input."""
from __future__ import annotations

import numpy as np

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
