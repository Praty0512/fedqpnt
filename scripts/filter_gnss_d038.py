"""FILTER-GNSS agent: D-038 item 3 (GNSS velocity-cov honesty + kappa_R split),
item 1 (pure-INS MEMS v/p linearisation-limit check), item 2 (D-036 single-
source delta_b_a check with all other P0 blocks zeroed).

Diagnosis only -- NO fix applied to fedqpnt/fusion/eskf.py or fedqpnt/gnss/*.
Seeds 500-599 only. Reuses helpers from scripts/cai_h3_investigation.py and
tests/_fusion_helpers.py.
"""
from __future__ import annotations

import dataclasses
import json
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from scipy.stats import chi2

from fedqpnt.core.types import G0
from fedqpnt.core.seeding import stream
from fedqpnt.sim.trajectory import make_trajectory
from fedqpnt.sim.rotations import so3_log, euler_to_dcm
from fedqpnt.sensors.imu import ClassicalImu, AxisErrorParams
from fedqpnt.gnss.signal import GnssSignalModel
from fedqpnt.gnss.receiver import GnssReceiver
from fedqpnt.fusion import ESKF, ESKFConfig
from tests._fusion_helpers import make_truth_with_hold, level_att, index_at

# Master directive (post-review): 5 seeds is enough; write each task's
# result to its own JSON as soon as it finishes; print with flush=True
# (run with `python -u`) so output is never lost to buffering.
SEEDS10 = list(range(500, 505))
SEEDS20 = list(range(500, 505))
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results", "fusion")


def _save(name, obj):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"d038_{name}.json")

    def _conv(x):
        if isinstance(x, np.ndarray):
            return x.tolist()
        if isinstance(x, (np.floating,)):
            return float(x)
        if isinstance(x, (np.integer,)):
            return int(x)
        return x

    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=_conv)
    print(f"   [saved {path}]", flush=True)


import builtins
import functools
print = functools.partial(builtins.print, flush=True)  # belt-and-suspenders vs stdout buffering


# ===========================================================================
# TASK 1 (PRIME): receiver cov_vel honesty
# ===========================================================================
def cov_vel_honesty(course="static", duration_s=600.0, dt=0.01):
    """Bypass the ESKF entirely: run truth + GnssSignalModel + GnssReceiver
    only, collect (fix.vel - truth.vel) and reported cov_vel at every fix."""
    all_err = []
    all_sigma = []
    per_seed_lag1 = []
    for seed in SEEDS10:
        rng_traj = stream(seed, "node", "traj")
        rng_gnss = stream(seed, "node", "gnss")
        traj = make_trajectory("ground" if course == "dynamic" else "ground")
        states = make_truth_with_hold(traj, duration_s, dt, rng_traj, hold_s=10.0,
                                       world="flat")
        if course == "static":
            # zero out velocity/accel post-hold to keep the platform static
            # for the whole run (truth-side only; the receiver/signal model
            # are untouched) -- isolates receiver noise from trajectory dynamics.
            states = [dataclasses.replace(s, vel=np.zeros(3), acc=np.zeros(3))
                      if s.t >= 10.0 else s for s in states]
        gnss_signal = GnssSignalModel(rate_hz=1.0)
        receiver = GnssReceiver()
        seed_err, seed_sigma = [], []
        for truth in states:
            epoch = gnss_signal.step(truth, rng_gnss)
            if epoch is None:
                continue
            fix = receiver.solve(epoch.for_agent())
            if not fix.valid or not np.all(np.isfinite(fix.vel)):
                continue
            seed_err.append(fix.vel - truth.vel)
            seed_sigma.append(np.sqrt(np.diag(fix.cov_vel)))
        seed_err = np.array(seed_err)
        seed_sigma = np.array(seed_sigma)
        all_err.append(seed_err)
        all_sigma.append(seed_sigma)
        # lag-1s autocorrelation of the velocity-error x-axis (1 Hz fixes -> lag=1 sample)
        e = seed_err[:, 0]
        if len(e) > 2:
            e0 = e - e.mean()
            r = np.corrcoef(e0[:-1], e0[1:])[0, 1]
            per_seed_lag1.append(r)

    err_cat = np.concatenate(all_err, axis=0)
    sigma_cat = np.concatenate(all_sigma, axis=0)
    actual_std = err_cat.std(axis=0)
    reported_mean = sigma_cat.mean(axis=0)
    ratio = reported_mean / actual_std
    nees3 = np.sum(err_cat ** 2 / sigma_cat ** 2, axis=1)  # per-axis normalized, summed = chi2_3-ish
    # more correct: use full cov_vel per-sample would need per-sample matrix;
    # per-axis normalized sum is the standard cheap diagonal NEES.
    print(f"\n=== cov_vel honesty ({course}, T={duration_s:.0f}s, {len(SEEDS10)} seeds) ===")
    print(f"  n_fixes total = {len(err_cat)}")
    print(f"  actual vel-error std (E,N,U) = {actual_std}")
    print(f"  reported mean sqrt(diag cov_vel) (E,N,U) = {reported_mean}")
    print(f"  ratio reported/actual (E,N,U) = {ratio}")
    print(f"  normalized-vel-err^2 (diag, 3dof, ideal~3): mean={nees3.mean():.3f} "
          f"(chi2_3 mean=3.0), median={np.median(nees3):.3f} (chi2_3 median={chi2.ppf(0.5, 3):.3f})")
    print(f"  lag-1s autocorrelation of vel-error (x-axis), per-seed: "
          f"mean={np.mean(per_seed_lag1):.3f}  values={[f'{v:.2f}' for v in per_seed_lag1]}")
    result = dict(course=course, duration_s=duration_s, n_seeds=len(SEEDS10), n_fixes=len(err_cat),
                  actual_std=actual_std, reported_mean=reported_mean, ratio=ratio,
                  nees3_mean=float(nees3.mean()), lag1_mean=float(np.mean(per_seed_lag1)))
    _save(f"1a_cov_vel_honesty_{course}", result)
    return result


