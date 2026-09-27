"""GNSS receiver: tracking-lock logic + weighted-least-squares PVT + RAIM.

WLS PVT weighted by the INVERSE of the same UERE error-budget variance the
signal model actually draws from (``fedqpnt.gnss.signal.uere_variance_m2`` --
single source of truth, see DECISION from Master WP-3.x review round 2: the
receiver's weight must match the true measurement covariance, otherwise the
RAIM chi-square statistic has no calibrated meaning). Standard weighted-LS
PVT practice: Misra & Enge, "Global Positioning System: Signals,
Measurements, and Performance", 2nd ed., Ganga-Jamuna Press, 2006, Ch. 6.
RAIM statistic = weighted sum-of-squares of post-fit residuals (chi-square
test), classic Parkinson & Axelrad snapshot RAIM (Parkinson & Axelrad,
"Autonomous GPS Integrity Monitoring Using the Pseudorange Residual",
Navigation, 1988): with a correctly-weighted W (= true inverse covariance)
and n satellites / 4 estimated states, raim_stat ~ chi-square(n-4) under
the null (no attack), which is what makes RAIM calibration testable.

PDOP uses the standard UNWEIGHTED geometry-only definition (Kaplan & Hegarty
2017 Ch.5): PDOP = sqrt(trace((H^T H)^-1)[0:3,0:3])) with H built from unit
line-of-sight vectors, independent of the measurement-noise weighting.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from fedqpnt.core.types import GnssEpoch, GnssFix, C_LIGHT
from fedqpnt.gnss.signal import uere_variance_m2, doppler_thermal_sigma_mps

CN0_LOCK_THRESHOLD_DBHZ = 25.0     # below this, lock is lost (typical L1 C/A tracking threshold)
REACQUISITION_DELAY_S = 1.0        # s, cold/warm reacquisition after lock loss (typical ~0.5-2 s)


@dataclass
class _SatLockState:
    locked: bool = True
    lost_since: float | None = None


@dataclass
class GnssReceiver:
    """Implements GnssReceiver protocol: solve(epoch) -> GnssFix."""
    cn0_lock_threshold_dbhz: float = CN0_LOCK_THRESHOLD_DBHZ
    reacq_delay_s: float = REACQUISITION_DELAY_S
    min_sats: int = 4
    _lock: dict = field(default_factory=dict)   # prn -> _SatLockState
    _last_fix: GnssFix | None = field(default=None)

    def config(self) -> dict:
        return dict(cn0_lock_threshold_dbhz=self.cn0_lock_threshold_dbhz,
                    reacq_delay_s=self.reacq_delay_s, min_sats=self.min_sats)

    def _apply_lock_logic(self, epoch: GnssEpoch) -> list:
        usable = []
        for o in epoch.obs:
            st = self._lock.setdefault(o.prn, _SatLockState())
            below = (o.cn0_dbhz < self.cn0_lock_threshold_dbhz) or (not o.tracked)
            if below:
                if st.locked:
                    st.locked = False
                    st.lost_since = epoch.t
            else:
                if not st.locked:
                    # require reacquisition delay of continuous good signal
                    if st.lost_since is not None and (epoch.t - st.lost_since) >= self.reacq_delay_s:
                        st.locked = True
                        st.lost_since = None
                else:
                    st.lost_since = None
            if st.locked:
                usable.append(o)
        return usable

    def solve(self, epoch: GnssEpoch) -> GnssFix:
        usable = self._apply_lock_logic(epoch)
        n = len(usable)
        if n < self.min_sats:
            fix = GnssFix(
                t=epoch.t, pos=np.full(3, np.nan), vel=np.full(3, np.nan),
                clk_bias=np.nan, clk_drift=np.nan,
                cov_pos=np.full((3, 3), np.nan), cov_vel=np.full((3, 3), np.nan),
                residual_rms=np.nan, num_sats=n,
                mean_cn0=float(np.mean([o.cn0_dbhz for o in usable])) if usable else 0.0,
                std_cn0=float(np.std([o.cn0_dbhz for o in usable])) if usable else 0.0,
                agc_db=epoch.agc_db, valid=False, raim_stat=np.nan,
                cn0_per_sat={o.prn: o.cn0_dbhz for o in usable},
                elev_per_sat={o.prn: o.elevation for o in usable},
            )
            self._last_fix = fix
            return fix

        x0 = self._last_fix.pos.copy() if (self._last_fix is not None and self._last_fix.valid) else np.zeros(3)
        b0 = self._last_fix.clk_bias if (self._last_fix is not None and self._last_fix.valid) else 0.0
        pos, clk_bias, cov_pos, resid, W, H, pdop = self._wls_pos(usable, x0, b0)

        v0 = self._last_fix.vel.copy() if (self._last_fix is not None and self._last_fix.valid) else np.zeros(3)
        d0 = self._last_fix.clk_drift if (self._last_fix is not None and self._last_fix.valid) else 0.0
        vel, clk_drift, cov_vel = self._wls_vel(usable, pos, v0, d0, W, H)

        raim_stat = float(resid.T @ W @ resid) if n > 4 else 0.0
        residual_rms = float(np.sqrt(np.mean(resid ** 2))) if n > 0 else np.nan
        cn0s = [o.cn0_dbhz for o in usable]

        fix = GnssFix(
            t=epoch.t, pos=pos, vel=vel, clk_bias=clk_bias, clk_drift=clk_drift,
            cov_pos=cov_pos, cov_vel=cov_vel, residual_rms=residual_rms, num_sats=n,
            mean_cn0=float(np.mean(cn0s)), std_cn0=float(np.std(cn0s)),
            agc_db=epoch.agc_db, valid=True, raim_stat=raim_stat, pdop=pdop,
            cn0_per_sat={o.prn: o.cn0_dbhz for o in usable},
            elev_per_sat={o.prn: o.elevation for o in usable},
        )
        self._last_fix = fix
        return fix

    @staticmethod
    def _weight(o) -> float:
        """Inverse of the true pseudorange measurement variance (UERE budget
        from fedqpnt.gnss.signal -- single source of truth, see module
        docstring). This is what calibrates the RAIM chi-square statistic."""
        var = uere_variance_m2(o.elevation, o.cn0_dbhz)
        return 1.0 / max(var, 1e-6)

    @staticmethod
    def _weight_vel(o) -> float:
        """Inverse of the true pseudorange-rate (Doppler) measurement variance."""
        sigma = doppler_thermal_sigma_mps(o.cn0_dbhz)
        return 1.0 / max(sigma ** 2, 1e-6)

    def _wls_pos(self, obs: list, x0: np.ndarray, b0: float, n_iter: int = 8):
        x = x0.copy()
        b = b0
        n = len(obs)
        W = np.diag([self._weight(o) for o in obs])
        H = np.zeros((n, 4))
        resid = np.zeros(n)
        for _ in range(n_iter):
            for k, o in enumerate(obs):
                los = o.sat_pos - x
                r = np.linalg.norm(los)
                u = los / r
                pred = r + b
                resid[k] = o.pseudorange - pred
                H[k, 0:3] = -u
                H[k, 3] = 1.0
            HtWH = H.T @ W @ H
            try:
                dx = np.linalg.solve(HtWH, H.T @ W @ resid)
            except np.linalg.LinAlgError:
                dx = np.linalg.lstsq(HtWH, H.T @ W @ resid, rcond=None)[0]
            x = x + dx[0:3]
            b = b + dx[3]
            if np.linalg.norm(dx[0:3]) < 1e-5:
                break
        try:
            cov = np.linalg.inv(H.T @ W @ H)
        except np.linalg.LinAlgError:
            cov = np.full((4, 4), np.nan)
        cov_pos = cov[0:3, 0:3]
        try:
            G = np.linalg.inv(H.T @ H)  # unweighted geometry-only DOP matrix
            pdop = float(np.sqrt(np.trace(G[0:3, 0:3])))
        except np.linalg.LinAlgError:
            pdop = float("nan")
        return x, b, cov_pos, resid, W, H, pdop

    def _wls_vel(self, obs: list, pos: np.ndarray, v0: np.ndarray, d0: float, W: np.ndarray, H_geom: np.ndarray):
        n = len(obs)
        H = H_geom.copy()  # same geometry (direction cosines + clock col), velocity-specific weight
        W = np.diag([self._weight_vel(o) for o in obs])
        y = np.zeros(n)
        for k, o in enumerate(obs):
            los = o.sat_pos - pos
            r = np.linalg.norm(los)
            u = los / r
            y[k] = o.pseudorange_rate - (-np.dot(o.sat_vel, u))
            H[k, 0:3] = u  # d(range_rate)/d(vel) sign convention
            H[k, 3] = 1.0
        HtWH = H.T @ W @ H
        try:
            sol = np.linalg.solve(HtWH, H.T @ W @ y)
            cov = np.linalg.inv(HtWH)
        except np.linalg.LinAlgError:
            sol = np.linalg.lstsq(HtWH, H.T @ W @ y, rcond=None)[0]
            cov = np.full((4, 4), np.nan)
        vel = sol[0:3]
        drift = sol[3]
        return vel, drift, cov[0:3, 0:3]
