"""Spoofing attacks: gradual drift-in (carry-off), meaconing/replay, abrupt jump.

References:
  * Humphreys, T.E., Ledvina, B.M., Psiaki, M., O'Hanlon, B., Kintner, P.,
    "Assessing the Spoofing Threat: Development of a Portable GPS Civilian
    Spoofer", ION GNSS 2008 -- introduces the "carry-off" gradual spoofing
    concept: align to authentic signal with a small power advantage, then
    slowly drag the tracked code/carrier away while staying inside the victim
    receiver's tracking loop bandwidth, so pseudoranges stay geometrically
    self-consistent and naive RAIM does not flag the fix.
  * Humphreys, T.E. et al., "Texas Spoofing Test Battery (TEXBAT)", 2012
    (dataset description) -- typical carry-off drift rates used in TEXBAT
    scenarios are on the order of <=1 m/s^2 ramping to bounded velocity
    offsets; exact TEXBAT numeric bounds not independently re-derived here
    (UNVERIFIED exact figures), so drift accel/velocity bounds below are a
    literature-consistent ASSUMPTION, swept over severity in validation.
  * Power advantage during alignment: +3 to +10 dB typical to capture the
    tracking loop (Humphreys 2008, Sec. III) -- used directly as the
    configurable ``power_bump_db`` range.
  * Radoš, Brkić & Begušić, "Recent Advances on Jamming and Spoofing
    Detection in GNSS", Sensors 24(13):4210, 2024, Sec. 3.1.2: field test
    shows spoofed C/N0 in 35-55 dB-Hz vs 20-40 dB-Hz clean, and a 5 dB power
    advantage over the authentic signal yields 98% fake-signal detection by
    a signal-quality monitor -- consistent with the power_bump_db range used
    here.

v2 design (Master WP-3.x review round 2, DECISION): a spoofer overpowers and
re-radiates a locally-generated signal; it does NOT know the victim
receiver's secret internal clock state (``GnssEpoch.meta`` is
environment-private, D-009/C-4) and it does NOT erase the victim antenna's
own multipath or the receiver's own thermal tracking noise. So every spoofed
observable is built as a DELTA on the CLEAN observable the environment
already generated for this epoch:

    pr_spoof  = pr_clean  + (|sat - fake_pos| - |sat - true_pos|) + e_spoofer
    prr_spoof = prr_clean + (range_rate(fake) - range_rate(true))

``e_spoofer`` is the spoofer's own atmosphere-model mismatch (it predicts the
victim's iono/tropo delay to build a convincing fake signal, but not
perfectly) -- modelled as a per-satellite Gauss-Markov process, sigma=0.5 m,
tau=300 s (ASSUMPTION, no primary source for this specific figure; chosen
small relative to the ~2-4 m natural UERE budget so that snapshot RAIM stays
statistically blind to single-antenna, all-satellite carry-off/abrupt
spoofing, matching the literature's stated difficulty of naive-RAIM
detection of coordinated spoofing).

Receiver thermal noise: pr_clean already contains a thermal-noise draw at
the ORIGINAL (unspoofed) C/N0. When spoofing changes C/N0 (typically UP, via
the power-advantage bump), the true thermal sigma changes too; since the
original noise draw cannot be un-drawn, we add the INCREMENTAL sigma
(sqrt(max(sigma_new^2 - sigma_old^2, 0))) via the same DLL tracking-error
formula used by the signal model (fedqpnt.gnss.signal.code_thermal_sigma_m,
single source of truth). This only adds noise when the new C/N0 implies MORE
thermal jitter than the original (e.g. a small/negative bump); a pure power
increase (the common case) contributes zero extra noise here -- an
ASSUMPTION simplification flagged in the notes doc (we do not reduce the
already-realised thermal noise when C/N0 goes up).
"""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass, field

import numpy as np

from fedqpnt.core.types import AttackLabel, GnssEpoch, TruthState
from fedqpnt.attacks.base import is_active, ramp_factor
from fedqpnt.gnss.signal import code_thermal_sigma_m

# Spoofer atmosphere-model mismatch (ASSUMPTION, see module docstring).
SPOOFER_ATMOS_SIGMA_M = 0.5
SPOOFER_ATMOS_TAU_S = 300.0


def _gm_step(x: float, dt: float, tau: float, sigma: float, rng: np.random.Generator) -> float:
    phi = np.exp(-dt / tau) if dt > 0 else 1.0
    w_sigma = sigma * np.sqrt(max(1.0 - phi ** 2, 0.0))
    return phi * x + rng.normal(0.0, w_sigma)


