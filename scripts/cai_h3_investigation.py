"""CAI-H3 investigation (agent CAI-H3): is CAI-worse-than-no-CAI at 60s
outage (industrial_mems, mean 214m vs 103m, D-023 flagged concern) a BUG
in fedqpnt/fusion/eskf.py or real estimation physics (Master's leading
hypothesis: GNSS-only aiding observes only the combination (b_a - g x
delta_theta), CAI pins b_a alone and unmasks the MEMS-gyro tilt error)?

Not a test; run manually. Seeds 500-509 only (500-599 range).
"""
from __future__ import annotations

import dataclasses
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from fedqpnt.core.types import ImuSample, QuantumSample, TrustState, TruthState, G0
from fedqpnt.core.seeding import stream
from fedqpnt.sim.rotations import so3_log, so3_exp, euler_to_dcm
from fedqpnt.sensors.imu import ClassicalImu, _AxisChannel, AxisErrorParams
from fedqpnt.sensors.quantum import QuantumAccelerometer
from fedqpnt.gnss.signal import GnssSignalModel, _gauss_markov_step
import fedqpnt.gnss.signal as _gnss_signal_mod
from fedqpnt.gnss.receiver import GnssReceiver
from fedqpnt.fusion import ESKF, ESKFConfig
from tests._fusion_helpers import make_truth_with_hold, level_att, _true_accel_bias, index_at, \
    run_scenario, anees_pos

TRUST1 = TrustState(t=0.0, weights={"gnss": 1.0, "imu": 1.0, "quantum": 1.0},
                     anomaly_scores={}, attack_detected=False)
T0 = 60.0
N_SEEDS = 10
SEEDS = list(range(500, 500 + N_SEEDS))
KAPPA_R = 40.0


# ===========================================================================
# 1(b) Bug check: noiseless IMU + noiseless CAI + injected constant accel
# bias must converge b_hat_a to truth and must NOT disturb attitude.
# ===========================================================================
def bug_check_noiseless_convergence():
    dt = 0.01
    imu_cfg = ClassicalImu(grade="industrial_mems", rng=np.random.default_rng(0)).config()
    eskf = ESKF(imu_cfg, config=ESKFConfig(world="flat"))
    eskf.initialize_static(0.0, np.zeros(3), np.array([0.0, 0.0, 0.0]))
    true_bias = np.array([0.05, -0.03, 0.02])
    f_true_b = np.array([0.0, 0.0, G0])  # stationary, level
    q_cfg = dict(t_interrogation=np.nan, response="boxcar", cycle_time=1.0)
    psi0 = float(np.linalg.norm(so3_log(eskf.C)))

    t = 0.0
    for k in range(400):
        t += dt
        f_tilde = f_true_b + true_bias  # noiseless IMU, constant true bias
        imu = ImuSample(t=t, f_b=f_tilde, omega_b=np.zeros(3))
        eskf.propagate(t, imu)
        quantum = None
        if k % 100 == 99:  # one CAI cycle per second, noiseless
            quantum = QuantumSample(t=t, f_b=f_true_b.copy(), variance=np.full(3, 1e-12),
                                     valid=True, cycle_time=1.0, t_interrogation=np.nan, response="boxcar")
        innov = eskf.innovations(t, None, quantum)
        eskf.correct(t, innov, TRUST1)

    b_err = eskf.b_a - true_bias
    psi_final = float(np.linalg.norm(so3_log(eskf.C)))  # true C is I, so this IS the attitude error
    print(f"bug_check(b): b_hat_a={eskf.b_a}, true={true_bias}, |error|={np.linalg.norm(b_err):.3e} m/s^2")
    print(f"  attitude error (should stay ~0, no disturbance from CAI): start={psi0:.3e} rad, "
          f"end={psi_final:.3e} rad")
    ok = np.linalg.norm(b_err) < 1e-3 and psi_final < 1e-6
    print(f"  PASS={ok}")
    return ok


