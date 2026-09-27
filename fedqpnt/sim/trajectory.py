"""Truth trajectory generators (WP-1.2, ARCHITECTURE.md section 11.2).

Each scalar "channel" (longitudinal accel, turn rate, road grade / vertical
velocity) is a ``scipy.interpolate.PPoly`` built as a sum of non-overlapping
smooth trapezoid pulses with a quintic-smoothstep ramp (C^2). Maneuvers are
scheduled sequentially (a cursor walks forward in time), so pulses never
overlap by construction and each pulse's local polynomial pieces line up
exactly with the combined piecewise-polynomial's breakpoints.

Position is obtained by 5-point Gauss-Legendre quadrature of the (nonlinear)
velocity field, per ARCHITECTURE.md section 11.2 (exact to degree 9).

PROPOSED-DECISION (marked, conservative/additive, default preserves the
brief's literal behaviour): ``generate()`` takes an optional ``world`` kwarg
(default ``"flat"``, matching the brief's fixed ``f_b = C^T(a_n - [0,0,-G0])``
exactly). Passing ``world="schuler_tangent"`` evaluates ``fedqpnt.core.world
.gravity_n`` at the true position for ``f_b`` instead, which the brief does
not specify a knob for but which SIM-IMPL's validation needs to exercise the
strapdown closure test in the Schuler world honestly (self-consistent truth
generation + integration, rather than reusing flat-gravity truth with a
mismatched-gravity integrator).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
from scipy.interpolate import PPoly

from fedqpnt.core import world as _world
from fedqpnt.core.types import G0, TruthTrajectory

from .rotations import body_rates_from_euler_rates, dcm_to_euler, euler_to_dcm, vee

# 5-point Gauss-Legendre nodes/weights on [-1, 1] (exact to degree 9).
_GL5_X = np.array([-0.9061798459386640, -0.5384693101056831, 0.0,
                    0.5384693101056831, 0.9061798459386640])
_GL5_W = np.array([0.2369268850561891, 0.4786286704993665, 0.5688888888888889,
                    0.4786286704993665, 0.2369268850561891])


# ---------------------------------------------------------------------------
# Smooth trapezoid pulses
# ---------------------------------------------------------------------------
def smoothstep(tau: np.ndarray) -> np.ndarray:
    """Quintic smoothstep S(tau) = 10 tau^3 - 15 tau^4 + 6 tau^5, S,S',S''=0 at ends."""
    return 10.0 * tau ** 3 - 15.0 * tau ** 4 + 6.0 * tau ** 5


def pulse_for_delta(delta: float, a_max: float, Tr: float) -> tuple[float, float]:
    """(Th, A) for a trapezoid pulse of ramp Tr whose integral equals delta, peak |A| <= |a_max|."""
    a_max = abs(a_max)
    if abs(delta) < 1e-12 or a_max < 1e-12:
        return 0.0, 0.0
    Th = abs(delta) / a_max - Tr
    if Th < 0.0:
        return 0.0, delta / Tr
    return Th, a_max * np.sign(delta)


@dataclass
class Pulse:
    t0: float
    Tr: float
    Th: float
    A: float

    @property
    def t1(self) -> float:
        return self.t0 + self.Tr

    @property
    def t2(self) -> float:
        return self.t0 + self.Tr + self.Th

    @property
    def t3(self) -> float:
        return self.t0 + 2.0 * self.Tr + self.Th

    def breakpoints(self) -> list[float]:
        pts = [self.t0, self.t1, self.t2, self.t3]
        out = [pts[0]]
        for p in pts[1:]:
            if p > out[-1] + 1e-9:
                out.append(p)
        return out


def _ramp_up_coeffs(A: float, Tr: float) -> np.ndarray:
    return np.array([6.0 * A / Tr ** 5, -15.0 * A / Tr ** 4, 10.0 * A / Tr ** 3, 0.0, 0.0, 0.0])


def _ramp_down_coeffs(A: float, Tr: float) -> np.ndarray:
    return np.array([-6.0 * A / Tr ** 5, 15.0 * A / Tr ** 4, -10.0 * A / Tr ** 3, 0.0, 0.0, A])


def _hold_coeffs(A: float) -> np.ndarray:
    return np.array([0.0, 0.0, 0.0, 0.0, 0.0, A])