def _geom_delta(sat_pos: np.ndarray, sat_vel: np.ndarray, fake_pos: np.ndarray, fake_vel: np.ndarray,
                 true_pos: np.ndarray, true_vel: np.ndarray) -> tuple[float, float]:
    """(range_fake - range_true, range_rate_fake - range_rate_true) for one satellite."""
    los_fake = sat_pos - fake_pos
    r_fake = float(np.linalg.norm(los_fake))
    u_fake = los_fake / r_fake
    rate_fake = -float(np.dot(sat_vel - fake_vel, u_fake))

    los_true = sat_pos - true_pos
    r_true = float(np.linalg.norm(los_true))
    u_true = los_true / r_true
    rate_true = -float(np.dot(sat_vel - true_vel, u_true))

    return r_fake - r_true, rate_fake - rate_true


def _apply_spoof_delta(o, fake_pos, fake_vel, truth: TruthState, cn0_new: float,
                        e_spoof_m: float, rng: np.random.Generator):
    """Build one spoofed SatObs as a delta on the clean o (never mutates o)."""
    o2 = copy(o)
    d_range, d_rate = _geom_delta(o.sat_pos, o.sat_vel, fake_pos, fake_vel, truth.pos, truth.vel)

    sigma_old = code_thermal_sigma_m(o.cn0_dbhz)
    sigma_new = code_thermal_sigma_m(cn0_new)
    extra_sigma = float(np.sqrt(max(sigma_new ** 2 - sigma_old ** 2, 0.0)))
    extra_noise = rng.normal(0.0, extra_sigma) if extra_sigma > 0 else 0.0

    o2.pseudorange = o.pseudorange + d_range + e_spoof_m + extra_noise
    o2.pseudorange_rate = o.pseudorange_rate + d_rate
    o2.cn0_dbhz = cn0_new
    return o2


