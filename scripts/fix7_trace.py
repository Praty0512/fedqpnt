"""FIX7 diagnostic trace (TUNING seeds only). Per-GNSS-epoch log of trust state / evidence / NIS / error for any
single-node result id. Usage: python scripts/fix7_trace.py <rid e.g. S11> <grade> <seed> [method] [--every N] [--tmax T]
Prints transitions, first E_s causes, and a periodic table. Weights: results/m1/detector_weights_sup_v4.npz (raises if missing)."""
import sys, argparse
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fedqpnt.eval import campaign as C, scenarios as SC
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config
from fedqpnt.node.agent import Agent

ap = argparse.ArgumentParser()
ap.add_argument("rid"); ap.add_argument("grade"); ap.add_argument("seed", type=int)
ap.add_argument("method", nargs="?", default="fedqpnt_local")
ap.add_argument("--every", type=float, default=30.0); ap.add_argument("--tmax", type=float, default=1e9)
ap.add_argument("--noise", default=None, help="override noise_scale e.g. imu=1,gnss=5,cai_contrast_div=1")
ap.add_argument("--blackout", type=float, default=None, help="CONTROL: remove all GNSS from this t on")
ap.add_argument("--zseq", action="store_true")
ap.add_argument("--quiet", action="store_true")
ap.add_argument("--weights", default="results/m1/detector_weights_sup_v4.npz")
a = ap.parse_args()
assert a.seed < 10000
sc = SC.get(a.rid)
sp = C.build_spec_dict(sc, a.method, a.seed, imu_grade=a.grade, detector_weights_path=a.weights)
if a.noise is not None:
    sp["noise_scale"] = {k: float(v) for k, v in (kv.split("=") for kv in a.noise.split(","))} if a.noise else None
atks = list(sp.get("attacks") or ([sp["attack"]] if sp.get("attack") else []))
env = NodeEnvironment(EnvConfig(platform=sp["platform"], world=sp["world"], imu_grade=sp["imu_grade"],
        quantum_grade=sp["quantum_grade"], gnss_rate_hz=sp["gnss_rate_hz"], hold_s=sp["hold_s"],
        heading_noise_deg=sp["heading_noise_deg"], attacks=atks, noise_scale=sp.get("noise_scale")),
        seed=a.seed, node_id=sp["node_id"], dt=sp["dt"], duration_s=min(sp["duration_s"], a.tmax))
cfg = make_agent_config(sp["method"], kappa_R=sp["kappa_R"], kappa_Q=sp["kappa_Q"], world=sp["world"],
        quantum_enabled=sp["quantum_grade"] is not None, detector_weights_path=sp["detector_weights_path"],
        imu_grade=a.grade, quantum_grade=sp["quantum_grade"],
        **({} if sp.get("quantum_cycle_time_s") is None else dict(quantum_cycle_time_s=sp["quantum_cycle_time_s"])))
agent = Agent(cfg, env.imu.config(), node_id=sp["node_id"])
cap = {}
orig_inn = agent.eskf.innovations
def inn(t, fix, q):
    out = orig_inn(t, fix, q)
    for iv in out:
        if iv.sensor == "gnss_shadow":
            cap["shadow"] = iv.nis
            o_ = [0, 3, 1, 4, 2, 5]
            Sx = np.asarray(iv.S)[np.ix_(o_, o_)]; nx = np.asarray(iv.nu)[o_]
            cap["zseq"] = np.linalg.solve(np.linalg.cholesky(Sx), nx) ** 2
        if iv.sensor == "gnss": cap["nis"] = iv.nis; cap["acc"] = iv.accepted
    return out
agent.eskf.innovations = inn
orig_es = agent.trust._physical_spoof_evidence
def es(raw, fix, nav_prior, innovations, skip_position=False, split=False):
    r = orig_es(raw, fix, nav_prior, innovations, skip_position=skip_position, split=split)
    cap["es"] = r; cap["raw"] = raw.copy()
    return r
