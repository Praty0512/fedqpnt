# Mini-matrix COMPARE (f7, f6, f5; tuning seeds; medians over seeds; units m, s, ns)

'nan' = undefined for all seeds (no such window), '-' = not run in that root. Current = f7.

## KEY cells (fedqpnt_local / fedqpnt; undefended and baseline_a from the current root)

| rid | grade | metric | f7 | f6 | f5 | undefended | baseline_a |
|---|---|---|---|---|---|---|---|
| S1 | industrial_mems | rmse_h_pre | 1.58 | 1.58 | 2.04 | 1.6 | 1.58 |
| S1 | industrial_mems | fpr | 0 | 0 | 0 | 0 | 0 |
| S1 | tactical | rmse_h_pre | 1.61 | 1.61 | 1.64 | 1.71 | 1.68 |
| S1 | tactical | fpr | 0 | 0 | 0 | 0 | 0 |
| S2-low | industrial_mems | rmse_h_att | 931 | 930 | 1.161e+04 | 127 | 629 |
| S2-low | industrial_mems | rmse_h_post | 1.21e+03 | 1.21e+03 | 1.080e+05 | 92.2 | 69.1 |
| S2-low | industrial_mems | max_h_att | 2.3e+03 | 2.3e+03 | 3.071e+04 | 237 | 1.66e+03 |
| S2-low | industrial_mems | fpr | 0.164 | 0.886 | 0.899 | 0.00336 | 0.00336 |
| S2-low | tactical | rmse_h_att | 1.76e+03 | 1.76e+03 | 2.33e+03 | 127 | 910 |
| S2-low | tactical | rmse_h_post | 2.52e+03 | 1.626e+04 | 2.155e+04 | 92.9 | 142 |
| S2-low | tactical | max_h_att | 4.62e+03 | 4.62e+03 | 6.13e+03 | 238 | 2.31e+03 |
| S2-low | tactical | fpr | 0.164 | 0.899 | 0.899 | 0.00336 | 0.00336 |
| S2-med | industrial_mems | rmse_h_att | 954 | 954 | 1.142e+04 | 254 | 1.09e+03 |
| S2-med | industrial_mems | rmse_h_post | 1.23e+03 | 1.24e+03 | 1.062e+05 | 181 | 1.49 |
| S2-med | industrial_mems | max_h_att | 2.36e+03 | 2.36e+03 | 3.023e+04 | 473 | 2.94e+03 |
| S2-med | industrial_mems | fpr | 0.164 | 0.886 | 0.899 | 0 | 0 |
| S2-med | tactical | rmse_h_att | 1.72e+03 | 1.72e+03 | 2.3e+03 | 253 | 935 |
| S2-med | tactical | rmse_h_post | 2.47e+03 | 1.597e+04 | 2.125e+04 | 182 | 1.4 |
| S2-med | tactical | max_h_att | 4.53e+03 | 4.53e+03 | 6.04e+03 | 473 | 2.37e+03 |
| S2-med | tactical | fpr | 0.164 | 0.899 | 0.899 | 0 | 0 |
| S2-high | industrial_mems | rmse_h_att | 985 | 985 | 1.116e+04 | 380 | 1.48e+03 |
| S2-high | industrial_mems | rmse_h_post | 1.27e+03 | 1.27e+03 | 1.036e+05 | 272 | 1.49 |
| S2-high | industrial_mems | max_h_att | 2.43e+03 | 2.43e+03 | 2.957e+04 | 708 | 3.89e+03 |
| S2-high | industrial_mems | fpr | 0.164 | 0.886 | 0.899 | 0 | 0 |
| S2-high | tactical | rmse_h_att | 1.68e+03 | 1.68e+03 | 2.25e+03 | 380 | 1.2e+03 |
| S2-high | tactical | rmse_h_post | 2.41e+03 | 1.557e+04 | 2.083e+04 | 274 | 1.45 |
| S2-high | tactical | max_h_att | 4.42e+03 | 4.42e+03 | 5.91e+03 | 708 | 3.05e+03 |
| S2-high | tactical | fpr | 0.164 | 0.899 | 0.899 | 0 | 0 |
| S2-DM | industrial_mems | rmse_h_att | 885 | 884 | 1.155e+04 | 2.37e+03 | 834 |
| S2-DM | industrial_mems | rmse_h_post | 1.17e+03 | 1.18e+03 | 1.095e+05 | 1.68e+03 | 172 |
| S2-DM | industrial_mems | max_h_att | 2.19e+03 | 2.19e+03 | 3.056e+04 | 4.37e+03 | 2.08e+03 |
| S2-DM | industrial_mems | fpr | 0.169 | 0.887 | 0.9 | 0.00267 | 0.00934 |
| S2-DM | tactical | rmse_h_att | 1.68e+03 | 1.68e+03 | 2.26e+03 | 2.37e+03 | 1.79e+03 |
| S2-DM | tactical | rmse_h_post | 2.48e+03 | 1.584e+04 | 2.126e+04 | 1.7e+03 | 487 |
| S2-DM | tactical | max_h_att | 4.43e+03 | 4.43e+03 | 5.95e+03 | 4.37e+03 | 4.71e+03 |
| S2-DM | tactical | fpr | 0.169 | 0.9 | 0.9 | 0.00267 | 0.00934 |
| S3 | industrial_mems | rmse_h_att | 16.8 | 16.8 | 172 | 17 | 16.9 |
| S3 | industrial_mems | rmse_h_post | 2.55 | 2.51 | 91 | 2.51 | 2.5 |
| S3 | industrial_mems | max_h_att | 51.5 | 51.5 | 419 | 51.8 | 51.5 |
| S3 | industrial_mems | fpr | 0 | 0 | 0.857 | 0 | 0 |
| S3 | tactical | rmse_h_att | 26.3 | 26.3 | 35.5 | 26.5 | 26.4 |
| S3 | tactical | rmse_h_post | 3.28 | 3.28 | 3.7 | 3.14 | 3.13 |
| S3 | tactical | max_h_att | 64.8 | 64.8 | 86.4 | 65.5 | 65.1 |
| S3 | tactical | fpr | 0 | 0 | 0 | 0 | 0 |
| S4 | industrial_mems | rmse_h_att | 501 | 501 | 6.2e+03 | 137 | 417 |
| S4 | industrial_mems | rmse_h_post | 1.12e+03 | 1.5e+03 | 3.634e+04 | 161 | 79.8 |
| S4 | industrial_mems | max_h_att | 1.24e+03 | 1.24e+03 | 1.624e+04 | 291 | 1.18e+03 |
| S4 | industrial_mems | fpr | 0.506 | 0.804 | 0.81 | 0.00633 | 0.00633 |
| S4 | tactical | rmse_h_att | 951 | 951 | 1.26e+03 | 137 | 260 |
| S4 | tactical | rmse_h_post | 1.04e+03 | 5.48e+03 | 7.21e+03 | 162 | 38.7 |
| S4 | tactical | max_h_att | 2.48e+03 | 2.48e+03 | 3.27e+03 | 291 | 712 |
| S4 | tactical | fpr | 0.506 | 0.81 | 0.81 | 0.00633 | 0.00633 |
| S6 | industrial_mems | rmse_h_pre | 2.07 | 2.07 | 2.85 | 2.07 | - |
| S6 | industrial_mems | rmse_h_att | 1.590e+04 | 1.590e+04 | 1.600e+04 | 438 | - |
| S6 | industrial_mems | rmse_h_post | 2.130e+04 | 2.130e+04 | 2.140e+04 | 266 | - |
| S6 | industrial_mems | max_h_att | 3.934e+04 | 3.934e+04 | 3.954e+04 | 777 | - |
| S6 | industrial_mems | fpr | 0.132 | 0.542 | 0.542 | 0 | - |
| S6 | tactical | rmse_h_pre | 2.02 | 2.02 | 2.07 | 2.1 | - |
| S6 | tactical | rmse_h_att | 2.61e+03 | 2.61e+03 | 2.66e+03 | 438 | - |
| S6 | tactical | rmse_h_post | 4.05e+03 | 4.05e+03 | 4.1e+03 | 266 | - |
| S6 | tactical | max_h_att | 7.04e+03 | 7.04e+03 | 7.14e+03 | 777 | - |
| S6 | tactical | fpr | 0.132 | 0.542 | 0.542 | 0 | - |
| S6-coast | industrial_mems | rmse_h_pre | 1.6 | 1.6 | 2.07 | - | - |
| S6-coast | industrial_mems | rmse_h_att | 188 | 188 | 189 | - | - |
| S6-coast | industrial_mems | rmse_h_post | 2.15 | 2.14 | 2.14 | - | - |
| S6-coast | industrial_mems | max_h_att | 484 | 484 | 484 | - | - |
| S6-coast | industrial_mems | fpr | 0 | 0 | 0 | - | - |
| S6-coast | tactical | rmse_h_pre | 1.63 | 1.63 | 1.66 | - | - |
| S6-coast | tactical | rmse_h_att | 45.2 | 45.2 | 45.6 | - | - |
| S6-coast | tactical | rmse_h_post | 1.99 | 1.99 | 1.99 | - | - |
| S6-coast | tactical | max_h_att | 97.2 | 97.2 | 98.1 | - | - |
| S6-coast | tactical | fpr | 0 | 0 | 0 | - | - |
| S7-p10 | industrial_mems | rmse_h_att | 29.8 | 32.5 | 2.521e+06 | 15.4 | - |
| S7-p10 | industrial_mems | rmse_h_post | 24.9 | 22.7 | 3.946e+06 | 7.06 | - |
| S7-p10 | industrial_mems | max_h_att | 129 | 183 | 3.835e+06 | 20.3 | - |
| S7-p10 | industrial_mems | fpr | 0.839 | 0.956 | 0.984 | 0 | - |
| S7-p10 | tactical | rmse_h_att | 47.6 | 44.5 | 5.108e+05 | 15.4 | - |
| S7-p10 | tactical | rmse_h_post | 17.6 | 52.5 | 8.596e+05 | 7.26 | - |
| S7-p10 | tactical | max_h_att | 447 | 447 | 8.507e+05 | 20.5 | - |
| S7-p10 | tactical | fpr | 0.86 | 0.94 | 0.984 | 0 | - |
| S7-p60 | industrial_mems | rmse_h_att | 30.5 | 43.3 | 39.8 | 19.9 | - |
| S7-p60 | industrial_mems | rmse_h_post | 8.57 | 19.3 | 19.3 | 10.8 | - |
| S7-p60 | industrial_mems | max_h_att | 207 | 300 | 208 | 28.4 | - |
| S7-p60 | industrial_mems | fpr | 0.645 | 0.968 | 0.953 | 0 | - |
| S7-p60 | tactical | rmse_h_att | 237 | 236 | 237 | 19.9 | - |
| S7-p60 | tactical | rmse_h_post | 64.2 | 47.3 | 47.3 | 10.9 | - |
| S7-p60 | tactical | max_h_att | 1.21e+03 | 1.24e+03 | 1.24e+03 | 28.6 | - |
| S7-p60 | tactical | fpr | 0.93 | 0.969 | 0.975 | 0 | - |
| S11 | industrial_mems | rmse_h_pre | 5.879e+04 | 5.879e+04 | 5.884e+04 | - | - |
| S11 | industrial_mems | fpr | 0.993 | 0.993 | 0.993 | - | - |
| S11 | tactical | rmse_h_pre | 4.590e+04 | 4.590e+04 | 4.590e+04 | - | - |
| S11 | tactical | fpr | 0.993 | 0.993 | 0.993 | - | - |
| S13 | industrial_mems | rmse_h_att | 25.2 | 25.2 | 23.3 | - | - |
| S13 | industrial_mems | rmse_h_post | 19.4 | 36.4 | 36.9 | - | - |
| S13 | industrial_mems | max_h_att | 39.1 | 39.1 | 37.5 | - | - |
| S13 | industrial_mems | fpr | 0.292 | 0.867 | 0.867 | - | - |
| S13 | tactical | rmse_h_att | 24.9 | 24.9 | 24.5 | - | - |
| S13 | tactical | rmse_h_post | 264 | 264 | 246 | - | - |
| S13 | tactical | max_h_att | 38.8 | 38.8 | 38.5 | - | - |
| S13 | tactical | fpr | 0.875 | 0.875 | 0.875 | - | - |
| S14 | industrial_mems | rmse_h_pre | 2.53 | 2.53 | - | - | - |
| S14 | industrial_mems | fpr | 0 | 0 | - | - | - |
| S14 | tactical | rmse_h_pre | 2.53 | 2.53 | - | - | - |
| S14 | tactical | fpr | 0 | 0 | - | - | - |

