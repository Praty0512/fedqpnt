# DETECTOR-V3 progress

## Phase A: DONE (no runs launched). Awaiting literal "core frozen — launch v3".
- Created scripts/train_supervised_v3.py (copy of v2). Changes only: outputs results/m1/detector_weights_sup_v3.npz + detector_train_sup_v3_report.json; kappa_R = DEFAULT_KAPPA_R (fedqpnt/core/defaults.py, =60; build_supervised_dataset.py already uses it); report records git HEAD + `git status --porcelain fedqpnt/` at launch and end (warns if changed); workers capped 4 (default 4); SGD rng stream name "train_supervised_v3". Seeds unchanged: train 500-549, Platt 550-574, held-out 575-599, 600 s pools; 6 families; MLP, epochs=3 lr=0.05 bs=64, balance, max_pos_fraction=0.5.
- Not added: meaconing_displaced (held out, D-072).
- Note: v2 seed-plan counts (train pool): clean5 jam_cw9 jam_wideband7 jam_then_spoof8 drift6 meaconing8 abrupt7 (plan_for is seed-deterministic, so v3 shares the same seed->family map).
- Note: scripts/run_m1_s1_far_check.py defaults --kappa-r 40.0 and is modified in the working tree by someone else; I pass --kappa-r 60 explicitly.

## Validation plan (Phase B)
1. `python -u scripts/train_supervised_v3.py --workers 4 > <scratch>/v3_train.log 2>&1` (background).
2. Report: per-family positive-epoch counts (train pool; check >=500 per family), per-family + overall held-out AUC (raw, calibrated, spoof/jam heads) with 95% bootstrap CI, Brier, Platt params; side by side with v2 report numbers (descriptive: v2 on old core).
3. S1 FAR: `python -u scripts/run_m1_s1_far_check.py --weights results/m1/detector_weights_sup_v3.npz --kappa-r 60 --workers 4 --out results/m1/s1_far_check_v3.json` (seeds 500-504, 1800 s). Report FAR, ANEES_pos, RMSE ratio vs fixed_trust for fedqpnt methods.
4. No default weights path changed; no commit.

## Master follow-ups (done, still no runs)
- --kappa-r/--kappa-R argparse default -> DEFAULT_KAPPA_R (import from fedqpnt.core.defaults) in: run_m1_s1_far_check.py, run_m1_smoke.py, run_campaign.py, defended_vs_undefended_check.py. Left alone (historical/diagnostic, hard-coded 40): cai_h3_investigation, core_robust_ba_nees_artifact_check, core_robust_overconfidence_diag, diag_s0_gate_localization, filter_gnss_d038, fusion_outage, fusion_profile, gate_a_labeller_v2, h2_abrupt_theta0_auc_by_severity, perf_benchmark, perf_bitident_check, recalibrate_and_retrain_v2, retrain_detector_real. (core_robust_safety_principle_sweep already defaults 60.0 literal; untouched.)
- train_supervised_v3.py: Step 3b added: meaconing_displaced (onset 60, dur 180, sev 0.5, default params) on seeds 575-579, scored with v3 + Platt, AUC raw/cal/spoof-head + CI, saved as report["generalisation_meaconing_displaced"]. Done via worker-side wrapper patching plan_for (no fedqpnt/ edit). Random-stream name "train_supervised_v3" noted: SGD stream differs from v2.
