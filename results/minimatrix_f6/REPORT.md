# FIX6 report (branch freeze6, D-086) - tuning seeds only (530-549); no seed >= 10000 run; results/m4, m4r2 untouched

## 1. What changed (commit 3c12e03 on freeze6; C2 option on branch freeze6_c2opt, commit 2d38cfd, worktree FEDQPNT_c2)
- C1: fedqpnt/fusion/eskf.py initialize_static: P0 roll/pitch std = max(1 mrad, sigma_ba_turnon/G0) (new tilt0, lines ~170-181).
- F3: fedqpnt/fl/client.py local_round: base_round = last_installed_round if >= 0 else round_idx.
- F4: new results/fleet/theta0_d054_f6.npz (+ _provenance.json): theta0 weights unchanged, norm_mu/norm_sd/norm_count (20552) from detector_weights_sup_v4.npz; fedqpnt/eval/fleet_adapter.py THETA0_PATH points to it. Old file untouched. Root cause: the pretrain script estimates the running normaliser from its own 1470-sample subset. Cleaner fix = re-pretrain with the sup_v4 normaliser frozen (weights were fitted under the narrow scaling); NOT done (needs retrain + AUC re-validation). Caveat: theta0 detector outputs shift with the new scaling; AUC not re-validated (fleet S15 AUC 0.82 f6 vs 0.69 f5, 1 seed).
- Tests added: test_fusion_eskf.py::test_p0_tilt_std_covers_levelling_error (2 grades), test_fl_client.py::test_never_installed_client_reports_fresh_base_round.
- Tooling: scripts/minimatrix.py (tuning-seed runner, refuses seeds >= 10000, spec-file launcher for S7-p2/p5), minimatrix_compare.py, kappa_q_early_outage_diag.py, c2_option_eval.py, c2_summary.py.
- C2/C2b NOT applied on freeze6; behind env FEDQPNT_PROBE_QUIET_OVERRIDE=1 (default off) on branch freeze6_c2opt only.

## 2. Test suite (freeze6 worktree, pytest tests -q)
659 passed (dots), 5 skipped, 1 failed, 0 errors (final summary line lost; counts from progress dots). Failure tests/test_data_jarlaud.py::test_manifest_covers_every_extracted_file is environmental: fails identically in the core-freeze-5 worktree, passes in the main checkout (worktrees lack untracked data/raw). Not caused by the fixes. C2 worktree: trust-law/probe tests (37) pass.

## 3. kappa_Q pre-registered rule (seeds 530-549, outage [120,300), CAI on, pooled ANEES 3-D position)
kappa_Q = 1: MEMS pooled 0.45 (0.41/0.45/0.48 at +60/+120/+179), tactical 0.37 -> rule picks kappa_Q = 1 both grades; defaults.py NOT changed. Curves in kappa_q_*.log (MEMS 0.45 -> 0.10 at 50; tactical 0.37 -> 0.16). Diagnostic early outage [60,240): kappa_Q = 1 MEMS 0.14, tactical 0.33 (grid 1,2,5), also <= 1.5.

## 4. Mini-matrix (seeds 530-532 single node, 530 fleet; detector sup_v4; f5 = core-freeze-5). Cells: COMPARE.md
Coverage: f6 = every single-node result id x all methods x 3 seeds (S1-S4, S6, S6-coast, S7 x5, S10 x16, S11, S13) both grades; S14 1 seed per grade; all 6 fleet ids 1 seed. f5 = S1, S2-low/med/high/DM, S3, S4, S6, S6-coast, S7-p10, S11, S13 with methods fedqpnt_local/undefended/baseline_a/abl_minus_quantum, plus all fleet ids. All statuses ok.
VALIDITY NOTE: my first f5 pass was INVALID: the core-freeze-5 worktree lacked results/m1/detector_weights_sup_v4.npz (untracked at the tag) and the runner silently falls back to an untrained detector when the file is missing. Kept as results/minimatrix_f5_INVALID_missing_sup_v4 (its fleet part is valid and reused). f5 single-node was re-run with the weights present.

Headline medians (rmse_h att/post, m; ud = undefended; A = baseline_a)
- S2-med MEMS: f5 11,420/114,900 -> f6 954/1,240 (ud 254/181, A 1,090/1.3). Tactical 2,300/21,250 -> 1,720/15,970 (ud 253/182, A 935/1.4).
- S2-low MEMS att 12,750 -> 930 (post 1,210); tactical 2,330 -> 1,760 (post 16.3 km). S2-DM MEMS 11,550 -> 884; tactical 2,260 -> 1,680 (post 15.8 km).
- S3 MEMS att 172 -> 16.8, post 91 -> 2.5 (= ud/A); tactical = ud.
- S4 MEMS att 6,200 -> 501, post 36,340 -> 1,500; tactical att 1,260 -> 951, post 5,480 (ud 137/162).
- S6 unchanged: MEMS 15,900/21,300 (ud 438/266), tactical 2,610/4,050.
- S13 post MEMS 36.9 -> 36.4, tactical 246 -> 264 (ud 14.6).
- S7-p10 MEMS att 3.9e6 -> 32.5 (ud 15.4), tactical 8.6e5 -> 44.5. S1 pre 2.04 -> 1.58 (MEMS), 1.64 -> 1.61.
- Fleet (seed 530): f5 rmse_h_pre 11,900-16,600 m, round_installs 0, fpr 0.74-0.80 -> f6 2.1-2.3 m, installs 2.5-5.0/node, fpr 0 (S15: pre 2.30, att 1,739, post 11,035, fpr 0.27).
- S14 (1 seed): MEMS rmse_h_pre 2.53, ANEES 0.89; tactical 2.53, 0.91; no drift (hour-first 2.2, last 2.8), fpr 0.
- M3 safety margin (mean def - mean ud vs 3 sigma_nom 3.42/3.36 m): PASS S1, S3, S7-p2, S7-p5, S6-coast, now S2-DM (-947/-298 m; FAIL in f5). FAIL S2-low/med/high, S4, S6, S7-p10/p20/p60, S11.

