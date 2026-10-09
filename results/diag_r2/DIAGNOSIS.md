# Round-2 failure diagnosis (TUNING SEEDS ONLY: 530-534; no seed >= 10000 run; results/m4, m4r2 only read)

Code under test: core-freeze-5 (main checkout fedqpnt/ identical to the tag). Candidates were tried only in a throwaway worktree; the diff is saved as results/diag_r2/candidate_fixes.patch (NOT applied to master). Detector weights: sup_v4 (as in round 2) for the matrix; the seed-530 per-epoch traces used sup_v3 (older Master script; same w sequence since E_s forces DISTRUST at t=61).
Scripts: scripts/diag_coast.py, diag_readmit.py, diag_matrix.py, diag_fleet_node.py, diag_fleet_fix.py, *_summary.py. Raw outputs: results/diag_r2/.

## Verdicts
| Q | Finding | Type | Confidence |
|---|---|---|---|
| 1 | PROBE exit needs mean 6-D shadow NIS <= bound, but the coast covariance is badly overconfident, so NIS is 1e4-1e5 vs bound 25.07/6.74. Probe can never pass; DISTRUST->PROBE->DISTRUST loops every 70 s. | Design property (coast-consistency probe, bound calibrated on 60 s clean outages) failing because of an ESKF initial-covariance defect | high |
| 2 | Coast error = physics floor plus P0 defect. MEMS free-inertial floor ~2.5 km at 300 s; filter gives 14-26 km (median) because P0 roll/pitch = 1 mrad while levelling from the biased accelerometer leaves ~10 mrad (MEMS), and gyro bias is unconverged at t=60 s. No spoof absorption at onset. CAI-on coasts worse than CAI-off on MEMS. | Defect (P0) + scenario/physics floor | high (P0), medium (CAI mechanism) |
| 3 | round_installs=0: bootstrap staleness deadlock (base_round=-1 until first install; server drops staleness>3) plus data starvation (first update only at round 6). Fleet rmse_h_pre 6-12 km: clean nodes false-fire E_s xsat/cn0 because theta0's normaliser sigma is ~3x narrower than sup_v4's; DISTRUST then latches (Q1) and the coast diverges. | Orchestration/data bugs, not core logic; latch is Q1 | high |

## Q1 re-admission (S2-med, seed 530; results/diag_r2/readmit_*, trace_*)
Attack drift_spoof on 60 s, off 362 s. fedqpnt_local -> DISTRUST at t=61 (raw p 0.635 and E_s); w_pos pinned at 0.02 (trust_law.py:349, D-075). After t_off raw p falls 0.17 -> 0.01, p-bar ~0.1-0.27 by t~400, E_s silent (es=0) during PROBE, so detector and evidence are NOT the blocker. Only exit: DISTRUST -(T_ex=60 s, :350)-> PROBE (10 s, w=0.3, no update applied, eskf.py:422) -> success iff mean shadow NIS <= bound and no xsat/cn0 evidence (:371-373). Probes at t=401, 471, 541, 611 all FAIL on NIS alone:
- MEMS (bound 25.07): shadow NIS 3.0e4 at 402 (NIS_pos 1094, NIS_vel 5008; cross terms make 6-D larger), 4.5e4 at 480, 1.4e5 at 612. At t=362: coast error 30.2 km vs filter sigma_pos 4.1 km/axis; velocity error 302 m/s vs sigma_v 44.
- tactical (bound 6.74): NIS 35-110 at 402, 600-1100 at 612.
- Baseline A recovers because it is memoryless (fixed_exclude): w=1 on the first epoch with p<0.5; soft gating (eskf.py:431-445) pulls 21.8 km -> 227 m in one epoch (K~0.9 because R_eff is scaled to the gate) and to ~3 m within ~240 s.
- Not a unit mismatch: shadow NIS (eskf.py:349-359) and bound are both un-normalised 6-D (the comment in trust_law.py near line 440 saying "dof-normalised" is misleading). Not stale state. The clock law does re-admit (w_clk -> ~1 by t=450); only the position law is stuck.
- Self-reinforcing: in DISTRUST the E_s position test (short-baseline, es_ins_short_sigma_pos=0.05 m, trust_law.py:106,855) fires every epoch once coast velocity error exceeds ~0.1 m/s, pinning p-bar=1.
- Why NIS is huge = coast covariance realism. 6-D NEES (pos+vel) in a pure GNSS blackout from t=60, CAI on, 4 seeds, median, core-freeze-5: MEMS 17 at T0, 98 at +60 s, 725 at +120 s, 12.5k at +240 s, 29k at +300 s (expected 6). Tactical 5.8 / 8.2 / 143 / 461 at +60/+120/+240/+300 s. The bound (calibrated on 60 s outages, seeds 510-529) is meaningful only for short coasts; after 300 s no honest GNSS can pass.

