# CORE-ROBUST progress (resume notes)

## MASTER REJECTED ITEM 6 (round 2): jam non-recovery, meaconing, drift regressions found
Master's own read of smoke_matrix_core_robust_v2.json: fedqpnt_local WORSE than undefended in
every attack (drift 121.7 vs 107.7; meaconing 22.3 vs 2.5; jam_cw att 282 vs 269 AND
post-attack 314 vs 3.1 -- never recovers). Directed to diagnose 4 questions in order with
per-epoch traces, NOT "pass vs threshold" framing. Constraint: <=4 worker processes (H2-ABRUPT
needs CPU).

### Q1 jam non-recovery: CONFIRMED Master's hypothesis, plus a SECOND bug, BOTH FIXED
Trace script `scripts/core_robust_jam_recovery_trace.py` (fedqpnt_local, seed 500, jam_cw
onset=120 dur=180 sev=0.5, kappa_R=60). Log: `scratchpad/jam_trace_v2.txt` (pre-fix),
`scratchpad/jam_trace_v4.txt` (post-fix).

Pre-fix trace: during the ~180s outage (fix invalid throughout), w_gnss FROZEN at 0.9998
(gnss_law.step never called when fix invalid -- expected), err_h grows unbounded to ~167m
(pure INS coasting, also expected/correct given no valid fix). At t=302 (first valid fix after
outage): es_evidence=1, stat=936.83 vs gate=16.27 (confirms Master's hypothesis exactly:
`_last_p_prior`/`_last_gnss_pos` stale from before the outage, so Delta p_INS spans the WHOLE
outage while Delta p_GNSS spans one epoch). This false-fires E_s, locks w_gnss to ~0.02-0.03.
SECOND, EXTRA bug found: even after implementing Master's fix (reset baseline on long gap),
ONE MORE false fire occurred at the NEXT epoch (t=303, stat=763 vs gate=16.27) -- because
`_last_p_prior` stores the PRE-correction estimate, and the first post-gap epoch applies a
large corrective pull (soft gating never fully rejects it, err_h dropped 122.9->13.5m in ONE
epoch); the epoch after that pull sees the pull itself as "Delta p_INS", causing a second
false fire and re-locking trust for another ~10 epochs.

