# Round-2 M3 summary (core-freeze-5, seeds 10030-10059, n=30/cell)

sigma_nom (results/sigma_nom_freeze5.json): industrial_mems 1.139 m, tactical 1.120 m. Tasks: 5280/5340 ok, 60 missing = S14@industrial_mems, S14@tactical (PENDING: S14 still running; nothing else missing; failed files: 0).

## Confirmatory family (paired Wilcoxon, Holm fixed m=8; HL = A-B with 95% BCa CI)

| Test | Setting | Metric (A vs B) | n | raw p | Holm p | Reject? | HL | 95% CI |
|---|---|---|---|---|---|---|---|---|
| H1_rmse_h_att_vs_A | S2-med@industrial_mems | rmse_h_att (fedqpnt_local vs baseline_a) | 30 | 1.863e-09 | 1.49e-08 | YES | 4514 | [3404, 6287] |
| H1_latency_on_vs_A | S2-med@industrial_mems | latency_on (fedqpnt_local vs baseline_a) | 30 | 5.337e-07 | 3.736e-06 | YES | -2 | [-2, -2] |
| H2_pd10_vs_Bcont | freeze-4 fleet file::h2 | pd10 (fedqpnt vs baseline_b_cont) | 10 | 1 | 1 | no | 0 | [0, 0] |
| H2_onset_latency_vs_Bcont | freeze-4 fleet file::h2 | onset_latency (fedqpnt vs baseline_b_cont) | 10 | 1 | 1 | no | 0 | [0, 0] |
| H3_latency_eff_mems | S6@industrial_mems | latency_eff (fedqpnt_local vs abl_minus_quantum) | 30 | 1 | 1 | no | 0 | [0, 0] |
| H3_latency_eff_tactical | S6@tactical | latency_eff (fedqpnt_local vs abl_minus_quantum) | 30 | 1 | 1 | no | 0 | [0, 0] |
| H4_pd10_coldstart | freeze-4 fleet file::h4 | pd10 (fedqpnt vs baseline_b_cont) | 10 | 1 | 1 | no | 0 | [0, 0] |
| H4_onset_latency_coldstart | freeze-4 fleet file::h4 | onset_latency (fedqpnt vs baseline_b_cont) | 10 | 1 | 1 | no | 0 | [0, 0] |

## Safety principle: mean_def <= mean_undef + 3 sigma_nom (field max_h_att; max_h_pre for S1)

| Scenario@grade | n | margin (m) | 3sigma_nom (m) | Primary | HL (def-undef) | 95% CI |
|---|---|---|---|---|---|---|
| S1@industrial_mems | 30 | 0.009513 | 3.417 | PASS | 0.0126 | [-0.007229, 0.03004] |
| S1@tactical | 30 | 0.006126 | 3.361 | PASS | 0.00434 | [-0.02641, 0.03822] |
| S2-low@industrial_mems | 30 | 2.158e+04 | 3.417 | FAIL | 2.104e+04 | [1.637e+04, 2.612e+04] |
| S2-low@tactical | 30 | 3916 | 3.361 | FAIL | 3850 | [3087, 4477] |
| S2-med@industrial_mems | 30 | 2.092e+04 | 3.417 | FAIL | 2.036e+04 | [1.584e+04, 2.545e+04] |
| S2-med@tactical | 30 | 3602 | 3.361 | FAIL | 3531 | [2778, 4156] |
| S2-high@industrial_mems | 30 | 2.01e+04 | 3.417 | FAIL | 1.953e+04 | [1.516e+04, 2.44e+04] |
| S2-high@tactical | 30 | 3256 | 3.361 | FAIL | 3178 | [2439, 3796] |
| S2-DM@industrial_mems | 30 | 1.94e+04 | 3.417 | FAIL | 1.881e+04 | [1.44e+04, 2.383e+04] |
| S2-DM@tactical | 30 | 1570 | 3.361 | FAIL | 1399 | [848.1, 2088] |
| S3@industrial_mems | 30 | 0.4912 | 3.417 | PASS | 0.4851 | [0.1592, 0.7355] |
| S3@tactical | 30 | 0.1011 | 3.361 | PASS | 0.1073 | [-0.004317, 0.1935] |
| S4@industrial_mems | 30 | 1.244e+04 | 3.417 | FAIL | 1.216e+04 | [9631, 1.498e+04] |
| S4@tactical | 30 | 2139 | 3.361 | FAIL | 2067 | [1695, 2470] |
| S6@industrial_mems | 30 | 4.618e+04 | 3.417 | FAIL | 4.482e+04 | [3.589e+04, 5.484e+04] |
| S6@tactical | 30 | 5682 | 3.361 | FAIL | 5365 | [4214, 6766] |
| S7-p2@industrial_mems | 30 | 4.535 | 3.417 | FAIL | 0.009264 | [-0.0008078, 0.05654] |
| S7-p2@tactical | 30 | 0.2844 | 3.361 | PASS | 0.02003 | [-0.02991, 0.05535] |
| S7-p5@industrial_mems | 30 | 3.385 | 3.417 | PASS | 0.002705 | [-0.01222, 0.01761] |
| S7-p5@tactical | 30 | 2.524 | 3.361 | PASS | 0.01384 | [-0.03062, 0.05629] |
| S7-p10@industrial_mems | 30 | 3.316e+06 | 3.417 | FAIL | 3.141e+06 | [2.289e+06, 4.301e+06] |
| S7-p10@tactical | 30 | 3.646e+05 | 3.361 | FAIL | 2.115e+05 | [3.552e+04, 5.663e+05] |
| S7-p20@industrial_mems | 30 | 2.285e+06 | 3.417 | FAIL | 2.134e+06 | [1.142e+06, 3.122e+06] |
| S7-p20@tactical | 30 | 3.135e+05 | 3.361 | FAIL | 2.506e+05 | [7549, 5.376e+05] |
| S7-p60@industrial_mems | 30 | 2.403e+05 | 3.417 | FAIL | 274 | [205.9, 454.5] |
| S7-p60@tactical | 30 | 1.358e+05 | 3.361 | FAIL | 4.519e+04 | [7410, 2.822e+05] |
| S14@industrial_mems | 0 | - | - | PENDING | - | - |
| S14@tactical | 0 | - | - | PENDING | - | - |

