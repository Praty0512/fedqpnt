"""Item 6(iii): E_s firing fraction on drift and meaconing attacks, using
the NEW D-058 short-baseline jump test (fedqpnt/trust/trust_law.py
TrustEngineImpl._physical_spoof_evidence). Unlike scripts/subrule_decompose_
_d056.py (which reimplements the OLD position_event logic independently and
is now stale), this reads agent.trust.last_es_evidence directly -- the
engine's own live D-056 logging side-channel, which already reflects
whatever _physical_spoof_evidence computes, so it is automatically current.

Target (D-058): low E_s firing fraction on slow drift; the short-baseline
test is specifically designed NOT to fire on a slowly dragged fix.

Not a test; run manually. Tuning seeds 500-504, 260s missions (60s onset +
180s attack + margin), method=fedqpnt (trust_law_version=v2), v2 detector
weights, kappa_R=60 (item 5's chosen value).
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
from fedqpnt.node.methods import make_agent_config, load_detector_weights

DETECTOR_WEIGHTS_V2 = ROOT / "results" / "m1" / "detector_weights_sup_v2.npz"
KAPPA_R = 60.0
SEEDS = list(range(500, 505))
DURATION_S = 260.0
ONSET_S, ATK_DUR_S = 60.0, 180.0


def run_once(seed: int, attack: dict) -> dict:
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=30.0,
                         heading_noise_deg=2.0, attacks=[attack])
    env = NodeEnvironment(env_cfg, seed=seed, node_id="es_frac", dt=0.01, duration_s=DURATION_S)
    agent_cfg = make_agent_config("fedqpnt_local", kappa_R=KAPPA_R, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True,
                                   detector_weights_path=str(DETECTOR_WEIGHTS_V2)
                                   if DETECTOR_WEIGHTS_V2.exists() else None)
    agent = Agent(agent_cfg, env.imu.config(), node_id="es_frac")

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
    print(f"=== item 6(iii): E_s firing fraction, NEW D-058 jump test, kappa_R={KAPPA_R}, "
          f"tuning seeds {SEEDS} ===\n")
    for family, attack_fn in (
        ("drift (severity=0.5, cn0_sig_scale=0.0 -- signature suppressed, pure kinematic drift)",
         lambda: dict(kind="drift_spoof", onset_s=ONSET_S, duration_s=ATK_DUR_S, severity=0.5,
                      params=dict(cn0_sig_scale=0.0))),
        ("meaconing (severity=0.6)",
         lambda: dict(kind="meaconing", onset_s=ONSET_S, duration_s=ATK_DUR_S, severity=0.6)),
    ):
        fracs, n_act_tot, n_fire_tot = [], 0, 0
        for seed in SEEDS:
            r = run_once(seed, attack_fn())
            fracs.append(r["frac"])
            n_act_tot += r["n_active"]
            n_fire_tot += r["n_fired"]
        print(f"[{family}]")
        print(f"  per-seed firing fractions: {['%.3f' % f for f in fracs]}")
        print(f"  pooled: n_active={n_act_tot} n_fired={n_fire_tot} "
              f"frac={n_fire_tot / n_act_tot if n_act_tot else float('nan'):.4f}\n")


if __name__ == "__main__":
    main()
