"""DIAG (round-2, tuning seeds only): decompose pure-IMU coast error after a GNSS blackout from T0.
Runs (a) the full Agent with GNSS removed from T0 (CAI on/off), (b) two ORACLE open-loop ESKF mechanisations
started from TRUTH at T0: A = bias estimate 0 (raw IMU), B = bias estimate = true current bias (turn-on + GM1), so the
remaining error is SF/misalignment/noise/ vertical-channel only.  Reports err_h, err_v, vel err, tilt/heading err,
bias-estimate error, filter sigma, at checkpoints.
Usage: python scripts/diag_coast.py <grade> <seed> [T0=60] [cai=1] [duration=420] [method=undefended]
"""
import sys
from pathlib import Path
import numpy as np
import os
ROOT = Path(os.environ.get('DIAG_ROOT') or Path(__file__).resolve().parent.parent)   # DIAG_ROOT = worktree with candidate fix
sys.path.insert(0, str(ROOT))
from fedqpnt.eval import campaign as C, scenarios as SC
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config
from fedqpnt.node.agent import Agent
from fedqpnt.fusion.eskf import ESKF, ESKFConfig
from fedqpnt.sim.rotations import euler_to_dcm

grade = sys.argv[1]; SEED = int(sys.argv[2])
T0 = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
CAI = int(sys.argv[4]) if len(sys.argv) > 4 else 1
DUR = float(sys.argv[5]) if len(sys.argv) > 5 else 420.0
method = sys.argv[6] if len(sys.argv) > 6 else "undefended"
assert SEED < 10000, "tuning seeds only"
sc = SC.get("S1")   # nominal scenario: no attack, schuler_tangent, same trajectory generator
sp = C.build_spec_dict(sc, method, SEED, imu_grade=grade, detector_weights_path="results/m1/detector_weights_sup_v4.npz",
                       duration_s=DUR)
env = NodeEnvironment(EnvConfig(platform=sp["platform"], world=sp["world"], imu_grade=sp["imu_grade"],
        quantum_grade=sp["quantum_grade"], gnss_rate_hz=sp["gnss_rate_hz"], hold_s=sp["hold_s"],
        heading_noise_deg=sp["heading_noise_deg"], attacks=[]),
        seed=SEED, node_id=sp["node_id"], dt=sp["dt"], duration_s=sp["duration_s"])
cfg = make_agent_config(sp["method"], kappa_R=sp["kappa_R"], kappa_Q=sp["kappa_Q"], world=sp["world"],
        quantum_enabled=sp["quantum_grade"] is not None, detector_weights_path=sp["detector_weights_path"],
        imu_grade=grade, quantum_grade=sp["quantum_grade"])
agent = Agent(cfg, env.imu.config(), node_id=sp["node_id"])
ocfg = ESKFConfig(world=sp["world"])
orA = ESKF(env.imu.config(), ocfg); orB = ESKF(env.imu.config(), ocfg)

def tilt_heading_err(C_est, att_true):
    Ct = euler_to_dcm(att_true)
    dC = C_est @ Ct.T                      # estimated-vs-true rotation (small)
    v = np.array([dC[2, 1] - dC[1, 2], dC[0, 2] - dC[2, 0], dC[1, 0] - dC[0, 1]]) / 2.0
    return float(np.hypot(v[0], v[1])), float(v[2])