# ===========================================================================
# TASK 1 continued: GNSS-aided ESKF block NEES under kappa_R variants,
# including a split kappa_pos / kappa_vel (test-local ESKF subclass --
# fedqpnt/fusion/eskf.py itself is NOT modified).
# ===========================================================================
class _SplitKappaESKF(ESKF):
    """Test-local subclass: applies self.kappa_pos to R_pos and self.kappa_vel
    to R_vel independently (identical to ESKF.innovations otherwise).
    Duplicates the GNSS branch of ESKF.innovations() verbatim except for
    the R_pos/R_vel scaling line -- required because ESKFConfig only exposes
    one kappa_R applied to both blocks (fedqpnt/fusion/eskf.py L317-318)."""
    kappa_pos: float = 1.0
    kappa_vel: float = 1.0

    def innovations(self, t, fix, quantum):
        from fedqpnt.core.types import Innovation
        self._pending = {}
        out = []
        if not self.initialized:
            return out
        if fix is not None and fix.valid and np.all(np.isfinite(fix.pos)) and np.all(np.isfinite(fix.vel)):
            from fedqpnt.fusion.eskf import _spd_or_fallback
            H = np.zeros((6, self.N))
            H[0:3, 0:3] = np.eye(3)
            H[3:6, 3:6] = np.eye(3)
            R_pos = self.kappa_pos * _spd_or_fallback(fix.cov_pos, self.cfg.fallback_cov_pos)
            R_vel = self.kappa_vel * _spd_or_fallback(fix.cov_vel, self.cfg.fallback_cov_vel)
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
        # quantum branch unused in this nominal (no-CAI) check; omitted.
        return out