def build_channel(pulses: list[Pulse], duration: float) -> PPoly:
    """Combine non-overlapping pulses into one C^2 PPoly on [0, duration], zero elsewhere."""
    bpts = {0.0, duration}
    for p in pulses:
        for b in p.breakpoints():
            if -1e-9 <= b <= duration + 1e-9:
                bpts.add(min(max(b, 0.0), duration))
    xs = np.array(sorted(bpts))
    xs = np.unique(np.round(xs, 9))
    if xs.shape[0] < 2:
        xs = np.array([0.0, duration])
    m = xs.shape[0] - 1
    c = np.zeros((6, m))
    for i in range(m):
        mid = 0.5 * (xs[i] + xs[i + 1])
        for p in pulses:
            if p.t0 - 1e-7 <= mid <= p.t3 + 1e-7:
                if mid < p.t1:
                    c[:, i] = _ramp_up_coeffs(p.A, p.Tr)
                elif mid < p.t2:
                    c[:, i] = _hold_coeffs(p.A)
                else:
                    c[:, i] = _ramp_down_coeffs(p.A, p.Tr)
                break
    return PPoly(c, xs, extrapolate=True)


def _gl5_integrate(t: np.ndarray, vel_fn, p0: np.ndarray) -> np.ndarray:
    """Position by 5-point Gauss-Legendre quadrature of ``vel_fn`` over each [t_k, t_k+1]."""
    N = t.shape[0]
    pos = np.empty((N, 3))
    pos[0] = p0
    if N < 2:
        return pos
    h = np.diff(t)
    CHUNK = 200_000  # intervals per chunk (5 evals each) -> well under 1e6 samples
    seg = np.empty((N - 1, 3))
    for start in range(0, N - 1, CHUNK):
        end = min(start + CHUNK, N - 1)
        hc = h[start:end]
        eval_t = t[start:end, None] + (hc[:, None] / 2.0) * (1.0 + _GL5_X[None, :])
        v = vel_fn(eval_t.reshape(-1)).reshape(end - start, 5, 3)
        weighted = np.sum(_GL5_W[None, :, None] * v, axis=1)
        seg[start:end] = (hc[:, None] / 2.0) * weighted
    pos[1:] = p0 + np.cumsum(seg, axis=0)
    return pos


def _tuples_to_lists(d: dict) -> dict:
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in d.items()}


# ---------------------------------------------------------------------------
# Ground vehicle
# ---------------------------------------------------------------------------
@dataclass
class GroundVehicleParams:
    v_max: float = 25.0
    a_acc_max: float = 2.5
    a_brake_max: float = 3.5
    a_lat_max: float = 3.0
    yaw_rate_max: float = 0.5
    ramp_s: float = 1.5
    grade_max: float = 0.06
    roll_gain: float = 0.006   # rad per m/s^2 lateral accel [ASSUMPTION, ~=3.4 deg/g]
    pitch_gain: float = 0.003  # rad per m/s^2 longitudinal accel [ASSUMPTION, ~=1.7 deg/g]
    t_static: float = 30.0
    p_cruise: float = 0.35
    p_speed: float = 0.25
    p_turn: float = 0.25
    p_stop: float = 0.15
    cruise_s: tuple[float, float] = (10.0, 60.0)
    turn_deg: tuple[float, float] = (30.0, 120.0)
    stop_hold_s: tuple[float, float] = (5.0, 20.0)
    speed_target: tuple[float, float] = (8.0, 25.0)
    min_turn_speed: float = 3.0