@dataclass
class DriftInSpoof:
    """Gradual carry-off spoofing (position-drag or time-push variant).

    Drag kinematics are a pure (deterministic, closed-form) function of t and
    config -- no accumulated per-tick integration state -- so the expected
    PVT offset at any time is exactly reproducible/testable via
    ``expected_offset(t)``.
    """
    onset_s: float = 30.0
    align_s: float = 10.0          # alignment phase before drag begins
    duration_s: float | None = 200.0
    off_ramp_s: float = 2.0
    severity: float = 0.5          # in [0,1] -> scales drift accel/vel and power bump
    mode: str = "position"         # "position" (carry-off) or "time" (clock-push)
    direction_enu: np.ndarray = field(default_factory=lambda: np.array([1.0, 0.0, 0.0]))
    max_drift_accel_mps2: float = 0.05   # bounded, literature-consistent ASSUMPTION
    max_drift_vel_mps: float = 3.0       # bounded terminal drift speed ASSUMPTION
    power_bump_db_range: tuple[float, float] = (3.0, 10.0)
    # Once the tracking loop is captured (end of alignment), the spoofer only
    # needs enough excess power to stay inside the discriminator's pull-in
    # range, not the full capture-time advantage (Humphreys 2008 Sec. III
    # qualitative point: capture requires a larger advantage than holding
    # lock) -- ASSUMPTION fraction, also keeps the C/N0-driven receiver
    # weight close to its pre-attack value during the drag, which is what
    # makes single-antenna snapshot RAIM stay statistically blind to a
    # smoothly-dragged, geometrically-consistent spoof (Master WP-3.x review
    # round 2, decision 3).
    maintenance_bump_fraction: float = 0.15

    # Single-antenna C/N0 signature (Master D-018 item 2; Radoš, Brkić &
    # Begušić 2024, Sensors 24(13):4210, Fig. 5: all spoofed PRNs are
    # re-radiated from ONE antenna/one signal generator chain, so their
    # measured C/N0 values become strongly cross-correlated and lose the
    # per-satellite elevation dependence a real multi-satellite constellation
    # would have (the paper reports a field-measured C/N0 cross-satellite
    # correlation coefficient of -0.76 clean vs 0.99 spoofed -- we reproduce
    # the qualitative "goes strongly positive" effect; the paper does not
    # give a convergence time constant or shared-fluctuation sigma, so both
    # below are ASSUMPTION). After capture (drag_start), each PRN's
    # individually-boosted C/N0 exponentially converges toward one common
    # spoofer-driven level plus a single shared (not per-PRN) Gauss-Markov
    # fluctuation applied identically to every spoofed PRN in the epoch.
    common_cn0_convergence_tau_s: float = 5.0     # ASSUMPTION
    common_spoofer_cn0_dbhz: float = 45.0         # ASSUMPTION (single generator's nominal output level)
    common_cn0_fluct_sigma_db: float = 1.0        # ASSUMPTION
    common_cn0_fluct_tau_s: float = 20.0          # ASSUMPTION

    _atmos_mismatch: dict = field(default_factory=dict, repr=False)   # prn -> e_spoofer [m]
    _last_t: float | None = field(default=None, repr=False)
    _clock_push_m: float = field(default=0.0, repr=False)  # kept only for config() introspection
    _shared_cn0_fluct: float = field(default=0.0, repr=False)  # ONE state shared by all PRNs (single antenna)

    def config(self) -> dict:
        return dict(kind="drift_spoof", mode=self.mode, onset_s=self.onset_s, align_s=self.align_s,
                    duration_s=self.duration_s, off_ramp_s=self.off_ramp_s, severity=self.severity,
                    max_drift_accel_mps2=self.max_drift_accel_mps2 * self.severity,
                    max_drift_vel_mps=self.max_drift_vel_mps * self.severity,
                    power_bump_db=self._power_bump_db(),
                    direction_enu=self.direction_enu.tolist(),
                    spoofer_atmos_sigma_m=SPOOFER_ATMOS_SIGMA_M, spoofer_atmos_tau_s=SPOOFER_ATMOS_TAU_S,
                    common_cn0_convergence_tau_s=self.common_cn0_convergence_tau_s,
                    common_spoofer_cn0_dbhz=self.common_spoofer_cn0_dbhz,
                    common_cn0_fluct_sigma_db=self.common_cn0_fluct_sigma_db,
                    common_cn0_fluct_tau_s=self.common_cn0_fluct_tau_s)

    def _power_bump_db(self) -> float:
        lo, hi = self.power_bump_db_range
        return lo + self.severity * (hi - lo)

    def _drag_start(self) -> float:
        return self.onset_s + self.align_s

    def label(self, t: float) -> AttackLabel:
        active = is_active(t, self.onset_s, self.duration_s, self.off_ramp_s)
        kind = "time_push" if self.mode == "time" else "drift_spoof"
        return AttackLabel(t=t, spoofing=active, jamming=False, kind=kind if active else "none",
                            severity=self.severity if active else 0.0)

    def expected_offset(self, t: float) -> tuple[np.ndarray, np.ndarray]:
        """Closed-form (pos_offset[3], vel_offset[3]) of the fake trajectory
        relative to truth at time t, given config only (deterministic, no
        rng) -- constant acceleration to a capped terminal drift speed."""
        drag_start = self._drag_start()
        if t <= drag_start:
            return np.zeros(3), np.zeros(3)
        dtau = t - drag_start
        accel = self.max_drift_accel_mps2 * self.severity
        vmax = self.max_drift_vel_mps * self.severity
        if accel <= 0:
            return np.zeros(3), np.zeros(3)
        t_ramp = vmax / accel
        if dtau <= t_ramp:
            speed = accel * dtau
            dist = 0.5 * accel * dtau ** 2
        else:
            speed = vmax
            dist = 0.5 * accel * t_ramp ** 2 + vmax * (dtau - t_ramp)
        return self.direction_enu * dist, self.direction_enu * speed

    def expected_clock_push_m(self, t: float) -> float:
        """Closed-form common-mode delay [m] added in "time" mode by time t."""
        drag_start = self._drag_start()
        if t <= drag_start:
            return 0.0
        vmax = self.max_drift_vel_mps * self.severity
        return vmax * (t - drag_start)

    def apply(self, epoch: GnssEpoch, truth: TruthState, rng: np.random.Generator) -> GnssEpoch:
        t = epoch.t
        if not is_active(t, self.onset_s, self.duration_s, self.off_ramp_s):
            return epoch

        dt = 0.0 if self._last_t is None else max(t - self._last_t, 0.0)
        self._last_t = t

        env = ramp_factor(t, self.onset_s, ramp_s=1.0, duration=self.duration_s, off_ramp_s=self.off_ramp_s)
        peak_bump_db = self._power_bump_db() * min(env, 1.0)
        drag_start = self._drag_start()
        if t < drag_start:
            bump_db = peak_bump_db
        else:
            # decay from peak (capture) to the smaller maintenance level over 2 s
            decay_env = min(max((t - drag_start) / 2.0, 0.0), 1.0)
            bump_db = peak_bump_db * (1.0 + decay_env * (self.maintenance_bump_fraction - 1.0))

        pos_offset, vel_offset = self.expected_offset(t)
        clock_push_m = self.expected_clock_push_m(t)

        # ONE shared Gauss-Markov draw per epoch (not per satellite): every
        # spoofed PRN comes off the same single-antenna signal chain, so a
        # fluctuation in that chain's output power hits all of them together.
        self._shared_cn0_fluct = _gm_step(self._shared_cn0_fluct, dt,
                                           self.common_cn0_fluct_tau_s, self.common_cn0_fluct_sigma_db, rng)
        conv_frac = 1.0 - np.exp(-max(t - drag_start, 0.0) / self.common_cn0_convergence_tau_s) if t >= drag_start else 0.0
        common_target = self.common_spoofer_cn0_dbhz + self._shared_cn0_fluct

        new_obs = []
        for o in epoch.obs:
            e_spoof = _gm_step(self._atmos_mismatch.get(o.prn, 0.0), dt,
                                SPOOFER_ATMOS_TAU_S, SPOOFER_ATMOS_SIGMA_M, rng)
            self._atmos_mismatch[o.prn] = e_spoof

            individual_cn0 = o.cn0_dbhz + bump_db
            # after capture, blend each PRN's own (still elevation-dependent)
            # boosted level toward the single-antenna common level -- this is
            # what collapses both the cross-PRN decorrelation and the C/N0-
            # vs-elevation slope (Radoš et al. 2024 Fig. 5 signature).
            cn0_new = individual_cn0 + conv_frac * (common_target - individual_cn0)
            if self.mode == "position":
                fake_pos = truth.pos + pos_offset
                fake_vel = truth.vel + vel_offset
                o2 = _apply_spoof_delta(o, fake_pos, fake_vel, truth, cn0_new, e_spoof, rng)
            else:  # time push: position stays true, common-mode delay grows on top of the clean obs
                o2 = copy(o)
                o2.pseudorange = o.pseudorange + clock_push_m + e_spoof
                o2.pseudorange_rate = o.pseudorange_rate + (self.max_drift_vel_mps * self.severity if t >= self._drag_start() else 0.0)
                o2.cn0_dbhz = cn0_new
            new_obs.append(o2)

        return GnssEpoch(t=epoch.t, obs=new_obs, agc_db=epoch.agc_db,
                          noise_floor_db=epoch.noise_floor_db, meta=dict(epoch.meta))


