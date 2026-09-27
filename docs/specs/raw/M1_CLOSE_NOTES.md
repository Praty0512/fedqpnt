# M1_CLOSE_NOTES -- WP M1-CLOSE (terse implementation record)

Reads: D-026 (detector design FROZEN), D-029 (retrain on real features),
D-035, D-043, D-046 (kappa_R=40 PROVISIONAL, overconfidence PARKED).
Reuses fedqpnt/node/{runner,methods,agent,environment}, scripts/run_m1_smoke.py,
scripts/tune_kappa_r.py. Did NOT edit fedqpnt/fusion/eskf.py, fedqpnt/core,
fedqpnt/gnss, fedqpnt/fl.

## Task 1: kappa_R = 40 PROVISIONAL -- CONFIRMED, no retune

`fedqpnt/node/agent.py::AgentConfig.kappa_R = 40.0` and
`fedqpnt/node/methods.py::DEFAULT_KAPPA_R = 40.0`, both commented PROVISIONAL
(D-023/D-027/D-046). Not touched.

## Task 2: detector retrained on REAL closed-loop features

New script `scripts/retrain_detector_real.py`. Design UNCHANGED (D-026:
xsat rule on, class-balanced local training). Runs the REAL Agent
(GnssReceiver.solve -> ESKF propagate/innovations/correct with FIELD CAI,
method="fixed_trust", kappa_R=40) over seeds 500-599, ground/industrial_mems,
300 s/run: 20 clean-calibration seeds (500-519, quantile reference, D-024/026
style, never self-referential), 60 training seeds (520-579, 1-in-5 clean +
4 attack families cycled), 20 disjoint held-out seeds (580-599, same mix).

Real features captured by wrapping (monkeypatch, not editing)
`TrustEngineImpl.extractor.step` on the running instance -- x1/x2 (nis_pos/
nis_vel) are now REAL ESKF innovations, not the always-zero placeholder the
old `methods.pretrain_detector` used. The hindsight divergence statistic fed
to `label_epochs` is `surrogate_s_cusum`'s SAME Page-CUSUM formula, now fed
REAL (nonzero, FIELD-CAI-aided) x1 -- per D-029 this is no longer a
surrogate: with a genuine running ESKF fusing CAI, nis_pos (innovation
before correction) literally IS "the CAI-aided-INS-vs-GNSS divergence" the
spec calls for. Weights + provenance (config hash, seeds, date, method,
kappa_R) -> `results/m1/detector_weights_real.npz` /
`results/m1/detector_retrain_report.json`. Labelled "tuning seeds, not for
publication" throughout.

Wall: 624 s collection (100 runs, 6 workers) + training/eval, 27072 epochs.

Pseudo-label precision/recall vs oracle (train pool, evaluator-only):
precision=0.602, recall=0.995, n_oracle_pos=4734.

AUC old (synthetic, D-026 frozen table) vs new (real closed-loop), held-out:

| family    | old (synthetic) AUC [CI]     | new (real) AUC [CI]           |
|-----------|-------------------------------|--------------------------------|
| overall   | 0.722 [0.697, 0.749]          | 0.835 [0.825, 0.845]           |
| drift     | 0.724 [0.652, 0.792]          | 0.924 [0.903, 0.941]           |
| meaconing | 0.575 [0.501, 0.652]          | 0.997 [0.995, 0.999]           |
| abrupt    | 0.749 [0.678, 0.817]          | 0.413 [0.380, 0.447]  (BELOW CHANCE) |
| jamming   | 0.515 [0.422, 0.603]          | 0.142 [0.038, 0.210]  (BELOW CHANCE) |

**Finding, not fixed (D-026 freeze forbids design changes; retrain-only
task):** abrupt/jamming regressed sharply below chance on real closed-loop
features despite drift/meaconing improving a lot. Overall AUC pooled across
families looks fine (0.835) but is dominated by drift+meaconing's large
sample counts; this masks the abrupt/jamming collapse -- report per-family,
never overall alone. Leading hypothesis (not verified): abrupt_spoof/jam_cw
epochs are the minority class in the real 60-seed training pool once
combined with balance=True 50% sampling, and/or "fixed_trust" data
generation (GNSS never excluded, kappa_R=40 R-inflation) shapes real x1/x14
differently for these two families than for drift/meaconing, whose signature
is dominantly C/N0-based (xsat rule) rather than innovation-based. Flagged
as a PROPOSED-DECISION for Master; no further iteration performed per the
D-026 stopping rule and this WP's retrain-only mandate.

