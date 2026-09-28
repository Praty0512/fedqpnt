"""D-053b signature-strength sweep: scales the spoofer's single-antenna
C/N0 signature (fedqpnt.attacks.spoofing.DriftInSpoof.cn0_sig_scale, D-018
ASSUMPTION parameters -- shared-fluctuation sigma + post-capture convergence
toward a common level) over s in {0, 0.25, 0.5, 0.75, 1.0} and reports the
FROZEN v2 detector's (trained once, at s=1, by scripts/train_supervised_v2.py)
AUC on held-out drift and meaconing missions at each s. Meaconing's config
has no cn0_sig_scale knob (its own C/N0 bump is already fully cross-PRN
correlated by construction, s independent) -- included as a same-detector,
same-eval-pipeline CONTROL curve, expected roughly flat across s.

Also (D-053b second half): at s=0 (no signature at all), runs the FedQPNT
attack-phase RMSE_h vs undefended baseline on drift-spoof missions
(3 seeds x 10 min), via the real closed-loop runner (fedqpnt.node.runner),
to characterise where detection degrades AND what that costs in navigation
error when it does.

Usage: python scripts/sweep_signature_strength.py [--weights PATH] [--workers 6]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from fedqpnt.training.build_supervised_dataset import collect_run, run_pool  # noqa: E402

DETECTOR_WEIGHTS_V2 = ROOT / "results" / "m1" / "detector_weights_sup_v2.npz"
SIG_SCALES = [0.0, 0.25, 0.5, 0.75, 1.0]
DRIFT_SEEDS = list(range(9500, 9505))     # tuning range, disjoint from 500-599 train/platt/heldout
MEACON_SEEDS = list(range(9505, 9510))
SWEEP_DURATION_S = 300.0
RMSE_SEEDS = [9600, 9601, 9602]
RMSE_DURATION_S = 600.0


def bootstrap_auc(scores, labels, n_boot=1000, seed=0):
    from sklearn.metrics import roc_auc_score
    rng_b = np.random.default_rng(seed)
    if len(np.unique(labels)) < 2:
        return float("nan"), (float("nan"), float("nan"))
    auc = roc_auc_score(labels, scores)
    boots = []
    n = len(labels)
    for _ in range(n_boot):
        idx = rng_b.integers(0, n, n)
        if len(np.unique(labels[idx])) < 2:
            continue
        boots.append(roc_auc_score(labels[idx], scores[idx]))
    lo, hi = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))) if boots else (float("nan"),) * 2
    return float(auc), (lo, hi)


def platt_apply(p_raw, a, b):
    eps = 1e-6
    z = np.log(np.clip(p_raw, eps, 1 - eps) / np.clip(1 - p_raw, eps, 1 - eps))
    return 1.0 / (1.0 + np.exp(-(a * z + b)))


def _collect_family(kind: str, seed: int, s: float, duration_s: float) -> dict:
    """One real closed-loop mission with a SINGLE attack (drift_spoof with
    cn0_sig_scale=s, or meaconing unaffected by s), method=fixed_trust (same
    data-collection convention as build_supervised_dataset.collect_run --
    bypasses plan_for's family cycling since the sweep wants ONE family per
    call, not the mixed pool)."""
    from fedqpnt.node.agent import Agent
    from fedqpnt.node.environment import EnvConfig, NodeEnvironment
    from fedqpnt.node.methods import make_agent_config
    G0 = 9.80665

    if kind == "drift":
        atk = dict(kind="drift_spoof", onset_s=60.0, duration_s=180.0, severity=0.5,
                    params=dict(cn0_sig_scale=s))
    elif kind == "meaconing":
        atk = dict(kind="meaconing", onset_s=60.0, duration_s=180.0, severity=0.5)
    else:
        raise ValueError(kind)

    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=30.0,
                         heading_noise_deg=2.0,
                         attacks=[dict(kind=atk["kind"], onset_s=atk["onset_s"], duration_s=atk["duration_s"],
                                       severity=atk["severity"], params=atk.get("params"))])
    env = NodeEnvironment(env_cfg, seed=seed, node_id="sweep", dt=0.01, duration_s=duration_s)
    agent_cfg = make_agent_config("fixed_trust", kappa_R=40.0, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True, detector_weights_path=None)
    agent = Agent(agent_cfg, env.imu.config(), node_id="sweep")

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
            phi0 = float(np.arctan2(f_mean[1], f_mean[2]))
            theta0 = float(np.arctan2(-f_mean[0], np.sqrt(f_mean[1] ** 2 + f_mean[2] ** 2)))
            psi0 = float(tick.truth.att[2])
            agent.initialize_static(t, tick.truth.pos.copy(), np.array([phi0, theta0, psi0]))
            initialized = True
            continue
        agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
        oracle_by_t[round(t, 6)] = (bool(tick.label.spoofing), bool(tick.label.jamming))

    ts = [c[0] for c in captured]
    raws = [c[1].tolist() for c in captured]
    y_spoof = [oracle_by_t.get(round(t, 6), (False, False))[0] for t in ts]
    y_jam = [oracle_by_t.get(round(t, 6), (False, False))[1] for t in ts]
    return dict(seed=seed, kind=kind, s=s, t=ts, raw=raws, y_spoof=y_spoof, y_jam=y_jam)


def score_with_detector(detector, c: dict):
    import torch
    from fedqpnt.trust.features import EwmaStack
    stack = EwmaStack()
    t = np.array(c["t"])
    p_spoof = []
    for j in range(len(t)):
        raw = np.asarray(c["raw"][j], dtype=np.float64)
        xtilde = detector.normalizer.normalize(raw)
        u = stack.step(t[j], xtilde)
        with torch.no_grad():
            out = detector.model(torch.as_tensor(u, dtype=torch.float32)).numpy()
        p_spoof.append(float(out[0]))
    p_spoof = np.array(p_spoof)
    p_cal = platt_apply(p_spoof, detector.platt_a_spoof, detector.platt_b_spoof)
    return p_cal, np.array(c["y_spoof"], dtype=float)


def run_sweep(weights_path: Path) -> dict:
    from fedqpnt.trust.detector import TrustDetector
    detector = TrustDetector(arch="mlp", seed=0)
    params = dict(np.load(weights_path, allow_pickle=True))
    detector.set_params(params)

    sweep_report = {}
    for s in SIG_SCALES:
        drift_p, drift_y = [], []
        for seed in DRIFT_SEEDS:
            c = _collect_family("drift", seed, s, SWEEP_DURATION_S)
            if not c["t"]:
                continue
            p, y = score_with_detector(detector, c)
            drift_p.append(p); drift_y.append(y)
        meacon_p, meacon_y = [], []
        for seed in MEACON_SEEDS:
            c = _collect_family("meaconing", seed, s, SWEEP_DURATION_S)
            if not c["t"]:
                continue
            p, y = score_with_detector(detector, c)
            meacon_p.append(p); meacon_y.append(y)
        drift_auc, drift_ci = bootstrap_auc(np.concatenate(drift_p), np.concatenate(drift_y)) if drift_p else (float("nan"), (float("nan"),) * 2)
        meacon_auc, meacon_ci = bootstrap_auc(np.concatenate(meacon_p), np.concatenate(meacon_y)) if meacon_p else (float("nan"), (float("nan"),) * 2)
        sweep_report[str(s)] = dict(
            auc_drift=drift_auc, ci95_drift=list(drift_ci), n_drift=int(sum(len(x) for x in drift_y)),
            auc_meaconing=meacon_auc, ci95_meaconing=list(meacon_ci), n_meaconing=int(sum(len(x) for x in meacon_y)),
        )
        print(f"s={s}: drift AUC={drift_auc:.3f} {drift_ci}  meaconing AUC={meacon_auc:.3f} {meacon_ci}")
    return sweep_report


def run_rmse_comparison(weights_path: Path, n_workers: int) -> dict:
    from fedqpnt.node.runner import RunSpec, run_many
    specs = []
    for seed in RMSE_SEEDS:
        for method in ("fedqpnt_local", "undefended"):
            specs.append(RunSpec(
                name=f"sig0_{method}_{seed}", master_seed=seed, method=method,
                duration_s=RMSE_DURATION_S, hold_s=30.0, platform="ground", world="flat",
                imu_grade="industrial_mems", quantum_grade="field", gnss_rate_hz=1.0,
                heading_noise_deg=2.0,
                attack=dict(kind="drift_spoof", onset_s=60.0, duration_s=180.0, severity=0.5,
                            params=dict(cn0_sig_scale=0.0)),
                kappa_R=40.0, kappa_Q=1.0,
                detector_weights_path=str(weights_path) if weights_path.exists() else None,
                record=False,
            ))
    results = run_many(specs, n_workers=min(n_workers, 6))
    by_method: dict[str, list] = {}
    for spec, res in zip(specs, results):
        by_method.setdefault(spec.method, []).append(res)
    out = {}
    for method, rows in by_method.items():
        rmses = [r.get("rmse_h_att", float("nan")) for r in rows]
        out[method] = dict(per_seed_rmse_h_att=rmses, mean_rmse_h_att=float(np.nanmean(rmses)))
    fq = out.get("fedqpnt_local", {}).get("mean_rmse_h_att", float("nan"))
    un = out.get("undefended", {}).get("mean_rmse_h_att", float("nan"))
    out["ratio_fedqpnt_over_undefended"] = float(fq / un) if un else float("nan")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=str, default=str(DETECTOR_WEIGHTS_V2))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", type=str, default=str(ROOT / "results" / "m1" / "sig_strength_sweep.json"))
    args = ap.parse_args()
    weights_path = Path(args.weights)
    t0 = time.time()

    sweep_report = run_sweep(weights_path)
    print(f"[{time.time()-t0:.0f}s] sweep done")

    rmse_report = run_rmse_comparison(weights_path, args.workers)
    print(f"[{time.time()-t0:.0f}s] s=0 RMSE comparison done:", json.dumps(rmse_report, indent=2))

    out = dict(
        label="kappa_R PROVISIONAL; tuning seeds; D-053b signature-strength sweep",
        weights_used=str(weights_path),
        drift_seeds=DRIFT_SEEDS, meaconing_seeds=MEACON_SEEDS, sweep_duration_s=SWEEP_DURATION_S,
        auc_vs_s=sweep_report,
        rmse_seeds=RMSE_SEEDS, rmse_duration_s=RMSE_DURATION_S, s0_rmse_h_att_comparison=rmse_report,
        wall_s=time.time() - t0,
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf8")
    print(f"written to {args.out}")


if __name__ == "__main__":
    main()
