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

## IN PROGRESS / NEXT
- Confirm `scratchpad/kappa60_block_nees.log` finished; read it.
- **Item 6** M1 re-verification with v2 detector (`results/m1/detector_weights_sup_v2.npz`),
  ALL using `--kappa-r 60`:
  (i) `scripts/run_m1_s1_far_check.py --kappa-r 60 --weights results/m1/detector_weights_sup_v2.npz`
  (ii) `scripts/run_m1_smoke.py --kappa-r 60 --weights results/m1/detector_weights_sup_v2.npz`
  (iii) `scripts/defended_vs_undefended_check.py --kappa-r 60 --weights results/m1/detector_weights_sup_v2.npz`
  (iv) `scripts/sweep_signature_strength.py` -- kappa_R is HARDCODED 40.0 in this script (lines
       ~92, ~196), no CLI flag yet. NEEDS a `--kappa-r` arg added before running at 60 (script
       edit, not core code, no approval needed) OR run as-is at 40 with a note. DECIDE: add
       the flag (cheap edit) so all item-6 runs are consistent at kappa_R=60.
  (v) E_s firing fraction on drift/meaconing with the NEW jump test: NO reusable script exists
      (`scripts/subrule_decompose_d056.py` reimplements the OLD position_event logic
      independently, stale vs the new `_physical_spoof_evidence`). Need a NEW small script that
      reads `agent.trust.last_es_evidence` directly (already reflects the new jump test live) --
      NOT YET WRITTEN.
- Retrain detector only if feature distributions changed materially -- NOT expected (E_s change
  doesn't touch detector features/training, only the E_s position term); state this in the report,
  don't retrain unless evidence says otherwise.
- Write terse notes to `docs/specs/raw/CORE_ROBUST_NOTES.md` (NOT YET CREATED).
- Run full suite `python -m pytest tests/ -q` once at the very end.
- Final report via SubagentHandback per the original task format.

## Resume command pattern
Background jobs: always `python -u <script> > "<scratchpad>/<name>.log" 2>&1` passed directly to
the Bash tool with `run_in_background: true` (do NOT nohup+disown -- that detaches it from the
tool's own tracking and notifications never fire). To wait without polling manually, wrap in a
`run_in_background: true` Bash call with an `until grep ...; do sleep N; done` loop, then end the
turn.
