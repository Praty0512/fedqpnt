# Evaluation Framework: Statistics, Scenarios, and Campaign Management

This document covers the evaluation infrastructure: statistical methods (Wilcoxon, Hodges-Lehmann, Holm-Bonferroni), the scenario registry (S1–S15), campaign runner, and the report generator. Final (publication) evaluation runs use the held-out test seeds and obey a gate that blocks them until GATE_D047 is cleared. Tuning, dry-run and diagnostic runs use tuning seeds (see Seed Ranges). [updated 2026-09-29, D-067]

---

## Purpose and Scope

**Owns:** `fedqpnt/eval/stats.py`, `fedqpnt/eval/scenarios.py`, `fedqpnt/eval/campaign.py`, `fedqpnt/eval/report.py`, `tests/test_eval_stats.py`, `tests/test_eval_campaign.py`, `scripts/run_campaign.py`.

**Boundaries:** Public APIs only from `fedqpnt.node.runner` (`RunSpec`, CLI `python -m fedqpnt.node.runner '<json>'`) and `fedqpnt.eval.metrics`. No edits to fusion/node/trust/fl/core/gnss/sensors.

---

## Statistical Methods (ARCHITECTURE §7)

### Primary Test: Wilcoxon Signed-Rank
Non-parametric paired comparison over M=30 seeds. Robust to outliers and non-normality.

**Conditional fallback:** Shapiro-Wilk test on paired differences (p > 0.05) → use paired t-test.

**Post-hoc:** Hodges-Lehmann shift estimator + 95% BCa bootstrap CI (10,000 resamples, RNG `stream(seed, "eval", "bootstrap")` per D-005).

### Effect Size and Multiple Comparisons
- **Matched-pairs rank-biserial r:** effect-size analog for Wilcoxon
- **Cohen's d_z:** standardized paired effect (for reference)
- **Holm-Bonferroni:** family-wise error rate control over declared test family

### Distributional and Categorical Tests
- **Friedman + Nemenyi (studentized range):** non-parametric ANOVA + post-hoc
- **Exact McNemar:** categorical 2×2 contingency
- **Wilson CI:** binomial proportion confidence

### Sample-Size Formula
Power analysis via Altman method for non-parametric tests.

**All tests validated** against `scipy.stats` directly or hand-computed textbook values. 27 tests in `tests/test_eval_stats.py` — PASS. No statsmodels dependency.

---

## Scenario Registry (ARCHITECTURE §6.1)

Declarative registry of S1–S15 (17 total entries; S2 splits into low/med/high severity).

Each scenario carries:
- **Acceptance criteria:** executable `Criterion.check(results)` callables over `campaign.load_results()` output
- **Blocked-by status:** D-046/D-047 gate (attitude/bias/CAI claims blocked)
- **Requires-FL flag:** S5, S8, S9, S12, S15 flagged `requires_fl=True`

### Scenario Categories

[updated 2026-09-29, D-067] The descriptions below were rewritten to match `fedqpnt/eval/scenarios.py` (the code is the source of truth; ARCHITECTURE §6.1 states the *intended* design). Where the registered configuration is narrower than the scenario's title or intent, this is stated as "CODE vs INTENT" and listed in `docs/specs/raw/EVAL_CONSIST_PROPOSALS.md` (item 6); the code was not changed. All single-node scenarios use `cai_grade="field"` and world `flat` unless stated. "Undefended" = fixed trust w = 1, NIS gate off.

#### S1: Nominal
1 node, 600 s, no attack, all 7 single-node methods. Criteria (all on `fedqpnt_local`): median paired RMSE_h(P_pre) ratio vs `fixed_trust` <= 1.05; FAR <= 1/h/node; ANEES_pos in [0.5, 2] (diagonal-covariance form, `metrics.anees_pos`); mean w_gnss >= 0.95.