def _plan_ground(p: GroundVehicleParams, duration: float, rng: np.random.Generator):
    t_cursor = p.t_static
    s_cur = 0.0
    accel_pulses: list[Pulse] = []
    turn_pulses: list[Pulse] = []
    grade_pulses: list[Pulse] = []
    maneuvers: list[dict[str, Any]] = [{"kind": "static", "t0": 0.0, "t1": p.t_static}]

    kinds = ["cruise", "speed", "turn", "stop"]
    weights = np.array([p.p_cruise, p.p_speed, p.p_turn, p.p_stop])
    weights = weights / weights.sum()
    forced = list(rng.permutation(kinds))  # guarantee coverage regardless of seed

    def draw_kind() -> str:
        if forced:
            return forced.pop(0)
        return kinds[rng.choice(len(kinds), p=weights)]

    def do_speed_change(target: float) -> None:
        nonlocal t_cursor, s_cur
        delta = target - s_cur
        a_max = p.a_acc_max if delta >= 0 else p.a_brake_max
        Th, A = pulse_for_delta(delta, a_max, p.ramp_s)
        pulse = Pulse(t0=t_cursor, Tr=p.ramp_s, Th=Th, A=A)
        accel_pulses.append(pulse)
        t1 = min(pulse.t3, duration)
        maneuvers.append({"kind": "speed_change", "t0": t_cursor, "t1": t1, "target": target})
        t_cursor = t1
        s_cur = target

    while t_cursor < duration:
        kind = draw_kind()
        if kind == "cruise":
            dur = rng.uniform(*p.cruise_s)
            t0, t1 = t_cursor, min(t_cursor + dur, duration)
            if s_cur > 3.0 and t1 - t0 > 2 * 5.0:
                Tr = 5.0
                Th = (t1 - t0) - 2 * Tr
                amp = rng.uniform(-p.grade_max, p.grade_max)
                grade_pulses.append(Pulse(t0=t0, Tr=Tr, Th=Th, A=amp))
            maneuvers.append({"kind": "cruise", "t0": t0, "t1": t1, "speed": s_cur})
            t_cursor = t1
        elif kind == "speed":
            do_speed_change(float(rng.uniform(*p.speed_target)))
        elif kind == "turn":
            if s_cur < p.min_turn_speed and t_cursor < duration:
                lo = max(p.min_turn_speed, p.speed_target[0])
                do_speed_change(float(rng.uniform(lo, max(lo, p.speed_target[1]))))
                if t_cursor >= duration:
                    break
            sign = 1.0 if rng.random() < 0.5 else -1.0
            dpsi = sign * np.radians(rng.uniform(*p.turn_deg))
            R = min(p.yaw_rate_max, p.a_lat_max / max(s_cur, 1e-6))
            Th, A = pulse_for_delta(dpsi, R, p.ramp_s)
            pulse = Pulse(t0=t_cursor, Tr=p.ramp_s, Th=Th, A=A)
            turn_pulses.append(pulse)
            t1 = min(pulse.t3, duration)
            maneuvers.append({"kind": "turn", "t0": t_cursor, "t1": t1, "delta_psi": dpsi})
            t_cursor = t1
        elif kind == "stop":
            Th, A = pulse_for_delta(-s_cur, p.a_brake_max, p.ramp_s)
            pulse = Pulse(t0=t_cursor, Tr=p.ramp_s, Th=Th, A=A)
            accel_pulses.append(pulse)
            t_brake_end = pulse.t3
            hold = rng.uniform(*p.stop_hold_s)
            t_resume = t_brake_end + hold
            maneuvers.append({"kind": "stop", "t0": t_cursor, "t1": min(t_resume, duration)})
            t_cursor = min(t_resume, duration)
            s_cur = 0.0
            if t_cursor >= duration:
                break
            do_speed_change(float(rng.uniform(*p.speed_target)))

    return accel_pulses, turn_pulses, grade_pulses, maneuvers


def _ground_kinematics(a_s: PPoly, r: PPoly, gamma: PPoly, s0: float, yaw0: float,
                        p: GroundVehicleParams, t: np.ndarray, origin: np.ndarray, world: str):
    F_as = a_s.antiderivative()
    F_r = r.antiderivative()
    d_as = a_s.derivative()
    d_r = r.derivative()
    d_gamma = gamma.derivative()

    def s_of(tt): return s0 + F_as(tt)
    def psi_of(tt): return yaw0 + F_r(tt)

    def vel_fn(tt):
        ss = s_of(tt); ps = psi_of(tt); gg = gamma(tt)
        return np.stack([ss * np.cos(ps), ss * np.sin(ps), ss * np.tan(gg)], axis=-1)

    pos = _gl5_integrate(t, vel_fn, origin)

    s = s_of(t); psi = psi_of(t); gam = gamma(t)
    sdot = a_s(t); psidot = r(t); gamdot = d_gamma(t)
    sddot = d_as(t); psiddot = d_r(t)
    cpsi, spsi = np.cos(psi), np.sin(psi)
    tgam = np.tan(gam)
    sec2 = 1.0 / np.cos(gam) ** 2

    vel = np.stack([s * cpsi, s * spsi, s * tgam], axis=-1)
    acc = np.stack([
        sdot * cpsi - s * psidot * spsi,
        sdot * spsi + s * psidot * cpsi,
        sdot * tgam + s * gamdot * sec2,
    ], axis=-1)

    theta = -(gam + p.pitch_gain * sdot)
    phi = p.roll_gain * (s * psidot)
    thetadot = -(gamdot + p.pitch_gain * sddot)
    phidot = p.roll_gain * (sdot * psidot + s * psiddot)
    att = np.stack([phi, theta, psi], axis=-1)
    att_dot = np.stack([phidot, thetadot, psidot], axis=-1)
    omega_b = body_rates_from_euler_rates(att, att_dot)

    C = euler_to_dcm(att)
    g = _world.gravity_n(pos, world)
    f_b = np.einsum('kji,kj->ki', C, acc - g)

    return pos, vel, acc, att, omega_b, f_b


