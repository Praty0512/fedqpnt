"""Displaced (remote-antenna) meaconing attack, kind ``"meaconing_displaced"``.

Threat model (D-063/D-066, TRUST_SPLIT_DESIGN s7): a fixed ground antenna at
ENU position ``p_m`` records the live GNSS signal and rebroadcasts it after a
processing delay. The victim tracks the rebroadcast; every channel then
carries the geometry of the MEACONER antenna, so the victim's PVT solution
collapses onto ``p_m`` (with zero velocity, the antenna being static) and the
position error is ``|p_true - p_m|`` -- it grows as the victim moves away.
This differs from the co-located MeaconingReplay (spoofing.py, unchanged),
whose common delay is absorbed by the receiver clock bias.
Source: Psiaki & Humphreys, "GNSS Spoofing and Detection", Proc. IEEE 104(6),
2016 (record-and-rebroadcast, victim solution pinned to the meaconer
antenna); numeric parameters below are ASSUMPTIONS.

Model (delta-on-clean, per satellite i, envelope e(t) in [0,1] from the same
ramp as MeaconingReplay; s_i, v_i = satellite position/velocity):

  pr_i  = pr_clean_i + e * [ (|s_i-p_m| - |s_i-p|) + |p_m-p| + d ]
  prr_i = prr_clean_i + e * [ rr_i(p_m, v=0) - rr_i(p, v) + d/dt|p_m-p| ]
  cn0_i = cn0_clean_i + e * cn0_bump_db

  (|s_i-p_m| - |s_i-p|) : per-satellite geometry swap to the meaconer antenna
  |p_m-p|               : rebroadcast leg meaconer->victim (common mode -> clock)
  d = replay_delay_m * severity : processing delay (common mode -> clock)
  d/dt|p_m-p|           : rate of the rebroadcast leg (common mode -> drift)

The receiver clock bias therefore becomes true_clk + e*(d + |p_m-p|); the
fix position tends to p_m and the fix velocity to ~0 (rr(p_m, v=0)).
Clean-signal noise (thermal/multipath/atmosphere) is inherited (a meaconer
forwards the real signal), and the meaconer's own atmosphere/thermal
differences are neglected (ASSUMPTION, small vs the geometry term).

Meaconer placement: ``meacon_pos_enu`` (absolute) if given; otherwise the
antenna is placed ONCE, at onset, at
    p_m = p_victim(onset) + severity * D_max * direction_unit
(offset-from-victim-at-onset convention; latched on the first active epoch,
reset when inactive). Justification: scenarios are position-agnostic (the
trajectory generator's origin is arbitrary), and this makes severity map
directly to the initial position error, in the same way as severity scales
AbruptSpoof.jump_vector_enu / DriftInSpoof bounds. D_max = 500 m
(ASSUMPTION: a ground meaconer within line-of-sight range of a vehicle).
Error at time t after onset is |p_m - p(t)|, so the victim's motion away
from the antenna drives it up.

Truth-side channel: ``epoch.meta["injected_offset_m"]`` (float, |reported -
true| position offset = e*|p_m - p|), ``["injected_offset_enu_m"]`` (list of
3, reported minus true) and ``["meacon_pos_enu"]``. meta is environment
private (stripped by ``for_agent``). Absent on inactive epochs (use
``.get(..., 0.0)``).
"""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass, field

import numpy as np

from fedqpnt.core.types import AttackLabel, GnssEpoch, TruthState
from fedqpnt.attacks.base import is_active, ramp_factor
from fedqpnt.attacks.spoofing import _geom_delta

D_MAX_M = 500.0   # displacement at severity 1 (ASSUMPTION)


@dataclass
class DisplacedMeaconing:
    onset_s: float = 30.0
    duration_s: float | None = None
    ramp_s: float = 0.2
    off_ramp_s: float = 0.2
    replay_delay_m: float = 1500.0
    cn0_bump_db: float = 4.0
    severity: float = 0.5
    d_max_m: float = D_MAX_M
    direction_enu: np.ndarray = field(default_factory=lambda: np.array([0.6, 0.8, 0.0]))
    meacon_pos_enu: np.ndarray | None = None   # absolute override

    _pos_m: np.ndarray | None = field(default=None, repr=False)

    def config(self) -> dict:
        d = np.asarray(self.direction_enu, dtype=float)
        return dict(kind="meaconing_displaced", onset_s=self.onset_s, duration_s=self.duration_s,
                    replay_delay_m=self.replay_delay_m * self.severity, cn0_bump_db=self.cn0_bump_db,
                    severity=self.severity, d_max_m=self.d_max_m,
                    displacement_m=self.severity * self.d_max_m,
                    direction_enu=(d / np.linalg.norm(d)).tolist(),
                    meacon_pos_enu=None if self.meacon_pos_enu is None
                    else np.asarray(self.meacon_pos_enu, dtype=float).tolist())

    def label(self, t: float) -> AttackLabel:
        active = is_active(t, self.onset_s, self.duration_s, self.off_ramp_s)
        return AttackLabel(t=t, spoofing=active, jamming=False,
                            kind="meaconing_displaced" if active else "none",
                            severity=self.severity if active else 0.0)

    def _antenna(self, truth: TruthState) -> np.ndarray:
        if self.meacon_pos_enu is not None:
            return np.asarray(self.meacon_pos_enu, dtype=float)
        if self._pos_m is None:
            d = np.asarray(self.direction_enu, dtype=float)
            self._pos_m = np.asarray(truth.pos, dtype=float) + \
                self.severity * self.d_max_m * d / np.linalg.norm(d)
        return self._pos_m

    def apply(self, epoch: GnssEpoch, truth: TruthState, rng: np.random.Generator) -> GnssEpoch:
        t = epoch.t
        if not is_active(t, self.onset_s, self.duration_s, self.off_ramp_s):
            self._pos_m = None
            return epoch
        env = ramp_factor(t, self.onset_s, self.ramp_s, self.duration_s, self.off_ramp_s)
        p_m = self._antenna(truth)
        p = np.asarray(truth.pos, dtype=float)
        v = np.asarray(truth.vel, dtype=float)
        leg = p_m - p
        leg_len = float(np.linalg.norm(leg))
        leg_rate = float(np.dot(-leg / leg_len, v)) if leg_len > 1e-9 else 0.0   # d|p_m-p|/dt
        delay = self.replay_delay_m * self.severity
        bump = self.cn0_bump_db * env

        zero = np.zeros(3)
        new_obs = []
        for o in epoch.obs:
            d_range, d_rate = _geom_delta(o.sat_pos, o.sat_vel, p_m, zero, truth.pos, truth.vel)
            o2 = copy(o)
            o2.pseudorange = o.pseudorange + env * (d_range + leg_len + delay)
            o2.pseudorange_rate = o.pseudorange_rate + env * (d_rate + leg_rate)
            o2.cn0_dbhz = o.cn0_dbhz + bump
            new_obs.append(o2)

        meta = dict(epoch.meta)
        off = env * leg
        meta["injected_offset_m"] = float(np.linalg.norm(off))
        meta["injected_offset_enu_m"] = off.tolist()
        meta["meacon_pos_enu"] = p_m.tolist()
        return GnssEpoch(t=epoch.t, obs=new_obs, agc_db=epoch.agc_db + 0.3 * env,
                          noise_floor_db=epoch.noise_floor_db, meta=meta)