#### S2: Gradual (drift) spoof, severities low / med / high
1 node, 600 s, `drift_spoof`, onset 60 s, duration 300 s, severity 0.3 / 0.6 / 0.9 (ASSUMPTION mapping; the "final offset >= 50 m" classification is **hard-coded in the code**: low = no, med and high = yes). Criteria on `fedqpnt_local`: `detection_prob` = P_D, the fraction of seeds with finite `latency_on`, must be >= 0.9 where final offset >= 50 m (otherwise reported only); `damage_bound`: where >= 50 m, median paired MAX_h(P_att) ratio vs `undefended` <= 0.5; for low severity, median(MAX_h_defended - MAX_h_undefended) <= 3 sigma_nom with **sigma_nom = 5 m hard-coded in the code**.
CODE vs INTENT: (i) D-048 ruled that the ">= 50 m" split must use the *measured* final offset per run and that sigma_nom must not be a constant; the code does neither (see "S2 Sigma_nom" below). (ii) ARCHITECTURE §6.1 applies the 3 sigma_nom "never worsen" bound to all severities; the code applies it only to low.

#### S3: Sudden jamming (BLOCKED, D-047)
1 node, 300 s, `jam_wideband`, onset 60 s, duration 60 s, severity 1.0. Single criterion `t_dist_bound` (design bound 2 GNSS epochs + 1 s = 3 s); it always returns `passed=None` (blocked) and only reports mean t_dist. The ARCHITECTURE consistency criterion (e_h <= 3 sigma_h in >= 95% of outage samples) is not implemented.

#### S4: Combined jam then spoof capture (BLOCKED, D-047)
1 node, 400 s. CODE vs INTENT: the title and ARCHITECTURE describe a jam followed by a spoof capture at reacquisition, but the registered attack is `jam_wideband` only (onset 60 s, duration 40 s, severity 1.0), i.e. **only the jam leg; there is no spoof leg**. The single criterion is a blocked stub (`passed=None`, reports mean w_gnss). The reacquisition-cap test (w_gnss <= w_reacq) is therefore not exercised.

#### S5: Partial node failure / delayed FL updates
Fleet, N = 10, 600 s, no attack; methods `fedqpnt`, `baseline_a`; `requires_fl=True`. Fault injection (`fleet_adapter._s5_kwargs`): `n_fail = max(1, round(0.3 N))` nodes (the first ids) fail at round `max(1, n_rounds // 2)`; a further `max(1, round(0.2 N))` nodes get a 1-3-round delay window. (Python `round(1.5) = 2`, so N = 5 fails 2 nodes = 40%, not 20%; N = 10 fails 3.) Criteria: `quorum_or_skip_no_deadlock` (P(no ABORT) = 1) and `auc_drop_le_0_02` = mean(AUC_nofault - AUC_fault) <= 0.02, which needs matched `fedqpnt_nofault` reference runs that the campaign does not currently generate (reported as not evaluable until they exist).

#### S6: Long-duration drift (Schuler world; BLOCKED, D-047)
1 node, 14 400 s, world `schuler_tangent`, methods `fedqpnt_local` and `baseline_b_cont`. CODE vs INTENT: titled "CAI bias drift", but the registered attack is a **GNSS `drift_spoof`** (onset 600 s, open-ended, severity 0.05); no CAI/quantum-bias fault is injected. The ARCHITECTURE criteria (RMSE_h <= 1.05 x RMSE_h(-quantum); w_q < 0.5 within 10 cycles) are blocked stubs, and there is no `-quantum` arm in the method list. `report.py`'s H3 entry reads S6 with `fedqpnt_local` vs `baseline_b_cont`.

#### S7: Trust-law chattering bound
1 node, 3600 s, `drift_spoof` severity 0.5, onset 60 s, open-ended, `toggle_period_s = 10` only (ARCHITECTURE lists periods {2, 5, 10, 20, 60} s; only 10 s is registered). Criterion: max over seeds of `n_cyc_per_hour` <= 3600/26.1 = 137.9 (the §3.3 formal bound, T_cyc >= T_clean + tau_r ln 5 = 26.1 s; ceiling 138). **The code bound is 138/h, not 52/h.** The 52/h figure (ceil(3600/70), T_ex + T_probe = 70 s for the D-051/D-052 v2 law) is *not* what `scenarios.py` checks; the trust law is being revised again (D-066), so the bound is to be re-derived after the freeze (D-067). Until then the S7 result is against the 138/h bound, which is the weaker of the two. TV_w <= 1/h in S1 (ARCHITECTURE) is not a coded criterion.

