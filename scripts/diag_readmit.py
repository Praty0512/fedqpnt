"""DIAG (round-2, tuning seeds only): S2-med re-admission trace. Per GNSS epoch around t_off and at each PROBE:
state, w_pos, p, p-bar, E_s, shadow NIS split into pos(3)/vel(3) parts, actual pos/vel/tilt error vs filter sigma.
Usage: python scripts/diag_readmit.py <grade> <seed> [method=fedqpnt_local] [scenario=S2-med] [worktree_root=.]
"""
import sys
from pathlib import Path
import numpy as np
import os
root = Path(os.environ.get('DIAG_ROOT') or Path(__file__).resolve().parent.parent)   # DIAG_ROOT = worktree with candidate fix
sys.path.insert(0, str(root))
from fedqpnt.eval import campaign as C, scenarios as SC
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config
from fedqpnt.node.agent import Agent
grade = sys.argv[1]; SEED = int(sys.argv[2]); assert SEED < 10000
method = sys.argv[3] if len(sys.argv) > 3 else "fedqpnt_local"
scn = sys.argv[4] if len(sys.argv) > 4 else "S2-med"
sc = SC.get(scn)
sp = C.build_spec_dict(sc, method, SEED, imu_grade=grade, detector_weights_path=str(Path("results/m1/detector_weights_sup_v4.npz").resolve()))
env = NodeEnvironment(EnvConfig(platform=sp["platform"], world=sp["world"], imu_grade=sp["imu_grade"],
        quantum_grade=sp["quantum_grade"], gnss_rate_hz=sp["gnss_rate_hz"], hold_s=sp["hold_s"],
        heading_noise_deg=sp["heading_noise_deg"], attacks=[sp["attack"]]),
        seed=SEED, node_id=sp["node_id"], dt=sp["dt"], duration_s=sp["duration_s"])
cfg = make_agent_config(sp["method"], kappa_R=sp["kappa_R"], kappa_Q=sp["kappa_Q"], world=sp["world"],
        quantum_enabled=sp["quantum_grade"] is not None, detector_weights_path=sp["detector_weights_path"],
        imu_grade=grade, quantum_grade=sp["quantum_grade"])
agent = Agent(cfg, env.imu.config(), node_id=sp["node_id"])
cap = {}
orig = agent.eskf.innovations
def inn(t, fix, q):
    out = orig(t, fix, q)
    for iv in out:
        if iv.sensor == "gnss_shadow":
            nu, S = iv.nu, iv.S
            cap.update(nis=iv.nis, nis_p=float(nu[:3] @ np.linalg.solve(S[:3, :3], nu[:3])),
                       nis_v=float(nu[3:] @ np.linalg.solve(S[3:, 3:], nu[3:])),
                       sp=float(np.sqrt(np.trace(S[:3, :3]) / 3)), sv=float(np.sqrt(np.trace(S[3:, 3:]) / 3)),
                       nu_p=float(np.linalg.norm(nu[:3])), nu_v=float(np.linalg.norm(nu[3:])))
    return out
agent.eskf.innovations = inn
atk = sp["attack"]; t_on = atk["onset_s"]; t_off = t_on + atk["duration_s"]
print(f"# {grade} {method} {scn} seed={SEED} attack={atk} bound={agent.cfg.trust.gnss_law_cfg.probe_nis_bound}")
print("   t   state  w_pos  p     pbar  es  NIS_shadow  NIS_pos  NIS_vel | |nu_p|m  |nu_v|m/s  S_pos_sig S_vel_sig | err_h  verr  probe")
f_hold, init = [], False
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
    cap.clear()
    a = agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
    if tick.gnss_epoch is None or not cap: continue
    law = agent.trust.gnss_law._core_v2 if hasattr(agent.trust.gnss_law, "_core_v2") else None
    st = law.state if law else "-"
    probe = bool(getattr(a.trust, "probe_shadow", False))
    show = (t_off - 2 <= t <= t_off + 6) or probe and (int(t) % 3 == 0) or (int(t) % 60 == 0) or (t_on <= t <= t_on + 3)
    if show:
        ev = a.nav.vel - tick.truth.vel; ep = a.nav.pos - tick.truth.pos
        print(f"{t:6.0f} {st:>8} {a.trust.weights.get('gnss_pos', 1):.3f} {agent.trust.last_raw_p or 0:.3f} {agent.trust.gnss_law.p_bar:.3f} {int(agent.trust.last_es_evidence)} "
              f"{cap['nis']:10.1f} {cap['nis_p']:9.1f} {cap['nis_v']:9.1f} | {cap['nu_p']:8.1f} {cap['nu_v']:8.2f} {cap['sp']:8.1f} {cap['sv']:8.3f} | "
              f"{np.hypot(*ep[:2]):8.1f} {np.hypot(*ev[:2]):7.2f} {int(probe)}")