## FLAGS: defended worse than undefended / baseline (median, strict >) in f7

- f7 S2-DM@industrial_mems: fedqpnt_local rmse_h_att 885 > baseline_a 834 (x1.1)
- f7 S2-DM@industrial_mems: fedqpnt_local rmse_h_post 1.17e+03 > baseline_a 172 (x6.8)
- f7 S2-DM@tactical: fedqpnt_local rmse_h_post 2.48e+03 > undefended 1.7e+03 (x1.5)
- f7 S2-DM@tactical: fedqpnt_local rmse_h_post 2.48e+03 > baseline_a 487 (x5.1)
- f7 S2-high@industrial_mems: fedqpnt_local rmse_h_att 985 > undefended 380 (x2.6)
- f7 S2-high@industrial_mems: fedqpnt_local rmse_h_post 1.27e+03 > undefended 272 (x4.7)
- f7 S2-high@industrial_mems: fedqpnt_local rmse_h_post 1.27e+03 > baseline_a 1.49 (x853.2)
- f7 S2-high@tactical: fedqpnt_local rmse_h_att 1.68e+03 > undefended 380 (x4.4)
- f7 S2-high@tactical: fedqpnt_local rmse_h_post 2.41e+03 > undefended 274 (x8.8)
- f7 S2-high@tactical: fedqpnt_local rmse_h_att 1.68e+03 > baseline_a 1.2e+03 (x1.4)
- f7 S2-high@tactical: fedqpnt_local rmse_h_post 2.41e+03 > baseline_a 1.45 (x1660.4)
- f7 S2-low@industrial_mems: fedqpnt_local rmse_h_att 931 > undefended 127 (x7.3)
- f7 S2-low@industrial_mems: fedqpnt_local rmse_h_post 1.21e+03 > undefended 92.2 (x13.1)
- f7 S2-low@industrial_mems: fedqpnt_local rmse_h_att 931 > baseline_a 629 (x1.5)
- f7 S2-low@industrial_mems: fedqpnt_local rmse_h_post 1.21e+03 > baseline_a 69.1 (x17.5)
- f7 S2-low@tactical: fedqpnt_local rmse_h_att 1.76e+03 > undefended 127 (x13.8)
- f7 S2-low@tactical: fedqpnt_local rmse_h_post 2.52e+03 > undefended 92.9 (x27.1)
- f7 S2-low@tactical: fedqpnt_local rmse_h_att 1.76e+03 > baseline_a 910 (x1.9)
- f7 S2-low@tactical: fedqpnt_local rmse_h_post 2.52e+03 > baseline_a 142 (x17.8)
- f7 S2-med@industrial_mems: fedqpnt_local rmse_h_att 954 > undefended 254 (x3.8)
- f7 S2-med@industrial_mems: fedqpnt_local rmse_h_post 1.23e+03 > undefended 181 (x6.8)
- f7 S2-med@industrial_mems: fedqpnt_local rmse_h_post 1.23e+03 > baseline_a 1.49 (x830.2)
- f7 S2-med@tactical: fedqpnt_local rmse_h_att 1.72e+03 > undefended 253 (x6.8)
- f7 S2-med@tactical: fedqpnt_local rmse_h_post 2.47e+03 > undefended 182 (x13.6)
- f7 S2-med@tactical: fedqpnt_local rmse_h_att 1.72e+03 > baseline_a 935 (x1.8)
- f7 S2-med@tactical: fedqpnt_local rmse_h_post 2.47e+03 > baseline_a 1.4 (x1766.7)
- f7 S4@industrial_mems: fedqpnt_local rmse_h_att 501 > undefended 137 (x3.7)
- f7 S4@industrial_mems: fedqpnt_local rmse_h_post 1.12e+03 > undefended 161 (x7.0)
- f7 S4@industrial_mems: fedqpnt_local rmse_h_att 501 > baseline_a 417 (x1.2)
- f7 S4@industrial_mems: fedqpnt_local rmse_h_post 1.12e+03 > baseline_a 79.8 (x14.1)
- f7 S4@tactical: fedqpnt_local rmse_h_att 951 > undefended 137 (x6.9)
- f7 S4@tactical: fedqpnt_local rmse_h_post 1.04e+03 > undefended 162 (x6.4)
- f7 S4@tactical: fedqpnt_local rmse_h_att 951 > baseline_a 260 (x3.7)
- f7 S4@tactical: fedqpnt_local rmse_h_post 1.04e+03 > baseline_a 38.7 (x26.9)
- f7 S6@industrial_mems: fedqpnt_local rmse_h_att 1.590e+04 > undefended 438 (x36.3)
- f7 S6@industrial_mems: fedqpnt_local rmse_h_post 2.130e+04 > undefended 266 (x80.0)
- f7 S6@tactical: fedqpnt_local rmse_h_att 2.61e+03 > undefended 438 (x6.0)
- f7 S6@tactical: fedqpnt_local rmse_h_post 4.05e+03 > undefended 266 (x15.2)
- f7 S7-p10@industrial_mems: fedqpnt_local rmse_h_att 29.8 > undefended 15.4 (x1.9)
- f7 S7-p10@industrial_mems: fedqpnt_local rmse_h_post 24.9 > undefended 7.06 (x3.5)
- f7 S7-p10@tactical: fedqpnt_local rmse_h_att 47.6 > undefended 15.4 (x3.1)
- f7 S7-p10@tactical: fedqpnt_local rmse_h_post 17.6 > undefended 7.26 (x2.4)
- f7 S7-p20@industrial_mems: fedqpnt_local rmse_h_att 46 > undefended 18.2 (x2.5)
- f7 S7-p20@industrial_mems: fedqpnt_local rmse_h_post 24.8 > undefended 9.02 (x2.8)
- f7 S7-p20@tactical: fedqpnt_local rmse_h_att 50.9 > undefended 18.1 (x2.8)
- f7 S7-p20@tactical: fedqpnt_local rmse_h_post 58.1 > undefended 9.19 (x6.3)
- f7 S7-p60@industrial_mems: fedqpnt_local rmse_h_att 30.5 > undefended 19.9 (x1.5)
- f7 S7-p60@tactical: fedqpnt_local rmse_h_att 237 > undefended 19.9 (x11.9)
- f7 S7-p60@tactical: fedqpnt_local rmse_h_post 64.2 > undefended 10.9 (x5.9)

## M3 safety margin (f7): mean(defended) - mean(undefended) vs 3 sigma_nom