#### S8: Cold-start node at T/2
Fleet, N = 5, 600 s, `drift_spoof` severity 0.6, onset 330 s, duration 120 s; method `fedqpnt` only. The last node id joins at round `max(1, n_rounds // 2)`. Criteria: P(cold-start node installs a global model within 2 rounds of joining) >= 0.95; mean(cold-start AUC - veteran AUC) >= -0.05 (mission-level per-node AUC, an approximation of "AUC on its first attack"). (The earlier description "Gilbert-Elliott loss" belonged to S9.)

#### S9: Comms dropouts
Fleet, N = 5, 600 s, no attack; method `fedqpnt`. Gilbert-Elliott loss with `loss_b = 0.9`, `p_gb = 0.1` (the harsher end of the ARCHITECTURE grid loss_B in {0.5, 0.9} x P(G->B) in {0.02, 0.1}; the full grid is not swept). This is not a "delay spike" scenario. Criterion: no deadlock/ABORT, and if `fedqpnt_noloss` reference runs exist, AUC drop <= 0.03; otherwise only the no-deadlock leg is evaluated.

#### S10: Sample-rate mismatch
1 node, 300 s, no attack, `fedqpnt_local`. Only the default rate configuration is registered as a single scenario; criterion ANEES in [0.5, 2] (`anees_pos_all`) and no crash. The GNSS-rate x cycle-time grid with +/-1 tick jitter is a described config axis, not registered.

#### S11: "Extreme noise (filter not told)"
1 node, 300 s, `fedqpnt_local`. CODE vs INTENT: the title and ARCHITECTURE (IMU noise x10, GNSS sigma x5, CAI contrast /3, filter not told) describe a noise-scaling stress test, but the registered scenario carries **only an `abrupt_spoof` (onset 60 s, duration 60 s, severity 1.0)** and no noise scaling. The single criterion is that `rmse_h_att` is finite in 100% of runs; the ARCHITECTURE bound RMSE_h <= 1.5 x GNSS-only is not implemented.

#### S12: Trust-score / model poisoning
Fleet, N = 10, 600 s, no attack; method `fedqpnt` (TRIM-NB-R). `fleet_adapter._s12_kwargs` poisons `max(1, round(f N))` nodes with `poison_kind="sign_flip"` (x(-5), see FEDERATION.md) at f = 0.2 by default. ARCHITECTURE lists four attack types (sign_flip, label_flip, gaussian_noise, ALIE) and f in {20%, 40%}; only sign_flip at 20% is wired into the scenario and its criterion (the other types and f = 40% were run by scripts). Criterion: mean(AUC_clean - AUC_poisoned) <= 0.05 against matched `fedqpnt_clean` reference runs (not generated by the campaign by default). The "95% CI subset of (-inf, 0.05]" form previously written here is not what the code checks; the CI is reported by the S12 scripts (see FEDERATION.md).

#### S13: Recovery after attack
1 node, 300 s, `abrupt_spoof` severity 0.8, onset 60 s, duration 60 s. Criterion: P(t_rec <= 60 s) >= 0.9 and all runs recover (finite t_rec).

#### S14: Multi-hour stability (Schuler world; BLOCKED, D-047)
1 node, 14 400 s, `schuler_tangent`, no attack. Blocked stub; the ARCHITECTURE criteria (hour-4 vs hour-1 RMSE, RSS growth, FAR) are not implemented. (Earlier title "Attitude Hold (Pendulum Swing)" was wrong.)

#### S15: Simultaneous attacks on a fleet subset
Fleet, N = 10, 600 s, `drift_spoof` severity 0.6, onset 60 s, duration 300 s applied to the first `max(1, round(0.3 N))` = 3 nodes simultaneously; method `fedqpnt`. **This is not "replay detection"** (the earlier description was wrong). Criteria: P(quarantine_events == 0) >= 0.9 and mean FAR of the unattacked nodes <= 1.5/h. The ARCHITECTURE leg "attacked nodes meet S2" is not implemented.