class GroundVehicleTrajectory:
    """Implements ``core.interfaces.TrajectoryGenerator``."""

    def __init__(self, params: GroundVehicleParams | None = None,
                 origin_enu: tuple[float, float, float] = (0.0, 0.0, 0.0),
                 yaw0: float | None = None):
        self.params = params or GroundVehicleParams()
        self.origin_enu = tuple(origin_enu)
        self._yaw0_fixed = yaw0

    def config(self) -> dict[str, Any]:
        return {
            "type": "GroundVehicleTrajectory",
            "params": _tuples_to_lists(asdict(self.params)),
            "origin_enu": list(self.origin_enu),
            "yaw0": self._yaw0_fixed,
        }

    def generate(self, duration_s: float, dt: float, rng: np.random.Generator,
                 world: str = "flat") -> TruthTrajectory:
        p = self.params
        yaw0 = self._yaw0_fixed if self._yaw0_fixed is not None else float(rng.uniform(-np.pi, np.pi))
        accel_pulses, turn_pulses, grade_pulses, maneuvers = _plan_ground(p, duration_s, rng)

        a_s = build_channel(accel_pulses, duration_s)
        r = build_channel(turn_pulses, duration_s)
        gamma = build_channel(grade_pulses, duration_s)

        N = int(round(duration_s / dt)) + 1
        t = np.arange(N) * dt
        origin = np.array(self.origin_enu, dtype=float)

        pos, vel, acc, att, omega_b, f_b = _ground_kinematics(
            a_s, r, gamma, 0.0, yaw0, p, t, origin, world)

        meta = {
            "platform": "ground",
            "params": _tuples_to_lists(asdict(p)),
            "maneuvers": maneuvers,
            "yaw0": yaw0,
            "limits": {"v_max": p.v_max, "a_acc_max": p.a_acc_max, "a_brake_max": p.a_brake_max,
                       "a_lat_max": p.a_lat_max, "yaw_rate_max": p.yaw_rate_max},
        }
        return TruthTrajectory(t=t, pos=pos, vel=vel, acc=acc, att=att, omega_b=omega_b, f_b=f_b, meta=meta)


# ---------------------------------------------------------------------------
# UAV (multirotor / VTOL, thrust-aligned)
# ---------------------------------------------------------------------------
@dataclass
class UavParams:
    v_max: float = 20.0
    vz_max: float = 4.0
    a_h_max: float = 3.0
    a_z_max: float = 2.0
    tilt_max_deg: float = 30.0
    yaw_rate_max: float = 0.6
    ramp_s: float = 1.5
    alt_min: float = 30.0
    alt_max: float = 300.0
    alt0: float = 50.0
    t_hover0: float = 30.0
    p_cruise: float = 0.25
    p_speed: float = 0.2
    p_turn: float = 0.2
    p_climb: float = 0.15
    p_loiter: float = 0.1
    p_hover: float = 0.1
    cruise_s: tuple[float, float] = (10.0, 60.0)
    turn_deg: tuple[float, float] = (30.0, 180.0)
    loiter_turns: tuple[float, float] = (1, 2)
    hover_s: tuple[float, float] = (5.0, 30.0)
    speed_target: tuple[float, float] = (5.0, 20.0)