| rid | field | mean def | mean undef | margin | 3sigma_nom | pass |
|---|---|---|---|---|---|---|
| S1@industrial_mems | max_h_pre | 3.25 | 3.26 | -0.0176 | 3.42 | PASS |
| S1@tactical | max_h_pre | 3.23 | 3.26 | -0.0369 | 3.36 | PASS |
| S2-DM@industrial_mems | max_h_att | 3.31e+03 | 4.25e+03 | -945 | 3.42 | PASS |
| S2-DM@tactical | max_h_att | 3.95e+03 | 4.25e+03 | -298 | 3.36 | PASS |
| S2-high@industrial_mems | max_h_att | 3.39e+03 | 708 | 2.68e+03 | 3.42 | FAIL |
| S2-high@tactical | max_h_att | 3.84e+03 | 708 | 3.13e+03 | 3.36 | FAIL |
| S2-low@industrial_mems | max_h_att | 3.46e+03 | 237 | 3.23e+03 | 3.42 | FAIL |
| S2-low@tactical | max_h_att | 4e+03 | 237 | 3.76e+03 | 3.36 | FAIL |
| S2-med@industrial_mems | max_h_att | 3.43e+03 | 472 | 2.96e+03 | 3.42 | FAIL |
| S2-med@tactical | max_h_att | 3.93e+03 | 472 | 3.46e+03 | 3.36 | FAIL |
| S3@industrial_mems | max_h_att | 49.4 | 48.6 | 0.753 | 3.42 | PASS |
| S3@tactical | max_h_att | 69.7 | 69.6 | 0.131 | 3.36 | PASS |
| S4@industrial_mems | max_h_att | 1.78e+03 | 292 | 1.49e+03 | 3.42 | FAIL |
| S4@tactical | max_h_att | 2.24e+03 | 292 | 1.95e+03 | 3.36 | FAIL |
| S6@industrial_mems | max_h_att | 3.474e+04 | 776 | 3.396e+04 | 3.42 | FAIL |
| S6@tactical | max_h_att | 6.99e+03 | 776 | 6.22e+03 | 3.36 | FAIL |
| S7-p10@industrial_mems | max_h_att | 207 | 20.5 | 187 | 3.42 | FAIL |
| S7-p10@tactical | max_h_att | 737 | 20.5 | 716 | 3.36 | FAIL |
| S7-p20@industrial_mems | max_h_att | 217 | 24 | 193 | 3.42 | FAIL |
| S7-p20@tactical | max_h_att | 1.846e+04 | 24 | 1.843e+04 | 3.36 | FAIL |
| S7-p2@industrial_mems | max_h_att | 5.38 | 5.38 | 0.00113 | 3.42 | PASS |
| S7-p2@tactical | max_h_att | 5.37 | 5.34 | 0.0251 | 3.36 | PASS |
| S7-p5@industrial_mems | max_h_att | 18.6 | 18.6 | -0.00713 | 3.42 | PASS |
| S7-p5@tactical | max_h_att | 18.6 | 18.5 | 0.0703 | 3.36 | PASS |
| S7-p60@industrial_mems | max_h_att | 197 | 28.6 | 168 | 3.42 | FAIL |
| S7-p60@tactical | max_h_att | 1.353e+04 | 28.6 | 1.350e+04 | 3.36 | FAIL |

## ANOMALY scan (f7, defended method, per seed)

- LOCKOUT fpr=0.993 on clean S11@industrial_mems fedqpnt_local seed 530
- KM-SCALE rmse_h_pre=16485 m on short (300 s) clean S11@industrial_mems fedqpnt_local seed 530
- KM-SCALE max_h_pre=48970 m on short (300 s) clean S11@industrial_mems fedqpnt_local seed 530
- LOCKOUT fpr=0.990 on clean S11@industrial_mems fedqpnt_local seed 531
- KM-SCALE rmse_h_pre=121194 m on short (300 s) clean S11@industrial_mems fedqpnt_local seed 531
- KM-SCALE max_h_pre=256673 m on short (300 s) clean S11@industrial_mems fedqpnt_local seed 531
- LOCKOUT fpr=0.993 on clean S11@industrial_mems fedqpnt_local seed 532
- KM-SCALE rmse_h_pre=58793 m on short (300 s) clean S11@industrial_mems fedqpnt_local seed 532
- KM-SCALE max_h_pre=109278 m on short (300 s) clean S11@industrial_mems fedqpnt_local seed 532
- LOCKOUT fpr=0.993 on clean S11@tactical fedqpnt_local seed 530
- KM-SCALE rmse_h_pre=6669 m on short (300 s) clean S11@tactical fedqpnt_local seed 530
- KM-SCALE max_h_pre=18818 m on short (300 s) clean S11@tactical fedqpnt_local seed 530
- LOCKOUT fpr=0.990 on clean S11@tactical fedqpnt_local seed 531
- KM-SCALE rmse_h_pre=45896 m on short (300 s) clean S11@tactical fedqpnt_local seed 531
- KM-SCALE max_h_pre=109868 m on short (300 s) clean S11@tactical fedqpnt_local seed 531
- LOCKOUT fpr=0.993 on clean S11@tactical fedqpnt_local seed 532
- KM-SCALE rmse_h_pre=54595 m on short (300 s) clean S11@tactical fedqpnt_local seed 532
- KM-SCALE max_h_pre=130746 m on short (300 s) clean S11@tactical fedqpnt_local seed 532

## STATUS != ok

(none)

---

## S10-r1-c0.5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r1-c0.5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 2 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r1-c0.73@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r1-c0.73@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 2 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r1-c2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r1-c2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.99 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.99 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10-c0.5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10-c0.5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10-c0.73@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10-c0.73@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10-c2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10-c2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r10@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r1@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r1@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.99 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.99 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2-c0.5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2-c0.5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2-c0.73@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2-c0.73@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2-c2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2-c2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5-c0.5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5-c0.5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.41 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.41 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5-c0.73@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5-c0.73@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.41 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.41 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5-c2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5-c2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.4 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.4 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.43 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S10-r5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | 1.4 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.41 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S11@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | 5.920e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | - |
| baseline_a | f5 | 3/3 | 461 | nan | nan | nan | 0.443 | nan | nan | nan | - | - |
| fedqpnt_local | f7 | 3/3 | 5.879e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 5.879e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | - |
| fedqpnt_local | f5 | 3/3 | 5.884e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | - |
| undefended | f5 | 3/3 | 17.5 | nan | nan | nan | 0.407 | nan | nan | nan | - | - |

## S11@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | 4.592e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | - |
| baseline_a | f5 | 3/3 | 3.81 | nan | nan | nan | 0.373 | nan | nan | nan | - | - |
| fedqpnt_local | f7 | 3/3 | 4.590e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 4.590e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | - |
| fedqpnt_local | f5 | 3/3 | 4.590e+04 | nan | nan | nan | 0.993 | nan | nan | nan | - | - |
| undefended | f5 | 3/3 | 4.05 | nan | nan | nan | 0.373 | nan | nan | nan | - | - |

## S12-f20

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt | f7 | 2/2 | 16.1 | - | - | - | 0.327 | - | - | - | 4.75 | - |
| fedqpnt | f6 | 1/1 | 2.29 | - | - | - | 0 | - | - | - | 4.7 | - |
| fedqpnt | f5 | 1/1 | 1.656e+04 | - | - | - | 0.798 | - | - | - | 0 | - |
| fedqpnt_clean | f7 | 2/2 | 16.1 | - | - | - | 0.327 | - | - | - | 4.75 | - |
| fedqpnt_clean | f6 | 1/1 | 2.29 | - | - | - | 0 | - | - | - | 4.7 | - |
| fedqpnt_clean | f5 | 1/1 | 1.656e+04 | - | - | - | 0.798 | - | - | - | 0 | - |

## S12-f40

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt | f7 | 2/2 | 16.1 | - | - | - | 0.327 | - | - | - | 4.75 | - |
| fedqpnt | f6 | 1/1 | 2.29 | - | - | - | 0 | - | - | - | 4.7 | - |
| fedqpnt | f5 | 1/1 | 1.656e+04 | - | - | - | 0.798 | - | - | - | 0 | - |
| fedqpnt_clean | f7 | 2/2 | 16.1 | - | - | - | 0.327 | - | - | - | 4.75 | - |
| fedqpnt_clean | f6 | 1/1 | 2.29 | - | - | - | 0 | - | - | - | 4.7 | - |
| fedqpnt_clean | f5 | 1/1 | 1.656e+04 | - | - | - | 0.798 | - | - | - | 0 | - |

## S13@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 24.7 | 1.33e+03 | 38.4 | 0.875 | 60 | nan | 0.975 | - | - |
| baseline_a | f5 | 3/3 | nan | 23.3 | 14.3 | 37.6 | 0 | 60 | 147 | 1 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 25.2 | 19.4 | 39.1 | 0.292 | 60 | 104 | 0.975 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 25.2 | 36.4 | 39.1 | 0.867 | 60 | 150 | 0.975 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 23.3 | 36.9 | 37.5 | 0.867 | 60 | nan | 0.973 | - | - |
| undefended | f5 | 3/3 | nan | 23.3 | 14.3 | 37.6 | 0 | 60 | 147 | 1 | - | - |

## S13@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 24.9 | 238 | 38.8 | 0.875 | 60 | nan | 0.975 | - | - |
| baseline_a | f5 | 3/3 | nan | 24.6 | 14.6 | 38.5 | 0 | 60 | 150 | 1 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 24.9 | 264 | 38.8 | 0.875 | 60 | nan | 0.975 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 24.9 | 264 | 38.8 | 0.875 | 60 | nan | 0.975 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 24.5 | 246 | 38.5 | 0.875 | 60 | nan | 0.975 | - | - |
| undefended | f5 | 3/3 | nan | 24.6 | 14.6 | 38.5 | 0 | 60 | 150 | 1 | - | - |

