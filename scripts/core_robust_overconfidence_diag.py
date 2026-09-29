"""CORE-ROBUST session, item 4 (D-046/D-047): diagnose the psi/b
overconfidence at kappa_R=40.

4(a) time-alignment check: static code trace (see report / notes), not a
     runtime measurement -- fedqpnt/node/environment.py's tick(k) builds
     imu/quantum/gnss_epoch from the SAME truth sample (same t), and
     fedqpnt/gnss/receiver.py's solve() sets fix.t = epoch.t = t. Agent.step
     calls eskf.propagate(t, imu) then eskf.innovations(t, fix, ...) with
     that SAME t, so the fix is always applied at its own timestamp with no
     propagate/correct-ordering lag. Zero offset by construction.

4(b) per-block NEES (p, v, psi_rp, psi_yaw, b_a, b_g), CAI ON vs OFF,
     industrial_mems, 5 seeds (tuning seeds 500-504), 10 min, GNSS-aided,
     kappa_R=40 (D-047 provisional value, pending item 5's re-tune).

4(c) CAI update R (sigma_win_g) vs realised CAI residual variance.

Not a test; run manually: python scripts/core_robust_overconfidence_diag.py
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
from fedqpnt.sim.rotations import so3_log, euler_to_dcm
from tests._fusion_helpers import make_truth_with_hold, level_att, _true_accel_bias

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cai_h3_investigation import _true_gyro_bias  # noqa: E402

TRUST1 = TrustState(t=0.0, weights={"gnss": 1.0, "imu": 1.0, "quantum": 1.0},
                     anomaly_scores={}, attack_detected=False)
KAPPA_R = 40.0
SEEDS = list(range(500, 505))
DURATION_S = 600.0


def _nees(e: np.ndarray, P: np.ndarray) -> float:
    return float(e @ np.linalg.solve(P, e))


def run_one(seed: int, use_cai: bool) -> dict:
    from fedqpnt.core.seeding import stream
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
                                    outlier_channel=True) if use_cai else None
    gnss_signal = GnssSignalModel(rate_hz=1.0)
    receiver = GnssReceiver()
    eskf = ESKF(imu.config(), config=ESKFConfig(world="flat", kappa_R=KAPPA_R))

    f_b_hold = []
    initialized = False
    heading_noise = np.radians(2.0) * rng_init.normal()

    rows = {k: [] for k in ("p", "v", "psi", "ba", "bg", "cai_res", "cai_var")}

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
        for iv in innov:
            if iv.sensor == "quantum":
                rows["cai_res"].append(iv.nu.copy())
                rows["cai_var"].append(np.diag(iv.S).copy())
        nav = eskf.correct(t, innov, TRUST1)

        if t < 15.0:
            continue  # skip the very first couple of epochs (init transient)

        p_err = nav.pos - truth.pos
        v_err = nav.vel - truth.vel
        C_true = euler_to_dcm(truth.att)
        psi_err = so3_log(eskf.C @ C_true.T)
        ba_err = eskf.b_a - _true_accel_bias(imu)
        bg_err = eskf.b_g - _true_gyro_bias(imu)

        rows["p"].append(_nees(p_err, eskf.P[0:3, 0:3]))
        rows["v"].append(_nees(v_err, eskf.P[3:6, 3:6]))
        rows["psi"].append((_nees(psi_err[:2], eskf.P[6:8, 6:8]), _nees(psi_err[2:3], eskf.P[8:9, 8:9])))
        rows["ba"].append(_nees(ba_err, eskf.P[9:12, 9:12]))
        rows["bg"].append(_nees(bg_err, eskf.P[12:15, 12:15]))

    return rows


def main() -> None:
    print(f"=== D-046/D-047 overconfidence diagnostic, tuning seeds {SEEDS}, "
          f"{DURATION_S:.0f}s, kappa_R={KAPPA_R} ===\n")
    for use_cai in (True, False):
        label = "CAI ON" if use_cai else "CAI OFF"
        p_all, v_all, rp_all, yaw_all, ba_all, bg_all = [], [], [], [], [], []
        cai_res_all, cai_var_all = [], []
        for seed in SEEDS:
            rows = run_one(seed, use_cai)
            p_all += rows["p"]
            v_all += rows["v"]
            rp_all += [x[0] for x in rows["psi"]]
            yaw_all += [x[1] for x in rows["psi"]]
            ba_all += rows["ba"]
            bg_all += rows["bg"]
            cai_res_all += rows["cai_res"]
            cai_var_all += rows["cai_var"]
        print(f"[{label}] n_epochs={len(p_all)}")
        print(f"  p   NEES(3dof,ideal 3)  mean={np.mean(p_all):.2f}")
        print(f"  v   NEES(3dof,ideal 3)  mean={np.mean(v_all):.2f}")
        print(f"  psi_rp  NEES(2dof,ideal 2)  mean={np.mean(rp_all):.2f}")
        print(f"  psi_yaw NEES(1dof,ideal 1)  mean={np.mean(yaw_all):.2f}")
        print(f"  b_a NEES(3dof,ideal 3)  mean={np.mean(ba_all):.2f}")
        print(f"  b_g NEES(3dof,ideal 3)  mean={np.mean(bg_all):.2f}")
        if use_cai and cai_res_all:
            res = np.array(cai_res_all)
            var_assumed = np.array(cai_var_all)
            realised_var = np.var(res, axis=0)
            print(f"  CAI residual: n={len(res)}  realised_var={realised_var}  "
                  f"assumed R diag mean={np.mean(var_assumed, axis=0)}  "
                  f"ratio(realised/assumed)={realised_var / np.mean(var_assumed, axis=0)}")
        print()


if __name__ == "__main__":
    main()