@dataclass
class MeaconingReplay:
    """Meaconing / replay: rebroadcast delay -> common-mode clock-bias jump,
    apparent meacon-antenna position offset, C/N0 change.

    Delta-on-clean by construction: a meaconer records and rebroadcasts the
    REAL signal (unlike a spoofer, it doesn't synthesise one), so it carries
    every clean-signal error component (thermal, multipath, atmosphere)
    unchanged plus one added common-mode delay. No per-satellite trajectory
    re-derivation is needed or appropriate here.

    Source: Psiaki & Humphreys, "GNSS Spoofing and Detection", Proc. IEEE,
    2016 -- meaconing described as record-and-rebroadcast producing a common
    delay across all channels (all pseudoranges shift together, unlike a
    per-satellite spoofed trajectory) and typically a C/N0 rise from
    re-radiated signal power. Exact delay/C/N0 figures not given a specific
    numeric citation here -> ASSUMPTION, parameterized.
    """
    onset_s: float = 30.0
    duration_s: float | None = None
    ramp_s: float = 0.2   # meaconing engages fast (near step, but avoid literal discontinuity)
    off_ramp_s: float = 0.2
    replay_delay_m: float = 1500.0     # ~5 microsecond common delay (typical retransmission latency ASSUMPTION)
    cn0_bump_db: float = 4.0
    severity: float = 0.5

    def config(self) -> dict:
        return dict(kind="meaconing", onset_s=self.onset_s, duration_s=self.duration_s,
                    replay_delay_m=self.replay_delay_m * self.severity, cn0_bump_db=self.cn0_bump_db,
                    severity=self.severity)

    def label(self, t: float) -> AttackLabel:
        active = is_active(t, self.onset_s, self.duration_s, self.off_ramp_s)
        return AttackLabel(t=t, spoofing=active, jamming=False, kind="meaconing" if active else "none",
                            severity=self.severity if active else 0.0)

    def apply(self, epoch: GnssEpoch, truth: TruthState, rng: np.random.Generator) -> GnssEpoch:
        t = epoch.t
        if not is_active(t, self.onset_s, self.duration_s, self.off_ramp_s):
            return epoch
        env = ramp_factor(t, self.onset_s, self.ramp_s, self.duration_s, self.off_ramp_s)
        delay = self.replay_delay_m * self.severity * env
        bump = self.cn0_bump_db * env

        new_obs = []
        for o in epoch.obs:
            o2 = copy(o)
            o2.pseudorange = o.pseudorange + delay   # common-mode jump -> receiver clock-bias jump
            o2.cn0_dbhz = o.cn0_dbhz + bump
            new_obs.append(o2)
        return GnssEpoch(t=epoch.t, obs=new_obs, agc_db=epoch.agc_db + 0.3 * env,
                          noise_floor_db=epoch.noise_floor_db, meta=dict(epoch.meta))