## S14@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 1/1 | 2.53 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 1/1 | 2.53 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S14@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 1/1 | 2.53 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 1/1 | 2.53 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S15

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt | f7 | 2/2 | 15.1 | 1.32e+03 | 2.01e+03 | - | 0.379 | 1 | - | - | 4.75 | 0.923 |
| fedqpnt | f6 | 1/1 | 2.3 | 1.74e+03 | 1.103e+04 | - | 0.267 | 1 | - | - | 4.7 | 0.822 |
| fedqpnt | f5 | 1/1 | 1.547e+04 | 1.130e+04 | 9.208e+04 | - | 0.838 | 1 | - | - | 0 | 0.688 |

## S1@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | 1.54 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_a | f7 | 3/3 | 1.58 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_a | f6 | 3/3 | 1.58 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_a | f5 | 3/3 | 2.02 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_bin | f7 | 3/3 | 1.57 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_bin | f6 | 3/3 | 1.57 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_cont | f7 | 3/3 | 1.58 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_cont | f6 | 3/3 | 1.58 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| bprime | f7 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| bprime | f6 | 3/3 | 1.56 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f7 | 3/3 | 1.58 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.58 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f5 | 3/3 | 2.04 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fixed_trust | f7 | 3/3 | 1.6 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fixed_trust | f6 | 3/3 | 1.6 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| undefended | f7 | 3/3 | 1.6 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| undefended | f6 | 3/3 | 1.6 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| undefended | f5 | 3/3 | 2.03 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S1@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | 1.52 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_a | f7 | 3/3 | 1.68 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_a | f6 | 3/3 | 1.68 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_a | f5 | 3/3 | 1.71 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_bin | f7 | 3/3 | 1.66 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_bin | f6 | 3/3 | 1.66 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_cont | f7 | 3/3 | 1.61 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| baseline_b_cont | f6 | 3/3 | 1.61 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| bprime | f7 | 3/3 | 1.62 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| bprime | f6 | 3/3 | 1.62 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f7 | 3/3 | 1.61 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f6 | 3/3 | 1.61 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fedqpnt_local | f5 | 3/3 | 1.64 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fixed_trust | f7 | 3/3 | 1.71 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| fixed_trust | f6 | 3/3 | 1.71 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| undefended | f7 | 3/3 | 1.71 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| undefended | f6 | 3/3 | 1.71 | nan | nan | nan | 0 | nan | nan | nan | - | - |
| undefended | f5 | 3/3 | 1.74 | nan | nan | nan | 0 | nan | nan | nan | - | - |

## S2-DM@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 1.95e+03 | 2.8e+03 | 5.09e+03 | 0.897 | 1 | 50.8 | 0.0572 | - | - |
| baseline_a | f7 | 3/3 | nan | 834 | 172 | 2.08e+03 | 0.00934 | 1 | 2.8 | 0.00333 | - | - |
| baseline_a | f6 | 3/3 | nan | 834 | 172 | 2.08e+03 | 0.00934 | 1 | 6.8 | 0.00333 | - | - |
| baseline_a | f5 | 3/3 | nan | 1.176e+04 | 3.22e+03 | 3.109e+04 | 0.00934 | 1 | 25.8 | 0.00333 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 2.32e+03 | 3.03e+03 | 4.35e+03 | 0.016 | 1 | nan | 0.0532 | - | - |
| baseline_b_bin | f6 | 3/3 | nan | 2.32e+03 | 3.03e+03 | 4.35e+03 | 0.016 | 1 | nan | 0.0532 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 885 | 1.17e+03 | 2.19e+03 | 0.169 | 1 | 50.8 | 0.0572 | - | - |
| baseline_b_cont | f6 | 3/3 | nan | 884 | 1.18e+03 | 2.19e+03 | 0.887 | 1 | 50.8 | 0.0572 | - | - |
| bprime | f7 | 3/3 | nan | 1.66e+03 | 4.97e+03 | 4.39e+03 | 0.897 | 1 | 11.8 | 0.0328 | - | - |
| bprime | f6 | 3/3 | nan | 1.23e+03 | 5.14e+03 | 4.38e+03 | 0.897 | 1 | 9.8 | 0.0237 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 885 | 1.17e+03 | 2.19e+03 | 0.169 | 1 | 50.8 | 0.0572 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 884 | 1.18e+03 | 2.19e+03 | 0.887 | 1 | 50.8 | 0.0572 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 1.155e+04 | 1.095e+05 | 3.056e+04 | 0.9 | 1 | nan | 0.0572 | - | - |
| fixed_trust | f7 | 3/3 | nan | 2.35e+03 | 3.42e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | - |
| fixed_trust | f6 | 3/3 | nan | 2.35e+03 | 3.42e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 2.37e+03 | 1.68e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | - |
| undefended | f6 | 3/3 | nan | 2.37e+03 | 1.68e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | - |
| undefended | f5 | 3/3 | nan | 2.37e+03 | 1.68e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | - |

## S2-DM@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 904 | 1.33e+03 | 2.38e+03 | 0.887 | 1 | 65 | 0.0572 | - | - |
| baseline_a | f7 | 3/3 | nan | 1.79e+03 | 487 | 4.71e+03 | 0.00934 | 1 | 2.8 | 0.00333 | - | - |
| baseline_a | f6 | 3/3 | nan | 1.79e+03 | 487 | 4.71e+03 | 0.00934 | 1 | 5.8 | 0.00333 | - | - |
| baseline_a | f5 | 3/3 | nan | 2.37e+03 | 643 | 6.23e+03 | 0.00934 | 1 | 11.8 | 0.00333 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 2.37e+03 | 3.25e+03 | 4.35e+03 | 0.016 | 1 | nan | 0.0532 | - | - |
| baseline_b_bin | f6 | 3/3 | nan | 2.37e+03 | 3.25e+03 | 4.35e+03 | 0.016 | 1 | nan | 0.0532 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 1.68e+03 | 2.48e+03 | 4.43e+03 | 0.169 | 1 | 53.8 | 0.0572 | - | - |
| baseline_b_cont | f6 | 3/3 | nan | 1.68e+03 | 1.584e+04 | 4.43e+03 | 0.9 | 1 | 50.8 | 0.0572 | - | - |
| bprime | f7 | 3/3 | nan | 1.72e+03 | 1.210e+04 | 3.96e+03 | 0.9 | 1 | 11.4 | 0.0237 | - | - |
| bprime | f6 | 3/3 | nan | 1.72e+03 | 1.107e+04 | 4.53e+03 | 0.9 | 1 | 10.8 | 0.0237 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 1.68e+03 | 2.48e+03 | 4.43e+03 | 0.169 | 1 | 53.8 | 0.0572 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 1.68e+03 | 1.584e+04 | 4.43e+03 | 0.9 | 1 | 50.8 | 0.0572 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 2.26e+03 | 2.126e+04 | 5.95e+03 | 0.9 | 1 | 50.8 | 0.0572 | - | - |
| fixed_trust | f7 | 3/3 | nan | 2.37e+03 | 3.73e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | - |
| fixed_trust | f6 | 3/3 | nan | 2.37e+03 | 3.72e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 2.37e+03 | 1.7e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | - |
| undefended | f6 | 3/3 | nan | 2.37e+03 | 1.7e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | - |
| undefended | f5 | 3/3 | nan | 2.37e+03 | 1.7e+03 | 4.37e+03 | 0.00267 | 1 | nan | 1 | - | - |

## S2-high@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 2.05e+03 | 2.85e+03 | 5.32e+03 | 0.896 | 1 | 49 | 0.057 | - | - |
| baseline_a | f7 | 3/3 | nan | 1.48e+03 | 1.49 | 3.89e+03 | 0 | 3 | 6 | 0.0331 | - | - |
| baseline_a | f6 | 3/3 | nan | 1.48e+03 | 1.38 | 3.89e+03 | 0 | 3 | 10 | 0.0331 | - | - |
| baseline_a | f5 | 3/3 | nan | 5.07e+03 | 6.76 | 1.308e+04 | 0 | 3 | 15 | 0.0331 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 379 | 300 | 708 | 0.0134 | 21 | 221 | 0.116 | - | - |
| baseline_b_bin | f6 | 3/3 | nan | 379 | 300 | 708 | 0.0134 | 21 | 221 | 0.116 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 985 | 1.27e+03 | 2.43e+03 | 0.164 | 1 | 49 | 0.057 | - | - |
| baseline_b_cont | f6 | 3/3 | nan | 985 | 1.27e+03 | 2.43e+03 | 0.886 | 1 | 49 | 0.057 | - | - |
| bprime | f7 | 3/3 | nan | 380 | 1.38e+03 | 708 | 0.899 | 302 | 245 | 0.999 | - | - |
| bprime | f6 | 3/3 | nan | 380 | 1.38e+03 | 708 | 0.899 | 302 | 245 | 0.999 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 985 | 1.27e+03 | 2.43e+03 | 0.164 | 1 | 49 | 0.057 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 985 | 1.27e+03 | 2.43e+03 | 0.886 | 1 | 49 | 0.057 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 1.116e+04 | 1.036e+05 | 2.957e+04 | 0.899 | 1 | nan | 0.057 | - | - |
| fixed_trust | f7 | 3/3 | nan | 380 | 408 | 708 | 0 | 3 | nan | 1 | - | - |
| fixed_trust | f6 | 3/3 | nan | 380 | 408 | 708 | 0 | 3 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 380 | 272 | 708 | 0 | 3 | nan | 1 | - | - |
| undefended | f6 | 3/3 | nan | 380 | 272 | 708 | 0 | 3 | nan | 1 | - | - |
| undefended | f5 | 3/3 | nan | 380 | 272 | 708 | 0 | 3 | nan | 1 | - | - |