def _run_nominal(seed, kappa_pos, kappa_vel, duration_s, imu_grade="industrial_mems"):
    from fedqpnt.core.types import TrustState
    TRUST1 = TrustState(t=0.0, weights={"gnss": 1.0, "imu": 1.0, "quantum": 1.0},
                         anomaly_scores={}, attack_detected=False)
    rng_traj = stream(seed, "node", "traj")
    rng_imu = stream(seed, "node", "imu")
    rng_gnss = stream(seed, "node", "gnss")
    rng_init = stream(seed, "node", "init")
    traj = make_trajectory("ground")
    states = make_truth_with_hold(traj, duration_s, dt=0.01, rng=rng_traj, hold_s=10.0, world="flat")
    imu = ClassicalImu(grade=imu_grade, rng=rng_imu, world="flat")
    gnss_signal = GnssSignalModel(rate_hz=1.0)
    receiver = GnssReceiver()
    eskf = _SplitKappaESKF(imu.config(), config=ESKFConfig(world="flat"))
    eskf.kappa_pos = kappa_pos
    eskf.kappa_vel = kappa_vel

    f_b_hold = []
    initialized = False
    heading_noise = np.radians(2.0) * rng_init.normal()
    rows_t, rows_p_err, rows_v_err, rows_psi_err, rows_ba_err, rows_bg_err = [], [], [], [], [], []
    rows_Pp, rows_Pv, rows_Ppsi, rows_Pba, rows_Pbg = [], [], [], [], []

    for truth in states:
        t = truth.t
        s = imu.step(truth, rng_imu)
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
        nav = eskf.step(t, s, None, fix, TRUST1)
        ba_true = (imu._accel_ch.turn_on_bias + imu._accel_ch.bias_gm + imu._accel_ch.bias_rrw)
        bg_true = (imu._gyro_ch.turn_on_bias + imu._gyro_ch.bias_gm + imu._gyro_ch.bias_rrw)
        C_true = euler_to_dcm(truth.att)
        rows_t.append(t)
        rows_p_err.append(nav.pos - truth.pos)
        rows_v_err.append(nav.vel - truth.vel)
        rows_psi_err.append(so3_log(eskf.C @ C_true.T))
        rows_ba_err.append(eskf.b_a - ba_true)
        rows_bg_err.append(eskf.b_g - bg_true)
        rows_Pp.append(np.diag(eskf.P[0:3, 0:3]).copy())
        rows_Pv.append(np.diag(eskf.P[3:6, 3:6]).copy())
        rows_Ppsi.append(eskf.P[6:9, 6:9].copy())
        rows_Pba.append(eskf.P[9:12, 9:12].copy())
        rows_Pbg.append(eskf.P[12:15, 12:15].copy())

    return dict(t=np.array(rows_t), p_err=np.array(rows_p_err), v_err=np.array(rows_v_err),
                psi_err=np.array(rows_psi_err), ba_err=np.array(rows_ba_err), bg_err=np.array(rows_bg_err),
                Pp=np.array(rows_Pp), Pv=np.array(rows_Pv), Ppsi=np.array(rows_Ppsi),
                Pba=np.array(rows_Pba), Pbg=np.array(rows_Pbg))


def _nees_diag(e, Pdiag):
    return float(np.sum(e ** 2 / np.clip(Pdiag, 1e-12, None)))


def _nees_full(e, P):
    try:
        return float(e @ np.linalg.solve(P, e))
    except np.linalg.LinAlgError:
        return float("nan")


def gnss_aided_kappa_sweep(vel_ratio, duration_s=310.0):
    """Block NEES (p,v,psi_rp,yaw,ba,bg) at 60s/300s for kappa_R in {1,40}
    applied to BOTH pos+vel, vs kappa_pos=1/kappa_vel=vel_ratio**2 (honest R_vel)."""
    print(f"\n=== GNSS-aided ANEES sweep, industrial_mems, seeds 500-{500+len(SEEDS10)-1} "
          f"(measured cov_vel ratio={vel_ratio:.3f}) ===")
    arms = [
        ("kappa_R=1 (pos+vel)", 1.0, 1.0),
        ("kappa_R=40 (pos+vel)", 40.0, 40.0),
        (f"kappa_pos=1, kappa_vel={vel_ratio**2:.3f} (honest R_vel only)", 1.0, vel_ratio ** 2),
    ]
    checkpoints = (60.0, 300.0)
    all_results = {}
    for label, kp, kv in arms:
        acc = {cp: dict(p=[], v=[], psi_rp=[], psi_yaw=[], ba=[], bg=[]) for cp in checkpoints}
        for seed in SEEDS10:
            res = _run_nominal(seed, kp, kv, duration_s)
            for cp in checkpoints:
                i = index_at(res["t"], cp)
                acc[cp]["p"].append(_nees_diag(res["p_err"][i], res["Pp"][i]) / 3.0)
                acc[cp]["v"].append(_nees_diag(res["v_err"][i], res["Pv"][i]) / 3.0)
                acc[cp]["psi_rp"].append(_nees_full(res["psi_err"][i][:2], res["Ppsi"][i][:2, :2]) / 2.0)
                acc[cp]["psi_yaw"].append((res["psi_err"][i][2] ** 2 / res["Ppsi"][i][2, 2]))
                acc[cp]["ba"].append(_nees_diag(res["ba_err"][i], res["Pba"][i]) / 3.0)
                acc[cp]["bg"].append(_nees_diag(res["bg_err"][i], res["Pbg"][i]) / 3.0)
        print(f"-- {label} --")
        arm_summary = {}
        for cp in checkpoints:
            a = acc[cp]
            print(f"   t={cp:.0f}s: ANEES p={np.mean(a['p']):.2f} v={np.mean(a['v']):.2f} "
                  f"psi_rp={np.mean(a['psi_rp']):.2f} psi_yaw={np.mean(a['psi_yaw']):.2f} "
                  f"ba={np.mean(a['ba']):.2f} bg={np.mean(a['bg']):.2f}  (ideal=1.0 each)")
            arm_summary[cp] = {k: float(np.mean(v)) for k, v in a.items()}
        all_results[label] = arm_summary
    _save("1b_gnss_aided_kappa_sweep", dict(vel_ratio=vel_ratio, n_seeds=len(SEEDS10), arms=all_results))
    return all_results