## Q2 coast divergence (results/diag_r2/coast/, coast_*)
- Spoofed GNSS is NOT absorbed at onset: filter error 3.1 -> 2.4 m over t=60-63; injected offset <1 m at onset (6 m at t=90). Pure-blackout control from t=60 matches the DISTRUST run to ~15%: err_h 82/420/2359/7220/16.7k/32.7k m at +30/+60/+120/+180/+240/+300 s (seed 530 MEMS). Any 300 s exclusion costs this regardless of defence; undefended follows the spoof (max offset 470 m) and wins on RMSE.
- Closed form err ~ g*eps*t^3/6. MEMS gyro in-run sigma_gm = 8/0.664 = 12 deg/h = 5.8e-5 rad/s -> 2.6 km at 300 s; oracle run (perfect initial biases, same mechanisation) gives 2.45 km at +300 s: the IMU preset is plausible for ADIS16470 class. Tactical 1.5 deg/h -> 0.32 km; oracle 0.33 km. The filter instead gives MEMS 14.1 km (+240 s median) / 26.4 km (+300 s), tactical 2.5 / 4.6 km, i.e. 8-10x the floor.
- Causes (seed 530): (a) initial roll/pitch error ~11 mrad from levelling with a biased accelerometer (accel turn-on sigma 10 mg MEMS) but P0 uses 1 mrad (eskf.py:171-175). With CAI the accel bias is pinned within 1 s so the tilt is NOT absorbed by b_a; GNSS with kappa_R=60 corrects it slowly (verr_h 0.43 m/s during GNSS vs 0.01 without CAI). (b) gyro bias not learned in the 30 s hold + 30 s motion before onset (horizontal bg error 117/-96 deg/h MEMS with CAI; tactical error ~ the full true bias), so tilt drifts ~0.5 mrad/s. Without CAI, accel-bias and tilt errors partly cancel.
- CAI effect, pure blackout, median err_h at +240 s, 4 seeds: MEMS CAI-on 14.1 km vs CAI-off 3.3 km; tactical 2.5 vs 1.6 km. S2-med att RMSE (seeds 530-532 medians): MEMS fedqpnt_local 11.4 km, abl_minus_quantum 2.0 km, baseline_a 5.3 km; tactical 2.3 / 1.0 / 1.4 km. CAI aiding currently HURTS the long coast, via (a).

## Q3 fleet
- results/m4r2/S8/fedqpnt/seed_10030.json (read-only): server_log ROUND_SKIPPED in all 10 rounds with n_fresh=0; provenance n_local_samples=0 rounds 0-5, 64/73/82/91 rounds 6-9; installed=False always. Mechanism: FLClient.local_round returns None until the replay buffer holds min_samples=64 (fl/client.py:40,97; local sets are ~9 samples/round from local_train_duration_s=60, fleet/orchestrator.py:69). The first ModelUpdate (round 6) carries base_round=-1 (client.py:118; node_runner.py:142), the server computes s=6-(-1)=7 > max_staleness=3 and discards it (fl/server.py:115-117) -> no fresh updates -> ROUND_SKIPPED -> never an install: permanent deadlock. fl/orchestrator.py comments document the same -1 trap for an earlier install bug. Orchestration bug in fl/ and fleet/, not ESKF/trust core.
- fleet rmse_h_pre: per node (seeds 10030/10031, S5/S8/S15) mostly 2-100 m, but 1-2 nodes per fleet are 3e4-6e4 m (fpr 0.92-0.97) and dominate the mean. Reproduced in-process on tuning seeds (diag_fleet_node.py; flat world, theta0, no attack): seed 530 node2 rmse 48 km, seed 531 node2 21.7 km, other nodes 8-321 m with 25-93% of epochs not TRUST. The first TRUST->DISTRUST on clean data is E_s xsat/cn0 (raw detector p only 0.01-0.11), e.g. xsat corr 0.116 vs threshold mu+1.96 sd = 0.081, because theta0's normaliser sd is 0.0435 (xsat) / 0.104 (cn0) from 1470 samples vs 0.140 / 0.278 from 20552 samples in sup_v4 (E_s reuses the detector normaliser). The Q1 latch then applies. With theta0 weights but sup_v4's norm_mu/sd/count: 6/6 clean nodes, 0 non-TRUST epochs, rmse 1.5-3.5 m.

