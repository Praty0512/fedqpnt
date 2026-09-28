# CORE-ROBUST progress (resume notes)

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