# ===========================================================================
# Extended scenario runner: logs attitude-error vector (nav-frame vex(psi)),
# true/estimated accel bias, and the P[b_a,psi] cross-covariance block, at
# every tick (local copy of tests._fusion_helpers.run_scenario + logging;
# does not modify the shared test helper).
# ===========================================================================
def run_scenario_diag(imu_grade="industrial_mems", quantum_grade=None, duration_s=120.0,
                       dt=0.01, seed=0, hold_s=10.0, world="flat", gnss_outage=None,
                       kappa_R=40.0, heading_noise_deg=2.0, gnss_rate_hz=1.0,
                       quantum_outlier_channel=True, gyro_override=None, accel_override=None):
    rng_traj = stream(seed, "node", "traj")
    rng_imu = stream(seed, "node", "imu")
    rng_q = stream(seed, "node", "quantum")
    rng_gnss = stream(seed, "node", "gnss")
    rng_att = stream(seed, "node", "attack")
    rng_init = stream(seed, "node", "init")

    from fedqpnt.sim.trajectory import make_trajectory
    traj = make_trajectory("ground")
    states = make_truth_with_hold(traj, duration_s, dt, rng_traj, hold_s=hold_s, world=world)

    imu = ClassicalImu(grade=imu_grade, rng=rng_imu, world=world)
    if gyro_override is not None:
        # Sec 2.4 lets the filter read whatever config() reports; we swap
        # only the SIMULATED gyro channel (truth-side sensor), the filter
        # is handed imu.config() as usual (post-swap) so it stays consistent.
        imu._cfg.gyro = gyro_override
        imu._gyro_ch = _AxisChannel(gyro_override, imu._dt, rng_imu)
    if accel_override is not None:
        imu._cfg.accel = accel_override
        imu._accel_ch = _AxisChannel(accel_override, imu._dt, rng_imu)
    quantum = QuantumAccelerometer(grade=quantum_grade, rng=rng_q, world=world,
                                    pointing="rigid",
                                    outlier_channel=quantum_outlier_channel) if quantum_grade else None
    gnss_signal = GnssSignalModel(rate_hz=gnss_rate_hz)
    receiver = GnssReceiver()
    eskf = ESKF(imu.config(), config=ESKFConfig(world=world, kappa_R=kappa_R))

    f_b_hold = []
    initialized = False
    heading_noise = np.radians(heading_noise_deg) * rng_init.normal()

    rows_t, rows_err, rows_ba_err, rows_psi_err, rows_pcross = [], [], [], [], []
    rows_p_pos_diag, rows_p_psiba, rows_bg_err = [], [], []
    rows_p_psi, rows_p_ba, rows_p_bg = [], [], []
    idx6 = [6, 7, 8, 9, 10, 11]
    gnss_innovations_in_outage = 0

    for truth in states:
        t = truth.t
        s = imu.step(truth, rng_imu)
        q = quantum.step(truth, rng_q) if quantum is not None else None
        epoch = gnss_signal.step(truth, rng_gnss)
        fix = None
        in_outage = gnss_outage is not None and gnss_outage[0] <= t < gnss_outage[1]
        if epoch is not None and not in_outage:
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
        C_true = euler_to_dcm(truth.att)
        psi_err = so3_log(eskf.C @ C_true.T)  # nav-frame attitude error vector (Sec 2.2 convention)
        ba_true = _true_accel_bias(imu)
        ba_err = eskf.b_a - ba_true
        bg_true = _true_gyro_bias(imu)
        bg_err = eskf.b_g - bg_true
        rows_t.append(t)
        rows_err.append(err)
        rows_ba_err.append(ba_err)
        rows_psi_err.append(psi_err)
        rows_bg_err.append(bg_err)
        rows_pcross.append(eskf.P[9:12, 6:9].copy())
        rows_p_pos_diag.append(np.diag(eskf.P[0:3, 0:3]).copy())
        rows_p_psiba.append(eskf.P[np.ix_(idx6, idx6)].copy())
        rows_p_psi.append(eskf.P[6:9, 6:9].copy())
        rows_p_ba.append(eskf.P[9:12, 9:12].copy())
        rows_p_bg.append(eskf.P[12:15, 12:15].copy())
        if fix is not None and in_outage:
            gnss_innovations_in_outage += 1

    return {
        "t": np.array(rows_t), "err": np.array(rows_err), "ba_err": np.array(rows_ba_err),
        "psi_err": np.array(rows_psi_err), "pcross": np.array(rows_pcross), "bg_err": np.array(rows_bg_err),
        "p_pos_diag": np.array(rows_p_pos_diag), "p_psiba": np.array(rows_p_psiba),
        "p_psi": np.array(rows_p_psi), "p_ba": np.array(rows_p_ba), "p_bg": np.array(rows_p_bg),
        "gnss_innovations_in_outage": gnss_innovations_in_outage,
    }


def _true_gyro_bias(imu: ClassicalImu) -> np.ndarray:
    ch = imu._gyro_ch
    return (ch.turn_on_bias + ch.bias_gm + ch.bias_rrw).copy()


# ===========================================================================
# Master follow-up: NEES consistency diagnostic. A correctly-modelled KF
# cannot make expected error WORSE with an extra correct measurement; if it
# does, the filter's own uncertainty must be inconsistent (NEES >> 1/dof).
# ===========================================================================
def nees_diagnostic():
    print("\n=== NEES diagnostic (T=60s outage), seeds 500-509 ===")
    print("Horizontal position NEES (H-NEES): e_h^T P_h^-1 e_h, e_h=(dx,dy), ideal mean = 2 (2 dof).")
    print("[psi,b_a] NEES: e^T P^-1 e, e=[psi_err(3),ba_err(3)], ideal mean = 6 (6 dof).\n")
    arms = [("industrial_mems (native)", "industrial_mems", None),
            ("tactical (full grade)", "tactical", None)]
    checkpoints = (T0, T0 + 30.0, T0 + 60.0)
    for label, grade, gyro_override in arms:
        for use_cai in (False, True):
            h_nees = {cp: [] for cp in checkpoints}
            sigma1 = {cp: [] for cp in checkpoints}
            actual = {cp: [] for cp in checkpoints}
            psiba_nees_t0 = []
            for seed in SEEDS:
                res = run_scenario_diag(imu_grade=grade, quantum_grade="field" if use_cai else None,
                                         duration_s=T0 + 60.0 + 30.0, dt=0.01, seed=seed, hold_s=10.0,
                                         kappa_R=KAPPA_R, gnss_outage=(T0, T0 + 60.0),
                                         quantum_outlier_channel=False, gyro_override=gyro_override)
                for cp in checkpoints:
                    i = index_at(res["t"], cp)
                    e_h = res["err"][i, :2]
                    P_h = res["p_pos_diag"][i, :2]  # diag only (off-diag pos cov not logged; ok, dominant terms)
                    h_nees[cp].append(float(e_h @ (e_h / P_h)))
                    sigma1[cp].append(float(np.sqrt(P_h.sum())))
                    actual[cp].append(float(np.linalg.norm(e_h)))
                i0 = index_at(res["t"], T0)
                e6 = np.concatenate([res["psi_err"][i0], res["ba_err"][i0]])
                P6 = res["p_psiba"][i0]
                try:
                    psiba_nees_t0.append(float(e6 @ np.linalg.solve(P6, e6)))
                except np.linalg.LinAlgError:
                    psiba_nees_t0.append(float("nan"))
            arm_label = f"{label} | {'CAI' if use_cai else 'no CAI'}"
            print(f"-- {arm_label} --")
            for cp in checkpoints:
                print(f"   t0+{cp-T0:.0f}s: H-NEES mean={np.mean(h_nees[cp]):.2f}  "
                      f"pred-1sig mean={np.mean(sigma1[cp]):.2f}m  actual-err mean={np.mean(actual[cp]):.2f}m")
            print(f"   [psi,ba] NEES @t0 mean={np.mean(psiba_nees_t0):.2f} (6 dof)")