## S2-high@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 945 | 1.35e+03 | 2.48e+03 | 0.886 | 1 | 63.7 | 0.057 | - | - |
| baseline_a | f7 | 3/3 | nan | 1.2e+03 | 1.45 | 3.05e+03 | 0 | 3 | 11 | 0.0331 | - | - |
| baseline_a | f6 | 3/3 | nan | 1.2e+03 | 1.38 | 3.05e+03 | 0 | 3 | 11 | 0.0331 | - | - |
| baseline_a | f5 | 3/3 | nan | 1.55e+03 | 1.45 | 3.96e+03 | 0 | 3 | 11 | 0.0331 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 371 | 300 | 703 | 0.0134 | 21 | 238 | 0.116 | - | - |
| baseline_b_bin | f6 | 3/3 | nan | 371 | 300 | 703 | 0.0134 | 21 | 238 | 0.116 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 1.68e+03 | 2.41e+03 | 4.42e+03 | 0.164 | 1 | 50 | 0.057 | - | - |
| baseline_b_cont | f6 | 3/3 | nan | 1.68e+03 | 1.557e+04 | 4.42e+03 | 0.899 | 1 | 49 | 0.057 | - | - |
| bprime | f7 | 3/3 | nan | 380 | 1.07e+03 | 708 | 0.899 | 302 | nan | 0.999 | - | - |
| bprime | f6 | 3/3 | nan | 380 | 1.07e+03 | 708 | 0.899 | 302 | nan | 0.999 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 1.68e+03 | 2.41e+03 | 4.42e+03 | 0.164 | 1 | 50 | 0.057 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 1.68e+03 | 1.557e+04 | 4.42e+03 | 0.899 | 1 | 49 | 0.057 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 2.25e+03 | 2.083e+04 | 5.91e+03 | 0.899 | 1 | 49 | 0.057 | - | - |
| fixed_trust | f7 | 3/3 | nan | 380 | 477 | 708 | 0 | 3 | nan | 1 | - | - |
| fixed_trust | f6 | 3/3 | nan | 380 | 477 | 708 | 0 | 3 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 380 | 274 | 708 | 0 | 3 | nan | 1 | - | - |
| undefended | f6 | 3/3 | nan | 380 | 274 | 708 | 0 | 3 | nan | 1 | - | - |
| undefended | f5 | 3/3 | nan | 380 | 274 | 708 | 0 | 3 | nan | 1 | - | - |

## S2-low@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 2.01e+03 | 2.81e+03 | 5.24e+03 | 0.896 | 1 | 49 | 0.057 | - | - |
| baseline_a | f7 | 3/3 | nan | 629 | 69.1 | 1.66e+03 | 0.00336 | 1 | 3 | 0.0132 | - | - |
| baseline_a | f6 | 3/3 | nan | 629 | 69 | 1.66e+03 | 0.00336 | 1 | 7 | 0.0132 | - | - |
| baseline_a | f5 | 3/3 | nan | 5.64e+03 | 9.21 | 1.451e+04 | 0 | 1 | 16 | 0.0132 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 127 | 90.9 | 237 | 0.0201 | 16 | 176 | 0.1 | - | - |
| baseline_b_bin | f6 | 3/3 | nan | 127 | 90.9 | 237 | 0.0201 | 16 | 176 | 0.1 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 931 | 1.21e+03 | 2.3e+03 | 0.164 | 1 | 49 | 0.057 | - | - |
| baseline_b_cont | f6 | 3/3 | nan | 930 | 1.21e+03 | 2.3e+03 | 0.886 | 1 | 49 | 0.057 | - | - |
| bprime | f7 | 3/3 | nan | 127 | 403 | 237 | 0.674 | 302 | 204 | 0.999 | - | - |
| bprime | f6 | 3/3 | nan | 127 | 403 | 237 | 0.674 | 302 | 204 | 0.999 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 931 | 1.21e+03 | 2.3e+03 | 0.164 | 1 | 49 | 0.057 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 930 | 1.21e+03 | 2.3e+03 | 0.886 | 1 | 49 | 0.057 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 1.161e+04 | 1.080e+05 | 3.071e+04 | 0.899 | 1 | nan | 0.057 | - | - |
| fixed_trust | f7 | 3/3 | nan | 127 | 110 | 237 | 0.00336 | 1 | nan | 1 | - | - |
| fixed_trust | f6 | 3/3 | nan | 127 | 110 | 237 | 0.00336 | 1 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 127 | 92.2 | 237 | 0.00336 | 1 | nan | 1 | - | - |
| undefended | f6 | 3/3 | nan | 127 | 92.2 | 237 | 0.00336 | 1 | nan | 1 | - | - |
| undefended | f5 | 3/3 | nan | 127 | 92.2 | 237 | 0.00336 | 1 | nan | 1 | - | - |

## S2-low@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 1.02e+03 | 1.44e+03 | 2.66e+03 | 0.886 | 1 | 63.5 | 0.057 | - | - |
| baseline_a | f7 | 3/3 | nan | 910 | 142 | 2.31e+03 | 0.00336 | 1 | 1.39 | 0.0132 | - | - |
| baseline_a | f6 | 3/3 | nan | 910 | 142 | 2.31e+03 | 0.00336 | 1 | 2 | 0.0132 | - | - |
| baseline_a | f5 | 3/3 | nan | 1.4e+03 | 218 | 3.56e+03 | 0.00336 | 1 | 2 | 0.0132 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 126 | 90.6 | 237 | 0.0201 | 16 | 198 | 0.1 | - | - |
| baseline_b_bin | f6 | 3/3 | nan | 126 | 90.6 | 237 | 0.0201 | 16 | 198 | 0.1 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 1.76e+03 | 2.52e+03 | 4.62e+03 | 0.164 | 1 | 52.5 | 0.057 | - | - |
| baseline_b_cont | f6 | 3/3 | nan | 1.76e+03 | 1.626e+04 | 4.62e+03 | 0.899 | 1 | 49 | 0.057 | - | - |
| bprime | f7 | 3/3 | nan | 127 | 367 | 237 | 0.899 | 302 | nan | 0.999 | - | - |
| bprime | f6 | 3/3 | nan | 127 | 367 | 237 | 0.899 | 302 | nan | 0.999 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 1.76e+03 | 2.52e+03 | 4.62e+03 | 0.164 | 1 | 52.5 | 0.057 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 1.76e+03 | 1.626e+04 | 4.62e+03 | 0.899 | 1 | 49 | 0.057 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 2.33e+03 | 2.155e+04 | 6.13e+03 | 0.899 | 1 | 49 | 0.057 | - | - |
| fixed_trust | f7 | 3/3 | nan | 127 | 117 | 238 | 0.00336 | 1 | nan | 1 | - | - |
| fixed_trust | f6 | 3/3 | nan | 127 | 117 | 238 | 0.00336 | 1 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 127 | 92.9 | 238 | 0.00336 | 1 | nan | 1 | - | - |
| undefended | f6 | 3/3 | nan | 127 | 92.9 | 238 | 0.00336 | 1 | nan | 1 | - | - |
| undefended | f5 | 3/3 | nan | 127 | 92.9 | 238 | 0.00336 | 1 | nan | 1 | - | - |

## S2-med@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 2.03e+03 | 2.83e+03 | 5.27e+03 | 0.896 | 1 | 49 | 0.057 | - | - |
| baseline_a | f7 | 3/3 | nan | 1.09e+03 | 1.49 | 2.94e+03 | 0 | 3 | 4 | 0.0265 | - | - |
| baseline_a | f6 | 3/3 | nan | 1.09e+03 | 1.33 | 2.94e+03 | 0 | 3 | 7 | 0.0265 | - | - |
| baseline_a | f5 | 3/3 | nan | 5.35e+03 | 7.93 | 1.378e+04 | 0 | 3 | 17 | 0.0265 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 253 | 181 | 473 | 0.0134 | 19 | 194 | 0.11 | - | - |
| baseline_b_bin | f6 | 3/3 | nan | 253 | 181 | 473 | 0.0134 | 19 | 194 | 0.11 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 954 | 1.23e+03 | 2.36e+03 | 0.164 | 1 | 49 | 0.057 | - | - |
| baseline_b_cont | f6 | 3/3 | nan | 954 | 1.24e+03 | 2.36e+03 | 0.886 | 1 | 49 | 0.057 | - | - |
| bprime | f7 | 3/3 | nan | 253 | 1.02e+03 | 473 | 0.899 | 302 | 219 | 0.999 | - | - |
| bprime | f6 | 3/3 | nan | 253 | 1.02e+03 | 473 | 0.899 | 302 | 219 | 0.999 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 954 | 1.23e+03 | 2.36e+03 | 0.164 | 1 | 49 | 0.057 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 954 | 1.24e+03 | 2.36e+03 | 0.886 | 1 | 49 | 0.057 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 1.142e+04 | 1.062e+05 | 3.023e+04 | 0.899 | 1 | nan | 0.057 | - | - |
| fixed_trust | f7 | 3/3 | nan | 254 | 252 | 473 | 0 | 3 | nan | 1 | - | - |
| fixed_trust | f6 | 3/3 | nan | 254 | 252 | 473 | 0 | 3 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 254 | 181 | 473 | 0 | 3 | nan | 1 | - | - |
| undefended | f6 | 3/3 | nan | 254 | 181 | 473 | 0 | 3 | nan | 1 | - | - |
| undefended | f5 | 3/3 | nan | 253 | 181 | 473 | 0 | 3 | nan | 1 | - | - |

