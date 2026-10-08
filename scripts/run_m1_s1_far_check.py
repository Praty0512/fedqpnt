"""M1-CLOSE task 4 (S1 false-alarm check, ARCHITECTURE.md section 6 S1
criteria): clean nominal runs, 5 seeds x 30 min, all 7 methods. Reports
FAR/h per method (criterion <= 1/h/node) and the S1 criterion
RMSE_h(FedQPNT) <= 1.05 x RMSE_h(fixed-trust), PAIRED per seed (median
ratio) -- not tuned to pass.

Usage: python scripts/run_m1_s1_far_check.py [--weights PATH] [--workers N]
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
from fedqpnt.node.runner import RunSpec, run_many  # noqa: E402
from fedqpnt.core.defaults import DEFAULT_KAPPA_R  # noqa: E402
from fedqpnt.node.methods import METHOD_NAMES  # noqa: E402

DETECTOR_WEIGHTS_REAL = ROOT / "results" / "m1" / "detector_weights_real.npz"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=1800.0)
    ap.add_argument("--seeds", type=int, nargs="+", default=[500, 501, 502, 503, 504])
    ap.add_argument("--kappa-r", type=float, default=DEFAULT_KAPPA_R)
    ap.add_argument("--imu-grade", type=str, default="industrial_mems")
    ap.add_argument("--world", type=str, default="schuler_tangent")  # D-083: S1 registered on schuler_tangent (core-freeze-5)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--weights", type=str, default=str(DETECTOR_WEIGHTS_REAL))
    ap.add_argument("--out", type=str, default=str(ROOT / "results" / "m1" / "s1_far_check.json"))
    args = ap.parse_args()
    weights_path = Path(args.weights)

    specs = []
    for method in METHOD_NAMES:
        for seed in args.seeds:
            specs.append(RunSpec(
                name=f"s1_{method}_{seed}", master_seed=seed, method=method,
                duration_s=args.duration, hold_s=30.0, platform="ground", world=args.world,
                imu_grade=args.imu_grade, quantum_grade="field", gnss_rate_hz=1.0,
                heading_noise_deg=2.0, attack=None, kappa_R=args.kappa_r, kappa_Q=1.0,
                detector_weights_path=str(weights_path) if weights_path.exists() else None,
                record=False,
            ))

    t0 = time.time()
    results = run_many(specs, n_workers=min(args.workers, 6))
    wall = time.time() - t0

    by_method: dict[str, list] = {}
    for spec, res in zip(specs, results):
        by_method.setdefault(spec.method, []).append(res)

    far_table = {}
    for method, rows in by_method.items():
        fars = [r.get("far_per_hour", float("nan")) for r in rows]
        aneess = [r.get("anees_pos_pre", r.get("anees_pos_all", float("nan"))) for r in rows]
        wgs = [r.get("mean_w_gnss", float("nan")) for r in rows]
        far_table[method] = dict(
            mean_far_per_hour=float(np.nanmean(fars)), per_seed_far=fars,
            pass_far=bool(np.nanmax(fars) <= 1.0) if fars else False,
            mean_anees_pos=float(np.nanmean(aneess)), mean_w_gnss=float(np.nanmean(wgs)),
        )

    # S1 criterion: RMSE_h(FedQPNT) <= 1.05 x RMSE_h(fixed-trust), paired per seed.
    fedqpnt_by_seed = {r["seed"]: r.get("rmse_h_pre", float("nan")) for r in by_method.get("fedqpnt_local", [])}
    fixed_by_seed = {r["seed"]: r.get("rmse_h_pre", float("nan")) for r in by_method.get("fixed_trust", [])}
    ratios = []
    for seed in args.seeds:
        fq, fx = fedqpnt_by_seed.get(seed), fixed_by_seed.get(seed)
        if fq is not None and fx is not None and fx > 0:
            ratios.append(fq / fx)
    median_ratio = float(np.median(ratios)) if ratios else float("nan")
    s1_pass = bool(median_ratio <= 1.05) if ratios else False

    out = dict(
        label="S1 false-alarm + criterion check, tuning seeds, not for publication",
        seeds=args.seeds, duration_s=args.duration, kappa_R=args.kappa_r, world=args.world, imu_grade=args.imu_grade,
        weights_used=str(weights_path), wall_s=wall,
        far_per_hour_by_method=far_table,
        s1_rmse_criterion=dict(
            per_seed_ratio=ratios, median_ratio=median_ratio, threshold=1.05,
            PASS=s1_pass, fedqpnt_rmse_h_pre_by_seed=fedqpnt_by_seed,
            fixed_trust_rmse_h_pre_by_seed=fixed_by_seed,
        ),
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf8")
    print(json.dumps(far_table, indent=2))
    print(f"S1 median RMSE ratio (fedqpnt/fixed_trust) = {median_ratio:.4f}  "
          f"(threshold 1.05)  PASS={s1_pass}")
    print(f"written to {args.out}  wall={wall:.1f}s")


if __name__ == "__main__":
    main()