# ===========================================================================
# TASK 2 (D-038 item 1): pure-INS MEMS v/p NEES @300s linearisation-limit check
# ===========================================================================
def pure_ins_tilt_and_gyro_scaledown():
    from tests._fusion_helpers import run_scenario  # not used; local pure-INS loop below
    print("\n=== D-038 item 1: true tilt magnitude + gyro turn-on sigma /10 ablation "
          f"(industrial_mems static, seeds 500-{500+len(SEEDS20)-1}) ===")

    def pure_ins_run(gyro_override=None, seed=500, duration_s=300.0, dt=0.01):
        rng_imu = stream(seed, "node", "imu")
        rng_init = stream(seed, "node", "init")
        imu = ClassicalImu(grade="industrial_mems", rng=rng_imu, world="flat")
        if gyro_override is not None:
            from fedqpnt.sensors.imu import _AxisChannel
            imu._cfg.gyro = gyro_override
            imu._gyro_ch = _AxisChannel(gyro_override, imu._dt, rng_imu)
        eskf = ESKF(imu.config(), config=ESKFConfig(world="flat"))
        att0 = np.zeros(3)
        dx0 = np.zeros(15)  # prior drawn AT the true bias (matches D-034's fixed-init convention)
        ba_true0 = (imu._accel_ch.turn_on_bias + imu._accel_ch.bias_gm + imu._accel_ch.bias_rrw).copy()
        bg_true0 = (imu._gyro_ch.turn_on_bias + imu._gyro_ch.bias_gm + imu._gyro_ch.bias_rrw).copy()
        eskf.initialize_static(0.0, np.zeros(3), att0)
        eskf.b_a = ba_true0.copy()
        eskf.b_g = bg_true0.copy()
        from fedqpnt.core.types import TruthState
        t = 0.0
        rows_t, rows_psi, rows_v, rows_p, rows_Pv, rows_Pp = [], [], [], [], [], []
        while t < duration_s:
            t += dt
            truth = TruthState(t=t, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                                att=np.zeros(3), omega_b=np.zeros(3), f_b=np.array([0., 0., G0]))
            s = imu.step(truth, rng_imu)
            eskf.propagate(t, s)
            C_true = np.eye(3)
            psi_err = so3_log(eskf.C @ C_true.T)
            rows_t.append(t)
            rows_psi.append(psi_err.copy())
            rows_v.append(eskf.v.copy())
            rows_p.append(eskf.p.copy())
            rows_Pv.append(np.diag(eskf.P[3:6, 3:6]).copy())
            rows_Pp.append(np.diag(eskf.P[0:3, 0:3]).copy())
        return dict(t=np.array(rows_t), psi=np.array(rows_psi), v=np.array(rows_v), p=np.array(rows_p),
                    Pv=np.array(rows_Pv), Pp=np.array(rows_Pp))

    ind_imu = ClassicalImu(grade="industrial_mems", rng=np.random.default_rng(0))
    gyro0 = ind_imu._cfg.gyro
    gyro_scaled = dataclasses.replace(gyro0, turn_on_bias_std=gyro0.turn_on_bias_std / 10.0)

    out = {}
    for label, gyro_ov in [("native gyro turn-on", None), ("gyro turn-on sigma /10", gyro_scaled)]:
        tilt60, tilt300 = [], []
        vnees300, pnees300 = [], []
        for seed in SEEDS20:
            res = pure_ins_run(gyro_override=gyro_ov, seed=seed)
            i60 = index_at(res["t"], 60.0)
            i300 = index_at(res["t"], 300.0)
            tilt60.append(np.linalg.norm(res["psi"][i60]))
            tilt300.append(np.linalg.norm(res["psi"][i300]))
            vnees300.append(_nees_diag(res["v"][i300], res["Pv"][i300]) / 3.0)
            pnees300.append(_nees_diag(res["p"][i300], res["Pp"][i300]) / 3.0)
        print(f"-- {label} --")
        print(f"   |tilt| @60s: mean={np.mean(tilt60):.4f} rad   @300s: mean={np.mean(tilt300):.4f} rad")
        print(f"   v ANEES @300s: mean={np.mean(vnees300):.2f}   p ANEES @300s: mean={np.mean(pnees300):.2f} "
              f"(ideal=1.0 each)")
        out[label] = dict(tilt60_mean=float(np.mean(tilt60)), tilt300_mean=float(np.mean(tilt300)),
                           v_anees300=float(np.mean(vnees300)), p_anees300=float(np.mean(pnees300)))
    _save("2_pure_ins_tilt_gyro_scaledown", out)
    return out


