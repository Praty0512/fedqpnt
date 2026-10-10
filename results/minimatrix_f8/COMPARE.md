# Mini-matrix COMPARE (f8, f7; tuning seeds; medians over seeds; units m, s, ns)

'nan' = undefined for all seeds (no such window), '-' = not run in that root. Current = f8.

## KEY cells (fedqpnt_local / fedqpnt; undefended and baseline_a from the current root)

| rid | grade | metric | f8 | f7 | undefended | baseline_a |
|---|---|---|---|---|---|---|
| S1 | industrial_mems | rmse_h_pre | 1.58 | 1.58 | 1.6 | 1.58 |
| S1 | industrial_mems | fpr | 0 | 0 | 0 | 0 |
| S1 | tactical | rmse_h_pre | 1.61 | 1.61 | 1.71 | 1.68 |
| S1 | tactical | fpr | 0 | 0 | 0 | 0 |
| S2-med | industrial_mems | rmse_h_att | 1.04e+03 | 954 | 254 | 756 |
| S2-med | industrial_mems | rmse_h_post | 1.33e+03 | 1.23e+03 | 181 | 213 |
| S2-med | industrial_mems | max_h_att | 2.55e+03 | 2.36e+03 | 473 | 1.98e+03 |
| S2-med | industrial_mems | fpr | 0.164 | 0.164 | 0 | 0.0201 |
| S2-med | tactical | rmse_h_att | 1.72e+03 | 1.72e+03 | 253 | 1.12e+03 |
| S2-med | tactical | rmse_h_post | 2.47e+03 | 2.47e+03 | 182 | 247 |
| S2-med | tactical | max_h_att | 4.53e+03 | 4.53e+03 | 473 | 2.83e+03 |
| S2-med | tactical | fpr | 0.164 | 0.164 | 0 | 0.0168 |
| S3 | industrial_mems | rmse_h_att | 16.8 | 16.8 | 17 | 16.9 |
| S3 | industrial_mems | rmse_h_post | 2.53 | 2.55 | 2.51 | 2.5 |
| S3 | industrial_mems | max_h_att | 51.5 | 51.5 | 51.8 | 51.5 |
| S3 | industrial_mems | fpr | 0 | 0 | 0 | 0 |
| S3 | tactical | rmse_h_att | 26.3 | 26.3 | 26.5 | 26.4 |
| S3 | tactical | rmse_h_post | 3.27 | 3.28 | 3.14 | 3.13 |
| S3 | tactical | max_h_att | 64.8 | 64.8 | 65.5 | 65.1 |
| S3 | tactical | fpr | 0 | 0 | 0 | 0 |
| S4 | industrial_mems | rmse_h_att | 559 | 501 | 137 | 341 |
| S4 | industrial_mems | rmse_h_post | 1.12e+03 | 1.12e+03 | 161 | 110 |
| S4 | industrial_mems | max_h_att | 1.37e+03 | 1.24e+03 | 291 | 974 |
| S4 | industrial_mems | fpr | 0.506 | 0.506 | 0.00633 | 0.0253 |
| S4 | tactical | rmse_h_att | 951 | 951 | 137 | 119 |
| S4 | tactical | rmse_h_post | 1.12e+03 | 1.04e+03 | 162 | 55 |
| S4 | tactical | max_h_att | 2.48e+03 | 2.48e+03 | 291 | 328 |
| S4 | tactical | fpr | 0.506 | 0.506 | 0.00633 | 0.019 |
| S6 | industrial_mems | rmse_h_pre | 2.06 | 2.07 | 2.07 | - |
| S6 | industrial_mems | rmse_h_att | 1.589e+04 | 1.590e+04 | 438 | - |
| S6 | industrial_mems | rmse_h_post | 2.130e+04 | 2.130e+04 | 266 | - |
| S6 | industrial_mems | max_h_att | 3.933e+04 | 3.934e+04 | 777 | - |
| S6 | industrial_mems | fpr | 0.132 | 0.132 | 0 | - |
| S6 | tactical | rmse_h_pre | 2.02 | 2.02 | 2.1 | - |
| S6 | tactical | rmse_h_att | 2.61e+03 | 2.61e+03 | 438 | - |
| S6 | tactical | rmse_h_post | 4.05e+03 | 4.05e+03 | 266 | - |
| S6 | tactical | max_h_att | 7.04e+03 | 7.04e+03 | 777 | - |
| S6 | tactical | fpr | 0.132 | 0.132 | 0 | - |
| S13 | industrial_mems | rmse_h_att | 25 | 25.2 | - | - |
| S13 | industrial_mems | rmse_h_post | 19.5 | 19.4 | - | - |
| S13 | industrial_mems | max_h_att | 38.9 | 39.1 | - | - |
| S13 | industrial_mems | fpr | 0.292 | 0.292 | - | - |
| S13 | tactical | rmse_h_att | 24.8 | 24.9 | - | - |
| S13 | tactical | rmse_h_post | 259 | 264 | - | - |
| S13 | tactical | max_h_att | 38.6 | 38.8 | - | - |
| S13 | tactical | fpr | 0.875 | 0.875 | - | - |

