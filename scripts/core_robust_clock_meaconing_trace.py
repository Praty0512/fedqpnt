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
DETECTOR_WEIGHTS_V2 = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results" / "m1" / "detector_weights_sup_v2.npz"
GRADE = sys.argv[2] if len(sys.argv) > 2 else "industrial_mems"
KAPPA_R = 60.0
SEED = 500
DURATION_S = 600.0
ONSET_S, ATK_DUR_S, SEVERITY = 120.0, 180.0, 0.5


def run_one(method: str, attack: dict | None, seed: int = SEED) -> dict:
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade=GRADE,
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=30.0,
                         heading_noise_deg=2.0, attacks=[attack] if attack else [])
    env = NodeEnvironment(env_cfg, seed=seed, node_id="clktrace", dt=0.01, duration_s=DURATION_S)
    agent_cfg = make_agent_config(method, kappa_R=KAPPA_R, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True, imu_grade=GRADE,
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
    seeds = [500, 501, 502, 503, 504]
    print(f"=== meaconing timing (clock bias RMSE, ns), grade={GRADE}, seeds {seeds}, weights={DETECTOR_WEIGHTS_V2} ===")
    for method in ("fedqpnt_local", "undefended"):
        acc = {k: [] for k in ("nominal", "pre", "att", "post", "whole")}
        for sd in seeds:
            rows = run_one(method, meaconing, sd)["rows"]
            acc["whole"].append(_rmse([x["err_ns"] for x in rows]))
            acc["att"].append(_rmse([x["err_ns"] for x in rows if ONSET_S <= x["t"] < ONSET_S + ATK_DUR_S]))
            acc["post"].append(_rmse([x["err_ns"] for x in rows if x["t"] >= ONSET_S + ATK_DUR_S]))
            acc["pre"].append(_rmse([x["err_ns"] for x in rows if x["t"] < ONSET_S]))
            acc["nominal"].append(_rmse([x["err_ns"] for x in run_one(method, None, sd)["rows"]]))
        print(f"[{method}] " + "  ".join(f"{k}={np.mean(v):.1f}ns" for k, v in acc.items()) +
              "   per-seed att=" + str([round(v, 1) for v in acc["att"]]), flush=True)


if __name__ == "__main__":
    main()
