"""D-067 (c): post-jam recovery summary with shadow probe / shadow-consistent reacquisition
(seed 500, jam_cw onset 120 dur 180 sev 0.5): time to TRUST after attack end, w path, post-attack error."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config

W = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results" / "m1" / "detector_weights_sup_v2.npz"
END = 300.0

def run(grade, seed=500):
    env = NodeEnvironment(EnvConfig(platform="ground", world="flat", imu_grade=grade, quantum_grade="field",
        gnss_rate_hz=1.0, hold_s=30.0, heading_noise_deg=2.0,
        attacks=[dict(kind="jam_cw", onset_s=120.0, duration_s=180.0, severity=0.5)]),
        seed=seed, node_id="jr", dt=0.01, duration_s=600.0)
    cfg = make_agent_config("fedqpnt_local", kappa_R=60.0, kappa_Q=1.0, world="flat", quantum_enabled=True,
                            detector_weights_path=str(W), imu_grade=grade)
    ag = Agent(cfg, env.imu.config(), node_id="jr")
    hold, init, rows = [], False, []
    for k in range(len(env)):
        tk = env.tick(k); t = tk.t
        if not init:
            if t < env.hold_s:
                if tk.imu is not None: hold.append(tk.imu.f_b)
                continue
            fm = np.mean(hold, axis=0); fx, fy, fz = fm
            ag.initialize_static(t, tk.truth.pos.copy(), np.array([np.arctan2(fy, fz), np.arctan2(-fx, np.hypot(fy, fz)), tk.truth.att[2] + env.initial_heading_noise()]))
            init = True; continue
        a = ag.step(t, tk.imu, tk.quantum, tk.gnss_epoch)
        if tk.gnss_epoch is not None:
            rows.append((t, ag.trust.gnss_law._core_v2.state, a.trust.weights["gnss"],
                         float(np.linalg.norm((a.nav.pos - tk.truth.pos)[:2])), a.fix is not None))
    post = [r for r in rows if r[0] >= END]
    e = np.array([r[3] for r in post])
    t_trust = next((r[0] - END for r in post if r[4] and r[1] == "TRUST" and r[2] > 0.9), float("nan"))
    t_e5 = next((r[0] - END for r in post if r[3] < 5.0), float("nan"))
    print(f"{grade}: post-attack RMSE_h={np.sqrt(np.mean(e**2)):.2f} max={e.max():.1f} time_to_TRUST&w>0.9={t_trust:.0f}s time_to_err<5m={t_e5:.0f}s")
    for r in post[:14]:
        print(f"   t={r[0]:.0f} state={r[1]} w={r[2]:.3f} err_h={r[3]:.2f} valid={int(r[4])}")

if __name__ == "__main__":
    for g in ("tactical", "industrial_mems"):
        run(g)