## FLAGS: defended worse than undefended / baseline (median, strict >) in f8

- f8 S2-med@industrial_mems: fedqpnt_local rmse_h_att 1.04e+03 > undefended 254 (x4.1)
- f8 S2-med@industrial_mems: fedqpnt_local rmse_h_post 1.33e+03 > undefended 181 (x7.3)
- f8 S2-med@industrial_mems: fedqpnt_local rmse_h_att 1.04e+03 > baseline_a 756 (x1.4)
- f8 S2-med@industrial_mems: fedqpnt_local rmse_h_post 1.33e+03 > baseline_a 213 (x6.2)
- f8 S2-med@tactical: fedqpnt_local rmse_h_att 1.72e+03 > undefended 253 (x6.8)
- f8 S2-med@tactical: fedqpnt_local rmse_h_post 2.47e+03 > undefended 182 (x13.6)
- f8 S2-med@tactical: fedqpnt_local rmse_h_att 1.72e+03 > baseline_a 1.12e+03 (x1.5)
- f8 S2-med@tactical: fedqpnt_local rmse_h_post 2.47e+03 > baseline_a 247 (x10.0)
- f8 S4@industrial_mems: fedqpnt_local rmse_h_att 559 > undefended 137 (x4.1)
- f8 S4@industrial_mems: fedqpnt_local rmse_h_post 1.12e+03 > undefended 161 (x7.0)
- f8 S4@industrial_mems: fedqpnt_local rmse_h_att 559 > baseline_a 341 (x1.6)
- f8 S4@industrial_mems: fedqpnt_local rmse_h_post 1.12e+03 > baseline_a 110 (x10.2)
- f8 S4@tactical: fedqpnt_local rmse_h_att 951 > undefended 137 (x6.9)
- f8 S4@tactical: fedqpnt_local rmse_h_post 1.12e+03 > undefended 162 (x6.9)
- f8 S4@tactical: fedqpnt_local rmse_h_att 951 > baseline_a 119 (x8.0)
- f8 S4@tactical: fedqpnt_local rmse_h_post 1.12e+03 > baseline_a 55 (x20.4)
- f8 S6@industrial_mems: fedqpnt_local rmse_h_att 1.589e+04 > undefended 438 (x36.3)
- f8 S6@industrial_mems: fedqpnt_local rmse_h_post 2.130e+04 > undefended 266 (x80.0)
- f8 S6@tactical: fedqpnt_local rmse_h_att 2.61e+03 > undefended 438 (x6.0)
- f8 S6@tactical: fedqpnt_local rmse_h_post 4.05e+03 > undefended 266 (x15.2)

## M3 safety margin (f8): mean(defended) - mean(undefended) vs 3 sigma_nom

| rid | field | mean def | mean undef | margin | 3sigma_nom | pass |
|---|---|---|---|---|---|---|
| S1@industrial_mems | max_h_pre | 3.24 | 3.26 | -0.0208 | 3.42 | PASS |
| S1@tactical | max_h_pre | 3.23 | 3.26 | -0.0385 | 3.36 | PASS |
| S2-med@industrial_mems | max_h_att | 3.49e+03 | 472 | 3.02e+03 | 3.42 | FAIL |
| S2-med@tactical | max_h_att | 3.98e+03 | 472 | 3.5e+03 | 3.36 | FAIL |
| S3@industrial_mems | max_h_att | 50.9 | 48.6 | 2.28 | 3.42 | PASS |
| S3@tactical | max_h_att | 70.3 | 69.6 | 0.751 | 3.36 | PASS |
| S4@industrial_mems | max_h_att | 1.83e+03 | 292 | 1.53e+03 | 3.42 | FAIL |
| S4@tactical | max_h_att | 2.26e+03 | 292 | 1.97e+03 | 3.36 | FAIL |
| S6@industrial_mems | max_h_att | 3.475e+04 | 776 | 3.397e+04 | 3.42 | FAIL |
| S6@tactical | max_h_att | 7e+03 | 776 | 6.22e+03 | 3.36 | FAIL |

## ANOMALY scan (f8, defended method, per seed)

(none)

## STATUS != ok

(none)

---

