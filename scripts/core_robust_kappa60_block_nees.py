"""Item 5: per-block NEES at the chosen kappa_R=60 (CORE-ROBUST session,
post D-043/D-057/D-058 fixes). CAI ON, industrial_mems, tuning seeds
500-504, 10 min. Reuses core_robust_overconfidence_diag.run_one by
monkey-patching its module-level KAPPA_R constant.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import core_robust_overconfidence_diag as diag  # noqa: E402

diag.KAPPA_R = 60.0


def main() -> None:
    print("=== item 5: per-block NEES at kappa_R=60, CAI ON, tuning seeds "
          f"{diag.SEEDS}, {diag.DURATION_S:.0f}s ===\n")
    p_all, v_all, rp_all, yaw_all, ba_all, bg_all = [], [], [], [], [], []
    for seed in diag.SEEDS:
        rows = diag.run_one(seed, True)
        p_all += rows["p"]
        v_all += rows["v"]
        rp_all += [x[0] for x in rows["psi"]]
        yaw_all += [x[1] for x in rows["psi"]]
        ba_all += rows["ba"]
        bg_all += rows["bg"]
    print(f"n_epochs={len(p_all)}")
    print(f"  p   NEES(3dof,ideal 3)  mean={np.mean(p_all):.2f}")
    print(f"  v   NEES(3dof,ideal 3)  mean={np.mean(v_all):.2f}")
    print(f"  psi_rp  NEES(2dof,ideal 2)  mean={np.mean(rp_all):.2f}")
    print(f"  psi_yaw NEES(1dof,ideal 1)  mean={np.mean(yaw_all):.2f}")
    print(f"  b_a NEES(3dof,ideal 3)  mean={np.mean(ba_all):.2f}  (metric artifact -- see "
          "core_robust_ba_nees_artifact_check.py; effective-bias truth brings this to ~19)")
    print(f"  b_g NEES(3dof,ideal 3)  mean={np.mean(bg_all):.2f}")


if __name__ == "__main__":
    main()
