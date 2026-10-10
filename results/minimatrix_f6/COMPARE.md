# Mini-matrix COMPARE (tuning seeds; medians over seeds; f6 = freeze6 branch, f5 = core-freeze-5)

Units m, s, ns. 'nan' = metric undefined for all seeds (e.g. no pre-attack/post-attack window). Status!=ok are listed under ANOMALIES.

## FLAGS: defended worse than undefended / baseline (median, strict >)

- f5 S11@industrial_mems: fedqpnt_local rmse_h_pre 5.884e+04 > undefended 17.5 (x3363.3)
- f5 S11@industrial_mems: fedqpnt_local rmse_h_pre 5.884e+04 > baseline_a 461 (x127.6)
- f5 S11@tactical: fedqpnt_local rmse_h_pre 4.590e+04 > undefended 4.05 (x11341.8)
- f5 S11@tactical: fedqpnt_local rmse_h_pre 4.590e+04 > baseline_a 3.81 (x12054.1)
- f5 S13@industrial_mems: fedqpnt_local rmse_h_post 36.9 > undefended 14.3 (x2.6)
- f5 S13@industrial_mems: fedqpnt_local rmse_h_post 36.9 > baseline_a 14.3 (x2.6)
- f5 S13@tactical: fedqpnt_local rmse_h_post 246 > undefended 14.6 (x16.8)
- f5 S13@tactical: fedqpnt_local rmse_h_post 246 > baseline_a 14.6 (x16.8)
- f6 S2-DM@industrial_mems: fedqpnt_local rmse_h_att 884 > baseline_a 834 (x1.1)
- f6 S2-DM@industrial_mems: fedqpnt_local rmse_h_post 1.18e+03 > baseline_a 172 (x6.9)
- f5 S2-DM@industrial_mems: fedqpnt_local rmse_h_att 1.155e+04 > undefended 2.37e+03 (x4.9)
- f5 S2-DM@industrial_mems: fedqpnt_local rmse_h_post 1.095e+05 > undefended 1.68e+03 (x65.2)
- f5 S2-DM@industrial_mems: fedqpnt_local rmse_h_post 1.095e+05 > baseline_a 3.22e+03 (x34.0)
- f6 S2-DM@tactical: fedqpnt_local rmse_h_post 1.584e+04 > undefended 1.7e+03 (x9.3)
- f6 S2-DM@tactical: fedqpnt_local rmse_h_post 1.584e+04 > baseline_a 487 (x32.5)
- f5 S2-DM@tactical: fedqpnt_local rmse_h_post 2.126e+04 > undefended 1.7e+03 (x12.5)
- f5 S2-DM@tactical: fedqpnt_local rmse_h_post 2.126e+04 > baseline_a 643 (x33.1)
- f6 S2-high@industrial_mems: fedqpnt_local rmse_h_att 985 > undefended 380 (x2.6)
- f6 S2-high@industrial_mems: fedqpnt_local rmse_h_post 1.27e+03 > undefended 272 (x4.7)
- f6 S2-high@industrial_mems: fedqpnt_local rmse_h_post 1.27e+03 > baseline_a 1.38 (x924.6)
- f5 S2-high@industrial_mems: fedqpnt_local rmse_h_att 1.116e+04 > undefended 380 (x29.3)
- f5 S2-high@industrial_mems: fedqpnt_local rmse_h_post 1.036e+05 > undefended 272 (x381.3)
- f5 S2-high@industrial_mems: fedqpnt_local rmse_h_att 1.116e+04 > baseline_a 5.07e+03 (x2.2)
- f5 S2-high@industrial_mems: fedqpnt_local rmse_h_post 1.036e+05 > baseline_a 6.76 (x15334.6)
- f6 S2-high@tactical: fedqpnt_local rmse_h_att 1.68e+03 > undefended 380 (x4.4)
- f6 S2-high@tactical: fedqpnt_local rmse_h_post 1.557e+04 > undefended 274 (x56.9)
- f6 S2-high@tactical: fedqpnt_local rmse_h_att 1.68e+03 > baseline_a 1.2e+03 (x1.4)
- f6 S2-high@tactical: fedqpnt_local rmse_h_post 1.557e+04 > baseline_a 1.38 (x11274.4)
- f5 S2-high@tactical: fedqpnt_local rmse_h_att 2.25e+03 > undefended 380 (x5.9)
- f5 S2-high@tactical: fedqpnt_local rmse_h_post 2.083e+04 > undefended 274 (x76.1)
- f5 S2-high@tactical: fedqpnt_local rmse_h_att 2.25e+03 > baseline_a 1.55e+03 (x1.4)
- f5 S2-high@tactical: fedqpnt_local rmse_h_post 2.083e+04 > baseline_a 1.45 (x14404.2)
- f6 S2-low@industrial_mems: fedqpnt_local rmse_h_att 930 > undefended 127 (x7.3)
- f6 S2-low@industrial_mems: fedqpnt_local rmse_h_post 1.21e+03 > undefended 92.2 (x13.1)
- f6 S2-low@industrial_mems: fedqpnt_local rmse_h_att 930 > baseline_a 629 (x1.5)
- f6 S2-low@industrial_mems: fedqpnt_local rmse_h_post 1.21e+03 > baseline_a 69 (x17.5)
- f5 S2-low@industrial_mems: fedqpnt_local rmse_h_att 1.161e+04 > undefended 127 (x91.4)
- f5 S2-low@industrial_mems: fedqpnt_local rmse_h_post 1.080e+05 > undefended 92.2 (x1172.0)
- f5 S2-low@industrial_mems: fedqpnt_local rmse_h_att 1.161e+04 > baseline_a 5.64e+03 (x2.1)
- f5 S2-low@industrial_mems: fedqpnt_local rmse_h_post 1.080e+05 > baseline_a 9.21 (x11725.9)
- f6 S2-low@tactical: fedqpnt_local rmse_h_att 1.76e+03 > undefended 127 (x13.8)
- f6 S2-low@tactical: fedqpnt_local rmse_h_post 1.626e+04 > undefended 92.9 (x175.0)
- f6 S2-low@tactical: fedqpnt_local rmse_h_att 1.76e+03 > baseline_a 910 (x1.9)
- f6 S2-low@tactical: fedqpnt_local rmse_h_post 1.626e+04 > baseline_a 142 (x114.8)
- f5 S2-low@tactical: fedqpnt_local rmse_h_att 2.33e+03 > undefended 127 (x18.3)
- f5 S2-low@tactical: fedqpnt_local rmse_h_post 2.155e+04 > undefended 92.9 (x232.0)
- f5 S2-low@tactical: fedqpnt_local rmse_h_att 2.33e+03 > baseline_a 1.4e+03 (x1.7)
- f5 S2-low@tactical: fedqpnt_local rmse_h_post 2.155e+04 > baseline_a 218 (x98.7)
- f6 S2-med@industrial_mems: fedqpnt_local rmse_h_att 954 > undefended 254 (x3.8)
- f6 S2-med@industrial_mems: fedqpnt_local rmse_h_post 1.24e+03 > undefended 181 (x6.8)
- f6 S2-med@industrial_mems: fedqpnt_local rmse_h_post 1.24e+03 > baseline_a 1.33 (x926.6)
- f5 S2-med@industrial_mems: fedqpnt_local rmse_h_att 1.142e+04 > undefended 253 (x45.1)
- f5 S2-med@industrial_mems: fedqpnt_local rmse_h_post 1.062e+05 > undefended 181 (x587.0)
- f5 S2-med@industrial_mems: fedqpnt_local rmse_h_att 1.142e+04 > baseline_a 5.35e+03 (x2.1)
- f5 S2-med@industrial_mems: fedqpnt_local rmse_h_post 1.062e+05 > baseline_a 7.93 (x13386.7)
- f6 S2-med@tactical: fedqpnt_local rmse_h_att 1.72e+03 > undefended 253 (x6.8)
- f6 S2-med@tactical: fedqpnt_local rmse_h_post 1.597e+04 > undefended 182 (x87.6)
- f6 S2-med@tactical: fedqpnt_local rmse_h_att 1.72e+03 > baseline_a 935 (x1.8)
- f6 S2-med@tactical: fedqpnt_local rmse_h_post 1.597e+04 > baseline_a 1.36 (x11767.2)
- f5 S2-med@tactical: fedqpnt_local rmse_h_att 2.3e+03 > undefended 253 (x9.1)
- f5 S2-med@tactical: fedqpnt_local rmse_h_post 2.125e+04 > undefended 182 (x116.6)
- f5 S2-med@tactical: fedqpnt_local rmse_h_att 2.3e+03 > baseline_a 1.39e+03 (x1.7)
- f5 S2-med@tactical: fedqpnt_local rmse_h_post 2.125e+04 > baseline_a 1.41 (x15083.2)
- f5 S3@industrial_mems: fedqpnt_local rmse_h_post 91 > undefended 4.01 (x22.7)
- f5 S3@industrial_mems: fedqpnt_local rmse_h_post 91 > baseline_a 5.14 (x17.7)
- f6 S4@industrial_mems: fedqpnt_local rmse_h_att 501 > undefended 137 (x3.7)
- f6 S4@industrial_mems: fedqpnt_local rmse_h_post 1.5e+03 > undefended 161 (x9.3)
- f6 S4@industrial_mems: fedqpnt_local rmse_h_att 501 > baseline_a 428 (x1.2)
- f6 S4@industrial_mems: fedqpnt_local rmse_h_post 1.5e+03 > baseline_a 86.6 (x17.3)
- f5 S4@industrial_mems: fedqpnt_local rmse_h_att 6.2e+03 > undefended 140 (x44.2)
- f5 S4@industrial_mems: fedqpnt_local rmse_h_post 3.634e+04 > undefended 161 (x226.3)
- f5 S4@industrial_mems: fedqpnt_local rmse_h_att 6.2e+03 > baseline_a 479 (x12.9)
- f5 S4@industrial_mems: fedqpnt_local rmse_h_post 3.634e+04 > baseline_a 83.4 (x435.8)
- f6 S4@tactical: fedqpnt_local rmse_h_att 951 > undefended 137 (x6.9)
- f6 S4@tactical: fedqpnt_local rmse_h_post 5.48e+03 > undefended 162 (x33.8)
- f6 S4@tactical: fedqpnt_local rmse_h_att 951 > baseline_a 260 (x3.7)
- f6 S4@tactical: fedqpnt_local rmse_h_post 5.48e+03 > baseline_a 38.8 (x141.3)
- f5 S4@tactical: fedqpnt_local rmse_h_att 1.26e+03 > undefended 137 (x9.2)
- f5 S4@tactical: fedqpnt_local rmse_h_post 7.21e+03 > undefended 162 (x44.5)
- f5 S4@tactical: fedqpnt_local rmse_h_att 1.26e+03 > baseline_a 244 (x5.1)
- f5 S4@tactical: fedqpnt_local rmse_h_post 7.21e+03 > baseline_a 50.8 (x141.9)
- f5 S5: fedqpnt rmse_h_pre 1.190e+04 > baseline_a 2.28 (x5231.3)
- f6 S6@industrial_mems: fedqpnt_local rmse_h_att 1.590e+04 > undefended 438 (x36.3)
- f6 S6@industrial_mems: fedqpnt_local rmse_h_post 2.130e+04 > undefended 266 (x80.0)
- f5 S6@industrial_mems: fedqpnt_local rmse_h_att 1.600e+04 > undefended 438 (x36.5)
- f5 S6@industrial_mems: fedqpnt_local rmse_h_post 2.140e+04 > undefended 266 (x80.4)
- f5 S6@industrial_mems: fedqpnt_local rmse_h_att 1.600e+04 > baseline_a 1.091e+04 (x1.5)
- f5 S6@industrial_mems: fedqpnt_local rmse_h_post 2.140e+04 > baseline_a 191 (x112.3)
- f6 S6@tactical: fedqpnt_local rmse_h_att 2.61e+03 > undefended 438 (x6.0)
- f6 S6@tactical: fedqpnt_local rmse_h_post 4.05e+03 > undefended 266 (x15.2)
- f5 S6@tactical: fedqpnt_local rmse_h_att 2.66e+03 > undefended 438 (x6.1)
- f5 S6@tactical: fedqpnt_local rmse_h_post 4.1e+03 > undefended 266 (x15.4)
- f5 S6@tactical: fedqpnt_local rmse_h_att 2.66e+03 > baseline_a 1.24e+03 (x2.1)
- f5 S6@tactical: fedqpnt_local rmse_h_post 4.1e+03 > baseline_a 2.36 (x1736.1)
- f6 S7-p10@industrial_mems: fedqpnt_local rmse_h_att 32.5 > undefended 15.4 (x2.1)
- f6 S7-p10@industrial_mems: fedqpnt_local rmse_h_post 22.7 > undefended 7.06 (x3.2)
- f5 S7-p10@industrial_mems: fedqpnt_local rmse_h_att 2.521e+06 > undefended 15.4 (x163500.7)
- f5 S7-p10@industrial_mems: fedqpnt_local rmse_h_post 3.946e+06 > undefended 7.06 (x558924.5)
- f5 S7-p10@industrial_mems: fedqpnt_local rmse_h_att 2.521e+06 > baseline_a 15.4 (x163465.0)
- f5 S7-p10@industrial_mems: fedqpnt_local rmse_h_post 3.946e+06 > baseline_a 7.06 (x559290.0)
- f6 S7-p10@tactical: fedqpnt_local rmse_h_att 44.5 > undefended 15.4 (x2.9)
- f6 S7-p10@tactical: fedqpnt_local rmse_h_post 52.5 > undefended 7.26 (x7.2)
- f5 S7-p10@tactical: fedqpnt_local rmse_h_att 5.108e+05 > undefended 15.4 (x33234.4)
- f5 S7-p10@tactical: fedqpnt_local rmse_h_post 8.596e+05 > undefended 7.26 (x118414.9)
- f5 S7-p10@tactical: fedqpnt_local rmse_h_att 5.108e+05 > baseline_a 15.4 (x33195.8)
- f5 S7-p10@tactical: fedqpnt_local rmse_h_post 8.596e+05 > baseline_a 7.31 (x117634.9)
- f6 S7-p20@industrial_mems: fedqpnt_local rmse_h_att 46 > undefended 18.2 (x2.5)
- f6 S7-p20@industrial_mems: fedqpnt_local rmse_h_post 27.7 > undefended 9.02 (x3.1)
- f6 S7-p20@tactical: fedqpnt_local rmse_h_att 33.9 > undefended 18.1 (x1.9)
- f6 S7-p20@tactical: fedqpnt_local rmse_h_post 14.4 > undefended 9.19 (x1.6)
- f6 S7-p60@industrial_mems: fedqpnt_local rmse_h_att 43.3 > undefended 19.9 (x2.2)
- f6 S7-p60@industrial_mems: fedqpnt_local rmse_h_post 19.3 > undefended 10.8 (x1.8)
- f6 S7-p60@tactical: fedqpnt_local rmse_h_att 236 > undefended 19.9 (x11.9)
- f6 S7-p60@tactical: fedqpnt_local rmse_h_post 47.3 > undefended 10.9 (x4.3)
- f5 S8: fedqpnt rmse_h_pre 1.148e+04 > baseline_b_cont 1.148e+04 (x1.0)