# ===========================================================================
# 2. Physics decomposition at outage onset: CAI vs no-CAI.
# ===========================================================================
def decomposition():
    print("\n=== Decomposition at outage onset (t0=60s), industrial_mems, seeds 500-509 ===")
    rows = []
    for use_cai in (False, True):
        ba_errs, psi_errs, pcross_norms, err60 = [], [], [], []
        for seed in SEEDS:
            res = run_scenario_diag(imu_grade="industrial_mems",
                                     quantum_grade="field" if use_cai else None,
                                     duration_s=T0 + 60.0 + 30.0, dt=0.01, seed=seed, hold_s=10.0,
                                     kappa_R=KAPPA_R, gnss_outage=(T0, T0 + 60.0),
                                     quantum_outlier_channel=False)
            i0 = index_at(res["t"], T0)
            i1 = index_at(res["t"], T0 + 60.0)
            ba_errs.append(res["ba_err"][i0, :2])       # horizontal-plane bias error at outage onset
            psi_errs.append(res["psi_err"][i0, :2])     # roll/pitch (horizontal-tilt) error at outage onset
            pcross_norms.append(np.linalg.norm(res["pcross"][i0][:2, :2]))
            err60.append(np.linalg.norm(res["err"][i1, :2]))
        ba_errs = np.array(ba_errs); psi_errs = np.array(psi_errs)
        ba_mag = np.linalg.norm(ba_errs, axis=1)
        psi_mag = np.linalg.norm(psi_errs, axis=1)
        # Sec 2.5 "honest expectation" formulas: bias term 0.5*|dba|*T^2,
        # tilt term g*|dtheta|*T^3/6 (T=60s window).
        T = 60.0
        bias_term = 0.5 * ba_mag * T ** 2
        tilt_term = G0 * psi_mag * T ** 3 / 6.0
        label = "CAI (outlier OFF)" if use_cai else "no CAI"
        print(f"-- {label} --")
        print(f"  |b_a err| @t0: mean={ba_mag.mean():.4e} m/s^2  |psi err| @t0: mean={psi_mag.mean():.4e} rad")
        print(f"  predicted bias-term drift (0.5|dba|T^2): mean={bias_term.mean():.1f} m")
        print(f"  predicted tilt-term drift (g|dpsi|T^3/6): mean={tilt_term.mean():.1f} m")
        print(f"  predicted sum: mean={(bias_term+tilt_term).mean():.1f} m  vs measured err@t0+60s: "
              f"mean={np.mean(err60):.1f} m median={np.median(err60):.1f}")
        print(f"  |P[ba,psi] cross-cov| @t0 (horiz block): mean={np.mean(pcross_norms):.3e}")
        rows.append((label, ba_mag.mean(), psi_mag.mean(), bias_term.mean(), tilt_term.mean(),
                     np.mean(err60), np.mean(pcross_norms)))
    return rows


# ===========================================================================
# 3+4. Gyro-quality sweep, CAI (outlier OFF) vs no-CAI. Also a "perfect gyro"
# arm (gyro noise and bias = 0), accel held at industrial_mems.
# ===========================================================================
def perfect_gyro_params(rate_hz_reference: AxisErrorParams) -> AxisErrorParams:
    return AxisErrorParams(
        turn_on_bias_std=0.0, bias_instability=0.0, bias_instability_tau_c=1.0,
        random_walk=0.0, rate_random_walk=0.0, scale_factor_std=0.0,
        misalignment_std=0.0, resolution=0.0, range_max=rate_hz_reference.range_max,
    )


