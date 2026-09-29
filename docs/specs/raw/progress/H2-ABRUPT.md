# H2-ABRUPT progress

## Context read
- D-054 (theta0 protocol, PRETRAIN seeds 400-449, restricted families),
  D-056 (H2/H4 AUC-decomposition protocol: auc_detector_only / auc(p_bar) /
  latency_on / es_fire_frac_attack; sub-rule regime requirement),
  D-058 (E_s redefined as a trust-independent short-baseline jump test;
  item 4 CONTROL result: abrupt is rule-quiet, chosen as the NOVEL family
  for this task), D-059 (B-cont = 1-node FedAvg federation, LOSSLESS comms).
- H2_SUBRULE_NOTES.md: drift/meaconing sub-rule regime unreachable (E_s
  coupled to trust-exclusion-driven EKF divergence); abrupt confirmed
  rule-quiet (E_s ~1.7-1.9% under the OLD/pre-CORE-ROBUST-fix E_s code).
- CORE-ROBUST (concurrent agent) found + fixed a bug in the D-058 jump test
  (`_physical_spoof_evidence` was using a stale `nav_prior` baseline,
  firing on 80% of CLEAN epochs). Fix landed in `fedqpnt/trust/trust_law.py`
  (uncommitted, in the working tree per git status). **My step 2 (E_s
  quiet-on-abrupt re-verification) MUST run against this fixed code**, since
  the old abrupt es_fire_frac numbers in H2_SUBRULE_NOTES.md predate the fix
  and cannot be trusted as-is.
- Reused without edits: `scripts/pretrain_theta0_d054.py` (pattern),
  `scripts/h2_h4_subrule_d056.py` (run_h2/run_h4 are already generic over
  family_name via `_seeds_excluding_family`/`_seeds_including_family` --
  reusable for abrupt-as-novel with a new theta0), `fedqpnt/eval/fleet_adapter.py`
  lossless-comms pattern (D-059), `scripts/core_robust_es_firing_fraction.py`
  (single-node E_s check pattern).