## Task 3: smoke matrix (real weights) -- results/m1/smoke_matrix_real.json

New `scripts/run_m1_smoke.py --weights` flag added (default unchanged, old
synthetic weights). Re-ran seeds 500-504, 10 min ground runs with
`detector_weights_real.npz`. **Critical regression, reported not fixed**:
`fedqpnt_local`/`baseline_b_cont` (both drive w_gnss off the same trained
detector's p through the continuous law) diverge on NOMINAL (no attack) to
tens-to-thousands of km RMSE_h (mean w_gnss during nominal ~0.28, vs >=0.95
required) -- the real-feature detector fires almost continuously even on
clean data, cascading through the continuous trust law into chronic MEMS
coasting. `baseline_b_bin` (hard exclude/recover state machine) stays sane
(nominal RMSE 3.8 m) because its law doesn't smoothly track a noisy p.
`bprime`/`undefended` are unaffected (don't consume the trained detector's p
for their weight). Wall: 949 s, 47.5 s/sim-hour, 120 runs.

## Task 4: S1 false-alarm check -- results/m1/s1_far_check.json -- **FAIL**

5 seeds x 30 min, clean nominal, all 7 methods, real weights.
- FAR/h: every method fails the <=1/h criterion. `bprime` alone passes
  (0.0/h, doesn't use the trained detector). `fedqpnt_local`/`baseline_b_cont`
  2.4/h, `baseline_a` 7.6/h, `baseline_b_bin` 2.8/h -- all > 1/h.
  `fixed_trust`/`undefended` (bookkeeping-only detector scoring, per
  methods.py) show 179-183/h: the retrained detector's raw p output crosses
  the detection threshold on nearly every clean epoch. This is a strong,
  method-independent signal that the RETRAIN (not any trust-law choice)
  produced a badly miscalibrated detector on real closed-loop nominal data.
- S1 RMSE criterion (RMSE_h(fedqpnt) <= 1.05 x RMSE_h(fixed-trust), paired
  median): median ratio = 40019 (fedqpnt_local RMSE_h_pre 91 km-4.2 Mm across
  seeds 500-504 vs fixed_trust's 1.9-3.9 m). **FAIL by four orders of
  magnitude.**
- ANEES_pos: fedqpnt_local/baseline_b_cont 18.6 (should be in [0.5,2]) --
  confirms filter divergence, not just a metric artefact.

**PROPOSED-DECISION for Master:** do NOT sign off M1 on this detector. The
D-029 retrain sequence (κ_R re-tune -> retrain -> re-smoke -> sign-off) is
only half satisfied: retrain is DONE and drift/meaconing improved sharply,
but abrupt/jamming AUC inverted (task 2) and, more urgently, clean-nominal
false-firing is catastrophic for any method whose weight tracks the learned
detector continuously. Recommend a dedicated follow-up session (not this
retrain-only WP) to investigate: (a) whether "fixed_trust" data generation
(GNSS never excluded during collection) under-represents the feature
distribution nominal missions actually produce once trust starts gating
GNSS, i.e. a train/deploy distribution-shift second-order effect; (b) the
detector's raw (pre-threshold) p distribution on clean data directly, not
just the pseudo-label pipeline. D-026's freeze forbids changing the
labelling/feature/balance DESIGN; it does not preclude widening/re-composing
the seed pool used to fit the frozen design, which is the more likely first
thing to try.

## Task 5: CW jamming defended-worse-than-undefended -- PERSISTS, worse

Old (synthetic weights) smoke: FedQPNT 964 m vs undefended 358 m under
jam_cw (attack-phase RMSE_h). New (real weights): FedQPNT/B-cont 13069 m vs
undefended 237 m -- same qualitative failure, much larger in magnitude
because (per Task 3/4) the same detector already has the node badly
diverged (RMSE_h_pre 526 m, not ~2 m) before the jam_cw attack even starts.
Diagnosis (unchanged root cause, now compounded):
1. Partial/degraded GNSS under CW jamming stays usable (undefended keeps
   ~237 m using it), but the continuous trust law distrusts it (w_gnss
   drops to 0.137 for fedqpnt/B-cont, 0.584 for B-bin, 0.316 for
   baseline_a), forcing MEMS-only coasting.
2. kappa_R=40's GNSS-R inflation (D-046, PARKED) makes the ESKF's own P
   too optimistic during that coast, so the coast error is worse than an
   honestly-uncertain filter would produce -- the same overconfidence
   mechanism D-046 parked, now visible again.
3. NEW: because the retrained detector already chronically false-fires on
   clean data (Task 4), the pre-attack baseline itself is far from
   converged, so the coasting starts from a worse state than a healthy
   filter would. This is a second, independent contributor layered on top
   of (1)/(2), specific to this retrain.
`baseline_b_bin` (hard exclude+recover) and `bprime`/`undefended` (no
continuous coupling to the trained detector's p) are comparatively spared,
consistent with the Task 3 diagnosis. Not fixed (out of scope; D-046 already
parked the root filter-overconfidence issue for a dedicated future session).

## pytest

`python -m pytest tests/test_node_*.py tests/test_eval_*.py tests/test_trust_*.py -q`
-- 108 tests, all passed (0 failed). No fedqpnt/trust or fedqpnt/node source
files were edited by this WP (only new scripts + this notes file + an
additive `--weights` CLI flag on `scripts/run_m1_smoke.py`), so this is
consistent with no regression from the retrain-only work.

---

## D-049 round (recalibrate reference stats, retrain, Platt-calibrate)

New script `scripts/recalibrate_and_retrain_v2.py`. Reference stats
(joint chi2_11 negative rule + D-024 xsat/cn0 positive rule) recalibrated
on REAL clean closed-loop runs, seeds 500-519, 1800s (30 min) each,
fixed_trust/kappa_R=40 -- a data-derived-constant recalibration, allowed
under D-026's freeze (no rule/threshold/feature-design change). Compared
against the same seeds at the old 300s duration:

Largest shifts (mu/sd, old->new): nis_vel sd 0.644->0.275; resid_rms sd
1.205->0.988; **nsat_delta sd 1.000->0.024** (a ~40x tightening -- over a
genuinely converged 30-min clean run, satellite count almost never changes,
so its empirical sd collapses near zero). cn0_std/cn0_mean sd widen instead
(0.104->0.16/0.26).

Effect: clean-run positive-label rate (new ref, applied to the calib pool
itself) = 2.77% -- better than an unmeasured baseline but still above the
<=1% target. Pseudo-label precision vs oracle DROPPED 0.602->0.290 (recall
stayed ~1.0): the near-zero nsat_delta sd makes the joint chi2_11 test
hypersensitive to that single dimension, so many oracle-negative epochs now
fail the "jointly nominal" test and get pushed to y=1 by default (window
clean-fraction <90%) rather than left as true negatives.

Retrained (same frozen design) on relabelled seeds 520-549. Per-head Platt
scaling fit on seeds 550-574 (natural ratio, PSEUDO-labels, never oracle) --
spoof (a=1.617, b=-0.275), jam (a=1.668, b=-0.134). Held out on 575-599:

| family    | v1 (fixed-trust data gen, old ref) | v2 (new ref, raw) | v2 (Platt-calibrated) |
|-----------|-------------------------------------|--------------------|--------------------------|
| overall   | 0.835 [.825,.845]                    | 0.623 [.614,.632]  | 0.625 [.616,.633]        |
| drift     | 0.924 [.903,.941]                    | **0.171 [.153,.189] (worse, below chance)** | 0.172 |
| meaconing | 0.997 [.995,.999]                    | 0.969 [.961,.977]  | 0.970                    |
| abrupt    | 0.413 [.380,.447] (below chance)     | 0.753 [.734,.772] (recovered) | 0.753           |
| jamming   | 0.142 [.038,.210] (below chance)     | 0.254 [.197,.312] (still below chance) | 0.258 |

Brier score (calibrated) = 0.393 vs raw 0.384 (Platt did not improve Brier
here -- reliability curve in results/m1/detector_retrain_v2_report.json).
Platt params were saved into detector_weights_real_v2.npz for reporting
only; NOT wired into the runtime `_gnss_p`/`detector.score()` path (that
would be a trust_law.py change, out of scope / not requested -- the S1 and
smoke re-runs below use the RAW MLP output exactly as trust_law.py already
consumes it).

**Honest finding: recalibration did not fix the abrupt/jamming problem
uniformly -- it TRADED drift's AUC for abrupt's.** No family combination
found across v1/v2 has all four families above chance simultaneously.
Flagged for Master; no further iteration attempted (D-026 freeze + token
economy).

**D-050 (weight-cap fix + unit test): NOT APPLIED.** The requested edit to
`fedqpnt/trust/detector.py::train_local` (cap inverse-class-frequency BCE
weights at 10x) was blocked by the harness's own permission system
("Modify Shared Resources" -- this file may be touched by concurrent
agents). Per the no-workaround rule this was left undone; v2's retrain used
the UNMODIFIED `train_local`. Needs explicit user/Master-side permission
grant to proceed.

## Re-run with v2 weights

S1 (results/m1/s1_far_check_v2.json), 5 seeds x 30 min: FAR/h still fails
for every method but bprime (0.0/h, unaffected -- doesn't use the trained
detector). fixed_trust/undefended FAR dropped sharply (179-183/h -> 9-10/h)
-- the new reference makes the raw detector fire less OFTEN, but
fedqpnt_local/baseline_b_cont's mean w_gnss dropped further, to 0.022 (v1:
0.108) -- essentially PINNED at w_min for the whole 30 min once triggered.
S1 RMSE ratio: median 726287 (v1: 40019) -- WORSE, not better. ANEES_pos
2.88 (still outside [0.5,2], though less extreme than v1's 18.6).

**This is the clean empirical confirmation of the Task-4/anti-lockout
finding below**: fewer, but now essentially PERMANENT once-triggered,
distrust episodes are strictly worse for RMSE than v1's more frequent but
shorter-lived ones, because nothing in `_LawCore` bounds total time spent
with D==1 -- see below.

Smoke matrix v2 (results/m1/smoke_matrix_v2.json): see final report for the
CW-jamming comparison; qualitative pattern (defended worse than undefended)
persists and is not improved by v2.

## Task 4 (this round): ANTI-LOCKOUT -- why it didn't bound GNSS exclusion

Read `fedqpnt/trust/trust_law.py::_LawCore.advance` (lines ~127-172, the
anti-lockout block). The recovery gate is
`G = (D==0) and (clean_dwell>=T_clean) and (frac_clean>=frac_clean_threshold)`.
The anti-lockout timer only accumulates while
`blocked_only_by_nis = (D==0) and (clean_dwell>=T_clean) and (frac_clean<0.9)
and features_nominal`; `G_capped` (which forces `target=min(tau_star,w_cap)`,
i.e. the actual escape hatch) requires `_lock_timer >= T_lock=120s`, and
`_lock_timer` resets to 0 on every step where `blocked_only_by_nis` is
False -- which is EVERY step where `D==1`. **The anti-lockout mechanism's
own precondition is `D==0`: it exists to rescue recovery that is blocked
ONLY by the frac_clean/NIS-dwell test despite the detector already having
cleared (D already back to 0), not to bound how long D itself can stay 1.**
There is no timer anywhere in `_LawCore` that forces D back to 0, or w back
up, purely as a function of elapsed time while D==1 -- recovery depends
ENTIRELY on `p_bar` (the EWMA of the detector's own p) dropping below
`theta_off=0.3` and staying there for `T_off=5s`. If the (mis-calibrated,
per D-029/D-049) detector's raw output stays chronically elevated on clean
data, D can remain 1 (or re-trigger immediately after each brief dip)
indefinitely, and the anti-lockout's `D==0` precondition is simply never
met, so `T_lock=120s` never engages. Empirical confirmation: v1's
fedqpnt_local held mean w_gnss=0.108-0.282 over a 10-30 min nominal run
without ever recovering to the S1-required >=0.95, and v2 (a differently
mis-calibrated detector, chosen independently) pinned w_gnss at 0.022 --
i.e. essentially floor -- for the same duration. Both are consistent with
"no upper bound on time-with-D==1" rather than any dwell/threshold-specific
number; changing kappa_R, T_lock, w_cap etc. would not by itself fix this,
since none of them are reachable while D stays locked at 1. Not changed
(reporting only, per Master's D-049/this-round instruction).