@dataclass
class AbruptSpoof:
    """Abrupt, non-aligned position-jump spoofing: causes tracking-loop
    discontinuity -> lock loss + reacquisition (no power alignment phase).

    Delta-on-clean like DriftInSpoof (see module docstring): the fake
    trajectory is a step to ``truth.pos + jump`` (held constant, no further
    drag), and the same spoofer atmosphere-mismatch process is applied.

    Source: qualitative behaviour per Psiaki & Humphreys 2016 Proc. IEEE
    (an un-aligned spoofer causes a sudden correlation-peak jump that a
    tracking loop cannot follow smoothly, unlike carry-off). Jump magnitude
    is an ASSUMPTION parameter.
    """
    onset_s: float = 30.0
    duration_s: float | None = 60.0
    off_ramp_s: float = 0.0
    jump_vector_enu: np.ndarray = field(default_factory=lambda: np.array([80.0, 0.0, 0.0]))
    severity: float = 0.7
    reacq_epochs: int = 2   # number of epochs immediately after onset reported as lock-lost

    _epochs_since_onset: int = field(default=-1, repr=False)
    _atmos_mismatch: dict = field(default_factory=dict, repr=False)
    _last_t: float | None = field(default=None, repr=False)

    def config(self) -> dict:
        return dict(kind="abrupt_spoof", onset_s=self.onset_s, duration_s=self.duration_s,
                    jump_vector_enu=(self.jump_vector_enu * self.severity).tolist(),
                    severity=self.severity, reacq_epochs=self.reacq_epochs,
                    spoofer_atmos_sigma_m=SPOOFER_ATMOS_SIGMA_M, spoofer_atmos_tau_s=SPOOFER_ATMOS_TAU_S)

    def label(self, t: float) -> AttackLabel:
        active = is_active(t, self.onset_s, self.duration_s, self.off_ramp_s)
        return AttackLabel(t=t, spoofing=active, jamming=False, kind="abrupt_spoof" if active else "none",
                            severity=self.severity if active else 0.0)

    def apply(self, epoch: GnssEpoch, truth: TruthState, rng: np.random.Generator) -> GnssEpoch:
        t = epoch.t
        if not is_active(t, self.onset_s, self.duration_s, self.off_ramp_s):
            self._epochs_since_onset = -1
            self._last_t = None
            return epoch
        if self._epochs_since_onset < 0:
            self._epochs_since_onset = 0
        else:
            self._epochs_since_onset += 1

        dt = 0.0 if self._last_t is None else max(t - self._last_t, 0.0)
        self._last_t = t

        jump = self.jump_vector_enu * self.severity
        fake_pos = truth.pos + jump
        fake_vel = truth.vel  # position jump only, no velocity change

        lock_lost = self._epochs_since_onset < self.reacq_epochs

        new_obs = []
        for o in epoch.obs:
            e_spoof = _gm_step(self._atmos_mismatch.get(o.prn, 0.0), dt,
                                SPOOFER_ATMOS_TAU_S, SPOOFER_ATMOS_SIGMA_M, rng)
            self._atmos_mismatch[o.prn] = e_spoof

            cn0_new = o.cn0_dbhz - 15.0 if lock_lost else o.cn0_dbhz
            o2 = _apply_spoof_delta(o, fake_pos, fake_vel, truth, cn0_new, e_spoof, rng)
            if lock_lost:
                o2.tracked = False
            new_obs.append(o2)
        return GnssEpoch(t=epoch.t, obs=new_obs, agc_db=epoch.agc_db,
                          noise_floor_db=epoch.noise_floor_db, meta=dict(epoch.meta))