## S2-med@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 987 | 1.4e+03 | 2.58e+03 | 0.886 | 1 | 63.6 | 0.057 | - | - |
| baseline_a | f7 | 3/3 | nan | 935 | 1.4 | 2.37e+03 | 0 | 3 | 5 | 0.0265 | - | - |
| baseline_a | f6 | 3/3 | nan | 935 | 1.36 | 2.37e+03 | 0 | 3 | 7 | 0.0265 | - | - |
| baseline_a | f5 | 3/3 | nan | 1.39e+03 | 1.41 | 3.53e+03 | 0 | 3 | 8 | 0.0265 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 248 | 180 | 469 | 0.0134 | 19 | 223 | 0.11 | - | - |
| baseline_b_bin | f6 | 3/3 | nan | 248 | 180 | 469 | 0.0134 | 19 | 223 | 0.11 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 1.72e+03 | 2.47e+03 | 4.53e+03 | 0.164 | 1 | 51.5 | 0.057 | - | - |
| baseline_b_cont | f6 | 3/3 | nan | 1.72e+03 | 1.597e+04 | 4.53e+03 | 0.899 | 1 | 49 | 0.057 | - | - |
| bprime | f7 | 3/3 | nan | 253 | 718 | 472 | 0.899 | 302 | nan | 0.999 | - | - |
| bprime | f6 | 3/3 | nan | 253 | 718 | 472 | 0.899 | 302 | nan | 0.999 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 1.72e+03 | 2.47e+03 | 4.53e+03 | 0.164 | 1 | 51.5 | 0.057 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 1.72e+03 | 1.597e+04 | 4.53e+03 | 0.899 | 1 | 49 | 0.057 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 2.3e+03 | 2.125e+04 | 6.04e+03 | 0.899 | 1 | 49 | 0.057 | - | - |
| fixed_trust | f7 | 3/3 | nan | 253 | 287 | 473 | 0 | 3 | nan | 1 | - | - |
| fixed_trust | f6 | 3/3 | nan | 253 | 287 | 473 | 0 | 3 | nan | 1 | - | - |
| undefended | f7 | 3/3 | nan | 253 | 182 | 473 | 0 | 3 | nan | 1 | - | - |
| undefended | f6 | 3/3 | nan | 253 | 182 | 473 | 0 | 3 | nan | 1 | - | - |
| undefended | f5 | 3/3 | nan | 253 | 182 | 473 | 0 | 3 | nan | 1 | - | - |

## S3@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 25.3 | 3.9 | 55.2 | 0 | 62 | 7.5 | 0.972 | - | - |
| baseline_a | f7 | 3/3 | nan | 16.9 | 2.5 | 51.5 | 0 | 62 | 13.2 | 1 | - | - |
| baseline_a | f6 | 3/3 | nan | 16.9 | 2.47 | 51.5 | 0 | 62 | 1 | 1 | - | - |
| baseline_a | f5 | 3/3 | nan | 172 | 5.14 | 421 | 0 | 62 | 35.7 | 1 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 16.9 | 2.49 | 51.6 | 0 | 62 | 13.9 | 1 | - | - |
| baseline_b_bin | f6 | 3/3 | nan | 16.9 | 2.46 | 51.6 | 0 | 62 | 1 | 1 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 16.8 | 2.55 | 51.5 | 0 | 62 | 63 | 0.972 | - | - |
| baseline_b_cont | f6 | 3/3 | nan | 16.8 | 2.51 | 51.5 | 0 | 62 | 1 | 0.972 | - | - |
| bprime | f7 | 3/3 | nan | 17.6 | 2.47 | 53.3 | 0 | 62 | 18 | 0.972 | - | - |
| bprime | f6 | 3/3 | nan | 17.6 | 2.44 | 53.3 | 0 | 62 | 1 | 0.972 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 16.8 | 2.55 | 51.5 | 0 | 62 | 63 | 0.972 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 16.8 | 2.51 | 51.5 | 0 | 62 | 1 | 0.972 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 172 | 91 | 419 | 0.857 | 62 | nan | 0.972 | - | - |
| fixed_trust | f7 | 3/3 | nan | 17 | 2.51 | 51.8 | 0 | 62 | 13.4 | 1 | - | - |
| fixed_trust | f6 | 3/3 | nan | 17 | 2.49 | 51.7 | 0 | 62 | 1 | 1 | - | - |
| undefended | f7 | 3/3 | nan | 17 | 2.51 | 51.8 | 0 | 62 | 13.4 | 1 | - | - |
| undefended | f6 | 3/3 | nan | 17 | 2.49 | 51.7 | 0 | 62 | 1 | 1 | - | - |
| undefended | f5 | 3/3 | nan | 172 | 4.01 | 421 | 0 | 62 | 38.2 | 1 | - | - |

## S3@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 12.7 | 3.15 | 33.1 | 0 | 62 | 40.4 | 0.972 | - | - |
| baseline_a | f7 | 3/3 | nan | 26.4 | 3.13 | 65.1 | 0 | 62 | 31.5 | 1 | - | - |
| baseline_a | f6 | 3/3 | nan | 26.4 | 3.13 | 65.1 | 0 | 62 | 31.5 | 1 | - | - |
| baseline_a | f5 | 3/3 | nan | 35.8 | 3.47 | 87.1 | 0 | 62 | 41.7 | 1 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 26.3 | 3.12 | 64.8 | 0 | 62 | 31.7 | 1 | - | - |
| baseline_b_bin | f6 | 3/3 | nan | 26.3 | 3.12 | 64.8 | 0 | 62 | 32 | 1 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 26.3 | 3.28 | 64.8 | 0 | 62 | 31 | 0.972 | - | - |
| baseline_b_cont | f6 | 3/3 | nan | 26.3 | 3.28 | 64.8 | 0 | 62 | 31 | 0.972 | - | - |
| bprime | f7 | 3/3 | nan | 27 | 3.34 | 66.6 | 0 | 62 | 33.5 | 0.972 | - | - |
| bprime | f6 | 3/3 | nan | 27 | 3.34 | 66.6 | 0 | 62 | 33.5 | 0.972 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 26.3 | 3.28 | 64.8 | 0 | 62 | 31 | 0.972 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 26.3 | 3.28 | 64.8 | 0 | 62 | 31 | 0.972 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 35.5 | 3.7 | 86.4 | 0 | 62 | 41.5 | 0.972 | - | - |
| fixed_trust | f7 | 3/3 | nan | 26.5 | 3.14 | 65.5 | 0 | 62 | 32.3 | 1 | - | - |
| fixed_trust | f6 | 3/3 | nan | 26.5 | 3.14 | 65.5 | 0 | 62 | 32.3 | 1 | - | - |
| undefended | f7 | 3/3 | nan | 26.5 | 3.14 | 65.5 | 0 | 62 | 32.3 | 1 | - | - |
| undefended | f6 | 3/3 | nan | 26.5 | 3.14 | 65.5 | 0 | 62 | 32.3 | 1 | - | - |
| undefended | f5 | 3/3 | nan | 35.9 | 3.49 | 87.5 | 0 | 62 | 42.1 | 1 | - | - |

## S4@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 1.02e+03 | 3.52e+03 | 2.74e+03 | 0.804 | 42 | 83.4 | 0.206 | - | - |
| baseline_a | f7 | 3/3 | nan | 417 | 79.8 | 1.18e+03 | 0.00633 | 77 | 9 | 0.312 | - | - |
| baseline_a | f6 | 3/3 | nan | 428 | 86.6 | 1.22e+03 | 0.00633 | 77 | 9.43 | 0.312 | - | - |
| baseline_a | f5 | 3/3 | nan | 479 | 83.4 | 1.4e+03 | 0.00633 | 75 | 13 | 0.308 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 136 | 166 | 290 | 0.038 | 82 | nan | 0.37 | - | - |
| baseline_b_bin | f6 | 3/3 | nan | 136 | 166 | 290 | 0.038 | 82 | nan | 0.37 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 501 | 1.12e+03 | 1.24e+03 | 0.506 | 42 | 80 | 0.206 | - | - |
| baseline_b_cont | f6 | 3/3 | nan | 501 | 1.5e+03 | 1.24e+03 | 0.804 | 42 | 80 | 0.206 | - | - |
| bprime | f7 | 3/3 | nan | 137 | 402 | 291 | 0.81 | 242 | nan | 0.974 | - | - |
| bprime | f6 | 3/3 | nan | 137 | 402 | 291 | 0.81 | 242 | nan | 0.974 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 501 | 1.12e+03 | 1.24e+03 | 0.506 | 42 | 80 | 0.206 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 501 | 1.5e+03 | 1.24e+03 | 0.804 | 42 | 80 | 0.206 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 6.2e+03 | 3.634e+04 | 1.624e+04 | 0.81 | 42 | nan | 0.206 | - | - |
| fixed_trust | f7 | 3/3 | nan | 137 | 210 | 291 | 0.00633 | 77 | nan | 0.998 | - | - |
| fixed_trust | f6 | 3/3 | nan | 137 | 210 | 291 | 0.00633 | 77 | nan | 0.998 | - | - |
| undefended | f7 | 3/3 | nan | 137 | 161 | 291 | 0.00633 | 77 | nan | 0.998 | - | - |
| undefended | f6 | 3/3 | nan | 137 | 161 | 291 | 0.00633 | 77 | nan | 0.998 | - | - |
| undefended | f5 | 3/3 | nan | 140 | 161 | 290 | 0.00633 | 75 | nan | 0.998 | - | - |