def _vertical_bump_shape_gain(Tr: float) -> float:
    """Altitude gained by a single 0->vz_peak->0 accel bump (Th=0, ramp Tr each
    side) per unit vz_peak (D-017: v_u must be the integral of a C^2 ACCEL
    pulse, so v_u is C^3 like ground's s(t); this is that pulse's shape
    constant). Altitude is exactly linear in vz_peak for fixed Tr (the bump's
    shape only rescales), so one PPoly double-antiderivative evaluation
    (exact, no hand calculus) gives the constant for any peak."""
    pulse = Pulse(t0=0.0, Tr=Tr, Th=0.0, A=1.0 / Tr)  # peak velocity = 1 after the bump
    a_pp = build_channel([pulse], 2.0 * Tr)
    z_pp = a_pp.antiderivative().antiderivative()
    return float(z_pp(2.0 * Tr))


def _plan_uav(p: UavParams, duration: float, rng: np.random.Generator):
    t_cursor = p.t_hover0
    s_cur = 0.0
    alt_cur = p.alt0
    bump_gain = _vertical_bump_shape_gain(p.ramp_s)
    accel_pulses: list[Pulse] = []
    turn_pulses: list[Pulse] = []
    vert_pulses: list[Pulse] = []
    maneuvers: list[dict[str, Any]] = [{"kind": "hover0", "t0": 0.0, "t1": p.t_hover0}]

    kinds = ["cruise", "speed", "turn", "climb", "loiter", "hover"]
    weights = np.array([p.p_cruise, p.p_speed, p.p_turn, p.p_climb, p.p_loiter, p.p_hover])
    weights = weights / weights.sum()
    forced = list(rng.permutation(kinds))

    def draw_kind() -> str:
        if forced:
            return forced.pop(0)
        return kinds[rng.choice(len(kinds), p=weights)]

    def turn_rate_cap() -> float:
        s_eff = max(s_cur, 1e-6)
        return min(p.yaw_rate_max, p.a_h_max / s_eff, 9.80665 * np.tan(np.radians(p.tilt_max_deg)) / s_eff)

    def do_speed_change(target: float) -> None:
        nonlocal t_cursor, s_cur
        delta = target - s_cur
        Th, A = pulse_for_delta(delta, p.a_h_max, p.ramp_s)
        pulse = Pulse(t0=t_cursor, Tr=p.ramp_s, Th=Th, A=A)
        accel_pulses.append(pulse)
        t1 = min(pulse.t3, duration)
        maneuvers.append({"kind": "speed_change", "t0": t_cursor, "t1": t1, "target": target})
        t_cursor = t1
        s_cur = target

    def do_turn(dpsi: float, kind_label: str) -> None:
        nonlocal t_cursor
        R = turn_rate_cap()
        Th, A = pulse_for_delta(dpsi, R, p.ramp_s)
        pulse = Pulse(t0=t_cursor, Tr=p.ramp_s, Th=Th, A=A)
        turn_pulses.append(pulse)
        t1 = min(pulse.t3, duration)
        maneuvers.append({"kind": kind_label, "t0": t_cursor, "t1": t1, "delta_psi": dpsi})
        t_cursor = t1

    while t_cursor < duration:
        kind = draw_kind()
        if kind == "cruise":
            dur = rng.uniform(*p.cruise_s)
            t1 = min(t_cursor + dur, duration)
            maneuvers.append({"kind": "cruise", "t0": t_cursor, "t1": t1, "speed": s_cur})
            t_cursor = t1
        elif kind == "speed":
            do_speed_change(float(rng.uniform(*p.speed_target)))
        elif kind == "turn":
            if s_cur < 1e-6:
                do_speed_change(float(rng.uniform(*p.speed_target)))
                if t_cursor >= duration:
                    break
            sign = 1.0 if rng.random() < 0.5 else -1.0
            dpsi = sign * np.radians(rng.uniform(*p.turn_deg))
            do_turn(dpsi, "turn")
        elif kind == "climb":
            target = rng.uniform(p.alt_min + 10.0, p.alt_max - 10.0)
            delta = target - alt_cur
            Tr = p.ramp_s
            full_bump_alt = 2.0 * bump_gain * p.vz_max
            if abs(delta) >= full_bump_alt:
                vz_peak = p.vz_max * np.sign(delta)
                hold = (abs(delta) - full_bump_alt) / p.vz_max
            else:
                vz_peak = delta / (2.0 * bump_gain)
                hold = 0.0
            pulse_up = Pulse(t0=t_cursor, Tr=Tr, Th=0.0, A=vz_peak / Tr)
            pulse_down = Pulse(t0=pulse_up.t3 + hold, Tr=Tr, Th=0.0, A=-vz_peak / Tr)
            vert_pulses.append(pulse_up)
            vert_pulses.append(pulse_down)
            t1 = min(pulse_down.t3, duration)
            maneuvers.append({"kind": "climb", "t0": t_cursor, "t1": t1, "target_alt": target})
            t_cursor = t1
            alt_cur = target
        elif kind == "loiter":
            if s_cur < 1e-6:
                do_speed_change(float(rng.uniform(*p.speed_target)))
                if t_cursor >= duration:
                    break
            k = rng.integers(int(p.loiter_turns[0]), int(p.loiter_turns[1]) + 1)
            sign = 1.0 if rng.random() < 0.5 else -1.0
            dpsi = sign * 2.0 * np.pi * k
            do_turn(dpsi, "loiter")
        elif kind == "hover":
            Th, A = pulse_for_delta(-s_cur, p.a_h_max, p.ramp_s)
            pulse = Pulse(t0=t_cursor, Tr=p.ramp_s, Th=Th, A=A)
            accel_pulses.append(pulse)
            t_dec_end = pulse.t3
            hold = rng.uniform(*p.hover_s)
            t_resume = t_dec_end + hold
            maneuvers.append({"kind": "hover", "t0": t_cursor, "t1": min(t_resume, duration)})
            t_cursor = min(t_resume, duration)
            s_cur = 0.0

    return accel_pulses, turn_pulses, vert_pulses, maneuvers


