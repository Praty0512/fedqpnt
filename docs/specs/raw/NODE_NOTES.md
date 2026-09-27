# NODE_NOTES — WP-8.1 single-node integration (TESTING/INTEGRATION agent)

Implements ARCHITECTURE.md section 0 (node boundary), section 1.3-1.4
(per-tick sequence), section 4.4 (leakage guards), section 5 (methods as
config diffs), section 6 (metrics), section 7.6 (tuning discipline),
section 8 (single-node part), plus DECISION_LOG D-011, D-021..D-027.

## Ownership / files added

- `fedqpnt/node/environment.py` — Environment half: truth (hold + generated
  trajectory), IMU, CAI, GNSS signal, chained attacks. Emits ONLY sensor
  outputs (`EnvTick.imu/.quantum/.gnss_epoch`, the latter already
  `.for_agent()`-stripped) plus an evaluator-only side channel
  (`.truth/.label/.true_clk_bias_m/.true_clk_drift_mps`).
- `fedqpnt/node/agent.py` — Agent half: `GnssReceiver.solve` -> `ESKF`
  (`propagate` -> `innovations` -> `TrustEngine.update` -> `correct`) ->
  `NavSolution`, plus `fedqpnt.fusion.clock.ClockKF` for the timing solution.
  Never imports `fedqpnt.sim`/`fedqpnt.attacks`/`AttackLabel`/`TruthState`
  (transitively; enforced by `tests/test_node_leakage_guard.py`, which walks
  its whole `fedqpnt`-internal import graph, not just direct imports).
- `fedqpnt/fusion/clock.py` (NEW) — standalone 2-state (bias, drift) clock
  KF (D-025/D-027), trust-weighted like GNSS: `R_eff = R / max(w_gnss, 0.02)`;
  coasts on the drift-only process model whenever there is no valid/trusted
  fix.
- `fedqpnt/node/methods.py` — the seven-method table (section 5) as
  `AgentConfig` diffs over one code path (`fedqpnt.trust.trust_law` already
  implements the FULL section-5 method table internally — this module only
  selects the right key + `alpha_gate` + which methods load a trained
  detector), plus `pretrain_detector` (local-only stand-in for the M2 FL
  training loop).
- `fedqpnt/node/runner.py` — `run_single`/`run_many`/`RunSpec`; writes
  `runs/<id>/` via `fedqpnt.sim.recorder.RunRecorder`; `run_many` fans out
  over a real `multiprocessing` "spawn" process pool. `python -m
  fedqpnt.node.runner '<json>'` is a CLI entry used by the real-subprocess
  end-to-end test.
- `fedqpnt/eval/metrics.py` (NEW package) — section 6 formulas (RMSE/MAX/P95
  of e_h/e_3/e_v, ANEES, phases, detection latency/P_D, FAR/FPR,
  time-to-distrust, recovery time, trust cycles/TV_w, ROC-AUC) + the D-025
  timing metrics (clock-bias/drift error in ns, RMSE_t/MAX_t).

## Key integration decision (PROPOSED-DECISION, most-conservative reading)

`ESKF.innovations()` emits ONE joint 6-D `Innovation` (`sensor="gnss"`,
dof=6) for the loosely-coupled position+velocity update, but
`fedqpnt.trust.features.GnssFeatureExtractor` (x1/x2) expects two SEPARATE
3-D innovations named `"gnss_pos"`/`"gnss_vel"` — which is exactly what
ARCHITECTURE.md section 3.1's per-block formula specifies
(`nu_p^T (H_p P^- H_p^T + R_p)^-1 nu_p`, no cross-covariance term).
`fedqpnt/node/agent.py::_split_gnss_innovation` reproduces that per-block
split (dropping the pos/vel cross-covariance block, which the spec formula
never used either) purely for the trust engine's feature input. `ESKF.correct`
ignores its own `innovations` argument for anything but bookkeeping (it uses
internal `self._pending` state built by `innovations()`), so the split does
not change the actual EKF correction in any way.

## D-028 (Master heads-up, mid-WP): ESKF process model changing concurrently

Another agent is editing `fedqpnt/fusion/eskf.py` (dynamics-dependent Q
inflation for unmodelled IMU scale-factor/misalignment) WHILE this WP ran.
Consequences applied here:
- `kappa_R = 40` (below) is marked **PROVISIONAL** everywhere it is recorded
  (`fedqpnt/node/agent.py::AgentConfig.kappa_R`, `fedqpnt/node/methods.py::
  DEFAULT_KAPPA_R`, `results/m1/kappa_r_frozen.json`, `results/m1/
  smoke_matrix.json`) — changing Q_c changes the propagated P that ANEES is
  computed against, so this value must be RE-CHOSEN, by the same procedure,
  once D-028 lands.
