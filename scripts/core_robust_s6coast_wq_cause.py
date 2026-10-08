"""Master diagnosis: why is w_q pinned at w_min? Logs contrast, p_q, law p_bar/w/D for the first CAI epochs. Short run, no fedqpnt edits."""
import sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fedqpnt.eval import campaign as C, scenarios as SC
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config
from fedqpnt.node.agent import Agent
grade = sys.argv[1]; SEED = 530
sc = SC.get("S6-coast")
sp = C.build_spec_dict(sc, "fedqpnt_local", SEED, imu_grade=grade, duration_s=150.0, detector_weights_path="results/m1/detector_weights_sup_v3.npz")
env = NodeEnvironment(EnvConfig(platform=sp["platform"], world=sp["world"], imu_grade=grade, quantum_grade=sp["quantum_grade"],
    gnss_rate_hz=1.0, hold_s=30.0, heading_noise_deg=2.0, attacks=[]), seed=SEED, node_id="node0", dt=0.01, duration_s=150.0)
cfg = make_agent_config("fedqpnt_local", kappa_R=sp["kappa_R"], kappa_Q=1.0, world=sp["world"], quantum_enabled=True,
    detector_weights_path=sp["detector_weights_path"], imu_grade=grade, quantum_grade=sp["quantum_grade"])
agent = Agent(cfg, env.imu.config(), node_id="node0")
qt = agent.trust.quantum_trust
print("QuantumTrust: c_min", qt.c_min, "c_nom", qt.c_nom, "cycle_time_s", qt.cycle_time_s, "tau_d", qt._law.cfg.tau_d, "nis_clean_thr", qt._law.cfg.nis_clean_threshold)
orig = qt.step; rows = []
def step(t, quantum, gnss_w, quantum_innovation):
    w = orig(t, quantum, gnss_w, quantum_innovation)
    if quantum is not None:
        ct = float(np.clip((quantum.contrast - qt.c_min) / max(qt.c_nom - qt.c_min, 1e-9), 0, 1))
        rows.append((t, float(quantum.contrast), ct, 1.0 - float(quantum.valid) * ct * 1.0, qt._law.p_bar, w,
                     (quantum_innovation.nis / quantum_innovation.dof) if quantum_innovation is not None else np.nan))
    return w
qt.step = step
fb, init = [], False
for k in range(len(env)):
    tick = env.tick(k); t = tick.t
    if not init:
        if t < env.hold_s:
            if tick.imu is not None: fb.append(tick.imu.f_b)
            continue
        fm = np.mean(fb, axis=0); phi = np.arctan2(fm[1], fm[2]); th = np.arctan2(-fm[0], np.hypot(fm[1], fm[2]))
        agent.initialize_static(t, tick.truth.pos.copy(), np.array([phi, th, float(tick.truth.att[2]) + env.initial_heading_noise()])); init = True; continue
    agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
print("t contrast contrast_term p_q(pre-CUSUM) p_bar w NIS/dof")
for r in rows[:6] + rows[len(rows)//2:len(rows)//2+3] + rows[-3:]:
    print(" ".join(f"{x:.3f}" for x in r))
a = np.array(rows); print("contrast mean/min/max", a[:,1].mean(), a[:,1].min(), a[:,1].max(), " mean p_q", a[:,3].mean(), " theta_on", qt._law.cfg.theta_on)
