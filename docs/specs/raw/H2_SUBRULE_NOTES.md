## H2-SUBRULE (D-056 protocol implementation) -- kappa_R PROVISIONAL; TUNING SEEDS

Agent: H2-SUBRULE. Implements DECISION_LOG D-056's amended H2/H4 evaluation
protocol on top of D-054's theta0 (results/fleet/theta0_d054.npz, restricted
to clean/abrupt/jam_* -- no drift, no meaconing) and D-054.3's chosen FL
hyperparams (local_epochs=2, lr=0.05, prox_mu=0.0, R=10, same for all FL
methods). Detector and trust-law design UNCHANGED; only read-only metric
logging was added (see "Instrumentation" below).

### Instrumentation (D-056 item 1)
`fedqpnt/trust/trust_law.py::TrustEngineImpl`: added two read-only
attributes, `last_raw_p` (the calibrated detector p BEFORE E_s/law fusion,
set at the same point `_gnss_p` is computed) and `last_es_evidence` (the
`_physical_spoof_evidence` boolean for that tick). Neither is read by any
control-flow branch -- purely a logging side channel, reset in `reset()`.
`fedqpnt/fleet/node_runner.py`: captures these into `rows_raw_p`/`rows_es`
per tick (mirroring the existing `rows_score` pattern) and adds two new
scalar fields to the per-node result dict:
  - `auc_detector_only = M.roc_auc(raw_p_arr, active)` -- metric (a).
  - `es_fire_frac_attack = mean(es_arr[active])` -- metric (d).
The existing `auc` field (built from `anomaly_scores` = p_bar) remains
metric (b); `latency_on`/`t_dist` (existing fields) are metric (c).

### Sub-rule verification (D-056 item 2) -- scripts/subrule_search_d056.py
Single-node, no-FL diagnostic (theta0 pretrained weights, method=
baseline_b_cont so trust_law_version=v2/E_s is active), 260 s missions,
60-240 s attack window, seed 500. Sweep:
  - **drift**: severity in {0.5, 0.75} x cn0_sig_scale in {1.0, 0.3, 0.1,
    0.05, 0.0}. Result: **es_fire_frac_attack = 0.9945 for EVERY combination**
    (10/10 cells identical to 4 decimals) -- **FAILS the <=5% target by a
    wide margin, and is completely insensitive to cn0_sig_scale.**
  - **meaconing**: cn0_bump_db in {2.9, 2.0, 1.0} x replay_delay_m in
    {300, 150, 75, 30}. Result: **es_fire_frac_attack = 0.9834 for EVERY
    combination** (12/12 cells identical) -- **also FAILS, insensitive to
    both cn0_bump_db and replay_delay_m.**

### Root cause (scripts/subrule_decompose_d056.py)
Decomposed E_s into its 4 disjoint terms for one representative cell each
(drift sev=0.5/cn0_sig_scale=0.0; meaconing bump=1.0/delay=30 m):

| family     | clk_frac | xsat_frac | cn0_frac | **pos_frac** | any_frac | first_fire_t | mean_w_gnss |
|------------|----------|-----------|----------|--------------|----------|---------------|-------------|
| drift      | 0.000    | 0.170     | 0.060    | **0.874**    | 0.9945   | 61.0 (onset 60.0) | 0.057 |
| meaconing  | 0.006    | 0.105     | 0.000    | **0.878**    | 0.9834   | 61.0 (onset 60.0) | 0.058 |

**`position_event` (the dof-normalised x1/NIS chi2 gate at the 99.9%
quantile, `_IDX_NIS_POS`) dominates in both families, not clk/xsat/cn0** --
the two channels the D-056 decision's tuning knobs (cn0_sig_scale,
cn0_bump_db/replay_delay_m) target are near-silent (cn0_frac<=0.06,
clk_frac<=0.006) exactly as intended. `position_event` fires ONE epoch
after attack onset and then persists for ~87-88% of the 180 s attack
window, coincident with `mean_w_gnss` collapsing to ~0.057 (near w_min=0.02)
almost immediately. **This is the D-055 gate-lockout-harm mechanism
(distrust -> free-inertial coasting -> the EKF's OWN state diverges from
truth -> its position innovations become persistently large relative to
its own diverged prior, independent of the attacker's designed physical
signature) tripping E_s's position gate as a SECOND-ORDER consequence of
trust exclusion, not as a first-order physical-evidence check on the
attack itself.** Because trust exclusion is driven by the learned detector
score (`p_source="detector"`) which theta0 generalises onto BOTH novel
families almost immediately (w_gnss down at t=61s, one epoch after onset),
tuning the attack's own physical signature (cn0_sig_scale, cn0_bump_db,
replay_delay_m) cannot prevent the position-NIS feedback loop that follows
detection -- the two mechanisms are coupled through the shared EKF/NIS
pipeline, not independent as D-056's design implicitly assumed.