## S10-r1-c0.5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r1-c0.5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r1-c0.73@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r1-c0.73@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r1-c2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r1-c2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.99 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10-c0.5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10-c0.5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10-c0.73@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10-c0.73@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10-c2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10-c2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r1@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r1@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.99 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2-c0.5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2-c0.5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2-c0.73@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2-c0.73@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2-c2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2-c2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5-c0.5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5-c0.5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.41 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5-c0.73@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5-c0.73@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.41 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5-c2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5-c2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.4 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.4 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S11@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 5.879e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | - |

## S11@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 4.590e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | - |

## S12-f20

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt | f8 | 1/1 | 2.29 | - | - | - | 0 | - | - | - | 4.7 | - |
| fedqpnt | f7 | 2/2 | 16.1 | - | - | - | 0.327 | - | - | - | 4.75 | - |
| fedqpnt_clean | f8 | 1/1 | 2.29 | - | - | - | 0 | - | - | - | 4.7 | - |
| fedqpnt_clean | f7 | 2/2 | 16.1 | - | - | - | 0.327 | - | - | - | 4.75 | - |

## S12-f40

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt | f8 | 1/1 | 2.29 | - | - | - | 0 | - | - | - | 4.7 | - |
| fedqpnt | f7 | 2/2 | 16.1 | - | - | - | 0.327 | - | - | - | 4.75 | - |
| fedqpnt_clean | f8 | 1/1 | 2.29 | - | - | - | 0 | - | - | - | 4.7 | - |
| fedqpnt_clean | f7 | 2/2 | 16.1 | - | - | - | 0.327 | - | - | - | 4.75 | - |

## S13@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f8 | 3/3 | nan | 25 | 19.5 | 38.9 | 0.292 | 60 | 104 | 0.981 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 25.2 | 19.4 | 39.1 | 0.292 | 60 | 104 | 0.975 | - | - |

## S13@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f8 | 3/3 | nan | 24.8 | 259 | 38.6 | 0.875 | 60 | nan | 0.982 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 24.9 | 264 | 38.8 | 0.875 | 60 | nan | 0.975 | - | - |

## S14@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 1/1 | 2.53 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S14@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 1/1 | 2.53 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S15

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt | f8 | 1/1 | 2.3 | 1.74e+03 | 2.65e+03 | - | 0.0493 | 1 | - | - | 4.7 | 0.924 |
| fedqpnt | f7 | 2/2 | 15.1 | 1.32e+03 | 2.01e+03 | - | 0.379 | 1 | - | - | 4.75 | 0.923 |

## S1@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f8 | 3/3 | 1.58 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_a | f7 | 3/3 | 1.58 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_bin | f8 | 3/3 | 1.57 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_bin | f7 | 3/3 | 1.57 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_cont | f8 | 3/3 | 1.58 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_cont | f7 | 3/3 | 1.58 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| bprime | f8 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| bprime | f7 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f8 | 3/3 | 1.58 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f7 | 3/3 | 1.58 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fixed_trust | f8 | 3/3 | 1.6 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fixed_trust | f7 | 3/3 | 1.6 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| undefended | f8 | 3/3 | 1.6 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| undefended | f7 | 3/3 | 1.6 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S1@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f8 | 3/3 | 1.68 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_a | f7 | 3/3 | 1.68 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_bin | f8 | 3/3 | 1.66 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_bin | f7 | 3/3 | 1.66 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_cont | f8 | 3/3 | 1.61 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_cont | f7 | 3/3 | 1.61 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| bprime | f8 | 3/3 | 1.62 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| bprime | f7 | 3/3 | 1.62 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f8 | 3/3 | 1.61 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f7 | 3/3 | 1.61 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fixed_trust | f8 | 3/3 | 1.71 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fixed_trust | f7 | 3/3 | 1.71 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| undefended | f8 | 3/3 | 1.71 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| undefended | f7 | 3/3 | 1.71 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S2-DM@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f7 | 3/3 | nan | 834 | 172 | 2.08e+03 | 0.00934 | 1 | 2.8 | 0.00333 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 2.32e+03 | 3.03e+03 | 4.35e+03 | 0.016 | 1 | nan | 0.0532 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 885 | 1.17e+03 | 2.19e+03 | 0.169 | 1 | 50.8 | 0.0572 | - | - |
| bprime | f7 | 3/3 | nan | 1.66e+03 | 4.97e+03 | 4.39e+03 | 0.897 | 1 | 11.8 | 0.0328 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 885 | 1.17e+03 | 2.19e+03 | 0.169 | 1 | 50.8 | 0.0572 | - | - |
| fixed_trust | f7 | 3/3 | nan | 2.35e+03 | 3.42e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 2.37e+03 | 1.68e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | - |

