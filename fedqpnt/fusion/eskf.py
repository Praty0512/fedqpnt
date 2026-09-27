"""15-state error-state EKF, loosely-coupled GNSS/IMU + CAI hybridisation
(WP-4.1, ARCHITECTURE.md section 2). Implements ``fedqpnt.core.interfaces.FusionFilter``.

This module MUST NEVER import ``fedqpnt.sim`` truth, ``fedqpnt.attacks`` or
``AttackLabel``: it only ever sees sensor outputs (``ImuSample``,
``QuantumSample``, ``GnssFix``) and the ``TrustState`` handed to it by the
trust engine.

State layout (error state, n=15), Ĉ = C_nb nominal attitude (stored as a DCM):
    delta x = [ dp(0:3), dv(3:6), psi(6:9), dba(9:12), dbg(12:15) ]
Nominal state: p, v (ENU), C (DCM), b_a, b_g.

Equation numbers below refer to ARCHITECTURE.md section 2.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.stats import chi2

from fedqpnt.core.types import G0, GnssFix, ImuSample, Innovation, NavSolution, QuantumSample, TrustState
from fedqpnt.core.world import gravity_gradient, gravity_n
from fedqpnt.sim.rotations import so3_exp, dcm_to_euler

I3 = np.eye(3)
Z3 = np.zeros((3, 3))


def _skew(v: np.ndarray) -> np.ndarray:
    x, y, z = v
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def _spd_or_fallback(cov: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    cov = np.asarray(cov, dtype=float)
    if cov.shape != fallback.shape or not np.all(np.isfinite(cov)):
        return fallback.copy()
    try:
        np.linalg.cholesky(0.5 * (cov + cov.T))
    except np.linalg.LinAlgError:
        return fallback.copy()
    return 0.5 * (cov + cov.T)


@dataclass
class ESKFConfig:
    world: str = "flat"
    kappa_R: float = 1.0            # [ASSUMPTION; swept] GNSS fix covariance inflation (LC bias per Sec 2.1)
    kappa_Q: float = 1.0            # [ASSUMPTION; swept] process-noise scale
    kappa_zoh: float = 10.0         # Q scale during IMU ZOH dropout ticks (Sec 1.4)
    max_gap_s: float = 0.1          # IMU dropout gap beyond which ZOH is no longer trusted (Sec 1.4)
    w_min: float = 0.02             # Sec 2.7
    w_excl: float = 0.05            # Sec 2.7
    alpha_gate: float = 1e-4        # Sec 2.7
    sigma_win_g: float = 1e-5       # [ASSUMPTION; swept over {1e-6,1e-5,1e-4}] x G0, Sec 2.5 CAI window mismatch
    cai_buffer_min_s: float = 5.0   # Sec 2.5: IMU buffer length = max(5s, 2*cycle_time)
    model_sf_mis: bool = False      # D-030: Master's dt-correlation-time PSD choice was wrong
                                     # for a per-run CONSTANT error (can't be white-noise
                                     # modelled); disabled by default, kept for ablation only
    bias_model: str = "random_walk"  # D-035: Sec 2.4's F[9:12,9:12]=-I/tau_a (and the gyro
                                      # equivalent) mean-reverts the ENTIRE b_a/b_g error state
                                      # incl. the P0 share from the non-decaying, per-run-constant
                                      # turn-on bias (fedqpnt/sensors/imu.py) -- P shrinks toward
                                      # the tiny GM1 stationary variance while the true error does
                                      # not, causing severe pure-INS NEES inconsistency (~11x by
                                      # 300s, industrial_mems, confirmed analytically as e^(-2t/tau)).
                                      # "random_walk" (new default) drops the decay term (F block
                                      # = 0); "gm1" keeps the old (pre-D-035) mean-reverting
                                      # behaviour, retained for ablation only.
    fallback_cov_pos: np.ndarray = field(default_factory=lambda: np.diag([9.0, 9.0, 25.0]))
    fallback_cov_vel: np.ndarray = field(default_factory=lambda: np.diag([0.01, 0.01, 0.01]))


class ESKF:
    """Error-state EKF implementing ``FusionFilter`` (contract v0.2)."""

    N = 15

    def __init__(self, imu_config: dict[str, Any], config: ESKFConfig | None = None):
        """``imu_config`` = the IMU model's ``.config()`` dict (Sec 2.4: the
        filter reads VRW/ARW/bias-instability from it and does not
        re-invent them)."""
        self.cfg = config or ESKFConfig()
        self._read_imu_noise(imu_config)

        self.t: float | None = None
        self.p = np.zeros(3)
        self.v = np.zeros(3)
        self.C = np.eye(3)
        self.b_a = np.zeros(3)
        self.b_g = np.zeros(3)
        self.P = np.eye(self.N) * 1e-6

        self._f_hat_prev: np.ndarray | None = None
        self._omega_hat_prev: np.ndarray | None = None
        self._last_raw_imu: ImuSample | None = None
        self._gap_accum_s: float = 0.0

        self._imu_buffer: list[tuple[float, np.ndarray]] = []  # (t, f_tilde) for CAI window mean
        self._pending: dict[str, tuple] = {}  # sensor -> (nu, H, R_nom, S_nom, dof)
        self._last_clk_bias: float = float("nan")
        self.initialized = False

    # ------------------------------------------------------------------
    def _read_imu_noise(self, imu_config: dict[str, Any]) -> None:
        acc = imu_config["accel_noise_SI"]
        gyr = imu_config["gyro_noise_SI"]
        self.vrw = float(acc["random_walk_per_sqrt_s"])          # [m/s^2 * sqrt(s)]
        self.arw = float(gyr["random_walk_per_sqrt_s"])          # [rad/s * sqrt(s)]
        sigma_ba = float(acc["bias_instability_gm1_sigma"])
        tau_a = float(acc["bias_instability_gm1_tau_c_s"])
        sigma_bg = float(gyr["bias_instability_gm1_sigma"])
        tau_g = float(gyr["bias_instability_gm1_tau_c_s"])
        self.tau_a = tau_a if tau_a > 0 else np.inf
        self.tau_g = tau_g if tau_g > 0 else np.inf
        # q_b = 2 sigma_BI^2 / tau_c (Sec 2.4, GM1 driving PSD)
        self.q_ba = (2.0 * sigma_ba ** 2 / tau_a) if tau_a > 0 else 0.0
        self.q_bg = (2.0 * sigma_bg ** 2 / tau_g) if tau_g > 0 else 0.0
        self.sigma_ba_turnon = float(acc.get("turn_on_bias_std", sigma_ba))
        self.sigma_bg_turnon = float(gyr.get("turn_on_bias_std", sigma_bg))
        # D-028: unmodelled per-run-constant scale-factor/misalignment error
        # (fedqpnt/sensors/imu.py AxisErrorParams), read from the IMU's own
        # config() -- no free tuning constant.
        self.sigma_sf_a = float(acc.get("scale_factor_std", 0.0))
        self.sigma_mis_a = float(acc.get("misalignment_std_rad", 0.0))
        self.sigma_sf_g = float(gyr.get("scale_factor_std", 0.0))
        self.sigma_mis_g = float(gyr.get("misalignment_std_rad", 0.0))

    # ------------------------------------------------------------------
    def config(self) -> dict[str, Any]:
        return {
            "type": "ESKF", "world": self.cfg.world, "kappa_R": self.cfg.kappa_R,
            "kappa_Q": self.cfg.kappa_Q, "kappa_zoh": self.cfg.kappa_zoh,
            "w_min": self.cfg.w_min, "w_excl": self.cfg.w_excl, "alpha_gate": self.cfg.alpha_gate,
            "sigma_win_g": self.cfg.sigma_win_g, "vrw": self.vrw, "arw": self.arw,
            "q_ba": self.q_ba, "q_bg": self.q_bg, "tau_a": self.tau_a, "tau_g": self.tau_g,
            "model_sf_mis": self.cfg.model_sf_mis, "bias_model": self.cfg.bias_model,
            "sigma_sf_a": self.sigma_sf_a, "sigma_mis_a": self.sigma_mis_a,
            "sigma_sf_g": self.sigma_sf_g, "sigma_mis_g": self.sigma_mis_g,
        }

    # ------------------------------------------------------------------
    def initialize_static(self, t0: float, pos0: np.ndarray, att0: np.ndarray,
                           vel0: np.ndarray | None = None) -> None:
        """Sec 2.9 initialisation. ``att0`` (roll,pitch,yaw) must be supplied
        by the caller (levelling from the first-10s mean f_b, heading from
        truth + N(0,(2 deg)^2) or an external aiding source) -- this filter
        never computes it from truth itself."""
        self.t = t0
        self.p = np.array(pos0, dtype=float).copy()
        self.v = np.zeros(3) if vel0 is None else np.array(vel0, dtype=float).copy()
        from fedqpnt.sim.rotations import euler_to_dcm
        self.C = euler_to_dcm(np.asarray(att0, dtype=float))
        self.b_a = np.zeros(3)
        self.b_g = np.zeros(3)
        mrad = 1e-3
        self.P = np.diag([
            3.0 ** 2, 3.0 ** 2, 3.0 ** 2,
            0.1 ** 2, 0.1 ** 2, 0.1 ** 2,
            mrad ** 2, mrad ** 2, (35 * mrad) ** 2,
            self.sigma_ba_turnon ** 2, self.sigma_ba_turnon ** 2, self.sigma_ba_turnon ** 2,
            self.sigma_bg_turnon ** 2, self.sigma_bg_turnon ** 2, self.sigma_bg_turnon ** 2,
        ])
        self._f_hat_prev = None
        self._omega_hat_prev = None
        self._last_raw_imu = None
        self._imu_buffer = []
        self._gap_accum_s = 0.0
        self.initialized = True

    # ------------------------------------------------------------------
    def propagate(self, t: float, imu: ImuSample | None) -> None:
        if not self.initialized:
            return
        dt = t - self.t
        if dt <= 0:
            self.t = t
            return

        is_zoh = imu is None
        if is_zoh:
            if self._last_raw_imu is None:
                self.t = t
                return
            self._gap_accum_s += dt
            f_tilde = self._last_raw_imu.f_b
            omega_tilde = self._last_raw_imu.omega_b
        else:
            self._gap_accum_s = 0.0
            f_tilde = imu.f_b
            omega_tilde = imu.omega_b
            self._last_raw_imu = imu
            self._imu_buffer.append((t, np.asarray(imu.f_b, dtype=float)))

        gap_ok = self._gap_accum_s <= self.cfg.max_gap_s

        f_hat_new = f_tilde - self.b_a
        omega_hat_new = omega_tilde - self.b_g
        if self._f_hat_prev is None:
            self._f_hat_prev = f_hat_new
            self._omega_hat_prev = omega_hat_new

        # --- mechanisation (Sec 2.3): trapezoid + coning ---
        om_avg = 0.5 * (self._omega_hat_prev + omega_hat_new)
        coning = (1.0 / 12.0) * np.cross(self._omega_hat_prev, omega_hat_new)
        phi_vec = om_avg * dt + coning * dt ** 2
        dC = so3_exp(phi_vec)
        C_old = self.C
        C_new = C_old @ dC

        g_n = gravity_n(self.p, self.cfg.world)
        f_n_old = C_old @ self._f_hat_prev
        f_n_new = C_new @ f_hat_new
        v_new = self.v + (0.5 * (f_n_old + f_n_new) + g_n) * dt
        p_new = self.p + 0.5 * (self.v + v_new) * dt

        # --- process model / covariance (Sec 2.4) ---
        f_n_mid = 0.5 * (f_n_old + f_n_new)
        C_used = C_new
        F = np.zeros((self.N, self.N))
        F[0:3, 3:6] = I3
        F[3:6, 0:3] = gravity_gradient(self.cfg.world)
        F[3:6, 6:9] = _skew(f_n_mid)
        F[3:6, 9:12] = -C_used
        F[6:9, 12:15] = C_used
        if self.cfg.bias_model == "gm1":
            if np.isfinite(self.tau_a):
                F[9:12, 9:12] = -I3 / self.tau_a
            if np.isfinite(self.tau_g):
                F[12:15, 12:15] = -I3 / self.tau_g
        # else "random_walk" (D-035 default): F blocks stay 0 -- q_ba/q_bg
        # (still 2*sigma_gm^2/tau_c) are kept as-is as an over-bound on the
        # GM1 part of the budget; negligible vs the non-decaying turn-on
        # share over any realistic mission duration.

        G = np.zeros((self.N, 12))
        G[3:6, 0:3] = C_used
        G[6:9, 3:6] = -C_used
        G[9:12, 6:9] = I3
        G[12:15, 9:12] = I3

        Qc = np.diag([self.vrw ** 2] * 3 + [self.arw ** 2] * 3 + [self.q_ba] * 3 + [self.q_bg] * 3)
        Qc = Qc * self.cfg.kappa_Q
        if is_zoh and not gap_ok:
            # beyond max_gap_s: freeze the correction (pure open-loop INS,
            # trust engine drives w_imu -> w_min separately), still inflate Q heavily.
            Qc = Qc * self.cfg.kappa_zoh * 10.0
        elif is_zoh:
            Qc = Qc * self.cfg.kappa_zoh

        if self.cfg.model_sf_mis:
            # D-028: unmodelled per-run-constant scale-factor/misalignment
            # error (fedqpnt/sensors/imu.py AxisErrorParams) is not an ESKF
            # state; it aliases into psi (via gyro) and dv (via accel),
            # dynamics-dependent (grows with the actual rate / specific
            # force, not stationary white noise). Per axis i: scale-factor
            # error ~ sigma_sf * |x_i| (same axis), misalignment ~
            # sigma_mis * |x_perp,i| (cross-axis coupling from the other
            # two axes), both body-frame, sigma_* read only from the IMU's
            # own config() (no free tuning constant). PSD conversion: a
            # per-run CONSTANT error held over one propagation step
            # contributes one-step variance (sigma*x)^2 * dt^2 to the
            # integrated state (bias * dt); an equivalent white-noise PSD
            # S with Qd ~= S*dt reproduces that SAME one-step variance for
            # S = (sigma*x)^2 * dt, i.e. treating the correlation time as
            # dt (the shortest defensible choice absent a fitted tau_c;
            # this under-covers the true long-horizon correlated growth of
            # a persistent constant, so it is a conservative floor, not an
            # exact model of the persistent term).
            f_hat_mid = 0.5 * (self._f_hat_prev + f_hat_new)  # body frame
            om = om_avg  # body frame
            f_perp = np.sqrt(np.maximum(np.sum(f_hat_mid ** 2) - f_hat_mid ** 2, 0.0))
            om_perp = np.sqrt(np.maximum(np.sum(om ** 2) - om ** 2, 0.0))
            extra_a = (self.sigma_sf_a * np.abs(f_hat_mid)) ** 2 + (self.sigma_mis_a * f_perp) ** 2
            extra_g = (self.sigma_sf_g * np.abs(om)) ** 2 + (self.sigma_mis_g * om_perp) ** 2
            Qc[0:3, 0:3] += np.diag(extra_a * dt)
            Qc[3:6, 3:6] += np.diag(extra_g * dt)

        Fdt = F * dt
        Phi = np.eye(self.N) + Fdt + 0.5 * (Fdt @ Fdt)
        GQGt = G @ Qc @ G.T
        Qd = 0.5 * (Phi @ GQGt + GQGt @ Phi.T) * dt

        self.P = Phi @ self.P @ Phi.T + Qd
        self._hygiene()

        self.C = C_new
        self.v = v_new
        self.p = p_new
        self._f_hat_prev = f_hat_new
        self._omega_hat_prev = omega_hat_new
        self.t = t

        if self._imu_buffer:
            tmin = t - max(self.cfg.cai_buffer_min_s, 10.0)
            self._imu_buffer = [(ti, fi) for ti, fi in self._imu_buffer if ti >= tmin]

    def _hygiene(self) -> None:
        self.P = 0.5 * (self.P + self.P.T)
        w = np.linalg.eigvalsh(self.P)
        if w.min() < 1e-12:
            self.P = self.P + 1e-12 * np.eye(self.N)

    # ------------------------------------------------------------------
    def innovations(self, t: float, fix: GnssFix | None, quantum: QuantumSample | None) -> list[Innovation]:
        self._pending = {}
        out: list[Innovation] = []
        if not self.initialized:
            return out

        if fix is not None and fix.valid and np.all(np.isfinite(fix.pos)) and np.all(np.isfinite(fix.vel)):
            H = np.zeros((6, self.N))
            H[0:3, 0:3] = I3
            H[3:6, 3:6] = I3
            R_pos = self.cfg.kappa_R * _spd_or_fallback(fix.cov_pos, self.cfg.fallback_cov_pos)
            R_vel = self.cfg.kappa_R * _spd_or_fallback(fix.cov_vel, self.cfg.fallback_cov_vel)
            R = np.zeros((6, 6))
            R[0:3, 0:3] = R_pos
            R[3:6, 3:6] = R_vel
            nu = np.concatenate([self.p - fix.pos, self.v - fix.vel])
            S = H @ self.P @ H.T + R
            nis = float(nu @ np.linalg.solve(S, nu))
            accepted = nis <= chi2.ppf(1.0 - self.cfg.alpha_gate, 6)
            self._pending["gnss"] = (nu, H, R, 6)
            out.append(Innovation(t=t, sensor="gnss", nu=nu, S=S, nis=nis, dof=6, accepted=bool(accepted)))
            self._last_clk_bias = fix.clk_bias

        if quantum is not None and quantum.valid:
            axes = [a for a in range(3) if np.isfinite(quantum.f_b[a]) and np.isfinite(quantum.variance[a])]
            if axes and self._imu_buffer:
                T = quantum.t_interrogation
                use_triangular = quantum.response == "triangular" and np.isfinite(T) and T > 0
                if use_triangular:
                    win_start = t - 2.0 * T
                    win_len = 2.0 * T
                else:
                    win_start = t - quantum.cycle_time
                    win_len = quantum.cycle_time
                samples = [(ti, fi) for ti, fi in self._imu_buffer if win_start - 1e-9 <= ti <= t + 1e-9]
                if samples:
                    taus = np.array([ti - win_start for ti, _ in samples])
                    fs = np.array([fi for _, fi in samples])
                    if use_triangular:
                        w = np.where(taus <= T, taus, win_len - taus)
                        w = np.clip(w, 0.0, None)
                    else:
                        w = np.ones_like(taus)
                    if w.sum() > 0:
                        w = w / w.sum()
                        f_bar_imu = (w[:, None] * (fs - self.b_a[None, :])).sum(axis=0)
                        nu_full = quantum.f_b - f_bar_imu
                        nu_q = nu_full[axes]
                        H = np.zeros((len(axes), self.N))
                        for row, ax in enumerate(axes):
                            H[row, 9 + ax] = 1.0
                        T_W = win_len
                        sigma_win2 = (self.cfg.sigma_win_g * G0) ** 2
                        R_q = np.diag(quantum.variance[axes] + (self.vrw ** 2 / max(T_W, 1e-6)) + sigma_win2)
                        S_q = H @ self.P @ H.T + R_q
                        nis_q = float(nu_q @ np.linalg.solve(S_q, nu_q))
                        dof = len(axes)
                        accepted_q = nis_q <= chi2.ppf(1.0 - self.cfg.alpha_gate, dof)
                        self._pending["quantum"] = (nu_q, H, R_q, dof)
                        out.append(Innovation(t=t, sensor="quantum", nu=nu_q, S=S_q, nis=nis_q,
                                               dof=dof, accepted=bool(accepted_q)))
        return out

    # ------------------------------------------------------------------
    def correct(self, t: float, innovations: list[Innovation], trust: TrustState) -> NavSolution:
        if not self.initialized:
            raise RuntimeError("ESKF.correct called before initialize_static()")

        for sensor in ("gnss", "quantum"):
            if sensor not in self._pending:
                continue
            nu, H, R_nom, dof = self._pending[sensor]
            w = trust.weights.get(sensor, 1.0)
            if w < self.cfg.w_excl:
                continue  # exclusion (Sec 2.7)
            R_eff = R_nom / max(w, self.cfg.w_min)
            S_eff = H @ self.P @ H.T + R_eff
            nis_eff = float(nu @ np.linalg.solve(S_eff, nu))
            if nis_eff > chi2.ppf(1.0 - self.cfg.alpha_gate, dof):
                continue  # NIS gate reject (Sec 2.7)
            K = self.P @ H.T @ np.linalg.inv(S_eff)
            dx = K @ nu
            IKH = np.eye(self.N) - K @ H
            self.P = IKH @ self.P @ IKH.T + K @ R_eff @ K.T
            self._hygiene()

            self.p = self.p - dx[0:3]
            self.v = self.v - dx[3:6]
            self.C = so3_exp(dx[6:9]) @ self.C
            self.b_a = self.b_a - dx[9:12]
            self.b_g = self.b_g - dx[12:15]

        self._pending = {}
        att = dcm_to_euler(self.C)
        return NavSolution(
            t=t, pos=self.p.copy(), vel=self.v.copy(), att=att,
            clk_bias=self._last_clk_bias, cov_pos=self.P[0:3, 0:3].copy(),
            trust=trust, cov_vel=self.P[3:6, 3:6].copy(),
            acc_bias=self.b_a.copy(), gyro_bias=self.b_g.copy(),
        )

    # ------------------------------------------------------------------
    def step(self, t: float, imu: ImuSample | None, quantum: QuantumSample | None,
              fix: GnssFix | None, trust: TrustState) -> NavSolution:
        self.propagate(t, imu)
        innov = self.innovations(t, fix, quantum)
        return self.correct(t, innov, trust)
