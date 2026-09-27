"""WP-8.1: choose kappa_R once on tuning seeds (500-599), for all methods
alike, so nominal ANEES_pos = 1 +- 0.1 (ARCHITECTURE.md section 7.6, D-023,
D-027). Uses the "fixed-trust" method (w == 1, NIS gate ON) per the WP-8.1
brief, ground platform, industrial_mems IMU, FIELD-grade CAI, 10-minute runs,
nominal scenario (no attack).

Usage: python scripts/tune_kappa_r.py [--seeds N] [--duration S] [--kappas ...]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fedqpnt.node.runner import RunSpec, run_single  # noqa: E402
DETECTOR_WEIGHTS = ROOT / "results" / "m1" / "detector_weights.npz"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10, help="number of tuning seeds starting at 500")
    ap.add_argument("--duration", type=float, default=600.0, help="sim seconds per run")
    ap.add_argument("--kappas", type=float, nargs="+", default=[10.0, 20.0, 30.0, 40.0, 60.0, 80.0, 120.0])
    ap.add_argument("--out", type=str, default=str(ROOT / "results" / "m1" / "kappa_r_tuning.json"))
    args = ap.parse_args()

    seeds = list(range(500, 500 + args.seeds))
    rows = []
    for kR in args.kappas:
        t0 = time.time()
        aneess = []
        for s in seeds:
            spec = RunSpec(name=f"tune_kR{kR}_{s}", master_seed=s, method="fixed_trust",
                            duration_s=args.duration, hold_s=30.0, platform="ground",
                            imu_grade="industrial_mems", quantum_grade="field", kappa_R=kR,
                            detector_weights_path=str(DETECTOR_WEIGHTS) if DETECTOR_WEIGHTS.exists() else None)
            res = run_single(spec)
            aneess.append(res["anees_pos_pre"] if np.isfinite(res.get("anees_pos_pre", float("nan")))
                          else res["anees_pos_all"])
        mean_anees = float(np.mean(aneess))
        rows.append(dict(kappa_R=kR, mean_anees_pos=mean_anees, per_seed=aneess, wall_s=time.time() - t0))
        print(f"kappa_R={kR:>7.2f}  mean ANEES_pos={mean_anees:.4f}  "
              f"(target 1.0 +- 0.1)  wall={time.time()-t0:.1f}s")

    best = min(rows, key=lambda r: abs(r["mean_anees_pos"] - 1.0))
    out = dict(seeds=seeds, duration_s=args.duration, rows=rows, chosen_kappa_R=best["kappa_R"],
               chosen_mean_anees_pos=best["mean_anees_pos"])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf8")
    print(f"\nChosen kappa_R = {best['kappa_R']} (mean ANEES_pos = {best['mean_anees_pos']:.4f})")
    print(f"Written to {args.out}")


if __name__ == "__main__":
    main()
