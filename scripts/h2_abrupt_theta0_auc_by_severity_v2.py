"""H2-ABRUPT (D-061a item 1, Master ruling): theta0_noabrupt's held-out AUC
on abrupt_spoof AT EXPLICIT SEVERITIES 0.15 (the E_s-quiet regime chosen by
h2_abrupt_es_firing_check.py), 0.1, and 0.2 -- using the SAME 13 abrupt-
family seeds (from the 500-599 range) that gave the 0.898 AUC in
h2_abrupt_theta0_auc_check.py. That earlier 0.898 number was measured at
the training pool's DEFAULT abrupt severity (0.5, from
fedqpnt.training.build_supervised_dataset._family_attacks), NOT at the
severity actually used in the H2/H4 fleet runs (0.15) -- Master's ruling
requires the severity-matched number before the fleet runs start.

Reimplements collect_run's body (fedqpnt/training/build_supervised_dataset.py,
NOT edited -- this is data collection/eval, same file the D-052 docstring
says is the ONLY module allowed to join AttackLabel with features; this
script follows the identical collect-then-join-offline pattern) with an
explicit severity override on the abrupt_spoof attack spec instead of using
plan_for's fixed severity=0.5.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import subprocess

import numpy as np

from fedqpnt.core.defaults import DEFAULT_KAPPA_R

from fedqpnt.eval import metrics as M
from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import load_detector_weights, make_agent_config
from fedqpnt.trust.detector import TrustDetector

THETA0_PATH = Path("results/fleet/theta0_noabrupt_v2.npz")
OUT = Path("results/fleet/h2_abrupt_theta0_auc_check_v2.json")
EVAL_DURATION_S = 120.0
HOLD_S = 30.0
G0 = 9.80665
# same 13 seeds h2_abrupt_theta0_auc_check.py found in 500-599 with
# plan_for(seed,"mixed") -> family=="abrupt"
ABRUPT_SEEDS = [506, 512, 518, 524, 536, 542, 548, 554, 566, 572, 578, 584, 596]
SEVERITIES = [0.15, 0.1, 0.2]


def _level_att(f_b_mean):
    fx, fy, fz = f_b_mean
    phi = float(np.arctan2(fy, fz))
    theta = float(np.arctan2(-fx, np.sqrt(fy ** 2 + fz ** 2)))
    return phi, theta


def collect_run_at_severity(seed: int, severity: float, duration_s: float) -> dict:
    """Same body as build_supervised_dataset.collect_run, but with the
    abrupt_spoof attack spec's severity overridden explicitly (onset_s/
    duration_s kept at the family default: 60.0/180.0)."""
    atk_list = [dict(kind="abrupt_spoof", onset_s=60.0, duration_s=180.0, severity=severity)]
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=HOLD_S,
                         heading_noise_deg=2.0, attacks=atk_list)
    env = NodeEnvironment(env_cfg, seed=seed, node_id="sup", dt=0.01, duration_s=duration_s)
    agent_cfg = make_agent_config("fixed_trust", kappa_R=DEFAULT_KAPPA_R, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True, detector_weights_path=None)
    agent = Agent(agent_cfg, env.imu.config(), node_id="sup")

    captured: list[tuple] = []
    orig_step = agent.trust.extractor.step

    def _wrapped(fix, innovations):
        raw = orig_step(fix, innovations)
        if raw is not None:
            captured.append((fix.t, raw.copy()))
        return raw
    agent.trust.extractor.step = _wrapped

    f_b_hold: list[np.ndarray] = []
    initialized = False
    oracle_by_t: dict[float, tuple[bool, bool]] = {}
    for k in range(len(env)):
        tick = env.tick(k)
        t = tick.t
        if not initialized:
            if t < env.hold_s:
                if tick.imu is not None:
                    f_b_hold.append(tick.imu.f_b)
                continue
            f_mean = np.mean(f_b_hold, axis=0) if f_b_hold else np.array([0.0, 0.0, G0])
            phi0, theta0 = _level_att(f_mean)
            psi0 = float(tick.truth.att[2]) + env.initial_heading_noise()
            pos0 = tick.truth.pos.copy()
            agent.initialize_static(t, pos0, np.array([phi0, theta0, psi0]))
            initialized = True
            continue
        agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
        oracle_by_t[round(t, 6)] = (bool(tick.label.spoofing), bool(tick.label.jamming))

    ts = [c[0] for c in captured]
    raws = [c[1].tolist() for c in captured]
    y_spoof = [oracle_by_t.get(round(t, 6), (False, False))[0] for t in ts]
    y_jam = [oracle_by_t.get(round(t, 6), (False, False))[1] for t in ts]
    return dict(seed=seed, family="abrupt", t=ts, raw=raws, y_spoof=y_spoof, y_jam=y_jam)


def main():
    params = load_detector_weights(THETA0_PATH)
    if params is None:
        raise SystemExit(f"{THETA0_PATH} missing -- run scripts/h2_abrupt_pretrain_theta0.py first")

    per_severity = {}
    for severity in SEVERITIES:
        by_seed = {s: collect_run_at_severity(s, severity, EVAL_DURATION_S) for s in ABRUPT_SEEDS}
        det = TrustDetector(arch="mlp", seed=0)
        det.set_params(params)
        scores, labels = [], []
        for s in ABRUPT_SEEDS:
            c = by_seed[s]
            det.reset_stream()
            for j in range(len(c["t"])):
                raw = np.asarray(c["raw"][j], dtype=np.float64)
                p_spoof, p_jam, _u = det.score(c["t"][j], raw)
                scores.append(max(p_spoof, p_jam))
                labels.append(bool(c["y_spoof"][j]) or bool(c["y_jam"][j]))
        scores = np.array(scores)
        labels = np.array(labels, dtype=bool)
        auc = M.roc_auc(scores, labels) if 0 < labels.sum() < len(labels) else float("nan")
        entry = dict(severity=severity, n_epochs=len(scores), n_pos=int(labels.sum()), auc=auc)
        per_severity[str(severity)] = entry
        print(json.dumps(entry, indent=2))

    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    out.update(dict(
        note_by_severity="D-061a item 1 (Master ruling): theta0_noabrupt held-out abrupt AUC "
                         "at EXPLICIT severities (same 13 seeds as the 0.5-default-severity "
                         "0.898 result above), matching the H2/H4 fleet severity (0.15) plus "
                         "0.1/0.2 for context. auc_abrupt_heldout (0.898) above was measured "
                         "at the training pool's DEFAULT severity=0.5, NOT 0.15.",
        theta0=str(THETA0_PATH), abrupt_seeds=ABRUPT_SEEDS,
        auc_by_severity=per_severity, kappa_R_default=DEFAULT_KAPPA_R,
        old_theta0_auc={'0.1': 0.8185, '0.15': 0.8053, '0.2': 0.7829},
        git_head=subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True).stdout.strip(),
        git_describe=subprocess.run(['git','describe','--tags','--always'],capture_output=True,text=True).stdout.strip(),
        git_status_porcelain_fedqpnt=subprocess.run(['git','status','--porcelain','fedqpnt/'],capture_output=True,text=True).stdout.strip(),
    ))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