## S2-DM@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f7 | 3/3 | nan | 1.79e+03 | 487 | 4.71e+03 | 0.00934 | 1 | 2.8 | 0.00333 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 2.37e+03 | 3.25e+03 | 4.35e+03 | 0.016 | 1 | nan | 0.0532 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 1.68e+03 | 2.48e+03 | 4.43e+03 | 0.169 | 1 | 53.8 | 0.0572 | - | - |
| bprime | f7 | 3/3 | nan | 1.72e+03 | 1.210e+04 | 3.96e+03 | 0.9 | 1 | 11.4 | 0.0237 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 1.68e+03 | 2.48e+03 | 4.43e+03 | 0.169 | 1 | 53.8 | 0.0572 | - | - |
| fixed_trust | f7 | 3/3 | nan | 2.37e+03 | 3.73e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 2.37e+03 | 1.7e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | - |

## S2-high@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f7 | 3/3 | nan | 1.48e+03 | 1.49 | 3.89e+03 | 0 | 3 | 6 | 0.0331 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 379 | 300 | 708 | 0.0134 | 21 | 221 | 0.116 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 985 | 1.27e+03 | 2.43e+03 | 0.164 | 1 | 49 | 0.057 | - | - |
| bprime | f7 | 3/3 | nan | 380 | 1.38e+03 | 708 | 0.899 | 302 | 245 | 0.999 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 985 | 1.27e+03 | 2.43e+03 | 0.164 | 1 | 49 | 0.057 | - | - |
| fixed_trust | f7 | 3/3 | nan | 380 | 408 | 708 | 0 | 3 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 380 | 272 | 708 | 0 | 3 | nan | 1 | - | - |

## S2-high@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f7 | 3/3 | nan | 1.2e+03 | 1.45 | 3.05e+03 | 0 | 3 | 11 | 0.0331 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 371 | 300 | 703 | 0.0134 | 21 | 238 | 0.116 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 1.68e+03 | 2.41e+03 | 4.42e+03 | 0.164 | 1 | 50 | 0.057 | - | - |
| bprime | f7 | 3/3 | nan | 380 | 1.07e+03 | 708 | 0.899 | 302 | nan | 0.999 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 1.68e+03 | 2.41e+03 | 4.42e+03 | 0.164 | 1 | 50 | 0.057 | - | - |
| fixed_trust | f7 | 3/3 | nan | 380 | 477 | 708 | 0 | 3 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 380 | 274 | 708 | 0 | 3 | nan | 1 | - | - |

## S2-low@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f7 | 3/3 | nan | 629 | 69.1 | 1.66e+03 | 0.00336 | 1 | 3 | 0.0132 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 127 | 90.9 | 237 | 0.0201 | 16 | 176 | 0.1 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 931 | 1.21e+03 | 2.3e+03 | 0.164 | 1 | 49 | 0.057 | - | - |
| bprime | f7 | 3/3 | nan | 127 | 403 | 237 | 0.674 | 302 | 204 | 0.999 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 931 | 1.21e+03 | 2.3e+03 | 0.164 | 1 | 49 | 0.057 | - | - |
| fixed_trust | f7 | 3/3 | nan | 127 | 110 | 237 | 0.00336 | 1 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 127 | 92.2 | 237 | 0.00336 | 1 | nan | 1 | - | - |

## S2-low@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f7 | 3/3 | nan | 910 | 142 | 2.31e+03 | 0.00336 | 1 | 1.39 | 0.0132 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 126 | 90.6 | 237 | 0.0201 | 16 | 198 | 0.1 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 1.76e+03 | 2.52e+03 | 4.62e+03 | 0.164 | 1 | 52.5 | 0.057 | - | - |
| bprime | f7 | 3/3 | nan | 127 | 367 | 237 | 0.899 | 302 | nan | 0.999 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 1.76e+03 | 2.52e+03 | 4.62e+03 | 0.164 | 1 | 52.5 | 0.057 | - | - |
| fixed_trust | f7 | 3/3 | nan | 127 | 117 | 238 | 0.00336 | 1 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 127 | 92.9 | 238 | 0.00336 | 1 | nan | 1 | - | - |

