# round 3 (AMENDMENT R3) M3 summary (core-freeze-6, seeds 10060-10089, n=30/cell)

sigma_nom (results/sigma_nom_freeze6.json): industrial_mems 1.098 m, tactical 1.117 m. Tasks: 5340/5340 ok, 0 missing = none (failed files: 0).

## Confirmatory family (paired Wilcoxon, Holm fixed m=8; HL = A-B with 95% BCa CI)

| Test | Setting | Metric (A vs B) | n | raw p | Holm p | Reject? | HL | 95% CI |
|---|---|---|---|---|---|---|---|---|
| H1_rmse_h_att_vs_A | S2-med@industrial_mems | rmse_h_att (fedqpnt_local vs baseline_a) | 30 | 0.271 | 1 | no | 85.3 | [-59.68, 235] |
| H1_latency_on_vs_A | S2-med@industrial_mems | latency_on (fedqpnt_local vs baseline_a) | 30 | 0.0004653 | 0.003722 | YES | -0.5 | [-1, -1] |
| H2_pd10_vs_Bcont | freeze-6 fleet file::h2 | pd10 (fedqpnt vs baseline_b_cont) | 10 | 1 | 1 | no | 0 | [0, 0] |
| H2_onset_latency_vs_Bcont | freeze-6 fleet file::h2 | onset_latency (fedqpnt vs baseline_b_cont) | 10 | 1 | 1 | no | 0 | [0, 0] |
| H3_latency_eff_mems | S6@industrial_mems | latency_eff (fedqpnt_local vs abl_minus_quantum) | 30 | 1 | 1 | no | 0 | [0, 0] |
| H3_latency_eff_tactical | S6@tactical | latency_eff (fedqpnt_local vs abl_minus_quantum) | 30 | 1 | 1 | no | 0 | [0, 0] |
| H4_pd10_coldstart | freeze-6 fleet file::h4 | pd10 (fedqpnt vs baseline_b_cont) | 10 | 1 | 1 | no | 0 | [0, 0] |
| H4_onset_latency_coldstart | freeze-6 fleet file::h4 | onset_latency (fedqpnt vs baseline_b_cont) | 10 | 1 | 1 | no | 0 | [0, 0] |

## Safety principle: mean_def <= mean_undef + 3 sigma_nom (field max_h_att; max_h_pre for S1)

| Scenario@grade | n | margin (m) | 3sigma_nom (m) | Primary | HL (def-undef) | 95% CI |
|---|---|---|---|---|---|---|
| S1@industrial_mems | 30 | -0.002229 | 3.293 | PASS | -0.003235 | [-0.02423, 0.01675] |
| S1@tactical | 30 | -0.01957 | 3.351 | PASS | -0.01949 | [-0.07094, 0.01735] |
| S2-low@industrial_mems | 30 | 2255 | 3.293 | FAIL | 2153 | [1595, 2758] |
| S2-low@tactical | 30 | 2865 | 3.351 | FAIL | 2779 | [2060, 3513] |
| S2-med@industrial_mems | 30 | 1994 | 3.293 | FAIL | 1873 | [1343, 2518] |
| S2-med@tactical | 30 | 2560 | 3.351 | FAIL | 2476 | [1768, 3230] |
| S2-high@industrial_mems | 30 | 1746 | 3.293 | FAIL | 1644 | [1081, 2295] |
| S2-high@tactical | 30 | 2230 | 3.351 | FAIL | 2162 | [1451, 2881] |
| S2-DM@industrial_mems | 30 | -60.09 | 3.293 | PASS | -59.84 | [-685.8, 577.8] |
| S2-DM@tactical | 30 | 522.2 | 3.351 | FAIL | 451.7 | [-269.8, 1172] |
| S3@industrial_mems | 30 | -0.006842 | 3.293 | PASS | -0.02383 | [-0.2544, 0.1847] |
| S3@tactical | 30 | 0.6821 | 3.351 | PASS | 0.04195 | [-0.06805, 0.3864] |
| S4@industrial_mems | 30 | 1044 | 3.293 | FAIL | 1015 | [743.7, 1303] |
| S4@tactical | 30 | 1502 | 3.351 | FAIL | 1459 | [1042, 1874] |
| S6@industrial_mems | 30 | 4.744e+04 | 3.293 | FAIL | 4.677e+04 | [3.706e+04, 5.712e+04] |
| S6@tactical | 30 | 6806 | 3.351 | FAIL | 6348 | [4804, 8439] |
| S7-p2@industrial_mems | 30 | 29.15 | 3.293 | FAIL | 28.12 | [17.97, 38.77] |
| S7-p2@tactical | 30 | 10.91 | 3.351 | FAIL | 7.419 | [4.258, 10.77] |
| S7-p5@industrial_mems | 30 | 26.07 | 3.293 | FAIL | 25.03 | [16.05, 35.16] |
| S7-p5@tactical | 30 | 165 | 3.351 | FAIL | 46.57 | [28, 121.4] |
| S7-p10@industrial_mems | 30 | 121.5 | 3.293 | FAIL | 122 | [112.9, 131] |
| S7-p10@tactical | 30 | 5.118e+04 | 3.351 | FAIL | 1523 | [720.5, 9999] |
| S7-p20@industrial_mems | 30 | 144.5 | 3.293 | FAIL | 139.5 | [130.8, 149.8] |
| S7-p20@tactical | 30 | 1.559e+04 | 3.351 | FAIL | 3996 | [1323, 1.446e+04] |
| S7-p60@industrial_mems | 30 | 202.2 | 3.293 | FAIL | 171.3 | [83.6, 270.7] |
| S7-p60@tactical | 30 | 6.585e+04 | 3.351 | FAIL | 4591 | [1374, 3.383e+04] |

