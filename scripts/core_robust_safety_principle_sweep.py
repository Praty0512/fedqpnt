"""Item 6(ii): the D-055 safety principle across the signature-strength
sweep, s in {0, 0.25, 0.5, 1.0}, drift spoof, 3 seeds x 10 min, every
method. sigma_nom = std of the UNDEFENDED method's own nominal-scenario
(no attack) rmse_h_pre across seeds (same convention as
scripts/defended_vs_undefended_check.py, D-048), applied once, shared
across every s value (D-055's "3sigma_nom" is the nominal noise floor, not
re-measured per attack condition).

A defended method PASSES at signature strength s iff
mean(rmse_h_att) <= mean_undefended(rmse_h_att @ s) + 3*sigma_nom.

Usage: python scripts/core_robust_safety_principle_sweep.py [--kappa-r 60]
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

from fedqpnt.node.runner import RunSpec, run_many  # noqa: E402
from fedqpnt.node.methods import METHOD_NAMES  # noqa: E402

DETECTOR_WEIGHTS_V2 = ROOT / "results" / "m1" / "detector_weights_sup_v2.npz"
S_VALUES = [0.0, 0.25, 0.5, 1.0]
SEEDS = [9600, 9601, 9602]   # tuning range 9500-9699
DURATION_S = 600.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kappa-r", type=float, default=60.0)
    ap.add_argument("--weights", type=str, default=str(DETECTOR_WEIGHTS_V2))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", type=str, default=str(ROOT / "results" / "m1" / "core_robust_safety_sweep.json"))
    args = ap.parse_args()
    weights_path = Path(args.weights)

    specs = []
    # nominal (no attack) runs, once, to get sigma_nom
    for method in METHOD_NAMES:
        for seed in SEEDS:
            specs.append(RunSpec(
                name=f"safety_nominal_{method}_{seed}", master_seed=seed, method=method,
                duration_s=DURATION_S, hold_s=30.0, platform="ground", world="flat",
                imu_grade="industrial_mems", quantum_grade="field", gnss_rate_hz=1.0,
                heading_noise_deg=2.0, attack=None, kappa_R=args.kappa_r, kappa_Q=1.0,
                detector_weights_path=str(weights_path) if weights_path.exists() else None,
                record=False,
            ))
    # drift-spoof at each signature strength s
    for s in S_VALUES:
        for method in METHOD_NAMES:
            for seed in SEEDS:
                specs.append(RunSpec(
                    name=f"safety_s{s}_{method}_{seed}", master_seed=seed, method=method,
                    duration_s=DURATION_S, hold_s=30.0, platform="ground", world="flat",
                    imu_grade="industrial_mems", quantum_grade="field", gnss_rate_hz=1.0,
                    heading_noise_deg=2.0,
                    attack=dict(kind="drift_spoof", onset_s=120.0, duration_s=180.0, severity=0.5,
                                params=dict(cn0_sig_scale=s)),
                    kappa_R=args.kappa_r, kappa_Q=1.0,
                    detector_weights_path=str(weights_path) if weights_path.exists() else None,
                    record=False,
                ))

    t0 = time.time()
    results = run_many(specs, n_workers=min(args.workers, 16))
    wall = time.time() - t0

    nominal_undef = [res.get("rmse_h_pre", float("nan")) for spec, res in zip(specs, results)
                      if spec.attack is None and spec.method == "undefended"]
    sigma_nom = float(np.nanstd(nominal_undef)) if len(nominal_undef) > 1 else float("nan")

    table: dict[str, dict] = {}
    for s in S_VALUES:
        by_method: dict[str, list] = {}
        for spec, res in zip(specs, results):
            if spec.attack is None or spec.attack.get("params", {}).get("cn0_sig_scale") != s:
                continue
            by_method.setdefault(spec.method, []).append(res.get("rmse_h_att", float("nan")))
        undefended = np.array(by_method.get("undefended", []), dtype=float)
        mean_undefended = float(np.nanmean(undefended)) if len(undefended) else float("nan")
        threshold = mean_undefended + 3.0 * sigma_nom
        rows = {}
        for method, vals in by_method.items():
            vals = np.array(vals, dtype=float)
            mean_val = float(np.nanmean(vals))
            worse = bool(mean_val > threshold) if np.isfinite(threshold) else None
            rows[method] = dict(mean_rmse_h_att=mean_val, per_seed=vals.tolist(),
                                 threshold=threshold, PASS=(not worse) if worse is not None else None)
        table[str(s)] = dict(mean_undefended=mean_undefended, methods=rows)

    out = dict(label="D-055 safety-principle sweep, tuning seeds 9600-9602, "
                      f"kappa_R={args.kappa_r} (post D-043/D-057/D-058 core-robust session)",
               seeds=SEEDS, duration_s=DURATION_S, kappa_R=args.kappa_r, sigma_nom=sigma_nom,
               weights_used=str(weights_path), wall_s=wall, s_values=S_VALUES, table=table)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf8")

    print(f"sigma_nom (nominal, undefended, across seeds) = {sigma_nom:.4f}\n")
    for s in S_VALUES:
        row = table[str(s)]
        print(f"[s={s}] mean_undefended={row['mean_undefended']:.4f}")
        for method, m in row["methods"].items():
            print(f"  {method:16s} mean={m['mean_rmse_h_att']:.4f}  threshold={m['threshold']:.4f}  "
                  f"PASS={m['PASS']}")
    print(f"\nwritten to {args.out}  wall={wall:.1f}s")


if __name__ == "__main__":
    main()