## S2-med@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f8 | 3/3 | nan | 756 | 213 | 1.98e+03 | 0.0201 | 1 | 6 | 0.00993 | - | - |
| baseline_a | f7 | 3/3 | nan | 1.09e+03 | 1.49 | 2.94e+03 | 0 | 3 | 4 | 0.0265 | - | - |
| baseline_b_bin | f8 | 3/3 | nan | 254 | 182 | 473 | 0.0168 | 2 | 194 | 0.0563 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 253 | 181 | 473 | 0.0134 | 19 | 194 | 0.11 | - | - |
| baseline_b_cont | f8 | 3/3 | nan | 1.04e+03 | 1.33e+03 | 2.55e+03 | 0.164 | 1 | 49 | 0.057 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 954 | 1.23e+03 | 2.36e+03 | 0.164 | 1 | 49 | 0.057 | - | - |
| bprime | f8 | 3/3 | nan | 253 | 1.02e+03 | 473 | 0.899 | 302 | 219 | 0.999 | - | - |
| bprime | f7 | 3/3 | nan | 253 | 1.02e+03 | 473 | 0.899 | 302 | 219 | 0.999 | - | - |
| fedqpnt_local | f8 | 3/3 | nan | 1.04e+03 | 1.33e+03 | 2.55e+03 | 0.164 | 1 | 49 | 0.057 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 954 | 1.23e+03 | 2.36e+03 | 0.164 | 1 | 49 | 0.057 | - | - |
| fixed_trust | f8 | 3/3 | nan | 254 | 252 | 473 | 0 | 1 | nan | 1 | - | - |
| fixed_trust | f7 | 3/3 | nan | 254 | 252 | 473 | 0 | 3 | nan | 1 | - | - |
| undefended | f8 | 3/3 | nan | 254 | 181 | 473 | 0 | 1 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 254 | 181 | 473 | 0 | 3 | nan | 1 | - | - |

## S2-med@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f8 | 3/3 | nan | 1.12e+03 | 247 | 2.83e+03 | 0.0168 | 1 | 3 | 0.00993 | - | - |
| baseline_a | f7 | 3/3 | nan | 935 | 1.4 | 2.37e+03 | 0 | 3 | 5 | 0.0265 | - | - |
| baseline_b_bin | f8 | 3/3 | nan | 253 | 181 | 472 | 0.0168 | 2 | 223 | 0.0563 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 248 | 180 | 469 | 0.0134 | 19 | 223 | 0.11 | - | - |
| baseline_b_cont | f8 | 3/3 | nan | 1.72e+03 | 2.47e+03 | 4.53e+03 | 0.164 | 1 | 51.3 | 0.057 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 1.72e+03 | 2.47e+03 | 4.53e+03 | 0.164 | 1 | 51.5 | 0.057 | - | - |
| bprime | f8 | 3/3 | nan | 253 | 718 | 472 | 0.899 | 302 | nan | 0.999 | - | - |
| bprime | f7 | 3/3 | nan | 253 | 718 | 472 | 0.899 | 302 | nan | 0.999 | - | - |
| fedqpnt_local | f8 | 3/3 | nan | 1.72e+03 | 2.47e+03 | 4.53e+03 | 0.164 | 1 | 51.3 | 0.057 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 1.72e+03 | 2.47e+03 | 4.53e+03 | 0.164 | 1 | 51.5 | 0.057 | - | - |
| fixed_trust | f8 | 3/3 | nan | 253 | 287 | 473 | 0 | 1 | nan | 1 | - | - |
| fixed_trust | f7 | 3/3 | nan | 253 | 287 | 473 | 0 | 3 | nan | 1 | - | - |
| undefended | f8 | 3/3 | nan | 253 | 182 | 473 | 0 | 1 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 253 | 182 | 473 | 0 | 3 | nan | 1 | - | - |

## S3@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f8 | 3/3 | nan | 16.9 | 2.5 | 51.5 | 0 | 62 | 13.2 | 1 | - | - |
| baseline_a | f7 | 3/3 | nan | 16.9 | 2.5 | 51.5 | 0 | 62 | 13.2 | 1 | - | - |
| baseline_b_bin | f8 | 3/3 | nan | 16.9 | 2.49 | 51.6 | 0 | 62 | 13.9 | 1 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 16.9 | 2.49 | 51.6 | 0 | 62 | 13.9 | 1 | - | - |
| baseline_b_cont | f8 | 3/3 | nan | 16.8 | 2.53 | 51.5 | 0 | 62 | 63 | 0.972 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 16.8 | 2.55 | 51.5 | 0 | 62 | 63 | 0.972 | - | - |
| bprime | f8 | 3/3 | nan | 17.6 | 2.47 | 53.3 | 0 | 62 | 18 | 0.972 | - | - |
| bprime | f7 | 3/3 | nan | 17.6 | 2.47 | 53.3 | 0 | 62 | 18 | 0.972 | - | - |
| fedqpnt_local | f8 | 3/3 | nan | 16.8 | 2.53 | 51.5 | 0 | 62 | 63 | 0.972 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 16.8 | 2.55 | 51.5 | 0 | 62 | 63 | 0.972 | - | - |
| fixed_trust | f8 | 3/3 | nan | 17 | 2.51 | 51.8 | 0 | 62 | 13.4 | 1 | - | - |
| fixed_trust | f7 | 3/3 | nan | 17 | 2.51 | 51.8 | 0 | 62 | 13.4 | 1 | - | - |
| undefended | f8 | 3/3 | nan | 17 | 2.51 | 51.8 | 0 | 62 | 13.4 | 1 | - | - |
| undefended | f7 | 3/3 | nan | 17 | 2.51 | 51.8 | 0 | 62 | 13.4 | 1 | - | - |