### Scenario Metadata
**Blocked status:** `scenarios.KAPPA_R_STATUS = "PROVISIONAL_D047_kappa_R=40"` stamped onto every campaign run and report row (D-047 parked the filter's ψ/b overconfidence investigation).

---

## Campaign Runner (ARCHITECTURE §7/8)

### Execution Model
`RunTask` = (scenario_id, method, seed) tuple.
- **CLI:** `python -m fedqpnt.node.runner '<json>'` as real subprocess (not in-process)
- **Result per run:** `runs/<scenario_id>/<method>/seed_<seed>.json` with `status`, `config_hash`, `kappa_R_status`, `metrics`
- **Resumability:** skips files with `status=="ok"` (proven: killed mid-run, restarted, verified exact skip count)

### Seed Ranges (D-002, D-005)
- **Tuning:** 500–599 (detector training, FL sanity check, preliminary runs)
- **Disjoint evaluation:** 9500–9699 (signature-strength sweep and other per-design studies, still tuning range)
- **Test (final results):** formally **[10000, 20000)** per D-067 (10000–10029 for the 30-seed cells), locked until `--final --gate-cleared` AND `results/GATE_D047.json` = `{"cleared": true}`. [updated 2026-09-29, D-067] **Code note:** `campaign.TEST_SEED_MIN = 10000` is enforced as `seed >= 10000` with no upper bound; D-067 requires the gate to enforce the range (see proposals, item 5). Fleet local-training mission seeds (`100000 + seed*100 + idx*10` by default, and the `200_000+`/`300_000+`/`400_000+` bases used in scripts) are a separate derived namespace, disjoint from [10000, 20000).
- **Pilot / pre-training:** pilot 600–609 (ARCHITECTURE §7.1); θ0 pre-training 400–449.

### Worker Discipline (D-048)
Hard-limited to `MAX_WORKERS=4` (shared machine with FL and M1-CLOSE agents).

### Gate File (D-047)
Campaign refuses test-range seeds unless:
1. `--final --gate-cleared` on CLI
2. `results/GATE_D047.json` exists with `{"cleared": true}`

File created with `{"cleared": false}` if missing; Master clears it after D-047 fixes are applied.

### Dry-Run Plumbing Check
Reduced scale (SHORT duration 120 s, 3 seeds, 3 methods) for infrastructure verification. Output marked "PLUMBING CHECK ONLY — NOT SCIENTIFIC RESULTS."

---

## Report Generator (§6.1/6.2/7.5)

### Output Format
Per-scenario acceptance tables (pass/fail/BLOCKED + value), confirmatory tests with Holm family-wise correction, exploratory secondary metrics labelled `EXPLORATORY`. [updated 2026-09-29, D-067] **The coded confirmatory family (`report.CONFIRMATORY_FAMILY`) is five paired Wilcoxon tests: H1 x {RMSE_h_att, latency_on} and H2 x {RMSE_h_att, latency_on} on S2-med, plus H4 latency_on on S8; H3 (S6, latency_on) is computed but excluded from the Holm family (BLOCKED, D-047).** This differs from ARCHITECTURE §7.5 ({H1..H4} x primary metrics); reconciliation is proposal 2 in `docs/specs/raw/EVAL_CONSIST_PROPOSALS.md`.

**Both Markdown and CSV output**, stamped with `kappa_R_status` on every row.

### Exploratory Metrics
`report.SECONDARY_METRICS`: rmse_h_pre, max_h_pre, rmse_h_post, max_h_post, rmse_3_att, rmse_v_att, anees_pos_pre, t_dist, t_rec, n_cyc_per_hour, tv_w_per_hour, mean_w_gnss, rmse_t_ns, max_t_ns, far_per_hour, fpr. [updated 2026-09-29, D-067] `latency_on` is a *primary* metric (ARCHITECTURE §6.2), not exploratory, and `latency_eff` is not implemented in `metrics.py`. Per-family AUC breakdowns and the learned-detector-only vs operational (p_bar) AUC (D-056) are produced by the H2/H4 and detector scripts, not by `report.py`.

### Markdown Structure
- Per-scenario row: outcome (PASS/FAIL/BLOCKED), measured value, criterion, CI or confidence interval
- H1–H4 section: overall hypothesis status, Holm-corrected p-values
- CAI-related rows marked BLOCKED with link to D-046/D-047

---

## Known Scope Limitations (PROPOSED-DECISION D-048)

### S5, S8, S9, S12, S15 Status
`NOT_RUNNABLE` in initial campaign pending:
1. Fleet runner stability proof (D-050: ACCEPTED)
2. FL sanity check (D-056: PASSED)
3. H2/H4 protocol finalization (D-056: ACCEPTED)

After these, full S5/S8/S9/S12/S15 runs with ≥5 seeds and CIs become valid.

### S2 "Final Offset ≥ 50 m" Split (D-048 Ruling)
Severities mapped to offsets per ASSUMPTION (low=0.3 → < 50 m; med/high=0.6/0.9 → ≥ 50 m), **but the D-048 ruling is that the acceptance criterion must use the measured final offset from each run**, not the nominal mapping. [updated 2026-09-29, D-067] The code still uses the nominal mapping (`final_offset_ge_50m` argument of `_make_s2`); see proposals item 6.

### S2 Sigma_nom (D-048 Ruling): three definitions in circulation [updated 2026-09-29, D-067]
The earlier text here said both "used 5 m" and "per run", which was self-contradictory. The facts:
1. **Code (`scenarios.py::_make_s2`)**: a hard-coded constant `sigma_nom_m = 5.0` [ASSUMPTION]. D-048 **rejected** this constant.
2. **D-048 ruling**: `sigma_nom = RMSE_h(P_pre)` measured in the same run (same seed and method); no assumed constant. Rationale: κ_R shifts the innovation scale, so a fixed σ_nom would be out of sync. **Not implemented in the code.**
3. **D-061 note, `scripts/core_robust_safety_principle_sweep.py`, `scripts/defended_vs_undefended_check.py`**: σ_nom = across-seed standard deviation of the *undefended* method's nominal-scenario RMSE_h(P_pre) (≈ 0.24 m in D-061), measured once and applied to every attack condition; used for the D-055 safety-principle results reported so far.
These are different quantities (a per-run error level, a constant, and a seed-to-seed spread) and differ by roughly 10x. D-055 itself states the principle qualitatively ("never substantially worse"); the "undefended + 3σ_nom" form and its σ_nom definition are pre-registered only through ARCHITECTURE §6.1 (σ_nom undefined), D-048 and D-061. Reconciliation is a Master ruling before M4; see `docs/specs/raw/EVAL_CONSIST_PROPOSALS.md` item 1.

---

## Validation Performed (D-048)

1. **Unit tests:** `pytest tests/test_eval_stats.py tests/test_eval_campaign.py -q` — all PASS.

2. **Dry-run:** 3 seeds × 3 methods (fedqpnt_local, baseline_a, undefended), S1 + S2-low, 120 s SHORT duration.
   - Started as background subprocess
   - Killed mid-way (10/18 files written)
   - Restarted identical command
   - Result: exact resumability (`skipped_done=10`, `ok=8`)
   - Output: `results/eval_dryrun/{report.md, report.csv}` with plumbing-check label

3. **Gate file:** `campaign.ensure_gate_file()` creates `results/GATE_D047.json` with `{"cleared": false}`.

---

## Related Decisions

- **D-002:** Results reported exactly as measured; no scenario dropped after seeing results; all ASSUMPTION values get sensitivity sweeps.
- **D-005:** Hierarchical deterministic RNG streams (`stream(master_seed, node_id, component)`) for paired tests across methods.
- **D-046/D-047:** κ_R = 40 PROVISIONAL; ψ/b overconfidence PARKED for dedicated filter session (S3, S4, S6, S14 blocked).
- **D-048:** 
  - σ_nom measured per run, not constant (ruling; not implemented in the code, see S2 Sigma_nom above [updated 2026-09-29, D-067])
  - Final offset used, not nominal severity mapping
  - Worker cap = 4 (shared machine)
  - S5/S8/S9/S12/S15 NOT_RUNNABLE until fleet/sanity/protocol finalized
  - FedAvg "negative drop" anomaly is designed vulnerability, not scoring bug

---

**Last updated:** 2026-09-29 (scenario descriptions, seed range and sigma_nom/S7 notes corrected, D-067) · **Status:** PROVISIONAL (D-046/D-047 gate active; 9/15 scenarios runnable) · **Test count:** 27 stats tests + 2 campaign tests PASS
