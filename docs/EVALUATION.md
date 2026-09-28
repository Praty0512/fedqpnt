# Evaluation Framework: Statistics, Scenarios, and Campaign Management

This document covers the evaluation infrastructure: statistical methods (Wilcoxon, Hodges-Lehmann, Holm-Bonferroni), the scenario registry (S1–S15), campaign runner, and the report generator. All evaluation runs use test seeds (≥ 10000) and obey a gate that blocks final runs until kappa_R is cleared.

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

#### S1: Nominal (Clean Signal)
No attacks. Acceptance: FAR ≤ 1/h; RMSE_h ratio (fedqpnt / undefended) ≤ 1.05; ANEES_pos ∈ [0.5, 2].

#### S2: Spoofing Severity (Drift)
Three severity levels: low (0.3, offset < 50 m), med (0.6), high (0.9, ≥ 50 m).
**PROPOSED-DECISION (D-048 ruling):** use measured final offset per run, not nominal mapping. Acceptance: P_D ≥ 0.9 at high severity; "never worsen" bounds at low/med.

#### S3, S4: Outage Legs
**BLOCKED by D-046/D-047** (kappa_R PROVISIONAL; CAI-dependent).

#### S5: Single-Node Failure Mid-Mission
Node fails at T/2 (20% of fleet at N=5). Acceptance: AUC drop ≤ 0.02.

#### S6: Receiver Aiding (CAI) Performance
**BLOCKED by D-046/D-047.**

#### S7: Trust-Law Chattering Bound
3600 s mission: cycles of distrust/recovery must not exceed 52 per hour (ceil(3600/70), where 70 = T_ex + T_probe for v2 law).

#### S8, S9: Comms Loss and Fading
**S8:** Gilbert-Elliott loss. **S9:** Delay spike. Both `requires_fl=True`.
Acceptance: AUC drop ≤ 0.03 (S9).

#### S12: Byzantine Poisoning
Server-coordinated attacks (sign_flip, label_flip, gaussian_noise, ALIE) at f ∈ {20%, 40%}. Both FedAvg and TRIM-NB-R.
Acceptance (TRIM-NB-R, f=20%, sign_flip): mean drop ≤ 0.05, 95% CI ⊆ [−∞, 0.05].

#### S14: Attitude Hold (Pendulum Swing)
**BLOCKED by D-046/D-047.**

#### S15: Replay Detection
Cold replay (same ephemeris/position as a past attack window, rebroadcast later). `requires_fl=True`.

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
- **Test (final results):** ≥ 10000 (locked until `--final --gate-cleared` AND `results/GATE_D047.json` = `{"cleared": true}`)

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
Per-scenario acceptance tables (pass/fail/BLOCKED + value), H1–H4 confirmatory tests with Holm family-wise correction, exploratory secondary metrics labelled `EXPLORATORY`.

**Both Markdown and CSV output**, stamped with `kappa_R_status` on every row.

### Exploratory Metrics
- Latency (time from attack onset to decision)
- Per-family AUC breakdowns
- Learned-detector-only vs operational (p_bar) AUC (D-056)

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
Severities mapped to offsets per ASSUMPTION (low=0.3 → < 50 m; high=0.9 → ≥ 50 m), **but acceptance criterion must use the measured final offset from each run**, not the nominal mapping. Justification recorded in criterion `justification` string.

### S2 Sigma_nom (D-048 Ruling)
Used 5 m as nominal 1-sigma horizontal-error margin for "3×sigma_nom" never-worsen bound **per run**: `sigma_nom = RMSE_h(P_pre)` measured in same run (same seed, method), not a frozen constant.
**Rationale:** κ_R = 40 (PROVISIONAL) shifts the innovation scale; retraining detector requires recalibrating reference stats (procedure in D-049), so a fixed sigma_nom would be out of sync. Per-run measurement avoids this.

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
  - σ_nom measured per run, not constant
  - Final offset used, not nominal severity mapping
  - Worker cap = 4 (shared machine)
  - S5/S8/S9/S12/S15 NOT_RUNNABLE until fleet/sanity/protocol finalized
  - FedAvg "negative drop" anomaly is designed vulnerability, not scoring bug

---

**Last updated:** 2026-09-29 · **Status:** PROVISIONAL (D-046/D-047 gate active; 9/15 scenarios runnable) · **Test count:** 27 stats tests + 2 campaign tests PASS