## S3@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f8 | 3/3 | nan | 26.4 | 3.13 | 65.1 | 0 | 62 | 31.5 | 1 | - | - |
| baseline_a | f7 | 3/3 | nan | 26.4 | 3.13 | 65.1 | 0 | 62 | 31.5 | 1 | - | - |
| baseline_b_bin | f8 | 3/3 | nan | 26.3 | 3.12 | 64.8 | 0 | 62 | 31.7 | 1 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 26.3 | 3.12 | 64.8 | 0 | 62 | 31.7 | 1 | - | - |
| baseline_b_cont | f8 | 3/3 | nan | 26.3 | 3.27 | 64.8 | 0 | 62 | 31 | 0.972 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 26.3 | 3.28 | 64.8 | 0 | 62 | 31 | 0.972 | - | - |
| bprime | f8 | 3/3 | nan | 27 | 3.34 | 66.6 | 0 | 62 | 33.5 | 0.972 | - | - |
| bprime | f7 | 3/3 | nan | 27 | 3.34 | 66.6 | 0 | 62 | 33.5 | 0.972 | - | - |
| fedqpnt_local | f8 | 3/3 | nan | 26.3 | 3.27 | 64.8 | 0 | 62 | 31 | 0.972 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 26.3 | 3.28 | 64.8 | 0 | 62 | 31 | 0.972 | - | - |
| fixed_trust | f8 | 3/3 | nan | 26.5 | 3.14 | 65.5 | 0 | 62 | 32.3 | 1 | - | - |
| fixed_trust | f7 | 3/3 | nan | 26.5 | 3.14 | 65.5 | 0 | 62 | 32.3 | 1 | - | - |
| undefended | f8 | 3/3 | nan | 26.5 | 3.14 | 65.5 | 0 | 62 | 32.3 | 1 | - | - |
| undefended | f7 | 3/3 | nan | 26.5 | 3.14 | 65.5 | 0 | 62 | 32.3 | 1 | - | - |

## S4@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f8 | 3/3 | nan | 341 | 110 | 974 | 0.0253 | 61 | 6 | 0.25 | - | - |
| baseline_a | f7 | 3/3 | nan | 417 | 79.8 | 1.18e+03 | 0.00633 | 77 | 9 | 0.312 | - | - |
| baseline_b_bin | f8 | 3/3 | nan | 135 | 164 | 289 | 0.0316 | 63 | nan | 0.295 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 136 | 166 | 290 | 0.038 | 82 | nan | 0.37 | - | - |
| baseline_b_cont | f8 | 3/3 | nan | 559 | 1.12e+03 | 1.37e+03 | 0.506 | 42 | 80 | 0.206 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 501 | 1.12e+03 | 1.24e+03 | 0.506 | 42 | 80 | 0.206 | - | - |
| bprime | f8 | 3/3 | nan | 137 | 402 | 291 | 0.81 | 242 | nan | 0.974 | - | - |
| bprime | f7 | 3/3 | nan | 137 | 402 | 291 | 0.81 | 242 | nan | 0.974 | - | - |
| fedqpnt_local | f8 | 3/3 | nan | 559 | 1.12e+03 | 1.37e+03 | 0.506 | 42 | 80 | 0.206 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 501 | 1.12e+03 | 1.24e+03 | 0.506 | 42 | 80 | 0.206 | - | - |
| fixed_trust | f8 | 3/3 | nan | 137 | 210 | 291 | 0.00633 | 61 | nan | 0.998 | - | - |
| fixed_trust | f7 | 3/3 | nan | 137 | 210 | 291 | 0.00633 | 77 | nan | 0.998 | - | - |
| undefended | f8 | 3/3 | nan | 137 | 161 | 291 | 0.00633 | 61 | nan | 0.998 | - | - |
| undefended | f7 | 3/3 | nan | 137 | 161 | 291 | 0.00633 | 77 | nan | 0.998 | - | - |

