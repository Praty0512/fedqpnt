"""Test-local (not part of fedqpnt.trust) harness building real GNSS +
attack runs for trust/detector validation. Mirrors tests/_helpers.py: this
file is allowed to import fedqpnt.attacks / truth because it lives in
tests/, never in fedqpnt/trust/ (the leakage guard only scans the package).

Innovations are SYNTHETIC (no fusion filter exists at M0 -- explicitly
permitted by the TRUST validation brief): nu = fix - truth, S = fix's own
reported covariance (nominal R, kappa_R=1), which is a reasonable physical
stand-in for a pre-correction EKF innovation. Truth is used only here, to
build this proxy -- never inside fedqpnt/trust.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fedqpnt.core.seeding import stream
from fedqpnt.core.types import AttackLabel, Innovation
from fedqpnt.gnss.signal import GnssSignalModel
from fedqpnt.gnss.receiver import GnssReceiver
from fedqpnt.attacks.spoofing import DriftInSpoof, MeaconingReplay, AbruptSpoof
from fedqpnt.attacks.jamming import Jamming
from fedqpnt.trust.features import GnssFeatureExtractor
from tests._helpers import static_truth, const_vel_truth


def _make_attack(family: str):
    if family == "clean":
        return None
    if family == "drift":
        return DriftInSpoof(onset_s=20.0, align_s=5.0, duration_s=60.0, severity=0.5)
    if family == "meaconing":
        return MeaconingReplay(onset_s=20.0, duration_s=60.0, severity=0.6)
    if family == "abrupt":
        return AbruptSpoof(onset_s=20.0, duration_s=60.0, severity=0.7)
    if family == "jamming":
        return Jamming(onset_s=20.0, duration_s=60.0, kind="jam_wideband", severity=0.6)
    raise ValueError(family)


FAMILIES = ("drift", "meaconing", "abrupt", "jamming")


@dataclass
class RunData:
    t: np.ndarray
    raw_features: np.ndarray   # (N, 13)
    raim_stat: np.ndarray
    num_sats: np.ndarray
    oracle_active: np.ndarray  # bool (N,) spoofing OR jamming
    family: str
    seed: int


def generate_run(seed: int, family: str, duration_s: float = 60.0, dt: float = 0.01) -> RunData:
    rng_sig = stream(seed, "n", "gnss")
    rng_atk = stream(seed, "n", "attack")
    model = GnssSignalModel(rate_hz=1.0)
    recv = GnssReceiver()
    extractor = GnssFeatureExtractor()
    attack = _make_attack(family)

    n = int(duration_s / dt)
    t_list, feat_list, raim_list, nsat_list, active_list = [], [], [], [], []
    for k in range(n):
        t = k * dt
        truth = const_vel_truth(t, speed_mps=5.0, heading_rad=0.3)
        ep = model.step(truth, rng_sig)
        if ep is None:
            continue
        if attack is not None:
            ep = attack.apply(ep, truth, rng_atk)
        fix = recv.solve(ep.for_agent())

        if fix.valid:
            nu_p = fix.pos - truth.pos
            nu_v = fix.vel - truth.vel
            Sp = fix.cov_pos if np.all(np.isfinite(fix.cov_pos)) else np.eye(3) * 100.0
            Sv = fix.cov_vel if np.all(np.isfinite(fix.cov_vel)) else np.eye(3) * 4.0
            nis_p = float(nu_p @ np.linalg.solve(Sp, nu_p))
            nis_v = float(nu_v @ np.linalg.solve(Sv, nu_v))
            innovations = [
                Innovation(t=t, sensor="gnss_pos", nu=nu_p, S=Sp, nis=nis_p, dof=3, accepted=True),
                Innovation(t=t, sensor="gnss_vel", nu=nu_v, S=Sv, nis=nis_v, dof=3, accepted=True),
            ]
        else:
            innovations = []

        feats = extractor.step(fix, innovations)
        if feats is None:
            continue
        # NOTE (D-022 review): an earlier version dropped every invalid-fix
        # epoch here on the theory that "no valid fix = no evidence event".
        # That was itself a bug contributor: features.py used to ZERO x4-x7/
        # x11 on any outage too, so the only jamming epochs left in the
        # training/eval pool were the mild, still-valid ones -- which look
        # nearly clean, mislabelling jamming as negative. Now that
        # GnssFeatureExtractor reports REAL mean_cn0/std_cn0/agc_db/num_sats
        # even on an invalid fix (the strongest jamming evidence: near-zero
        # C/N0, deeply negative AGC, sats dropping out), these epochs are
        # kept: they carry real signal and TrustEngineImpl separately decides
        # not to run the trust-LAW update on them (valid-fix-only), which is
        # an unrelated, correct causal-engine concern.
        label: AttackLabel = attack.label(t) if attack is not None else AttackLabel(t=t, spoofing=False, jamming=False)

        t_list.append(t)
        feat_list.append(feats)
        raim_list.append(fix.raim_stat if np.isfinite(fix.raim_stat) else 0.0)
        nsat_list.append(fix.num_sats)
        active_list.append(bool(label.spoofing or label.jamming))

    return RunData(
        t=np.array(t_list), raw_features=np.array(feat_list),
        raim_stat=np.array(raim_list), num_sats=np.array(nsat_list),
        oracle_active=np.array(active_list, dtype=bool), family=family, seed=seed,
    )