## S7 chattering (prereg bound 223 cycles/h, integer; 133 annotation only)

- S7-p2@industrial_mems: max 2/h -> PASS (<=133: yes)
- S7-p2@tactical: max 2/h -> PASS (<=133: yes)
- S7-p5@industrial_mems: max 2/h -> PASS (<=133: yes)
- S7-p5@tactical: max 2/h -> PASS (<=133: yes)
- S7-p10@industrial_mems: max 0/h -> PASS (<=133: yes)
- S7-p10@tactical: max 1/h -> PASS (<=133: yes)
- S7-p20@industrial_mems: max 1/h -> PASS (<=133: yes)
- S7-p20@tactical: max 0/h -> PASS (<=133: yes)
- S7-p60@industrial_mems: max 15/h -> PASS (<=133: yes)
- S7-p60@tactical: max 12/h -> PASS (<=133: yes)

## Scenario criteria (registry; status per scenario@grade; '*' = metric absent from records)

- S1@industrial_mems: rmse_h_vs_fixed_trust=PASS; far_le_1_per_hour=PASS; anees_in_band=PASS; mean_w_gnss_ge_0_95=PASS; tv_w_le_1_per_hour=FAIL
- S1@tactical: rmse_h_vs_fixed_trust=PASS; far_le_1_per_hour=PASS; anees_in_band=PASS; mean_w_gnss_ge_0_95=PASS; tv_w_le_1_per_hour=FAIL
- S2-low@industrial_mems: detection_prob=not-evaluable; damage_never_worse=FAIL
- S2-low@tactical: detection_prob=not-evaluable; damage_never_worse=FAIL
- S2-med@industrial_mems: detection_prob=PASS; damage_halved=FAIL; damage_never_worse=FAIL
- S2-med@tactical: detection_prob=PASS; damage_halved=FAIL; damage_never_worse=FAIL
- S2-high@industrial_mems: detection_prob=PASS; damage_halved=FAIL; damage_never_worse=FAIL
- S2-high@tactical: detection_prob=PASS; damage_halved=FAIL; damage_never_worse=FAIL
- S2-DM@industrial_mems: detection_prob=not-evaluable; damage_never_worse=FAIL
- S2-DM@tactical: detection_prob=not-evaluable; damage_never_worse=FAIL
- S3@industrial_mems: tdist_consistency_no_update=FAIL*
- S3@tactical: tdist_consistency_no_update=FAIL*
- S4@industrial_mems: s2_s3_joint_plus_reacq_cap=FAIL*
- S4@tactical: s2_s3_joint_plus_reacq_cap=FAIL*
- S6@industrial_mems: h3_latency_eff=not-evaluable; never_worse=FAIL
- S6@tactical: h3_latency_eff=not-evaluable; never_worse=FAIL
- S6-coast@industrial_mems: coast_ratio_exploratory=not-evaluable
- S6-coast@tactical: coast_ratio_exploratory=not-evaluable
- S11@industrial_mems: finite_spd_and_vs_raw_gnss=FAIL
- S11@tactical: finite_spd_and_vs_raw_gnss=FAIL
- S13@industrial_mems: t_rec_bounds=FAIL
- S13@tactical: t_rec_bounds=FAIL
- S14@industrial_mems: PENDING (no data)
- S14@tactical: PENDING (no data)
- S5: quorum_or_skip_no_deadlock=PASS; auc_drop_le_0_02=FAIL*
- S8: global_model_within_2_rounds=FAIL; first_attack_auc=not-evaluable
- S9: no_deadlock_auc_bound=FAIL*
- S12-f20: auc_drop_f20=FAIL*
- S12-f40: auc_drop_f40=not-evaluable*
- S15: attacked_meet_s2_pd=PASS; unattacked_far_no_quarantine=FAIL
- S10-* (32 rids): see M3_REPORT.md section 2
