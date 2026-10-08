"""Master diagnosis (tuning seed, no fedqpnt edits): S2-med @ MEMS fedqpnt_local trace -- state, w_pos, shadow NIS at probes,
detector p, E_s, error and injected offset. Run: python scripts/core_robust_s2med_trace.py <grade> [seed]"""
import sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fedqpnt.eval import campaign as C, scenarios as SC
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config
from fedqpnt.node.agent import Agent
grade = sys.argv[1]; SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 530
assert 500 <= SEED <= 599 or 9500 <= SEED <= 9699
method = sys.argv[3] if len(sys.argv) > 3 else "fedqpnt_local"
BLACKOUT = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0   # CONTROL: pure GNSS outage from this t, same filter
sc = SC.get("S2-med")
sp = C.build_spec_dict(sc, method, SEED, imu_grade=grade, detector_weights_path="results/m1/detector_weights_sup_v3.npz")
env = NodeEnvironment(EnvConfig(platform=sp["platform"], world=sp["world"], imu_grade=sp["imu_grade"],
        quantum_grade=sp["quantum_grade"], gnss_rate_hz=sp["gnss_rate_hz"], hold_s=sp["hold_s"],
        heading_noise_deg=sp["heading_noise_deg"], attacks=[sp["attack"]]),
        seed=SEED, node_id=sp["node_id"], dt=sp["dt"], duration_s=sp["duration_s"])
cfg = make_agent_config(sp["method"], kappa_R=sp["kappa_R"], kappa_Q=sp["kappa_Q"], world=sp["world"],
        quantum_enabled=sp["quantum_grade"] is not None, detector_weights_path=sp["detector_weights_path"],
        imu_grade=grade, quantum_grade=sp["quantum_grade"])
agent = Agent(cfg, env.imu.config(), node_id=sp["node_id"])
shadow = {}
orig_inn = agent.eskf.innovations
def inn(t, fix, q):
    out = orig_inn(t, fix, q)
    for iv in out:
        if iv.sensor == "gnss_shadow": shadow["nis"] = iv.nis; shadow["t"] = t
    return out
agent.eskf.innovations = inn
atk = sp["attack"]; t_on = atk["onset_s"]; t_off = t_on + atk["duration_s"]
print(f"# {grade} {method} seed={SEED} attack={atk} duration={sp['duration_s']}")
f_b_hold, init = [], False; log = []; pe = []
for k in range(len(env)):
    tick = env.tick(k); t = tick.t
    if not init:
        if t < env.hold_s:
            if tick.imu is not None: f_b_hold.append(tick.imu.f_b)
            continue
        fm = np.mean(f_b_hold, axis=0)
        phi = np.arctan2(fm[1], fm[2]); th = np.arctan2(-fm[0], np.hypot(fm[1], fm[2]))
        agent.initialize_static(t, tick.truth.pos.copy(), np.array([phi, th, float(tick.truth.att[2]) + env.initial_heading_noise()]))
        init = True; continue
    shadow.clear()
    ge = tick.gnss_epoch
    if BLACKOUT and t >= BLACKOUT: ge = None
    a = agent.step(t, tick.imu, tick.quantum, ge)
    err = float(np.linalg.norm((a.nav.pos - tick.truth.pos)[:2]))
    pe.append((t, err))
    if tick.gnss_epoch is not None:
        law = agent.trust.gnss_law._core_v2
        log.append(dict(t=t, st=law.state, w=a.trust.weights.get("gnss_pos", a.trust.weights.get("gnss", 1.0)),
                        wc=a.trust.weights.get("gnss_clk", np.nan), p=agent.trust.last_raw_p, es=agent.trust.last_es_evidence,
                        shn=shadow.get("nis", np.nan), probe=bool(getattr(a.trust, "probe_shadow", False)),
                        err=err, off=float(tick.injected_offset_m), cov=float(np.sqrt(np.trace(a.nav.cov_pos) / 3))))
pe = np.array(pe)
att = (pe[:, 0] >= t_on) & (pe[:, 0] < t_off); post = pe[:, 0] >= t_off; pre = pe[:, 0] < t_on
print(f"# rmse_pre={np.sqrt(np.mean(pe[pre,1]**2)):.2f} att: rmse={np.sqrt(np.mean(pe[att,1]**2)):.1f} max={pe[att,1].max():.1f} "
      f"post: rmse={np.sqrt(np.mean(pe[post,1]**2)):.1f} max={pe[post,1].max():.1f}")
if BLACKOUT:
    for tt in (60,70,90,120,180,200,240,300,360,450,600):
        i=int(np.argmin(abs(pe[:,0]-tt))); print(f"BLACKOUT-from-{BLACKOUT:.0f}s err_h at t={tt}: {pe[i,1]:.1f} m")
print(" t_s  state    w_pos  w_clk   p      es shadowNIS probe   err_h   offset  sqrt(P_pos)")
prev = None
for r in log:
    chg = r["st"] != prev; prev = r["st"]
    show = chg or r["probe"] or (t_on - 5 <= r["t"] <= t_on + 10) or (t_off - 3 <= r["t"] <= t_off + 15) or (r["t"] % 30 < 1.0)
    if show:
        print(f"{r['t']:6.0f} {r['st']:>8} {r['w']:.3f} {r['wc']:.3f} {(r['p'] if r['p'] is not None else float('nan')):.3f} {int(r['es'])} {r['shn']:9.2f} {int(r['probe'])} {r['err']:9.1f} {r['off']:8.1f} {r['cov']:8.1f}")
