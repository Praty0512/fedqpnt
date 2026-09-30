"""D-048: defended-vs-undefended check on nominal and CW jamming, sigma_nom
measured per run (not assumed). For each scenario, sigma_nom = std across
seeds of the UNDEFENDED method's own metric within that scenario; a defended
method fails iff its mean metric exceeds undefended's mean + 3*sigma_nom.
nominal metric = rmse_h_pre (no attack window; the whole run is "pre"),
jam_cw metric = rmse_h_att (the attack-phase RMSE, the metric this
comparison is actually about).

Usage: python scripts/defended_vs_undefended_check.py [--weights PATH] [--workers 8]
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

SCENARIOS = {
    "nominal": (None, "rmse_h_pre"),
    "jam_cw": (dict(kind="jam_cw", onset_s=120.0, duration_s=180.0, severity=0.5), "rmse_h_att"),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=600.0)
    ap.add_argument("--seeds", type=int, nargs="+", default=[500, 501, 502, 503, 504])
    ap.add_argument("--kappa-r", type=float, default=DEFAULT_KAPPA_R)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--weights", type=str, default=str(ROOT / "results" / "m1" / "detector_weights_sup_v1.npz"))
    ap.add_argument("--out", type=str, default=str(ROOT / "results" / "m1" / "defended_vs_undefended_v1.json"))
    args = ap.parse_args()
    weights_path = Path(args.weights)

    specs = []
    for scen_name, (atk, _metric) in SCENARIOS.items():
        for method in METHOD_NAMES:
            for seed in args.seeds:
                specs.append(RunSpec(
                    name=f"dvu_{scen_name}_{method}_{seed}", master_seed=seed, method=method,
                    duration_s=args.duration, hold_s=30.0, platform="ground", world="flat",
                    imu_grade="industrial_mems", quantum_grade="field", gnss_rate_hz=1.0,
                    heading_noise_deg=2.0, attack=atk, kappa_R=args.kappa_r, kappa_Q=1.0,
                    detector_weights_path=str(weights_path) if weights_path.exists() else None,
                    record=False,
                ))

    t0 = time.time()
    results = run_many(specs, n_workers=min(args.workers, 8))
    wall = time.time() - t0

    table: dict[str, dict] = {}
    for scen_name, (_atk, metric) in SCENARIOS.items():
        by_method: dict[str, list] = {}
        for spec, res in zip(specs, results):
            scen = (spec.attack or {}).get("kind", "nominal")
            if scen != scen_name:
                continue
            by_method.setdefault(spec.method, []).append(res.get(metric, float("nan")))

        undefended = np.array(by_method.get("undefended", []), dtype=float)
        sigma_nom = float(np.nanstd(undefended)) if len(undefended) > 1 else float("nan")
        mean_undefended = float(np.nanmean(undefended)) if len(undefended) else float("nan")
        rows = {}
        for method, vals in by_method.items():
            vals = np.array(vals, dtype=float)
            mean_val = float(np.nanmean(vals))
            threshold = mean_undefended + 3.0 * sigma_nom
            worse_than_undefended_by_3sigma = bool(mean_val > threshold) if np.isfinite(threshold) else None
            rows[method] = dict(metric=metric, mean=mean_val, per_seed=vals.tolist(),
                                 threshold_undefended_plus_3sigma=threshold,
                                 PASS=(not worse_than_undefended_by_3sigma) if worse_than_undefended_by_3sigma is not None else None)
        table[scen_name] = dict(metric=metric, sigma_nom=sigma_nom, mean_undefended=mean_undefended, methods=rows)

    out = dict(label="D-048 defended-vs-undefended check, tuning seeds, kappa_R PROVISIONAL",
               seeds=args.seeds, duration_s=args.duration, kappa_R=args.kappa_r,
               weights_used=str(weights_path), wall_s=wall, scenarios=table)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf8")
    for scen_name, row in table.items():
        print(f"[{scen_name}] metric={row['metric']} sigma_nom={row['sigma_nom']:.4f} "
              f"mean_undefended={row['mean_undefended']:.4f}")
        for method, m in row["methods"].items():
            print(f"  {method:16s} mean={m['mean']:.4f}  PASS={m['PASS']}")
    print(f"written to {args.out}  wall={wall:.1f}s")


if __name__ == "__main__":
    main()
