"""D-056 step 2: find sub-rule parameters (E_s fires <=5% of attack epochs)
for drift and meaconing, WITHOUT running the full fleet machinery (this is
a single-node, no-FL diagnostic -- cheap). Sweeps cn0_sig_scale for drift
(at severity s in {0.5,0.75}) and replay_delay_m/cn0_bump_db for meaconing.
Uses the same theta0 (D-054, restricted family set) so the E_s normalizer
reference (detector.normalizer) matches what H2/H4 will actually use.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import load_detector_weights, make_agent_config

THETA0 = load_detector_weights(Path("results/fleet/theta0_d054.npz"))
DURATION_S = 260.0
ONSET_S = 60.0
ATK_DUR_S = 180.0


def run_once(seed: int, attack: dict) -> dict:
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=30.0,
                         heading_noise_deg=2.0, attacks=[attack])
    env = NodeEnvironment(env_cfg, seed=seed, node_id="diag", dt=0.01, duration_s=DURATION_S)
    agent_cfg = make_agent_config("baseline_b_cont", kappa_R=40.0, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True)
    agent = Agent(agent_cfg, env.imu.config(), node_id="diag")
    agent.trust.detector.set_params({k: np.asarray(v) for k, v in THETA0.items()})

    f_b_hold, initialized = [], False
    n_attack_epochs, n_es_fired = 0, 0
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
            theta0_ = float(np.arctan2(-fx, np.sqrt(fy ** 2 + fz ** 2)))
            psi0 = float(tick.truth.att[2]) + env.initial_heading_noise()
            agent.initialize_static(t, tick.truth.pos.copy(), np.array([phi0, theta0_, psi0]))
            initialized = True
            continue
        atick = agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
        active = bool(tick.label.spoofing or tick.label.jamming)
        if active:
            n_attack_epochs += 1
            if agent.trust.last_es_evidence:
                n_es_fired += 1
    frac = (n_es_fired / n_attack_epochs) if n_attack_epochs else float("nan")
    return dict(n_attack_epochs=n_attack_epochs, es_fire_frac=frac)


def main():
    print("=== DRIFT sweep (severity x cn0_sig_scale) ===")
    for sev in (0.5, 0.75):
        for scale in (1.0, 0.3, 0.1, 0.05, 0.0):
            attack = dict(kind="drift_spoof", onset_s=ONSET_S, duration_s=ATK_DUR_S,
                          severity=sev, params=dict(cn0_sig_scale=scale))
            res = run_once(500, attack)
            print(f"drift sev={sev} cn0_sig_scale={scale}: n_att={res['n_attack_epochs']} "
                  f"es_frac={res['es_fire_frac']:.4f}")

    print("=== MEACONING sweep (cn0_bump_db x replay_delay_m) ===")
    for bump in (2.9, 2.0, 1.0):
        for delay in (300.0, 150.0, 75.0, 30.0):
            attack = dict(kind="meaconing", onset_s=ONSET_S, duration_s=ATK_DUR_S,
                          severity=1.0, params=dict(cn0_bump_db=bump, replay_delay_m=delay))
            res = run_once(500, attack)
            print(f"meaconing bump={bump} delay={delay}: n_att={res['n_attack_epochs']} "
                  f"es_frac={res['es_fire_frac']:.4f}")


if __name__ == "__main__":
    main()
