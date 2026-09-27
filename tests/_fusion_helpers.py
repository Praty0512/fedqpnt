"""Shared validation harness for fedqpnt.fusion (WP-4.1). Test-local, not
part of fedqpnt.fusion itself -- this file imports truth/trajectory freely
(it IS the harness), unlike fedqpnt/fusion/eskf.py which must never do so.
"""
from __future__ import annotations

import numpy as np

from fedqpnt.core.types import TrustState, TruthState
from fedqpnt.core.seeding import stream
from fedqpnt.sim.trajectory import make_trajectory
from fedqpnt.sim.rotations import euler_to_dcm
from fedqpnt.sensors.imu import ClassicalImu
from fedqpnt.sensors.quantum import QuantumAccelerometer
from fedqpnt.gnss.signal import GnssSignalModel
from fedqpnt.gnss.receiver import GnssReceiver
from fedqpnt.fusion import ESKF, ESKFConfig

G0 = 9.80665
TRUST1 = TrustState(t=0.0, weights={"gnss": 1.0, "imu": 1.0, "quantum": 1.0},
                     anomaly_scores={}, attack_detected=False)


def level_att(f_b_mean: np.ndarray) -> tuple[float, float]:
    fx, fy, fz = f_b_mean
    phi = np.arctan2(fy, fz)
    theta = np.arctan2(-fx, np.sqrt(fy ** 2 + fz ** 2))
    return phi, theta


def make_truth_with_hold(traj, duration_s, dt, rng, hold_s=10.0, world="flat"):
    """Prepend a stationary hold segment (Sec 2.9 levelling / Sec 11.2)."""
    tt = traj.generate(duration_s, dt, rng, world=world)
    n_hold = int(round(hold_s / dt))
    att0 = tt.att[0]
    pos0 = tt.pos[0]
    C0 = euler_to_dcm(att0)
    f_b0 = C0.T @ np.array([0.0, 0.0, G0])
    states = []
    for k in range(n_hold):
        t = k * dt
        states.append(TruthState(t=t, pos=pos0, vel=np.zeros(3), acc=np.zeros(3), att=att0,
                                  omega_b=np.zeros(3), f_b=f_b0))
    for k in range(len(tt)):
        states.append(TruthState(t=hold_s + tt.t[k], pos=tt.pos[k], vel=tt.vel[k], acc=tt.acc[k],
                                  att=tt.att[k], omega_b=tt.omega_b[k], f_b=tt.f_b[k]))
    return states


