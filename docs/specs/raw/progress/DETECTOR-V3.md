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

## Phase B LAUNCHED (core-freeze-1 = a7c8bf0 per Master)
- Chain script scratchpad/run_v3_chain.sh: train v3 (workers 4) -> S1 FAR (weights v3, --kappa-r default=60, workers 4, out results/m1/s1_far_check_v3.json). Logs in scratchpad: v3_train.log, v3_far.log, v3_chain.log. Displaced check is inside the training script (Step 3b).
- Launch git HEAD/fedqpnt status recorded in scratchpad/v3_chain.log and report json.
- Launched (background). Launch HEAD 08f29dd (ops commit atop a7c8bf0; fedqpnt/ diff vs a7c8bf0 empty, status clean). On completion: read scratchpad v3_train.log, results/m1/detector_train_sup_v3_report.json, results/m1/s1_far_check_v3.json; compare to results/m1/detector_train_sup_v2_report.json; report to Master.
- Note: HEAD moved 08f29dd -> 6dd7cc9 (ops-only commits; git diff a7c8bf0..HEAD -- fedqpnt empty) between chain launch and training script launch. Not a core change. Chain still running (background); the earlier task-completion notice was just the launcher's sleep wrapper.

## CHAIN STOPPED by Master (core bug: clock-jump features use wrong gap after jamming). Discard outputs.
- Found still-running run_m1_s1_far_check.py (--weights sup_v3...) tree (pid 12320 + 4 workers); killed. Chain log had "train exit 127 / far exit 127" (bash chain itself never ran python; that FAR process had a different parent, not from my chain).
- No results/m1/*sup_v3* or s1_far_check_v3.json present. Nothing to delete. No other detector-v3 processes running.
- WAITING for "core frozen — launch v3 (core-freeze-2)"; then relaunch same chain (scratchpad/run_v3_chain.sh; fix: bash chain got exit 127 -> use full python path / PowerShell launch).

## core-freeze-2 (845636e) relaunch
- Launched training via full python path, run_in_background (task b79zxvcsc), log scratchpad/v3_train2.log. Launch HEAD b002fdc (fedqpnt/ diff vs 845636e empty, status clean). First log line confirmed ([git @launch]).
- NEXT (when notified training done): read report json + log; then run S1 FAR separately: python -u scripts/run_m1_s1_far_check.py --weights results/m1/detector_weights_sup_v3.npz --workers 4 --out results/m1/s1_far_check_v3.json (kappa default now 60) -> scratchpad/v3_far2.log; compare to v2 report; report to Master.

## v4 (D-083, core-freeze-5) 
- Created scripts/train_supervised_v4.py (= v3 with _v4 names/outputs only; dataset builder now world=schuler_tangent). Launched detached via PowerShell Start-Process (python pid 28184), 4 workers, log scratchpad/v4_train.log (+ .err). Launch HEAD 22481b0, fedqpnt/ clean, fedqpnt diff vs core-freeze-5 empty. First log line confirmed.
- Flag: scripts/run_m1_s1_far_check.py hard-codes RunSpec world="flat" (line 46), whereas v4 training uses schuler_tangent. Running FAR as specified (unchanged script) unless Master says otherwise.
- NEXT after training ends: S1 FAR detached x2 grades (industrial_mems, tactical), --weights results/m1/detector_weights_sup_v4.npz --imu-grade g --out results/m1/s1_v4_<g>.json, run sequentially (4 workers). Then compare with v3 report (results/m1/detector_train_sup_v3_report.json) and s1_v3_<g>.json.
- Master approved: added --world (default schuler_tangent) to run_m1_s1_far_check.py (also stamped world/imu_grade in output json). v3 S1 numbers were on 'flat' -> v3-vs-v4 S1 comparison is descriptive across worlds. Grades: industrial_mems, tactical, run detached sequentially after training.
- Launched detached waiter (powershell pid 5048, scratchpad/v4_far_chain.ps1): waits for training pid 28184, then runs S1 FAR sequentially for industrial_mems then tactical (--world schuler_tangent, 4 workers) -> results/m1/s1_v4_<g>.json, logs scratchpad/v4_far_<g>.log/.err. Skipped if detector_weights_sup_v4.npz absent. Training still running at this point.

## theta0 re-pretrain (D-084, core-freeze-5)
- FINDING: scripts/pretrain_theta0_d054.py calls collect_run, which since core-freeze-5 hard-codes world="schuler_tangent" -> would NOT match the fleet's world="flat". Wrote scripts/pretrain_theta0_d054_freeze5.py: imports and runs the original script UNCHANGED, with the dataset module patched in-process (EnvConfig/make_agent_config world forced to "flat"; verified). Backs up results/fleet/theta0_d054.npz -> theta0_d054_pre_freeze5.npz (+provenance), writes new theta0 to the original path, provenance to theta0_d054_freeze5_provenance.json (git at launch/end, world, seeds, held-out old-vs-new AUC on seeds 575-599, 600 s, flat).
- Queued: powershell waiter (scratchpad/theta0_chain.ps1) waits for FAR chain pid 5048 (itself waiting on v4 training pid 28184), then runs it detached. Log scratchpad/theta0_freeze5.log.
