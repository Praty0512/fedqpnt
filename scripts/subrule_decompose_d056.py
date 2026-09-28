"""D-056 step 2 follow-up: the sweep in subrule_search_d056.py found E_s
firing ~98-99% of ATTACK epochs for BOTH drift (all cn0_sig_scale in
{1,0.3,0.1,0.05,0}) and meaconing (all cn0_bump_db in {2.9,2.0,1.0} x
replay_delay_m in {300,150,75,30}), IDENTICAL to 4 decimals across every
swept value in each family -- meaning the C/N0/clock channels the sweep
targeted are NOT what is firing. This decomposes E_s into its 4 disjoint
terms (clk_event, xsat_event, cn0_event, position_event, see
trust_law.py::_physical_spoof_evidence) per attack epoch, using the SAME
live detector.normalizer state (wraps GnssFeatureExtractor.step to capture
the raw feature vector, the same technique build_supervised_dataset.py
uses) to find which term dominates and from when in the attack window.
Read-only diagnostic; no production code path changed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import load_detector_weights, make_agent_config
from fedqpnt.trust.pseudolabel import apply_sigma_floor

THETA0 = load_detector_weights(Path("results/fleet/theta0_d054.npz"))
_IDX_NIS_POS, _IDX_CN0_MEAN, _IDX_CLK_JUMP, _IDX_DRIFT_JUMP, _IDX_XSAT_CORR = 0, 3, 7, 8, 13
DURATION_S = 260.0
ONSET_S, ATK_DUR_S = 60.0, 180.0


def run_once(seed: int, attack: dict) -> dict:
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=30.0,
                         heading_noise_deg=2.0, attacks=[attack])
    env = NodeEnvironment(env_cfg, seed=seed, node_id="diag", dt=0.01, duration_s=DURATION_S)
    agent_cfg = make_agent_config("baseline_b_cont", kappa_R=40.0, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True)
    agent = Agent(agent_cfg, env.imu.config(), node_id="diag")
    agent.trust.detector.set_params({k: np.asarray(v) for k, v in THETA0.items()})
    c = agent.trust.gnss_law.cfg

    captured: list[tuple[float, np.ndarray]] = []
    orig_step = agent.trust.extractor.step

    def _wrapped(fix, innovations):
        raw = orig_step(fix, innovations)
        if raw is not None:
            captured.append((fix.t, raw.copy()))
        return raw
    agent.trust.extractor.step = _wrapped

    f_b_hold, initialized = [], False
    rows = []  # (t, active, clk, xsat, cn0, pos, w_gnss)
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
        n_before = len(captured)
        atick = agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
        active = bool(tick.label.spoofing or tick.label.jamming)
        if len(captured) > n_before and active:
            _t, raw = captured[-1]
            mu = agent.trust.detector.normalizer.mu
            sd = apply_sigma_floor(agent.trust.detector.normalizer.sd)
            clk = bool((raw[_IDX_CLK_JUMP] >= c.es_clk_sigma) or (raw[_IDX_DRIFT_JUMP] >= c.es_clk_sigma))
            xsat = bool(raw[_IDX_XSAT_CORR] > (mu[_IDX_XSAT_CORR] + c.es_xsat_quantile_z * sd[_IDX_XSAT_CORR]))
            cn0 = bool(raw[_IDX_CN0_MEAN] > (mu[_IDX_CN0_MEAN] + c.es_xsat_quantile_z * sd[_IDX_CN0_MEAN]
                                              + c.es_cn0_band_excess_db))
            pos = bool(raw[_IDX_NIS_POS] > c.position_gate_threshold)
            rows.append((t, clk, xsat, cn0, pos, atick.trust.weights.get("gnss", 1.0)))
    n = len(rows)
    if n == 0:
        return dict(n=0)
    arr = np.array([(r[1], r[2], r[3], r[4], r[5]) for r in rows], dtype=float)
    ts = np.array([r[0] for r in rows])
    any_fire = np.any(arr[:, :4] > 0, axis=1)
    first_idx = int(np.argmax(any_fire)) if any_fire.any() else -1
    return dict(n=n, clk_frac=float(arr[:, 0].mean()), xsat_frac=float(arr[:, 1].mean()),
                cn0_frac=float(arr[:, 2].mean()), pos_frac=float(arr[:, 3].mean()),
                any_frac=float(any_fire.mean()),
                first_fire_t=float(ts[first_idx]) if first_idx >= 0 else None,
                onset_t=ONSET_S, mean_w_gnss=float(arr[:, 4].mean()))


def main():
    print("=== DRIFT decomposition (sev=0.5, cn0_sig_scale=0.0) ===")
    r = run_once(500, dict(kind="drift_spoof", onset_s=ONSET_S, duration_s=ATK_DUR_S,
                           severity=0.5, params=dict(cn0_sig_scale=0.0)))
    print(r)
    print("=== MEACONING decomposition (bump=1.0, delay=30.0) ===")
    r = run_once(500, dict(kind="meaconing", onset_s=ONSET_S, duration_s=ATK_DUR_S,
                           severity=1.0, params=dict(cn0_bump_db=1.0, replay_delay_m=30.0)))
    print(r)


if __name__ == "__main__":
    main()
