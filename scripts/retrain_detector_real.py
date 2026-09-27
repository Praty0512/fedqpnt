"""M1-CLOSE task 2 (D-029/D-046): retrain the FROZEN detector design (D-026:
xsat rule on, class-balanced local training -- design UNCHANGED) on REAL
closed-loop features.

Runs the real Agent (real ``GnssReceiver.solve`` -> real ``ESKF.propagate/
innovations/correct`` with real FIELD-CAI aiding, method="fixed_trust" so
GNSS corrections are never suppressed by an as-yet-untrained detector) over
pseudo-labelled missions, ground platform / industrial_mems IMU / FIELD CAI,
seeds 500-599 only, a mix of clean + all four attack families.

The M0 "surrogate CUSUM" (``trust.pseudolabel.surrogate_s_cusum`` fed
all-zero x1 because no fusion filter existed yet) is replaced by the SAME
Page-CUSUM formula fed the REAL x1 (nis_pos): now that the closed-loop
Agent's ESKF genuinely fuses CAI, this is exactly the architecture's "a
slowly drifting CAI-aided INS is a trustworthy hindsight reference"
(Sec 4.3) -- nis_pos IS the real INS(+CAI)-vs-GNSS divergence, computed from
the real innovation before correction. No surrogate remains.

Real x1/x2 features are captured by wrapping (monkeypatching) the running
Agent's ``TrustEngineImpl.extractor.step`` for this script only -- no edits
to fedqpnt/trust or fedqpnt/node files.

Usage: python scripts/retrain_detector_real.py [--workers N]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

G0 = 9.80665
DURATION_S = 300.0
DT = 0.01
HOLD_S = 30.0

# family cycle (skip "clean" at index 0 for the attacked-seed assignment)
FAMILY_ATTACKS = [
    ("drift", dict(kind="drift_spoof", onset_s=60.0, duration_s=180.0, severity=0.5)),
    ("meaconing", dict(kind="meaconing", onset_s=60.0, duration_s=180.0, severity=0.5)),
    ("abrupt", dict(kind="abrupt_spoof", onset_s=60.0, duration_s=180.0, severity=0.5)),
    ("jamming", dict(kind="jam_cw", onset_s=60.0, duration_s=180.0, severity=0.5)),
]

# Seed pools (disjoint, all inside 500-599 per the WP brief):
CLEAN_CALIB_SEEDS = list(range(500, 520))           # 20 clean-only, quantile reference
TRAIN_SEEDS = list(range(520, 580))                 # 60 mixed clean(20%)/attacked(80%), training
HELDOUT_SEEDS = list(range(580, 600))               # 20 mixed, disjoint, held-out AUC eval


def _level_att(f_b_mean: np.ndarray) -> tuple[float, float]:
    fx, fy, fz = f_b_mean
    phi = float(np.arctan2(fy, fz))
    theta = float(np.arctan2(-fx, np.sqrt(fy ** 2 + fz ** 2)))
    return phi, theta


def _plan_for(seed: int, pool: str) -> tuple[str, dict | None]:
    if pool == "clean":
        return "clean", None
    # 1-in-5 clean, else cycle the 4 attack families -- deterministic in seed order
    idx = seed % 5
    if idx == 0:
        return "clean", None
    return FAMILY_ATTACKS[(seed // 5) % 4]


def collect_one(args: tuple[int, str]) -> dict:
    """Runs ONE real closed-loop Agent for one seed and returns per-epoch
    real raw features (15,), raim_stat, num_sats, oracle-active flag, and t.
    Picklable module-level worker for ProcessPoolExecutor."""
    seed, pool = args
    from fedqpnt.node.agent import Agent
    from fedqpnt.node.environment import EnvConfig, NodeEnvironment
    from fedqpnt.node.methods import make_agent_config

    family, atk = _plan_for(seed, pool)
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=HOLD_S,
                         heading_noise_deg=2.0, attacks=[atk] if atk else [])
    env = NodeEnvironment(env_cfg, seed=seed, node_id="retrain", dt=DT, duration_s=DURATION_S)
    agent_cfg = make_agent_config("fixed_trust", kappa_R=40.0, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True, detector_weights_path=None)
    agent = Agent(agent_cfg, env.imu.config(), node_id="retrain")

    captured: list[tuple] = []
    orig_step = agent.trust.extractor.step

    def _wrapped(fix, innovations):
        raw = orig_step(fix, innovations)
        if raw is not None:
            captured.append((fix.t, raw.copy(), float(fix.raim_stat) if np.isfinite(fix.raim_stat) else 0.0,
                              float(fix.num_sats)))
        return raw
    agent.trust.extractor.step = _wrapped

    f_b_hold: list[np.ndarray] = []
    initialized = False
    oracle_active: dict[float, bool] = {}
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
        oracle_active[round(t, 6)] = bool(tick.label.spoofing or tick.label.jamming)

    if not captured:
        return dict(seed=seed, family=family, t=[], raw=[], raim=[], nsat=[], oracle=[])
    ts = [c[0] for c in captured]
    raws = [c[1].tolist() for c in captured]
    raims = [c[2] for c in captured]
    nsats = [c[3] for c in captured]
    oracle = [oracle_active.get(round(t, 6), False) for t in ts]
    return dict(seed=seed, family=family, t=ts, raw=raws, raim=raims, nsat=nsats, oracle=oracle)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", type=str, default=str(ROOT / "results" / "m1" / "detector_weights_real.npz"))
    ap.add_argument("--report", type=str, default=str(ROOT / "results" / "m1" / "detector_retrain_report.json"))
    args = ap.parse_args()
    n_workers = min(args.workers, 6, mp.cpu_count())

    jobs = ([(s, "clean") for s in CLEAN_CALIB_SEEDS]
            + [(s, "mixed") for s in TRAIN_SEEDS]
            + [(s, "mixed") for s in HELDOUT_SEEDS])

    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=n_workers, mp_context=ctx) as ex:
        collected = list(ex.map(collect_one, jobs))
    wall_collect = time.time() - t0
    print(f"collected {len(collected)} runs in {wall_collect:.1f}s "
          f"({sum(len(c['t']) for c in collected)} epochs total)")

    by_seed = {c["seed"]: c for c in collected}

    # --- clean-only quantile reference (D-024/D-026 style: never self-referential) ---
    clean_raw = []
    for s in CLEAN_CALIB_SEEDS:
        clean_raw.extend(by_seed[s]["raw"])
    clean_raw = np.array(clean_raw)
    quantile_mu = clean_raw.mean(axis=0)
    quantile_sd = clean_raw.std(axis=0)
    quantile_sd = np.where(quantile_sd < 1e-9, 1.0, quantile_sd)

    from fedqpnt.trust.pseudolabel import PseudoLabelConfig, label_epochs, surrogate_s_cusum, \
        pseudolabel_precision_recall
    from fedqpnt.trust.detector import TrustDetector
    from fedqpnt.eval import metrics as M
    from fedqpnt.core.seeding import stream

    def label_seed(seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        c = by_seed[seed]
        t = np.array(c["t"])
        raw = np.array(c["raw"])
        raim = np.array(c["raim"])
        nsat = np.array(c["nsat"])
        oracle = np.array(c["oracle"], dtype=bool)
        # REAL S_cusum: Page CUSUM of the REAL x1 (nis_pos) from the genuine
        # closed-loop FIELD-CAI-aided ESKF innovation -- not the M0 surrogate.
        s_real = surrogate_s_cusum(raw)  # same formula, now fed real (nonzero) x1
        y = label_epochs(t, raw, raim, nsat, s_real, cfg=PseudoLabelConfig(),
                          quantile_mu=quantile_mu, quantile_sd=quantile_sd)
        return t, raw, y, oracle, s_real

    # --- pseudo-label precision/recall against oracle (evaluator-only), train pool ---
    all_y, all_oracle = [], []
    train_U, train_yspoof = [], []
    detector = TrustDetector(arch="mlp", seed=0)
    per_seed_labels = {}
    for seed in TRAIN_SEEDS:
        t, raw, y, oracle, _s = label_seed(seed)
        per_seed_labels[seed] = (t, raw, y, oracle)
        keep = ~np.isnan(y)
        all_y.append(y[keep])
        all_oracle.append(oracle[keep])
    y_concat = np.concatenate(all_y) if all_y else np.array([])
    oracle_concat = np.concatenate(all_oracle) if all_oracle else np.array([])
    pl_pr = pseudolabel_precision_recall(y_concat, oracle_concat)

    # --- build (52,)-stacked training set: causal per-seed pass so EWMA state is correct ---
    for seed in TRAIN_SEEDS:
        t, raw, y, oracle = per_seed_labels[seed]
        stack = detector._stack.__class__()  # fresh EwmaStack per seed (causal, independent streams)
        for j in range(len(t)):
            if np.isnan(y[j]):
                xtilde = detector.normalizer.normalize(raw[j])
                u = stack.step(t[j], xtilde)
                continue
            xtilde = detector.normalizer.normalize(raw[j])
            if y[j] == 0.0:
                detector.normalizer.update(raw[j])
            u = stack.step(t[j], xtilde)
            train_U.append(u)
            train_yspoof.append(y[j])
    train_U = np.array(train_U)
    train_yspoof = np.array(train_yspoof)
    train_yjam = train_yspoof.copy()  # hindsight rule set doesn't distinguish spoof/jam heads (per methods.py precedent)

    rng = stream(0, "retrain_real", "sgd")
    train_metrics = detector.train_local(train_U, train_yspoof, train_yjam, epochs=2, lr=0.05,
                                          batch_size=64, rng=rng, balance=True, max_pos_fraction=0.5)
    print("train_local:", train_metrics)

    # --- held-out per-family AUC with bootstrap CI ---
    def bootstrap_auc(scores: np.ndarray, labels: np.ndarray, n_boot: int = 1000, seed: int = 0):
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
        lo, hi = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))) if boots else (float("nan"), float("nan"))
        return float(auc), (lo, hi)

    per_family_scores: dict[str, list] = {}
    per_family_oracle: dict[str, list] = {}
    overall_scores, overall_oracle = [], []
    for seed in HELDOUT_SEEDS:
        t, raw, y, oracle, _s = label_seed(seed)
        family = by_seed[seed]["family"]
        stack = detector._stack.__class__()
        norm = detector.normalizer  # frozen post-training normalizer (causal eval, no further updates)
        scores = []
        for j in range(len(t)):
            xtilde = norm.normalize(raw[j])
            u = stack.step(t[j], xtilde)
            with __import__("torch").no_grad():
                out = detector.model(__import__("torch").as_tensor(u, dtype=__import__("torch").float32)).numpy()
            scores.append(max(float(out[0]), float(out[1])))
        scores = np.array(scores)
        per_family_scores.setdefault(family, []).extend(scores.tolist())
        per_family_oracle.setdefault(family, []).extend(oracle.astype(float).tolist())
        overall_scores.extend(scores.tolist())
        overall_oracle.extend(oracle.astype(float).tolist())

    auc_report = {}
    for family, scores in per_family_scores.items():
        auc, ci = bootstrap_auc(np.array(scores), np.array(per_family_oracle[family]))
        auc_report[family] = dict(auc=auc, ci95=list(ci), n=len(scores))
    auc_overall, ci_overall = bootstrap_auc(np.array(overall_scores), np.array(overall_oracle))
    auc_report["overall"] = dict(auc=auc_overall, ci95=list(ci_overall), n=len(overall_scores))

    # --- save weights + provenance ---
    import subprocess as sp
    try:
        commit = sp.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        commit = "unknown"
    params = detector.get_params()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.out, **{k: np.asarray(v) for k, v in params.items()})

    old_synth_auc = {  # D-026 frozen-design table, {rule on, balance on} row, synthetic-feature harness
        "overall": [0.722, 0.697, 0.749], "drift": [0.724, 0.652, 0.792],
        "meaconing": [0.575, 0.501, 0.652], "abrupt": [0.749, 0.678, 0.817],
        "jamming": [0.515, 0.422, 0.603],
    }

    report = dict(
        label="tuning seeds, not for publication",
        provenance=dict(config_hash=commit, seeds_clean_calib=CLEAN_CALIB_SEEDS,
                         seeds_train=TRAIN_SEEDS, seeds_heldout=HELDOUT_SEEDS,
                         date="2026-09-27", duration_s=DURATION_S, method="fixed_trust",
                         platform="ground", imu_grade="industrial_mems", quantum_grade="field",
                         kappa_R=40.0, detector_design="D-026 frozen (xsat rule on, balance on)",
                         s_cusum="REAL (Page CUSUM of real closed-loop x1 nis_pos, FIELD-CAI-aided ESKF; "
                                 "replaces M0 surrogate_s_cusum-on-zeros)"),
        pseudolabel_precision_recall_vs_oracle=pl_pr,
        train_local_metrics=train_metrics,
        auc_real_closed_loop=auc_report,
        auc_old_synthetic_D026=old_synth_auc,
        wall_collect_s=wall_collect,
    )
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf8")
    print(json.dumps(auc_report, indent=2))
    print(f"weights -> {args.out}")
    print(f"report -> {args.report}")


if __name__ == "__main__":
    main()