## S4@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f8 | 3/3 | nan | 119 | 55 | 328 | 0.019 | 62 | 11 | 0.254 | - | - |
| baseline_a | f7 | 3/3 | nan | 260 | 38.7 | 712 | 0.00633 | 77 | 99 | 0.312 | - | - |
| baseline_b_bin | f8 | 3/3 | nan | 131 | 166 | 285 | 0.0316 | 63 | nan | 0.295 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 137 | 169 | 290 | 0.038 | 82 | nan | 0.37 | - | - |
| baseline_b_cont | f8 | 3/3 | nan | 951 | 1.12e+03 | 2.48e+03 | 0.506 | 42 | 45.5 | 0.206 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 951 | 1.04e+03 | 2.48e+03 | 0.506 | 42 | 45.5 | 0.206 | - | - |
| bprime | f8 | 3/3 | nan | 137 | 379 | 291 | 0.81 | 242 | nan | 0.974 | - | - |
| bprime | f7 | 3/3 | nan | 137 | 379 | 291 | 0.81 | 242 | nan | 0.974 | - | - |
| fedqpnt_local | f8 | 3/3 | nan | 951 | 1.12e+03 | 2.48e+03 | 0.506 | 42 | 45.5 | 0.206 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 951 | 1.04e+03 | 2.48e+03 | 0.506 | 42 | 45.5 | 0.206 | - | - |
| fixed_trust | f8 | 3/3 | nan | 137 | 230 | 291 | 0.00633 | 62 | nan | 0.998 | - | - |
| fixed_trust | f7 | 3/3 | nan | 137 | 230 | 291 | 0.00633 | 77 | nan | 0.998 | - | - |
| undefended | f8 | 3/3 | nan | 137 | 162 | 291 | 0.00633 | 62 | nan | 0.998 | - | - |
| undefended | f7 | 3/3 | nan | 137 | 162 | 291 | 0.00633 | 77 | nan | 0.998 | - | - |

## S5

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f8 | 1/1 | 2.1 | - | - | - | 0 | - | - | - | 2.5 | - |
| baseline_a | f7 | 2/2 | 15.7 | - | - | - | 0.312 | - | - | - | 2.6 | - |
| fedqpnt | f8 | 1/1 | 2.09 | - | - | - | 0 | - | - | - | 2.5 | - |
| fedqpnt | f7 | 2/2 | 12.2 | - | - | - | 0.276 | - | - | - | 2.6 | - |
| fedqpnt_nofault | f8 | 1/1 | 2.29 | - | - | - | 0 | - | - | - | 4.7 | - |
| fedqpnt_nofault | f7 | 2/2 | 16.1 | - | - | - | 0.327 | - | - | - | 4.75 | - |

## S6-coast@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f7 | 3/3 | 1.51 | 158 | 2.17 | 419 | 0 | 182 | 3 | 1 | - | - |
| fedqpnt_local | f7 | 3/3 | 1.6 | 188 | 2.15 | 484 | 0 | 182 | 1 | 1 | - | - |

## S6-coast@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f7 | 3/3 | 1.53 | 55.1 | 2.02 | 124 | 0 | 182 | 4 | 1 | - | - |
| fedqpnt_local | f7 | 3/3 | 1.63 | 45.2 | 1.99 | 97.2 | 0 | 182 | 3 | 1 | - | - |

## S6@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f8 | 3/3 | 1.99 | 1.563e+04 | 2.140e+04 | 3.933e+04 | 0.132 | 1 | 89 | 0.0548 | - | - |
| abl_minus_quantum | f7 | 3/3 | 2 | 1.564e+04 | 2.141e+04 | 3.936e+04 | 0.132 | 1 | 89 | 0.0548 | - | - |
| fedqpnt_local | f8 | 3/3 | 2.06 | 1.589e+04 | 2.130e+04 | 3.933e+04 | 0.132 | 1 | 90 | 0.0548 | - | - |
| fedqpnt_local | f7 | 3/3 | 2.07 | 1.590e+04 | 2.130e+04 | 3.934e+04 | 0.132 | 1 | 90 | 0.0548 | - | - |
| undefended | f8 | 3/3 | 2.07 | 438 | 266 | 777 | 0 | 1 | 293 | 1 | - | - |
| undefended | f7 | 3/3 | 2.07 | 438 | 266 | 777 | 0 | 2 | 293 | 1 | - | - |

