"""Master-directed diagnostic: trace jam_cw non-recovery. Per-epoch (every
tick where env emits a gnss_epoch, valid or not): t, fix.valid, w_gnss,
E_s (last_es_evidence), the d-stat and gate used inside
_physical_spoof_evidence's position term (only meaningful on a VALID fix
tick), detector raw p, horizontal error.

Not a test; run manually, one seed, kappa_R=60, v2 detector.
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

DETECTOR_WEIGHTS_V2 = ROOT / "results" / "m1" / "detector_weights_sup_v2.npz"
KAPPA_R = 60.0
SEED = 500
DURATION_S = 400.0
ONSET_S, ATK_DUR_S = 120.0, 180.0  # matches run_m1_smoke.py SCENARIOS["jam_cw"]


def main() -> None:
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=30.0,
                         heading_noise_deg=2.0,
                         attacks=[dict(kind="jam_cw", onset_s=ONSET_S, duration_s=ATK_DUR_S, severity=0.5)])
    env = NodeEnvironment(env_cfg, seed=SEED, node_id="jamtrace", dt=0.01, duration_s=DURATION_S)
    agent_cfg = make_agent_config("fedqpnt_local", kappa_R=KAPPA_R, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True,
                                   detector_weights_path=str(DETECTOR_WEIGHTS_V2)
                                   if DETECTOR_WEIGHTS_V2.exists() else None)
    agent = Agent(agent_cfg, env.imu.config(), node_id="jamtrace")

    # Instrument _physical_spoof_evidence to record d/stat/gate KEYED BY t,
    # so a later misalignment between "gnss_epoch present" ticks and
    # "fix.valid" ticks can't silently truncate the trace (the bug in the
    # first version of this script).
    dbg_by_t: dict[float, dict] = {}
    orig = agent.trust._physical_spoof_evidence

    def wrapped(raw, fix, nav_prior, innovations, skip_position=False):
        c = agent.trust.gnss_law.cfg
        p_prior = tl._p_prior_from_innovations(fix, innovations)
        d = stat = gate = None
        if (p_prior is not None and agent.trust._last_p_prior is not None
                and agent.trust._last_gnss_pos is not None and agent.trust._last_gnss_cov is not None):
            delta_ins = p_prior - agent.trust._last_p_prior
            delta_gnss = np.asarray(fix.pos, dtype=float) - agent.trust._last_gnss_pos
            d = delta_gnss - delta_ins
            cov_now = tl._spd_cov_or_fallback(fix.cov_pos)
            cov_ins_short = (c.es_ins_short_sigma_pos ** 2) * np.eye(3)
            S_d = cov_now + agent.trust._last_gnss_cov + cov_ins_short
            stat = float(d @ np.linalg.solve(S_d, d))
            gate = float(chi2.ppf(c.es_position_gate_quantile, 3))
        r = orig(raw, fix, nav_prior, innovations, skip_position=skip_position)
        dbg_by_t[round(fix.t, 3)] = dict(d_norm=float(np.linalg.norm(d)) if d is not None else float("nan"),
                                          stat=stat if stat is not None else float("nan"),
                                          gate=gate if gate is not None else float("nan"))
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
            fix_valid = atick.fix is not None and atick.fix.valid
            log.append(dict(t=t, valid=fix_valid, w_gnss=atick.trust.weights.get("gnss", 1.0),
                             raw_p=agent.trust.last_raw_p, es=agent.trust.last_es_evidence,
                             err_h=err_h, active=bool(tick.label.spoofing or tick.label.jamming)))

    print(f"{'t':>7} {'valid':>5} {'active':>6} {'w_gnss':>8} {'raw_p':>8} {'es':>4} {'err_h':>10} "
          f"{'d_norm':>10} {'stat':>10} {'gate':>8}")
    for row in log:
        dbg = dbg_by_t.get(round(row["t"], 3), {})
        d_norm = dbg.get("d_norm", float("nan"))
        stat = dbg.get("stat", float("nan"))
        gate = dbg.get("gate", float("nan"))
        rawp = row["raw_p"] if row["raw_p"] is not None else float("nan")
        print(f"{row['t']:7.1f} {int(row['valid']):5d} {int(row['active']):6d} {row['w_gnss']:8.4f} "
              f"{rawp:8.4f} {int(row['es']):4d} {row['err_h']:10.3f} {d_norm:10.3f} {stat:10.2f} {gate:8.2f}")


if __name__ == "__main__":
    main()
