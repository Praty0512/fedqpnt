"""Profile one sim-hour of the ESKF pipeline (Master D-023 item 3). Not a
test; prints cProfile top-15 by cumulative time. Run manually.
"""
from __future__ import annotations

import sys, os, cProfile, pstats, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests._fusion_helpers import run_scenario


def main():
    pr = cProfile.Profile()
    pr.enable()
    run_scenario(platform="ground", imu_grade="industrial_mems", quantum_grade=None,
                 duration_s=3600.0, dt=0.01, seed=1, hold_s=10.0, kappa_R=40.0,
                 check_hygiene=False)
    pr.disable()
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
    ps.print_stats(15)
    print(s.getvalue())


if __name__ == "__main__":
    main()