## M3 safety margin: mean(defended) - mean(undefended) vs 3 sigma_nom (field max_h_att, or max_h_pre when no attack window)

| ver | rid | field | mean def | mean undef | margin | 3sigma_nom | pass |
|---|---|---|---|---|---|---|---|
| f5 | S11@industrial_mems | max_h_pre | 1.389e+05 | 34.6 | 1.388e+05 | 3.42 | FAIL |
| f5 | S11@tactical | max_h_pre | 8.647e+04 | 6.91 | 8.646e+04 | 3.36 | FAIL |
| f5 | S13@industrial_mems | max_h_att | 38.9 | 39.1 | -0.197 | 3.42 | PASS |
| f5 | S13@tactical | max_h_att | 39.4 | 39.5 | -0.187 | 3.36 | PASS |
| f6 | S1@industrial_mems | max_h_pre | 3.25 | 3.26 | -0.0173 | 3.42 | PASS |
| f5 | S1@industrial_mems | max_h_pre | 4.15 | 4.13 | 0.0193 | 3.42 | PASS |
| f6 | S1@tactical | max_h_pre | 3.23 | 3.26 | -0.0369 | 3.36 | PASS |
| f5 | S1@tactical | max_h_pre | 3.29 | 3.32 | -0.038 | 3.36 | PASS |
| f6 | S2-DM@industrial_mems | max_h_att | 3.31e+03 | 4.25e+03 | -947 | 3.42 | PASS |
| f5 | S2-DM@industrial_mems | max_h_att | 2.716e+04 | 4.25e+03 | 2.290e+04 | 3.42 | FAIL |
| f6 | S2-DM@tactical | max_h_att | 3.95e+03 | 4.25e+03 | -298 | 3.36 | PASS |
| f5 | S2-DM@tactical | max_h_att | 5.44e+03 | 4.25e+03 | 1.18e+03 | 3.36 | FAIL |
| f6 | S2-high@industrial_mems | max_h_att | 3.38e+03 | 708 | 2.68e+03 | 3.42 | FAIL |
| f5 | S2-high@industrial_mems | max_h_att | 2.602e+04 | 708 | 2.531e+04 | 3.42 | FAIL |
| f6 | S2-high@tactical | max_h_att | 3.84e+03 | 708 | 3.13e+03 | 3.36 | FAIL |
| f5 | S2-high@tactical | max_h_att | 5.32e+03 | 708 | 4.61e+03 | 3.36 | FAIL |
| f6 | S2-low@industrial_mems | max_h_att | 3.46e+03 | 237 | 3.22e+03 | 3.42 | FAIL |
| f5 | S2-low@industrial_mems | max_h_att | 2.710e+04 | 237 | 2.686e+04 | 3.42 | FAIL |
| f6 | S2-low@tactical | max_h_att | 4e+03 | 237 | 3.76e+03 | 3.36 | FAIL |
| f5 | S2-low@tactical | max_h_att | 5.49e+03 | 237 | 5.25e+03 | 3.36 | FAIL |
| f6 | S2-med@industrial_mems | max_h_att | 3.43e+03 | 472 | 2.95e+03 | 3.42 | FAIL |
| f5 | S2-med@industrial_mems | max_h_att | 2.665e+04 | 472 | 2.617e+04 | 3.42 | FAIL |
| f6 | S2-med@tactical | max_h_att | 3.93e+03 | 472 | 3.46e+03 | 3.36 | FAIL |
| f5 | S2-med@tactical | max_h_att | 5.42e+03 | 472 | 4.95e+03 | 3.36 | FAIL |
| f6 | S3@industrial_mems | max_h_att | 49.3 | 48.6 | 0.74 | 3.42 | PASS |
| f5 | S3@industrial_mems | max_h_att | 450 | 448 | 1.92 | 3.42 | PASS |
| f6 | S3@tactical | max_h_att | 69.7 | 69.6 | 0.132 | 3.36 | PASS |
| f5 | S3@tactical | max_h_att | 92.7 | 92.7 | 0.0103 | 3.36 | PASS |
| f6 | S4@industrial_mems | max_h_att | 1.78e+03 | 291 | 1.49e+03 | 3.42 | FAIL |
| f5 | S4@industrial_mems | max_h_att | 1.513e+04 | 291 | 1.484e+04 | 3.42 | FAIL |
| f6 | S4@tactical | max_h_att | 2.24e+03 | 292 | 1.95e+03 | 3.36 | FAIL |
| f5 | S4@tactical | max_h_att | 3.06e+03 | 292 | 2.76e+03 | 3.36 | FAIL |
| f5 | S6-coast@industrial_mems | max_h_att | 481 | 480 | 0.877 | 3.42 | PASS |
| f5 | S6-coast@tactical | max_h_att | 94.1 | 92.5 | 1.54 | 3.36 | PASS |
| f6 | S6@industrial_mems | max_h_att | 3.474e+04 | 776 | 3.397e+04 | 3.42 | FAIL |
| f5 | S6@industrial_mems | max_h_att | 3.506e+04 | 776 | 3.428e+04 | 3.42 | FAIL |
| f6 | S6@tactical | max_h_att | 6.99e+03 | 776 | 6.22e+03 | 3.36 | FAIL |
| f5 | S6@tactical | max_h_att | 7.08e+03 | 776 | 6.31e+03 | 3.36 | FAIL |
| f6 | S7-p10@industrial_mems | max_h_att | 192 | 20.5 | 172 | 3.42 | FAIL |
| f5 | S7-p10@industrial_mems | max_h_att | 4.320e+06 | 20.5 | 4.320e+06 | 3.42 | FAIL |
| f6 | S7-p10@tactical | max_h_att | 2.032e+05 | 20.5 | 2.032e+05 | 3.36 | FAIL |
| f5 | S7-p10@tactical | max_h_att | 7.097e+05 | 20.5 | 7.097e+05 | 3.36 | FAIL |
| f6 | S7-p20@industrial_mems | max_h_att | 207 | 24 | 183 | 3.42 | FAIL |
| f6 | S7-p20@tactical | max_h_att | 397 | 24 | 373 | 3.36 | FAIL |
| f6 | S7-p2@industrial_mems | max_h_att | 5.38 | 5.38 | 0.00212 | 3.42 | PASS |
| f6 | S7-p2@tactical | max_h_att | 5.37 | 5.34 | 0.0251 | 3.36 | PASS |
| f6 | S7-p5@industrial_mems | max_h_att | 18.6 | 18.6 | -0.00714 | 3.42 | PASS |
| f6 | S7-p5@tactical | max_h_att | 18.6 | 18.5 | 0.0703 | 3.36 | PASS |
| f6 | S7-p60@industrial_mems | max_h_att | 247 | 28.6 | 219 | 3.42 | FAIL |
| f6 | S7-p60@tactical | max_h_att | 3.712e+04 | 28.6 | 3.710e+04 | 3.36 | FAIL |