def one_run(grade, use_cai, T, seed, gyro_override=None):
    from tests._fusion_helpers import run_scenario
    res = run_scenario(platform="ground", imu_grade=grade, quantum_grade="field" if use_cai else None,
                        duration_s=T0 + T + 30.0, dt=0.01, seed=seed, hold_s=10.0,
                        kappa_R=KAPPA_R, gnss_outage=(T0, T0 + T), quantum_outlier_channel=False) \
        if gyro_override is None else run_scenario_diag(
        imu_grade=grade, quantum_grade="field" if use_cai else None,
        duration_s=T0 + T + 30.0, dt=0.01, seed=seed, hold_s=10.0,
        kappa_R=KAPPA_R, gnss_outage=(T0, T0 + T), quantum_outlier_channel=False,
        gyro_override=gyro_override)
    assert res["gnss_innovations_in_outage"] == 0
    t = res["t"]
    i1 = index_at(t, T0 + T)
    err_h = np.linalg.norm(res["err"][:, :2], axis=1)
    i0 = index_at(t, T0)
    return float(err_h[i1]), float(err_h[i0:i1 + 1].max())


def gyro_sweep():
    print("\n=== Gyro-quality sweep (T=60s outage), industrial_mems accel, seeds 500-509 ===")
    imu_ind = ClassicalImu(grade="industrial_mems", rng=np.random.default_rng(0))
    gyro_tactical = ClassicalImu(grade="tactical", rng=np.random.default_rng(0))._cfg.gyro
    gyro_perfect = perfect_gyro_params(imu_ind._cfg.gyro)

    arms = [
        ("industrial_mems gyro (native)", "industrial_mems", None),
        ("tactical gyro (mixed w/ industrial_mems accel)", "industrial_mems", gyro_tactical),
        ("perfect gyro (mixed w/ industrial_mems accel)", "industrial_mems", gyro_perfect),
        ("tactical (full grade)", "tactical", None),
    ]
    table = []
    for label, grade, gyro_override in arms:
        for use_cai in (False, True):
            errs, maxes = [], []
            for seed in SEEDS:
                e, m = one_run(grade, use_cai, 60.0, seed, gyro_override=gyro_override)
                errs.append(e); maxes.append(m)
            errs = np.array(errs)
            row = (label, "CAI" if use_cai else "no CAI", errs.mean(), np.median(errs), errs.max())
            table.append(row)
            print(f"{label:50s} | {'CAI' if use_cai else 'no CAI':7s} | "
                  f"mean={row[2]:8.2f}  median={row[3]:8.2f}  max={row[4]:8.2f}")
    return table


# ===========================================================================
# D-030: truth-side ablation to localise the [psi,b_a] NEES mismatch.
# Test-local ImuGradeConfig overrides ONLY (fedqpnt/sensors/imu.py untouched).
# ===========================================================================
def _nees(e, P):
    try:
        return float(e @ np.linalg.solve(P, e))
    except np.linalg.LinAlgError:
        return float("nan")


def truth_side_ablation():
    print("\n=== D-030 truth-side ablation (industrial_mems, CAI off, T=60s), seeds 500-509 ===")
    # NOTE: an earlier version of this ablation overrode the accel/gyro
    # channel AFTER ClassicalImu.__init__ already built the default ones,
    # which double-draws from rng_imu and shifts the noise stream between
    # arms (unrelated to the ablated parameter) -- invalidating the
    # comparison. Fixed here by registering each arm as its own GRADES
    # entry so every arm gets exactly ONE clean ClassicalImu(grade=...)
    # construction (fedqpnt/sensors/imu.py itself is not edited/persisted;
    # GRADES is restored at the end).
    from fedqpnt.sensors.imu import GRADES, ImuGradeConfig
    base = ClassicalImu(grade="industrial_mems", rng=np.random.default_rng(0))
    acc0, gyr0 = base._cfg.accel, base._cfg.gyro

    def ov(p, **kw):
        return dataclasses.replace(p, **kw)

    no_sf = dict(scale_factor_std=0.0)
    no_mis = dict(misalignment_std=0.0)
    no_sf_mis = dict(scale_factor_std=0.0, misalignment_std=0.0)
    no_quant_sat = dict(scale_factor_std=0.0, misalignment_std=0.0, resolution=0.0, range_max=1e6)

    grade_specs = {
        "cai_h3_b": (ov(acc0, **no_sf), ov(gyr0, **no_sf)),
        "cai_h3_c": (ov(acc0, **no_mis), ov(gyr0, **no_mis)),
        "cai_h3_d": (ov(acc0, **no_sf_mis), ov(gyr0, **no_sf_mis)),
        "cai_h3_e": (ov(acc0, **no_quant_sat), ov(gyr0, **no_quant_sat)),
    }
    saved_grades = dict(GRADES)
    for name, (a, g) in grade_specs.items():
        GRADES[name] = (lambda a=a, g=g, n=name: ImuGradeConfig(name=n, rate_hz=100.0, accel=a, gyro=g))

    arms = [
        ("(a) as-is", "industrial_mems"),
        ("(b) scale_factor=0 (both ch.)", "cai_h3_b"),
        ("(c) misalignment=0 (both ch.)", "cai_h3_c"),
        ("(d) both=0 (both ch.)", "cai_h3_d"),
        ("(e) both=0 + no quant/sat", "cai_h3_e"),
        ("(f) bias=GM1+turn-on only (already the truth model; rate_random_walk=0 "
         "for this grade already -> structurally identical to (a))", "industrial_mems"),
    ]
    results = {}
    for label, grade_name in arms:
        psi3, psi_rp, psi_yaw, ba3, bg3, hpos = [], [], [], [], [], []
        for seed in SEEDS:
            res = run_scenario_diag(imu_grade=grade_name, quantum_grade=None,
                                     duration_s=T0 + 60.0 + 30.0, dt=0.01, seed=seed, hold_s=10.0,
                                     kappa_R=KAPPA_R, gnss_outage=(T0, T0 + 60.0),
                                     quantum_outlier_channel=False)
            i0 = index_at(res["t"], T0)
            i1 = index_at(res["t"], T0 + 60.0)
            psi_e = res["psi_err"][i0]
            psi3.append(_nees(psi_e, res["p_psi"][i0]))
            psi_rp.append(_nees(psi_e[:2], res["p_psi"][i0][:2, :2]))
            psi_yaw.append(psi_e[2] ** 2 / res["p_psi"][i0][2, 2])
            ba3.append(_nees(res["ba_err"][i0], res["p_ba"][i0]))
            bg3.append(_nees(res["bg_err"][i0], res["p_bg"][i0]))
            e_h = res["err"][i1, :2]
            hpos.append(_nees(e_h, np.diag(res["p_pos_diag"][i1, :2])))
        results[label] = dict(err60=None)
        print(f"-- {label} --")
        print(f"   psi NEES(3dof,ideal3)={np.mean(psi3):.1f}  psi_rollpitch(2dof,ideal2)={np.mean(psi_rp):.1f}  "
              f"psi_yaw(1dof,ideal1)={np.mean(psi_yaw):.1f}")
        print(f"   b_a NEES(3dof,ideal3)={np.mean(ba3):.1f}  b_g NEES(3dof,ideal3)={np.mean(bg3):.1f}  "
              f"H-pos NEES@t0+60(2dof,ideal2)={np.mean(hpos):.1f}")
        results[label]["consistent"] = np.mean(hpos) <= 6.0  # <=3x ideal(2)
    GRADES.clear()
    GRADES.update(saved_grades)
    return results


