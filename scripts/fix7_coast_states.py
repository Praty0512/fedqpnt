"""FIX7 B5 diagnostic: state-level errors vs filter sigma during a pure-GNSS outage (tuning seeds). 
Usage: python scripts/fix7_coast_states.py <grade> <seed> [t_on] [--nocai]"""
import sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config
from fedqpnt.sim.rotations import euler_to_dcm
grade, seed = sys.argv[1], int(sys.argv[2]); assert seed < 10000
t_on = float(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else 60.0
cai = "--nocai" not in sys.argv
world = "schuler_tangent"
env = NodeEnvironment(EnvConfig(platform="ground", world=world, imu_grade=grade, quantum_grade="field" if cai else None,
                                gnss_rate_hz=1.0, hold_s=30.0, heading_noise_deg=2.0, attacks=[]),
                      seed=seed, node_id="n", dt=0.01, duration_s=t_on + 300.0)
cfg = make_agent_config("undefended", world=world, imu_grade=grade, quantum_grade="field" if cai else None)
ag = Agent(cfg, env.imu.config(), node_id="n")
ga, gg = env.imu._accel_ch, env.imu._gyro_ch
print(f"# {grade} seed {seed} t_on {t_on} cai {cai}; true turn-on bg [deg/h] {np.degrees(gg.turn_on_bias)*3600}  ba [mg] {ga.turn_on_bias/9.80665*1e3}")
print(f"# sf_g {(gg.scale_factor-1)*1e6} ppm; mis_g(max) {np.abs(gg.misalignment-np.eye(3)).max()*1e6:.0f} urad; sf_a {(ga.scale_factor-1)*1e6} ppm")
hold, init = [], False
marks = [0, 30, 60, 120, 180, 240, 299]
def log_rot(R):
    ang = np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))
    if ang < 1e-9: return np.zeros(3)
    return ang / (2 * np.sin(ang)) * np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
print("  +s   err_h    sig_h  | tilt_err(mrad) E,N  sig | yaw_err sig | bg_err(deg/h) E,N,U | sig_bg | ba_err(mg) E,N,U | verr_h sig_v")
for k in range(len(env)):
    tk = env.tick(k); t = tk.t
    if not init:
        if t < env.hold_s:
            if tk.imu is not None: hold.append(tk.imu.f_b)
            continue
        fx, fy, fz = np.mean(hold, axis=0)
        ag.initialize_static(t, tk.truth.pos.copy(), np.array([np.arctan2(fy, fz), np.arctan2(-fx, np.hypot(fy, fz)), float(tk.truth.att[2]) + env.initial_heading_noise()]))
        init = True; continue
    ge = tk.gnss_epoch
    if t_on <= t < t_on + 300: ge = None
    a = ag.step(t, tk.imu, tk.quantum, ge)
    off = round(t - t_on, 3)
    if off in marks:
        e = ag.eskf; P = e.P
        Ct = euler_to_dcm(tk.truth.att)
        dpsi = log_rot(e.C @ Ct.T)            # nav-frame attitude error vector (approx)
        bg_true = gg.turn_on_bias + gg.bias_gm; ba_true = ga.turn_on_bias + ga.bias_gm
        # body -> nav for bias errors
        bg_err_n = Ct @ (e.b_g - bg_true); ba_err_n = Ct @ (e.b_a - ba_true)
        ev = a.nav.vel - tk.truth.vel; ep = a.nav.pos - tk.truth.pos
        print(f"{off:5.0f} {np.hypot(*ep[:2]):8.1f} {np.sqrt((P[0,0]+P[1,1])/2):8.1f} | {dpsi[0]*1e3:7.2f} {dpsi[1]*1e3:7.2f} {np.sqrt((P[6,6]+P[7,7])/2)*1e3:6.2f} | "
              f"{dpsi[2]*1e3:7.2f} {np.sqrt(P[8,8])*1e3:6.2f} | {np.degrees(bg_err_n[0])*3600:7.1f} {np.degrees(bg_err_n[1])*3600:7.1f} {np.degrees(bg_err_n[2])*3600:7.1f} | "
              f"{np.degrees(np.sqrt((P[12,12]+P[13,13]+P[14,14])/3))*3600:6.1f} | {ba_err_n[0]/9.80665*1e3:6.2f} {ba_err_n[1]/9.80665*1e3:6.2f} {ba_err_n[2]/9.80665*1e3:6.2f} | {np.hypot(*ev[:2]):6.3f} {np.sqrt((P[3,3]+P[4,4])/2):6.3f}")