## S7 chattering (prereg bound 223 cycles/h, integer; 133 annotation only)

- S7-p2@industrial_mems: max 3/h -> PASS (<=133: yes)
- S7-p2@tactical: max 4/h -> PASS (<=133: yes)
- S7-p5@industrial_mems: max 4/h -> PASS (<=133: yes)
- S7-p5@tactical: max 4/h -> PASS (<=133: yes)
- S7-p10@industrial_mems: max 1/h -> PASS (<=133: yes)
- S7-p10@tactical: max 1/h -> PASS (<=133: yes)
- S7-p20@industrial_mems: max 1/h -> PASS (<=133: yes)
- S7-p20@tactical: max 1/h -> PASS (<=133: yes)
- S7-p60@industrial_mems: max 29/h -> PASS (<=133: yes)
- S7-p60@tactical: max 13/h -> PASS (<=133: yes)

## Scenario criteria (registry; status per scenario@grade; '*' = metric absent from records)

- S1@industrial_mems: rmse_h_vs_fixed_trust=PASS; far_le_1_per_hour=PASS; anees_in_band=PASS; mean_w_gnss_ge_0_95=PASS; tv_w_le_1_per_hour=FAIL
- S1@tactical: rmse_h_vs_fixed_trust=PASS; far_le_1_per_hour=PASS; anees_in_band=PASS; mean_w_gnss_ge_0_95=PASS; tv_w_le_1_per_hour=FAIL
- S2-low@industrial_mems: detection_prob=not-evaluable; damage_never_worse=FAIL
- S2-low@tactical: detection_prob=not-evaluable; damage_never_worse=FAIL
- S2-med@industrial_mems: detection_prob=PASS; damage_halved=FAIL; damage_never_worse=FAIL
- S2-med@tactical: detection_prob=PASS; damage_halved=FAIL; damage_never_worse=FAIL
- S2-high@industrial_mems: detection_prob=PASS; damage_halved=FAIL; damage_never_worse=FAIL
- S2-high@tactical: detection_prob=PASS; damage_halved=FAIL; damage_never_worse=FAIL
- S2-DM@industrial_mems: detection_prob=not-evaluable; damage_never_worse=PASS
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
- S14@industrial_mems: no_slow_drift=not-evaluable*
- S14@tactical: no_slow_drift=not-evaluable*
- S5: quorum_or_skip_no_deadlock=PASS; auc_drop_le_0_02=FAIL*
- S8: global_model_within_2_rounds=PASS; first_attack_auc=not-evaluable
- S9: no_deadlock_auc_bound=FAIL*
- S12-f20: auc_drop_f20=FAIL*
- S12-f40: auc_drop_f40=not-evaluable*
- S15: attacked_meet_s2_pd=PASS; unattacked_far_no_quarantine=PASS
- S10-* (32 rids): see M3_REPORT.md section 2
