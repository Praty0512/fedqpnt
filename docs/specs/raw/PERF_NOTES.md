# PERF agent notes

Scope per Master task: cut wall time per simulated node-hour, bit-identical
outputs required, `fedqpnt/fusion/eskf.py`/`trust/*`/`node/*`/`fl/*`/
`fleet/*`/`eval/*` off-limits (other agents own them). Profile source:
docs/specs/raw/FUSION_NOTES.md, "Item 3 (runtime profile, R-3)".

## What changed

`fedqpnt/sim/rotations.py`: added single-sample fast paths to `so3_exp` and
`dcm_to_euler` that short-circuit on `phi.shape == (3,)` / `C.shape == (3,3)`
(the overwhelmingly common per-tick call shape) and compute the exact same
scalar arithmetic as the existing N=1 batch path, but skip the
`reshape`/`np.broadcast_to`/batched-matmul/`np.stack` machinery whose
`numpy.moveaxis` internals were a measured hotspot (5.0s of the 326.7s
cProfile total, FUSION_NOTES.md). Batch (N>1) calls -- e.g. whole-trajectory
generation in `fedqpnt/sim/trajectory.py` -- are untouched, still go through
the original vectorised code path.

No changes to `fedqpnt/sensors/imu.py`, `fedqpnt/sensors/quantum.py`,
`fedqpnt/gnss/*.py`, `fedqpnt/attacks/*.py`: their per-tick cost is
dominated by `rng.normal()` draws and small (3,)/(3,3) array arithmetic that
is already about as cheap as numpy allows without touching draw order or
associativity (forbidden -- would break bit-identity). No safe win found
there within the token/time budget.

## Bit-identical proof

`scripts/perf_bitident_check.py`: full node pipeline
(`fedqpnt.node.environment` + `fedqpnt.node.agent`), methods
`fedqpnt_local` and `fixed_trust`, seeds {101, 202, 303}, 60s each (5s
hold + init), dt=0.01. Captures per tick: IMU sample (f_b, omega_b),
quantum/CAI sample (valid, f_b), GNSS epoch obs count, GNSS fix
(pos, valid), full `NavSolution` (pos, vel, att, cov_pos, cov_vel,
acc_bias, gyro_bias), trust weights + attack_detected, clock bias -- 114
arrays total. Reference trace saved with `--save-before` BEFORE any edit;
`--compare` re-runs post-edit and checks `np.array_equal` (exact, no
tolerance) on every array. Result: **BIT-IDENTICAL, all 114/114 arrays
match exactly** across all 3 seeds x 2 methods x 60s.

## Benchmark (`scripts/perf_benchmark.py`, s / simulated-hour, wall clock)

| component                              | before  | after   | speedup |
|-----------------------------------------|--------:|--------:|--------:|
| rotations (so3_exp+dcm_to_euler, 1/tick) |  13.69  |   5.95  |  2.30x  |
| IMU (`ClassicalImu.step`)                |  10.49  |  10.95  |  ~1.0x (noise, unchanged) |
| GNSS (`GnssSignalModel.step`)            |   6.11  |   6.85  |  ~1.0x (noise, unchanged) |
| CAI (`QuantumAccelerometer.step`)        |   0.50  |   0.79  |  ~1.0x (noise, unchanged; small absolute numbers) |
| full node (`fedqpnt_local`, incl. eskf)  | 135.60  | 120.73  |  1.12x  |

(Machine is shared with several other agents' concurrent sweeps per the
task brief, so absolute wall-clock numbers are noisy; the "before" column
was measured by `git stash`-ing only `fedqpnt/sim/rotations.py` and
re-running the same benchmark script back-to-back with the "after" run, to
keep the comparison as apples-to-apples as load noise allows.)

Full-node speedup is modest (1.12x) because `ESKF.propagate`/`correct`
(off-limits, dominant cost per FUSION_NOTES.md: 98.2s self-time of 326.7s
cProfile total, plus the 11.4s `eigvalsh` PSD check and 11.3s coning
`np.cross` inside it) is untouched; the rotations fast path only removes
the moveaxis/batch overhead layered on top of the two functions PERF is
allowed to touch.

## Deferred ideas (for Master to route to the eskf.py-owning agent, or to
## decide are worth a non-bit-identical accuracy trade)

All of these were flagged in FUSION_NOTES.md and require touching
`fedqpnt/fusion/eskf.py` (off-limits for PERF) or would change floating-point
results (forbidden by the bit-identical constraint):

1. **`np.linalg.eigvalsh` PSD hygiene check (11.4s / 326.7s cProfile
   total)** -- called on every propagate+correct (363,600x) purely to test
   one scalar bound (P PSD floor). A Cholesky-attempt short-circuit (O(n^3/3),
   fails fast on non-PSD) or checking every K ticks instead of every tick
   would be much cheaper. Either changes numerical behaviour (Cholesky
   failure modes differ from eigvalsh, and skipping ticks changes when a
   correction is triggered) or is at minimum a judgment call on acceptable
   risk -- not a pure bit-identical refactor, so left to the eskf.py owner.
2. **F/G/Phi/Qd per-tick allocation (part of the 98.2s propagate self-time)**
   -- static zero/identity blocks are rebuilt fresh every tick; hoisting them
   into preallocated buffers reused across ticks is plausible bit-identical
   arithmetic (same operations, no reassociation) but touches eskf.py's
   state-carrying internals, out of PERF's ownership -- risk of interfering
   with the concurrent D-028 Q-inflation work another agent is doing there
   (per fedqpnt/node/methods.py comments).
3. **Coning-term `np.cross` inside `ESKF.propagate` (11.3s)** -- same
   off-limits-file constraint as above.
4. **Non-bit-identical option**: if the Master later decides exact bit
   reproducibility is not required for a given sweep (e.g. an exploratory
   run, not one feeding a frozen kappa_R/regression baseline), float32 state
   arrays or BLAS-threaded batched matmuls in `ESKF.propagate` would likely
   give a larger speedup than anything PERF found in its allowed files --
   but that is explicitly forbidden by this task's hard constraint #1 and is
   flagged here only as a possibility for a future, differently-scoped task.

## Deliverables

- `scripts/perf_bitident_check.py` -- equivalence harness (`--save-before`,
  `--compare`).
- `scripts/perf_benchmark.py` -- s/sim-hour benchmark for node/rotations/IMU/
  GNSS/CAI.
- `fedqpnt/sim/rotations.py` -- single-sample fast paths, `so3_exp` /
  `dcm_to_euler`.
- This file.