def cai_effect_for_consistent_arm(accel_ov, gyro_ov, label):
    print(f"\n=== CAI vs no-CAI for consistent arm [{label}] ===")
    for use_cai in (False, True):
        errs = []
        for seed in SEEDS:
            res = run_scenario_diag(imu_grade="industrial_mems", quantum_grade="field" if use_cai else None,
                                     duration_s=T0 + 60.0 + 30.0, dt=0.01, seed=seed, hold_s=10.0,
                                     kappa_R=KAPPA_R, gnss_outage=(T0, T0 + 60.0),
                                     quantum_outlier_channel=False,
                                     accel_override=accel_ov, gyro_override=gyro_ov)
            i1 = index_at(res["t"], T0 + 60.0)
            errs.append(float(np.linalg.norm(res["err"][i1, :2])))
        print(f"  {'CAI' if use_cai else 'no CAI'}: mean={np.mean(errs):.2f} median={np.median(errs):.2f} "
              f"max={np.max(errs):.2f}")


# ===========================================================================
# D-031: GNSS truth-side ablation (correlated iono/tropo/multipath residuals
# treated as white by the receiver/filter, D-023 item 2). Module-level
# function monkeypatch (test-local; fedqpnt/gnss/signal.py, receiver.py NOT
# edited on disk) -- every arm still calls the SAME rng.normal() sites the
# same number of times (only the sigma/tau VALUES change), so the
# single-construction RNG discipline from D-030 holds automatically; no
# object reconstruction is needed here.
# ===========================================================================
def _gnss_fix_error_check(zero_correlated: bool, seed_list, duration_s=60.0):
    """Mean reported horizontal 1sigma (from GnssFix.cov_pos) vs actual
    horizontal fix-error std, over ordinary (non-outage) GNSS fixes."""
    reported_1sig, actual_errs = [], []
    for seed in seed_list:
        rng_traj = stream(seed, "node", "traj")
        rng_imu = stream(seed, "node", "imu")
        rng_gnss = stream(seed, "node", "gnss")
        from fedqpnt.sim.trajectory import make_trajectory
        traj = make_trajectory("ground")
        states = make_truth_with_hold(traj, duration_s, 0.01, rng_traj, hold_s=10.0, world="flat")
        gnss_signal = GnssSignalModel(rate_hz=1.0)
        receiver = GnssReceiver()
        for truth in states:
            epoch = gnss_signal.step(truth, rng_gnss)
            if epoch is None:
                continue
            fix = receiver.solve(epoch.for_agent())
            if not fix.valid:
                continue
            reported_1sig.append(float(np.sqrt(fix.cov_pos[0, 0] + fix.cov_pos[1, 1])))
            actual_errs.append(fix.pos[:2] - truth.pos[:2])
    actual_errs = np.array(actual_errs)
    actual_std = float(np.sqrt(np.mean(np.sum(actual_errs ** 2, axis=1))))
    return float(np.mean(reported_1sig)), actual_std


