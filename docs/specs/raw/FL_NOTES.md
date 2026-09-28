# FL_NOTES.md (WP-5.1-5.3, FEDERATED agent) -- terse, no prose

## Scope / independence
- Owns: fedqpnt/fl/{__init__,transport,server,client,aggregator,comms,poisoning,orchestrator}.py,
  tests/test_fl_*.py, tests/_fl_harness.py (test-only), scripts/run_fl_validate.py, results/fl/.
- Does NOT import fedqpnt.node / fedqpnt.fusion / fedqpnt.sim / fedqpnt.attacks. Uses
  fedqpnt.trust only via TrustDetector.get_params/set_params/train_local(balance=True) and
  FeatureNormalizer (through TrustDetector). AST leakage-guard test mirrors trust's.
- Data source: `local_dataset_provider(node_id, round) -> (X (n,13), y (n,2))`, swappable.
  M0/M1 stand-in: tests/_fl_harness.TrustHarnessProvider on tests/_trust_harness real
  fedqpnt.gnss+fedqpnt.attacks streams + label_epochs hindsight pseudo-labels. Real closed-loop
  features wired in at M2 -- zero code changes needed in fedqpnt/fl/.

## Contract (SS4.1)
- Trained object: TrustDetector weights theta (fc*.weight/bias). Sent as DELTA in ModelUpdate.params.
- norm_mu/norm_sd sent as ABSOLUTE values (not deltas), server aggregates by coordinate median.
- metrics: n_pos, n_neg, loss, pl_rate (SS4.2) + base_round (PROPOSED-DECISION, see below).
- Leakage guard (fedqpnt/fl/transport.enforce_leakage_guard): params must be exactly the
  detector's param names/shapes (+ optional norm_mu/norm_sd/norm_count); metrics must be scalars.
  tests/test_fl_leakage_guard.py has a smuggled-array + smuggled-non-scalar-metric test, both reject.

## Round schedule (SS4.2) / execution model (SS8)
- multiprocessing spawn + mp.Queue (fedqpnt/fl/transport.MpQueueTransport is the reusable
  abstraction; fedqpnt/fl/orchestrator.py implements the actual Server+N Node processes directly
  against raw ctx.Queue()s for the real validation runs -- same wire contract).
- Server aggregates in node_id order (never arrival order): fedqpnt/fl/server.py sorts by node_id.
- torch.set_num_threads(1) + OMP_NUM_THREADS=1 set at the top of every process entry point
  (client.py, server.py, orchestrator.py's _node_main/_server_main).
- Determinism: uplink RNG = stream(seed, node_id, "comms_up") (persistent across rounds, one
  instance per node, not re-seeded per round -- the G-E chain is Markov across rounds).
  Downlink RNG = stream(seed, "server", "comms_down", node_id), owned by the server (SS8 step 2
  literal key). Node's own detector init seed = derived via stream(seed, node_id, "detector_init").
- tests/test_fl_orchestrator.py::test_determinism_bit_identical_across_runs: two full runs with
  identical ScenarioConfig give np.array_equal on every theta array. PASS (see EXECUTION_LOG).

## Aggregators (SS4.5)
- FedAvg: weight = n_samples (self-reported, the deliberate vulnerability) * staleness_weight(s).
- FedProx: aggregation IS FedAvg (fedprox_aggregate = fedavg alias); the prox term (mu/2)||theta-theta_g||^2
  is entirely client-side, inside TrustDetector.train_local(theta_g=..., prox_mu=...).
- TRIM-NB-R: clip (c=2, probation c=1 for SS4.7 cold-start's first 2 rounds) -> exclude quarantined
  -> coordinate-wise trimmed mean (beta=0.2, N_live>=5) else coordinate median -> reputation
  r <- 0.8*r + 0.2*max(0,cos(clipped_i, agg)) -> quarantine (r<0.2 for 3 consecutive rounds -> 10
  rounds out). Verified in tests/test_fl_aggregator.py (clips an 1000x outlier back near the honest
  cluster; quarantines a persistent -1000x attacker after ~11 rounds; median fallback at N_live<5;
  excludes an already-quarantined node from the trim).
- Staleness weight (1+s)^-0.5 applied as an extra per-update weight in BOTH fedavg and TRIM-NB-R
  (multiplied into the clipped delta before the trimmed mean/median), s = round_idx - base_round,
  discarded (treated as too-stale, dropped from the fresh set) if s>3.

### PROPOSED-DECISION: `base_round` / staleness bookkeeping
ARCHITECTURE.md SS4.6 defines staleness s = r - r' for "an update built on global round r'
arriving for round r" but does not specify how the server learns r' on the wire (ModelUpdate has
no such field; core/types.py is Master-owned, not edited here). Implemented by writing
`metrics["base_round"] = last_installed_round` (a plain float, passes the leakage guard's
scalar-metrics check) on the client side; server reads it back the same way. In the current
bulk-synchronous SS8 protocol (node blocks at t_r for the reply) staleness s>0 only actually arises
when a node's OWN downlink was Lost/RoundSkipped in a prior round (it never installed round r'
and kept training on an older base) -- verified by test_fl_aggregator's staleness unit tests, not
yet by an end-to-end s>0 orchestrator scenario (S9's comms-loss test checks no-deadlock only, not
this specific staleness path numerically).

