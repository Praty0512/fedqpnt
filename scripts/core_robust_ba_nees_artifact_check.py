"""Master hypothesis follow-up (D-046/D-047 diagnostic): is the b_a NEES=522
(CAI ON, see overconf_diag.log) a metric artifact -- the CAI observes the
classical IMU's TOTAL accel error (incl. the per-run-constant scale-factor/
misalignment aliasing term M@(f_b*sf) - f_b, D-028), while the NEES "true
b_a" (tests._fusion_helpers._true_accel_bias = turn_on+GM+RRW only) excludes
it -- rather than a filter defect?

(a) b_a NEES per axis (vs the current truth definition).
(b) b_a NEES vs an "effective bias" truth = turn_on+GM+RRW + [M@(f_b*sf) - f_b]
    (the same per-run-constant M/sf the sensor actually applies, combined
    with the INSTANTANEOUS true specific force f_b -- this is exactly the
    deterministic, non-noise part of "meas - f_b" in _AxisChannel.step()).

Not a test; run manually. Same 5 tuning seeds (500-504), CAI ON only (cheap).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fedqpnt.core.types import TrustState, G0
from fedqpnt.sensors.imu import ClassicalImu
from fedqpnt.sensors.quantum import QuantumAccelerometer
from fedqpnt.gnss.signal import GnssSignalModel
from fedqpnt.gnss.receiver import GnssReceiver
from fedqpnt.fusion import ESKF, ESKFConfig
from tests._fusion_helpers import make_truth_with_hold, level_att, _true_accel_bias
from fedqpnt.core.seeding import stream

TRUST1 = TrustState(t=0.0, weights={"gnss": 1.0, "imu": 1.0, "quantum": 1.0},
                     anomaly_scores={}, attack_detected=False)
KAPPA_R = 40.0
SEEDS = list(range(500, 505))
DURATION_S = 600.0


def run_one(seed: int) -> dict:
    rng_traj = stream(seed, "node", "traj")
    rng_imu = stream(seed, "node", "imu")
    rng_q = stream(seed, "node", "quantum")
    rng_gnss = stream(seed, "node", "gnss")
    rng_init = stream(seed, "node", "init")

    from fedqpnt.sim.trajectory import make_trajectory
    traj = make_trajectory("ground")
    states = make_truth_with_hold(traj, DURATION_S, 0.01, rng_traj, hold_s=10.0, world="flat")

    imu = ClassicalImu(grade="industrial_mems", rng=rng_imu, world="flat")
    quantum = QuantumAccelerometer(grade="field", rng=rng_q, world="flat", pointing="rigid",
                                    outlier_channel=True)
    gnss_signal = GnssSignalModel(rate_hz=1.0)
    receiver = GnssReceiver()
    eskf = ESKF(imu.config(), config=ESKFConfig(world="flat", kappa_R=KAPPA_R))

    ch = imu._accel_ch
    sf = ch.scale_factor.copy()
    M = ch.misalignment.copy()

    f_b_hold = []
    initialized = False
    heading_noise = np.radians(2.0) * rng_init.normal()

    ba_err_sq = []       # squared error vs classical truth, per axis
    ba_var = []          # P_ba diag, per axis
    eff_err_sq = []       # squared error vs effective-bias truth, per axis

    for truth in states:
        t = truth.t
        s = imu.step(truth, rng_imu)
        q = quantum.step(truth, rng_q) if quantum is not None else None
        epoch = gnss_signal.step(truth, rng_gnss)
        fix = None
        if epoch is not None:
            fix = receiver.solve(epoch.for_agent())
            if not fix.valid:
                fix = None

        if not initialized:
            if t < 10.0:
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

        eskf.propagate(t, s)
        innov = eskf.innovations(t, fix, q)
        eskf.correct(t, innov, TRUST1)

        if t < 15.0:
            continue

        ba_classical = _true_accel_bias(imu)
        aliasing = M @ (truth.f_b * sf) - truth.f_b   # deterministic SF/mis distortion at this f_b
        ba_effective = ba_classical + aliasing

        e_classical = eskf.b_a - ba_classical
        e_effective = eskf.b_a - ba_effective
        p_ba_diag = np.diag(eskf.P[9:12, 9:12])

        ba_err_sq.append(e_classical ** 2)
        eff_err_sq.append(e_effective ** 2)
        ba_var.append(p_ba_diag)

    return dict(ba_err_sq=np.array(ba_err_sq), eff_err_sq=np.array(eff_err_sq), ba_var=np.array(ba_var))


def main() -> None:
    print(f"=== D-046/D-047 b_a NEES artifact check, CAI ON, tuning seeds {SEEDS}, {DURATION_S:.0f}s ===\n")
    all_classical, all_eff, all_var = [], [], []
    for seed in SEEDS:
        r = run_one(seed)
        all_classical.append(r["ba_err_sq"])
        all_eff.append(r["eff_err_sq"])
        all_var.append(r["ba_var"])
    classical = np.concatenate(all_classical, axis=0)
    eff = np.concatenate(all_eff, axis=0)
    var = np.concatenate(all_var, axis=0)

    nees_classical_axis = np.mean(classical / var, axis=0)
    nees_eff_axis = np.mean(eff / var, axis=0)
    print("Per-axis b_a NEES (1 dof each, ideal 1.0):")
    print(f"  vs classical truth (turn_on+GM+RRW):        x={nees_classical_axis[0]:.2f}  "
          f"y={nees_classical_axis[1]:.2f}  z={nees_classical_axis[2]:.2f}  "
          f"(3dof sum ideal 3 -> {np.sum(nees_classical_axis):.2f})")
    print(f"  vs effective-bias truth (+SF/mis aliasing): x={nees_eff_axis[0]:.2f}  "
          f"y={nees_eff_axis[1]:.2f}  z={nees_eff_axis[2]:.2f}  "
          f"(3dof sum ideal 3 -> {np.sum(nees_eff_axis):.2f})")


if __name__ == "__main__":
    main()