def gnss_truth_side_ablation():
    print("\n=== D-031 GNSS truth-side ablation (industrial_mems, CAI off, T=60s), seeds 500-509 ===")
    orig_iono = _gnss_signal_mod.iono_residual_sigma_m
    orig_tropo = _gnss_signal_mod.tropo_residual_sigma_m
    orig_mp = _gnss_signal_mod.multipath_sigma_m
    orig_gm = _gnss_signal_mod._gauss_markov_step

    def _zero(el):
        return 0.0

    def _gm_tau1(x, dt, tau, sigma, rng):
        return orig_gm(x, dt, 1.0, sigma, rng)

    def _set_mode(mode):
        if mode == "zero":
            _gnss_signal_mod.iono_residual_sigma_m = _zero
            _gnss_signal_mod.tropo_residual_sigma_m = _zero
            _gnss_signal_mod.multipath_sigma_m = _zero
            _gnss_signal_mod._gauss_markov_step = orig_gm
        elif mode == "tau1":
            _gnss_signal_mod.iono_residual_sigma_m = orig_iono
            _gnss_signal_mod.tropo_residual_sigma_m = orig_tropo
            _gnss_signal_mod.multipath_sigma_m = orig_mp
            _gnss_signal_mod._gauss_markov_step = _gm_tau1
        else:
            _gnss_signal_mod.iono_residual_sigma_m = orig_iono
            _gnss_signal_mod.tropo_residual_sigma_m = orig_tropo
            _gnss_signal_mod.multipath_sigma_m = orig_mp
            _gnss_signal_mod._gauss_markov_step = orig_gm

    arms = [
        ("(a) as-is, kappa_R=40", "baseline", KAPPA_R),
        ("(g) iono/tropo/mp OFF, kappa_R=40", "zero", 40.0),
        ("(h) iono/tropo/mp OFF, kappa_R=1", "zero", 1.0),
        ("(i) tau->1s (same sigma), kappa_R=40", "tau1", 40.0),
    ]
    try:
        for label, mode, kR in arms:
            _set_mode(mode)
            psi3, psi_rp, psi_yaw, ba3, bg3, hpos = [], [], [], [], [], []
            for seed in SEEDS:
                res = run_scenario_diag(imu_grade="industrial_mems", quantum_grade=None,
                                         duration_s=T0 + 60.0 + 30.0, dt=0.01, seed=seed, hold_s=10.0,
                                         kappa_R=kR, gnss_outage=(T0, T0 + 60.0),
                                         quantum_outlier_channel=False)
                i0 = index_at(res["t"], T0)
                i1 = index_at(res["t"], T0 + 60.0)
                psi_e = res["psi_err"][i0]
                psi3.append(_nees(psi_e, res["p_psi"][i0]))
                psi_rp.append(_nees(psi_e[:2], res["p_psi"][i0][:2, :2]))
                psi_yaw.append(psi_e[2] ** 2 / res["p_psi"][i0][2, 2])
                ba3.append(_nees(res["ba_err"][i0], res["p_ba"][i0]))
                bg3.append(_nees(res["bg_err"][i0], res["p_bg"][i0]))
                e_h = res["err"][i1, :2]
                hpos.append(_nees(e_h, np.diag(res["p_pos_diag"][i1, :2])))
            print(f"-- {label} --")
            print(f"   psi NEES(3dof,ideal3)={np.mean(psi3):.1f}  psi_rollpitch(2dof,ideal2)={np.mean(psi_rp):.1f}  "
                  f"psi_yaw(1dof,ideal1)={np.mean(psi_yaw):.1f}")
            print(f"   b_a NEES(3dof,ideal3)={np.mean(ba3):.1f}  b_g NEES(3dof,ideal3)={np.mean(bg3):.1f}  "
                  f"H-pos NEES@t0+60(2dof,ideal2)={np.mean(hpos):.1f}")

        for label, mode in (("(a) as-is", "baseline"), ("(g) iono/tropo/mp OFF", "zero")):
            _set_mode(mode)
            rep1sig, actual_std = _gnss_fix_error_check(mode == "zero", SEEDS, duration_s=60.0)
            print(f"-- fix-error check {label} -- reported mean 1sigma={rep1sig:.2f}m  "
                  f"actual horizontal fix-error std={actual_std:.2f}m")
    finally:
        _gnss_signal_mod.iono_residual_sigma_m = orig_iono
        _gnss_signal_mod.tropo_residual_sigma_m = orig_tropo
        _gnss_signal_mod.multipath_sigma_m = orig_mp
        _gnss_signal_mod._gauss_markov_step = orig_gm


