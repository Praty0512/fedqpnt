"""D-076 leak-exposure PROXY for H2-ABRUPT. The fleet run JSON/npz do NOT record trust state (only epoch_t/active/raw_p, scalars,
provenance), so PROBE->DISTRUST counts cannot be read from them. This replays the same live missions SINGLE-NODE closed loop
(fedqpnt_local, theta0_noabrupt_v2 as the detector, same attack config/seeds as the fleet runs; NOT the arms' final installed
models) and counts, per law (position = gnss_law, clock = clk_law), PROBE episodes and PROBE->DISTRUST (probe FAILED)
transitions, plus epochs spent in each state. One process, no fedqpnt/ edits."""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config

W = Path("results/fleet/theta0_noabrupt_v2.npz")
OUT = Path("results/fleet/h2_abrupt_leak_exposure_proxy.json")
CASES = {"abrupt_sev0.15": dict(kind="abrupt_spoof", onset_s=120.0, duration_s=300.0, severity=0.15),
         "drift_sev1.0_control": dict(kind="drift_spoof", onset_s=120.0, duration_s=300.0, severity=1.0)}


def run(seed, attack):
    env = NodeEnvironment(EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems", quantum_grade="field",
                                    gnss_rate_hz=1.0, hold_s=30.0, heading_noise_deg=2.0, attacks=[attack]),
                          seed=seed, node_id="leak", dt=0.01, duration_s=600.0)
    agent = Agent(make_agent_config("fedqpnt_local", quantum_enabled=True, world="flat", detector_weights_path=str(W)),
                  env.imu.config(), node_id="leak")
    laws = {"position": agent.trust.gnss_law, "clock": agent.trust.clk_law}
    prev = {k: "TRUST" for k in laws}
    cnt = {k: dict(probe_entries=0, probe_failed=0, probe_ok=0, epochs={"TRUST": 0, "DISTRUST": 0, "PROBE": 0}) for k in laws}
    fb, init = [], False
    for k in range(len(env)):
        tick = env.tick(k); t = tick.t
        if not init:
            if t < env.hold_s:
                if tick.imu is not None: fb.append(tick.imu.f_b)
                continue
            fm = np.mean(fb, axis=0) if fb else np.array([0, 0, 9.80665]); fx, fy, fz = fm
            agent.initialize_static(t, tick.truth.pos.copy(), np.array([np.arctan2(fy, fz), np.arctan2(-fx, np.sqrt(fy**2+fz**2)),
                                    float(tick.truth.att[2]) + env.initial_heading_noise()])); init = True; continue
        agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
        if tick.gnss_epoch is None: continue
        for name, law in laws.items():
            st = law._core_v2.state if getattr(law, "_uses_v2", False) else "TRUST"
            cnt[name]["epochs"][st] += 1
            if prev[name] != "PROBE" and st == "PROBE": cnt[name]["probe_entries"] += 1
            if prev[name] == "PROBE" and st == "DISTRUST": cnt[name]["probe_failed"] += 1
            if prev[name] == "PROBE" and st == "TRUST": cnt[name]["probe_ok"] += 1
            prev[name] = st
    return cnt


if __name__ == "__main__":
    res = {}
    for case, atk in CASES.items():
        res[case] = {}
        for seed in range(500, 510):
            res[case][seed] = run(seed, atk)
            print(case, seed, json.dumps(res[case][seed]), flush=True)
    OUT.write_text(json.dumps(res, indent=1))