f_hold, init, oracle_on = [], False, False
rows = []
CK = [T0 + x for x in (-29, -25, -20, -10, -5, -1, 0, 10, 30, 60, 120, 180, 240, 300, 360)]
ck_i = 0
print(f"# diag_coast {grade} seed={SEED} T0={T0} cai={CAI} method={method} world={sp['world']}")
for k in range(len(env)):
    tick = env.tick(k); t = tick.t
    if not init:
        if t < env.hold_s:
            if tick.imu is not None: f_hold.append(tick.imu.f_b)
            continue
        fm = np.mean(f_hold, axis=0)
        phi = np.arctan2(fm[1], fm[2]); th = np.arctan2(-fm[0], np.hypot(fm[1], fm[2]))
        agent.initialize_static(t, tick.truth.pos.copy(), np.array([phi, th, float(tick.truth.att[2]) + env.initial_heading_noise()]))
        init = True; continue
    ge = tick.gnss_epoch if t < T0 else None
    q = tick.quantum if CAI else None
    a = agent.step(t, tick.imu, q, ge)
    if not oracle_on and t >= T0:
        oracle_on = True
        ach, gch = env.imu._accel_ch, env.imu._gyro_ch
        ba = ach.turn_on_bias + ach.bias_gm; bg = gch.turn_on_bias + gch.bias_gm
        print(f"# true biases at T0: accel(mg)={np.round(ba/9.80665*1e3,3)} gyro(deg/h)={np.round(np.degrees(bg)*3600,1)}"
              f"  turn_on accel(mg)={np.round(ach.turn_on_bias/9.80665*1e3,3)} gyro(deg/h)={np.round(np.degrees(gch.turn_on_bias)*3600,1)}")
        print(f"# true SF accel(ppm)={np.round((ach.scale_factor-1)*1e6,0)} gyro(ppm)={np.round((gch.scale_factor-1)*1e6,0)}")
        for o, b_a, b_g in ((orA, 0*ba, 0*bg), (orB, ba, bg)):
            o.initialize_static(t, tick.truth.pos.copy(), tick.truth.att.copy(), vel0=tick.truth.vel.copy())
            o.b_a = b_a.copy(); o.b_g = b_g.copy()
        b_true0 = (ba, bg)
    if oracle_on:
        orA.propagate(t, tick.imu); orB.propagate(t, tick.imu)
    if ck_i < len(CK) and t >= CK[ck_i] - 1e-9:
        ck_i += 1
        n = a.nav
        e = n.pos - tick.truth.pos
        ach, gch = env.imu._accel_ch, env.imu._gyro_ch
        eb_a = n.acc_bias - (ach.turn_on_bias + ach.bias_gm); eb_g = n.gyro_bias - (gch.turn_on_bias + gch.bias_gm)
        tl, hd = tilt_heading_err(agent.eskf.C, tick.truth.att)
        if not oracle_on:
            print(f"t={t:6.1f} PRE-T0 FILTER err_h={np.hypot(e[0],e[1]):7.2f} verr_h={np.hypot(*(n.vel-tick.truth.vel)[:2]):6.3f} tilt={tl*1e3:6.2f}mrad head={np.degrees(hd):6.2f}deg "
                  f"ba_err={np.round(eb_a/9.80665*1e3,2)}mg bg_err={np.round(np.degrees(eb_g)*3600,0)}deg/h "
                  f"sig_tilt={np.round(np.sqrt(np.diag(agent.eskf.P)[6:9])*1e3,2)}mrad sig_bg={np.round(np.degrees(np.sqrt(np.diag(agent.eskf.P)[12:15]))*3600,0)}deg/h")
            continue
        P6 = agent.eskf.P[0:6, 0:6]; d6 = np.concatenate([e, n.vel - tick.truth.vel])
        nees6 = float(d6 @ np.linalg.solve(P6, d6))
        def oe(o): return float(np.hypot(*(o.p - tick.truth.pos)[:2])) if oracle_on else float("nan")
        print(f"t={t:6.1f} (T0+{t-T0:4.0f}) FILTER err_h={np.hypot(e[0],e[1]):9.1f} err_v={e[2]:9.1f} verr_h={np.hypot(*(n.vel-tick.truth.vel)[:2]):7.2f} "
              f"vz_err={(n.vel-tick.truth.vel)[2]:7.2f} tilt={tl*1e3:6.2f}mrad head={np.degrees(hd):6.2f}deg "
              f"ba_err={np.round(eb_a/9.80665*1e3,2)}mg bg_err={np.round(np.degrees(eb_g)*3600,0)}deg/h sigP_h={np.sqrt((n.cov_pos[0,0]+n.cov_pos[1,1])):8.1f} "
              f"NEES6={nees6:9.1f} | ORACLE_A(b=0) err_h={oe(orA):9.1f} ORACLE_B(b=true) err_h={oe(orB):9.1f}")
