"""Jamming attacks: CW and wideband/chirp, and jam-then-spoof combination.

Effective C/N0 under interference (jamming-to-signal degradation formula):
  (C/N0)_eff^-1 = (C/N0)_nominal^-1 + (J/S) / (Q * R_c)
Standard GNSS anti-jam literature form (interference reduces effective C/N0
by an amount proportional to J/S normalised by a waveform-dependent factor Q
and the chipping rate R_c). Source: Kaplan & Hegarty, "Understanding
GPS/GNSS", 3rd ed., 2017, Ch. 6 (interference & jamming performance,
effective carrier-to-noise degradation). Q depends on jammer waveform vs.
C/A code spreading: Q~=1 for wideband/broadband noise fully covering the
signal bandwidth (matched degradation), Q~=2/3 for a CW tone (per Betz,
J.W., "Effect of Narrowband Interference on GPS Code Tracking Accuracy",
Proc. ION NTM 2000 -- qualitative CW-vs-wideband factor; exact Q=2/3 value
used here is an ASSUMPTION consistent with that paper's narrowband-vs-wideband
discussion, not a verbatim number from it -> flagged ASSUMPTION).

J/S from jammer geometry: J/S (dB) = EIRP_J(dBW) - FSPL(d)(dB) - S_rx(dBW),
free-space path loss FSPL(d) = 20log10(4*pi*d*f/c) (standard Friis/FSPL
relation, e.g. Kaplan & Hegarty Ch.6). S_rx (received GNSS signal power) for
L1 C/A is taken as the typical minimum specified power -158.5 dBW (GPS
ICD-200 minimum received power spec, widely cited).

AGC response: front-end AGC reduces reported gain roughly linearly with
J/N (jammer-to-noise ratio) until saturating at a configured max backoff --
qualitative behaviour per Kaplan & Hegarty Ch.6; the linear slope used here
is an ASSUMPTION (no single-number citation available).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from fedqpnt.core.types import AttackLabel, GnssEpoch, TruthState, C_LIGHT
from fedqpnt.attacks.base import is_active, ramp_factor

L1_FREQ_HZ = 1575.42e6
CHIP_RATE_CA_HZ = 1.023e6
S_RX_DBW = -158.5   # GPS ICD-200 minimum specified received L1 C/A power


def fspl_db(distance_m: float, freq_hz: float = L1_FREQ_HZ) -> float:
    distance_m = max(distance_m, 1.0)
    return 20 * np.log10(4 * np.pi * distance_m * freq_hz / C_LIGHT)


def js_ratio_db(jammer_eirp_dbw: float, distance_m: float) -> float:
    return jammer_eirp_dbw - fspl_db(distance_m) - S_RX_DBW


def effective_cn0_dbhz(cn0_nominal_dbhz: float, js_db: float, q_factor: float,
                        chip_rate_hz: float = CHIP_RATE_CA_HZ) -> float:
    cn0_lin = 10 ** (cn0_nominal_dbhz / 10.0)
    js_lin = 10 ** (js_db / 10.0)
    inv = (1.0 / cn0_lin) + js_lin / (q_factor * chip_rate_hz)
    return 10 * np.log10(1.0 / inv)


@dataclass
class Jamming:
    """CW or wideband/chirp jammer. Severity maps to jammer distance (closer
    = stronger). A moving victim => J/S changes with rx_pos-jammer_pos each
    epoch (free-space path loss)."""
    onset_s: float = 30.0
    duration_s: float | None = 60.0
    ramp_s: float = 2.0
    off_ramp_s: float = 2.0
    kind: str = "jam_wideband"       # "jam_cw" or "jam_wideband"
    jammer_pos_enu: np.ndarray = field(default_factory=lambda: np.array([500.0, 0.0, 0.0]))
    jammer_eirp_dbw: float = 10.0    # ~ handheld/vehicle jammer class, ASSUMPTION
    severity: float = 0.6            # scales effective EIRP (closer-equivalent / stronger)
    agc_max_drop_db: float = 20.0
    agc_slope: float = 0.8           # dB AGC drop per dB J/N, ASSUMPTION

    def config(self) -> dict:
        q = 2.0 / 3.0 if self.kind == "jam_cw" else 1.0
        return dict(kind=self.kind, onset_s=self.onset_s, duration_s=self.duration_s,
                    jammer_pos_enu=self.jammer_pos_enu.tolist(), jammer_eirp_dbw=self.jammer_eirp_dbw,
                    severity=self.severity, q_factor=q, agc_max_drop_db=self.agc_max_drop_db,
                    agc_slope=self.agc_slope, source="Kaplan & Hegarty 2017 Ch.6; see module docstring")

    def label(self, t: float) -> AttackLabel:
        active = is_active(t, self.onset_s, self.duration_s, self.off_ramp_s)
        return AttackLabel(t=t, spoofing=False, jamming=active, kind=self.kind if active else "none",
                            severity=self.severity if active else 0.0)

    def apply(self, epoch: GnssEpoch, truth: TruthState, rng: np.random.Generator) -> GnssEpoch:
        t = epoch.t
        if not is_active(t, self.onset_s, self.duration_s, self.off_ramp_s):
            return epoch
        env = ramp_factor(t, self.onset_s, self.ramp_s, self.duration_s, self.off_ramp_s)
        eirp_eff = self.jammer_eirp_dbw + 10.0 * np.log10(max(self.severity, 1e-3)) + 10.0 * env
        dist = float(np.linalg.norm(truth.pos - self.jammer_pos_enu))
        js_db = js_ratio_db(eirp_eff, dist)
        q = 2.0 / 3.0 if self.kind == "jam_cw" else 1.0

        jn_db = js_db + S_RX_DBW - (-201.0)  # J/N: noise floor kT ~ -201.5 dBW/Hz *1Hz ref, ASSUMPTION ref bw
        agc_drop = -min(max(self.agc_slope * max(js_db - (-10.0), 0.0), 0.0), self.agc_max_drop_db) * env

        new_obs = []
        for o in epoch.obs:
            o2 = _copy_satobs(o)
            cn0_eff = effective_cn0_dbhz(o.cn0_dbhz, js_db, q)
            o2.cn0_dbhz = o.cn0_dbhz + env * (cn0_eff - o.cn0_dbhz)
            new_obs.append(o2)
        return GnssEpoch(t=epoch.t, obs=new_obs, agc_db=epoch.agc_db + agc_drop,
                          noise_floor_db=epoch.noise_floor_db + max(js_db, 0.0) * env,
                          meta=dict(epoch.meta))


@dataclass
class JamThenSpoof:
    """Combined attack: jamming forces lock loss, then (once jamming eases or
    after a hold) a drift-in spoof captures the reacquiring receiver.
    Common real-world pattern noted qualitatively in Psiaki & Humphreys 2016
    Proc. IEEE (jam-to-degrade-then-spoof-to-capture); exact timing here is
    an ASSUMPTION scenario design, not a cited numeric sequence."""
    jam: "Jamming"
    spoof: "object"   # DriftInSpoof, onset should be >= jam onset+duration typically

    def config(self) -> dict:
        return dict(kind="jam_then_spoof", jam=self.jam.config(), spoof=self.spoof.config())

    def label(self, t: float) -> AttackLabel:
        jl = self.jam.label(t)
        sl = self.spoof.label(t)
        if jl.jamming and sl.spoofing:
            return AttackLabel(t=t, spoofing=True, jamming=True, kind="jam_then_spoof",
                                severity=max(jl.severity, sl.severity))
        if jl.jamming:
            return jl
        if sl.spoofing:
            return sl
        return AttackLabel(t=t, spoofing=False, jamming=False, kind="none", severity=0.0)

    def apply(self, epoch: GnssEpoch, truth: TruthState, rng: np.random.Generator) -> GnssEpoch:
        epoch = self.jam.apply(epoch, truth, rng)
        epoch = self.spoof.apply(epoch, truth, rng)
        return epoch


def _copy_satobs(o):
    from copy import copy
    return copy(o)