# ===========================================================================
# D-032 item 2(a): truth-noise-parameter vs ESKF-Q parameter table.
# ===========================================================================
def q_parameter_table():
    print("\n=== D-032 (2a) truth IMU params vs ESKF Q entries ===")
    for grade in ("industrial_mems", "tactical"):
        imu = ClassicalImu(grade=grade, rng=np.random.default_rng(0))
        cfg = imu.config()
        eskf = ESKF(cfg, config=ESKFConfig())
        acc, gyr = cfg["accel"], cfg["gyro"]
        print(f"-- {grade} --")
        print(f"  ACCEL truth: VRW(random_walk)={acc['random_walk']:.4e} m/s^2*sqrt(s)  "
              f"GM1 sigma_BI(bias_instability)={acc['bias_instability']:.4e} m/s^2  "
              f"tau_c={acc['bias_instability_tau_c']:.1f} s  turn_on_std={acc['turn_on_bias_std']:.4e} m/s^2  "
              f"RRW={acc['rate_random_walk']:.4e} (unused if 0)")
        print(f"  GYRO  truth: ARW(random_walk)={gyr['random_walk']:.4e} rad/s*sqrt(s)  "
              f"GM1 sigma_BI(bias_instability)={gyr['bias_instability']:.4e} rad/s  "
              f"tau_c={gyr['bias_instability_tau_c']:.1f} s  turn_on_std={gyr['turn_on_bias_std']:.4e} rad/s  "
              f"RRW={gyr['rate_random_walk']:.4e} (unused if 0)")
        print(f"  ESKF reads: vrw={eskf.vrw:.4e} (== truth VRW, no conversion needed)  "
              f"arw={eskf.arw:.4e} rad/s*sqrt(s) (== truth ARW, already converted deg/sqrt(hr)->rad/sqrt(s) "
              f"in fedqpnt/sensors/imu.py, /60 for sqrt(hr->s))")
        sigma_ba_gm = acc["bias_instability"] / 0.664
        sigma_bg_gm = gyr["bias_instability"] / 0.664
        print(f"  ESKF Qc entries (continuous PSD, per axis): accel block=vrw^2={eskf.vrw**2:.4e} (m/s^2)^2*s;  "
              f"gyro block=arw^2={eskf.arw**2:.4e} (rad/s)^2*s;  "
              f"b_a block q_ba=2*sigma_gm^2/tau_a, sigma_gm=BI/0.664={sigma_ba_gm:.4e} -> "
              f"q_ba={eskf.q_ba:.4e} (m/s^2)^2/s;  "
              f"b_g block q_bg=2*sigma_gm^2/tau_g, sigma_gm={sigma_bg_gm:.4e} -> q_bg={eskf.q_bg:.4e} (rad/s)^2/s")
        print(f"  Discretisation: Qd = 0.5*(Phi@GQGt + GQGt@Phi.T)*dt (dt=0.01s), Phi=I+F*dt+0.5*(F*dt)^2 "
              f"(2nd-order Taylor, not exact expm) -- no unit mismatch found (VRW/ARW pass through unchanged, "
              f"GM1 sigma/tau match the architecture's q_b=2*sigma_BI^2/tau_c formula exactly); "
              f"RRW=0 for both grades so its absence from Qc is a non-issue here.")


# ===========================================================================
# D-032 item 2(b): pure-INS (no GNSS, no CAI) NEES consistency test. True
# initial errors drawn from the filter's own P0 -> prior is exactly
# consistent by construction; isolates Q/Phi discretisation from GNSS/CAI.
# ===========================================================================
def _static_truth_states(duration_s, dt, pos0=None):
    n = int(round(duration_s / dt))
    pos0 = np.zeros(3) if pos0 is None else pos0
    return [TruthState(t=k * dt, pos=pos0.copy(), vel=np.zeros(3), acc=np.zeros(3),
                        att=np.zeros(3), omega_b=np.zeros(3), f_b=np.array([0.0, 0.0, G0]))
            for k in range(n)]