## ANOMALIES (status != ok)

(none)

---

## S10-r1-c0.5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | 15.1 |

## S10-r1-c0.5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 2 | nan | nan | nan | 0 | nan | nan | nan | - | 15.1 |

## S10-r1-c0.73@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | 15.1 |

## S10-r1-c0.73@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 2 | nan | nan | nan | 0 | nan | nan | nan | - | 15.1 |

## S10-r1-c2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | 15.1 |

## S10-r1-c2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.99 | nan | nan | nan | 0 | nan | nan | nan | - | 15.1 |

## S10-r10-c0.5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | 7.58 |

## S10-r10-c0.5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | 7.58 |

## S10-r10-c0.73@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | 7.58 |

## S10-r10-c0.73@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | 7.58 |

## S10-r10-c2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | 7.58 |

## S10-r10-c2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | 7.58 |

## S10-r10@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | 7.58 |

## S10-r10@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | 7.58 |

## S10-r1@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | 15.1 |

## S10-r1@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.99 | nan | nan | nan | 0 | nan | nan | nan | - | 15.1 |

## S10-r2-c0.5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | 12.9 |

## S10-r2-c0.5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | 12.9 |

## S10-r2-c0.73@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | 12.9 |

## S10-r2-c0.73@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | 12.9 |

## S10-r2-c2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | 12.9 |