def _uav_kinematics(a_s: PPoly, r: PPoly, a_u_chan: PPoly, yaw0: float, p: UavParams,
                     t: np.ndarray, origin: np.ndarray, world: str):
    """D-017: the vertical channel is now ``a_u_chan`` (vertical ACCELERATION,
    a C^2 quintic-pulse channel, same design as ``a_s``), not ``v_u`` directly
    -- so vertical velocity ``F_au1 = a_u_chan.antiderivative()`` is C^3, the
    same smoothness class as ground's ``s(t) = integral(a_s)``."""
    F_as = a_s.antiderivative()
    F_r = r.antiderivative()
    F_au1 = a_u_chan.antiderivative()   # vertical velocity v_u(t)
    F_au2 = F_au1.antiderivative()      # vertical position contribution
    d_as = a_s.derivative()
    d_r = r.derivative()
    d_au = a_u_chan.derivative()        # vertical jerk j_u(t)

    def s_of(tt): return F_as(tt)
    def psi_of(tt): return yaw0 + F_r(tt)
    def zu_of(tt): return p.alt0 + F_au2(tt)

    def vel_fn(tt):
        ss = s_of(tt); ps = psi_of(tt); vu = F_au1(tt)
        return np.stack([ss * np.cos(ps), ss * np.sin(ps), vu], axis=-1)

    pos_h = _gl5_integrate(t, vel_fn, origin)
    pos = pos_h.copy()
    pos[:, 2] = zu_of(t)  # exact PPoly double-antiderivative for the vertical channel

    s = s_of(t); psi = psi_of(t)
    sdot = a_s(t); psidot = r(t)
    sddot = d_as(t); psiddot = d_r(t)
    vu = F_au1(t); a_u = a_u_chan(t); j_u = d_au(t)
    cpsi, spsi = np.cos(psi), np.sin(psi)

    vel = np.stack([s * cpsi, s * spsi, vu], axis=-1)
    acc = np.stack([sdot * cpsi - s * psidot * spsi, sdot * spsi + s * psidot * cpsi, a_u], axis=-1)
    jerk = np.stack([
        sddot * cpsi - 2 * sdot * psidot * spsi - s * psiddot * spsi - s * psidot ** 2 * cpsi,
        sddot * spsi + 2 * sdot * psidot * cpsi + s * psiddot * cpsi - s * psidot ** 2 * spsi,
        j_u,
    ], axis=-1)

    f_n = acc + np.array([0.0, 0.0, G0])
    norm_f = np.linalg.norm(f_n, axis=-1)
    z_b = f_n / norm_f[:, None]
    x_c = np.stack([cpsi, spsi, np.zeros_like(cpsi)], axis=-1)
    m = np.cross(z_b, x_c)
    norm_m = np.linalg.norm(m, axis=-1)
    y_b = m / norm_m[:, None]
    x_b = np.cross(y_b, z_b)

    zdot = (jerk - z_b * np.sum(z_b * jerk, axis=-1, keepdims=True)) / norm_f[:, None]
    xc_dot = psidot[:, None] * np.stack([-spsi, cpsi, np.zeros_like(cpsi)], axis=-1)
    mdot = np.cross(zdot, x_c) + np.cross(z_b, xc_dot)
    ydot = (mdot - y_b * np.sum(y_b * mdot, axis=-1, keepdims=True)) / norm_m[:, None]
    xdot = np.cross(ydot, z_b) + np.cross(y_b, zdot)

    N = t.shape[0]
    C = np.empty((N, 3, 3))
    C[:, :, 0] = x_b; C[:, :, 1] = y_b; C[:, :, 2] = z_b
    Cdot = np.empty((N, 3, 3))
    Cdot[:, :, 0] = xdot; Cdot[:, :, 1] = ydot; Cdot[:, :, 2] = zdot

    M = np.einsum('kji,kjl->kil', C, Cdot)  # C^T Cdot
    omega_b = vee_batch = np.stack([M[:, 2, 1], M[:, 0, 2], M[:, 1, 0]], axis=-1)

    att = dcm_to_euler(C)
    g = _world.gravity_n(pos, world)
    f_b = np.einsum('kji,kj->ki', C, acc - g)

    return pos, vel, acc, att, omega_b, f_b