## S6@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f8 | 3/3 | 2 | 2.76e+03 | 4.43e+03 | 7.71e+03 | 0.132 | 1 | 79 | 0.0548 | - | - |
| abl_minus_quantum | f7 | 3/3 | 2 | 2.76e+03 | 4.43e+03 | 7.72e+03 | 0.132 | 1 | 79 | 0.0548 | - | - |
| fedqpnt_local | f8 | 3/3 | 2.02 | 2.61e+03 | 4.05e+03 | 7.04e+03 | 0.132 | 1 | 79 | 0.0548 | - | - |
| fedqpnt_local | f7 | 3/3 | 2.02 | 2.61e+03 | 4.05e+03 | 7.04e+03 | 0.132 | 1 | 79 | 0.0548 | - | - |
| undefended | f8 | 3/3 | 2.1 | 438 | 266 | 777 | 0 | 1 | 301 | 1 | - | - |
| undefended | f7 | 3/3 | 2.1 | 438 | 266 | 777 | 0 | 2 | 301 | 1 | - | - |

## S7-p10@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 29.8 | 24.9 | 129 | 0.839 | 5 | 49.5 | 0.116 | - | - |
| undefended | f7 | 3/3 | nan | 15.4 | 7.06 | 20.3 | 0 | 3.48e+03 | 68 | 1 | - | - |

## S7-p10@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 47.6 | 17.6 | 447 | 0.86 | 5 | 30.5 | 0.108 | - | - |
| undefended | f7 | 3/3 | nan | 15.4 | 7.26 | 20.5 | 0 | 3.48e+03 | 68 | 1 | - | - |

## S7-p20@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 46 | 24.8 | 158 | 0.957 | 10 | 65 | 0.109 | - | - |
| undefended | f7 | 3/3 | nan | 18.2 | 9.02 | 23.8 | 0 | 3.47e+03 | 83.5 | 1 | - | - |

## S7-p20@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 50.9 | 58.1 | 317 | 0.902 | 10 | nan | 0.122 | - | - |
| undefended | f7 | 3/3 | nan | 18.1 | 9.19 | 24 | 0 | 3.47e+03 | 73.7 | 1 | - | - |

## S7-p2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 2.5 | 2.08 | 5.32 | 0 | 3.48e+03 | 0 | 0.947 | - | - |
| undefended | f7 | 3/3 | nan | 2.49 | 2.18 | 5.31 | 0.00108 | 2.88e+03 | 0 | 1 | - | - |

## S7-p2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 2.52 | 2.03 | 5.19 | 0 | 3.48e+03 | 0 | 0.948 | - | - |
| undefended | f7 | 3/3 | nan | 2.56 | 2.56 | 5.18 | 0.00108 | 2.88e+03 | 0 | 1 | - | - |

## S7-p5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 13.8 | 5.6 | 18.5 | 0 | 3.48e+03 | 53.5 | 0.943 | - | - |
| undefended | f7 | 3/3 | nan | 13.7 | 5.8 | 18.5 | 0 | 3.48e+03 | 54.5 | 1 | - | - |

## S7-p5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 13.8 | 5.56 | 18.8 | 0 | 3.48e+03 | 52 | 0.943 | - | - |
| undefended | f7 | 3/3 | nan | 13.7 | 6.01 | 18.8 | 0 | 3.48e+03 | 53.4 | 1 | - | - |

## S7-p60@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 30.5 | 8.57 | 207 | 0.645 | 30 | 59.5 | 0.378 | - | - |
| undefended | f7 | 3/3 | nan | 19.9 | 10.8 | 28.4 | 0 | 3.45e+03 | 99 | 1 | - | - |

## S7-p60@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 237 | 64.2 | 1.21e+03 | 0.93 | 30 | 49 | 0.14 | - | - |
| undefended | f7 | 3/3 | nan | 19.9 | 10.9 | 28.6 | 0 | 3.45e+03 | 98 | 1 | - | - |

## S8

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_b_cont | f8 | 1/1 | 2.28 | - | - | - | 0 | - | - | - | 5 | - |
| baseline_b_cont | f7 | 2/2 | 18.7 | - | - | - | 0.35 | - | - | - | 4.5 | - |
| fedqpnt | f8 | 1/1 | 2.28 | - | - | - | 0 | - | - | - | 4.8 | - |
| fedqpnt | f7 | 2/2 | 18.5 | - | - | - | 0.35 | - | - | - | 4.3 | - |

## S9

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt | f8 | 1/1 | 2.28 | - | - | - | 0 | - | - | - | 4.8 | - |
| fedqpnt | f7 | 2/2 | 18.6 | - | - | - | 0.35 | - | - | - | 3.9 | - |
| fedqpnt_noloss | f8 | 1/1 | 2.28 | - | - | - | 0 | - | - | - | 5 | - |
| fedqpnt_noloss | f7 | 2/2 | 18.5 | - | - | - | 0.35 | - | - | - | 4.5 | - |