## S10-r2-c2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | 12.9 |

## S10-r2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | 12.9 |

## S10-r2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | 12.9 |

## S10-r5-c0.5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | 8.23 |

## S10-r5-c0.5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.41 | nan | nan | nan | 0 | nan | nan | nan | - | 8.23 |

## S10-r5-c0.73@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | 8.23 |

## S10-r5-c0.73@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.41 | nan | nan | nan | 0 | nan | nan | nan | - | 8.23 |

## S10-r5-c2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | 8.23 |

## S10-r5-c2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.4 | nan | nan | nan | 0 | nan | nan | nan | - | 8.23 |

## S10-r5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | 8.23 |

## S10-r5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | 1.41 | nan | nan | nan | 0 | nan | nan | nan | - | 8.23 |

## S11@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | 5.920e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | 428 |
| baseline_a | f5 | 3/3 | 461 | nan | nan | nan | 0.443 | nan | nan | nan | - | 22.9 |
| fedqpnt_local | f6 | 3/3 | 5.879e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | 486 |
| fedqpnt_local | f5 | 3/3 | 5.884e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | 486 |
| undefended | f5 | 3/3 | 17.5 | nan | nan | nan | 0.407 | nan | nan | nan | - | 19.3 |

## S11@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | 4.592e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | 428 |
| baseline_a | f5 | 3/3 | 3.81 | nan | nan | nan | 0.373 | nan | nan | nan | - | 20.5 |
| fedqpnt_local | f6 | 3/3 | 4.590e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | 486 |
| fedqpnt_local | f5 | 3/3 | 4.590e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | 486 |
| undefended | f5 | 3/3 | 4.05 | nan | nan | nan | 0.373 | nan | nan | nan | - | 19.3 |

## S12-f20

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt | f6 | 1/1 | 2.29 | - | - | - | 0 | - | - | - | 4.7 | - |
| fedqpnt | f5 | 1/1 | 1.656e+04 | - | - | - | 0.798 | - | - | - | 0 | - |
| fedqpnt_clean | f6 | 1/1 | 2.29 | - | - | - | 0 | - | - | - | 4.7 | - |
| fedqpnt_clean | f5 | 1/1 | 1.656e+04 | - | - | - | 0.798 | - | - | - | 0 | - |

## S12-f40

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt | f6 | 1/1 | 2.29 | - | - | - | 0 | - | - | - | 4.7 | - |
| fedqpnt | f5 | 1/1 | 1.656e+04 | - | - | - | 0.798 | - | - | - | 0 | - |
| fedqpnt_clean | f6 | 1/1 | 2.29 | - | - | - | 0 | - | - | - | 4.7 | - |
| fedqpnt_clean | f5 | 1/1 | 1.656e+04 | - | - | - | 0.798 | - | - | - | 0 | - |

## S13@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 24.7 | 1.33e+03 | 38.4 | 0.875 | 60 | nan | 0.975 | - | 15.1 |
| baseline_a | f5 | 3/3 | nan | 23.3 | 14.3 | 37.6 | 0 | 60 | 147 | 1 | - | 14.6 |
| fedqpnt_local | f6 | 3/3 | nan | 25.2 | 36.4 | 39.1 | 0.867 | 60 | 150 | 0.975 | - | 15.1 |
| fedqpnt_local | f5 | 3/3 | nan | 23.3 | 36.9 | 37.5 | 0.867 | 60 | nan | 0.973 | - | 15.1 |
| undefended | f5 | 3/3 | nan | 23.3 | 14.3 | 37.6 | 0 | 60 | 147 | 1 | - | 14.6 |

## S13@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 24.9 | 238 | 38.8 | 0.875 | 60 | nan | 0.975 | - | 15.1 |
| baseline_a | f5 | 3/3 | nan | 24.6 | 14.6 | 38.5 | 0 | 60 | 150 | 1 | - | 14.6 |
| fedqpnt_local | f6 | 3/3 | nan | 24.9 | 264 | 38.8 | 0.875 | 60 | nan | 0.975 | - | 15.1 |
| fedqpnt_local | f5 | 3/3 | nan | 24.5 | 246 | 38.5 | 0.875 | 60 | nan | 0.975 | - | 15.1 |
| undefended | f5 | 3/3 | nan | 24.6 | 14.6 | 38.5 | 0 | 60 | 150 | 1 | - | 14.6 |

## S14@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 1/1 | 2.53 | nan | nan | nan | 0 | nan | nan | nan | - | 12.1 |

## S14@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 1/1 | 2.53 | nan | nan | nan | 0 | nan | nan | nan | - | 12.1 |

## S15

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt | f6 | 1/1 | 2.3 | 1.74e+03 | 1.103e+04 | - | 0.267 | 1 | - | - | 4.7 | - |
| fedqpnt | f5 | 1/1 | 1.547e+04 | 1.130e+04 | 9.208e+04 | - | 0.838 | 1 | - | - | 0 | - |

## S1@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | 1.54 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| baseline_a | f6 | 3/3 | 1.58 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| baseline_a | f5 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| baseline_b_bin | f6 | 3/3 | 1.57 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| baseline_b_cont | f6 | 3/3 | 1.58 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| bprime | f6 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| fedqpnt_local | f6 | 3/3 | 1.58 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| fedqpnt_local | f5 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| fixed_trust | f6 | 3/3 | 1.6 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| undefended | f6 | 3/3 | 1.6 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| undefended | f5 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |

## S1@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| baseline_a | f6 | 3/3 | 1.68 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| baseline_a | f5 | 3/3 | 1.71 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| baseline_b_bin | f6 | 3/3 | 1.66 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| baseline_b_cont | f6 | 3/3 | 1.61 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| bprime | f6 | 3/3 | 1.62 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| fedqpnt_local | f6 | 3/3 | 1.61 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| fedqpnt_local | f5 | 3/3 | 1.64 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| fixed_trust | f6 | 3/3 | 1.71 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| undefended | f6 | 3/3 | 1.71 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |
| undefended | f5 | 3/3 | 1.74 | nan | nan | nan | 0 | nan | nan | nan | - | 12.8 |

## S2-DM@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 1.95e+03 | 2.8e+03 | 5.09e+03 | 0.897 | 1 | 50.8 | 0.0572 | - | 878 |
| baseline_a | f6 | 3/3 | nan | 834 | 172 | 2.08e+03 | 0.00934 | 1 | 6.8 | 0.00333 | - | 280 |
| baseline_a | f5 | 3/3 | nan | 1.176e+04 | 3.22e+03 | 3.109e+04 | 0.00934 | 1 | 25.8 | 0.00333 | - | 280 |
| baseline_b_bin | f6 | 3/3 | nan | 2.32e+03 | 3.03e+03 | 4.35e+03 | 0.016 | 1 | nan | 0.0532 | - | 7.66e+03 |
| baseline_b_cont | f6 | 3/3 | nan | 884 | 1.18e+03 | 2.19e+03 | 0.887 | 1 | 50.8 | 0.0572 | - | 878 |
| bprime | f6 | 3/3 | nan | 1.23e+03 | 5.14e+03 | 4.38e+03 | 0.897 | 1 | 9.8 | 0.0237 | - | 762 |
| fedqpnt_local | f6 | 3/3 | nan | 884 | 1.18e+03 | 2.19e+03 | 0.887 | 1 | 50.8 | 0.0572 | - | 878 |
| fedqpnt_local | f5 | 3/3 | nan | 1.155e+04 | 1.095e+05 | 3.056e+04 | 0.9 | 1 | nan | 0.0572 | - | 878 |
| fixed_trust | f6 | 3/3 | nan | 2.35e+03 | 3.42e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | 7.66e+03 |
| undefended | f6 | 3/3 | nan | 2.37e+03 | 1.68e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | 7.66e+03 |
| undefended | f5 | 3/3 | nan | 2.37e+03 | 1.68e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | 7.66e+03 |

