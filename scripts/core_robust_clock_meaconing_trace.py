"""Master-directed diagnostic (D-063 task B): trace ClockKF under meaconing.
Logs per-epoch: t, w_gnss, fix.clk_bias (raw, contaminated by the replay
delay when active), ClockKF's own bias/drift estimate, the TRUE clock bias
(read from truth, evaluator-only channel -- this script may import it since
it's test/diagnostic code, not fedqpnt/), and the resulting |error| in ns.
Also reports whole-mission vs attack-window-only vs post-attack-only RMSE_t
to see WHERE the 1.3us error actually accumulates, plus a nominal
(no-attack) control run for reference.

Not a test; run manually: python scripts/core_robust_clock_meaconing_trace.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config

C_LIGHT = 299_792_458.0
DETECTOR_WEIGHTS_V2 = ROOT / "results" / "m1" / "detector_weights_sup_v2.npz"
KAPPA_R = 60.0
SEED = 500
DURATION_S = 600.0
ONSET_S, ATK_DUR_S, SEVERITY = 120.0, 180.0, 0.5


def run_one(method: str, attack: dict | None) -> dict:
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=30.0,
                         heading_noise_deg=2.0, attacks=[attack] if attack else [])
    env = NodeEnvironment(env_cfg, seed=SEED, node_id="clktrace", dt=0.01, duration_s=DURATION_S)
    agent_cfg = make_agent_config(method, kappa_R=KAPPA_R, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True,
                                   detector_weights_path=str(DETECTOR_WEIGHTS_V2)
                                   if DETECTOR_WEIGHTS_V2.exists() else None)
    agent = Agent(agent_cfg, env.imu.config(), node_id="clktrace")

    f_b_hold, initialized = [], False
    rows = []
    for k in range(len(env)):
        tick = env.tick(k)
        t = tick.t
        if not initialized:
            if t < env.hold_s:
                if tick.imu is not None:
                    f_b_hold.append(tick.imu.f_b)
                continue
            f_mean = np.mean(f_b_hold, axis=0) if f_b_hold else np.array([0.0, 0.0, 9.80665])
            fx, fy, fz = f_mean
            phi0 = float(np.arctan2(fy, fz))
            theta0 = float(np.arctan2(-fx, np.sqrt(fy ** 2 + fz ** 2)))
            psi0 = float(tick.truth.att[2]) + env.initial_heading_noise()
            agent.initialize_static(t, tick.truth.pos.copy(), np.array([phi0, theta0, psi0]))
            initialized = True
            continue
        atick = agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
        if atick.clock is not None and tick.gnss_epoch is not None:
            err_ns = abs(atick.clock.bias_m - tick.true_clk_bias_m) / C_LIGHT * 1e9
            active = bool(tick.label.spoofing or tick.label.jamming)
            fix_clk_bias = atick.fix.clk_bias if atick.fix is not None else float("nan")
            rows.append(dict(t=t, w=atick.trust.weights.get("gnss", 1.0), err_ns=err_ns,
                              est_bias=atick.clock.bias_m, est_drift=atick.clock.drift_mps,
                              true_bias=tick.true_clk_bias_m, fix_clk_bias=fix_clk_bias, active=active))
    return dict(rows=rows)


def _rmse(vals):
    a = np.array(vals)
    return float(np.sqrt(np.mean(a ** 2))) if len(a) else float("nan")


def main() -> None:
    meaconing = dict(kind="meaconing", onset_s=ONSET_S, duration_s=ATK_DUR_S, severity=SEVERITY)
    print("=== D-063 task B: ClockKF under meaconing, seed 500, kappa_R=60 ===\n")
    for method in ("fedqpnt_local", "undefended"):
        r_nominal = run_one(method, None)
        r_meacon = run_one(method, meaconing)

        rows_m = r_meacon["rows"]
        whole = _rmse([x["err_ns"] for x in rows_m])
        att = _rmse([x["err_ns"] for x in rows_m if ONSET_S <= x["t"] < ONSET_S + ATK_DUR_S])
        post = _rmse([x["err_ns"] for x in rows_m if x["t"] >= ONSET_S + ATK_DUR_S])
        pre = _rmse([x["err_ns"] for x in rows_m if x["t"] < ONSET_S])
        nominal_whole = _rmse([x["err_ns"] for x in r_nominal["rows"]])

        print(f"[{method}]")
        print(f"  nominal (no attack) whole-mission RMSE_t = {nominal_whole:.1f} ns")
        print(f"  meaconing run: pre={pre:.1f}ns  attack-window={att:.1f}ns  post={post:.1f}ns  "
              f"whole-mission={whole:.1f}ns")
        # print a few rows spanning onset to see the fix.clk_bias jump and w response
        onset_rows = [x for x in rows_m if ONSET_S - 2 <= x["t"] <= ONSET_S + 8]
        for x in onset_rows:
            print(f"    t={x['t']:6.1f} w={x['w']:7.4f} active={int(x['active'])} "
                  f"fix.clk_bias={x['fix_clk_bias']:10.3f} est_bias={x['est_bias']:10.3f} "
                  f"true_bias={x['true_bias']:10.3f} err_ns={x['err_ns']:8.1f}")
        print()


if __name__ == "__main__":
    main()