## S4@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 570 | 1.9e+03 | 1.48e+03 | 0.804 | 42 | 98.6 | 0.206 | - | - |
| baseline_a | f7 | 3/3 | nan | 260 | 38.7 | 712 | 0.00633 | 77 | 99 | 0.312 | - | - |
| baseline_a | f6 | 3/3 | nan | 260 | 38.8 | 711 | 0.00633 | 77 | 99 | 0.312 | - | - |
| baseline_a | f5 | 3/3 | nan | 244 | 50.8 | 664 | 0.00633 | 77 | 99 | 0.312 | - | - |
| baseline_b_bin | f7 | 3/3 | nan | 137 | 169 | 290 | 0.038 | 82 | nan | 0.37 | - | - |
| baseline_b_bin | f6 | 3/3 | nan | 137 | 169 | 290 | 0.038 | 82 | nan | 0.37 | - | - |
| baseline_b_cont | f7 | 3/3 | nan | 951 | 1.04e+03 | 2.48e+03 | 0.506 | 42 | 45.5 | 0.206 | - | - |
| baseline_b_cont | f6 | 3/3 | nan | 951 | 5.48e+03 | 2.48e+03 | 0.81 | 42 | 95.4 | 0.206 | - | - |
| bprime | f7 | 3/3 | nan | 137 | 379 | 291 | 0.81 | 242 | nan | 0.974 | - | - |
| bprime | f6 | 3/3 | nan | 137 | 379 | 291 | 0.81 | 242 | nan | 0.974 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 951 | 1.04e+03 | 2.48e+03 | 0.506 | 42 | 45.5 | 0.206 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 951 | 5.48e+03 | 2.48e+03 | 0.81 | 42 | 95.4 | 0.206 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 1.26e+03 | 7.21e+03 | 3.27e+03 | 0.81 | 42 | 80 | 0.206 | - | - |
| fixed_trust | f7 | 3/3 | nan | 137 | 230 | 291 | 0.00633 | 77 | nan | 0.998 | - | - |
| fixed_trust | f6 | 3/3 | nan | 137 | 230 | 291 | 0.00633 | 77 | nan | 0.998 | - | - |
| undefended | f7 | 3/3 | nan | 137 | 162 | 291 | 0.00633 | 77 | nan | 0.998 | - | - |
| undefended | f6 | 3/3 | nan | 137 | 162 | 291 | 0.00633 | 77 | nan | 0.998 | - | - |
| undefended | f5 | 3/3 | nan | 137 | 162 | 291 | 0.00633 | 77 | nan | 0.998 | - | - |

## S5

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_a | f7 | 2/2 | 15.7 | - | - | - | 0.312 | - | - | - | 2.6 | - |
| baseline_a | f6 | 1/1 | 2.1 | - | - | - | 0 | - | - | - | 2.5 | - |
| baseline_a | f5 | 1/1 | 2.28 | - | - | - | 0.00183 | - | - | - | 0 | - |
| fedqpnt | f7 | 2/2 | 12.2 | - | - | - | 0.276 | - | - | - | 2.6 | - |
| fedqpnt | f6 | 1/1 | 2.09 | - | - | - | 0 | - | - | - | 2.5 | - |
| fedqpnt | f5 | 1/1 | 1.190e+04 | - | - | - | 0.741 | - | - | - | 0 | - |
| fedqpnt_nofault | f7 | 2/2 | 16.1 | - | - | - | 0.327 | - | - | - | 4.75 | - |
| fedqpnt_nofault | f6 | 1/1 | 2.29 | - | - | - | 0 | - | - | - | 4.7 | - |
| fedqpnt_nofault | f5 | 1/1 | 1.656e+04 | - | - | - | 0.798 | - | - | - | 0 | - |

## S6-coast@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f7 | 3/3 | 1.51 | 158 | 2.17 | 419 | 0 | 182 | 3 | 1 | - | - |
| abl_minus_quantum | f6 | 3/3 | 1.49 | 160 | 2.16 | 423 | 0 | 182 | 3 | 1 | - | - |
| abl_minus_quantum | f5 | 3/3 | 1.57 | 195 | 2.17 | 513 | 0 | 182 | 3.84 | 1 | - | - |
| baseline_a | f5 | 3/3 | 2.05 | 188 | 2.15 | 483 | 0 | 182 | 1 | 1 | - | - |
| fedqpnt_local | f7 | 3/3 | 1.6 | 188 | 2.15 | 484 | 0 | 182 | 1 | 1 | - | - |
| fedqpnt_local | f6 | 3/3 | 1.6 | 188 | 2.14 | 484 | 0 | 182 | 1 | 1 | - | - |
| fedqpnt_local | f5 | 3/3 | 2.07 | 189 | 2.14 | 484 | 0 | 182 | 1 | 1 | - | - |
| undefended | f5 | 3/3 | 2.07 | 188 | 2.15 | 483 | 0 | 182 | 1 | 1 | - | - |

## S6-coast@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f7 | 3/3 | 1.53 | 55.1 | 2.02 | 124 | 0 | 182 | 4 | 1 | - | - |
| abl_minus_quantum | f6 | 3/3 | 1.53 | 55.1 | 2.02 | 124 | 0 | 182 | 4 | 1 | - | - |
| abl_minus_quantum | f5 | 3/3 | 1.54 | 54 | 2.02 | 121 | 0 | 182 | 4 | 1 | - | - |
| baseline_a | f5 | 3/3 | 1.73 | 46.1 | 1.95 | 98.8 | 0 | 182 | 2 | 1 | - | - |
| fedqpnt_local | f7 | 3/3 | 1.63 | 45.2 | 1.99 | 97.2 | 0 | 182 | 3 | 1 | - | - |
| fedqpnt_local | f6 | 3/3 | 1.63 | 45.2 | 1.99 | 97.2 | 0 | 182 | 3 | 1 | - | - |
| fedqpnt_local | f5 | 3/3 | 1.66 | 45.6 | 1.99 | 98.1 | 0 | 182 | 3 | 1 | - | - |
| undefended | f5 | 3/3 | 1.76 | 46.1 | 1.92 | 99.8 | 0 | 182 | 2 | 1 | - | - |

## S6@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f7 | 3/3 | 2 | 1.564e+04 | 2.141e+04 | 3.936e+04 | 0.132 | 1 | 89 | 0.0548 | - | - |
| abl_minus_quantum | f6 | 3/3 | 2 | 1.565e+04 | 2.143e+04 | 3.938e+04 | 0.542 | 1 | 114 | 0.0548 | - | - |
| abl_minus_quantum | f5 | 3/3 | 2.21 | 1.920e+04 | 3.959e+04 | 5.541e+04 | 0.547 | 1 | 79 | 0.0548 | - | - |
| baseline_a | f5 | 3/3 | 2.81 | 1.091e+04 | 191 | 2.901e+04 | 0.00167 | 2 | 0 | 0.00554 | - | - |
| fedqpnt_local | f7 | 3/3 | 2.07 | 1.590e+04 | 2.130e+04 | 3.934e+04 | 0.132 | 1 | 90 | 0.0548 | - | - |
| fedqpnt_local | f6 | 3/3 | 2.07 | 1.590e+04 | 2.130e+04 | 3.934e+04 | 0.542 | 1 | 114 | 0.0548 | - | - |
| fedqpnt_local | f5 | 3/3 | 2.85 | 1.600e+04 | 2.140e+04 | 3.954e+04 | 0.542 | 1 | 114 | 0.0548 | - | - |
| undefended | f7 | 3/3 | 2.07 | 438 | 266 | 777 | 0 | 2 | 293 | 1 | - | - |
| undefended | f6 | 3/3 | 2.07 | 438 | 266 | 777 | 0 | 2 | 293 | 1 | - | - |
| undefended | f5 | 3/3 | 2.82 | 438 | 266 | 777 | 0 | 2 | 298 | 1 | - | - |

## S6@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f7 | 3/3 | 2 | 2.76e+03 | 4.43e+03 | 7.72e+03 | 0.132 | 1 | 79 | 0.0548 | - | - |
| abl_minus_quantum | f6 | 3/3 | 2 | 2.76e+03 | 4.43e+03 | 7.72e+03 | 0.483 | 1 | 79 | 0.0548 | - | - |
| abl_minus_quantum | f5 | 3/3 | 2.03 | 2.94e+03 | 4.72e+03 | 8.25e+03 | 0.542 | 1 | 79 | 0.0548 | - | - |
| baseline_a | f5 | 3/3 | 2.14 | 1.24e+03 | 2.36 | 3.33e+03 | 0 | 2 | 0 | 0.00554 | - | - |
| fedqpnt_local | f7 | 3/3 | 2.02 | 2.61e+03 | 4.05e+03 | 7.04e+03 | 0.132 | 1 | 79 | 0.0548 | - | - |
| fedqpnt_local | f6 | 3/3 | 2.02 | 2.61e+03 | 4.05e+03 | 7.04e+03 | 0.542 | 1 | 79 | 0.0548 | - | - |
| fedqpnt_local | f5 | 3/3 | 2.07 | 2.66e+03 | 4.1e+03 | 7.14e+03 | 0.542 | 1 | 79 | 0.0548 | - | - |
| undefended | f7 | 3/3 | 2.1 | 438 | 266 | 777 | 0 | 2 | 301 | 1 | - | - |
| undefended | f6 | 3/3 | 2.1 | 438 | 266 | 777 | 0 | 2 | 301 | 1 | - | - |
| undefended | f5 | 3/3 | 2.16 | 438 | 266 | 777 | 0 | 2 | 299 | 1 | - | - |

