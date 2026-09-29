# CORE-ROBUST session notes (D-057/D-058 combined session)

Tuning seeds only (500-599, 9500-9699). All numbers below are from the v2 (post
rotations.py D-060 revert) re-run; earlier pre-revert numbers for items 1-3 were
identical where re-checked (position algebra doesn't touch rotations.py) and
items 4/5 were re-run and matched their pre-revert values exactly (so3_exp/
so3_log numerics were equivalent for these trajectories' angle range).

## 1. `_hygiene` -> eigenvalue clip (D-043)
Symmetrise, then clip only negative eigenvalues to 0 (no additive floor).
Regression: single-source delta_b_a case, sqrt(P_v) == sigma_ba*t at 300s
(rtol 1e-6). `fedqpnt/fusion/eskf.py::ESKF._hygiene`.

## 2. Soft gating (D-057)
`ESKFConfig.gating`: "soft" (new default) | "hard" (ablation). Soft: when
NIS_eff > gate, scale R_eff by (NIS_eff/gate) so the effective NIS becomes
exactly the gate value -- measurement kept, never dropped. "undefended"
unaffected (alpha_gate=0.0 -> gate=inf regardless of switch).

## 3. E_s short-baseline jump test (D-058)
`_physical_spoof_evidence`'s position term replaced: d = Delta p_GNSS -
Delta p_INS over one GNSS epoch, chi2_3(99.9%), using fix.cov_pos(t, t-1) +
a small fixed `es_ins_short_sigma_pos` (0.05m [ASSUMPTION]) INS term.

**Bug found and fixed during verification**: the first implementation used
`nav_prior` (previous AGENT TICK, e.g. 0.01s old at 100Hz) as the INS
baseline instead of the previous GNSS EPOCH's pre-correction estimate (e.g.
1s old at 1Hz gnss_rate). This made Delta p_INS cover ~100x less time than
Delta p_GNSS, so d was dominated by ordinary vehicle motion -> false-fired
on 80% of CLEAN nominal epochs, collapsing mean w_gnss to 0.18 and failing
S1 (RMSE ratio 5.82 vs 1.05 threshold). Fixed by tracking the engine's own
`_last_p_prior` (updated once per GNSS epoch, not per tick). Post-fix: 0/300
false fires on the same clean run; S1 RMSE ratio 0.9877 (PASS).

E_s firing fraction (item 6iii, kappa_R=60, 5 seeds x 260s):
- drift (severity=0.5, cn0_sig_scale=0.0, pure kinematic, CN0 signature
  suppressed): 21.0% (191/910). Not near-zero because severity=0.5 ramps to
  1.5 m/s terminal drift velocity -- a genuinely fast kinematic drag, not
  "slow" in absolute terms, so some real physical inconsistency IS present
  for the test to (correctly) catch.
- meaconing (severity=0.6): 96.6% (874/905).

## 4. Overconfidence diagnosis (D-046/D-047)
(a) Time alignment: zero offset by construction (code trace, not measured
    -- fedqpnt/node/environment.py builds imu/gnss from the same truth
    tick; gnss/receiver.py sets fix.t=epoch.t; agent.step propagates and
    corrects at that same t). Ruled out as a cause.
(b) Per-block NEES, CAI on/off, kappa_R=40 (pre-retune), 5 seeds x 600s,
    GNSS-aided industrial_mems:
    CAI ON:  p=3.58  v=1.98  psi_rp=4.64  psi_yaw=0.48  b_a=522.09  b_g=7.10
    CAI OFF: p=2.84  v=2.14  psi_rp=17.60 psi_yaw=0.64  b_a=67.83   b_g=4.24
(c) b_a NEES root cause (Master's hypothesis, tested and CONFIRMED, mostly):
    the CAI observes the classical IMU's TOTAL accel error, including the
    per-run-constant scale-factor/misalignment aliasing term
    M@(f_b*sf) - f_b (D-028), which the NEES "true b_a" (turn_on+GM+RRW
    only) excludes. Vs an "effective bias" truth = turn_on+GM+RRW +
    M@(f_b*sf)-f_b: b_a NEES drops from 522.19 to **19.04** (27x). Per-axis:
    classical x=297 y=142 z=83; effective x=9.68 y=5.51 z=3.85.
    CONCLUSION: mostly (~96%) a NEES metric-definition artifact, not a
    filter defect -- no eskf.py/trust_law.py fix applied. Residual ~6.3x
    (19 vs ideal 3) overconfidence unexplained; not chased further per the
    "diagnose, fix only if clear" instruction. RECOMMENDATION: use the
    effective-bias truth definition for all future b_a NEES reporting.

## 5. kappa_R re-tune (post items 1-3)
`tune_kappa_r.py`, 5 seeds, 600s, fixed_trust:
kR=10:5.33 kR=20:2.70 kR=30:1.82 kR=40:1.38 **kR=60:0.9499** kR=80:0.74 kR=120:0.54
CHOSEN kappa_R = 60 (within 1+-0.1 target; old kappa_R=40 was tuned PRE the
D-043/D-057 core fixes, hence the shift).
Per-block NEES at kappa_R=60, CAI ON: p=2.61 v=2.03 psi_rp=4.84 psi_yaw=0.48
b_a=521.16(artifact) b_g=7.31.

## 6. Re-verification with v2 detector, kappa_R=60
No detector retrain: the D-058 E_s change only touches the position
EVIDENCE term inside `_physical_spoof_evidence`, not the 13-feature vector
the detector itself trains/scores on -- feature distributions are
unaffected.

(i) M1 S1 criteria (5 seeds x 30 min): fedqpnt_local FAR=0.0/h (PASS),
ANEES_pos=0.875 (in [0.5,2], PASS), mean_w_gnss=0.971, RMSE ratio
(fedqpnt/fixed_trust) = 0.9877 (threshold 1.05, **PASS**). Smoke matrix
(nominal/drift/meaconing/jam_cw x 7 methods x 5 seeds x 10 min): no
divergence seen; nominal FAR=0 for all methods except baseline_a/
fixed_trust/undefended (1 seed each with FAR=8/h, pre-existing baseline
behaviour, not v2-trust-law-specific). Defended-vs-undefended (nominal,
jam_cw): fedqpnt_local PASSES both; baseline_a FAILS jam_cw (745.7 vs
threshold 324.3).

(ii) D-055 safety-principle sweep (s in {0,0.25,0.5,1.0}, drift, 3 seeds x
10 min, kappa_R=60): fedqpnt_local is only 1-5% worse than undefended's
RMSE_h_att at every s (108-112 vs ~107), but technically FAILS the literal
3*sigma_nom bound at every s because sigma_nom (measured from the NOMINAL
scenario's own tiny seed-to-seed variance, ~0.24-0.82) is very tight.
baseline_a catastrophically fails at s>=0.5 (182 -> 1227 vs ~107).
PROPOSED-DECISION: the literal 3*sigma_nom(nominal) bound may be stricter
than D-055's stated intent ("never SUBSTANTIALLY worse") when sigma_nom is
this small; consider whether a 1-5% relative RMSE increase should count as
a safety-principle failure, or whether the bound should scale with the
attack-scenario's own noise floor instead of the nominal one. Flagged for
Master, not resolved here.

(iii) E_s firing fraction: see section 3 above.

## Files
- Code: `fedqpnt/fusion/eskf.py`, `fedqpnt/trust/trust_law.py`.
- Tests: `tests/test_fusion_eskf.py` (+3 new/updated), `tests/test_trust_law_es_position.py` (new, 6 tests).
- New scripts: `scripts/core_robust_overconfidence_diag.py`,
  `scripts/core_robust_ba_nees_artifact_check.py`,
  `scripts/core_robust_kappa60_block_nees.py`,
  `scripts/core_robust_safety_principle_sweep.py`,
  `scripts/core_robust_es_firing_fraction.py`.
- Modified script: `scripts/sweep_signature_strength.py` (added `--kappa-r` CLI flag).
- Results: `results/m1/kappa_r_tuning_v2.json`, `results/m1/s1_far_check_core_robust_v2.json`,
  `results/m1/smoke_matrix_core_robust_v2.json`,
  `results/m1/defended_vs_undefended_core_robust_v2.json`,
  `results/m1/core_robust_safety_sweep_v2.json`,
  `results/m1/sig_strength_sweep_core_robust_v2.json`.
- Progress/checkpoint log (superseded by this file + the final report):
  `docs/specs/raw/progress/CORE-ROBUST.md`.

## Known pre-existing, out-of-scope failure
`tests/test_fleet_adapter.py::test_local_only_detector_hash_changes_across_rounds`
fails (`round_installs == 0`). This is `fedqpnt/eval/fleet_adapter.py`, outside
this session's edit scope (fedqpnt/fusion/eskf.py, fedqpnt/trust/*,
fedqpnt/node/*), and matches the already-known D-059 "B-cont frozen-theta0"
bug (commit cd4b36f, fix pending, not part of this session).
