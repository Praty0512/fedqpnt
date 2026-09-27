"""Scheduling helpers shared by all attacks (onset / duration / ramp)."""
from __future__ import annotations

import numpy as np


def ramp_factor(t: float, onset: float, ramp_s: float, duration: float | None, off_ramp_s: float | None = None) -> float:
    """Smooth [0,1] envelope: linear ramp-up over ramp_s starting at onset,
    holds at 1, optional linear ramp-down over off_ramp_s at the end of
    ``duration`` (None duration => never ends)."""
    if t < onset:
        return 0.0
    if ramp_s > 0 and t < onset + ramp_s:
        return (t - onset) / ramp_s
    if duration is None:
        return 1.0
    end = onset + duration
    off_ramp_s = off_ramp_s if off_ramp_s is not None else ramp_s
    if t < end:
        return 1.0
    if off_ramp_s > 0 and t < end + off_ramp_s:
        return 1.0 - (t - end) / off_ramp_s
    return 0.0


def is_active(t: float, onset: float, duration: float | None, off_ramp_s: float = 0.0) -> bool:
    if t < onset:
        return False
    if duration is None:
        return True
    return t < onset + duration + off_ramp_s