## S7-p10@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 9.44e+03 | 17.7 | 4.593e+04 | 0.963 | 5 | 73.3 | 0.0628 | - | - |
| baseline_a | f5 | 3/3 | nan | 15.4 | 7.06 | 20.3 | 0 | 3.48e+03 | 68 | 1 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 29.8 | 24.9 | 129 | 0.839 | 5 | 49.5 | 0.116 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 32.5 | 22.7 | 183 | 0.956 | 5 | nan | 0.066 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 2.521e+06 | 3.946e+06 | 3.835e+06 | 0.984 | 5 | nan | 0.0555 | - | - |
| undefended | f7 | 3/3 | nan | 15.4 | 7.06 | 20.3 | 0 | 3.48e+03 | 68 | 1 | - | - |
| undefended | f6 | 3/3 | nan | 15.4 | 7.06 | 20.3 | 0 | 3.48e+03 | 68 | 1 | - | - |
| undefended | f5 | 3/3 | nan | 15.4 | 7.06 | 20.3 | 0 | 3.48e+03 | 68 | 1 | - | - |

## S7-p10@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abl_minus_quantum | f5 | 3/3 | nan | 395 | 22.7 | 3.08e+03 | 0.953 | 5 | nan | 0.0683 | - | - |
| baseline_a | f5 | 3/3 | nan | 15.4 | 7.31 | 20.6 | 0 | 3.48e+03 | 67.6 | 1 | - | - |
| fedqpnt_local | f7 | 3/3 | nan | 47.6 | 17.6 | 447 | 0.86 | 5 | 30.5 | 0.108 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 44.5 | 52.5 | 447 | 0.94 | 5 | nan | 0.0756 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 5.108e+05 | 8.596e+05 | 8.507e+05 | 0.984 | 5 | nan | 0.0569 | - | - |
| undefended | f7 | 3/3 | nan | 15.4 | 7.26 | 20.5 | 0 | 3.48e+03 | 68 | 1 | - | - |
| undefended | f6 | 3/3 | nan | 15.4 | 7.26 | 20.5 | 0 | 3.48e+03 | 68 | 1 | - | - |
| undefended | f5 | 3/3 | nan | 15.4 | 7.26 | 20.5 | 0 | 3.48e+03 | 68 | 1 | - | - |

## S7-p20@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 46 | 24.8 | 158 | 0.957 | 10 | 65 | 0.109 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 46 | 27.7 | 158 | 0.983 | 10 | nan | 0.109 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 2.581e+06 | 4.690e+06 | 4.656e+06 | 0.984 | 10 | nan | 0.0586 | - | - |
| undefended | f7 | 3/3 | nan | 18.2 | 9.02 | 23.8 | 0 | 3.47e+03 | 83.5 | 1 | - | - |
| undefended | f6 | 3/3 | nan | 18.2 | 9.02 | 23.8 | 0 | 3.47e+03 | 83.5 | 1 | - | - |
| undefended | f5 | 3/3 | nan | 18.2 | 9.02 | 23.8 | 0 | 3.47e+03 | 83.5 | 1 | - | - |

## S7-p20@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 50.9 | 58.1 | 317 | 0.902 | 10 | nan | 0.122 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 33.9 | 14.4 | 114 | 0.969 | 10 | 80.5 | 0.0704 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 3.631e+05 | 6.096e+05 | 6.033e+05 | 0.984 | 10 | nan | 0.0586 | - | - |
| undefended | f7 | 3/3 | nan | 18.1 | 9.19 | 24 | 0 | 3.47e+03 | 73.7 | 1 | - | - |
| undefended | f6 | 3/3 | nan | 18.1 | 9.19 | 24 | 0 | 3.47e+03 | 73.7 | 1 | - | - |
| undefended | f5 | 3/3 | nan | 18.1 | 9.19 | 24 | 0 | 3.47e+03 | 73.7 | 1 | - | - |

## S7-p2@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 2.5 | 2.08 | 5.32 | 0 | 3.48e+03 | 0 | 0.947 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 2.5 | 2.08 | 5.32 | 0 | 3.48e+03 | 0 | 0.947 | - | - |
| undefended | f7 | 3/3 | nan | 2.49 | 2.18 | 5.31 | 0.00108 | 2.88e+03 | 0 | 1 | - | - |
| undefended | f6 | 3/3 | nan | 2.49 | 2.18 | 5.31 | 0.00108 | 2.88e+03 | 0 | 1 | - | - |

## S7-p2@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 2.52 | 2.03 | 5.19 | 0 | 3.48e+03 | 0 | 0.948 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 2.52 | 2.03 | 5.19 | 0 | 3.48e+03 | 0 | 0.948 | - | - |
| undefended | f7 | 3/3 | nan | 2.56 | 2.56 | 5.18 | 0.00108 | 2.88e+03 | 0 | 1 | - | - |
| undefended | f6 | 3/3 | nan | 2.56 | 2.56 | 5.18 | 0.00108 | 2.88e+03 | 0 | 1 | - | - |

## S7-p5@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 13.8 | 5.6 | 18.5 | 0 | 3.48e+03 | 53.5 | 0.943 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 13.8 | 5.6 | 18.5 | 0 | 3.48e+03 | 53.5 | 0.943 | - | - |
| undefended | f7 | 3/3 | nan | 13.7 | 5.8 | 18.5 | 0 | 3.48e+03 | 54.5 | 1 | - | - |
| undefended | f6 | 3/3 | nan | 13.7 | 5.8 | 18.5 | 0 | 3.48e+03 | 54.5 | 1 | - | - |

## S7-p5@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 13.8 | 5.56 | 18.8 | 0 | 3.48e+03 | 52 | 0.943 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 13.8 | 5.56 | 18.8 | 0 | 3.48e+03 | 52 | 0.943 | - | - |
| undefended | f7 | 3/3 | nan | 13.7 | 6.01 | 18.8 | 0 | 3.48e+03 | 53.4 | 1 | - | - |
| undefended | f6 | 3/3 | nan | 13.7 | 6.01 | 18.8 | 0 | 3.48e+03 | 53.4 | 1 | - | - |

## S7-p60@industrial_mems

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 30.5 | 8.57 | 207 | 0.645 | 30 | 59.5 | 0.378 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 43.3 | 19.3 | 300 | 0.968 | 30 | nan | 0.144 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 39.8 | 19.3 | 208 | 0.953 | 30 | nan | 0.157 | - | - |
| undefended | f7 | 3/3 | nan | 19.9 | 10.8 | 28.4 | 0 | 3.45e+03 | 99 | 1 | - | - |
| undefended | f6 | 3/3 | nan | 19.9 | 10.8 | 28.4 | 0 | 3.45e+03 | 99 | 1 | - | - |
| undefended | f5 | 3/3 | nan | 19.9 | 10.8 | 28.4 | 0 | 3.45e+03 | 99 | 1 | - | - |

## S7-p60@tactical

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt_local | f7 | 3/3 | nan | 237 | 64.2 | 1.21e+03 | 0.93 | 30 | 49 | 0.14 | - | - |
| fedqpnt_local | f6 | 3/3 | nan | 236 | 47.3 | 1.24e+03 | 0.969 | 30 | nan | 0.117 | - | - |
| fedqpnt_local | f5 | 3/3 | nan | 237 | 47.3 | 1.24e+03 | 0.975 | 30 | nan | 0.117 | - | - |
| undefended | f7 | 3/3 | nan | 19.9 | 10.9 | 28.6 | 0 | 3.45e+03 | 98 | 1 | - | - |
| undefended | f6 | 3/3 | nan | 19.9 | 10.9 | 28.6 | 0 | 3.45e+03 | 98 | 1 | - | - |
| undefended | f5 | 3/3 | nan | 19.9 | 10.9 | 28.6 | 0 | 3.45e+03 | 98 | 1 | - | - |

## S8

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_b_cont | f7 | 2/2 | 18.7 | - | - | - | 0.35 | - | - | - | 4.5 | - |
| baseline_b_cont | f6 | 1/1 | 2.28 | - | - | - | 0 | - | - | - | 5 | - |
| baseline_b_cont | f5 | 1/1 | 1.148e+04 | - | - | - | 0.735 | - | - | - | 0 | - |
| fedqpnt | f7 | 2/2 | 18.5 | - | - | - | 0.35 | - | - | - | 4.3 | - |
| fedqpnt | f6 | 1/1 | 2.28 | - | - | - | 0 | - | - | - | 4.8 | - |
| fedqpnt | f5 | 1/1 | 1.148e+04 | - | - | - | 0.735 | - | - | - | 0 | - |

## S9

| method | ver | n(ok/tot) | rmse_h_pre | rmse_h_att | rmse_h_post | max_h_att | fpr | latency_on | t_rec | mean_w_gnss_att | round_installs | auc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fedqpnt | f7 | 2/2 | 18.6 | - | - | - | 0.35 | - | - | - | 3.9 | - |
| fedqpnt | f6 | 1/1 | 2.28 | - | - | - | 0 | - | - | - | 4.8 | - |
| fedqpnt | f5 | 1/1 | 1.148e+04 | - | - | - | 0.735 | - | - | - | 0 | - |
| fedqpnt_noloss | f7 | 2/2 | 18.5 | - | - | - | 0.35 | - | - | - | 4.5 | - |
| fedqpnt_noloss | f6 | 1/1 | 2.28 | - | - | - | 0 | - | - | - | 5 | - |
| fedqpnt_noloss | f5 | 1/1 | 1.148e+04 | - | - | - | 0.735 | - | - | - | 0 | - |
