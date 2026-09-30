"""D-068 pre-registration: sigma_nom per IMU grade. Undefended method, nominal scenario (same config as the
smoke-matrix nominal: ground, flat, 600 s, hold 30 s, field CAI, kappa_R default), tuning seeds 560-579
(n=20), each grade separately. sigma_nom = across-seed sample std (ddof=1) of rmse_h_pre (whole-mission RMSE_h
for nominal). Writes results/sigma_nom.json in the layout metrics.load_sigma_nom expects (top-level
"sigma_nom_m": {grade: metres}) plus a "detail" block per grade.

Usage: python scripts/core_robust_sigma_nom.py [--workers 4]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fedqpnt.node.runner import RunSpec, run_many  # noqa: E402

GRADES = ("industrial_mems", "tactical")
SEEDS = list(range(560, 580))


def _git() -> tuple[str, str]:
    h = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    s = subprocess.run(["git", "status", "--porcelain", "fedqpnt/"], capture_output=True, text=True,
                       cwd=ROOT).stdout.strip().replace("\n", "; ")
    return h, (s or "clean")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=str(ROOT / "results" / "sigma_nom.json"))
    a = ap.parse_args()
    head0, status0 = _git()
    print(f"git at launch: HEAD={head0} status[fedqpnt/]={status0}", flush=True)
    detail, sig = {}, {}
    for g in GRADES:
        specs = [RunSpec(name=f"sigmanom_{g}_{s}", master_seed=s, method="undefended", duration_s=600.0,
                         hold_s=30.0, platform="ground", world="flat", imu_grade=g, quantum_grade="field",
                         gnss_rate_hz=1.0, heading_noise_deg=2.0, attack=None, detector_weights_path=None,
                         record=False) for s in SEEDS]
        res = run_many(specs, n_workers=min(a.workers, 4))
        vals = [float(r["rmse_h_pre"]) for r in res]
        sd = float(np.std(vals, ddof=1))
        sig[g] = sd
        detail[g] = dict(sigma_nom_m=sd, n=len(vals), seeds=SEEDS, mean_rmse_h=float(np.mean(vals)),
                         per_seed=vals, definition="D-068")
        Path(a.out + f".partial_{g}.json").write_text(json.dumps(detail[g]), encoding="utf8")   # crash-safe
        print(f"{g}: sigma_nom={sd:.4f} m  mean_rmse_h={np.mean(vals):.4f}  n={len(vals)}  "
              f"min={min(vals):.3f} max={max(vals):.3f}", flush=True)
    head1, status1 = _git()
    for g in GRADES:
        detail[g].update(git_head=head0, git_status=status0, git_head_end=head1, git_status_end=status1)
    out = dict(sigma_nom_m=sig, detail=detail, definition=("D-068: sample std (ddof=1) across tuning seeds "
                                                            "560-579 of rmse_h_pre, undefended, nominal, 600 s"))
    Path(a.out).write_text(json.dumps(out, indent=2), encoding="utf8")
    print("git at end:", f"HEAD={head1} status[fedqpnt/]={status1}", flush=True)
    print("written", a.out)


if __name__ == "__main__":
    main()