### Verdict (D-056 item 2 fallback: "if you can't find sub-rule parameters
### for a family, say so and drop that family")
**Both drift (s in {0.5,0.75}) and meaconing (cn0_bump<3dB, small delay)
FAIL the <=5% E_s-firing target across the full swept grid and are DROPPED
from the H2/H4 full-mission run.** This is not a parameter-search failure
(the swept knobs are already at their extremes, including fully disabling
the C/N0 signature at cn0_sig_scale=0.0) -- it is a structural interaction
between the continuous trust law's exclusion dynamics and E_s's
position-NIS term, present for BOTH families as soon as the detector's own
p crosses theta_on. A genuine sub-rule regime (E_s silent while the
learned detector alone carries the signal) is not reachable for these two
families under the current trust-law/detector coupling.

### H2/H4 full-mission runs: NOT executed for drift/meaconing
Given the above, the N=5, >=5-seed, 600 s H2/H4 fleet runs specified in
D-056 items 3/4 were **not run** for either novel family -- their
precondition (item 2) is not met, and running them would produce AUCs
dominated by E_s-driven p_bar saturation exactly like the D-054 preview
Master already ruled invalid (identical failure mode: both arms detect via
the rule floor, not learned transfer).

### CONTROL (D-056 item 5): family = abrupt_spoof
theta0 already saw `abrupt` (D-054.1 restricted set = clean+abrupt+jam_*)
AND n0's own local FL training pool includes it (no exclusion), so this is
the "n0 DID see it locally" arm -- a design check, not a novel-family test.
Running with the SAME instrumentation/pipeline (N=5, 5 seeds [500-504],
600 s live missions, theta0 + D-054.3 hyperparams) via
`scripts/h2_h4_subrule_d056.py --parts h2_control`. **This run is
compute-heavy** (each `fedqpnt_local` seed needs 5 nodes' worth of local FL
training data built sequentially in-process before the fleet even starts --
~700-900 s per seed -- plus the 600 s x N=5 fleet mission itself; ~5-10 min
per fleet invocation, ~10 invocations total, so the full 5-seed table takes
on the order of 1-1.5 h wall time) and was still running in the background
when this note was written. Partial results so far (raw per-seed n0
values, NOT yet the full run's CI table):

| seed | method | auc_detector_only (a) | auc / p_bar (b) | es_fire_frac_attack (d) |
|------|--------|------------------------|------------------|--------------------------|
| 500  | fedqpnt_local   | 0.6533 | 0.5962 | 0.0067 |
| 500  | baseline_b_cont | 0.6689 | 0.6239 | 0.0067 |
| 501  | fedqpnt_local   | 0.6797 | 0.6046 | 0.0000 |
| 501  | baseline_b_cont | (running) | | |

Already visible in this partial data: **E_s fires in <1% of attack epochs
for `abrupt` (vs ~98-99% for drift/meaconing)**, confirming `abrupt` is a
genuinely rule-quiet control family whose AUC is carried by the learned
detector, not the physical-evidence floor -- and FedQPNT/B-cont track each
other closely per seed (no gap), as expected when n0 already has the
family locally (design-check PASS so far, n=2/5 seeds). The full run
continues writing to `results/fleet/h2_h4_subrule_d056.json` (key
`h2_control_abrupt`, including the paired Wilcoxon on auc_detector_only/
latency_on once all 5 seeds land) and to this same log
(`scratchpad` path noted in the agent's tool transcript) -- re-run
`python scripts/h2_h4_subrule_d056.py --parts h2_control` to resume/redo if
the in-flight process was interrupted (it overwrites `h2_control_abrupt`
only, other keys in the JSON are preserved).

### PROPOSED-DECISIONs (for Master)
1. D-056's sub-rule regime cannot be reached for drift/meaconing via
   attack-parameter tuning alone (cn0_sig_scale / cn0_bump_db /
   replay_delay_m) because E_s's position_event term is triggered by the
   trust law's OWN exclusion-driven EKF divergence, not by the attacker's
   physical signature -- the two are coupled, not independent as the
   protocol assumed. Either (a) find/design a novel family+severity where
   the LEARNED detector itself stays below theta_on (so trust never
   excludes, so the EKF never free-inertial-coasts, so position_event never
   fires) -- but that may make the family undetectable by design and moot
   the H2 question; or (b) accept that a genuine "below-the-rule-floor"
   H2/H4 test is not achievable for spoofing-class attacks under the
   current continuous trust law + E_s coupling, and reframe H2/H4 around a
   family/channel where detection and trust-exclusion are less tightly
   coupled (e.g. a jamming variant, where the trust law's recovery
   semantics differ per `_METHOD_TABLE`/law_mode).
2. This finding sharpens D-055's gate-lockout-harm mechanism: it is not
   just a downstream RMSE_h harm (2360 m vs 108 m at s=0) but ALSO
   contaminates the safety-floor rule (E_s) that D-056 was trying to
   isolate FROM the learned detector's contribution -- E_s and the
   detector-driven trust dynamics are not actually independent evidence
   channels once trust exclusion begins.
