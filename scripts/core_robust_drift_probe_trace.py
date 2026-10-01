"""Master-directed diagnostic (Q2/Q3): generalized per-epoch trace for
meaconing/drift_spoof (and jam_cw, reusing the same harness as
core_robust_jam_recovery_trace.py). Logs: t, fix.valid, w_gnss, E_s,
E_s's d-norm/stat/gate, detector raw p, raw features x1 (nis_pos), x8
(clk_jump), x9 (drift_jump), horizontal error, and the GNSS position
INNOVATION norm (nu_pos, nominal-R, pre-correction) to separate "the GNSS
fix itself is bad" from "the fix is fine but de-weighted".

Not a test; run manually: python scripts/core_robust_attack_trace.py <kind>
where <kind> in {meaconing, drift_spoof, jam_cw}.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.stats import chi2

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config
from fedqpnt.trust import trust_law as tl

DETECTOR_WEIGHTS_V2 = (Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "results" / "m1" / "detector_weights_sup_v2.npz")
KAPPA_R = 60.0
SEED = 500
DURATION_S = 600.0
ONSET_S, ATK_DUR_S, SEVERITY = 120.0, 180.0, 0.5


def main(kind: str) -> None:
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="tactical",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=30.0,
                         heading_noise_deg=2.0,
                         attacks=[dict(kind=kind, onset_s=ONSET_S, duration_s=ATK_DUR_S, severity=SEVERITY)])
    env = NodeEnvironment(env_cfg, seed=SEED, node_id="atktrace", dt=0.01, duration_s=DURATION_S)
    agent_cfg = make_agent_config("fedqpnt_local", kappa_R=KAPPA_R, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True,
                                   detector_weights_path=str(DETECTOR_WEIGHTS_V2)
                                   if DETECTOR_WEIGHTS_V2.exists() else None)
    agent = Agent(agent_cfg, env.imu.config(), node_id="atktrace")

    dbg_by_t: dict[float, dict] = {}
    orig = agent.trust._physical_spoof_evidence

    def wrapped(raw, fix, nav_prior, innovations, skip_position=False, split=False):
        c = agent.trust.gnss_law.cfg
        p_prior = tl._p_prior_from_innovations(fix, innovations)
        d = stat = gate = None
        if (not skip_position and p_prior is not None and agent.trust._last_p_prior is not None
                and agent.trust._last_gnss_pos is not None and agent.trust._last_gnss_cov is not None):
            delta_ins = p_prior - agent.trust._last_p_prior
            delta_gnss = np.asarray(fix.pos, dtype=float) - agent.trust._last_gnss_pos
            d = delta_gnss - delta_ins
            cov_now = tl._spd_cov_or_fallback(fix.cov_pos)
            cov_ins_short = (c.es_ins_short_sigma_pos ** 2) * np.eye(3)
            S_d = cov_now + agent.trust._last_gnss_cov + cov_ins_short
            stat = float(d @ np.linalg.solve(S_d, d))
            gate = float(chi2.ppf(c.es_position_gate_quantile, 3))
        r = orig(raw, fix, nav_prior, innovations, skip_position=skip_position, split=split)
        dbg_by_t[round(fix.t, 3)] = dict(d_norm=float(np.linalg.norm(d)) if d is not None else float("nan"),
                                          stat=stat if stat is not None else float("nan"),
                                          gate=gate if gate is not None else float("nan"),
                                          x1=float(raw[0]), x8=float(raw[7]), x9=float(raw[8]))
        return r
    agent.trust._physical_spoof_evidence = wrapped

    f_b_hold, initialized = [], False
    log = []
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
        if tick.gnss_epoch is not None:
            err_h = float(np.linalg.norm((atick.nav.pos - tick.truth.pos)[:2]))
            fix_valid = atick.fix is not None
            # nu_pos norm from the RAW (nominal-R, pre-correction) gnss_pos
            # innovation -- separates "GNSS fix itself is off" from
            # "GNSS fix is fine but de-weighted".
            spoof_off = float(np.linalg.norm((atick.fix.pos - tick.truth.pos)[:2])) if atick.fix is not None else float("nan")
            st = agent.trust.gnss_law._core_v2.state
            log.append(dict(t=t, st=st, spoof_off=spoof_off, valid=fix_valid, w_gnss=atick.trust.weights.get("gnss", 1.0),
                             raw_p=agent.trust.last_raw_p, es=agent.trust.last_es_evidence,
                             err_h=err_h, active=bool(tick.label.spoofing or tick.label.jamming)))

    print(f"{'t':>7} {'state':>8} {'spoofoff':>9} {'valid':>5} {'active':>6} {'w_gnss':>8} {'raw_p':>8} {'es':>4} {'err_h':>10} "
          f"{'d_norm':>9} {'stat':>9} {'x1_nis':>8} {'x8_clk':>8} {'x9_drft':>8}")
    for row in log:
        dbg = dbg_by_t.get(round(row["t"], 3), {})
        rawp = row["raw_p"] if row["raw_p"] is not None else float("nan")
        print(f"{row['t']:7.1f} {row['st']:>8} {row['spoof_off']:9.2f} {int(row['valid']):5d} {int(row['active']):6d} {row['w_gnss']:8.4f} "
              f"{rawp:8.4f} {int(row['es']):4d} {row['err_h']:10.3f} "
              f"{dbg.get('d_norm', float('nan')):9.3f} {dbg.get('stat', float('nan')):9.2f} "
              f"{dbg.get('x1', float('nan')):8.3f} {dbg.get('x8', float('nan')):8.3f} "
              f"{dbg.get('x9', float('nan')):8.3f}")


if __name__ == "__main__":
    kind = sys.argv[1] if len(sys.argv) > 1 else "meaconing"
    main(kind)
