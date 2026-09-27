# FedQPNT evaluation report

**PLUMBING CHECK ONLY -- these numbers are NOT results.** Generated from a short-duration, TUNING-seed dry run to prove resumability and end-to-end reporting; do not cite.

kappa_R_status (all rows): `PROVISIONAL_D047_kappa_R=40` (D-046/D-047)

## Section 6.1 acceptance criteria

### S1: Nominal
n per method: {'fedqpnt_local': 3, 'baseline_a': 3, 'undefended': 3}

| Criterion | Passed | Value | Blocked by D-047 | Detail |
|---|---|---|---|---|
| rmse_h_vs_fixed_trust | n/a | - | False | missing/mismatched fedqpnt_local vs fixed_trust |
| far_le_1_per_hour | FAIL | 30 | False | FAR=30.000/h/node (bound 1.0) |
| anees_in_band | FAIL | 0.4506 | False | ANEES_pos=0.451 (band [0.5,2]) |
| mean_w_gnss_ge_0_95 | FAIL | 0.1727 | False | mean w_gnss=0.1727 (bound >=0.95) |

### S2-low: Gradual spoof (low)
n per method: {'fedqpnt_local': 3, 'baseline_a': 3, 'undefended': 3}

| Criterion | Passed | Value | Blocked by D-047 | Detail |
|---|---|---|---|---|
| detection_prob | n/a | 1 | False | P_D=1.000 (n=3) |
| damage_bound | PASS | -0.007626 | False | median(MAX_h_a - MAX_h_u)=-0.008 (bound 3*sigma_nom=15.0) |

## Section 6.2/7 confirmatory hypotheses (H1-H4, Holm-corrected; H3 BLOCKED, excluded)
| Hypothesis | Evaluable | n | Wilcoxon p | Holm-adj p | Reject@.05 | HL diff | 95% BCa CI | d_z | rank-biserial r |
|---|---|---|---|---|---|---|---|---|---|
| H1_rmse_h_att_vs_A | NO (missing/mismatched fedqpnt_local vs baseline_a in S2-med) | - | - | - | - | - | - | - | - |
| H1_latency_on_vs_A | NO (missing/mismatched fedqpnt_local vs baseline_a in S2-med) | - | - | - | - | - | - | - | - |
| H2_rmse_h_att_vs_Bcont | NO (missing/mismatched fedqpnt_local vs baseline_b_cont in S2-med) | - | - | - | - | - | - | - | - |
| H2_latency_on_vs_Bcont | NO (missing/mismatched fedqpnt_local vs baseline_b_cont in S2-med) | - | - | - | - | - | - | - | - |
| H4_latency_on_coldstart | NO (missing/mismatched fedqpnt_local vs baseline_b_cont in S8) | - | - | - | - | - | - | - | - |
| H3_latency_eff_vs_minus_quantum | NO (missing/mismatched fedqpnt_local vs baseline_b_cont in S6) | - | - | - | - | - | - | - | - |