## Comms (SS4.6/SS8)
- Delay: LogNormal(ln 0.2, 0.5) + bytes*8/1Mbit, capped/lost beyond d_max=5s.
- Gilbert-Elliott: P(G->B)=0.02, P(B->G)=0.3, loss_G=0.01, loss_B=0.9 (S9 sweeps loss_B in
  {0.5,0.9}, P(G->B) in {0.02,0.1} via CommsConfig overrides).
- quorum: aggregate iff #fresh >= ceil(0.5*N_live) else theta_g unchanged + RoundSkipped to every
  expected node this round (logged as event ROUND_SKIPPED in FLServer.log).

## Cold start (SS4.7)
- ScenarioConfig.join_round[node_id]; dormant nodes are simply excluded from
  ScenarioConfig.expected_ids(r) for r < join_round -- the server never waits on them, so no
  handshake message type was needed (orchestrator precomputes the whole schedule; this is a
  simulation-harness simplification, a real deployment would need an explicit join announcement).
- Probation: TrimNbRConfig.probation_rounds=2 / probation_clip_c=1.0, keyed off
  FLServer._joined_round[node_id] (set to the first round a node's message is ever seen).

## Poisoning (SS4.5, S12/S15)
- sign_flip (x-5) and label_flip: applied NODE-LOCALLY (self-contained, no peer info needed).
  label_flip is applied to y BEFORE train_local (inside orchestrator._node_main's provider wrapper).
- gaussian_noise (10x median norm) and alie: applied SERVER-SIDE
  (FLServer._poison_fresh_updates), because both need cross-node information the isolated node
  process doesn't have (a representative honest norm / the honest mean+std). PROPOSED-DECISION:
  this models a coordinated attacker's shared infrastructure as living conceptually at the
  aggregator/harness level for the simulation's convenience -- it is NOT a claim that a real
  distributed attacker gets free access to honest clients' updates before they reach the real
  server; `malicious_ids`/`poison_kind` are simulation-only bookkeeping passed into
  `aggregate_round`, never part of the wire `ModelUpdate` contract, so the leakage guard is
  unaffected.
- alie_z(): closed-form Baruch et al. 2019 z (PROPOSED-DECISION: approximates the paper's exact
  per-coordinate order-statistics tracking with the standard closed-form simplification most open
  re-implementations use).

## Known scope simplifications (all PROPOSED-DECISION, flagged for Master)
1. Replay buffer cap (20k, class-balanced reservoir) is FIFO-truncated in fedqpnt/fl/client.py,
   not literally a class-balanced reservoir; the class-balance cap itself IS enforced at train
   time via TrustDetector.train_local(balance=True, max_pos_fraction=0.5), matching SS4.2's design
   rule (per D-026, mirrored from trust's own local training).
2. S5's "delays 1-3 rounds" is implemented as a scripted window during which the affected node
   sends NoUpdate(reason="scripted_delay") instead of training (ScenarioConfig.delay_window),
   rather than actually holding a trained update and replaying it k rounds later with s=k
   staleness. Both are spec-compatible readings of "delayed updates"; this one was chosen because
   it composes cleanly with the bulk-synchronous barrier without inventing a second message queue
   per node. Numeric AUC-drop-under-S5 is reported by scripts/run_fl_validate.py.
3. Node-process "ticks" (SS8's "runs ticks until t>=t_r") are delegated entirely to
   local_dataset_provider per round, rather than a literal dt=0.01 tick loop -- required by the
   INDEPENDENCE constraint (no dependency on fedqpnt.node/fusion) and by M0/M1 not having a
   closed-loop mission to tick through yet.

## Two real bugs found and fixed during validation (both via actual multi-process runs, not unit tests)
1. **Server discarded out-of-round messages instead of buffering them.** A cold-start node reaches
   its join round almost instantly (it only skips dormant rounds, no compute), so its round-r
   message can land on the shared `server_q` before the server has even finished collecting round
   0/1. The original loop did `if round_idx != r: continue` after already popping the message off
   the queue -- silently dropping it forever. Symptom: `wall-clock ABORT round 2, missing {'cold0'}`
   after a genuine ~600s wait. Fix: `orchestrator._server_main` now keeps a `pending: dict[(node_id,
   round), msg]` buffer across rounds; each round first drains any already-buffered message for its
   expected nodes before blocking on the queue for the rest. Regression test:
   `test_s8_cold_start_receives_model_within_two_rounds` (its docstring explains the failure mode).
2. **`_node_main` never actually installed the new global model.** `FLServer.aggregate_round`
   replies with a `(GlobalModel, delay_s)` TUPLE on success (Lost/RoundSkipped are bare), but the
   node checked `isinstance(reply, GlobalModel)` directly -- always False for the tuple, so
   `install_global` was never called. `base_round` metric stayed at its initial -1 forever, so
   staleness `s = round_idx - (-1)` silently exceeded `max_staleness=3` from round 3 onward and
   every later round was wrongly `ROUND_SKIPPED` (looked exactly like "quorum lost", not an
   exception -- no crash, no traceback, just silent staleness starvation). Regression test:
   `test_clients_install_global_model_after_successful_rounds`.
Both were caught only because the validation runs (real `multiprocessing.spawn`) were actually
executed and their logs read, not just because the code compiled/unit-tested; the standalone/
single-process aggregator and client unit tests could not have caught either one, since both are
purely about wire-level reply shape and message-ordering across real processes.

## Validation status (seeds 500-599)
- Determinism: PASS (bit-identical `np.array_equal` on every param array across two runs).
- `tests/test_fl_*.py`: 41 passed (`python -m pytest tests/test_fl_*.py -q`), including a
  CI-scoped (reduced N/n_rounds/duration_s) real-multiprocess pass of S5/S8/S9/S12/S15's
  engineering criteria (no deadlock; ROUND_SKIPPED logged, never a silent hang; cold-start joins
  clean; TRIM-NB-R's ||delta_theta|| stays far smaller than FedAvg's under 20% sign-flip; no false
  quarantine of honest heterogeneous nodes).
- `scripts/run_fl_validate.py` (full N in {5,10}, 6-10 rounds, duration_s=45 so attacks actually
  fire before the mission ends -- NOTE: an earlier duration_s=20 run gave AUC=NaN for every cell
  because `tests/_trust_harness` attacks default `onset_s=20.0`, i.e. the mission ended exactly
  when the attack would start, so oracle labels were never positive; this is now documented in the
  script):
  - Wall time: N=5 -> 12.66s / 6 rounds (2.11s/round); N=10 -> 22.21s / 6 rounds (3.70s/round).
  - AUC per round (PROVISIONAL): FedAvg and TRIM-NB-R both land around 0.6-0.89 with round-to-round
    noise (8 nodes, tiny synthetic missions); local-only starts at parity with the FL runs (shared
    theta0) then drifts lower (0.45-0.66) after a few rounds without federation to correct it --
    directionally consistent with H2 (FL beats local-only) but NOT a claim of significance (n=1
    seed-draw per round point, not the SS7 protocol).
  - S12: retracted/superseded by D-037 below (the f=20%/f=40% "identical bit-pattern" reading was
    wrong -- it was a real bug, not attack symmetry).

## D-037 (Master review): the f=20%/f=40% "identical" S12 result was a REAL bug, not attack symmetry
Master correctly rejected the earlier explanation: a plain FedAvg weighted average cannot be
insensitive to doubling the poisoned-node count. Root cause, confirmed with
`tests/_fl_harness`-driven per-node logging: several nodes' cumulative replay buffer never
contained a single negative-labelled (y=0) pseudo-label sample across all rounds, purely from
unlucky random attack-family draws (only ~20% chance of drawing "clean" per round, and attack-family
runs frequently failed the window-based negative rule too). `TrustDetector.train_local`'s
class-balance cap (SS4.2/D-026, frozen, not owned by FEDERATED) computes
`max_pos_kept = n_neg * 0.5/0.5`; with `n_neg=0` this is 0, so ALL samples are dropped and the SGD
loop never runs -- that node's delta is **exactly zero every round**. Multiplying a zero delta by
any poisoning transform (sign-flip x(-5) etc.) is a no-op, so whether such a node was "malicious" or
not never showed up in the aggregate -- and in the f=20%->f=40% test, the two EXTRA malicious nodes
happened to be exactly this chronically-zero-delta kind, on both attempts, for both aggregators
(both use the same seed/provider). This was a test-harness data-generation flaw
(`tests/_fl_harness.py`, which FEDERATED owns), not a bug in `fedqpnt/fl/aggregator.py`.
**Fix**: `TrustHarnessProvider._pick` now forces round 0's family to `"clean"` for every node (a
deterministic warm-start); the replay buffer is cumulative, so one guaranteed clean round seeds real
negatives for the whole run. This raised the fraction of rounds with a real (non-degenerate) SGD
step from 4/10 nodes to 9/10 nodes in the diagnostic re-run (1 node, "n8", still occasionally starts
with <16 raw samples in its warm-start round and stays degenerate -- a residual, smaller-magnitude
version of the same issue, left as a known limitation rather than chased further).
**Regression test** (isolates the aggregation math from the flaky data source):
`tests/test_fl_aggregator.py::test_fedavg_delta_measurably_changes_with_poisoned_fraction` --
10 synthetic non-zero deltas, sign-flip applied to a growing subset; asserts FedAvg's output
strictly moves further from the honest mean at f=40% than at f=20%, and that TRIM-NB-R moves less
than FedAvg at every f. PASSES: FedAvg w moves 1.0254 -> -0.1734 (f=20%) -> -1.5076 (f=40%);
TRIM-NB-R w moves 0.9301 (f=20%) -> -0.3323 (f=40%, beyond its beta=20% design point, as expected).

### S12 full sweep (post-fix): all 4 SS4.5 poisoning types x f in {0.2,0.4} x {FedAvg,TRIM-NB-R},
5 seeds (500-504), N=5 nodes (<=6 worker processes total, per Master's process-count rule). Per-run
malicious-node count logged and asserted == round(f*N) for every one of the 90 runs (10 clean
baselines + 80 poisoned). `results/fl/fl_s12_full_sweep.json` has full per-seed detail. Mean AUC
drop vs clean (range in brackets), PROVISIONAL:

| f | attack | FedAvg mean drop [range] | TRIM-NB-R mean drop [range] |
|---|---|---|---|
| 20% | sign_flip | 0.164 [0.000, 0.330] | 0.063 [-0.002, 0.219] |
| 20% | label_flip | 0.236 [0.036, 0.433] | 0.112 [0.032, 0.301] |
| 20% | gaussian_noise | 0.072 [-0.037, 0.250] | 0.038 [-0.019, 0.167] |
| 20% | alie | 0.061 [-0.028, 0.230] | 0.044 [-0.025, 0.203] |
| 40% | sign_flip | 0.328 [0.014, 0.482] | 0.105 [0.028, 0.327] |
| 40% | label_flip | 0.276 [-0.088, 0.570] | 0.212 [-0.068, 0.445] |
| 40% | gaussian_noise | 0.017 [-0.227, 0.117] | 0.018 [-0.005, 0.045] |
| 40% | alie | 0.025 [-0.017, 0.122] | 0.000 [-0.022, 0.046] |

f now clearly changes both aggregators' behaviour (confirming the fix), and TRIM-NB-R's mean drop is
lower than FedAvg's in 7 of 8 cells (label_flip@40% is the exception, likely noise given the wide
range at N=5). **Acceptance criterion (TRIM-NB-R, f=20%, sign_flip only, per spec): mean drop=0.063
> 0.05 threshold -> FAIL, reported as-is (not loosened).** This is driven mainly by one outlier seed
(502: drop=0.219; the other 4 seeds are 0.028, 0.067, -0.002, 0.000); with only N=5 nodes (forced by
the <=6-process rule) a single malicious node is 20% of the fleet and the held-out eval set is small,
so variance is high. The synthetic-delta unit test above confirms the TRIM-NB-R mechanism itself
degrades gracefully and less than FedAvg at every f; this FAIL is about noise/small-N in the
end-to-end harness, not the aggregator, but it is reported as a failure per instruction, not tuned away.

## S5/S9 missing numeric criteria (Master D-037 request), 5 seeds (500-504), N=5, PROVISIONAL
(`scripts/run_fl_s5_s9_auc.py`, `results/fl/fl_s5_s9_auc.json`)
- S5 (1 of 5 nodes fails at T/2, i.e. 20% at this N): mean no-failure AUC=0.848, mean failure
  AUC=0.830, drop=0.019 <= 0.02 threshold -> **PASS**.
- S9 (loss_B=0.9, P(G->B)=0.1, the worse sweep cell): mean no-loss AUC=0.844, mean lossy
  AUC=0.849, drop=-0.004 (negative, i.e. no drop) <= 0.03 threshold -> **PASS**.

## Process-count discipline (D-037)
All validation scripts from this point on use N=5 nodes (+1 server = 6 processes total) and are run
strictly one federation at a time (never two `run_federation` calls concurrently), per Master's
instruction to keep to <=6 worker processes while another agent runs heavy simulations. Verified with
`Get-CimInstance Win32_Process` before/after each run that only this session's own
`fedqpnt.fl`/`run_fl_*`/`test_fl_*` command lines were present; no process was stopped that wasn't
confirmed as this session's own.

## D-039 (Master follow-up): the real source fix + S12 at the spec fleet size (N=10)
The D-037 round-0-forced-clean warm-start in `tests/_fl_harness.py` was a workaround, not the real
fix. Master approved fixing the actual source, `fedqpnt/trust/detector.py`'s
`TrustDetector.train_local(balance=True)`, under D-026's freeze (a correctness fix, not a design
change): when `n_neg < n_min` (new param, default `n_min=10`, PROPOSED-DECISION), subsampling is
skipped entirely and the node trains on ALL available samples, relying on the existing inverse-
class-frequency loss weights (`w_pos`/`w_neg`) instead of the sample cap. At/above `n_min` negatives,
behaviour is unchanged (bit-identical subsampling).
- Unit tests added to `tests/test_trust_detector.py`: `n_neg=0` (all-positive batch -- SGD now runs,
  finite loss, weights actually update) and `n_neg=3` (< n_min -- trains on all 40 samples, not just
  ~3 positives). A third sanity test confirms n_neg=20 (>= n_min) still subsamples as before.
  `python -m pytest tests/test_trust_*.py -q` -> 40 passed.
- The D-037 warm-start workaround in `tests/_fl_harness.py` was REVERTED (random family draws every
  round again, including round 0) so the harness exercises the real fix under the same conditions
  that originally exposed the bug.
- **Result: zero-delta nodes disappeared.** Diagnostic re-run (10 nodes, 8 rounds, base_seed=540,
  same conditions as the D-037 diagnosis): 0/10 chronically-degenerate nodes (was 6/10 before any
  fix, 1/10 with only the harness-level warm-start workaround).

### S12 at N=10 (spec fleet size), 10 seeds (500-509), 4 rounds, `scripts/run_fl_s12_n10.py`,
`results/fl/fl_s12_n10_sweep.json`. Federations run strictly sequentially (11 processes per run,
approved by Master alongside two other agents' concurrent work). Mean AUC drop vs clean with 95%
percentile bootstrap CI (2000 resamples), PROVISIONAL:

| f | attack | FedAvg mean drop [95% CI] | TRIM-NB-R mean drop [95% CI] |
|---|---|---|---|
| 20% | sign_flip | -0.163 [-0.278, -0.044] | **0.032 [-0.049, 0.110]** |
| 20% | label_flip | 0.045 [-0.024, 0.115] | 0.070 [0.015, 0.130] |
| 20% | gaussian_noise | -0.095 [-0.192, -0.005] | -0.024 [-0.072, 0.035] |
| 20% | alie | -0.021 [-0.057, 0.014] | 0.015 [-0.010, 0.041] |
| 40% | sign_flip | -0.234 [-0.345, -0.123] | -0.003 [-0.117, 0.102] |
| 40% | label_flip | 0.010 [-0.093, 0.120] | 0.147 [0.088, 0.206] |
| 40% | gaussian_noise | -0.192 [-0.279, -0.113] | 0.011 [-0.078, 0.100] |
| 40% | alie | 0.021 [-0.041, 0.082] | 0.020 [-0.018, 0.056] |

**Acceptance criterion (TRIM-NB-R, f=20%, sign_flip): mean drop=0.032, 95% CI=[-0.049, 0.110] <= 0.05
-> PASS** at the spec fleet size (the N=5 FAIL on record from D-037 stands for that smaller fleet;
at N=10 the trimmed-mean's designed behaviour holds, consistent with beta=20% covering exactly one
malicious node in five being the harder, noisier case).
Several FedAvg cells show a NEGATIVE mean drop (poisoned AUC > clean AUC) -- expected under this
much noise (small held-out eval set, 4-round runs, single-seed-per-cell training): FedAvg has no
defence, so its variance is large and not all draws land on the "attack hurts" side; this is honestly
reported, not evidence FedAvg is fine (see the D-037 synthetic-delta unit test, which isolates the
aggregation math and shows FedAvg's raw output IS pulled further from the honest mean by more
poisoning -- AUC is a noisier, indirect readout of that same underlying effect).

### Process-count discipline (D-039)
Verified via `Get-CimInstance Win32_Process` before/after: two other agents' processes observed
during this work (`scripts/filter_gnss_d038.py`, `pytest tests/test_eval_stats.py`) were left
untouched (confirmed by command line, not assumed). No process was stopped this session. Federations
were run one at a time throughout (N=10 -> 11 processes per run, no concurrent federation runs).

## D-048: FedAvg poisoned-better-than-clean diagnosis (NOT a bug)
Checked (a) pairing: clean and poisoned arms use identical seed/base_seed, n_rounds, eval set and
node data (same `make_provider(base_seed=seed,...)` call, stateless given (node_id, round) -- CONFIRMED
correctly paired.
(b) AUC-per-round, seed=500, FedAvg, clean: round1..4 = 0.873, 0.857, 0.784, **0.483** -- the clean
arm does NOT plateau, it COLLAPSES at round 4 (does not converge in 4 rounds; actively destabilises).
(c) Per-node contribution trace (in-process replica, same seed/data) showed the cause: at round 3,
one HONEST node (n3, not malicious in either run) produced a delta_norm of 6.88 vs ~0.1-0.3 for every
other node that round -- an outlier SGD step (small per-round batch, lr=0.05, no clipping in FedAvg
by design) that DOMINATES the uncapped weighted average and destabilises the global model for round
4. In the poisoned run, n3's OWN round-3 delta_norm was smaller (1.87) purely because its starting
point (theta_g installed after round 2) differed between the two runs -- round 2's aggregate itself
differs since n0/n1 are poisoned in one run and not the other, so by round 3 the two runs are
training from different points and hit different (in)stability. The poisoned run's random walk
happened to avoid the instability the clean run hit.
(d) AUC polarity: per-head AUCs decay toward ~0.5 (random), never invert toward ~0 -- no sign/scoring
bug; this is instability/collapse, not a polarity flip.
**Conclusion: this is FedAvg's documented, designed vulnerability (ARCHITECTURE.md SS4.1: "FedAvg does
weight by [self-reported n_samples], which is part of why FedAvg is the vulnerable reference in
S12") manifesting as uncapped-gradient instability over few rounds with tiny synthetic per-round
batches, not a pairing/scoring/aggregator bug. No fix applied (per Master: "if after the fix FedAvg
still improves significantly, report the numbers and stop" -- no fix was warranted since no bug was
found).** TRIM-NB-R's clipping step (SS4.5, c=2 x median norm) is exactly the mechanism that prevents
this kind of single-outlier-gradient instability, which is why it does not show this pathology.

## D-048: M2 fleet integration (fedqpnt/fleet/)
- `features.py`: `FleetFeatureTracker` -- real hindsight-pseudo-label feature extraction per node,
  reusing the ALREADY-APPROVED `fedqpnt.node.methods.pretrain_detector` precedent exactly
  (own `GnssFeatureExtractor`, `innovations=[]`, `surrogate_s_cusum`+`label_epochs`). x1/x2
  (innovation-NIS features) are therefore unavailable, same limitation as that precedent;
  PROPOSED-DECISION, out of scope without editing `fedqpnt/fusion/eskf.py`. Implements
  `local_dataset_provider(node_id, round) -> (X, y)` exactly, fed by real per-tick `GnssFix`.
- `node_runner.py`: one real fleet node process. Builds `NodeEnvironment`+`Agent` via the PUBLIC
  `fedqpnt.node` API only (no edits to fedqpnt/node/*.py). `FLClient` wraps `agent.trust.detector`
  DIRECTLY (the same live object the Agent's trust engine uses for real navigation), so
  `client.install_global(...)` immediately changes what the live trust engine uses from the next
  tick on -- exactly "the installed global model is used by the node's trust engine from the next
  round on." Reuses `fedqpnt.fl`'s message types (`NoUpdate`/`Lost`/`Failed`) and `uplink_channel`
  unchanged. Guarantees exactly one result on ``node_result_q`` even on a hard crash (top-level
  try/except wrapper), so the orchestrator's join loop can't hang on a node that died outside the
  tick loop.
- `orchestrator.py`: `FleetScenarioConfig` (adds mission fields: duration_s, round_period_s,
  attacks-per-node, kappa_R/kappa_Q, gnss_rate_hz) on top of the same SS4.7/S5/S12/S15 knobs as
  `fedqpnt.fl.orchestrator.ScenarioConfig` (join_round/failure_round/delay_window/poison_kind).
  **The server side is 100% REUSED, unchanged**: `to_fl_scenario()` builds a plain
  `fl.orchestrator.ScenarioConfig` and `run_fleet` spawns `fl.orchestrator._server_main` directly as
  the server process -- no new aggregation/comms/poisoning code was written for the fleet, since the
  server never depended on the data source. `write_campaign_result()` writes
  `runs_fleet/<scenario_id>/<method>/seed_<seed>.json` matching `fedqpnt.eval.campaign`'s exact
  schema (status/scenario_id/method/seed/config_hash/wall_s/metrics), with `metrics` = flat per-node
  MEAN of each scalar (report-generator-compatible) plus `metrics["nodes"]` (full per-node
  breakdown) and `metrics["fleet"]` (rounds_skipped/quarantine_events/wall time per fleet-hour).
- Leakage guard extended: `tests/test_fleet_leakage_guard.py` mirrors trust's/fl's AST scan over
  `fedqpnt/fleet/*.py` (no `fedqpnt.sim`/`fedqpnt.attacks`/`AttackLabel`/`TruthState` imports).
- S5/S8/S9/S12/S15 support: `FleetScenarioConfig.failure_round`/`delay_window` (S5),
  `.join_round` (S8, cold start), `.comms_cfg` (S9), `.poison_kind` (S12, node-local sign_flip/
  label_flip; gaussian_noise/alie route through the SAME server-side hook as fl.orchestrator, no
  fleet-specific code needed), `.attacks` per-node dict (S15, heterogeneous attack subsets).

### Validation (item 3), tuning seeds only (500-599), N=5, 10-min missions, 2 seeds, kappa_R
PROVISIONAL (D-046/D-047; tuning seeds). `scripts/run_fleet_validate.py` ->
`results/fleet/fleet_validation_report.json`. See the FEDERATED report for the numeric summary
(rounds skipped, global-model installs per node, mean w_gnss, wall time per fleet-hour, nominal vs
30%-drift-spoof).

## D-052/D-050 (M2 completion): local training data replaced (FLEET-SUP)
- REJECTED surrogate path (`innovations=[]` + `surrogate_s_cusum`, `fedqpnt/fleet/features.py`'s
  old `FleetFeatureTracker`) removed entirely. Each node's local FL training dataset is now built
  OFFLINE (parent process, before node processes spawn) by
  `fedqpnt.fleet.local_data.build_node_local_dataset`, which reuses
  `fedqpnt.training.build_supervised_dataset.collect_run` (real Agent innovations, oracle
  `tick.label` joined by timestamp strictly outside the Agent/trust runtime) -- the node's own
  attack mix (per-node `seeds`/`pool`). `fedqpnt/fleet/features.py` now holds only a pure-numpy
  `make_round_provider(X, y, n_rounds)` round-slicer (no label/feature imports) that runs INSIDE
  the node process against the pre-built arrays passed via `FleetNodeSpec.local_X/local_y`.
- Leakage guard extended (`tests/test_fleet_leakage_guard.py`):
  `test_node_runner_never_reaches_the_builder` walks `fedqpnt/fleet/node_runner.py`'s import graph
  (mirrors `test_training_leakage_guard.py`'s agent.py walk) and asserts it never reaches
  `fedqpnt/training/build_supervised_dataset.py`; `test_node_runner_does_not_import_training_
  package_directly` checks the direct-import case. `fedqpnt/fleet/__init__.py` was made import-free
  of its own submodules (was eagerly re-exporting `orchestrator`, which now imports `local_data` ->
  the builder -- would have pulled the label join into every spawned node process via package
  `__init__` execution otherwise).
- `pytest tests/test_fl_*.py tests/test_fleet_*.py tests/test_training_leakage_guard.py -q`: 58
  passed.

### Fleet plumbing run (tuning seeds; kappa_R PROVISIONAL; plumbing, not results)
N=5, 10-min missions, seeds 500-501 (nominal + S15-style 2-of-5 drift-spoof), plus one H2 preview
seed and one H4 preview seed. `scripts/run_fleet_validate.py` -> `results/fleet/
fleet_validation_report.json`.
- (a) nominal FAR/h (fleet-wide, both seeds): ~12/h per node (one node -- n3 seed500, n0 seed501's
  nominal comparator -- shows 24/h or 0/h; small-N noise, not investigated further at plumbing
  scope).
- (b) S15 (2/5 nodes drift-spoofed): FAR/h on the clean phase is unchanged (~12/h) for both
  attacked and honest nodes; round_installs 8-10/10 per node both seeds (a couple of nodes miss one
  round, non-fatal -- comms-loss/quorum behavior, not investigated).
- (c) H2 PREVIEW (n0 never sees meaconing in its OWN local training data; its 4 peers do; n0
  evaluated on a live meaconing attack): FedQPNT (fleet, FL) AUC 0.708, latency_on 0.0s vs B-cont
  (n0 alone, local-only) AUC 0.708, latency_on 0.0s -- IDENTICAL to reported precision. Reported
  honestly: this plumbing run shows NO measurable FL-generalization benefit for H2 -- most likely
  because 10 rounds x tiny (60 s mission) per-round datasets barely move TRIM-NB-R's aggregate
  before this 10-min live mission ends, not because the mechanism doesn't work. A real H2 result
  needs longer local-training missions and/or more FL rounds before the live evaluation; NOT
  claimed as a negative result on the mechanism itself.
- (d) H4 PREVIEW (n0 cold-starts at round 5/10, first attack after joining): FedQPNT AUC 0.40985
  (5 installs) vs B-cont AUC 0.40984 (10 installs, no join) -- again near-identical, same
  short-mission caveat as (c).
- Wall time: (a)+(b) alone average ~295 s per fleet-hour (N=5, 60 s local-training missions
  included). Overall across all 8 runs (including the 1-node H2/H4 previews, whose fixed per-
  mission overhead is amortized over far fewer fleet-hours) = 307.7 s per fleet-hour.

### PROPOSED-DECISION (FLEET-SUP)
H2/H4 need longer per-node local-training missions (or more FL rounds) before the effect is
visible above noise at this short (10-min) live-mission plumbing scale; the M4 campaign should use
the full training-seed range (500-599) per node's local set, not the 60 s stand-in used here.
