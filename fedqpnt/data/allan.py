"""Overlapping Allan deviation, implemented locally for DATA-INGEST (WP-2.5).

fedqpnt/sensors/ (owned by the QUANTUM-SENSOR work package) did not have an
allan.py at the time this was written, so a minimal, dependency-free
implementation lives here instead. Do not move/import fedqpnt.sensors from
this module.

Reference: IEEE Std 1139-2008; Riley, "Handbook of Frequency Stability
Analysis", NIST SP 1065 (2008), Sec. 3.3.4 (overlapping ADEV estimator).
"""
from __future__ import annotations

import numpy as np


def overlapping_adev(x: np.ndarray, fs_hz: float, n_octaves: int | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Overlapping Allan deviation of a rate-domain signal x(t) (e.g. an
    acceleration time series in m/s^2), sampled uniformly at fs_hz.

    Returns (tau, adev, n_clusters) where tau is in seconds and adev has the
    same units as x (e.g. m/s^2 for an acceleration ADEV).

    Standard estimator (Riley, NIST SP 1065, Eq. 16 applied to the
    "phase"-equivalent cumulative sum of x, which is the standard trick for
    computing ADEV directly on a rate/rectangular-average signal):

        sigma_A^2(tau) = 1 / (2 (M-2m) tau^2) * sum_{i=1}^{M-2m} (S[i+2m] - 2 S[i+m] + S[i])^2

    where S is the cumulative sum of x * dt (the integral, i.e. "phase"),
    m = tau / dt is the averaging factor (in samples), and M is the number
    of phase samples (len(x)+1).
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    dt = 1.0 / fs_hz
    # Integrate to get the "phase" (cumulative) signal, length n+1, S[0]=0.
    s = np.concatenate(([0.0], np.cumsum(x) * dt))

    if n_octaves is None:
        n_octaves = int(np.floor(np.log2(n / 4))) if n >= 8 else 1
        n_octaves = max(n_octaves, 1)

    taus = []
    adevs = []
    counts = []
    for octave in range(n_octaves):
        m = 2**octave
        tau = m * dt
        if n - 2 * m < 2:
            break
        # Overlapping second difference of the phase signal.
        d2 = s[2 * m :] - 2 * s[m:-m] + s[: -2 * m]
        n_clusters = len(d2)
        var = np.sum(d2**2) / (2.0 * n_clusters * tau**2)
        taus.append(tau)
        adevs.append(np.sqrt(var))
        counts.append(n_clusters)

    return np.array(taus), np.array(adevs), np.array(counts)


def fit_white_noise_coefficient(
    tau: np.ndarray, adev: np.ndarray, n_points: int = 2
) -> tuple[float, np.ndarray]:
    """Estimate the white-noise sensitivity coefficient N in
    adev(tau) = N / sqrt(tau), using the shortest `n_points` octaves.

    This is the standard vendor-datasheet convention (read the noise
    density off the ADEV curve at the shortest available averaging time,
    i.e. close to the raw sample rate), rather than an automated search for
    a -1/2 log-log slope over the whole curve. The latter was tried first
    and rejected: real accelerometer records (this one included -- see
    docs/specs/raw/DATA_JARLAUD_NOTES.md) commonly show mechanical
    resonances at intermediate tau (here, tau ~ 3-100 ms, i.e. ~10-300 Hz,
    matching the resonances the source paper itself documents in its
    Fig. 4) that transiently mimic a -1/2 slope without being genuine
    broadband sensor noise, which made an automatic slope-scan fit
    unreliable and non-reproducible on this dataset.

    Returns (N, mask) where N has units of adev*sqrt(s) (e.g.
    m/s^2/sqrt(Hz) for an acceleration ADEV) and mask selects the points
    used (the shortest n_points octaves).
    """
    n_points = min(n_points, len(tau))
    mask = np.zeros(len(tau), dtype=bool)
    mask[:n_points] = True
    log_tau = np.log(tau)
    log_adev = np.log(adev)
    # adev = N * tau^-0.5  =>  log(adev) + 0.5*log(tau) = log(N).
    log_n = np.mean(log_adev[mask] + 0.5 * log_tau[mask])
    n_fit = np.exp(log_n)
    return float(n_fit), mask


def find_floor(tau: np.ndarray, adev: np.ndarray) -> tuple[float, float]:
    """Return (adev_floor, tau_at_floor): the minimum of the ADEV curve."""
    idx = int(np.argmin(adev))
    return float(adev[idx]), float(tau[idx])
