"""WP-8.1 M1 smoke matrix: seeds 500-504, 10-min ground runs, medium-severity
attacks from fedqpnt.attacks, crossed with the method table. FUNCTIONAL CHECK
ONLY -- "M1 smoke, tuning seeds, not for publication" (not a scientific
result; see ARCHITECTURE.md section 7 for the real 30-test-seed protocol).

Usage: python scripts/run_m1_smoke.py [--duration 600] [--workers N]
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

from fedqpnt.node.runner import RunSpec, run_many  # noqa: E402
DETECTOR_WEIGHTS = ROOT / "results" / "m1" / "detector_weights.npz"

SCENARIOS = {
    "nominal": None,
    "drift_spoof": dict(kind="drift_spoof", onset_s=120.0, duration_s=180.0, severity=0.5),
    "meaconing": dict(kind="meaconing", onset_s=120.0, duration_s=180.0, severity=0.5),
    "jam_cw": dict(kind="jam_cw", onset_s=120.0, duration_s=180.0, severity=0.5),
}
METHODS = ("fedqpnt_local", "baseline_a", "baseline_b_bin", "baseline_b_cont", "bprime", "undefended")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=600.0)
    ap.add_argument("--seeds", type=int, nargs="+", default=[500, 501, 502, 503, 504])
    ap.add_argument("--kappa-r", type=float, default=40.0)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--out", type=str, default=str(ROOT / "results" / "m1" / "smoke_matrix.json"))
    args = ap.parse_args()

    specs = []
    for scen_name, atk in SCENARIOS.items():
        for method in METHODS:
            for seed in args.seeds:
                specs.append(RunSpec(
                    name=f"m1_{scen_name}_{method}_{seed}", master_seed=seed, method=method,
                    duration_s=args.duration, hold_s=30.0, platform="ground", world="flat",
                    imu_grade="industrial_mems", quantum_grade="field", gnss_rate_hz=1.0,
                    heading_noise_deg=2.0, attack=atk, kappa_R=args.kappa_r, kappa_Q=1.0,
                    detector_weights_path=str(DETECTOR_WEIGHTS) if DETECTOR_WEIGHTS.exists() else None,
                    record=False,
                ))

    t0 = time.time()
    results = run_many(specs, n_workers=args.workers)
    wall_total = time.time() - t0

    # group by (scenario, method)
    table: dict[str, dict[str, list]] = {}
    for spec, res in zip(specs, results):
        scen = (spec.attack or {}).get("kind", "nominal")
        key = f"{scen}|{spec.method}"
        table.setdefault(key, []).append(res)

    summary = []
    for key, rows in table.items():
        scen, method = key.split("|")

        def mean_of(field):
            import numpy as np
            vals = [r.get(field, float("nan")) for r in rows]
            vals = [v for v in vals if v is not None]
            return float(np.nanmean(vals)) if vals else float("nan")

        summary.append(dict(
            scenario=scen, method=method, n_seeds=len(rows),
            rmse_h_pre=mean_of("rmse_h_pre"), max_h_pre=mean_of("max_h_pre"),
            rmse_h_att=mean_of("rmse_h_att"), max_h_att=mean_of("max_h_att"),
            rmse_h_post=mean_of("rmse_h_post"), max_h_post=mean_of("max_h_post"),
            latency_on=mean_of("latency_on"), t_rec=mean_of("t_rec"),
            rmse_t_ns=mean_of("rmse_t_ns"), max_t_ns=mean_of("max_t_ns"),
            mean_w_gnss=mean_of("mean_w_gnss"), far_per_hour=mean_of("far_per_hour"),
            wall_s_per_run=mean_of("wall_s"),
        ))

    n_sim_hours = sum(s.duration_s for s in specs) / 3600.0
    out = dict(label="M1 smoke, tuning seeds, not for publication",
               kappa_R_status="PROVISIONAL (D-028: ESKF process model changing concurrently; "
                              "re-run after it lands, see results/m1/kappa_r_frozen.json)",
               n_runs=len(specs), wall_total_s=wall_total,
               sim_hours_total=n_sim_hours, wall_s_per_sim_hour=wall_total / max(n_sim_hours, 1e-9),
               kappa_R=args.kappa_r, seeds=args.seeds, duration_s=args.duration, summary=summary)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf8")
    print(f"wall_total={wall_total:.1f}s  sim_hours={n_sim_hours:.3f}  "
          f"wall_s_per_sim_hour={wall_total/max(n_sim_hours,1e-9):.1f}")
    print(f"written to {args.out}")


if __name__ == "__main__":
    main()