## S2-DM@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 904 | 1.33e+03 | 2.38e+03 | 0.887 | 1 | 65 | 0.0572 | - | 878 |
| baseline_a | f6 | 3/3 | nan | 1.79e+03 | 487 | 4.71e+03 | 0.00934 | 1 | 5.8 | 0.00333 | - | 280 |
| baseline_a | f5 | 3/3 | nan | 2.37e+03 | 643 | 6.23e+03 | 0.00934 | 1 | 11.8 | 0.00333 | - | 280 |
| baseline_b_bin | f6 | 3/3 | nan | 2.37e+03 | 3.25e+03 | 4.35e+03 | 0.016 | 1 | nan | 0.0532 | - | 7.66e+03 |
| baseline_b_cont | f6 | 3/3 | nan | 1.68e+03 | 1.584e+04 | 4.43e+03 | 0.9 | 1 | 50.8 | 0.0572 | - | 878 |
| bprime | f6 | 3/3 | nan | 1.72e+03 | 1.107e+04 | 4.53e+03 | 0.9 | 1 | 10.8 | 0.0237 | - | 762 |
| fedqpnt_local | f6 | 3/3 | nan | 1.68e+03 | 1.584e+04 | 4.43e+03 | 0.9 | 1 | 50.8 | 0.0572 | - | 878 |
| fedqpnt_local | f5 | 3/3 | nan | 2.26e+03 | 2.126e+04 | 5.95e+03 | 0.9 | 1 | 50.8 | 0.0572 | - | 878 |
| fixed_trust | f6 | 3/3 | nan | 2.37e+03 | 3.72e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | 7.66e+03 |
| undefended | f6 | 3/3 | nan | 2.37e+03 | 1.7e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | 7.66e+03 |
| undefended | f5 | 3/3 | nan | 2.37e+03 | 1.7e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | 7.66e+03 |

## S2-high@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 2.05e+03 | 2.85e+03 | 5.32e+03 | 0.896 | 1 | 49 | 0.057 | - | 333 |
| baseline_a | f6 | 3/3 | nan | 1.48e+03 | 1.38 | 3.89e+03 | 0 | 3 | 10 | 0.0331 | - | 428 |
| baseline_a | f5 | 3/3 | nan | 5.07e+03 | 6.76 | 1.308e+04 | 0 | 3 | 15 | 0.0331 | - | 426 |
| baseline_b_bin | f6 | 3/3 | nan | 379 | 300 | 708 | 0.0134 | 21 | 221 | 0.116 | - | 12.8 |
| baseline_b_cont | f6 | 3/3 | nan | 985 | 1.27e+03 | 2.43e+03 | 0.886 | 1 | 49 | 0.057 | - | 333 |
| bprime | f6 | 3/3 | nan | 380 | 1.38e+03 | 708 | 0.899 | 302 | 245 | 0.999 | - | 195 |
| fedqpnt_local | f6 | 3/3 | nan | 985 | 1.27e+03 | 2.43e+03 | 0.886 | 1 | 49 | 0.057 | - | 333 |
| fedqpnt_local | f5 | 3/3 | nan | 1.116e+04 | 1.036e+05 | 2.957e+04 | 0.899 | 1 | nan | 0.057 | - | 333 |
| fixed_trust | f6 | 3/3 | nan | 380 | 408 | 708 | 0 | 3 | nan | 1 | - | 12.9 |
| undefended | f6 | 3/3 | nan | 380 | 272 | 708 | 0 | 3 | nan | 1 | - | 12.9 |
| undefended | f5 | 3/3 | nan | 380 | 272 | 708 | 0 | 3 | nan | 1 | - | 12.9 |

## S2-high@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 945 | 1.35e+03 | 2.48e+03 | 0.886 | 1 | 63.7 | 0.057 | - | 333 |
| baseline_a | f6 | 3/3 | nan | 1.2e+03 | 1.38 | 3.05e+03 | 0 | 3 | 11 | 0.0331 | - | 428 |
| baseline_a | f5 | 3/3 | nan | 1.55e+03 | 1.45 | 3.96e+03 | 0 | 3 | 11 | 0.0331 | - | 428 |
| baseline_b_bin | f6 | 3/3 | nan | 371 | 300 | 703 | 0.0134 | 21 | 238 | 0.116 | - | 12.7 |
| baseline_b_cont | f6 | 3/3 | nan | 1.68e+03 | 1.557e+04 | 4.42e+03 | 0.899 | 1 | 49 | 0.057 | - | 333 |
| bprime | f6 | 3/3 | nan | 380 | 1.07e+03 | 708 | 0.899 | 302 | nan | 0.999 | - | 195 |
| fedqpnt_local | f6 | 3/3 | nan | 1.68e+03 | 1.557e+04 | 4.42e+03 | 0.899 | 1 | 49 | 0.057 | - | 333 |
| fedqpnt_local | f5 | 3/3 | nan | 2.25e+03 | 2.083e+04 | 5.91e+03 | 0.899 | 1 | 49 | 0.057 | - | 333 |
| fixed_trust | f6 | 3/3 | nan | 380 | 477 | 708 | 0 | 3 | nan | 1 | - | 12.9 |
| undefended | f6 | 3/3 | nan | 380 | 274 | 708 | 0 | 3 | nan | 1 | - | 12.9 |
| undefended | f5 | 3/3 | nan | 380 | 274 | 708 | 0 | 3 | nan | 1 | - | 12.9 |

## S2-low@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 2.01e+03 | 2.81e+03 | 5.24e+03 | 0.896 | 1 | 49 | 0.057 | - | 333 |
| baseline_a | f6 | 3/3 | nan | 629 | 69 | 1.66e+03 | 0.00336 | 1 | 7 | 0.0132 | - | 484 |
| baseline_a | f5 | 3/3 | nan | 5.64e+03 | 9.21 | 1.451e+04 | 0 | 1 | 16 | 0.0132 | - | 478 |
| baseline_b_bin | f6 | 3/3 | nan | 127 | 90.9 | 237 | 0.0201 | 16 | 176 | 0.1 | - | 12.2 |
| baseline_b_cont | f6 | 3/3 | nan | 930 | 1.21e+03 | 2.3e+03 | 0.886 | 1 | 49 | 0.057 | - | 333 |
| bprime | f6 | 3/3 | nan | 127 | 403 | 237 | 0.674 | 302 | 204 | 0.999 | - | 127 |
| fedqpnt_local | f6 | 3/3 | nan | 930 | 1.21e+03 | 2.3e+03 | 0.886 | 1 | 49 | 0.057 | - | 333 |
| fedqpnt_local | f5 | 3/3 | nan | 1.161e+04 | 1.080e+05 | 3.071e+04 | 0.899 | 1 | nan | 0.057 | - | 333 |
| fixed_trust | f6 | 3/3 | nan | 127 | 110 | 237 | 0.00336 | 1 | nan | 1 | - | 12.3 |
| undefended | f6 | 3/3 | nan | 127 | 92.2 | 237 | 0.00336 | 1 | nan | 1 | - | 12.3 |
| undefended | f5 | 3/3 | nan | 127 | 92.2 | 237 | 0.00336 | 1 | nan | 1 | - | 12.3 |