## 5. Remaining defended-worse cells (f6 medians; list in COMPARE.md FLAGS)
GNSS is excluded after an attack and not re-admitted.
- All S2-low/med/high, both grades: att above undefended (MEMS 3.8-7x, tactical 4-14x); post above ud and A (MEMS ~1.2 km vs A 1.3-70 m; tactical ~16 km vs A 1.4-142 m). S2-DM: MEMS att 884 vs A 834, post 1,180 vs A 172; tactical post 15.8 km vs ud 1.7 km, A 487. Tactical S2 att 1.8-1.9x A.
- S4, S6 (both grades), S7-p10/p20/p60 (S7-p2/p5 equal), S11, S13 tactical post (264 vs 14.6).
- No f6 cell is worse than f5 except S13 tactical post (+7%) and noise-level differences on S4/S6.

## 6. Anomalies
1. S11 (extreme noise, filter not told): fedqpnt_local rmse_h_pre 58.8 km MEMS / 45.9 km tactical, fpr 0.993, identical in f5 and f6 (ud 17.5/4.05 m, A 461/3.8 m). Permanent DISTRUST lockout on a clean mission, unchanged by C1/F3/F4 (C2 on: MEMS 20.3 km, tactical unchanged). Not diagnosed.
2. Divergence outliers: S7-p10 tactical seed 531: max_h 609 km, post RMSE 615 km (other seeds 66-447 m); S7-p60 tactical seed 530: 110 km. Free-inertial floor for 3600 s tactical is tens of km at most: looks like filter divergence. Not diagnosed.
3. Identical values: S12-f20/f40 fedqpnt == fedqpnt_clean == S5 fedqpnt_nofault to all digits (poisoning/faults have no effect on reported metrics, or are not applied); S8 fedqpnt vs baseline_b_cont near-identical. rmse_t_ns identical across IMU grades (expected).
4. undefended identical f5 vs f6 (control).
5. Run discipline: briefly 3 own simulations while S14 ran (a duplicate S7-p5 invocation I could not kill; the permission layer denied the kill); RAM stayed >= 2.3 GB free.

## 7. Step 4: C2+C2b option (branch freeze6_c2opt, off by default)
Triggered: post-attack error stayed ~16 km tactical, ~1.2 km MEMS (>> A). Flag on vs off (C2_OPTION_TABLE.md), medians:
- Tactical post: S2-low 16,260 -> 2,520; S2-med 15,970 -> 2,470; S2-DM 15,840 -> 2,480; S4 5,480 -> 1,040; S13 264 -> 24. MEMS post barely changes (S2-med 1,240 -> 1,230; S4 1,500 -> 1,120; S13 36 -> 19). S1, S3, S6, S2 attack-phase unchanged; fpr 0.89 -> 0.16 (S2). S7-p10 tactical att 44.5 -> 21.0, post 52.5 -> 13.7; MEMS 32.5/22.7 -> 29.7/24.9. S11 MEMS 58.8 -> 20.3 km.
- Even with C2 tactical post error is 1-2.5 km (A: 1.4 m).
- Adversarial quiet spoof (S2-style drift, 300 s, cn0_sig_scale=0), QUIET-0.3 / QUIET-0.1, C2 off -> on, att RMSE MEMS 140 -> 127 / 58.9 -> 43.8, tactical 137 -> 129 / 51.5 -> 46.7 (ud 126 / 42; A 127 / 42; max offset 236 / 79 m): defence falls to undefended-level exposure. Caveat: these spoofs were still detected at onset (fpr 0.89, C2 off), so this measures re-admission during an ongoing attack, not an undetected one; only severities 0.1 and 0.3.
- Trade-off: C2 recovers 3-10x of post-attack error on tactical and helps S7/S13 tactical, costs nothing on S1/S3/S6, but re-admits any spoofer quiet to detector and E_s for >= 70 s (then no better than undefended). Not enabled; Master decides.

## 8. Further bugs / suspicions (not fixed)
- Missing detector-weights file silently falls back to an untrained detector (methods.load_detector_weights returns None); invalidated my first f5 pass. Should raise.
- S11 lockout; S7 tactical divergence.
- trust_law.py comment near line 440 says the probe bound is dof-normalised; it is un-normalised 6-D.
- scripts/m4_campaign.py: manifest note names theta0_d054.npz; phase-2 precondition checks the freeze5 theta0 provenance (not f6 theta0).
- theta0 weights were trained under the narrow normaliser; retrain with sup_v4 normaliser is the clean fix.