def pure_ins_nees(imu_grade, seed, course, duration_s=302.0, dt=0.01, fix_init_bias=False,
                   accel_override=None, gyro_override=None,
                   checkpoints=(10.0, 60.0, 300.0)):
    rng_imu = stream(seed, "node", "imu")
    rng_err = stream(seed, "node", "init_err")
    if course == "static":
        states = _static_truth_states(duration_s, dt)
    else:
        from fedqpnt.sim.trajectory import make_trajectory
        traj = make_trajectory("ground")
        tt = traj.generate(duration_s, dt, stream(seed, "node", "traj"), world="flat")
        states = [TruthState(t=tt.t[k], pos=tt.pos[k], vel=tt.vel[k], acc=tt.acc[k],
                              att=tt.att[k], omega_b=tt.omega_b[k], f_b=tt.f_b[k]) for k in range(len(tt))]

    imu = ClassicalImu(grade=imu_grade, rng=rng_imu, world="flat")
    if accel_override is not None:
        imu._cfg.accel = accel_override
        imu._accel_ch = _AxisChannel(accel_override, imu._dt, rng_imu)
    if gyro_override is not None:
        imu._cfg.gyro = gyro_override
        imu._gyro_ch = _AxisChannel(gyro_override, imu._dt, rng_imu)
    eskf = ESKF(imu.config(), config=ESKFConfig(world="flat"))
    t0 = states[0].t
    eskf.initialize_static(t0, states[0].pos.copy(), states[0].att.copy(), vel0=states[0].vel.copy())
    # D-034 item 1: eskf.initialize_static() leaves b_a=b_g=0 (a real cold
    # start has no bias estimate yet), but the truth IMU's turn_on_bias +
    # bias_gm(0) is already a nonzero realised draw at construction --
    # BEFORE this fix, injecting dx0 on top of eskf.b_a=0 (instead of on
    # top of the TRUE b_a) leaves an unmatched baseline error of
    # -true_b_a(t0) that P0 never accounted for, inflating b_a/b_g NEES by
    # a diagnostic-only bug (not an eskf.py bug). fix_init_bias=True
    # matches the filter's nominal bias to truth before injecting dx0, so
    # err(0)=dx0 exactly for EVERY block, as intended.
    ba0_true = _true_accel_bias(imu)
    bg0_true = _true_gyro_bias(imu)
    dx0 = rng_err.multivariate_normal(np.zeros(eskf.N), eskf.P)
    eskf.p = eskf.p + dx0[0:3]
    eskf.v = eskf.v + dx0[3:6]
    eskf.C = so3_exp(dx0[6:9]) @ eskf.C
    if fix_init_bias:
        eskf.b_a = ba0_true + dx0[9:12]
        eskf.b_g = bg0_true + dx0[12:15]
    else:
        eskf.b_a = eskf.b_a + dx0[9:12]
        eskf.b_g = eskf.b_g + dx0[12:15]

    def _block(truth, imu_):
        C_true = euler_to_dcm(truth.att)
        psi_e = so3_log(eskf.C @ C_true.T)
        v_e = eskf.v - truth.vel
        p_e = eskf.p - truth.pos
        ba_e = eskf.b_a - _true_accel_bias(imu_)
        bg_e = eskf.b_g - _true_gyro_bias(imu_)
        return dict(
            psi3=_nees(psi_e, eskf.P[6:9, 6:9]),
            psi_rp=_nees(psi_e[:2], eskf.P[6:8, 6:8]),
            psi_yaw=psi_e[2] ** 2 / eskf.P[8, 8],
            v3=_nees(v_e, eskf.P[3:6, 3:6]), p3=_nees(p_e, eskf.P[0:3, 0:3]),
            ba3=_nees(ba_e, eskf.P[9:12, 9:12]), bg3=_nees(bg_e, eskf.P[12:15, 12:15]),
            P_diag=dict(psi=np.diag(eskf.P[6:9, 6:9]).copy(), v=np.diag(eskf.P[3:6, 3:6]).copy(),
                        p=np.diag(eskf.P[0:3, 0:3]).copy(), ba=np.diag(eskf.P[9:12, 9:12]).copy(),
                        bg=np.diag(eskf.P[12:15, 12:15]).copy()),
            err=dict(psi=psi_e.copy(), v=v_e.copy(), p=p_e.copy(), ba=ba_e.copy(), bg=bg_e.copy()))

    out = {cp: None for cp in checkpoints}
    if 0.0 in out:
        out[0.0] = _block(states[0], imu)
    for truth in states[1:]:
        if all(v is not None for v in out.values()):
            break
        t = truth.t
        s = imu.step(truth, rng_imu)
        eskf.propagate(t, s)
        rel_t = t - t0
        for cp in checkpoints:
            if out[cp] is None and rel_t >= cp - 1e-9:
                out[cp] = _block(truth, imu)
    return out


def pure_ins_sweep():
    print("\n=== D-032 (2b) pure-INS NEES (no GNSS, no CAI), seeds 500-519 ===")
    print("ideal means: psi3~3 psi_rp~2 psi_yaw~1 v3~3 p3~3 ba3~3 bg3~3\n")
    seeds20 = list(range(500, 520))
    for grade in ("industrial_mems", "tactical"):
        for course in ("static", "maneuvering"):
            acc = {cp: {k: [] for k in ("psi3", "psi_rp", "psi_yaw", "v3", "p3", "ba3", "bg3")}
                   for cp in (10.0, 60.0, 300.0)}
            for seed in seeds20:
                res = pure_ins_nees(grade, seed, course)
                for cp, block in res.items():
                    for k, v in block.items():
                        acc[cp][k].append(v)
            print(f"-- {grade} | {course} --")
            for cp in (10.0, 60.0, 300.0):
                m = {k: np.mean(v) for k, v in acc[cp].items()}
                print(f"   t={cp:.0f}s: psi3={m['psi3']:.1f} psi_rp={m['psi_rp']:.1f} psi_yaw={m['psi_yaw']:.1f} "
                      f"v3={m['v3']:.1f} p3={m['p3']:.1f} ba3={m['ba3']:.1f} bg3={m['bg3']:.1f}")


# ===========================================================================
# D-035 item 2(c): nominal 10-min GNSS-aided ANEES, kappa_R=40 vs kappa_R=1.
# ===========================================================================
def nominal_aneess_sweep(grade="industrial_mems", seeds=(500, 501, 502, 503, 504), duration_s=600.0):
    print(f"\n=== D-035 (2c) nominal {duration_s:.0f}s GNSS-aided ANEES, {grade}, seeds {seeds[0]}-{seeds[-1]} ===")
    for kR in (40.0, 1.0):
        vals = []
        for seed in seeds:
            res = run_scenario(platform="ground", imu_grade=grade, quantum_grade=None,
                                duration_s=duration_s, dt=0.01, seed=seed, hold_s=10.0, kappa_R=kR)
            vals.append(anees_pos(res))
        print(f"  kappa_R={kR:g}: ANEES mean={np.mean(vals):.2f} (ideal ~1.0)  per-seed={[round(v,2) for v in vals]}")


if __name__ == "__main__":
    print("=== Bug check 1(b): noiseless convergence + no attitude disturbance ===")
    bug_check_noiseless_convergence()
    decomposition()
    gyro_sweep()