## S2-low@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 1.02e+03 | 1.44e+03 | 2.66e+03 | 0.886 | 1 | 63.5 | 0.057 | - | 333 |
| baseline_a | f6 | 3/3 | nan | 910 | 142 | 2.31e+03 | 0.00336 | 1 | 2 | 0.0132 | - | 484 |
| baseline_a | f5 | 3/3 | nan | 1.4e+03 | 218 | 3.56e+03 | 0.00336 | 1 | 2 | 0.0132 | - | 484 |
| baseline_b_bin | f6 | 3/3 | nan | 126 | 90.6 | 237 | 0.0201 | 16 | 198 | 0.1 | - | 12.2 |
| baseline_b_cont | f6 | 3/3 | nan | 1.76e+03 | 1.626e+04 | 4.62e+03 | 0.899 | 1 | 49 | 0.057 | - | 333 |
| bprime | f6 | 3/3 | nan | 127 | 367 | 237 | 0.899 | 302 | nan | 0.999 | - | 143 |
| fedqpnt_local | f6 | 3/3 | nan | 1.76e+03 | 1.626e+04 | 4.62e+03 | 0.899 | 1 | 49 | 0.057 | - | 333 |
| fedqpnt_local | f5 | 3/3 | nan | 2.33e+03 | 2.155e+04 | 6.13e+03 | 0.899 | 1 | 49 | 0.057 | - | 333 |
| fixed_trust | f6 | 3/3 | nan | 127 | 117 | 238 | 0.00336 | 1 | nan | 1 | - | 12.3 |
| undefended | f6 | 3/3 | nan | 127 | 92.9 | 238 | 0.00336 | 1 | nan | 1 | - | 12.3 |
| undefended | f5 | 3/3 | nan | 127 | 92.9 | 238 | 0.00336 | 1 | nan | 1 | - | 12.3 |

## S2-med@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 2.03e+03 | 2.83e+03 | 5.27e+03 | 0.896 | 1 | 49 | 0.057 | - | 333 |
| baseline_a | f6 | 3/3 | nan | 1.09e+03 | 1.33 | 2.94e+03 | 0 | 3 | 7 | 0.0265 | - | 415 |
| baseline_a | f5 | 3/3 | nan | 5.35e+03 | 7.93 | 1.378e+04 | 0 | 3 | 17 | 0.0265 | - | 413 |
| baseline_b_bin | f6 | 3/3 | nan | 253 | 181 | 473 | 0.0134 | 19 | 194 | 0.11 | - | 12.7 |
| baseline_b_cont | f6 | 3/3 | nan | 954 | 1.24e+03 | 2.36e+03 | 0.886 | 1 | 49 | 0.057 | - | 333 |
| bprime | f6 | 3/3 | nan | 253 | 1.02e+03 | 473 | 0.899 | 302 | 219 | 0.999 | - | 195 |
| fedqpnt_local | f6 | 3/3 | nan | 954 | 1.24e+03 | 2.36e+03 | 0.886 | 1 | 49 | 0.057 | - | 333 |
| fedqpnt_local | f5 | 3/3 | nan | 1.142e+04 | 1.062e+05 | 3.023e+04 | 0.899 | 1 | nan | 0.057 | - | 333 |
| fixed_trust | f6 | 3/3 | nan | 254 | 252 | 473 | 0 | 3 | nan | 1 | - | 12.9 |
| undefended | f6 | 3/3 | nan | 254 | 181 | 473 | 0 | 3 | nan | 1 | - | 12.9 |
| undefended | f5 | 3/3 | nan | 253 | 181 | 473 | 0 | 3 | nan | 1 | - | 12.9 |

## S2-med@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 987 | 1.4e+03 | 2.58e+03 | 0.886 | 1 | 63.6 | 0.057 | - | 333 |
| baseline_a | f6 | 3/3 | nan | 935 | 1.36 | 2.37e+03 | 0 | 3 | 7 | 0.0265 | - | 415 |
| baseline_a | f5 | 3/3 | nan | 1.39e+03 | 1.41 | 3.53e+03 | 0 | 3 | 8 | 0.0265 | - | 415 |
| baseline_b_bin | f6 | 3/3 | nan | 248 | 180 | 469 | 0.0134 | 19 | 223 | 0.11 | - | 12.7 |
| baseline_b_cont | f6 | 3/3 | nan | 1.72e+03 | 1.597e+04 | 4.53e+03 | 0.899 | 1 | 49 | 0.057 | - | 333 |
| bprime | f6 | 3/3 | nan | 253 | 718 | 472 | 0.899 | 302 | nan | 0.999 | - | 195 |
| fedqpnt_local | f6 | 3/3 | nan | 1.72e+03 | 1.597e+04 | 4.53e+03 | 0.899 | 1 | 49 | 0.057 | - | 333 |
| fedqpnt_local | f5 | 3/3 | nan | 2.3e+03 | 2.125e+04 | 6.04e+03 | 0.899 | 1 | 49 | 0.057 | - | 333 |
| fixed_trust | f6 | 3/3 | nan | 253 | 287 | 473 | 0 | 3 | nan | 1 | - | 12.9 |
| undefended | f6 | 3/3 | nan | 253 | 182 | 473 | 0 | 3 | nan | 1 | - | 12.9 |
| undefended | f5 | 3/3 | nan | 253 | 182 | 473 | 0 | 3 | nan | 1 | - | 12.9 |

## S3@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 25.3 | 3.9 | 55.2 | 0 | 62 | 7.5 | 0.972 | - | 30.2 |
| baseline_a | f6 | 3/3 | nan | 16.9 | 2.47 | 51.5 | 0 | 62 | 1 | 1 | - | 30 |
| baseline_a | f5 | 3/3 | nan | 172 | 5.14 | 421 | 0 | 62 | 35.7 | 1 | - | 30 |
| baseline_b_bin | f6 | 3/3 | nan | 16.9 | 2.46 | 51.6 | 0 | 62 | 1 | 1 | - | 30 |
| baseline_b_cont | f6 | 3/3 | nan | 16.8 | 2.51 | 51.5 | 0 | 62 | 1 | 0.972 | - | 30.2 |
| bprime | f6 | 3/3 | nan | 17.6 | 2.44 | 53.3 | 0 | 62 | 1 | 0.972 | - | 30.1 |
| fedqpnt_local | f6 | 3/3 | nan | 16.8 | 2.51 | 51.5 | 0 | 62 | 1 | 0.972 | - | 30.2 |
| fedqpnt_local | f5 | 3/3 | nan | 172 | 91 | 419 | 0.857 | 62 | nan | 0.972 | - | 30.2 |
| fixed_trust | f6 | 3/3 | nan | 17 | 2.49 | 51.7 | 0 | 62 | 1 | 1 | - | 30 |
| undefended | f6 | 3/3 | nan | 17 | 2.49 | 51.7 | 0 | 62 | 1 | 1 | - | 30 |
| undefended | f5 | 3/3 | nan | 172 | 4.01 | 421 | 0 | 62 | 38.2 | 1 | - | 30 |

