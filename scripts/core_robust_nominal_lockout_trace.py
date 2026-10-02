"""Diagnosis: clean nominal mission (no attack) where fedqpnt_local diverges (seed 9604 in the decisive safety_nominal group).
Prints law-state transitions and, per probe/epoch around them, w_pos/w_clk, E_s flags, detector p, shadow NIS and err_h.
Usage: python scripts/core_robust_nominal_lockout_trace.py <weights> <grade> [seed] [method]
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config

W = Path(sys.argv[1]); GRADE = sys.argv[2]; SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 9604
METHOD = sys.argv[4] if len(sys.argv) > 4 else "fedqpnt_local"
env = NodeEnvironment(EnvConfig(platform="ground", world="flat", imu_grade=GRADE, quantum_grade="field", gnss_rate_hz=1.0,
    hold_s=30.0, heading_noise_deg=2.0, attacks=[]), seed=SEED, node_id="node0", dt=0.01, duration_s=600.0)
cfg = make_agent_config(METHOD, kappa_R=60.0, world="flat", quantum_enabled=True, imu_grade=GRADE,
                        detector_weights_path=str(W), quantum_grade="field")
ag = Agent(cfg, env.imu.config(), node_id="node0")
cap = {}
orig = ag.trust._physical_spoof_evidence
def ev(raw, fix, nav_prior, innovations, skip_position=False, split=False):
    r = orig(raw, fix, nav_prior, innovations, skip_position=skip_position, split=split)
    cap["ev"] = r; cap["x"] = (float(raw[0]), float(raw[7]), float(raw[8])); return r
ag.trust._physical_spoof_evidence = ev
orig_innov = ag.eskf.innovations
def innov(t, fix, q):
    out = orig_innov(t, fix, q)
    sh = next((i for i in out if i.sensor == "gnss_shadow"), None)
    cap["shadow"] = float(sh.nis) if sh is not None else float("nan")
    return out
ag.eskf.innovations = innov
hold, init = [], False
prev = None
print(f"{'t':>6} {'posSt':>8} {'clkSt':>8} {'w_pos':>6} {'w_clk':>6} {'pos':>3} {'clk':>3} {'xc':>3} {'p':>6} {'shadowNIS':>10} {'x1':>7} {'x8':>7} {'x9':>6} {'err_h':>9}")
for k in range(len(env)):
    tk = env.tick(k); t = tk.t
    if not init:
        if t < env.hold_s:
            if tk.imu is not None: hold.append(tk.imu.f_b)
            continue
        fx, fy, fz = np.mean(hold, axis=0)
        ag.initialize_static(t, tk.truth.pos.copy(), np.array([np.arctan2(fy, fz), np.arctan2(-fx, np.hypot(fy, fz)),
                             float(tk.truth.att[2]) + env.initial_heading_noise()]))
        init = True; continue
    cap.clear()
    a = ag.step(t, tk.imu, tk.quantum, tk.gnss_epoch)
    if tk.gnss_epoch is None or a.fix is None:
        continue
    ps, cs = ag.trust.gnss_law._core_v2.state, ag.trust.clk_law._core_v2.state
    err = float(np.linalg.norm((a.nav.pos - tk.truth.pos)[:2]))
    ev_ = cap.get("ev", (False, False, False)); x = cap.get("x", (np.nan,) * 3)
    changed = (ps, cs) != prev
    if changed or int(t) % 25 == 0:
        print(f"{t:6.1f} {ps:>8} {cs:>8} {a.trust.weights['gnss_pos']:6.3f} {a.trust.weights['gnss_clk']:6.3f} {int(ev_[0]):3d} {int(ev_[1]):3d} {int(ev_[2]):3d} "
              f"{(ag.trust.last_raw_p if ag.trust.last_raw_p is not None else np.nan):6.3f} {cap.get('shadow', np.nan):10.2f} {x[0]:7.2f} {x[1]:7.2f} {x[2]:6.2f} {err:9.1f}")
    prev = (ps, cs)
