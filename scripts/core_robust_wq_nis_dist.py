import sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scipy.stats import chi2
from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config
grade = sys.argv[1]; dur = float(sys.argv[2]); seed = int(sys.argv[3]) if len(sys.argv) > 3 else 530
env = NodeEnvironment(EnvConfig(platform="ground", world="flat", imu_grade=grade, quantum_grade="field", gnss_rate_hz=1.0,
        hold_s=30.0, heading_noise_deg=2.0, attacks=[]), seed=seed, node_id="n", dt=0.01, duration_s=dur)
agent = Agent(make_agent_config("fedqpnt_local", world="flat", quantum_enabled=True, imu_grade=grade, quantum_grade="field"), env.imu.config(), node_id="n")
rows = []; orig = agent.eskf.innovations
def inn(t, fix, q):
    out = orig(t, fix, q)
    for iv in out:
        if iv.sensor == "quantum":
            rows.append((t, iv.nis, *iv.nu, *np.sqrt(np.diag(iv.S)), *np.sqrt(np.diag(agent.eskf.P[9:12, 9:12]))))
    return out
agent.eskf.innovations = inn
fb, init = [], False; wq = []
for k in range(len(env)):
    tick = env.tick(k)
    if not init:
        if tick.t < env.hold_s:
            if tick.imu is not None: fb.append(tick.imu.f_b)
            continue
        fm = np.mean(fb, axis=0)
        agent.initialize_static(tick.t, tick.truth.pos.copy(), np.array([np.arctan2(fm[1], fm[2]), np.arctan2(-fm[0], np.hypot(fm[1], fm[2])), float(tick.truth.att[2]) + env.initial_heading_noise()])); init = True; continue
    a = agent.step(tick.t, tick.imu, tick.quantum, tick.gnss_epoch)
    if tick.quantum is not None: wq.append(a.trust.weights["quantum"])
r = np.array(rows); nis = r[:, 1]
print(f"{grade} seed {seed} n={len(r)} mean NIS/3={nis.mean()/3:.2f} median NIS={np.median(nis):.2f} (chi2_3 median {chi2.ppf(.5,3):.2f})")
print("frac NIS/3 > chi2_3(.95)/3:", (nis/3 > chi2.ppf(.95,3)/3).mean(), " frac NIS > chi2_3(.999):", (nis > chi2.ppf(.999,3)).mean())
print("nu rms per axis", np.sqrt((r[:,2:5]**2).mean(0)), "sqrt(S) per axis mean", r[:,5:8].mean(0), "sqrt(P_ba)", r[:,8:11].mean(0))
print("mean w_q", np.mean(wq), "frac w_q>=0.05", np.mean(np.array(wq)>=0.05))
