"""H2-ABRUPT step 2: verify E_s stays quiet on abrupt under the CURRENT core
(D-058 short-baseline jump test, post CORE-ROBUST's nav_prior bug fix).
Mirrors scripts/core_robust_es_firing_fraction.py's single-node pattern
(reads agent.trust.last_es_evidence directly -- no reimplementation of the
jump-test math) but for the 'abrupt_spoof' family across a range of
severities/step sizes, tuning seeds 500-504.

Target: es_fire_frac_attack <= 5% (task threshold). If the CONTROL_ATTACK
severity used by h2_h4_subrule_d056.py (0.6) now fires above target (the new
jump test is designed to catch abrupt jumps), sweep severity downward to find
a value below threshold; if none exists below the point where the attack
also becomes essentially undetectable, report that.
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

KAPPA_R = 60.0
SEEDS = list(range(500, 505))
DURATION_S = 260.0
ONSET_S, ATK_DUR_S = 60.0, 180.0
SEVERITIES = [0.15]  # bisecting between 0.2 (9.8% fire, FAIL) and 0.1 (0% fire, PASS)


def run_once(seed: int, attack: dict) -> dict:
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=30.0,
                         heading_noise_deg=2.0, attacks=[attack])
    env = NodeEnvironment(env_cfg, seed=seed, node_id="es_frac_abrupt", dt=0.01, duration_s=DURATION_S)
    agent_cfg = make_agent_config("fedqpnt_local", kappa_R=KAPPA_R, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True, detector_weights_path=None)
    agent = Agent(agent_cfg, env.imu.config(), node_id="es_frac_abrupt")

    f_b_hold, initialized = [], False
    n_active, n_fired = 0, 0
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
        agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
        active = bool(tick.label.spoofing or tick.label.jamming)
        if active and tick.gnss_epoch is not None:
            n_active += 1
            if agent.trust.last_es_evidence:
                n_fired += 1
    return dict(n_active=n_active, n_fired=n_fired,
                frac=(n_fired / n_active if n_active else float("nan")))


def main() -> None:
    print(f"=== H2-ABRUPT step 2: E_s firing fraction on abrupt_spoof, current core, "
          f"kappa_R={KAPPA_R}, seeds {SEEDS} ===\n")
    for severity in SEVERITIES:
        fracs, n_act_tot, n_fire_tot = [], 0, 0
        for seed in SEEDS:
            attack = dict(kind="abrupt_spoof", onset_s=ONSET_S, duration_s=ATK_DUR_S, severity=severity)
            r = run_once(seed, attack)
            fracs.append(r["frac"])
            n_act_tot += r["n_active"]
            n_fire_tot += r["n_fired"]
        pooled = n_fire_tot / n_act_tot if n_act_tot else float("nan")
        print(f"[abrupt_spoof severity={severity}]")
        print(f"  per-seed firing fractions: {['%.3f' % f for f in fracs]}")
        print(f"  pooled: n_active={n_act_tot} n_fired={n_fire_tot} frac={pooled:.4f}")
        print(f"  PASS(<=5%)={pooled <= 0.05}\n")


if __name__ == "__main__":
    main()