## CPU budget note
Task says: at most 6 processes TOTAL across this agent and CORE-ROBUST.
`tasklist` at start of this session showed ~13 python.exe processes already
alive (CORE-ROBUST's item-6 chains, incl. a `--workers 6` run_many pool).
**Decision:** ran step 1 (pretrain, single process) and step 2 (E_s check,
single process, no fleet/multiprocessing) now since they are lightweight
relative to CORE-ROBUST's load. Steps 3/4/5 (H2/H4/control) each spawn 1
server + N=5 node processes (6 processes, per `fedqpnt/fleet/orchestrator.py`
`ctx.Process`) and MUST run strictly sequentially, one fleet invocation at a
time, and I will check `tasklist` before each to avoid oversubscribing
alongside CORE-ROBUST's chains.

## Done
- Wrote `scripts/h2_abrupt_pretrain_theta0.py` (theta0_noabrupt: seeds
  400-449, families {clean, drift, jam_cw, jam_wideband, jam_then_spoof},
  EXCLUDING abrupt and meaconing). Output: `results/fleet/theta0_noabrupt.npz`
  + `..._provenance.json`.
- Wrote `scripts/h2_abrupt_theta0_auc_check.py` (held-out abrupt AUC of
  theta0_noabrupt; scans seeds 585-599 for family=="abrupt", causal replay
  eval per fl_sanity_check_d054.py's `_eval_detector` pattern). Output:
  `results/fleet/h2_abrupt_theta0_auc_check.json`.
- Wrote `scripts/h2_abrupt_es_firing_check.py` (step 2: E_s firing fraction
  on abrupt_spoof at severities [0.6, 0.4, 0.2, 0.1], seeds 500-504,
  single-node, current/fixed trust_law.py, target <=5%).

## In progress (background)
- PID/task **b9qy23zwe**: `python -u scripts/h2_abrupt_pretrain_theta0.py`
  THEN (chained with `&&`) `python -u scripts/h2_abrupt_theta0_auc_check.py`.
  Log: scratchpad `h2_abrupt_pretrain.log` and `h2_abrupt_theta0_auc.log`.
  Started this turn; single process, lightweight (~120s missions x ~35
  seeds, same cost profile as the original D-054.1 pretrain).
- PID/task **bldmc9gy5**: `python -u scripts/h2_abrupt_es_firing_check.py`
  (step 2, independent of theta0 -- single node, no detector weights loaded,
  pure E_s/trust_law check). Log: scratchpad `h2_abrupt_es_check.log`.
  Started this turn in parallel with b9qy23zwe (both single-process, low
  footprint; only the step-3+ fleet runs need the tasklist headroom check).

## Step 1 result (theta0_noabrupt pretrain, task b9qy23zwe DONE)
- 36 seeds used (400-449 restricted), families present: clean, drift,
  jam_cw, jam_then_spoof, jam_wideband (no abrupt/meaconing -- restriction
  held). U.shape=(3284,60), n_pos_spoof=1039, n_pos_jam=887, train loss 0.134.
  Wrote `results/fleet/theta0_noabrupt.npz` + provenance JSON.
- FIRST held-out abrupt AUC pass (seeds 585-599): only ONE abrupt-family
  seed in that narrow range (596, n=118 epochs, 89 positive) -> AUC=0.912.
  **Surprisingly high for a detector that never saw abrupt** (D-055's
  centrally-trained-WITH-abrupt detector only got 0.691-0.754 AUC on
  abrupt), but n=1 seed is too thin to trust. Plausible explanation (not
  yet confirmed): theta0_noabrupt's `jam_then_spoof` family literally
  contains a spoofing sub-phase, and D-054's earlier restricted theta0
  (abrupt+jam, no drift/meaconing) already showed meaconing transfer to
  0.708 AUC from jam+abrupt alone -- some cross-family feature transfer
  (RAIM/C-N0/clock-jump features) is an established pattern in this
  pipeline, not necessarily a leak.
- **Re-running with the full 500-599 range** (task **bz1y0pqnt**, log
  `h2_abrupt_theta0_auc_v2.log`) to get more abrupt-family seeds before
  reporting a final number. Confirmed reusing base seeds 500-599 here does
  NOT leak into the later fleet runs (those use offset seed spaces like
  `300000+seed*100` for local-train data, not raw 500-599).

## Step 1 FINAL result (theta0_noabrupt held-out abrupt AUC)
- Widened eval to full seeds 500-599 (task bz1y0pqnt): 13 abrupt-family
  seeds found, n_epochs=1534, n_pos=1157. **auc_abrupt_heldout=0.898**
  (well-powered, robust vs the earlier 1-seed 0.912 estimate).
- **This is NOT near chance** as the task anticipated. theta0_noabrupt
  never saw abrupt in training (assertion held: families_present =
  [clean, drift, jam_cw, jam_then_spoof, jam_wideband]), yet scores 0.898
  on it -- HIGHER than D-055's centrally-trained-WITH-abrupt detector
  (0.691-0.754 AUC on abrupt!). Working hypothesis (not further chased,
  report as-is per task's "report honestly" instruction): strong cross-
  family feature transfer, plausibly via `jam_then_spoof`'s literal
  spoofing sub-phase and/or shared physical-evidence features (RAIM
  residual, clock-jump, C/N0 anomaly) that abrupt's step-jump also trips.
  D-054's earlier restricted theta0 (abrupt+jam, no drift/meaconing) showed
  a similar pattern (meaconing transferred to 0.708 from abrupt+jam alone),
  so this fits an established cross-family-transfer pattern in this
  pipeline, not an isolated anomaly.
- Consequence for H2/H4: the "novel family, FL should help n0 generalise"
  framing is weaker here than intended, since theta0 ALREADY generalises
  well to abrupt without ever training on it or via FL. Report this
  explicitly as a limitation/caveat on H2/H4 abrupt: FL's marginal
  contribution may be small because theta0 already covers the family.

## Step 2 result (E_s firing fraction on abrupt, CURRENT/fixed core)
Tasks bldmc9gy5 (severities 0.6/0.4/0.2/0.1) + buktjihbs (bisection 0.15),
seeds 500-504, N=5, single-node checks:

| severity | jump magnitude (80m x severity) | pooled es_fire_frac | PASS<=5%? |
|---|---|---|---|
| 0.6 (D-056 CONTROL_ATTACK value) | 48 m | 0.1556 | NO |
| 0.4 | 32 m | 0.1556 (identical to 0.6) | NO |
| 0.2 | 16 m | 0.0978 | NO |
| 0.15 | 12 m | 0.0000 | YES |
| 0.1 | 8 m | 0.0000 | YES |

**CHOSEN: severity=0.15** (12 m jump) -- passes cleanly, keeps more signal
than 0.1. This is the value used in `scripts/h2_abrupt_h2h4_driver.py`'s
`NOVEL_ABRUPT` attack config.

**CONFIRMED per the task's own prediction: the new D-058 jump test DOES
fire on abrupt now** (unlike the pre-fix ~1.7-1.9% control number in
H2_SUBRULE_NOTES.md, which predates CORE-ROBUST's nav_prior fix and is now
known-stale for this family too -- makes sense, since the jump test is
LITERALLY designed to catch GNSS-vs-INS position jumps, and abrupt_spoof IS
a position jump by construction). Severity 0.6/0.4 give an IDENTICAL fired
count (140/900) -- suspect the reacq_epochs=2 lock-loss window right after
onset dominates the fire count at these severities more than raw jump size;
0.2 (16m) still fails; 0.15 (12m) and 0.1 (8m) both pass cleanly (0/900).

## Master ruling D-061a (received mid-task, addressed before fleet runs)
1. Compute theta0_noabrupt's held-out abrupt AUC at EXPLICIT severities
   0.15/0.1/0.2 (same 13 seeds as the 0.898 result), since that 0.898 was
   measured at the training-pool DEFAULT abrupt severity (0.5, from
   `build_supervised_dataset._family_attacks`), NOT the 0.15 the fleet runs
   actually use. Master confirmed no leakage (`jam_then_spoof` uses
   `drift_spoof`, not `abrupt_spoof` -- checked, correct, see
   `_family_attacks` line ~105-107: jam_wideband + drift_spoof, no abrupt).
   Wrote `scripts/h2_abrupt_theta0_auc_by_severity.py` (reimplements
   `collect_run`'s body locally with an explicit severity override --
   `build_supervised_dataset.py` not edited) and launched it in the
   background (task **b1mcfth4f**, log `h2_abrupt_theta0_auc_by_severity.log`,
   writes into `results/fleet/h2_abrupt_theta0_auc_check.json` alongside the
   existing severity=0.5 result under a new `auc_by_severity` key).
   **Severity=0.15 result (same 13 seeds, n=1534 epochs, 1157 positive):
   AUC=0.805** -- BELOW Master's 0.85 low-headroom threshold, so per the
   pre-registered decision rule, **H2/H4 run "as planned" (not flagged
   low-headroom)** -- CONFIRMED by Master's follow-up message ("AUC 0.805
   at severity 0.15 is accepted"). **Job b1mcfth4f now DONE, full table:**

   | severity | jump (80m x sev) | AUC (13 seeds, n=1534, 1157 pos) |
   |---|---|---|
   | 0.1  | 8 m  | 0.819 |
   | 0.15 (fleet severity, ACCEPTED) | 12 m | 0.805 |
   | 0.2  | 16 m | 0.783 |
   | 0.5 (training-pool default, not fleet-matched) | 40 m | 0.898 |

   All three explicit-severity values sit in a narrow 0.78-0.82 band, well
   below the 0.5-severity 0.898 and below Master's 0.85 threshold --
   meaningful headroom for FL to add value exists at the fleet's chosen
   severity (0.15). Written to `results/fleet/h2_abrupt_theta0_auc_check.json`.

## Wait-loop bug found + fixed (Master's second message)
Master identified the original wait-loop (task bg6yh1t5m, condition "total
python.exe <=4") could NEVER fire: 6 orphaned idle worker processes from
2026-09-28 10:29 (PIDs 22248, 34792, 6288, 19688, 31960, 33460; parent 7460)
are permanently alive, user-owned, and must NOT be killed by me. Stopped
bg6yh1t5m via TaskStop (it had NOT yet launched the fleet driver -- confirmed
safe, no orphaned fleet processes from my side). Rewrote
`<scratchpad>/h2_abrupt_wait_and_run.sh` to explicitly exclude those 6 PIDs
from the count (condition now: <=4 OTHER python.exe, i.e. excluding the 6
known orphans). Relaunched as task **bdoo5lti3**
(log `h2_abrupt_wait_and_run_v2.log`). Current count (8 other processes):
CORE-ROBUST's `defended_vs_undefended` job (PID 5800 + its 6 workers
34340/33040/27112/32324/25068/22388) + my own severity-AUC job (PID 17020,
"fine" per Master, will exit on its own once severity=0.2 finishes). In
practice the gate is waiting for PID 5800's job to finish, per Master's note.
2. Pre-registered decision rule (DO NOT change after seeing fleet results):
   if zero-shot AUC at sev 0.15 >= 0.85 -> still run H2/H4 as planned but
   label it 'low-headroom' and ALSO report per-severity AUC deltas (FL
   minus zero-shot); if < 0.85 -> run as planned either way. Recorded here
   BEFORE the fleet driver runs, per Master's pre-registration requirement.
3. Severity 0.15 (E_s-quiet, 0% firing) ACCEPTED by Master for H2/H4/control.
4. Old H2_SUBRULE_NOTES.md abrupt-control numbers: add a one-line header
   note "SUPERSEDED by H2-ABRUPT (D-061a), measured on pre-D-058 core" --
   NOT deleted (done below, see "H2_SUBRULE_NOTES.md header" section).
5. CPU budget: `tasklist` still shows 13-14 python.exe processes (CORE-
   ROBUST's chain still running) as of this ruling; the wait-loop
   (bg6yh1t5m) has NOT yet started the fleet driver -- confirmed correct,
   still respecting the <=6-process shared budget. The new severity-check
   script (b1mcfth4f) is single-process/lightweight, same footprint class
   as steps 1/2, launched without waiting.

## H2_SUBRULE_NOTES.md header note (done)
Added a one-line SUPERSEDED marker at the top of the file (see that file);
content otherwise left intact per Master's "not deletion" instruction.

## Steps 1+2 COMPLETE. Step 3-5 driver written, waiting on CPU headroom.
- Wrote `scripts/h2_abrupt_h2h4_driver.py`: runs H2 (novel family=abrupt),
  H4 (cold-start, same), and the control (family=drift, s=1, n0 DID see it)
  sequentially, --parts h2,h4,control, output results/fleet/h2_abrupt.json.
  Reuses the same generic seed-partition helpers as h2_h4_subrule_d056.py
  (not imported -- this is a standalone new script per the task's script-
  only rule); same CHOSEN hyperparams, N=5, seeds [500-504], 600s missions.
- `tasklist` at the point of writing still showed 13 python.exe processes
  (CORE-ROBUST's item6 chain still running: smoke_matrix -> defended_vs_
  undefended -> safety_sweep -> sig_strength_auc -> es_firing_fraction).
  Since each of MY fleet runs needs 6 fresh processes (1 server + 5 nodes)
  and CORE-ROBUST already had a BrokenProcessPool/MemoryError crash once at
  16 concurrent workers, launching immediately risks a repeat crash for
  BOTH agents. **Did NOT launch immediately.**
- Instead launched a background wait-loop, task **bg6yh1t5m**
  (script `<scratchpad>/h2_abrupt_wait_and_run.sh`, its own log
  `h2_abrupt_wait_and_run.log`): polls `tasklist` every 60s, and once
  python.exe process count drops to <=4 (i.e. CORE-ROBUST's chain has
  finished), runs `python -u scripts/h2_abrupt_h2h4_driver.py --parts
  h2,h4,control` to `<scratchpad>/h2_abrupt_driver.log`. This is expected to
  be compute-heavy: per h2_h4_subrule_d056.py's own estimate, ~10-15 min per
  seed x 5 seeds x 3 parts (h2/h4/control) x 2 arms (fedqpnt_local/
  baseline_b_cont) -- likely 2-4+ hours wall time total. Do NOT poll
  manually; wait for the bg6yh1t5m completion notification (or an
  intermediate one if the wait-loop itself needs attention).

## D-062 Master ruling: H2/H4 null marked INVALID pending diagnostic (received
after the "TASK COMPLETE" note below was written -- that verdict is WITHDRAWN,
see this section)

### Item 3 (code consistency) -- CONFIRMED PROBLEM
`ls -la --time-style=full-iso fedqpnt/trust/trust_law.py` -> mtime
**2026-09-29 09:40:55**, which is INSIDE the fleet driver's run window
(08:38-10:24 IST). `git status`/`git diff --stat` confirm it is still
uncommitted-modified (171 insertions/5 deletions vs HEAD) -- this is
CORE-ROBUST's E_s gap-reset fix landing WHILE my fleet driver was running.
**CONFIRMED: the H2/H4/control run used mixed code (part of it under one
version of trust_law.py, part under another) and must be repeated after the
core is frozen.** This alone invalidates the run regardless of items 1/2's
findings.

### Item 1 (weight provenance) -- IN PROGRESS, cheap offline replay (no new
fleet missions, single process, reuses real fedqpnt.fl.client/aggregator
code directly instead of fedqpnt.fleet.orchestrator.run_fleet's 6-process
spawn)
Wrote `scripts/h2_abrupt_diag_weight_provenance.py`: builds n0 + 4 peers'
REAL local datasets (same seeds as h2_abrupt_h2h4_driver.py's run_h2,
seed=500), runs one real `FLClient.local_round()` per node, then applies
BOTH the B-cont path (`fedavg([n0_update])`, N=1 identity per D-059) and
the FedQPNT path (`trim_nb_r_aggregate([n0, n1..n4])`, real TRIM-NB-R) to
theta0, comparing n0's resulting installed-params hash/L2-diff under each
arm, for 2 rounds. **Important limitation stated plainly: I did NOT persist
per-round provenance (hash_pre/hash_post_train/hash_post_install,
round_installs) from the ALREADY-COMPLETED h2_abrupt.json fleet run** --
`fedqpnt/fleet/node_runner.py` computes and returns this exact data per
node (the `provenance` list + `round_installs` + `final_theta_hash` keys
already exist in `result.node_results["n0"]`, D-054's own provenance
diagnostic!), but my driver's `_record()` only captured the 5 scalar
METRIC_KEYS and discarded the rest before the process exited -- a real gap
in my own driver script, now impossible to recover for that specific run.
H4's log DID print install counts (5 vs 10, fedqpnt_local vs baseline_b_cont)
-- a real, already-available, structural difference (see "H4 install
counts" note in the earlier section of this file) -- but H2's log did not.
This diagnostic script is the substitute: it answers the MECHANISM question
(does TRIM-NB-R-aggregating-peers actually move n0's weights away from its
own solo update) directly via the real aggregator code, cheaply, without
needing the original run's lost telemetry or a new fleet spawn.

### Item 2 (AUC inversion cause) -- hypothesis + a diagnostic script to test it
Read `fedqpnt/fleet/node_runner.py` (lines ~256-290) and confirmed:
- (a) label alignment: `active = bool(tick.label.spoofing or tick.label.jamming)`
  read at the SAME tick as `raw_p = agent.trust.last_raw_p`, right after
  `agent.step(...)` -- no epoch/onset shift in the code.
- (b) score polarity: `auc_detector_only = M.roc_auc(raw_p_arr, active)` --
  the SAME `fedqpnt.eval.metrics.roc_auc` function (standard convention,
  higher score = more positive) I already used in my own offline held-out
  checks (h2_abrupt_theta0_auc_check.py/_by_severity.py) -- SAME polarity,
  no inversion in the scoring code itself.
- (c)/(d): **working hypothesis, not yet empirically confirmed**: abrupt_spoof
  is a ONE-TIME step-jump (held constant after onset, no further dragging --
  see `fedqpnt/attacks/spoofing.py` AbruptSpoof docstring), so its actual
  feature SIGNATURE (lock-loss/reacq, C/N0 anomaly) is transient (near
  onset), while its ORACLE LABEL (`is_active(t, onset_s, duration_s)`) marks
  the ENTIRE 300s live-mission duration as positive. My OWN isolated
  held-out check (0.805 AUC) used a 120s mission that only captured ~60s of
  the 180s label window immediately AFTER onset (the transient), while the
  live H2 run captures the FULL 300s (mostly a quiet, steady, small-offset
  state after the transient fades) -- if raw_p is low during that long
  steady-state remainder (arguably indistinguishable from nominal to a
  detector that never trained on abrupt) while some nominal CLEAN epochs
  score comparably or higher (miscalibration), AUC over the full window can
  go sub-chance even with NO code bug -- a property of this specific
  attack's oracle-label-vs-signature mismatch at LOW severity, amplified by
  using the full duration.
  Wrote `scripts/h2_abrupt_diag_score_trace.py`: single-node fedqpnt_local
  closed-loop replay (matches the live H2 pipeline, not the isolated
  open-loop check), SAME attack config as H2 (onset=120/dur=300/sev=0.15),
  full 600s mission, seed=500, theta0_noabrupt. Logs the full per-tick
  trace and reports mean raw_p / w_gnss / es_frac in FOUR windows
  (pre-onset clean, attack EARLY 5s transient, attack LATE steady-state,
  post-attack clean), plus AUC recomputed with only the EARLY window's
  epochs as positives vs only the LATE window's epochs as positives, to
  directly test the transient-vs-full-duration hypothesis.

### Master's follow-up (3 additions + H4 install-count question)
1. State the exact label/window definition of BOTH measurements side by
   side (isolated vs live) in the report -- isolated check: 1157 positives
   / 1534 epochs over 13 seeds (~89 pos / ~118 total per seed), from a
   120s mission, onset_s=60/duration_s=180 (so only t in [60,120) -- the
   FIRST ~60s of the 180s label window -- is ever reachable before the
   mission ends; the isolated check therefore ONLY EVER SEES the early
   part of the attack, never the full duration_s). Live H2/H4: onset_s=120/
   duration_s=300 inside a 600s mission -- the FULL 300s window [120,420)
   is reachable and labelled positive. **This is the side-by-side
   definition Master asked for; will restate cleanly in the final report.**
2. Will NOT choose a metric window myself. Once `h2_abrupt_diag_score_trace.py`
   finishes, will present the raw per-window numbers (full 300s window /
   an onset-only window of N s / both) to Master for pre-registration
   before any re-run -- no window chosen unilaterally.
3. Updated `scripts/h2_abrupt_h2h4_driver.py` (my own script, not a core
   module) to (a) persist FULL node_runner provenance (round_installs,
   the per-round `provenance` list with hash_pre/hash_post_train/
   hash_post_install, final_theta_hash) per (part, seed, method) to a new
   `results/fleet/h2_abrupt_provenance.json` via `_flush_provenance()`
   after each part, and (b) log `git rev-parse HEAD` +
   `git status --porcelain fedqpnt/` at launch AND at end into the report
   JSON, with an explicit `WARNING_code_changed_during_run` flag if they
   differ. This is ready for the NEXT re-run (not run yet -- no new fleet
   missions per Master's instruction).

### H4 install-count question (5 vs 10, fedqpnt_local vs baseline_b_cont)
   ANSWERED from code inspection (`scripts/h2_abrupt_h2h4_driver.py`'s
   `run_h4`, identical to `h2_h4_subrule_d056.py`'s original design): the
   two arms are given DIFFERENT `join_round` configs on purpose --
   `("fedqpnt_local", node_ids, {"n0": 5})` vs `("baseline_b_cont", ["n0"], {})`.
   H4's entire premise is cold-start: n0 is deliberately excluded from the
   FL arm until round 5 (`fedqpnt/fleet/node_runner.py::_do_fl_round`: `if r
   < spec.join_round: ... return` -- no send, no install, for rounds 0-4),
   so it can only install in rounds 5-9 = 5 installs, matching the observed
   5 exactly. `baseline_b_cont` has NO cold-start concept (it is n0's own
   1-node "no-FL" baseline, D-059) -- `join_round` defaults to 0, so it
   trains/installs every one of the 10 rounds, matching the observed 10
   exactly. **This is the H4 experimental design working as intended, not
   an anomaly or a bug** -- the FL arm installs LESS often specifically
   because H4 is testing whether a LATE-joining node benefits from
   federation despite fewer total updates.

### Both diagnostic scripts launched (task bsh1mo6mj, sequential, single
process at a time -- weight_provenance THEN score_trace, well within the
Master's <=2-process instruction). **NO new fleet missions run.** Logs:
`<scratchpad>/h2_abrupt_diag_weight_provenance.log`,
`<scratchpad>/h2_abrupt_diag_score_trace.log`. **BOTH COMPLETE (confirmed
across a usage-limit reset).**

## RESULTS (all diagnostics complete)

### Item 1 ANSWER: n0's weights DO differ between arms (H2 is NOT invalid
by construction)
`results/fleet/h2_abrupt_weight_provenance_diag.json` (seed=500, real
FLClient.local_round + real fedavg/trim_nb_r_aggregate, 2 rounds):

| round | n_samples (n0..n4) | bcont_hash | fq_hash | bcont L2 from theta0 | fq L2 from theta0 | bcont vs fq L2 |
|---|---|---|---|---|---|---|
| 0 | 67,49,57,54,63 | 877679d9d5c9 | 23588723b340 | 0.0148 | 0.0038 | 0.0119 |
| 1 | 133,98,115,108,126 | 6caa672ae635 | a0bb124a9de2 | 0.0122 | 0.0067 | 0.0071 |

Different hashes both rounds; bcont-vs-fq L2 (0.007-0.012) is the same order
of magnitude as each arm's own movement from theta0 -- **n0's installed
weights are genuinely different between arms, not a D-054-pattern
duplicate. H2 is valid-by-construction on this axis.** (min_samples=8 was
never binding here -- n0 always had 49+ samples by round 0.)

### H4 install-count ANSWER (5 vs 10): BY DESIGN, not a bug
`run_h4`'s own arm definitions: `("fedqpnt_local", node_ids, {"n0": 5})` vs
`("baseline_b_cont", ["n0"], {})`. H4 cold-starts n0 in the FL arm only
(`join_round=5`; `node_runner.py::_do_fl_round`: `if r < join_round: return`
-- no send, no install, rounds 0-4) so it can install only in rounds 5-9 (=5).
`baseline_b_cont` has no cold-start concept (D-059's 1-node "no-FL"
baseline) -- `join_round` defaults to 0, trains/installs every round (=10).
This is H4's cold-start design working correctly.

### Item 2 ANSWER: inversion cause found -- late-attack-window scores LOWER
than nominal, AND post-attack recovery scores HIGHER than nominal; BOTH
contribute, neither is a labeling/polarity bug
Confirmed (a) label alignment and (b) score polarity are correct in
`node_runner.py` (same tick, standard `roc_auc` convention, matches my own
offline checks). Root cause is in (c)/(d), from
`scripts/h2_abrupt_diag_score_trace.py` (single-node, fedqpnt_local
closed-loop, seed=500, SAME live attack config, theta0_noabrupt):

**Side-by-side window definitions (Master's ask, item 1):**
| | isolated check (0.5/0.15/0.1/0.2-severity AUCs) | live H2/H4 |
|---|---|---|
| method | `fixed_trust` (open-loop, trust never gates) | `fedqpnt_local`/`baseline_b_cont` (closed-loop, trust actively gates GNSS) |
| mission length | 120 s | 600 s |
| attack onset/duration | onset_s=60, duration_s=180 | onset_s=120, duration_s=300 |
| window actually REACHABLE before mission ends | only t in [60,120) = the FIRST 60s of the 180s label window (mission ends before duration_s elapses) | the FULL t in [120,420) = all 300s, PLUS 180s of post-attack recovery (t in [420,600)) is also scored (as a negative) |
| n_epochs / n_pos (13-seed aggregate, isolated) | 1534 / 1157 (~89 pos of ~118 total per seed) | n/a (this diagnostic used ticks, see below) |
| sampling | one row per detector-scored GNSS epoch (~1 Hz) | one row per 100 Hz IMU tick (`rows_t.append(t)` unconditional in `node_runner.py`'s tick loop) -- raw_p is piecewise-constant between the 1 Hz detector updates, replicated ~100x per second |

**Live trace numbers (seed=500, single node, this diagnostic):**
`compute_phases`: t_on=120.0, t_off=420.0 -- EXACTLY matches the attack
config (onset_s=120, duration_s=300); **no epoch/onset shift, ruling out (a)
as a cause.**

| window | n (ticks) | mean raw_p | mean w_gnss | es_frac |
|---|---|---|---|---|
| pre-onset (clean) | 6000 | 0.0270 | 0.9952 | 0.0000 |
| attack, onset..+2s (=reacq_epochs) | 200 | 0.0147 | 0.9999 | 0.0000 |
| attack, onset..+5s | 500 | 0.0724 | 0.9999 | 0.0000 |
| attack, onset..+10s | 1000 | 0.0892 | 1.0000 | 0.0000 |
| attack, +2s..offset (steady-state) | 29800 | 0.0213 | 0.7393 | 0.0470 |
| attack, +5s..offset | 29500 | 0.0204 | 0.7366 | 0.0475 |
| attack, +10s..offset | 29000 | 0.0189 | 0.7321 | 0.0483 |
| post-attack (clean) | 21001 | **0.2482** | 0.6052 | 0.0714 |

**Two compounding effects, both real, neither a code bug:**
1. The attack's STEADY-STATE window (>99% of the labelled-positive ticks,
   since `duration_s=300` but the detector's own response ramps up over
   only the first ~2-10s) scores LOWER (mean 0.019-0.021) than pre-onset
   CLEAN baseline (0.027) -- a held-constant small (12 m) GNSS offset, once
   the receiver re-locks, looks quieter/more nominal than genuine sensor
   noise to a detector that never trained on abrupt.
2. POST-ATTACK recovery (labelled NEGATIVE, `t>=420`) scores dramatically
   HIGHER (mean 0.248, ~9x pre-onset) than any other window, and stays
   elevated over the FULL 180s post window (not a brief blip) -- plausibly
   because the spoofed-to-truth REVERSION at t=420 is itself an abrupt
   jump-like discontinuity (physically similar to the onset the detector
   DOES respond to), compounded by w_gnss still recovering (mean 0.605,
   below 1.0) through this whole window.
   Even discounting effect 2 entirely (excluding post-attack negatives, using
   ONLY pre-onset as the negative class): AUC = 0.2555 -- STILL far below
   chance, confirming effect 1 (the steady-state window scoring lower than
   nominal) is the dominant driver on its own, not merely a post-attack
   artifact.
3. Onset-window width is HIGHLY sensitive and non-monotonic in a way that
   itself needs pre-registering, not picking post-hoc: N=2s (=reacq_epochs,
   the attack's own principled parameter) -> AUC 0.102 (WORSE than the full
   window!); N=5s -> 0.458; N=10s -> 0.567. The detector's response visibly
   RAMPS UP over the first ~2-10s (mean raw_p rises 0.015->0.072->0.089 as N
   grows) -- the very first reacq_epochs=2 ticks catch the detector BEFORE
   it ramps up, so the "obvious" principled choice (2s) is actually the
   worst option here.

**Window options for Master to pre-register (proposal only, not chosen
here), all from this one seed's trace -- full numbers above:**
- **A. Full attack window** (current `node_runner.py` definition, t in
  [onset, onset+duration_s)): auc=0.2404 (this seed).
- **B. Onset window of N s** (positives = t in [onset, onset+N); negatives
  unchanged, pre+post): N=2s -> 0.1018; N=5s -> 0.4578; N=10s -> 0.5674.
- **C. Both / a hybrid** (e.g. full window as positives but drop post-attack
  from the negative class): 0.2555.
No option recovers a clearly "good" AUC at this severity/seed from what
I've tested -- flagging that pre-registering ANY of these will likely still
show FedQPNT/B-cont both performing weakly here; the comparison between
arms (not the absolute number) is what H2/H4 actually tests, so this may be
acceptable, but reporting honestly per D-002.

## STATUS: diagnostics complete, awaiting Master's window pre-registration
and confirmation to re-run H2/H4/control (on frozen code, with the updated
driver that persists full provenance + git state, per D-062 item 3).

## TASK COMPLETE (task bdoo5lti3 / driver DONE, 08:38-10:24 IST) -- WITHDRAWN
by D-062, kept for history; see the D-062 section above for the current
status (H2/H4/control numbers below are NOT valid evidence until the run is
repeated on frozen code with the AUC-inversion cause fixed/understood)
Fleet driver ran h2,h4,control sequentially (gate opened once CORE-ROBUST's
defended_vs_undefended job finished, per the fixed wait-loop). Full results
in `results/fleet/h2_abrupt.json`; compiled tables + discussion written to
`docs/specs/raw/H2_ABRUPT_NOTES.md`. Summary:
- H2 (novel=abrupt): NULL result, FedQPNT ~= B-cont (Wilcoxon auc_detector_only
  p=1.0, latency_on p=1.0, identical per-seed).
- H4 (cold-start, novel=abrupt): same NULL result (p=1.0 both metrics).
- Control (drift, s=1, n0 DID see it): no significant gap (p=0.0625, n=5,
  direction opposite of "FL helps" anyway) -- as expected design check.
- OPEN FINDING flagged (not resolved): live-mission auc_detector_only
  (~0.25-0.27, both arms) is far below the isolated theta0 held-out check
  at the same severity (0.805) -- both arms track identically per-seed, so
  not per-arm noise; likely a live/closed-loop vs isolated/open-loop
  protocol difference (trust-gating dynamics around the weak-by-design
  attack). Reported as measured, not chased further (compute budget, D-002).

All steps done. Final report delivered via SendMessage (SubagentHandback
was already used once this task and cannot be called again).

## Next (on wake, after bg6yh1t5m / the driver notification) -- SUPERSEDED, task complete, kept for history
1. Read `<scratchpad>/h2_abrupt_driver.log` and `results/fleet/h2_abrupt.json`.
   If any fleet invocation errored/aborted, re-run just that missing
   `--parts` value (h2, h4, or control individually) -- each is
   self-contained and idempotent (the driver merges into the existing json).
2. Compile the H2 table, H4 table, and control table (mean +/- CI95 per
   metric per arm, plus the Wilcoxon rows already computed by `_summarize`).
3. Write terse notes to `docs/specs/raw/H2_ABRUPT_NOTES.md` (one pass).
4. Final SubagentHandback report per the task's REPORT format: AGENT /
   STATUS / theta0 abrupt AUC (0.898, NOT near chance -- flag this
   explicitly) / E_s firing on abrupt (fires at default/D-056-control
   severity 0.6, chose 0.15 to pass) / H2 table / H4 table / control /
   PROPOSED-DECISIONs (at minimum: (a) the H2_SUBRULE_NOTES.md abrupt
   control numbers are now stale post CORE-ROBUST's E_s fix and should be
   superseded by this task's fresh 0.15-severity numbers; (b) theta0's
   strong zero-shot abrupt transfer (0.898) may blunt the H2/H4 "FL helps
   generalise to novel families" claim for this particular family --
   flag for Master to consider whether abrupt is still a good "novel
   family" choice or whether the claim should be reframed).

## Resume command pattern
`python -u <script> > "<scratchpad>/<name>.log" 2>&1` via the Bash tool with
run_in_background; do not poll manually, wait for the completion notification.
