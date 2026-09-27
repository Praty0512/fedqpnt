"""Overlapping Allan deviation (WP-2.3).

Standard estimator, e.g. IEEE Std 952-1997 Annex C / El-Sheimy, Hou & Niu
(2008) "Analysis and Modeling of Inertial Sensors Using Allan Variance",
IEEE Trans. Instrum. Meas. 57(1):140-149. Overlapping estimator (uses every
possible cluster start, not just non-overlapping blocks) for lower variance
at a given number of samples, following Riley (NIST SP1065 "Handbook of
Frequency Stability Analysis", 2008), sec. 3.4.

For a scalar random process sampled at rate f_s = 1/dt with N samples, and
cluster length m = round(tau / dt):

    AVAR(tau) = 1 / (2 * tau^2 * (N - 2m)) * sum_{k=0}^{N-2m-1}
                    (X[k+2m] - 2*X[k+m] + X[k])^2

where X is the cumulative sum ("phase") of the sampled process
(X[0]=0, X[k] = dt * sum_{i<k} x[i]). ADEV = sqrt(AVAR).
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares


def overlapping_adev(
    x: np.ndarray,
    dt: float,
    taus: np.ndarray | None = None,
    n_octaves: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Overlapping Allan deviation of a rate-like sequence ``x`` sampled at 1/dt.

    Parameters
    ----------
    x : (N,) array of the instantaneous quantity (e.g. gyro rate [rad/s] or
        accelerometer specific force [m/s^2]), sampled uniformly at dt.
    dt : sample interval [s].
    taus : optional explicit averaging times [s]; if omitted, a log-spaced
        set from 1 sample up to N/4 samples is used (dyadic-ish spacing).

    Returns
    -------
    taus_out, adev, n_clusters : arrays of the same length. ``n_clusters`` is
        the number of overlapping clusters used at each tau (for weighting /
        confidence-interval computations downstream).
    """
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[0]
    if n < 4:
        raise ValueError("need at least 4 samples for Allan deviation")

    # Cumulative integral ("phase"): X[0] = 0, X[k] = dt * sum_{i<k} x[i]
    big_x = np.concatenate(([0.0], np.cumsum(x))) * dt  # length n+1

    if taus is None:
        max_m = max(1, n // 4)
        m_list = np.unique(np.geomspace(1, max_m, num=max(2, 30)).astype(int))
    else:
        m_list = np.unique(np.maximum(1, np.round(np.asarray(taus) / dt).astype(int)))
        m_list = m_list[m_list <= n // 4] if n // 4 >= 1 else m_list[:0]

    taus_out = []
    adevs = []
    nclusters = []
    for m in m_list:
        m = int(m)
        if 2 * m >= len(big_x):
            continue
        # second difference of the phase, stride 1 (overlapping)
        d2 = big_x[2 * m:] - 2.0 * big_x[m:-m] + big_x[:-2 * m]
        k = d2.shape[0]
        if k < 1:
            continue
        avar = np.sum(d2 ** 2) / (2.0 * (m * dt) ** 2 * k)
        taus_out.append(m * dt)
        adevs.append(np.sqrt(avar))
        nclusters.append(k)

    return np.array(taus_out), np.array(adevs), np.array(nclusters)


def _avar_gm1(tau: np.ndarray, sigma: float, tau_c: float) -> np.ndarray:
    """Exact overlapping-Allan-variance of a first-order Gauss-Markov (GM1)
    process with stationary std ``sigma`` and correlation time ``tau_c``
    (e.g. Barnes 1971 / El-Sheimy, Hou & Niu 2008 Table II form). Verified
    numerically against direct Monte-Carlo simulation of a GM1 sequence
    (matches to <1% once the standard formula's overall variance-domain
    factor of 2 is included, i.e. AVAR = 2*sigma^2*tau_c/tau*[1 - ...] --
    NOT sigma^2*tau_c/tau*[1 - ...] as printed in some secondary sources;
    the factor of 2 was confirmed here by simulation, not assumed)."""
    x = tau / tau_c
    return 2.0 * sigma ** 2 * tau_c / tau * (1.0 - (tau_c / (2.0 * tau)) * (3.0 - 4.0 * np.exp(-x) + np.exp(-2.0 * x)))


def fit_white_and_bias_instability(
    taus: np.ndarray, adev: np.ndarray, n_clusters: np.ndarray | None = None,
) -> dict[str, float]:
    """Nonlinear noise-coefficient fit of an Allan-deviation curve to the
    standard three-term IMU/CAI noise model: white noise (N/sqrt(tau)) +
    GM1 bias instability (sigma, tau_c) + rate random walk (K*sqrt(tau/3))
    (IEEE Std 952-1997 Annex C; El-Sheimy, Hou & Niu 2008). Fits in
    log(AVAR) with weights sqrt(n_clusters) (more overlapping clusters =
    lower-variance estimate at that tau), via Levenberg-Marquardt on
    log-parameters (keeps N, sigma, tau_c, K positive).

    This replaces two earlier, less accurate approaches (kept only in the
    module's git history): (1) reading the curve's global minimum, which is
    wrong whenever the GM1 term dominates everywhere and the curve is a
    rounded hump rather than a bathtub; (2) a linear (white + flat + ramp)
    regression, which is systematically biased low for a genuine GM1 shape
    since a flat term cannot represent a hump. The GM1 fit implemented here
    was validated to recover known (N, sigma, tau_c) to <2% on synthetic
    GM1+white data at durations >= ~40*tau_c (see tests/test_sensors_imu.py,
    tests/test_sensors_quantum.py).

    Returns the bias-instability figure via the standard datasheet
    convention ADEV_floor = B*sqrt(2*ln2/pi) ~= 0.664*B, i.e. B = 0.664*sigma.
    """
    taus = np.asarray(taus, dtype=np.float64)
    adev = np.asarray(adev, dtype=np.float64)
    if taus.size < 4:
        return {"N_white": float("nan"), "B_bias_instability": float("nan"), "K_rate_random_walk": float("nan")}

    if n_clusters is not None and len(n_clusters) == len(taus):
        weights = np.sqrt(np.asarray(n_clusters, dtype=np.float64))
        weights = weights / np.max(weights)
    else:
        weights = np.ones_like(taus)

    avar = adev ** 2
    n0 = float(adev[0] * np.sqrt(taus[0]))
    sigma0 = float(np.max(adev) / 0.664)
    tauc0 = float(taus[len(taus) // 2])
    x0 = [np.log(max(n0, 1e-30)), np.log(max(sigma0, 1e-30)), np.log(max(tauc0, 1e-6)), np.log(1e-30)]

    def model(params):
        logN, logSigma, logTauc, logK = params
        n_w, sigma, tau_c, k_rrw = np.exp(params)
        return n_w ** 2 / taus + _avar_gm1(taus, sigma, tau_c) + k_rrw ** 2 * taus / 3.0

    def resid(params):
        return weights * (np.log(model(params)) - np.log(avar))

    lb = np.array([-60.0, -60.0, np.log(max(taus[0] * 1e-3, 1e-9)), -60.0])
    ub = np.array([30.0, 30.0, np.log(taus[-1] * 1e4), 30.0])
    x0 = np.clip(np.array(x0, dtype=np.float64), lb + 1e-9, ub - 1e-9)
    res = least_squares(resid, x0, max_nfev=20000, bounds=(lb, ub))
    n_white, sigma, tau_c, k_rrw = np.exp(res.x)
    return {
        "N_white": float(n_white),
        "B_bias_instability": float(0.664 * sigma),
        "K_rate_random_walk": float(k_rrw),
        "tau_c_fit_s": float(tau_c),
    }
