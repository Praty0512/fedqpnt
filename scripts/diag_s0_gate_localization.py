"""D-055 diagnostic (Master, requested, no code changes): localise WHY
FedQPNT is 21.9x worse than undefended at s=0 (drift spoof, D-053b sweep).
Hypothesis under test: the shared-core NIS gate (fedqpnt/fusion/eskf.py
ESKF.correct, Sec 2.7) rejects the slowly-dragged GNSS fix once the drift
outgrows S, so the node coasts free-inertial on MEMS; "undefended" has the
gate off (alpha_gate=0) and just follows the spoof.

Read-only instrumentation: wraps `agent.eskf.correct` to capture P (pre-
update) and reconstructs the EXACT gate decision `correct()` makes
internally (same H, same R_nom = S - H@P@H.T recovered from the Innovation
already returned by `innovations()`, same R_eff = R_nom/max(w, w_min),
same nis_eff/chi2 threshold) -- no edit to eskf.py, just observing its
already-public Innovation/TrustState objects plus the instance's own P/cfg,
which are already public attributes.

Methods: fixed_trust (w==1, gate ON), undefended (w==1, gate OFF),
fedqpnt_local, bprime, baseline_b_bin. 3 seeds x 10 min, drift spoof,
cn0_sig_scale=0 (same scenario as the D-053b s=0 RMSE check).

Usage: python scripts/diag_s0_gate_localization.py [--workers 5]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from scipy.stats import chi2

METHODS = ["fixed_trust", "undefended", "fedqpnt_local", "bprime", "baseline_b_bin"]
SEEDS = [9600, 9601, 9602]
DURATION_S = 600.0
ATTACK = dict(kind="drift_spoof", onset_s=60.0, duration_s=180.0, severity=0.5, cn0_sig_scale=0.0)
DETECTOR_WEIGHTS_V2 = ROOT / "results" / "m1" / "detector_weights_sup_v2.npz"
G0 = 9.80665
H_GNSS = np.zeros((6, 15))
H_GNSS[0:3, 0:3] = np.eye(3)
H_GNSS[3:6, 3:6] = np.eye(3)


def run_one(method: str, seed: int) -> dict:
    from fedqpnt.node.agent import Agent
    from fedqpnt.node.environment import EnvConfig, NodeEnvironment
    from fedqpnt.node.methods import make_agent_config
    import fedqpnt.core.types as core_types

    atk = dict(kind=ATTACK["kind"], onset_s=ATTACK["onset_s"], duration_s=ATTACK["duration_s"],
               severity=ATTACK["severity"], params=dict(cn0_sig_scale=ATTACK["cn0_sig_scale"]))
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=30.0,
                         heading_noise_deg=2.0, attacks=[atk])
    env = NodeEnvironment(env_cfg, seed=seed, node_id="node0", dt=0.01, duration_s=DURATION_S)
    weights = str(DETECTOR_WEIGHTS_V2) if DETECTOR_WEIGHTS_V2.exists() else None
    agent_cfg = make_agent_config(method, kappa_R=40.0, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True, detector_weights_path=weights)
    agent = Agent(agent_cfg, env.imu.config(), node_id="node0")

    gate_log: list[tuple[float, bool]] = []   # (t, nis_gate_rejected) for gnss, attack window only
    state_log: list[tuple[float, str]] = []   # (t, gnss_law state) fedqpnt only
    pbar_log: list[tuple[float, float]] = []
    orig_correct = agent.eskf.correct

    def wrapped_correct(t, innovations, trust):
        P_pre = agent.eskf.P.copy()
        w_min = agent.eskf.cfg.w_min
        alpha = agent.eskf.cfg.alpha_gate
        for inn in innovations:
            if inn.sensor != "gnss":
                continue
            w = trust.weights.get("gnss", 1.0)
            R_nom = inn.S - H_GNSS @ P_pre @ H_GNSS.T
            R_eff = R_nom / max(w, w_min)
            S_eff = H_GNSS @ P_pre @ H_GNSS.T + R_eff
            nis_eff = float(inn.nu @ np.linalg.solve(S_eff, inn.nu))
            rejected = bool(nis_eff > chi2.ppf(1.0 - alpha, inn.dof))
            gate_log.append((t, rejected))
        state = getattr(getattr(agent.trust.gnss_law, "_core_v2", None), "state", None)
        if state is not None:
            state_log.append((t, state))
        pbar_log.append((t, trust.anomaly_scores.get("gnss", 0.0)))
        return orig_correct(t, innovations, trust)
    agent.eskf.correct = wrapped_correct

    f_b_hold: list[np.ndarray] = []
    initialized = False
    rows_t, rows_pos, rows_true = [], [], []
    for k in range(len(env)):
        tick = env.tick(k)
        t = tick.t
        if not initialized:
            if t < env.hold_s:
                if tick.imu is not None:
                    f_b_hold.append(tick.imu.f_b)
                continue
            f_mean = np.mean(f_b_hold, axis=0) if f_b_hold else np.array([0.0, 0.0, G0])
            phi0 = float(np.arctan2(f_mean[1], f_mean[2]))
            theta0 = float(np.arctan2(-f_mean[0], np.sqrt(f_mean[1] ** 2 + f_mean[2] ** 2)))
            psi0 = float(tick.truth.att[2]) + env.initial_heading_noise()
            agent.initialize_static(t, tick.truth.pos.copy(), np.array([phi0, theta0, psi0]))
            initialized = True
            continue
        atick = agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
        rows_t.append(t)
        rows_pos.append(atick.nav.pos.copy())
        rows_true.append(tick.truth.pos.copy())

    t_arr = np.array(rows_t)
    pos_est, pos_true = np.array(rows_pos), np.array(rows_true)
    e_h = np.linalg.norm((pos_est - pos_true)[:, :2], axis=1)
    onset, dur = ATTACK["onset_s"], ATTACK["duration_s"]
    att_mask = (t_arr >= onset) & (t_arr < onset + dur)
    rmse_h_att = float(np.sqrt(np.mean(e_h[att_mask] ** 2))) if att_mask.any() else float("nan")

    gate_t = np.array([g[0] for g in gate_log])
    gate_rej = np.array([g[1] for g in gate_log])
    att_gate_mask = (gate_t >= onset) & (gate_t < onset + dur)
    n_att_gnss = int(att_gate_mask.sum())
    frac_rejected = float(gate_rej[att_gate_mask].mean()) if n_att_gnss else float("nan")

    longest_run = 0
    cur = 0
    for rej in gate_rej[att_gate_mask]:
        if rej:
            cur += 1
            longest_run = max(longest_run, cur)
        else:
            cur = 0
    longest_run_s = float(longest_run) * 1.0  # gnss_rate_hz=1.0

    frac_distrust_probe = float("nan")
    if state_log:
        st_t = np.array([s[0] for s in state_log])
        st = np.array([s[1] for s in state_log])
        m = (st_t >= onset) & (st_t < onset + dur)
        if m.any():
            frac_distrust_probe = float(np.mean(np.isin(st[m], ["DISTRUST", "PROBE"])))

    pbar_t = np.array([p[0] for p in pbar_log])
    pbar_v = np.array([p[1] for p in pbar_log])
    pm = (pbar_t >= onset) & (pbar_t < onset + dur)
    mean_p_attack = float(np.mean(pbar_v[pm])) if pm.any() else float("nan")

    return dict(method=method, seed=seed, rmse_h_att=rmse_h_att,
                frac_gnss_epochs_nis_rejected=frac_rejected,
                n_attack_window_gnss_epochs=n_att_gnss,
                longest_continuous_gate_reject_run_s=longest_run_s,
                frac_time_distrust_or_probe=frac_distrust_probe,
                mean_detector_p_attack=mean_p_attack)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--out", type=str, default=str(ROOT / "results" / "m1" / "diag_s0_gate_localization.json"))
    args = ap.parse_args()

    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor
    jobs = [(m, s) for m in METHODS for s in SEEDS]
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=min(args.workers, 6), mp_context=ctx) as ex:
        rows = list(ex.map(_worker, jobs))

    by_method: dict[str, list] = {}
    for r in rows:
        by_method.setdefault(r["method"], []).append(r)

    summary = {}
    for method, rs in by_method.items():
        summary[method] = dict(
            mean_rmse_h_att=float(np.mean([r["rmse_h_att"] for r in rs])),
            per_seed_rmse_h_att=[r["rmse_h_att"] for r in rs],
            mean_frac_nis_rejected=float(np.nanmean([r["frac_gnss_epochs_nis_rejected"] for r in rs])),
            per_seed_frac_nis_rejected=[r["frac_gnss_epochs_nis_rejected"] for r in rs],
            max_longest_continuous_gate_reject_run_s=float(np.max([r["longest_continuous_gate_reject_run_s"] for r in rs])),
            per_seed_longest_run_s=[r["longest_continuous_gate_reject_run_s"] for r in rs],
            mean_frac_time_distrust_or_probe=float(np.nanmean([r["frac_time_distrust_or_probe"] for r in rs])),
            mean_detector_p_attack=float(np.nanmean([r["mean_detector_p_attack"] for r in rs])),
        )
    out = dict(label="D-055 diagnostic; kappa_R PROVISIONAL; tuning seeds; NO code changes",
               seeds=SEEDS, duration_s=DURATION_S, attack=ATTACK, by_method=summary, raw_rows=rows)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf8")
    print(json.dumps(summary, indent=2))
    print(f"written to {args.out}")


def _worker(args):
    return run_one(*args)


if __name__ == "__main__":
    main()