FIX CHOSEN: Master's option (a) -- reset the baseline (not scale the gate by elapsed-time
covariance) -- PLUS a 2-epoch quarantine (not just 1) to cover both the stale-baseline epoch
AND the corrective-pull epoch that follows it. New `TrustLawConfig.es_nominal_epoch_s`
(=1.0s [ASSUMPTION, matches project's standard GNSS rate]) and `es_gap_reset_factor` (=1.5,
per Master's directive). New `TrustEngineImpl._es_position_quarantine` counter. New
`_physical_spoof_evidence(..., skip_position=...)` parameter. All in
`fedqpnt/trust/trust_law.py`.

POST-FIX trace (`jam_trace_v4.txt`): es never fires during the whole recovery; w_gnss climbs
SMOOTHLY and MONOTONICALLY from 0.50 (t=302) to 0.91 (t=323) to ~1.0 shortly after; err_h
converges to ~1.3-1.5m by t=313 (13s after the outage ends) and stays there. No lockout, no
re-firing, no oscillation.

New regression test: `tests/test_trust_law_es_position.py::test_post_gap_reset_prevents_jam_recovery_lockout`
(4-epoch scenario: normal -> 180s-gap epoch with ~150m apparent INS drift -> quarantined
epoch -> quarantine-expired epoch with a genuine abrupt jump that MUST still fire, proving the
fix doesn't disable detection permanently). Full `tests/test_trust_law_es_position.py` (8
tests) PASSES. Full suite re-run in progress: `scratchpad/suite_after_jamfix.log` (background
task bwg9sapji).

### Q2 meaconing: DIAGNOSED (design limitation, not a quick-fix bug; no code change applied)
Trace: `scripts/core_robust_attack_trace.py meaconing`, log `scratchpad/meaconing_trace.txt`.
At onset (t=121): x8 (clk_jump feature) spikes to 250.1 sigma (>> es_clk_sigma=5.0) -> E_s
clk_event correctly fires (a REAL clock-bias jump IS present -- meaconing's common-mode replay
delay is physically a clock artifact, Psiaki & Humphreys 2016). w_gnss crashes to w_min=0.02
within 4 epochs and STAYS there (w < w_excl=0.05 in eskf.correct -> GNSS position update is
FULLY EXCLUDED every epoch, not soft-gated -- w_excl is a separate Sec 2.7 mechanism from the
D-057 NIS soft-gating fix; soft gating never even gets a chance to run). Meanwhile x1 (nis_pos,
the position innovation) STAYS TINY throughout (0.001-0.37, same order as clean nominal) --
the GNSS position fix itself is essentially undisturbed by meaconing (physically expected: a
common-mode range delay across all satellites is nearly degenerate with clock bias in the
navigation solution geometry, so it barely perturbs position). err_h grows from ~2m to ~32m
over 60s purely from the resulting free-inertial coasting (position corrections excluded),
NOT from a bad GNSS fix. undefended's 2.5m is NOT "soft gating neutralising meaconing" (its
alpha_gate=0, w=1 always -- gating/trust play no role at all for undefended); it is simply
that the underlying fix stays good, so blindly accepting it costs nothing.
ROOT CAUSE: a single scalar "gnss" trust weight conflates POSITION trust and CLOCK trust. A
genuine clock-only anomaly (meaconing) correctly triggers distrust, but the current design has
no way to keep trusting position while distrusting clock, so trust correctly detecting an
attack forces an unnecessarily large position-side cost. This is an ARCHITECTURAL limitation
(TrustState.weights has one "gnss" weight consumed by both ESKF position/velocity correction
and ClockKF), not a localized bug in trust_law.py/eskf.py. NO FIX APPLIED without further
Master direction -- flagged as PROPOSED-DECISION in the final report.

### Q3 drift: DIAGNOSED (correct, intended full-exclusion defence; not a bug)
Trace: `scripts/core_robust_attack_trace.py drift_spoof`, log `scratchpad/drift_trace.txt`.
raw_p (ML detector's calibrated spoof/jam probability) rises to 0.85-0.99 within 1-2 epochs of
onset and STAYS high throughout -- the detector correctly identifies the drift attack (via
C/N0/other features, NOT via nis_pos: x1 stays tiny, 0.001-0.09, confirming drift_spoof's
smooth carry-off deliberately produces almost no per-epoch position-innovation signature, by
design -- ARCHITECTURE.md's whole point of a "drift-in" attack). w_gnss correctly crashes to
w_min=0.02 and stays there (same w_excl full-exclusion mechanism as Q2) for the entire attack:
this IS the intended, correct response to sustained, confidently-detected spoofing. The
resulting error growth (to ~31.7m by 60s into the attack, in the fixed run) is pure
free-inertial MEMS coasting drift, traded against undefended's behavior of simply following
the spoof's own (bounded, ramped) drift-off from truth. For THIS attack configuration
(severity=0.5, 180s), the two costs are comparable in magnitude (fedqpnt_local's coasting-drift
cost is only modestly larger than undefended's spoof-following cost) -- this is the SAME
tension already flagged in item 6(ii)'s D-055 safety-principle sweep (1-5% RMSE excess vs
undefended failing the literal 3sigma_nom bound). NOT a new bug; NO FIX APPLIED (there is no
"wrong exclusion" here -- the exclusion is correct and working as designed; the cost is
inherent to correctly rejecting a confidently-detected, sustained spoof with an inertial-only
navigation fallback).

### D-062 git state (recorded at launch and end of the Q4 runs)
Launch: HEAD=112bfcfe7708e5c1a6ddae7c3398b595acf52bfc, `git status --porcelain fedqpnt/` = M
fedqpnt/fusion/eskf.py, M fedqpnt/trust/trust_law.py (my own items 1/2/3+jam-fix edits, nothing
else). End (after both runs completed): SAME HEAD, SAME two modified files -- confirmed no
fedqpnt/ edits happened while the evaluation runs were live.

### Q4 RESULTS (DONE)
`results/m1/smoke_matrix_core_robust_v3.json` (wall=1855.9s, --workers 4) and
`results/m1/s1_far_check_core_robust_v3.json` (wall=1404.5s, --workers 4), both post-jam-fix.
S1: fedqpnt_local FAR=0.0/h, ANEES_pos=0.875, mean_w_gnss=0.971, RMSE ratio (fedqpnt/fixed_trust)
= 0.9877. Smoke matrix drift_spoof/meaconing unchanged from pre-fix (121.7/107.7 and 22.3/2.5 --
expected, no code change applied to those paths). jam_cw IMPROVED: att RMSE 282.4 (same as
before -- during-attack behavior unaffected, expected), **post RMSE 314.29 -> 35.53** (8.8x
better), max_post 1163.4 -> 156.7, mean_w_gnss(att) 0.817 -> 0.883. Residual gap vs
baseline_b_bin's post=3.07 remains (not fully matching a hard-switch law's recovery speed) --
not chased further this session. Full report SENT to Master via SubagentHandback with the raw
table (no PASS/FAIL framing) and the Q1-Q3 diagnosis.

## D-066 ROUND 5 (approvals: ClockKF holdover, shadow probe, shadow-consistent reacq, trust split)
STATE: WAITING for Master's "H2 telemetry landed" before the FIRST fedqpnt/ edit.
Git at last check: HEAD=d56b49051ea8d3b30f910f43bb9bbb9a4de1b2e9; fedqpnt/ dirty ONLY in
fedqpnt/fleet/node_runner.py (H2-ABRUPT's telemetry work, not mine).
Done while waiting: xfail-marked intended-behaviour tests written (remove pytestmark xfail when
implemented): tests/test_fusion_clock_holdover.py (needs ClockKFConfig.w_excl=0.05, skip update when
w<w_excl, P equals no-fix coast P), tests/test_trust_shadow_probe.py (needs SensorTrustLaw.step
kwarg es_position, .probe_shadow, probe success iff mean NIS<=chi2_6 99% (16.81) and no
clk/xsat/cn0 event; es_position superseded in PROBE).
q_bias check (Brown&Hwang two-state, range units): q_bias=c^2*h0/2, q_drift=c^2*2*pi^2*h_-2. TCXO
typical h0=2e-19 s, h_-2=2e-20 /s (Brown&Hwang Table) -> q_bias=9e-3 m^2/s, q_drift=3.6e-2
(m/s)^2/s. Current ClockKFConfig q_bias=1.0 (~110x above), q_drift=1e-3 (~36x below). Simulated
truth (gnss/signal.py ClockState): sigma_bias_rw=3e-2 m/sqrt(s) -> 9e-4 m^2/s, sigma_drift_rw=3e-3
-> 9e-6. Citation source (Brown&Hwang) is NOT in refs.bib/REFERENCES as far as grepped -> flag TODO.
Decision on changing q_bias deferred until holdover implemented and its effect measured.
D-066 ADDENDUM (clock model): TCXO, Brown&Hwang two-state, h0=2e-19 s, h_-2=2e-20 1/s ->
q_bias=c^2*h0/2~9e-3 m^2/s, q_drift=c^2*2pi^2*h_-2~3.6e-2 (m/s)^2/s. Set BOTH truth
(fedqpnt/gnss/signal.py ClockState: sigma_bias_rw=sqrt(q_bias)~0.0949, sigma_drift_rw=sqrt(q_drift)
~0.19) AND ClockKFConfig (q_bias, q_drift) as part of change (i) with holdover; provenance in code
comments; truth was ~4000x too quiet in drift so old holdover/timing results flattered the defence.
Done (non-fedqpnt): docs/REFERENCES.md entry "[TO VERIFY by user]" (not in refs.bib);
tests/test_clock_nees_consistency.py (xfail-marked): truth/filter share values and mean clock NEES
over 20 seeds x 600 epochs within chi2_2 bounds. STILL waiting for "H2 telemetry landed" (no
fedqpnt/ edits yet).
CITATIONS VERIFIED by user (Consensus): h0=2e-19 s, h_-2=2e-20 1/s (h_-1=7e-21 not modelled),
attributed to Brown & Hwang in Krawinkel & Schon 2021, NAVIGATION, doi:10.1002/navi.444;
q_b=h0/2 and q_d=2*pi^2*h_-2 from Qin et al. 2021, Sensors 21:466, doi:10.3390/s21020466.
q_drift=3.55e-2 m^2/s^3 (note: my docstring in tests says ~3.6e-2, fine). Use all three in
change (i) provenance comments. REFS agent edits REFERENCES.md/refs.bib: I must NOT touch them (my
earlier "[TO VERIFY]" REFERENCES.md entry is theirs to reconcile). Still waiting for "H2 telemetry landed".
ORDER after go: (i) ClockKF holdover, (ii) shadow probe + reacq consistency, (iii) trust split
(weights["gnss"]=min alias; mean_w_pos/mean_w_clk over attack window AND whole mission), each with
tests + full suite green + git state per D-062; then ONE combined re-verification at MEMS+tactical
(smoke 7 methods, coasting A-script @179, S1 FAR, safety sweep, drift trace tactical seed 500).

## D-065 ROUND 4 (resume after auto-mode outage). Master committed core at 906ae98.
Git at start: HEAD=906ae9830b634552cfec2561d8711fdbf52155c2, fedqpnt/ clean.
- A-fix: coasting script marks now 60/120/179 (was 180 = post-outage, INVALID column); re-run
  would take >10 min so NOT re-run; old "@180s" column values must be treated as invalid. 60/120
  columns and RMSE/max remain valid.
- mean_w_gnss (runner.py:197) = mean over ALL ticks of the WHOLE mission (not attack window).
- E (drift contradiction): trace script scripts/core_robust_drift_probe_trace.py (tactical,
  seed 500, state/w/E_s/raw_p/err_h/spoof offset), log scratchpad/drift_tactical_trace.txt,
  running (bg task byjlos2ew). NO fedqpnt edits. Then propose fix.
- E DONE (diagnosis): log scratchpad/drift_tactical_trace.txt. Master hypothesis CONFIRMED (see
  final report). D note written: docs/specs/raw/TRUST_SPLIT_DESIGN.md. C trace, B still pending.
- B (ClockKF hold-exclusion, q_bias citation): wait for Master's go (H2-ABRUPT telemetry).
- C trace, D design note (Write to docs/specs/raw/TRUST_SPLIT_DESIGN.md failed by outage; content
  drafted in this session, must be re-written): pending.

## D-063 ROUND 3 (Master accepted the jam fix; commit pending; NO fedqpnt/ edits until told)
Git state at start of round 3: HEAD=112bfcfe7708e5c1a6ddae7c3398b595acf52bfc,
`git status --porcelain fedqpnt/` = M fedqpnt/fusion/eskf.py, M fedqpnt/trust/trust_law.py
(same as end of round 2 -- unchanged).

Tasks (order A -> B -> C(proposal only) -> D(design note)), <=4 processes, NO fedqpnt/ edits:

**Task A (coasting envelope + tactical smoke matrix)**: LAUNCHED, background task **b9exmk10b**.
- New script `scripts/core_robust_coasting_envelope.py`: forces gnss_epoch=None for an exact
  180s window (no attack model involved -- pure measurement), grid imu_grade
  {industrial_mems, tactical} x CAI {on, off}, 5 seeds (500-504), reports RMSE/max over the
  outage + err_h at +60/120/180s. Log: `scratchpad/taskA_coasting_envelope.log`.
- Edited `scripts/run_m1_smoke.py` (scripts/, not fedqpnt/ -- allowed) to add `--imu-grade` and
  `--methods` CLI flags (previously hardcoded to industrial_mems and all 7 methods).
- Then runs `run_m1_smoke.py --imu-grade tactical --methods fedqpnt_local undefended
  baseline_b_bin bprime --workers 4` -> `results/m1/smoke_matrix_tactical_v1.json`, log
  `scratchpad/taskA_smoke_tactical.log`.
- Partial result so far (industrial_mems/CAI-ON row only): RMSE=257.05 max=645.45 @60s=36.71
  @120s=218.96 @180s=8.18 (mean across 5 seeds; per-seed @180s=[4.97,1.57,9.73,19.05,5.59] --
  high seed-to-seed variance, expected for a coasting-error metric that depends on trajectory
  dynamics during the outage window).

**Task B (ClockKF under meaconing): DONE.** `scripts/core_robust_clock_meaconing_trace.py`
(v2, first version had a units bug -- logged every IMU tick instead of every GNSS epoch, fixed
by gating on `tick.gnss_epoch is not None`). Log: `scratchpad/taskB_clock_meaconing_v2.log`.

CONFIRMED from reading `fedqpnt/fusion/clock.py` (READ ONLY): ClockKF.step DOES consume
w_gnss (`R = diag(r_bias,r_drift) / max(w_gnss, w_min)`) -- distrust inflates R, it does not
hard-skip the update.

ROOT CAUSE FOUND: `ClockKFConfig.q_bias = 1.0` (m^2/s continuous-time PSD) is a LARGE,
UNCONDITIONAL process-noise term added to P every epoch via `Q = q_bias*dt` in `_propagate`,
REGARDLESS of the trust weight. During meaconing, fix.clk_bias jumps to ~753m (matches
replay_delay_m=1500*severity(0.5)=750m) at onset. w_gnss crashes to w_min=0.02 within 4
epochs (as expected/correct), inflating R_eff to ~450 (=9/0.02) -- but P keeps growing by
q_bias*dt=1.0 m^2 EVERY epoch regardless, so the Kalman gain K=P/(P+R_eff) creeps back UP
over time even though R_eff itself never changes. Traced values (fedqpnt_local, seed 500):
est_bias climbs from 4.0m (t=120) through 46.5/59.7/69.2/79.3/90.7/103.3/117.2/132.1m
(t=121..128), i.e. the PER-EPOCH increment is GROWING (9.5, 10.1, 11.3, 12.6, 13.9, 14.9m/epoch)
even at w pinned at the 0.02 floor -- P is winning the tug-of-war against R_eff's inflation
the longer the attack persists. RESULT: attack-window RMSE_t = 2298.7ns for fedqpnt_local
(vs undefended's 2480.2ns -- only marginally better, because the "protection" from distrust
decays over the 180s window instead of holding). Nominal (no-attack) whole-mission RMSE_t =
13.7ns for BOTH methods (confirms the clock model itself is fine; the 1.3us number is
attack-specific, not a baseline artifact). POST-attack RMSE_t: fedqpnt_local=387.7ns is WORSE
than undefended's 198.6ns -- undefended's full-trust (w=1) fix snaps the KF back quickly once
meaconing ends (high gain, fast convergence); fedqpnt_local's elevated P (grown during the
"protected" period) takes longer to shrink back down even after trust returns to 1, since P
only shrinks via well-gained corrections, not just the passage of time. Whole-mission RMSE_t:
fedqpnt_local=1291.6ns, undefended=1366.5ns (matches the two numbers Master quoted almost
exactly, 1284 vs 1358ns).
ANSWER to "why is the timing error ~1.3us even when GNSS is excluded": it's NOT because
exclusion fails to work at all -- w_gnss correctly crashes to 0.02 -- it's because
ClockKFConfig.q_bias's UNCONDITIONAL (not trust-scaled) process noise lets P grow unbounded
during a sustained low-trust period, so the SAME w_min floor that fully protects the ESKF's
position states (which use w_excl-based hard exclusion, not just R-inflation) only partially
and TEMPORARILY protects the clock bias, because ClockKF has no w_excl-style hard-exclusion
floor -- it only ever inflates R (soft-scoring), which is exactly what q_bias's continuous
growth eventually overwhelms. PROPOSED-DECISION (no fix applied -- awaiting Master's commit
+ go-ahead): scale q_bias (and/or q_drift) down by the trust weight too (e.g.
`Q = q_bias*dt*max(w_gnss, w_min)` or similar), or add a w_excl-style hard skip to ClockKF
matching the ESKF's Sec 2.7 convention, so P does not grow unboundedly while GNSS is
confidently distrusted.

**Task C (post-jam residual)**: NOT YET STARTED. Plan: trace the recovery path with the ALREADY
-ACCEPTED jam fix (E_s gap-reset + 2-epoch quarantine) active, check whether the SensorTrustLaw
v2 PROBE state (T_probe=10s, w_probe=0.3 fixed during PROBE) is what caps the recovery slope
even once E_s stops firing (i.e. is a PROBE ramp, not E_s, now the bottleneck for the residual
35.5m vs 3.1m gap found in round 2's Q4). Propose a fix; DO NOT IMPLEMENT until Master's commit
lands and gives the go-ahead.

**Task D (position/clock trust split design note)**: NOT YET STARTED. Write
`docs/specs/raw/TRUST_SPLIT_DESIGN.md` covering w_pos/w_clk split, which evidence drives which
weight, state-machine implications, affected files/tests, effect on
`patent/CLAIMS_SKELETON.md` (READ ONLY), and flag whether a displaced-meaconer scenario variant
is needed (current meaconing model is effectively co-located -- position barely disturbed).

### Q4 re-verification: LAUNCHED (background task b858j98ql)
Full suite re-run after the jam fix CONFIRMED GREEN (`scratchpad/suite_after_jamfix.log`, exit
0, no F/E markers). Smoke matrix (`scratchpad/v3_smoke_matrix.log` ->
`results/m1/smoke_matrix_core_robust_v3.json`) THEN S1 far check
(`scratchpad/v3_s1_far_check.log` -> `results/m1/s1_far_check_core_robust_v3.json`), both
`--workers 4` per Master's CPU constraint. When done, read both, build the raw-numbers table
(no PASS/FAIL framing) with drift_spoof/meaconing/jam_cw x rmse_h_att/rmse_h_post/max_h_att/
max_h_post/mean_w_gnss for fedqpnt_local vs undefended (and the other methods for context),
and send the structured report per Master's 4 questions.

### Q4 re-verification: IN PROGRESS (superseded by "LAUNCHED" above; keeping for history)
Re-run smoke matrix + S1 far check with the Q1 fix applied, `--workers 4` (Master's CPU
constraint for H2-ABRUPT), full table including post-attack column, RAW NUMBERS ONLY (no
PASS/FAIL framing). Full suite re-run after the jam fix (`scratchpad/suite_after_jamfix.log`,
background task bwg9sapji) still running as of this checkpoint -- confirm green before/while
launching Q4's heavier campaign. NOT YET LAUNCHED as of this checkpoint.

Planned commands (run sequentially, not parallel, per the earlier BrokenProcessPool lesson):
```
python -u scripts/run_m1_smoke.py --kappa-r 60 --weights results/m1/detector_weights_sup_v2.npz --workers 4 --out results/m1/smoke_matrix_core_robust_v3.json > scratchpad/v3_smoke_matrix.log 2>&1
python -u scripts/run_m1_s1_far_check.py --kappa-r 60 --weights results/m1/detector_weights_sup_v2.npz --workers 4 --out results/m1/s1_far_check_core_robust_v3.json > scratchpad/v3_s1_far_check.log 2>&1
```
(scratchpad path prefix omitted above for brevity -- use the full path as in earlier commands.)

## STATUS: SESSION COMPLETE (STALE -- see "MASTER REJECTED ITEM 6" section above; item 6 is
back open, do not treat this file's older "COMPLETE" marker below as current)
All 6 items done. Final report sent via SubagentHandback. Full test suite green (final run,
`scratchpad/final_full_suite.log`, exit 0, no failure markers -- the earlier
test_fleet_adapter.py::test_local_only_detector_hash_changes_across_rounds failure, which was
pre-existing/out-of-scope (D-059), is no longer present in this final run). See
`docs/specs/raw/CORE_ROBUST_NOTES.md` for the terse writeup.


Scratchpad dir (all logs live here):
`C:\Users\DELL\AppData\Local\Temp\claude\C--Users-DELL-Downloads-FEDQPNT\c48dadfb-ab52-4d01-a3c2-95547b6c76be\scratchpad`

## DONE
- **Item 1** (`_hygiene` eigenvalue clip, D-043): `fedqpnt/fusion/eskf.py::ESKF._hygiene` --
  symmetrise + clip only negative eigenvalues (no additive floor). Regression test
  `tests/test_fusion_eskf.py::test_hygiene_eigenvalue_clip_exact_single_source_delta_ba` PASSES
  (sqrt(P_v) == sigma_ba*t at 300s to rtol 1e-6).
- **Item 2** (soft gating, D-057): `ESKFConfig.gating` = "soft" (new default) | "hard" (ablation),
  implemented in `ESKF.correct`. Tests added/updated in `tests/test_fusion_eskf.py`
  (`test_soft_gating_default_never_fully_rejects_abrupt_50m_jump`,
  `test_soft_gating_slowly_dragged_fix_never_fully_rejected`,
  `test_nis_gate_rejects_50m_jump_hard_gating_ablation`). ALL PASS.
- **Item 3** (E_s short-baseline jump test, D-058): `fedqpnt/trust/trust_law.py`
  `TrustEngineImpl._physical_spoof_evidence` position term replaced with
  d = Delta p_GNSS - Delta p_INS (one epoch), chi2_3(99.9%), using fix.cov_pos (t, t-1) +
  `es_ins_short_sigma_pos` (new TrustLawConfig field, [ASSUMPTION]=0.05m). New engine state
  `_last_gnss_pos`/`_last_gnss_cov`. New test file `tests/test_trust_law_es_position.py`
  (4 tests: abrupt fires, slow drift doesn't, filter self-divergence doesn't, no-history doesn't).
  ALL PASS. Full `pytest -k "trust or fusion or eskf"` PASSED (exit 0) after items 1-3.
- **Item 4(a)** time alignment: code-trace only (no runtime measurement needed) -- fix.t ==
  propagate t always (fedqpnt/node/environment.py tick() builds imu/gnss from the same truth
  sample; gnss/receiver.py solve() sets fix.t=epoch.t). Offset = 0 by construction.
- **Item 4(b)** per-block NEES CAI on/off, kappa_R=40, 5 seeds (500-504), 600s: see
  `scratchpad/overconf_diag.log`. CAI ON: p=3.58 v=1.98 psi_rp=4.64 psi_yaw=0.48 **b_a=522.09**
  b_g=7.10; CAI OFF: p=2.84 v=2.14 psi_rp=17.60 psi_yaw=0.64 b_a=67.83 b_g=4.24. CAI residual
  vs assumed R ratio 0.84-1.43 (roughly honest).
- **Item 4 follow-up** (Master's metric-artifact hypothesis, TESTED): script
  `scripts/core_robust_ba_nees_artifact_check.py`, log `scratchpad/ba_nees_artifact.log`.
  b_a NEES vs classical truth (turn_on+GM+RRW) = 522.19 (per-axis x=297 y=142 z=83); vs
  EFFECTIVE-bias truth (+ SF/misalignment aliasing M@(f_b*sf)-f_b) = **19.04** (x=9.68 y=5.51
  z=3.85). CONFIRMED: mostly a metric artifact (27x reduction), residual ~6.3x overconfidence
  still unexplained (not chased further per "diagnose, fix only if clear" instruction).
  CONCLUSION for item 4: no eskf.py/trust_law.py code fix applied (root cause is a NEES
  evaluation-definition artifact, not a filter defect); recommend future b_a NEES reporting use
  the effective-bias truth definition. PROPOSED-DECISION, not yet written to DECISION_LOG.
- **Item 5** kappa_R re-tune, `scripts/tune_kappa_r.py --seeds 5 --duration 600`, log
  `scratchpad/kappa_tuning.log`, output `results/m1/kappa_r_tuning.json`:
  kR=10:5.33 kR=20:2.70 kR=30:1.82 kR=40:1.38 kR=60:0.9499 kR=80:0.74 kR=120:0.54.
  **CHOSEN kappa_R = 60** (ANEES_pos=0.9499, within 1+-0.1 target). This is WITH the D-043/D-057
  core fixes applied (old κ_R=40 was tuned pre-fix).
  Per-block NEES at kappa_R=60 (DONE): p=2.61 v=2.03 psi_rp=4.84 psi_yaw=0.48 b_a=521.16
  (metric artifact, see item 4) b_g=7.31. Close to CAI-ON kappa_R=40 numbers (item 4b) except
  p is closer to ideal (2.61 vs 3.58).

## CRITICAL BUG FOUND AND FIXED (post item-6 first launch)
- First item-6 launch (chains b17ktblbp / bjaxuyjmj) revealed a SEVERE regression:
  S1 far check (`scratchpad/item6_s1_far_check.log`, DONE, wall=1149.6s) showed
  fedqpnt_local/baseline_b_cont (both trust_law_version=v2) with FAR=9.2/h (fail), mean
  w_gnss=0.184 (GNSS chronically distrusted on CLEAN nominal data!), RMSE ratio vs
  fixed_trust = 5.82 (threshold 1.05, FAIL). Chain B crashed (BrokenProcessPool, resource
  contention from running both chains at once -- do NOT do that again, run sequentially).
- ROOT CAUSE (found by direct diagnostic, `python -c` inline, not a background job): my D-058
  `_physical_spoof_evidence` position term used `nav_prior` (the previous AGENT TICK's
  corrected NavSolution, e.g. 0.01s old at 100 Hz IMU rate) as the Delta p_INS baseline, but
  Delta p_GNSS spans a full GNSS epoch (e.g. 1s at 1 Hz). So Delta p_INS captured only ~0.01s
  of INS growth while Delta p_GNSS captured ~1s of real motion -- d was dominated by ordinary
  vehicle motion, not spoofing. Measured: fired on 239/300 (80%) of epochs on a totally clean
  nominal run.
- FIX (`fedqpnt/trust/trust_law.py`): added `TrustEngineImpl._last_p_prior` (the engine's OWN
  previous-epoch PRE-correction estimate p_prior = fix.pos + nu_pos, exactly one GNSS epoch old
  by construction, tracked alongside `_last_gnss_pos`/`_last_gnss_cov`). New helper
  `_p_prior_from_innovations(fix, innovations)`. `_physical_spoof_evidence` no longer uses
  `nav_prior` for the position term at all (parameter kept for signature stability, unused).
  Re-verified: 0/300 false fires on the same clean nominal run post-fix (mean w_gnss rose from
  0.18 to 0.38 -- still somewhat below 1.0, likely normal ML-detector-driven distrust on
  nominal data, NOT E_s -- confirmed E_s fired 0 times in that run; not chased further, S1 far
  check will give the official number).
- Tests: `tests/test_trust_law_es_position.py` REWRITTEN (6 tests now, added
  `test_real_fast_motion_does_not_fire_when_ins_tracks_it`, the exact case the bug broke). ALL
  PASS. Full `pytest -k "trust or fusion or eskf"` needs RE-RUN after this fix (was green
  before, but this changes trust_law.py again) -- NOT YET RE-RUN as of this write.
- results/m1/s1_far_check_core_robust.json from the FIRST (buggy) launch is STALE -- re-run S1
  far check after this fix and overwrite.

## D-060 rotations.py revert (Master note, usage-limit resume point)
- `fedqpnt/sim/rotations.py` was modified (mtime 01:05:20) by another agent's commit
  `8a3b680` ("perf: rotations fast path rejected; not bit-identical for large angles").
  ALL of my item 4/5/6 diagnostic runs before that timestamp (overconf_diag ~00:32-00:39,
  kappa_tuning ~00:20-00:24, kappa60_block_nees ~00:32-00:35, the FIRST item-6 launch
  ~00:38-01:03) may have run against a different (possibly non-bit-identical, fast-path)
  version of so3_exp/so3_log than what's committed now. The E_s position-term math (items
  1-3) does NOT depend on rotations.py (pure position algebra), so items 1-3 are UNAFFECTED
  and do not need re-running. Items 4, 5, and 6 (all use so3_exp/so3_log for
  attitude/mechanization) DO need re-running now that rotations.py is confirmed at the
  committed/reverted version, to avoid mixing two code versions in one comparison.
- PLAN: re-run item 4 (overconfidence diag + b_a artifact check), item 5 (kappa_R tuning +
  block NEES), and item 6 (the full re-verification campaign, already needed anyway due to
  the E_s nav_prior bug) -- all fresh, all after this point in time, all using the current
  repo state. Do NOT reuse any numbers from before 01:05:20 in the final report.
- Full suite run (`scratchpad/full_suite_after_esfix.log`) DONE. ONE failure:
  `tests/test_fleet_adapter.py::test_local_only_detector_hash_changes_across_rounds`
  (`assert node.get("round_installs", 0) >= 1` fails, got 0). CONFIRMED OUT OF SCOPE: this is
  `fedqpnt/eval/fleet_adapter.py`, not in my edit scope (fedqpnt/fusion/eskf.py,
  fedqpnt/trust/*, fedqpnt/node/*), and the failure matches the ALREADY-KNOWN D-059 bug
  from commit cd4b36f ("B-cont frozen-theta0 bug found -> fix pending") -- pre-existing,
  not caused by CORE-ROBUST. Every fusion/trust/eskf test PASSES. Report this as a known
  pre-existing failure, not something I introduced.
- **RELAUNCHED full items 4/5/6 campaign fresh** (background task **b0tam5szs**), one long
  sequential chain (NOT parallel -- learned from the earlier BrokenProcessPool crash), all
  logs prefixed `v2_*` in the scratchpad, all results written to `*_v2.json` / `*_core_robust_v2*`
  in `results/m1/` (do NOT use the pre-01:05:20 `*_core_robust.json` files or the original
  `overconf_diag.log`/`kappa_tuning.log`/`kappa60_block_nees.log`/`ba_nees_artifact.log` --
  those may be pre-rotations-revert and are SUPERSEDED):
  1. `scratchpad/v2_overconf_diag.log` (item 4b, CAI on/off NEES)
  2. `scratchpad/v2_ba_nees_artifact.log` (item 4 follow-up, b_a effective-bias truth)
  3. `scratchpad/v2_kappa_tuning.log` + `results/m1/kappa_r_tuning_v2.json` (item 5)
  4. `scratchpad/v2_kappa60_block_nees.log` (item 5, per-block NEES at chosen kappa_R)
  5. `scratchpad/v2_item6_s1_far_check.log` + `results/m1/s1_far_check_core_robust_v2.json`
  6. `scratchpad/v2_item6_smoke_matrix.log` + `results/m1/smoke_matrix_core_robust_v2.json`
  7. `scratchpad/v2_item6_defended_vs_undefended.log` + `.../defended_vs_undefended_core_robust_v2.json`
  8. `scratchpad/v2_item6_safety_sweep.log` + `results/m1/core_robust_safety_sweep_v2.json`
  9. `scratchpad/v2_item6_sig_strength_auc.log` + `results/m1/sig_strength_sweep_core_robust_v2.json`
  10. `scratchpad/v2_item6_es_firing_fraction.log`
  Final line in the chain's own output (the b0tam5szs task's own log, not scratchpad) is
  `=== FULL v2 CAMPAIGN (items 4,5,6) ALL DONE ===` when everything succeeds. If it fails
  partway, check which `v2_*.log` is incomplete/has a Traceback and re-run ONLY that step's
  command (each is self-contained, listed above) -- do not restart the whole chain.
- Expect this chain to take a while (S1 far check alone took ~19 min pre-fix); do not poll
  manually, use a background wait-loop + end turn, per the standing instruction.

## v2 campaign RESULTS so far (post rotations-revert, post E_s nav_prior-bug fix)
- Item 4b (`v2_overconf_diag.log`): SAME numbers as the pre-revert run (CAI ON: p=3.58 v=1.98
  psi_rp=4.64 psi_yaw=0.48 b_a=522.09 b_g=7.10; CAI OFF: p=2.84 v=2.14 psi_rp=17.60 psi_yaw=0.64
  b_a=67.83 b_g=4.24) -- rotations.py revert did NOT change these (confirms so3_exp/so3_log
  numerics were equivalent for this trajectory's angle range; not a wasted re-run, a needed
  confirmation).
- Item 4 b_a artifact check (`v2_ba_nees_artifact.log`): SAME as before (classical truth
  522.19 -> effective-bias truth 19.04, per-axis x=9.68 y=5.51 z=3.85). CONFIRMED unaffected
  by the rotations revert.
- Item 5 kappa_R tuning (`v2_kappa_tuning.log`, `results/m1/kappa_r_tuning_v2.json`): SAME
  chosen kappa_R=60 (ANEES_pos=0.9499). Full curve identical to pre-revert run.
- Item 5 block NEES at kappa_R=60 (`v2_kappa60_block_nees.log`): SAME (p=2.61 v=2.03
  psi_rp=4.84 psi_yaw=0.48 b_a=521.16 b_g=7.31).
- Item 6(i) S1 far check (`v2_item6_s1_far_check.log`, `results/m1/s1_far_check_core_robust_v2.json`):
  **MASSIVE IMPROVEMENT post E_s-bug-fix**: S1 median RMSE ratio (fedqpnt/fixed_trust) =
  **0.9877, threshold 1.05, PASS=True** (was 5.82/FAIL before the nav_prior fix). Full
  per-method FAR/ANEES table is in the json/log -- read it fresh for the final report (don't
  trust my earlier partial read, get the fedqpnt_local row specifically: FAR, ANEES_pos,
  mean_w_gnss).
- Item 6(ii)-(iii) chain CRASHED again at the smoke matrix step (BrokenProcessPool /
  MemoryError, default `--workers` too high e.g. 16 concurrent 600s-sim workers). RELAUNCHED
  the remainder with `--workers 6` explicitly on every run_many-based script (background task
  **bbbg0ztuf**): smoke_matrix -> defended_vs_undefended -> safety_sweep -> sig_strength_auc ->
  es_firing_fraction, same log/output filenames as before (they get overwritten/appended
  fresh). If THIS also crashes on memory, try `--workers 3` or 4 next.

## IN PROGRESS / NEXT (as of this write)
- Item 5 kappa_R=60 per-block NEES: DONE (see above).
- sweep_signature_strength.py: added `--kappa-r` CLI flag (threaded through `_collect_family`,
  `run_sweep`, `run_rmse_comparison`). DONE.
- New scripts written for item 6: `scripts/core_robust_safety_principle_sweep.py` (item 6ii,
  s-sweep safety table, writes `results/m1/core_robust_safety_sweep.json`),
  `scripts/core_robust_es_firing_fraction.py` (item 6iii, reads `agent.trust.last_es_evidence`
  directly -- automatically reflects the NEW D-058 jump test).
- **Item 6 campaign LAUNCHED as two parallel background chains** (both `run_in_background: true`,
  direct Bash tool tracking, NOT nohup+disown):
  - Chain A (task id **b17ktblbp**, log dir prefix `item6_*`): S1 far check (kappa-r 60, sup_v2
    weights, out `results/m1/s1_far_check_core_robust.json`, log
    `scratchpad/item6_s1_far_check.log`) THEN smoke matrix (out
    `results/m1/smoke_matrix_core_robust.json`, log `scratchpad/item6_smoke_matrix.log`) THEN
    defended_vs_undefended (out `results/m1/defended_vs_undefended_core_robust.json`, log
    `scratchpad/item6_defended_vs_undefended.log`).
  - Chain B (task id **bjaxuyjmj**): safety-principle s-sweep (log
    `scratchpad/item6_safety_sweep.log`) THEN signature-strength AUC sweep (out
    `results/m1/sig_strength_sweep_core_robust.json`, log `scratchpad/item6_sig_strength_auc.log`)
    THEN E_s firing fraction (log `scratchpad/item6_es_firing_fraction.log`).
  - Quick single-seed sanity check of the E_s firing script already ran manually: drift
    severity=0.5 (cn0_sig_scale=0.0) fired 31/32 active epochs (0.97). This looks HIGH but is
    plausibly correct, not a bug: DriftInSpoof severity=0.5 ramps to 1.5 m/s terminal drift
    velocity over ~60s, which is a genuinely fast KINEMATIC drag (not "slow" in absolute
    velocity), so the short-baseline test (designed to catch exactly this GNSS-vs-INS motion
    inconsistency) firing often is expected/correct, distinct from the earlier unit test's
    truly-slow 0.1 m/epoch case (which correctly did NOT fire). State this interpretation in
    the final report; don't chase further unless the full campaign shows something inconsistent.
  - If EITHER chain fails/errors, re-launch just the failed step (each step's `python -u ...`
    command is self-contained and listed above/in the script files); do not re-run completed
    steps.
- After both chains finish: read all `item6_*.log` files, cross-check against M1 criteria (S1
  FAR<=1/h, RMSE ratio<=1.05, ANEES_pos in [0.5,2], no divergence), the D-055 safety-principle
  table (PASS/FAIL per method per s), and the E_s firing fractions (drift vs meaconing).
- Retrain detector only if feature distributions changed materially -- NOT expected (the D-058
  E_s change only touches the position evidence TERM inside _physical_spoof_evidence, not the
  13-feature vector the detector itself trains/scores on); state this in the report, don't
  retrain unless the campaign shows AUC/feature-distribution drift.
- Write terse notes to `docs/specs/raw/CORE_ROBUST_NOTES.md` (NOT YET CREATED) -- do this once
  the item-6 numbers are in hand, one pass, not incrementally.
- Run full suite `python -m pytest tests/ -q` once at the very end (already confirmed green
  after items 1-3; re-run after item 6 in case any script edits broke an import, though scripts/
  aren't covered by tests/ normally -- just a final sanity gate per the task's "keep the whole
  suite green" instruction).
- Final report via SubagentHandback per the original task format (AGENT/STATUS/pytest line/
  items 1-6 with numbers/kappa_R chosen/M1 table/safety table/E_s fractions/PROPOSED-DECISIONs/
  permission denials -- there have been NONE so far, no edit prompts were denied).

## Resume command pattern
Background jobs: always `python -u <script> > "<scratchpad>/<name>.log" 2>&1` passed directly to
the Bash tool with `run_in_background: true` (do NOT nohup+disown -- that detaches it from the
tool's own tracking and notifications never fire). To wait without polling manually, wrap in a
`run_in_background: true` Bash call with an `until grep ...; do sleep N; done` loop, then end the
turn.

## D-067 change (0): kappa_R=60 single source of truth (BEFORE (i)); still waiting for H2 telemetry go
Hardcoded-40 sites found (all in fedqpnt/): node/methods.py:36 (DEFAULT_KAPPA_R), node/runner.py:50,
node/agent.py:65 (AgentConfig), eval/scenarios.py:30 (KAPPA_R_STATUS + docstring l.11),
eval/campaign.py:65,101,152,203, eval/fleet_adapter.py:154,275, fleet/orchestrator.py:55,
fleet/node_runner.py:63 (H2-ABRUPT still editing this file: touch only after it lands),
training/build_supervised_dataset.py:142. Plan: DEFAULT_KAPPA_R=60.0 in node/methods.py (D-061
provenance comment), others import it (check scenarios.py import-cycle note l.39), KAPPA_R_STATUS=
"D-061_kappa_R=60"; ESKFConfig stays 1.0; historical scripts untouched. Test written (xfail-marked,
remove when landed): tests/test_kappa_r_default.py. Order then: (0),(i),(ii),(iii).

## CHANGE (0) IMPLEMENTED (awaiting full-suite result, then Master commits)
New leaf fedqpnt/core/defaults.py (DEFAULT_KAPPA_R=60.0, D-061 provenance); node/methods.py re-exports it
(avoids methods<->agent import cycle); agent.py, runner.py, campaign.py (4 defaults), fleet_adapter.py,
fleet/orchestrator.py, fleet/node_runner.py, training/build_supervised_dataset.py now use it;
eval/scenarios.py KAPPA_R_STATUS="D-061_kappa_R=60". tests/test_kappa_r_default.py xfail removed, 7 pass.
Full suite log: scratchpad/suite_change0.log (bg task bjb0v4dcp). Start HEAD=77d4ff79a3707318da94fa5974379dfc651553e0.
CHANGE (0) READY TO COMMIT: full suite green (xfail-pending tests for (i)/(ii) only; 0 failures). Git: HEAD=6b32975e37c889cb202a06cb6086623e2b2413b8. My files: core/defaults.py (new), node/{methods,agent,runner}.py, eval/{campaign,fleet_adapter,scenarios}.py, fleet/{orchestrator,node_runner}.py, training/build_supervised_dataset.py, tests/test_kappa_r_default.py. NOT mine (MEACON agent): node/environment.py, attacks/meaconing_displaced.py. PAUSED for Master's commit before (i).

## CHANGE (i) IMPLEMENTED (awaiting full suite: scratchpad/suite_change_i.log, bg task bmljx1m0s)
Edited: fedqpnt/fusion/clock.py (ClockKFConfig q_bias=c^2*h0/2=8.99e-3, q_drift=c^2*2pi^2*h_-2=3.55e-2
with Brown&Hwang / Krawinkel&Schon 2021 doi:10.1002/navi.444 / Qin 2021 doi:10.3390/s21020466
provenance; new w_excl=0.05; update skipped when w_gnss<w_excl, Q untrusted-scaled), fedqpnt/gnss/signal.py
(ClockState sigma_bias_rw/sigma_drift_rw = sqrt of same q, same provenance). Tests: holdover (3) +
NEES/consistency (2) xfail removed, pass with tests/test_node_clock.py (10 pass). XPASS name (pre-change):
tests/test_fusion_clock_holdover.py::test_above_w_excl_still_updates = regression guard for existing
w=1 update behaviour, intentionally passes before the change (kept, not a defect). Not touched: eval/*, attacks/*, environment.py.
Timing baselines (rmse_t_ns 13.7 nominal, 1284/1358 meaconing) are PRE-change; re-measure in combined run.
PAUSE for Master commit after suite green, then (ii).

## CHANGE (ii) IMPLEMENTED (awaiting full suite: scratchpad/suite_change_ii.log, bg task b672d1o5z)
Files: core/types.py (TrustState.probe_shadow=False default), fusion/eskf.py (innovations() also emits
"gnss_shadow" 6-D innovation = same nu vs coasting P with the receiver's own UN-inflated covariance, chi2_6
under nominal; correct() skips the GNSS update when trust.probe_shadow), node/agent.py (ClockKF weight 0
during shadow), trust/trust_law.py (CHI2_6_99; _LawCoreV2.advance(es_position): position jump term
superseded in PROBE, clk/xsat/cn0 veto stays; PROBE accept iff mean shadow NIS<=chi2_6(0.99) and no
non-position E_s; SensorTrustLaw.probe_shadow; engine passes shadow NIS, splits E_s parts, waives
apply_reacquisition_cap ONLY for v2 laws when a shadow innovation exists, NIS<=chi2_6(.99), E_s silent;
consistency-matched-adversary limit documented in the PROBE branch comment; tau_r untouched).
Design note: kappa_R-inflated NIS was ~100x too small for consistency (x1~0.28 with a 26 m spoof), hence the
un-inflated shadow statistic. Tests: tests/test_trust_shadow_probe.py xfail removed (9 pass: law-level probe
accept/veto/supersede, engine reacq waived/kept/no-shadow, ESKF no-update + shadow NIS). Pause for commit.

## D-068-era check before (iii): shadow-NIS false-veto/power check (Master request; change (ii) committed)
Script scripts/core_robust_shadow_nis_check.py (3 outage windows/mission x seeds 500-509 x grades x offsets 0/10/26/50 m,
NO update applied in the first 10 s after each 60 s outage, per-epoch clean shadow NIS via --with-clean-epochs, <=4 workers).
Pre-registered rule: clean false-veto <=1% at both grades -> keep chi2_6(0.99)=16.81; else replace with p99 of clean
mean-shadow-NIS on seeds 510-529 per grade (frozen; clean data only). (c) jam_cw tactical seed 500 recovery trace also due.
Then (iii); message Master before touching eval/metrics.py.
SHADOW-NIS CHECK seeds 500-509 (log scratchpad/shadow_nis_500_509.log, results/m1/shadow_nis_check_500_509.json; start HEAD=1cc9d4e, end 1f43a36, fedqpnt/ dirty only from other agents):
mean shadow NIS over first 10 s after a 60 s outage, no update applied (n=30 windows/cell); frac>16.81:
MEMS  off0: median 3.58 p95 13.40 p99 17.06 frac 0.033 | off10: 4.69/17.26/21.95 0.067 | off26: 9.77/29.19/35.16 0.233 | off50: 28.24/58.15/66.87 1.000
TACT  off0: median 3.12 p95 6.35 p99 9.85 frac 0.000 | off10: 6.15/10.28/12.67 0.000 | off26: 21.43/31.81/32.92 0.733 | off50: 74.63/97.91/100.79 1.000
Clean per-epoch (no outage, n=4900): MEMS median 1.84 p95 8.02 p99 19.37 frac>16.81 0.0159; TACT 1.88/5.84/8.16 0.0002.
Rule triggered (MEMS clean false-veto 3.3% > 1%): calibrate per grade on seeds 510-529 (running, log shadow_nis_510_529.log).
CALIBRATION seeds 510-529 (n=60 clean windows/grade, log shadow_nis_510_529.log): MEMS p99=25.07 (frac>16.81=0.050), TACT p99=6.74 (0.000).
FROZEN per pre-registered rule: PROBE_NIS_BOUND_BY_GRADE = {industrial_mems: 25.07, tactical: 6.74} (node/methods.py; TrustLawConfig.probe_nis_bound;
make_agent_config(imu_grade=...); runner + fleet/node_runner pass grade). Detection power at frozen bounds (seeds 500-509, n=30, frac vetoed):
MEMS@25.07: off0 0.00, off10 0.00, off26 0.067, off50 0.70. TACT@6.74: off0 0.033, off10 0.367, off26 1.00, off50 1.00.
(b at chi2_6(0.99)=16.81: MEMS 0.033/0.067/0.233/1.00, TACT 0/0/0.733/1.00.)
Full suite + (c) recovery summary running (scratchpad/suite_shadow_bound.log, jam_recovery_summary.log).
(c) RESULT with shadow probe + per-grade bounds (scripts/core_robust_jam_recovery_summary.py, seed 500, jam_cw): REGRESSION.
At t=302 (first valid fix after the 180 s outage) state goes TRUST->DISTRUST, w=0.02 and STAYS; err_h keeps growing (tactical 51.6->56 m over
t300-313, MEMS 325->378 m); post RMSE tactical 31.82 / MEMS 243.23, time_to_TRUST(w>0.9) 163 s both. Suite green (log suite_shadow_bound.log, 0 F/E).
Hypothesis (verifying via scratchpad/jam_trace_v5.txt): the TCXO truth (change i, drift RW 0.19 m/s/sqrt(s)) makes the clk_jump features x8/x9
(dt-scaled prediction over the 180 s gap, sigma 3 m) huge on the first post-gap fix -> E_s clk_event and detector p fire -> D=1 -> DISTRUST 60 s
at w<w_excl (no correction) -> PROBE. Position gap-reset never covered the clock features. Candidate fix (needs Master ok, trust/features.py):
treat x8/x9 as unavailable (0) when dt since last fix > 3 s (gap-aware), like the outage handling.
FIX for the (c) regression: trust/features.py CLK_JUMP_MAX_DT_S=3.0: x8/x9 unavailable (0) when gap since last fix > 3 s (root cause: x8=141 sigma, x9=28.8 sigma on
the first post-outage fix with TCXO truth -> E_s clk_event + detector -> DISTRUST at w=0.02). Test test_clock_jump_features_unavailable_after_long_gap.
Re-run (jam_recovery_summary2.log): tactical post RMSE 5.10 (max 51.9 at the 2 invalid epochs), err<5 m in 3 s, TRUST&w>0.9 in 20 s; MEMS post RMSE 25.61
(max 328.6, same), 3 s, 20 s; first fix w=0.774 (cap waived, consistent). Full suite green (suite_features_fix.log). Change (ii) follow-up READY; then (iii).

## D-071 (before (iii)): principled clock-jump normalisation replaces the blanket >3 s gap blind
features.py x8/x9 normalised by predicted TCXO innovation std over dt (closed form; q values now single-sourced in core/defaults.py CLOCK_Q_BIAS/CLOCK_Q_DRIFT,
used by ClockKFConfig, signal.py ClockState, features.py): sigma_b^2=r_bias+q_b dt+q_d dt^3/3, sigma_d^2=r_drift+q_d dt. At dt=1 s sigma_b 3.000->3.003
(0.1%), sigma_d 0.200->0.275 (x9 x0.73: stated change). Tests (tests/test_trust_features.py): (a) post-180 s-outage x8/x9 under TCXO truth: false clk_event <=2%
(numbers in scratchpad/x89_after_gap.log); (b) 750 m replay step on first fix after 180 s gap gives x8=2.855 (sigma_b(180)=262.7 m), BELOW es_clk_sigma=5
-> does NOT fire (reported, threshold not tuned); same step at dt=1 s is ~250 sigma. Recovery re-run: scratchpad/jam_recovery_summary3.log; suite: suite_d071.log.
Detector retrain deferred (v3 + theta0_noabrupt after freeze, D-067).

## CHANGE (iii) IN PROGRESS (trust split, D-072): applied core edits (types clk_probe_shadow, eskf reads gnss_pos, agent w_clk, trust_law clk_law + evidence routing + alias),
test subset running (task bwn5wcyfc). Prepared but NOT yet applied: scratchpad/apply_metrics.py (metrics.mean_w/mean_w_report, runner + fleet node_runner use it).
Remaining: apply metrics edit, update tests (weights["gnss"] alias min -> read gnss_pos in tests/test_trust_shadow_probe.py reacq tests), new split tests
(clk_event only -> w_clk down, w_pos stays; meaconing-like), ClockKF clk_probe_shadow, full suite, git state, pause for Master commit. Master OK'd metrics.py edits.

## CHANGE (iii) IMPLEMENTED (D-072 trust split) - READY TO COMMIT; full suite green (scratchpad/suite_change_iii_b.log, 0 F/E). HEAD=12b6d92a03783c0ca5a284bce585e4555cad29e6
Files: core/types.py (TrustState.clk_probe_shadow), fusion/eskf.py (GNSS update reads weights["gnss_pos"], falls back to "gnss"), node/agent.py (ClockKF reads
"gnss_clk"; weight 0 during clk probe), trust/trust_law.py (TrustEngineImpl.clk_law = second v2 law; position law <- position_event + xsat/cn0; clock law <- clk_event + xsat/cn0
with statistic x8^2+x9^2 vs chi2_2 (bound 9.21, ok<=5.99); detector p drives both; shadow probe + reacq consistency stay on w_pos; clock keeps the unconditional reacq cap; weights
"gnss"=min alias, "gnss_pos", "gnss_clk"; anomaly_scores gnss_clk; attack_detected = pos OR clk), eval/metrics.py (mean_w, mean_w_report: whole-mission and attack-window
mean_w_gnss/pos/clk), node/runner.py + fleet/node_runner.py (report them), tests/test_trust_split.py (4 tests), tests/test_trust_shadow_probe.py (reacq tests read gnss_pos).
Caveat for combined re-verification: detector p (trained) fired 0.98-0.999 on meaconing in the earlier trace and drives BOTH weights by design, so w_pos may still drop under meaconing;
effectiveness is empirical. Next: combined re-verification (both grades, <=4 procs) after Master's commit.
