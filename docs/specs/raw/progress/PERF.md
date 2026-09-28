# PERF agent progress

## Done
- Read profile (docs/specs/raw/FUSION_NOTES.md "Item 3"): hotspots outside
  eskf.py that PERF may touch are `ClassicalImu._AxisChannel.step` (28.2s),
  `rotations.so3_exp` (22.1s), `rotations.dcm_to_euler` (6.8s), and
  `numpy.moveaxis` batch-reshape overhead (5.0s) paid by both.
- Wrote `scripts/perf_bitident_check.py`: runs the full node pipeline
  (fedqpnt.node.environment + fedqpnt.node.agent), methods
  `fedqpnt_local` and `fixed_trust`, 3 seeds x 60s, captures IMU/quantum/
  GNSS-epoch/fix/NavSolution/trust/clock per tick into one npz trace.
  `--save-before` snapshots reference, `--compare` re-runs and checks
  np.array_equal (exact) on every array.
- Saved BEFORE reference trace (scratchpad/perf_before.npz, 114 arrays)
  BEFORE any source edit.

- Single-sample fast paths in fedqpnt/sim/rotations.py for so3_exp /
  dcm_to_euler (avoid moveaxis/batch-matmul overhead on N=1 calls, same
  arithmetic as batch path). Verified BIT-IDENTICAL via
  perf_bitident_check.py --compare (114/114 arrays match).
- scripts/perf_benchmark.py written and run before/after (via git stash of
  just rotations.py). Speedup: rotations 13.69s->5.95s/simhour (2.30x),
  full node 135.60s->120.73s/simhour (1.12x); IMU/GNSS/CAI unchanged
  (not touched, no safe win found).
- docs/specs/raw/PERF_NOTES.md written with full table + deferred ideas
  (eigvalsh PSD check, F/G hoisting, coning cross -- all require eskf.py,
  off-limits).

- Required test suite: `python -m pytest tests/test_sensors_*.py
  tests/test_gnss_*.py tests/test_attacks_*.py tests/test_sim_*.py -q`
  -> all green, exit code 0 (174 dots, 100%).

## Next
- Task complete. PERF handed final report back to Master.

## Background PIDs / output paths
- None running in background. perf_before.npz at:
  C:\Users\DELL\AppData\Local\Temp\claude\C--Users-DELL-Downloads-FEDQPNT\c48dadfb-ab52-4d01-a3c2-95547b6c76be\scratchpad\perf_before.npz

## Resume command
```
cd C:\Users\DELL\Downloads\FEDQPNT
python scripts/perf_bitident_check.py --compare "C:\Users\DELL\AppData\Local\Temp\claude\C--Users-DELL-Downloads-FEDQPNT\c48dadfb-ab52-4d01-a3c2-95547b6c76be\scratchpad\perf_before.npz"
```