agent.trust._physical_spoof_evidence = es
print(f"# {a.rid} {a.grade} {a.method} seed={a.seed} attacks={atks} noise_scale={sp.get('noise_scale')} dur={sp['duration_s']}")
hold, init = [], False
prev = None; last_print = -1e9; ne = 0
stats = dict(n=0, st={}, es_pos=0, es_clk=0, es_xc=0, se=[], first_dist=None)
print("   t   state   w_pos  p_raw  es(pos,clk,xc)  nis6   shadow  err_h    sig_h  err_v   sig_v  | raw x1 cn0 xsat")
for k in range(len(env)):
    tk = env.tick(k); t = tk.t
    if not init:
        if t < env.hold_s:
            if tk.imu is not None: hold.append(tk.imu.f_b)
            continue
        fm = np.mean(hold, axis=0)
        agent.initialize_static(t, tk.truth.pos.copy(), np.array([np.arctan2(fm[1], fm[2]), np.arctan2(-fm[0], np.hypot(fm[1], fm[2])),
                                float(tk.truth.att[2]) + env.initial_heading_noise()]))
        init = True; continue
    cap.clear()
    ge_ = None if (a.blackout is not None and t >= a.blackout) else tk.gnss_epoch
    at = agent.step(t, tk.imu, tk.quantum, ge_)
    if ge_ is None and a.blackout is None: continue
    if a.blackout is not None and t >= a.blackout and int(t) % 1 != 0: continue
    if a.blackout is not None and ge_ is None and tk.gnss_epoch is None: continue
    law = agent.trust.gnss_law._core_v2
    if ge_ is None and a.blackout is not None and tk.gnss_epoch is not None:
        pass
    e = at.nav.pos - tk.truth.pos; ev = at.nav.vel - tk.truth.vel
    st = law.state
    row = (f"{t:6.0f} {st:>8} {at.trust.weights.get('gnss_pos',1):.3f} "
           f"{(agent.trust.last_raw_p if agent.trust.last_raw_p is not None else np.nan):.3f} "
           f"{cap.get('es')} {cap.get('nis', np.nan):8.1f} {cap.get('shadow', np.nan):9.1f} "
           f"{np.hypot(e[0], e[1]):8.1f} {np.sqrt(np.trace(at.nav.cov_pos[:2,:2])/2):8.1f} "
           f"{np.linalg.norm(ev[:2]):6.2f} {np.sqrt(np.trace(agent.eskf.P[3:5,3:5])/2):6.2f}")
    if "raw" in cap:
        row += f" | {cap['raw'][0]:.2f} {cap['raw'][3]:.1f} {cap['raw'][13]:.3f}"
    stats["n"] += 1; stats["st"][st] = stats["st"].get(st, 0) + 1
    es_t = cap.get("es")
    if isinstance(es_t, tuple):
        stats["es_pos"] += int(es_t[0]); stats["es_clk"] += int(es_t[1]); stats["es_xc"] += int(es_t[2])
    stats["se"].append(np.hypot(e[0], e[1]))
    if st != "TRUST" and stats["first_dist"] is None: stats["first_dist"] = t
    if (not a.quiet) and a.zseq and "zseq" in cap and st == "PROBE":
        row += "  zseq[pE,vE,pN,vN,pU,vU]=" + " ".join(f"{x:.1f}" for x in cap["zseq"])
    if (not a.quiet) and (st != prev or at.trust.probe_shadow or t - last_print >= a.every):
        print(row); last_print = t
    prev = st

se = np.array(stats["se"])
print(f"SUMMARY n_epochs={stats['n']} states={stats['st']} first_non_trust_t={stats['first_dist']} es_pos={stats['es_pos']} es_clk={stats['es_clk']} es_xc={stats['es_xc']} "
      f"rmse_h_epochs={np.sqrt(np.mean(se**2)):.1f} max_h={se.max():.1f} final_err_h={se[-1]:.1f}")
