# EVALUATION agent notes (WP-8.x: fedqpnt/eval/{stats,scenarios,campaign,report}.py)

Scope owned: `fedqpnt/eval/stats.py`, `fedqpnt/eval/scenarios.py`, `fedqpnt/eval/campaign.py`,
`fedqpnt/eval/report.py`, `tests/test_eval_stats.py`, `tests/test_eval_campaign.py`,
`scripts/run_campaign.py`, this file. Public APIs only from `fedqpnt.node.runner`
(`RunSpec`, its `python -m fedqpnt.node.runner '<json>'` CLI entry) and `fedqpnt.eval.metrics`.
No edits to fusion/node/trust/fl/core/gnss/sensors.

## stats.py (ARCHITECTURE.md section 7)
Wilcoxon signed-rank (primary), conditional paired t-test (Shapiro p>0.05), Hodges-Lehmann +
95% BCa bootstrap CI (10k resamples, RNG `stream(seed,"eval","bootstrap")` per D-005/section 7.4),
matched-pairs rank-biserial r, Cohen's d_z, Holm-Bonferroni, Friedman + Nemenyi (studentized range),
exact McNemar, Wilson CI, sample-size formula. All validated against `scipy.stats` directly or
hand-computed textbook values (`tests/test_eval_stats.py`, 27 tests) -- no statsmodels installed in
this environment, so nothing depends on it.

## scenarios.py (section 6.1)
Declarative registry of S1-S15 (17 entries: S2 splits into low/med/high). Each carries its
acceptance criteria as executable `Criterion.check(results)` callables over
`campaign.load_results()` output.

**PROPOSED-DECISION:** S5, S8, S9, S12, S15 need a multi-node federated fleet; `fedqpnt.fl` is out
of scope for this agent and `fedqpnt.node.runner` is single-node only (`FLConfig(enabled=False)`
in `_to_run_config`). These are registered declaratively (`requires_fl=True`) with criteria that
report `NOT_RUNNABLE` rather than fabricate a fleet harness. Master/FL-agent should wire fleet
execution into campaign.py once a federated multi-node runner exists.

**D-046/D-047 gate:** every criterion/scenario carries `blocked_by_D047`. S3, S4 (outage legs),
S6, S14 (attitude/bias/CAI claims) are scenario-level BLOCKED; their criteria report `passed=None`
with a BLOCKED detail regardless of data. `scenarios.KAPPA_R_STATUS =
"PROVISIONAL_D047_kappa_R=40"` is stamped onto every campaign run record and report row.

**PROPOSED-DECISION** (S2 "final offset >= 50m" split): severities are ASSUMPTION-mapped as
low=0.3 (offset <50m, "never worsen" bound only), med=0.6, high=0.9 (>=50m, full P_D>=0.9 + halve-
damage bounds) pending an explicit severity->metres calibration from the spoofing model owner.

**PROPOSED-DECISION** (S2 sigma_nom): used 5 m as the nominal 1-sigma horizontal-error margin for
the "3*sigma_nom" never-worsen bound (no single frozen value found in ARCHITECTURE.md section 9);
flagged in the criterion's `justification` string.

## campaign.py (section 7/8)
`RunTask` = (scenario_id, method, seed) -> a `RunSpec` dict, executed via
`python -m fedqpnt.node.runner '<json>'` as a real subprocess (section 8's "runs execute as real
processes" policy, applied here to Monte Carlo fan-out rather than FL rounds). One result file per
run: `runs/<scenario_id>/<method>/seed_<seed>.json`, containing `status`, `config_hash`,
`kappa_R_status`, and the `metrics` dict from `run_single`. Restart skips any file with
`status=="ok"` (resumability -- proven live below). Refuses seed >= 10000 (TEST range, section
7.1) unless `--final --gate-cleared`; `--gate-cleared` is itself refused unless
`results/GATE_D047.json` says `{"cleared": true}` (file created with `{"cleared": false}` if
missing).

**PROPOSED-DECISION:** worker cap hard-limited to `MAX_WORKERS = 4` inside `campaign.py` itself
(not just the CLI default), since two other agents (FL, M1-CLOSE) share this machine.

## report.py (sections 6.1/6.2/7.5)
Per-scenario acceptance tables (pass/fail/BLOCKED + value), H1-H4 confirmatory tests with Holm
correction over the declared family (H3/CAI excluded per D-046/D-047, still computed and shown),
exploratory secondary metrics labelled `EXPLORATORY`. Markdown + CSV, both stamped with
`kappa_R_status` on every row.

## Validation performed
1. `python -m pytest tests/test_eval_stats.py tests/test_eval_campaign.py -q` -- all pass.
2. Campaign dry-run: TUNING seeds 500-502, S1 + S2-low, methods {fedqpnt_local, baseline_a,
   undefended}, `duration_s=120` (SHORT), `runs/dryrun/`. Started as a real background subprocess,
   killed mid-way with `TaskStop` (its own task id only -- no other process touched) after 10/18
   run files existed; restarted with the identical command; the run log confirms
   `{"skipped_done": 10, "ok": 8}` -- exact resumability. `fedqpnt.eval.report.write_report`
   produced `results/eval_dryrun/{report.md,report.csv}` end to end, explicitly labelled
   "PLUMBING CHECK ONLY -- these numbers are NOT results".
3. `results/GATE_D047.json` created (`{"cleared": false}`) via `campaign.ensure_gate_file()`.

The dry-run's FAR/anees/latency numbers are artefacts of the 120 s SHORT duration (60 s alignment
transient excludes half the run) and TUNING seeds/untuned short-run detector behaviour -- they are
NOT scientific results and must not be cited as such.
