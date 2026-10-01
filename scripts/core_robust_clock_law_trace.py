"""Diagnosis (D-076-era, no fedqpnt/ edits): per-epoch trace of the CLOCK trust path under meaconing, seed 500.
Columns: t, w_clk, w_pos, clock-law state (and shadow), clk_event/xsat_cn0/position evidence, x8, x9, detector p,
fix.clk_bias, ClockKF bias estimate, true clock bias, |error| ns.
Usage: python scripts/core_robust_clock_law_trace.py <weights.npz> <grade> [method]
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

C_LIGHT = 299_792_458.0
W = Path(sys.argv[1]); GRADE = sys.argv[2]; METHOD = sys.argv[3] if len(sys.argv) > 3 else "fedqpnt_local"
ONSET, DUR = 120.0, 180.0

env = NodeEnvironment(EnvConfig(platform="ground", world="flat", imu_grade=GRADE, quantum_grade="field",
    gnss_rate_hz=1.0, hold_s=30.0, heading_noise_deg=2.0,
    attacks=[dict(kind="meaconing", onset_s=ONSET, duration_s=DUR, severity=0.5)]),
    seed=500, node_id="cl", dt=0.01, duration_s=400.0)
cfg = make_agent_config(METHOD, kappa_R=60.0, world="flat", quantum_enabled=True, imu_grade=GRADE,
                        detector_weights_path=str(W), quantum_grade="field")
ag = Agent(cfg, env.imu.config(), node_id="cl")
cap = {}
orig_ev = ag.trust._physical_spoof_evidence
def ev(raw, fix, nav_prior, innovations, skip_position=False, split=False):
    r = orig_ev(raw, fix, nav_prior, innovations, skip_position=skip_position, split=split)
    cap["ev"] = r; cap["x8"], cap["x9"] = float(raw[7]), float(raw[8]); return r
ag.trust._physical_spoof_evidence = ev
hold, init = [], False
print(f"{'t':>6} {'w_clk':>7} {'w_pos':>7} {'clkSt':>8} {'shd':>3} {'pos':>3} {'clk':>3} {'xc':>3} {'x8':>8} {'x9':>7} {'p':>6} {'fixclk':>9} {'estb':>9} {'trueb':>9} {'err_ns':>8}")
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
    if tk.gnss_epoch is None or a.clock is None:
        continue
    ev_ = cap.get("ev", (False, False, False))
    err = abs(a.clock.bias_m - tk.true_clk_bias_m) / C_LIGHT * 1e9
    fixclk = a.fix.clk_bias if a.fix is not None else float("nan")
    if t < ONSET - 3 or t > ONSET + DUR + 40:
        if int(t) % 20: continue
    print(f"{t:6.1f} {a.trust.weights['gnss_clk']:7.4f} {a.trust.weights['gnss_pos']:7.4f} "
          f"{ag.trust.clk_law._core_v2.state:>8} {int(a.trust.clk_probe_shadow):3d} {int(ev_[0]):3d} {int(ev_[1]):3d} "
          f"{int(ev_[2]):3d} {cap.get('x8', float('nan')):8.2f} {cap.get('x9', float('nan')):7.2f} "
          f"{(ag.trust.last_raw_p if ag.trust.last_raw_p is not None else float('nan')):6.3f} {fixclk:9.2f} "
          f"{a.clock.bias_m:9.2f} {tk.true_clk_bias_m:9.2f} {err:8.1f}")
