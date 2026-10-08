"""Master diagnosis (tuning seed only, no fedqpnt edits): per-CAI-epoch trace of the quantum update path
in fedqpnt_local on S6-coast. Mirrors fedqpnt.node.runner.run_single exactly (same spec), with read-only
wrappers around eskf.correct. Run: python scripts/core_robust_s6coast_cai_trace.py <grade> [seed] [method]"""
import sys
from pathlib import Path
import numpy as np
from scipy.stats import chi2
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fedqpnt.eval import campaign as C, scenarios as SC
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config
from fedqpnt.node.agent import Agent

grade = sys.argv[1]
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 530
method = sys.argv[3] if len(sys.argv) > 3 else "fedqpnt_local"
assert 500 <= SEED <= 599 or 9500 <= SEED <= 9699
sc = SC.get("S6-coast")
sp = C.build_spec_dict(sc, method, SEED, imu_grade=grade, detector_weights_path="results/m1/detector_weights_sup_v3.npz")
env = NodeEnvironment(EnvConfig(platform=sp["platform"], world=sp["world"], imu_grade=sp["imu_grade"],
        quantum_grade=sp["quantum_grade"], gnss_rate_hz=sp["gnss_rate_hz"], hold_s=sp["hold_s"],
        heading_noise_deg=sp["heading_noise_deg"], attacks=[sp["attack"]]),
        seed=SEED, node_id=sp["node_id"], dt=sp["dt"], duration_s=sp["duration_s"])
cfg = make_agent_config(sp["method"], kappa_R=sp["kappa_R"], kappa_Q=sp["kappa_Q"], world=sp["world"],
        quantum_enabled=True, detector_weights_path=sp["detector_weights_path"], imu_grade=grade,
        quantum_grade=sp["quantum_grade"])
agent = Agent(cfg, env.imu.config(), node_id=sp["node_id"])
eskf = agent.eskf
rec = []          # per CAI-correct call
cur = {}
orig_correct = eskf.correct
def wrapped(t, innovations, trust):
    pend = eskf._pending.get("quantum")
    row = None
    if pend is not None:
        nu, H, R_nom, dof = pend
        wq = trust.weights.get("quantum", 1.0)
        row = dict(t=t, w_q=wq, nis=float(next(iv.nis for iv in innovations if iv.sensor == "quantum")), dof=dof,
                   skipped=bool(wq < eskf.cfg.w_excl), nis_eff=np.nan, scale=1.0)
        if not row["skipped"]:
            R_eff = R_nom / max(wq, eskf.cfg.w_min)
            S_eff = H @ eskf.P @ H.T + R_eff
            ne = float(nu @ np.linalg.solve(S_eff, nu))
            g = chi2.ppf(1.0 - eskf.cfg.alpha_gate, dof)
            row["nis_eff"] = ne; row["scale"] = max(ne / g, 1.0)
        row["w_gnss"] = trust.weights.get("gnss", 1.0)
        row["tr_state"] = getattr(agent.trust.quantum_trust._law, "state", None) if agent.trust.quantum_trust else None
        cur["row"] = row
    out = orig_correct(t, innovations, trust)
    if row is not None:
        row["ba_est"] = eskf.b_a.copy()
        ch = env.imu._accel_ch
        row["ba_true"] = (ch.turn_on_bias + ch.bias_gm + ch.bias_rrw).copy()
        row["P_ba"] = np.diag(eskf.P[9:12, 9:12]).copy()
        rec.append(row)
    return out
eskf.correct = wrapped

f_b_hold, init = [], False
errs, ts, jam = [], [], []
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
    a = agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
    errs.append(float(np.linalg.norm((a.nav.pos - tick.truth.pos)[:2]))); ts.append(t); jam.append(bool(tick.label.jamming))
errs = np.array(errs); ts = np.array(ts); jam = np.array(jam)
print(f"# {grade} {method} seed={SEED} quantum_grade={sp['quantum_grade']} w_excl={eskf.cfg.w_excl} alpha_gate={eskf.cfg.alpha_gate}")
print(f"# max_h over jam window = {errs[jam].max():.2f} m ; n_CAI_epochs={len(rec)}")
R = rec
def seg(name, lo, hi):
    s = [r for r in R if lo <= r["t"] < hi]
    if not s: print(name, "none"); return
    wq = np.array([r["w_q"] for r in s]); nis = np.array([r["nis"] for r in s]); sk = np.array([r["skipped"] for r in s])
    sc_ = np.array([r["scale"] for r in s])
    print(f"{name:>14s} t[{lo:.0f},{hi:.0f}) n={len(s):4d} mean_w_q={wq.mean():.3f} min_w_q={wq.min():.3f} "
          f"frac_skipped(w_q<w_excl)={sk.mean():.3f} mean_NIS/dof={np.mean(nis)/s[0]['dof']:.2f} median_NIS={np.median(nis):.2f} "
          f"mean_softgate_scale={sc_.mean():.2f} max_scale={sc_.max():.1f}")
seg("pre-jam", 0, 600); seg("jam", 600, 780); seg("post-jam", 780, 1200)
print("t, w_q, NIS(dof), skipped, softgate_scale, w_gnss, |ba_est-ba_true| (m/s2, x/y/z), sqrt(P_ba)")
for r in R:
    if (r["t"] % 20 < 1.0 and 540 <= r["t"] <= 840) or (560 <= r["t"] <= 565) or (600 <= r["t"] <= 604) or (779 <= r["t"] <= 783):
        e = np.abs(r["ba_est"] - r["ba_true"])
        print(f"{r['t']:7.2f} {r['w_q']:.3f} {r['nis']:8.2f}({r['dof']}) {int(r['skipped'])} {r['scale']:.2f} {r['w_gnss']:.3f} "
              f"{e[0]:.4f} {e[1]:.4f} {e[2]:.4f} {np.sqrt(r['P_ba'][0]):.4f}")