## Q4 candidate fixes (all in candidate_fixes.patch; none applied to master)
- C1 (fusion/eskf.py initialize_static, 3 lines): P0 roll/pitch std = max(1 mrad, sigma_ba_turnon/G0). Small, local; changes the frozen core, so needs a freeze decision.
- C2 (trust/trust_law.py, ~10 lines behind a flag): PROBE also succeeds if the detector was quiet (mean raw p over probe <= theta_off) and no xsat/cn0 evidence, even if the coast NIS fails. C2b (5 lines in TrustEngineImpl.update): quarantine the E_s position test for 2 epochs after PROBE->TRUST (otherwise the pull false-fires E_s next epoch: observed TRUST->DISTRUST right after success). Trade-off: a spoofer quiet to both detector and E_s is re-admitted after >=70 s with damage bounded only by soft gating (Baseline A's exposure); NOT tested against adversarial quiet spoofs.
- F3 (fl/client.py:118): base_round = round_idx if last_installed_round < 0. Tested on a reduced fleet (S8, 2 nodes, seed 530, 10 rounds): round_installs 0 -> 5 per node (rounds 5-9).
- F4: give E_s xsat/cn0 a well-supported reference (ship theta0 with sup_v4 norm stats, or a larger sigma floor / minimum clean-sample count). Tested in-process only.
- Not fixed: gyro-bias convergence before onset; NEES growth beyond +180 s on tail seeds even with C1.

Pure-coast with C1 vs core-freeze-5 (seeds 531-534 medians): MEMS +60 s err 74 m vs 462 m; +240 s 1.17 km vs 14.1 km; NEES6 2.2 vs 12.5k. Tactical +240 s 1.49 km vs 2.48 km; NEES6 28 vs 143 (still growing: 66 at +300 s).

### Matrix through run_single (TUNING seeds 530-532, medians, sup_v4; m, m/s, s). main = core-freeze-5
| scenario | grade | variant | n | rmse_h_att | rmse_v_att | rmse_h_post | t_rec | fpr |
|---|---|---|---|---|---|---|---|---|
| S2-med | MEMS | main | 3 | 11,420 | 135.6 | 106,200 | none | 0.90 |
| S2-med | MEMS | C1 | 3 | 954 | 11.0 | 1,236 | 49 | 0.89 |
| S2-med | MEMS | C1+C2+C2b | 3 | 954 | 11.0 | 1,235 | 49 | 0.16 |
| S2-med | tactical | main | 3 | 2,297 | 26.8 | 21,250 | 49 | 0.90 |
| S2-med | tactical | C1 | 3 | 1,722 | 20.1 | 15,970 | 49 | 0.90 |
| S2-med | tactical | C1+C2+C2b | 3 | 1,722 | 20.1 | 2,475 | 56 | 0.16 |
| S2-med | MEMS | abl_minus_quantum (main) | 3 | 2,026 | 24.1 | 2,830 | 49 | 0.90 |
| S2-med | tactical | abl_minus_quantum (main) | 3 | 987 | 11.4 | 1,403 | 64 | 0.89 |
| S2-med | MEMS | baseline_a (main) | 3 | 5,349 | 60.7 | 7.9 | 17 | 0 |
| S2-med | tactical | baseline_a (main) | 3 | 1,385 | 15.2 | 1.4 | 8 | 0 |
| S3 | MEMS | main | 3 | 171.7 | 8.5 | 91.0 | - | 0.86 |
| S3 | MEMS | C1+C2+C2b | 3 | 16.8 | 1.5 | 2.5 | 1 | 0 |
| S3 | tactical | main | 3 | 35.5 | 1.75 | 3.7 | 42 | 0 |
| S3 | tactical | C1+C2+C2b | 3 | 26.3 | 1.33 | 3.3 | 31 | 0 |
| S1 | MEMS | main -> C1+C2 | 3 | rmse_h_pre 2.04 -> 1.58 | | | | 0 -> 0 |
| S1 | tactical | main -> C1+C2 | 3 | rmse_h_pre 1.64 -> 1.61 | | | | 0 -> 0 |

Full per-run numbers: results/diag_r2/matrix_*.json (python scripts/diag_matrix_summary.py). Caveats: 3 seeds per cell with large seed spread; no undefended tuning-seed matrix (seed-530 trace: undefended MEMS att 251 m, post 183 m); C1 removes the catastrophic post-attack latch but attack-phase RMSE stays far above undefended (954 m vs ~250 m MEMS) because a 300 s MEMS coast cannot beat following a <=470 m drift; C2 evaluated only on post-attack recovery, S3, S1.

## Could not determine
- Source of residual NEES growth beyond +180 s on tail seeds (unmodelled SF/misalignment vs vertical channel); not isolated.
- Proof of why CAI-on degrades pre-onset gyro-bias learning (hypothesis: P0 tilt/b_a decorrelation plus CAI cross-covariance; C1 removes most of the effect).
- Fleet beyond a 2-node, 10-round F3 check; effect of FL installs on false-alarm rate not measured.