# ===========================================================================
# TASK 3 (D-038 item 2): D-036 single-source delta_b_a check, ALL other
# P0 blocks = 0 (previously only the truth-side sources were zeroed; P0 was
# left at its normal Sec 2.9 values for the OTHER blocks).
# ===========================================================================
def single_source_zero_p0():
    print("\n=== D-038 item 2: D-036 delta_b_a check, ALL OTHER P0 blocks = 0 ===")
    dt = 0.01
    T = 300.0
    b0 = 0.01  # m/s^2, matches D-036's arm (i)
    imu_cfg = ClassicalImu(grade="industrial_mems", rng=np.random.default_rng(0)).config()
    eskf = ESKF(imu_cfg, config=ESKFConfig(world="flat"))
    eskf.initialize_static(0.0, np.zeros(3), np.zeros(3))
    eskf.P = np.zeros((15, 15))
    eskf.P[9, 9] = b0 ** 2  # ONLY delta_b_a[x] nonzero; every other P0 entry = 0 (incl. off-diag)
    # zero-noise IMU: vrw=arw=q_ba=q_bg=0 already true for this construction
    # only if the config's noise params happen to be nonzero -- force Qc=0
    # by zeroing the read noise params directly (test-local, eskf instance only).
    eskf.vrw = 0.0
    eskf.arw = 0.0
    eskf.q_ba = 0.0
    eskf.q_bg = 0.0

    from fedqpnt.core.types import ImuSample
    t = 0.0
    n = int(round(T / dt))
    checkpoints = {10.0: None, 60.0: None, 300.0: None}
    for k in range(n):
        t += dt
        f_tilde = np.array([b0, 0.0, G0])  # true accel = [0,0,g]; filter sees true+bias
        imu = ImuSample(t=t, f_b=f_tilde, omega_b=np.zeros(3))
        eskf.propagate(t, imu)
        for cp in list(checkpoints):
            if checkpoints[cp] is None and t >= cp - 1e-9:
                v_err_analytic = -b0 * cp   # dv = -C @ dba integrated, C=I here
                p_err_analytic = -0.5 * b0 * cp ** 2
                Pv = eskf.P[3, 3]
                Pp = eskf.P[0, 0]
                checkpoints[cp] = (np.sqrt(Pv), abs(v_err_analytic), np.sqrt(Pp), abs(p_err_analytic))
    out = {}
    for cp, (sqrtPv, v_analytic, sqrtPp, p_analytic) in checkpoints.items():
        print(f"   t={cp:.0f}s: sqrt(Pv)={sqrtPv:.6f} vs b0*t={v_analytic:.6f} "
              f"(ratio={sqrtPv / v_analytic:.4f})   sqrt(Pp)={sqrtPp:.6f} vs 0.5*b0*t^2={p_analytic:.6f} "
              f"(ratio={sqrtPp / p_analytic:.4f})")
        out[cp] = dict(sqrtPv=float(sqrtPv), v_analytic=float(v_analytic), sqrtPp=float(sqrtPp),
                        p_analytic=float(p_analytic))
    _save("3_single_source_zero_p0", out)
    return out


if __name__ == "__main__":
    # Master directive: order by cost, save each task's result immediately,
    # report 1a and 3 as soon as they land (don't wait for the slow 1b sweep).
    print("=== TASK 1a: cov_vel honesty (receiver only, cheapest) ===")
    r_static = cov_vel_honesty(course="static", duration_s=600.0)
    r_dynamic = cov_vel_honesty(course="dynamic", duration_s=600.0)
    vel_ratio = float(np.mean(r_static["ratio"]))  # reported/actual, averaged over axes; static arm (thermal-dominated, matches item's "clean" framing)

    print("\n=== TASK 3: D-036 single-source check, P0=0 elsewhere (one seed, noise-free, seconds) ===")
    single_source_zero_p0()

    print("\n=== TASK 2: pure-INS tilt + gyro-scaledown ===")
    pure_ins_tilt_and_gyro_scaledown()

    print("\n=== TASK 1b: GNSS-aided kappa sweep (slowest, last) ===")
    gnss_aided_kappa_sweep(vel_ratio=vel_ratio, duration_s=310.0)

    print("\n=== ALL TASKS DONE ===")