## S3@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 12.7 | 3.15 | 33.1 | 0 | 62 | 40.4 | 0.972 | - | 30.2 |
| baseline_a | f6 | 3/3 | nan | 26.4 | 3.13 | 65.1 | 0 | 62 | 31.5 | 1 | - | 30 |
| baseline_a | f5 | 3/3 | nan | 35.8 | 3.47 | 87.1 | 0 | 62 | 41.7 | 1 | - | 30 |
| baseline_b_bin | f6 | 3/3 | nan | 26.3 | 3.12 | 64.8 | 0 | 62 | 32 | 1 | - | 30 |
| baseline_b_cont | f6 | 3/3 | nan | 26.3 | 3.28 | 64.8 | 0 | 62 | 31 | 0.972 | - | 30.2 |
| bprime | f6 | 3/3 | nan | 27 | 3.34 | 66.6 | 0 | 62 | 33.5 | 0.972 | - | 30.1 |
| fedqpnt_local | f6 | 3/3 | nan | 26.3 | 3.28 | 64.8 | 0 | 62 | 31 | 0.972 | - | 30.2 |
| fedqpnt_local | f5 | 3/3 | nan | 35.5 | 3.7 | 86.4 | 0 | 62 | 41.5 | 0.972 | - | 30.2 |
| fixed_trust | f6 | 3/3 | nan | 26.5 | 3.14 | 65.5 | 0 | 62 | 32.3 | 1 | - | 30 |
| undefended | f6 | 3/3 | nan | 26.5 | 3.14 | 65.5 | 0 | 62 | 32.3 | 1 | - | 30 |
| undefended | f5 | 3/3 | nan | 35.9 | 3.49 | 87.5 | 0 | 62 | 42.1 | 1 | - | 30 |

## S4@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 1.02e+03 | 3.52e+03 | 2.74e+03 | 0.804 | 42 | 83.4 | 0.206 | - | 352 |
| baseline_a | f6 | 3/3 | nan | 428 | 86.6 | 1.22e+03 | 0.00633 | 77 | 9.43 | 0.312 | - | 125 |
| baseline_a | f5 | 3/3 | nan | 479 | 83.4 | 1.4e+03 | 0.00633 | 75 | 13 | 0.308 | - | 187 |
| baseline_b_bin | f6 | 3/3 | nan | 136 | 166 | 290 | 0.038 | 82 | nan | 0.37 | - | 19.3 |
| baseline_b_cont | f6 | 3/3 | nan | 501 | 1.5e+03 | 1.24e+03 | 0.804 | 42 | 80 | 0.206 | - | 352 |
| bprime | f6 | 3/3 | nan | 137 | 402 | 291 | 0.81 | 242 | nan | 0.974 | - | 161 |
| fedqpnt_local | f6 | 3/3 | nan | 501 | 1.5e+03 | 1.24e+03 | 0.804 | 42 | 80 | 0.206 | - | 352 |
| fedqpnt_local | f5 | 3/3 | nan | 6.2e+03 | 3.634e+04 | 1.624e+04 | 0.81 | 42 | nan | 0.206 | - | 352 |
| fixed_trust | f6 | 3/3 | nan | 137 | 210 | 291 | 0.00633 | 77 | nan | 0.998 | - | 19.3 |
| undefended | f6 | 3/3 | nan | 137 | 161 | 291 | 0.00633 | 77 | nan | 0.998 | - | 19.3 |
| undefended | f5 | 3/3 | nan | 140 | 161 | 290 | 0.00633 | 75 | nan | 0.998 | - | 19.3 |

## S4@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 570 | 1.9e+03 | 1.48e+03 | 0.804 | 42 | 98.6 | 0.206 | - | 352 |
| baseline_a | f6 | 3/3 | nan | 260 | 38.8 | 711 | 0.00633 | 77 | 99 | 0.312 | - | 125 |
| baseline_a | f5 | 3/3 | nan | 244 | 50.8 | 664 | 0.00633 | 77 | 99 | 0.312 | - | 125 |
| baseline_b_bin | f6 | 3/3 | nan | 137 | 169 | 290 | 0.038 | 82 | nan | 0.37 | - | 19.3 |
| baseline_b_cont | f6 | 3/3 | nan | 951 | 5.48e+03 | 2.48e+03 | 0.81 | 42 | 95.4 | 0.206 | - | 352 |
| bprime | f6 | 3/3 | nan | 137 | 379 | 291 | 0.81 | 242 | nan | 0.974 | - | 161 |
| fedqpnt_local | f6 | 3/3 | nan | 951 | 5.48e+03 | 2.48e+03 | 0.81 | 42 | 95.4 | 0.206 | - | 352 |
| fedqpnt_local | f5 | 3/3 | nan | 1.26e+03 | 7.21e+03 | 3.27e+03 | 0.81 | 42 | 80 | 0.206 | - | 352 |
| fixed_trust | f6 | 3/3 | nan | 137 | 230 | 291 | 0.00633 | 77 | nan | 0.998 | - | 19.3 |
| undefended | f6 | 3/3 | nan | 137 | 162 | 291 | 0.00633 | 77 | nan | 0.998 | - | 19.3 |
| undefended | f5 | 3/3 | nan | 137 | 162 | 291 | 0.00633 | 77 | nan | 0.998 | - | 19.3 |

## S5

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f6 | 1/1 | 2.1 | - | - | - | 0 | - | - | - | 2.5 | - |
| baseline_a | f5 | 1/1 | 2.28 | - | - | - | 0.00183 | - | - | - | 0 | - |
| fedqpnt | f6 | 1/1 | 2.09 | - | - | - | 0 | - | - | - | 2.5 | - |
| fedqpnt | f5 | 1/1 | 1.190e+04 | - | - | - | 0.741 | - | - | - | 0 | - |
| fedqpnt_nofault | f6 | 1/1 | 2.29 | - | - | - | 0 | - | - | - | 4.7 | - |
| fedqpnt_nofault | f5 | 1/1 | 1.656e+04 | - | - | - | 0.798 | - | - | - | 0 | - |

## S6-coast@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f6 | 3/3 | 1.49 | 160 | 2.16 | 423 | 0 | 182 | 3 | 1 | - | 172 |
| abl_minus_quantum | f5 | 3/3 | 1.57 | 195 | 2.17 | 513 | 0 | 182 | 3.84 | 1 | - | 172 |
| baseline_a | f5 | 3/3 | 2.05 | 188 | 2.15 | 483 | 0 | 182 | 1 | 1 | - | 172 |
| fedqpnt_local | f6 | 3/3 | 1.6 | 188 | 2.14 | 484 | 0 | 182 | 1 | 1 | - | 172 |
| fedqpnt_local | f5 | 3/3 | 2.07 | 189 | 2.14 | 484 | 0 | 182 | 1 | 1 | - | 172 |
| undefended | f5 | 3/3 | 2.07 | 188 | 2.15 | 483 | 0 | 182 | 1 | 1 | - | 172 |

## S6-coast@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f6 | 3/3 | 1.53 | 55.1 | 2.02 | 124 | 0 | 182 | 4 | 1 | - | 172 |
| abl_minus_quantum | f5 | 3/3 | 1.54 | 54 | 2.02 | 121 | 0 | 182 | 4 | 1 | - | 172 |
| baseline_a | f5 | 3/3 | 1.73 | 46.1 | 1.95 | 98.8 | 0 | 182 | 2 | 1 | - | 172 |
| fedqpnt_local | f6 | 3/3 | 1.63 | 45.2 | 1.99 | 97.2 | 0 | 182 | 3 | 1 | - | 172 |
| fedqpnt_local | f5 | 3/3 | 1.66 | 45.6 | 1.99 | 98.1 | 0 | 182 | 3 | 1 | - | 172 |
| undefended | f5 | 3/3 | 1.76 | 46.1 | 1.92 | 99.8 | 0 | 182 | 2 | 1 | - | 172 |

