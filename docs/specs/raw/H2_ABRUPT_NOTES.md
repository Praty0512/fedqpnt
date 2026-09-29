## H2-ABRUPT (D-061a: abrupt as the NOVEL family, post CORE-ROBUST E_s fix)

Agent: H2-ABRUPT. theta0_noabrupt (results/fleet/theta0_noabrupt.npz):
pretrained seeds 400-449 restricted to {clean, drift, jam_cw, jam_wideband,
jam_then_spoof} -- abrupt AND meaconing excluded. Chosen FL hyperparams
(D-054.3/D-056): local_epochs=2, lr=0.05, prox_mu=0, R=10. N=5 nodes,
5 seeds [500-504], 600s live missions, abrupt attack onset_s=120,
duration_s=300, **severity=0.15** (Master-accepted per D-061a).

### Step 1: theta0_noabrupt held-out abrupt AUC
Two measurements, same 13 abrupt-family seeds (from 500-599; n=1534 epochs,
1157 positive):
- At the training-pool's DEFAULT severity (0.5, unrelated to the fleet's
  chosen severity): **AUC = 0.898** -- higher than D-055's centrally-
  trained-WITH-abrupt detector (0.691-0.754!). Strong cross-family zero-
  shot transfer, most likely via shared physical-evidence features
  (RAIM/clock-jump/C-N0 anomaly) and/or `jam_then_spoof`'s drift_spoof
  sub-phase; not chased further (D-002: report as measured).
- At the fleet's EXPLICIT severities (Master's D-061a item 1 ruling):
  0.1->0.819, **0.15->0.805**, 0.2->0.783 -- all in a narrow 0.78-0.82 band,
  below Master's 0.85 low-headroom threshold. **Pre-registered rule: run
  H2/H4 "as planned" (confirmed by Master).**

### Step 2: E_s firing fraction on abrupt (current, CORE-ROBUST-fixed core)
Confirms the task's own prediction: the new D-058 short-baseline jump test
DOES fire on abrupt (it targets exactly this: a GNSS position jump). Sweep
(seeds 500-504, N=1 node, jump = 80m x severity):
0.6->15.6%, 0.4->15.6% (identical count, reacq-window-dominated), 0.2->9.8%,
**0.15->0%**, 0.1->0%. Severity 0.6 was D-056's old abrupt-CONTROL value;
its ~1.8% number in H2_SUBRULE_NOTES.md predates CORE-ROBUST's nav_prior
fix and is now stale (header note added there). **Chose severity=0.15**
(more signal than 0.1, still 0% E_s firing over 900 attack epochs).

### H2 (novel family = abrupt, N=5, 5 seeds, 600s)
| arm | auc_detector_only | auc (p_bar) | latency_on [s] | t_dist [s] | es_fire_frac_attack |
|---|---|---|---|---|---|
| fedqpnt_local | 0.253 +/- 0.045 | 0.552 +/- 0.081 | 48.6 +/- 93.3 | 52.2 +/- 91.7 | 0.019 +/- 0.018 |
| baseline_b_cont | 0.254 +/- 0.061 | 0.551 +/- 0.084 | 48.6 +/- 93.3 (identical per seed) | 52.2 +/- 91.7 | 0.019 +/- 0.017 |

Paired Wilcoxon (n=5): auc_detector_only diff_mean=-0.001, W=7.0, p=1.0
(n.s.); latency_on diff_mean=0.0, W=0.0, p=1.0 (identical per-seed:
[0,2,2,239,0] s for both arms). **NULL RESULT: FedQPNT ~= B-cont, no FL
benefit detected for abrupt as the novel family at severity 0.15.**

### H4 (cold-start, novel family = abrupt, n0 joins round 5)
| arm | auc_detector_only | auc (p_bar) | latency_on [s] | t_dist [s] | es_fire_frac_attack |
|---|---|---|---|---|---|
| fedqpnt_local | 0.263 +/- 0.052 | 0.554 +/- 0.079 | 48.6 +/- 93.3 | 51.8 +/- 91.9 | 0.019 +/- 0.018 |
| baseline_b_cont | 0.268 +/- 0.046 | 0.552 +/- 0.080 | 48.6 +/- 93.3 (identical) | 49.0 +/- 93.1 | 0.017 +/- 0.015 |

Paired Wilcoxon (n=5): auc_detector_only diff_mean=-0.005, W=7.0, p=1.0
(n.s.); latency_on diff_mean=0.0, W=0.0, p=1.0. **Same NULL result as H2.**

### CONTROL (family = drift, severity=1.0, n0 DID see it locally)
| arm | auc_detector_only | auc (p_bar) | latency_on [s] | t_dist [s] | es_fire_frac_attack |
|---|---|---|---|---|---|
| fedqpnt_local | 0.735 +/- 0.082 | 0.947 +/- 0.003 | 0.6 +/- 0.48 | 1.0 +/- 0.0 | 0.997 +/- 0.0 |
| baseline_b_cont | 0.782 +/- 0.097 | 0.949 +/- 0.005 | 0.6 +/- 0.48 (identical) | 1.0 +/- 0.0 | 0.997 +/- 0.0 |

Paired Wilcoxon (n=5): auc_detector_only diff_mean=-0.046, W=0.0, p=0.0625
(n.s. at alpha=0.05, n=5 too small to reach significance; direction is
B-cont slightly HIGHER, opposite of an "FL helps" story anyway); latency_on
identical, p=1.0. **As expected (design check): no significant gap when n0
already has the family locally.** E_s fires on ~99.7% of attack epochs
(full-strength drift saturates the rule floor, as established in
H2_SUBRULE_NOTES.md / D-058) -- both arms' p_bar (0.947-0.949) is almost
entirely rule-carried here, consistent with the sub-rule finding.

### Open finding to flag (not resolved, reported honestly per D-002)
H2/H4's absolute auc_detector_only (~0.25-0.27) is FAR below the isolated
theta0_noabrupt held-out check at the SAME severity 0.15 (0.805). Both
arms track each other almost exactly per-seed in the live runs (e.g. seed
500: 0.192 fedqpnt vs 0.181 b_cont; seed 502: 0.296 vs 0.315), so this is
not per-arm noise -- it looks like a property of the LIVE, CLOSED-LOOP
fleet mission at these 5 seeds (500-504) and this attack window (onset
120s/duration 300s in a 600s mission, trust-gating active) versus the
ISOLATED, OPEN-LOOP `fixed_trust` collection protocol used for the
held-out check (onset 60s/duration 180s in a 120s mission, no trust
feedback). Plausible contributor: trust-driven filter dynamics after the
abrupt event (or around it) may elevate scores on nominal/recovery epochs
enough to depress AUC when the attack epochs' own signal is this weak by
design (severity chosen specifically to sit BELOW the E_s threshold).
NOT chased further this task (compute budget; D-002 says report as
measured, not retune to look better) -- flagging for Master/a follow-up
diagnostic if the H2/H4 abrupt numbers are to be used in the paper.

### Files
- results/fleet/theta0_noabrupt.npz + provenance JSON
- results/fleet/h2_abrupt_theta0_auc_check.json (0.5-default AUC + per-
  severity AUC table)
- results/fleet/h2_abrupt.json (h2_abrupt, h4_abrupt, control_drift, full
  per-seed values + Wilcoxon)
- scripts/h2_abrupt_pretrain_theta0.py, h2_abrupt_theta0_auc_check.py,
  h2_abrupt_theta0_auc_by_severity.py, h2_abrupt_es_firing_check.py,
  h2_abrupt_h2h4_driver.py