def run_scenario(platform="ground", imu_grade="industrial_mems", quantum_grade=None,
                  duration_s=1800.0, dt=0.01, seed=0, hold_s=10.0, world="flat",
                  gnss_outage=None, attack=None, kappa_R=1.0, heading_noise_deg=2.0,
                  gnss_rate_hz=1.0, quantum_pointing="rigid", quantum_outlier_channel=True,
                  record_diagnostics=False, check_hygiene=True):
    """gnss_outage: (t_start, t_end) window where fixes are withheld from the
    filter entirely (not merely rejected by the gate).

    Returns a dict with per-tick error/covariance traces plus counters used
    to VERIFY the outage was real (``gnss_innovations_in_outage`` must be 0),
    and, if ``record_diagnostics``, per-GNSS-epoch NIS/yaw-rate/lateral-accel
    series for root-causing gate rejections.
    """
    rng_traj = stream(seed, "node", "traj")
    rng_imu = stream(seed, "node", "imu")
    rng_q = stream(seed, "node", "quantum")
    rng_gnss = stream(seed, "node", "gnss")
    rng_att = stream(seed, "node", "attack")
    rng_init = stream(seed, "node", "init")

    traj = make_trajectory(platform)
    states = make_truth_with_hold(traj, duration_s, dt, rng_traj, hold_s=hold_s, world=world)

    imu = ClassicalImu(grade=imu_grade, rng=rng_imu, world=world)
    quantum = QuantumAccelerometer(grade=quantum_grade, rng=rng_q, world=world,
                                    pointing=quantum_pointing,
                                    outlier_channel=quantum_outlier_channel) if quantum_grade else None
    gnss_signal = GnssSignalModel(rate_hz=gnss_rate_hz)
    receiver = GnssReceiver()

    eskf = ESKF(imu.config(), config=ESKFConfig(world=world, kappa_R=kappa_R))

    f_b_hold = []
    initialized = False
    heading_noise = np.radians(heading_noise_deg) * rng_init.normal()

    n_valid_q = 0
    n_invalid_q = 0
    gnss_innovations_in_outage = 0
    gnss_innovations_total = 0

    rows_t, rows_err, rows_cov, rows_gnss_used = [], [], [], []
    rows_acc_bias_est, rows_acc_bias_true = [], []
    diag_t, diag_nis, diag_yaw_rate, diag_lat_acc, diag_accepted = [], [], [], [], []

    for truth in states:
        t = truth.t
        s = imu.step(truth, rng_imu)
        q = quantum.step(truth, rng_q) if quantum is not None else None
        if q is not None:
            if q.valid:
                n_valid_q += 1
            else:
                n_invalid_q += 1
        epoch = gnss_signal.step(truth, rng_gnss)
        fix = None
        in_outage = gnss_outage is not None and gnss_outage[0] <= t < gnss_outage[1]
        if epoch is not None and not in_outage:
            if attack is not None:
                epoch = attack.apply(epoch, truth, rng_att)
            fix = receiver.solve(epoch.for_agent())
            if not fix.valid:
                fix = None

        if not initialized:
            if t < hold_s:
                f_b_hold.append(s.f_b if s is not None else None)
                continue
            fbs = [x for x in f_b_hold if x is not None]
            f_mean = np.mean(fbs, axis=0) if fbs else np.array([0.0, 0.0, G0])
            phi0, theta0 = level_att(f_mean)
            psi0 = truth.att[2] + heading_noise
            pos0 = fix.pos.copy() if fix is not None else truth.pos.copy()
            eskf.initialize_static(t, pos0, np.array([phi0, theta0, psi0]))
            initialized = True
            continue

        nav = eskf.step(t, s, q, fix, TRUST1)
        err = nav.pos - truth.pos
        rows_t.append(t)
        rows_err.append(err)
        rows_cov.append(np.diag(nav.cov_pos).copy())
        rows_gnss_used.append(fix is not None)
        rows_acc_bias_est.append(nav.acc_bias.copy())
        rows_acc_bias_true.append(_true_accel_bias(imu))
        if fix is not None:
            gnss_innovations_total += 1
            if in_outage:
                gnss_innovations_in_outage += 1
        if check_hygiene and len(rows_t) % 500 == 0:
            P = eskf.P
            if not np.all(np.isfinite(P)):
                raise AssertionError(f"P not finite at t={t}")
            if not np.allclose(P, P.T, atol=1e-6):
                raise AssertionError(f"P not symmetric at t={t}")
            if np.linalg.eigvalsh(P).min() < 0:
                raise AssertionError(f"P not PSD at t={t}")

    return {
        "t": np.array(rows_t), "err": np.array(rows_err), "cov_diag": np.array(rows_cov),
        "gnss_used": np.array(rows_gnss_used), "n_valid_q": n_valid_q, "n_invalid_q": n_invalid_q,
        "gnss_innovations_in_outage": gnss_innovations_in_outage,
        "gnss_innovations_total": gnss_innovations_total,
        "final_p": eskf.P.copy(), "imu": imu, "true_accel_bias_final": _true_accel_bias(imu),
        "acc_bias_est": np.array(rows_acc_bias_est), "acc_bias_true": np.array(rows_acc_bias_true),
    }


def _true_accel_bias(imu: ClassicalImu) -> np.ndarray:
    """Instantaneous TRUE total accelerometer bias (turn-on + GM instability
    + rate-random-walk) at the end of the run -- for the sanity-check
    diagnostic only (reads the sensor's own private state; not visible to
    the filter, which never sees this)."""
    ch = imu._accel_ch
    return (ch.turn_on_bias + ch.bias_gm + ch.bias_rrw).copy()


def anees_pos(res):
    err = res["err"]
    cov = res["cov_diag"]
    nees = np.sum(err ** 2 / np.clip(cov, 1e-9, None), axis=1)
    return float(np.mean(nees) / 3.0)


def rmse_h(res):
    err = res["err"][:, :2]
    return float(np.sqrt(np.mean(np.sum(err ** 2, axis=1))))


def index_at(t_array: np.ndarray, t_query: float) -> int:
    return int(np.argmin(np.abs(t_array - t_query)))