## S6@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f6 | 3/3 | 2 | 1.565e+04 | 2.143e+04 | 3.938e+04 | 0.542 | 1 | 114 | 0.0548 | - | 2.9e+03 |
| abl_minus_quantum | f5 | 3/3 | 2.21 | 1.920e+04 | 3.959e+04 | 5.541e+04 | 0.547 | 1 | 79 | 0.0548 | - | 2.9e+03 |
| baseline_a | f5 | 3/3 | 2.81 | 1.091e+04 | 191 | 2.901e+04 | 0.00167 | 2 | 0 | 0.00554 | - | 2.62e+03 |
| fedqpnt_local | f6 | 3/3 | 2.07 | 1.590e+04 | 2.130e+04 | 3.934e+04 | 0.542 | 1 | 114 | 0.0548 | - | 2.9e+03 |
| fedqpnt_local | f5 | 3/3 | 2.85 | 1.600e+04 | 2.140e+04 | 3.954e+04 | 0.542 | 1 | 114 | 0.0548 | - | 2.9e+03 |
| undefended | f6 | 3/3 | 2.07 | 438 | 266 | 777 | 0 | 2 | 293 | 1 | - | 9.96 |
| undefended | f5 | 3/3 | 2.82 | 438 | 266 | 777 | 0 | 2 | 298 | 1 | - | 9.96 |

## S6@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f6 | 3/3 | 2 | 2.76e+03 | 4.43e+03 | 7.72e+03 | 0.483 | 1 | 79 | 0.0548 | - | 2.9e+03 |
| abl_minus_quantum | f5 | 3/3 | 2.03 | 2.94e+03 | 4.72e+03 | 8.25e+03 | 0.542 | 1 | 79 | 0.0548 | - | 2.9e+03 |
| baseline_a | f5 | 3/3 | 2.14 | 1.24e+03 | 2.36 | 3.33e+03 | 0 | 2 | 0 | 0.00554 | - | 2.62e+03 |
| fedqpnt_local | f6 | 3/3 | 2.02 | 2.61e+03 | 4.05e+03 | 7.04e+03 | 0.542 | 1 | 79 | 0.0548 | - | 2.9e+03 |
| fedqpnt_local | f5 | 3/3 | 2.07 | 2.66e+03 | 4.1e+03 | 7.14e+03 | 0.542 | 1 | 79 | 0.0548 | - | 2.9e+03 |
| undefended | f6 | 3/3 | 2.1 | 438 | 266 | 777 | 0 | 2 | 301 | 1 | - | 9.96 |
| undefended | f5 | 3/3 | 2.16 | 438 | 266 | 777 | 0 | 2 | 299 | 1 | - | 9.96 |

## S7-p10@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 9.44e+03 | 17.7 | 4.593e+04 | 0.963 | 5 | 73.3 | 0.0628 | - | 13.3 |
| baseline_a | f5 | 3/3 | nan | 15.4 | 7.06 | 20.3 | 0 | 3.48e+03 | 68 | 1 | - | 13.3 |
| fedqpnt_local | f6 | 3/3 | nan | 32.5 | 22.7 | 183 | 0.956 | 5 | nan | 0.066 | - | 13.3 |
| fedqpnt_local | f5 | 3/3 | nan | 2.521e+06 | 3.946e+06 | 3.835e+06 | 0.984 | 5 | nan | 0.0555 | - | 16 |
| undefended | f6 | 3/3 | nan | 15.4 | 7.06 | 20.3 | 0 | 3.48e+03 | 68 | 1 | - | 13.3 |
| undefended | f5 | 3/3 | nan | 15.4 | 7.06 | 20.3 | 0 | 3.48e+03 | 68 | 1 | - | 13.3 |

## S7-p10@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 395 | 22.7 | 3.08e+03 | 0.953 | 5 | nan | 0.0683 | - | 13.3 |
| baseline_a | f5 | 3/3 | nan | 15.4 | 7.31 | 20.6 | 0 | 3.48e+03 | 67.6 | 1 | - | 13.3 |
| fedqpnt_local | f6 | 3/3 | nan | 44.5 | 52.5 | 447 | 0.94 | 5 | nan | 0.0756 | - | 13.3 |
| fedqpnt_local | f5 | 3/3 | nan | 5.108e+05 | 8.596e+05 | 8.507e+05 | 0.984 | 5 | nan | 0.0569 | - | 13.3 |
| undefended | f6 | 3/3 | nan | 15.4 | 7.26 | 20.5 | 0 | 3.48e+03 | 68 | 1 | - | 13.3 |
| undefended | f5 | 3/3 | nan | 15.4 | 7.26 | 20.5 | 0 | 3.48e+03 | 68 | 1 | - | 13.3 |

## S7-p20@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | nan | 46 | 27.7 | 158 | 0.983 | 10 | nan | 0.109 | - | 13.4 |
| undefended | f6 | 3/3 | nan | 18.2 | 9.02 | 23.8 | 0 | 3.47e+03 | 83.5 | 1 | - | 13.3 |

## S7-p20@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | nan | 33.9 | 14.4 | 114 | 0.969 | 10 | 80.5 | 0.0704 | - | 13.4 |
| undefended | f6 | 3/3 | nan | 18.1 | 9.19 | 24 | 0 | 3.47e+03 | 73.7 | 1 | - | 13.3 |

## S7-p2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | nan | 2.5 | 2.08 | 5.32 | 0 | 3.48e+03 | 0 | 0.947 | - | 13.3 |
| undefended | f6 | 3/3 | nan | 2.49 | 2.18 | 5.31 | 0.00108 | 2.88e+03 | 0 | 1 | - | 13.3 |

## S7-p2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | nan | 2.52 | 2.03 | 5.19 | 0 | 3.48e+03 | 0 | 0.948 | - | 13.3 |
| undefended | f6 | 3/3 | nan | 2.56 | 2.56 | 5.18 | 0.00108 | 2.88e+03 | 0 | 1 | - | 13.3 |

## S7-p5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | nan | 13.8 | 5.6 | 18.5 | 0 | 3.48e+03 | 53.5 | 0.943 | - | 13.4 |
| undefended | f6 | 3/3 | nan | 13.7 | 5.8 | 18.5 | 0 | 3.48e+03 | 54.5 | 1 | - | 13.4 |

## S7-p5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | nan | 13.8 | 5.56 | 18.8 | 0 | 3.48e+03 | 52 | 0.943 | - | 13.4 |
| undefended | f6 | 3/3 | nan | 13.7 | 6.01 | 18.8 | 0 | 3.48e+03 | 53.4 | 1 | - | 13.4 |

## S7-p60@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | nan | 43.3 | 19.3 | 300 | 0.968 | 30 | nan | 0.144 | - | 13.3 |
| undefended | f6 | 3/3 | nan | 19.9 | 10.8 | 28.4 | 0 | 3.45e+03 | 99 | 1 | - | 13.2 |

## S7-p60@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f6 | 3/3 | nan | 236 | 47.3 | 1.24e+03 | 0.969 | 30 | nan | 0.117 | - | 13.3 |
| undefended | f6 | 3/3 | nan | 19.9 | 10.9 | 28.6 | 0 | 3.45e+03 | 98 | 1 | - | 13.2 |

## S8

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_b_cont | f6 | 1/1 | 2.28 | - | - | - | 0 | - | - | - | 5 | - |
| baseline_b_cont | f5 | 1/1 | 1.148e+04 | - | - | - | 0.735 | - | - | - | 0 | - |
| fedqpnt | f6 | 1/1 | 2.28 | - | - | - | 0 | - | - | - | 4.8 | - |
| fedqpnt | f5 | 1/1 | 1.148e+04 | - | - | - | 0.735 | - | - | - | 0 | - |

## S9

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | rmse_t_ns |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt | f6 | 1/1 | 2.28 | - | - | - | 0 | - | - | - | 4.8 | - |
| fedqpnt | f5 | 1/1 | 1.148e+04 | - | - | - | 0.735 | - | - | - | 0 | - |
| fedqpnt_noloss | f6 | 1/1 | 2.28 | - | - | - | 0 | - | - | - | 5 | - |
| fedqpnt_noloss | f5 | 1/1 | 1.148e+04 | - | - | - | 0.735 | - | - | - | 0 | - |