class UavTrajectory:
    """Implements ``core.interfaces.TrajectoryGenerator``."""

    def __init__(self, params: UavParams | None = None,
                 origin_enu: tuple[float, float, float] = (0.0, 0.0, 0.0),
                 yaw0: float | None = None):
        self.params = params or UavParams()
        self.origin_enu = tuple(origin_enu)
        self._yaw0_fixed = yaw0

    def config(self) -> dict[str, Any]:
        return {
            "type": "UavTrajectory",
            "params": _tuples_to_lists(asdict(self.params)),
            "origin_enu": list(self.origin_enu),
            "yaw0": self._yaw0_fixed,
        }

    def generate(self, duration_s: float, dt: float, rng: np.random.Generator,
                 world: str = "flat") -> TruthTrajectory:
        p = self.params
        yaw0 = self._yaw0_fixed if self._yaw0_fixed is not None else float(rng.uniform(-np.pi, np.pi))
        accel_pulses, turn_pulses, vert_pulses, maneuvers = _plan_uav(p, duration_s, rng)

        a_s = build_channel(accel_pulses, duration_s)
        r = build_channel(turn_pulses, duration_s)
        a_u_chan = build_channel(vert_pulses, duration_s)  # D-017: vertical ACCEL pulses now

        N = int(round(duration_s / dt)) + 1
        t = np.arange(N) * dt
        origin = np.array([self.origin_enu[0], self.origin_enu[1], p.alt0], dtype=float)

        pos, vel, acc, att, omega_b, f_b = _uav_kinematics(a_s, r, a_u_chan, yaw0, p, t, origin, world)

        meta = {
            "platform": "uav",
            "params": _tuples_to_lists(asdict(p)),
            "maneuvers": maneuvers,
            "yaw0": yaw0,
            "limits": {"v_max": p.v_max, "vz_max": p.vz_max, "a_h_max": p.a_h_max,
                       "tilt_max_deg": p.tilt_max_deg, "alt_min": p.alt_min, "alt_max": p.alt_max},
        }
        return TruthTrajectory(t=t, pos=pos, vel=vel, acc=acc, att=att, omega_b=omega_b, f_b=f_b, meta=meta)


def make_trajectory(platform: str, params: dict | None = None):
    if platform == "ground":
        p = GroundVehicleParams(**(params or {}))
        return GroundVehicleTrajectory(params=p)
    if platform == "uav":
        p = UavParams(**(params or {}))
        return UavTrajectory(params=p)
    raise ValueError(f"unknown platform {platform!r}; expected 'ground' or 'uav'")
