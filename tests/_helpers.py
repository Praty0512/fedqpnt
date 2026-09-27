"""Minimal truth-trajectory builders shared by GNSS/attack tests.

Not part of fedqpnt.sim (owned by another agent) -- these are deliberately
tiny, test-local helpers producing TruthState sequences.
"""
from __future__ import annotations

import numpy as np

from fedqpnt.core.types import TruthState

G = 9.80665


def static_truth(t: float, pos=(0.0, 0.0, 0.0)) -> TruthState:
    return TruthState(t=t, pos=np.array(pos, dtype=float), vel=np.zeros(3), acc=np.zeros(3),
                       att=np.zeros(3), omega_b=np.zeros(3), f_b=np.array([0.0, 0.0, G]))


def const_vel_truth(t: float, speed_mps: float = 10.0, heading_rad: float = 0.0,
                     origin=(0.0, 0.0, 0.0)) -> TruthState:
    vel = np.array([speed_mps * np.sin(heading_rad), speed_mps * np.cos(heading_rad), 0.0])
    pos = np.array(origin, dtype=float) + vel * t
    return TruthState(t=t, pos=pos, vel=vel, acc=np.zeros(3), att=np.array([0.0, 0.0, heading_rad]),
                       omega_b=np.zeros(3), f_b=np.array([0.0, 0.0, G]))


def turning_truth(t: float, speed_mps: float = 10.0, turn_rate_rps: float = 0.05,
                   origin=(0.0, 0.0, 0.0)) -> TruthState:
    """Constant-speed coordinated turn starting heading = 0 (north)."""
    heading = turn_rate_rps * t
    vel = np.array([speed_mps * np.sin(heading), speed_mps * np.cos(heading), 0.0])
    # position via simple forward-Euler integral approximation (closed form for const turn rate)
    if abs(turn_rate_rps) < 1e-9:
        pos = np.array(origin, dtype=float) + vel * t
    else:
        r = speed_mps / turn_rate_rps
        pos = np.array(origin, dtype=float) + np.array([
            r * (1 - np.cos(heading)),
            r * np.sin(heading),
            0.0,
        ])
    acc = np.array([speed_mps * turn_rate_rps * np.cos(heading),
                     -speed_mps * turn_rate_rps * np.sin(heading), 0.0])
    return TruthState(t=t, pos=pos, vel=vel, acc=acc, att=np.array([0.0, 0.0, heading]),
                       omega_b=np.array([0.0, 0.0, turn_rate_rps]), f_b=np.array([0.0, 0.0, G]))


def run_truth_sequence(kind: str, duration_s: float, dt: float = 0.01, **kwargs):
    n = int(round(duration_s / dt))
    fn = {"static": static_truth, "const_vel": const_vel_truth, "turning": turning_truth}[kind]
    for k in range(n):
        t = k * dt
        yield fn(t, **kwargs) if kwargs else fn(t)