- The tuning procedure is a committed, reusable script:
  `scripts/tune_kappa_r.py` (already existed from this WP; nothing new
  needed) — re-run as `python scripts/tune_kappa_r.py --seeds 10 --duration
  600.0` once D-028 is in.
- `fedqpnt/fusion/eskf.py` itself was NOT edited by this WP (out of scope
  per the original brief too).
- A sanity re-run (`run_single`, fixed-trust, 15 s) was executed after this
  notice to confirm eskf.py still imports/runs correctly at the time of
  writing; if a future run breaks because eskf.py is mid-edit, the fix is to
  re-run, never to patch fedqpnt/fusion/eskf.py from this WP.

## kappa_R tuning (section 7.6, D-023/D-027) -- PROVISIONAL, see D-028 above

Root cause (per D-027, unchanged): time-correlated GNSS errors (multipath/
tropo Gauss-Markov, tau = 20-1800 s) are treated as white by the loosely-
coupled position/velocity update, and the architecture deliberately does NOT
add a GNSS error state (D-023: doing so would let a slow drift-spoof be
absorbed as "correlated error", which is exactly the failure mode the
no-GNSS-error-state rule exists to prevent). `kappa_R` (GNSS fix-covariance
inflation) is the single knob that restores nominal ANEES ~= 1 given that
known, accepted limitation; it is chosen ONCE on tuning seeds only, for every
method alike, then frozen with its config hash (D-002/section 7.6 tuning
discipline). See `scripts/tune_kappa_r.py` and the EXECUTION_LOG / final
report for the frozen value and the measured ANEES.

## M1 smoke matrix

seeds 500-504, 10-min ground runs, medium-severity attacks from
`fedqpnt.attacks` (`drift_spoof`, `meaconing`, `jam_cw`), crossed with
{nominal} x {fedqpnt_local, baseline_a, baseline_b_bin, baseline_b_cont,
bprime, undefended} (`baseline_b_cont` doubling as `fixed_trust`'s
consistency check; see the final report table). This is a FUNCTIONAL check
that the whole node runs end-to-end for every method, NOT a scientific
result — labelled "M1 smoke, tuning seeds, not for publication" everywhere
it is reported, per the WP-8.1 brief.

## Known simplifications / PROPOSED-DECISIONs (flagged, not hidden)

1. **"FedQPNT-local" detector training.** The FL part (server aggregation,
   TRIM-NB-R) is M2 scope. `methods.pretrain_detector` trains ONE `TrustDetector`
   (mlp) offline on a handful of tuning seeds using the REAL hindsight
   pseudo-labeller (`fedqpnt.trust.pseudolabel.label_epochs`) fed a SURROGATE
   INS-GNSS divergence CUSUM (`surrogate_s_cusum`, computed from x1/nis_pos
   directly, exactly the same surrogate `tests/test_trust_pseudolabel.py`
   already documents as a stand-in for the real CAI-aided-INS reference).
   The same weights file is reused, for budget reasons, by every method that
   needs a "locally trained" detector (`fedqpnt_local`, `baseline_a`,
   `baseline_b_bin`, `baseline_b_cont`, and — for reporting-only bookkeeping,
   since their trust WEIGHT never depends on it — `fixed_trust`/`undefended`).
   In the real M2/FL experiment each node trains (and, for FedQPNT, exchanges)
   its own weights; this is a deliberate M1 simplification, not the final
   experimental design.
2. **x1/x2 unavailable during `pretrain_detector`.** That pretraining loop
   has no running ESKF (a second full fusion instance per training seed was
   judged out of the WP-8.1 token/time budget), so the innovation-based
   features (x1 `nis_pos`, x2 `nis_vel`) are always 0 there; the pseudo-label
   rule and the detector still see x3..x15 (RAIM, C/N0, AGC, clock jumps,
   cross-satellite structure), which is where most of the jamming/meaconing
   signal already lives per D-022/D-024. During REAL agent runs (`run_single`),
   x1/x2 are populated normally from the live ESKF innovations.
3. **`build_attack`** (environment.py) does not wire up
   `fedqpnt.attacks.jamming.JamThenSpoof` (it needs two pre-built sub-attack
   objects, not scalar kwargs) — not needed by the M1 smoke matrix, which
   uses one attack per scenario.

## Tests

`python -m pytest tests/test_node_*.py tests/test_eval_*.py -q` — see the
final report for the pass/fail line. Covers: the node-level leakage guard
(AST import-graph walk from `agent.py`); clock-KF consistency (convergence,
coasting, trust-weighted R_eff, invalid-fix rejection); every implemented
`fedqpnt.eval.metrics` formula against a synthetic input with a known,
hand-computed answer; one short end-to-end run per method executed as a
real `python -m fedqpnt.node.runner` subprocess.
