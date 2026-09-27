"""Root-cause the NIS-gate lockout at low kappa_R during ground manoeuvres
(Master D-023 item 2). Not a test; run manually.

Logs, per GNSS epoch (kappa_R=1, ground, industrial_mems, seed=500):
NIS (nominal-R), yaw rate, lateral (horizontal, cross-track) specific force.
Plots NIS vs both, and reports correlation, to distinguish:
  (a) time-correlated GNSS errors (iono/tropo/multipath GM, tau up to 1800s)
      mis-treated as white per-epoch noise,
  (b) unmodelled IMU scale-factor / misalignment error, which is a FIXED
      per-run constant multiplied by the instantaneous specific force / rate
      -- so it is large exactly when |f_b| or |omega_b| is large, i.e.
      during manoeuvres,
  (c) GNSS velocity latency / time misalignment.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fedqpnt.core.seeding import stream
from fedqpnt.core.types import TrustState
from fedqpnt.sim.trajectory import make_trajectory
from fedqpnt.sim.rotations import euler_to_dcm
from fedqpnt.sensors.imu import ClassicalImu
from fedqpnt.gnss.signal import GnssSignalModel
from fedqpnt.gnss.receiver import GnssReceiver
from fedqpnt.fusion import ESKF, ESKFConfig

from tests._fusion_helpers import make_truth_with_hold, level_att, G0

OUT = os.path.join(os.path.dirname(__file__), "..", "results", "fusion")
os.makedirs(OUT, exist_ok=True)

TRUST1 = TrustState(t=0.0, weights={"gnss": 1.0, "imu": 1.0, "quantum": 1.0},
                     anomaly_scores={}, attack_detected=False)


def run(seed=500, kappa_R=1.0, duration_s=300.0):
    rng_traj = stream(seed, "node", "traj")
    rng_imu = stream(seed, "node", "imu")
    rng_gnss = stream(seed, "node", "gnss")

    traj = make_trajectory("ground")
    states = make_truth_with_hold(traj, duration_s, 0.01, rng_traj, hold_s=10.0)
    imu = ClassicalImu(grade="industrial_mems", rng=rng_imu)
    gnss_signal = GnssSignalModel(rate_hz=1.0)
    receiver = GnssReceiver()
    eskf = ESKF(imu.config(), config=ESKFConfig(kappa_R=kappa_R))

    f_b_hold = []
    initialized = False
    rows = []  # (t, nis, accepted, yaw_rate, lateral_f)

    for truth in states:
        t = truth.t
        s = imu.step(truth, rng_imu)
        epoch = gnss_signal.step(truth, rng_gnss)
        fix = receiver.solve(epoch.for_agent()) if epoch is not None else None
        if fix is not None and not fix.valid:
            fix = None

        if not initialized:
            if t < 10.0:
                f_b_hold.append(s.f_b if s is not None else None)
                continue
            fbs = [x for x in f_b_hold if x is not None]
            phi0, theta0 = level_att(np.mean(fbs, axis=0))
            psi0 = truth.att[2]
            pos0 = fix.pos.copy() if fix is not None else truth.pos.copy()
            eskf.initialize_static(t, pos0, np.array([phi0, theta0, psi0]))
            initialized = True
            continue

        eskf.propagate(t, s)
        innov = eskf.innovations(t, fix, None)
        nav = eskf.correct(t, innov, TRUST1)
        if fix is not None and innov:
            yaw_rate = float(truth.omega_b[2])
            # lateral (cross-track, horizontal) component of specific force
            f_b = truth.f_b
            lateral_f = float(np.hypot(f_b[0], f_b[1]))
            rows.append((t, innov[0].nis, innov[0].accepted, yaw_rate, lateral_f))

    return rows


def main():
    rows = run(seed=500, kappa_R=1.0, duration_s=300.0)
    t = np.array([r[0] for r in rows])
    nis = np.array([r[1] for r in rows])
    accepted = np.array([r[2] for r in rows])
    yaw_rate = np.array([r[3] for r in rows])
    lat_f = np.array([r[4] for r in rows])

    log_nis = np.log10(np.clip(nis, 1e-3, None))
    corr_yaw = float(np.corrcoef(log_nis, np.abs(yaw_rate))[0, 1])
    corr_latf = float(np.corrcoef(log_nis, lat_f)[0, 1])
    print(f"corr(log10 NIS, |yaw_rate|) [instantaneous, at epoch] = {corr_yaw:.3f}")
    print(f"corr(log10 NIS, lateral specific force) [instantaneous] = {corr_latf:.3f}")
    # cumulative/rolling: unmodelled scale-factor & misalignment are FIXED
    # per-run constants multiplied by rate/specific force, so their effect
    # ACCUMULATES over sustained manoeuvres rather than tracking the
    # instantaneous value -- test a rolling mean over the preceding W epochs.
    for W in (3, 5, 10):
        roll_yaw = np.array([np.mean(np.abs(yaw_rate[max(0, i - W):i + 1])) for i in range(len(yaw_rate))])
        roll_latf = np.array([np.mean(lat_f[max(0, i - W):i + 1]) for i in range(len(lat_f))])
        cy = float(np.corrcoef(log_nis, roll_yaw)[0, 1])
        cl = float(np.corrcoef(log_nis, roll_latf)[0, 1])
        print(f"  rolling W={W}: corr(log10 NIS, mean|yaw_rate|)={cy:.3f}  corr(log10 NIS, mean lat_f)={cl:.3f}")
    print(f"n epochs = {len(rows)}, n rejected = {int((~accepted).sum())}")
    first_reject = t[~accepted][0] if (~accepted).any() else None
    print(f"first rejection at t={first_reject}")
    if first_reject is not None:
        i = np.argmin(np.abs(t - first_reject))
        lo, hi = max(0, i - 5), min(len(t), i + 5)
        print("around first rejection: t, nis, yaw_rate, lat_f")
        for k in range(lo, hi):
            print(f"  t={t[k]:.1f} nis={nis[k]:.1f} accepted={accepted[k]} "
                  f"yaw_rate={yaw_rate[k]:.4f} lat_f={lat_f[k]:.4f}")

    fig, axes = plt.subplots(3, 1, figsize=(9, 7), sharex=True)
    axes[0].semilogy(t, nis, ".-", lw=0.7, ms=3)
    axes[0].axhline(27.86, color="r", ls="--", lw=0.8, label="chi2_6(0.9999)")
    axes[0].set_ylabel("NIS (nominal R)"); axes[0].legend()
    axes[1].plot(t, yaw_rate, ".-", lw=0.7, ms=3, color="g")
    axes[1].set_ylabel("yaw rate [rad/s]")
    axes[2].plot(t, lat_f, ".-", lw=0.7, ms=3, color="m")
    axes[2].set_ylabel("|f_b horiz| [m/s^2]"); axes[2].set_xlabel("t [s]")
    fig.suptitle(f"NIS vs manoeuvre (ground, industrial_mems, seed=500, kappa_R=1)\n"
                 f"corr(log NIS, |yaw_rate|)={corr_yaw:.2f}  corr(log NIS, lat_f)={corr_latf:.2f}")
    fig.tight_layout()
    fig.savefig(f"{OUT}/nis_diagnostic.png", dpi=110)
    print("plot written to", f"{OUT}/nis_diagnostic.png")


if __name__ == "__main__":
    main()
