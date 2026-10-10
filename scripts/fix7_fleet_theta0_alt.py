"""FIX7: run minimatrix phase 2 with an ALTERNATIVE fleet theta0 (patches fleet_adapter.THETA0_PATH in-process; no repo state change).
Usage: python scripts/fix7_fleet_theta0_alt.py <theta0.npz> <minimatrix.py args...>"""
import sys, runpy
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import fedqpnt.eval.fleet_adapter as FA
FA.THETA0_PATH = Path(sys.argv[1])
sys.argv = [str(REPO / "scripts" / "minimatrix.py")] + sys.argv[2:]
runpy.run_path(sys.argv[0], run_name="__main__")
