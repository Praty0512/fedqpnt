import sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scipy.stats import chi2
from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config
grade = sys.argv[1]; dur = float(sys.argv[2]) if len(sys.argv) > 2 else 150.0
env = NodeEnvironment(EnvConfig(platform="ground", world="flat", imu_grade=grade, quantum_grade="field", gnss_rate_hz=1.0,
        hold_s=30.0, heading_noise_deg=2.0, attacks=[]), seed=530, node_id="n", dt=0.01, duration_s=dur)
agent = Agent(make_agent_config("fedqpnt_local", world="flat", quantum_enabled=True, imu_grade=grade, quantum_grade="field"),
              env.imu.config(), node_id="n")
qt = agent.trust.quantum_trust; print("c_min,c_nom", qt.c_min, qt.c_nom)
orig = qt.step; rows = []
def step(t, q, gnss_w=1.0, quantum_innovation=None):
    qi = quantum_innovation
    w = orig(t, q, gnss_w=gnss_w, quantum_innovation=qi)
    if q is not None:
        ct = float(np.clip((q.contrast - qt.c_min) / (qt.c_nom - qt.c_min), 0, 1))
        ok_hi = True if qi is None else qi.nis <= chi2.ppf(qt.nis_quantile, max(qi.dof, 1))
        ok_clean = True if qi is None else qi.nis / max(qi.dof, 1) <= qt._law.cfg.nis_clean_threshold
        rows.append((t, q.contrast, bool(q.valid), 1 - float(q.valid) * ct * float(ok_hi), qt._splus, qt._sminus, ok_clean, qt._law.p_bar, w))
    return w
qt.step = step
fb, init = [], False
for k in range(len(env)):
    tick = env.tick(k)
    if not init:
        if tick.t < env.hold_s:
            if tick.imu is not None: fb.append(tick.imu.f_b)
            continue
        fm = np.mean(fb, axis=0)
        agent.initialize_static(tick.t, tick.truth.pos.copy(), np.array([np.arctan2(fm[1], fm[2]), np.arctan2(-fm[0], np.hypot(fm[1], fm[2])), float(tick.truth.att[2]) + env.initial_heading_noise()])); init = True; continue
    agent.step(tick.t, tick.imu, tick.quantum, tick.gnss_epoch)
a = np.array(rows, float)
print("t contrast valid p_q splus sminus ok_clean p_bar w")
for r in rows[:: max(1, len(rows)//40)]: print(" ".join(f"{float(x):.3f}" for x in r))
print("frac p_q>0.6", (a[:,3]>0.6).mean(), "frac ok_clean false", (a[:,6]==0).mean(), "max splus", a[:,4].max(), "max sminus", a[:,5].max(), "frac invalid", (a[:,2]==0).mean())