## Exploratory secondary metrics (unadjusted p-values, labelled exploratory)
| Scenario | Method | Metric | n | Mean | Median | Std |
|---|---|---|---|---|---|---|
| S1 | fedqpnt_local | rmse_h_pre | 3 | 4.981 | 4.443 | 1.004 |
| S1 | fedqpnt_local | max_h_pre | 3 | 6.815 | 5.978 | 1.663 |
| S1 | fedqpnt_local | anees_pos_pre | 3 | 0.4506 | 0.4892 | 0.0715 |
| S1 | fedqpnt_local | n_cyc_per_hour | 3 | 0 | 0 | 0 |
| S1 | fedqpnt_local | tv_w_per_hour | 3 | 25.27 | 24.81 | 1.004 |
| S1 | fedqpnt_local | mean_w_gnss | 3 | 0.1727 | 0.1834 | 0.03549 |
| S1 | fedqpnt_local | rmse_t_ns | 3 | 13.92 | 11.53 | 5.586 |
| S1 | fedqpnt_local | max_t_ns | 3 | 19 | 16.15 | 6.627 |
| S1 | fedqpnt_local | far_per_hour | 3 | 30 | 30 | 0 |
| S1 | fedqpnt_local | fpr | 3 | 0.9834 | 0.9834 | 0 |
| S1 | baseline_a | rmse_h_pre | 3 | 338.7 | 129.6 | 362.6 |
| S1 | baseline_a | max_h_pre | 3 | 960.5 | 359.5 | 1051 |
| S1 | baseline_a | anees_pos_pre | 3 | 3.558 | 0.6957 | 5.073 |
| S1 | baseline_a | n_cyc_per_hour | 3 | 150 | 150 | 120 |
| S1 | baseline_a | tv_w_per_hour | 3 | 340 | 330 | 255.2 |
| S1 | baseline_a | mean_w_gnss | 3 | 0.09714 | 0.07075 | 0.07245 |
| S1 | baseline_a | rmse_t_ns | 3 | 13.01 | 10.8 | 4.738 |
| S1 | baseline_a | max_t_ns | 3 | 18.23 | 15.52 | 5.204 |
| S1 | baseline_a | far_per_hour | 3 | 180 | 180 | 120 |
| S1 | baseline_a | fpr | 3 | 0.9001 | 0.9251 | 0.07407 |
| S1 | undefended | rmse_h_pre | 3 | 1.743 | 1.38 | 0.6443 |
| S1 | undefended | max_h_pre | 3 | 2.251 | 2.235 | 0.6382 |
| S1 | undefended | anees_pos_pre | 3 | 0.6029 | 0.659 | 0.1628 |
| S1 | undefended | n_cyc_per_hour | 3 | 0 | 0 | 0 |
| S1 | undefended | tv_w_per_hour | 3 | 30 | 30 | 0 |
| S1 | undefended | mean_w_gnss | 3 | 0.9958 | 0.9958 | 1.36e-16 |
| S1 | undefended | rmse_t_ns | 3 | 14.22 | 11.86 | 5.648 |
| S1 | undefended | max_t_ns | 3 | 20.18 | 17.2 | 6.908 |
| S1 | undefended | far_per_hour | 3 | 520 | 480 | 124.9 |
| S1 | undefended | fpr | 3 | 0.6639 | 0.6501 | 0.03153 |
| S2-low | fedqpnt_local | rmse_3_att | 3 | 19.71 | 18.53 | 2.36 |
| S2-low | fedqpnt_local | rmse_v_att | 3 | 0.6915 | 0.6899 | 0.02049 |
| S2-low | fedqpnt_local | t_dist | 3 | 0 | 0 | 0 |
| S2-low | fedqpnt_local | n_cyc_per_hour | 3 | 0 | 0 | 0 |
| S2-low | fedqpnt_local | tv_w_per_hour | 3 | 25.29 | 24.81 | 0.9745 |
| S2-low | fedqpnt_local | mean_w_gnss | 3 | 0.172 | 0.1834 | 0.03467 |
| S2-low | fedqpnt_local | rmse_t_ns | 3 | 13.37 | 11.21 | 5.364 |
| S2-low | fedqpnt_local | max_t_ns | 3 | 18.25 | 15.29 | 6.371 |
| S2-low | fedqpnt_local | far_per_hour | 3 | 120 | 120 | 0 |
| S2-low | fedqpnt_local | fpr | 3 | 0.9336 | 0.9336 | 1.36e-16 |
| S2-low | baseline_a | rmse_3_att | 3 | 310.4 | 53.01 | 461.8 |
| S2-low | baseline_a | rmse_v_att | 3 | 14.56 | 3.809 | 20.32 |
| S2-low | baseline_a | t_dist | 3 | 0.6667 | 1 | 0.5774 |
| S2-low | baseline_a | n_cyc_per_hour | 3 | 260 | 270 | 225.2 |
| S2-low | baseline_a | tv_w_per_hour | 3 | 550 | 570 | 450.4 |
| S2-low | baseline_a | mean_w_gnss | 3 | 0.1472 | 0.1124 | 0.1428 |
| S2-low | baseline_a | rmse_t_ns | 3 | 12.24 | 10.67 | 4.452 |
| S2-low | baseline_a | max_t_ns | 3 | 17.94 | 15.52 | 4.293 |
| S2-low | baseline_a | far_per_hour | 3 | 440.1 | 240.1 | 454.5 |
| S2-low | baseline_a | fpr | 3 | 0.7558 | 0.9003 | 0.3098 |
| S2-low | undefended | rmse_3_att | 3 | 18.79 | 18.74 | 0.5831 |
| S2-low | undefended | rmse_v_att | 3 | 0.6322 | 0.6341 | 0.00676 |
| S2-low | undefended | n_cyc_per_hour | 3 | 0 | 0 | 0 |
| S2-low | undefended | tv_w_per_hour | 3 | 30 | 30 | 0 |
| S2-low | undefended | mean_w_gnss | 3 | 0.9958 | 0.9958 | 1.36e-16 |
| S2-low | undefended | rmse_t_ns | 3 | 13.67 | 11.51 | 5.455 |
| S2-low | undefended | max_t_ns | 3 | 19.36 | 16.26 | 6.768 |
| S2-low | undefended | far_per_hour | 3 | 400.1 | 360.1 | 69.31 |
| S2-low | undefended | fpr | 3 | 0.8336 | 0.8003 | 0.05775 |
