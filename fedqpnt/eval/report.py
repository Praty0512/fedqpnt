"""Aggregates campaign run files into per-scenario acceptance tables, H1-H4
confirmatory tests (Holm-corrected), and exploratory secondary metrics --
ARCHITECTURE.md section 6.1/6.2/7. EVALUATOR-ONLY.

Output: markdown (human report) + CSV (machine-readable table), both
stamped with ``kappa_R_status`` (D-046/D-047) on every row.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from fedqpnt.eval import campaign as CP
from fedqpnt.eval import scenarios as SC
from fedqpnt.eval import stats as ST

# --------------------------------------------------------------------------
# Confirmatory family: H1-H4 x primary metrics (section 6.2/7.5). Each entry
# is (label, scenario_id, metric_field, method_a, method_b) meaning
# "method_a < method_b on metric_field" (lower is better for both primaries).
# H3 is CAI/H3 -- BLOCKED by D-047 and excluded from the Holm family (still
# computed and reported, but never as a pass/fail confirmatory claim).
# --------------------------------------------------------------------------
CONFIRMATORY_FAMILY: tuple[tuple[str, str, str, str, str], ...] = (
    ("H1_rmse_h_att_vs_A", "S2-med", "rmse_h_att", "fedqpnt_local", "baseline_a"),
    ("H1_latency_on_vs_A", "S2-med", "latency_on", "fedqpnt_local", "baseline_a"),
    ("H2_rmse_h_att_vs_Bcont", "S2-med", "rmse_h_att", "fedqpnt_local", "baseline_b_cont"),
    ("H2_latency_on_vs_Bcont", "S2-med", "latency_on", "fedqpnt_local", "baseline_b_cont"),
    ("H4_latency_on_coldstart", "S8", "latency_on", "fedqpnt_local", "baseline_b_cont"),
)
H3_ENTRY = ("H3_latency_eff_vs_minus_quantum", "S6", "latency_on", "fedqpnt_local", "baseline_b_cont")

SECONDARY_METRICS = ("rmse_h_pre", "max_h_pre", "rmse_h_post", "max_h_post", "rmse_3_att", "rmse_v_att",
                      "anees_pos_pre", "t_dist", "t_rec", "n_cyc_per_hour", "tv_w_per_hour", "mean_w_gnss",
                      "rmse_t_ns", "max_t_ns", "far_per_hour", "fpr")


@dataclass
class ScenarioReport:
    scenario_id: str
    kappa_R_status: str
    criteria_rows: list[dict[str, Any]]
    n_by_method: dict[str, int]


def _field(results: dict[str, list[dict]], method: str, field_name: str) -> np.ndarray:
    if method not in results:
        return np.array([])
    return np.array([r.get(field_name, np.nan) for r in results[method]], dtype=float)


def build_scenario_report(scenario_id: str, run_root: str = "runs") -> ScenarioReport:
    scenario = SC.get(scenario_id)
    results = CP.load_results(run_root, scenario_id, list(scenario.methods))
    rows = []
    for crit in scenario.criteria:
        outcome = crit.check(results)
        blocked = crit.blocked_by_D047 or scenario.blocked_by_D047
        passed = None if blocked else outcome.get("passed")
        rows.append(dict(
            criterion=crit.name, justification=crit.justification, blocked_by_D047=blocked,
            passed=passed, value=outcome.get("value"), detail=outcome.get("detail"),
        ))
    n_by_method = {m: len(v) for m, v in results.items()}
    return ScenarioReport(scenario_id=scenario_id, kappa_R_status=SC.KAPPA_R_STATUS, criteria_rows=rows,
                          n_by_method=n_by_method)


def confirmatory_tests(run_root: str = "runs", master_seed: int = 0) -> dict[str, dict[str, Any]]:
    """H1-H4 (+ H3, reported but excluded from Holm) over paired per-seed
    values, with Holm-Bonferroni correction over the declared confirmatory
    family (section 7.5). Missing data (scenario/method not yet run) yields
    an entry with ``evaluable=False`` rather than a fabricated p-value."""
    raw: dict[str, dict[str, Any]] = {}
    pvals: dict[str, float] = {}

    def _one(label, sid, field_name, method_a, method_b):
        scenario = SC.get(sid)
        results = CP.load_results(run_root, sid, list(scenario.methods))
        a = _field(results, method_a, field_name)
        b = _field(results, method_b, field_name)
        if a.size == 0 or b.size == 0 or a.size != b.size:
            return dict(evaluable=False, detail=f"missing/mismatched {method_a} vs {method_b} in {sid}")
        censor = np.nanmax(np.concatenate([a[np.isfinite(a)], b[np.isfinite(b)], [0.0]]))
        a_c = ST.censor_latencies(a, censor) if "latency" in field_name else a
        b_c = ST.censor_latencies(b, censor) if "latency" in field_name else b
        pt = ST.paired_test(a_c, b_c)
        diffs = a_c - b_c
        hl = ST.hodges_lehmann(diffs)
        ci = ST.bca_bootstrap_ci(diffs, master_seed=master_seed)
        r = ST.rank_biserial_matched(a_c, b_c)
        dz = ST.cohens_dz(a_c, b_c)
        return dict(evaluable=True, n=pt.n, wilcoxon_p=pt.wilcoxon_p, t_p=pt.t_p,
                    normal_by_shapiro=pt.normal_by_shapiro, hodges_lehmann=hl, hl_ci95=ci,
                    rank_biserial_r=r, cohens_dz=dz, blocked_by_D047=scenario.blocked_by_D047)

    for label, sid, field_name, ma, mb in CONFIRMATORY_FAMILY:
        raw[label] = _one(label, sid, field_name, ma, mb)
        if raw[label]["evaluable"] and not raw[label].get("blocked_by_D047"):
            pvals[label] = raw[label]["wilcoxon_p"]

    h3_label, sid, field_name, ma, mb = H3_ENTRY
    raw[h3_label] = _one(h3_label, sid, field_name, ma, mb)
    raw[h3_label]["excluded_from_holm_family"] = "H3/CAI benefit BLOCKED by D-046/D-047"

    holm = ST.holm_bonferroni(pvals) if pvals else {}
    for label, (adj_p, reject) in holm.items():
        raw[label]["holm_adjusted_p"] = adj_p
        raw[label]["holm_reject_at_0.05"] = reject
    return raw


def secondary_metrics_table(scenario_ids: list[str], run_root: str = "runs") -> list[dict[str, Any]]:
    rows = []
    for sid in scenario_ids:
        scenario = SC.get(sid)
        results = CP.load_results(run_root, sid, list(scenario.methods))
        for method, recs in results.items():
            for metric in SECONDARY_METRICS:
                vals = np.array([r.get(metric, np.nan) for r in recs], dtype=float)
                finite = vals[np.isfinite(vals)]
                if finite.size == 0:
                    continue
                rows.append(dict(label="EXPLORATORY", scenario=sid, method=method, metric=metric,
                                  n=finite.size, mean=float(np.mean(finite)), median=float(np.median(finite)),
                                  std=float(np.std(finite, ddof=1)) if finite.size > 1 else 0.0,
                                  kappa_R_status=SC.KAPPA_R_STATUS))
    return rows


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def render_markdown(scenario_ids: list[str], run_root: str = "runs", *, is_dry_run: bool = False,
                     master_seed: int = 0) -> str:
    lines = ["# FedQPNT evaluation report", ""]
    if is_dry_run:
        lines += ["**PLUMBING CHECK ONLY -- these numbers are NOT results.** Generated from a short-duration, "
                  "TUNING-seed dry run to prove resumability and end-to-end reporting; do not cite.", ""]
    lines.append(f"kappa_R_status (all rows): `{SC.KAPPA_R_STATUS}` (D-046/D-047)")
    lines.append("")

    lines.append("## Section 6.1 acceptance criteria")
    for sid in scenario_ids:
        rep = build_scenario_report(sid, run_root)
        scenario = SC.get(sid)
        lines.append(f"\n### {sid}: {scenario.title}")
        if scenario.requires_fl:
            lines.append("_requires_fl: dispatched via fedqpnt.eval.fleet_adapter to the fleet "
                          "orchestrator (fedqpnt.fleet.orchestrator.run_fleet), not fedqpnt.node.runner._")
        lines.append(f"n per method: {rep.n_by_method}")
        lines.append("")
        lines.append("| Criterion | Passed | Value | Blocked by D-047 | Detail |")
        lines.append("|---|---|---|---|---|")
        for row in rep.criteria_rows:
            passed = "BLOCKED" if row["blocked_by_D047"] else (
                "n/a" if row["passed"] is None else ("PASS" if row["passed"] else "FAIL"))
            val = f"{row['value']:.4g}" if isinstance(row["value"], (int, float)) and row["value"] is not None \
                and np.isfinite(row["value"]) else "-"
            lines.append(f"| {row['criterion']} | {passed} | {val} | {row['blocked_by_D047']} | "
                          f"{row['detail']} |")

    lines.append("\n## Section 6.2/7 confirmatory hypotheses (H1-H4, Holm-corrected; H3 BLOCKED, excluded)")
    conf = confirmatory_tests(run_root, master_seed=master_seed)
    lines.append("| Hypothesis | Evaluable | n | Wilcoxon p | Holm-adj p | Reject@.05 | HL diff | 95% BCa CI | "
                  "d_z | rank-biserial r |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for label, r in conf.items():
        if not r.get("evaluable"):
            lines.append(f"| {label} | NO ({r.get('detail')}) | - | - | - | - | - | - | - | - |")
            continue
        excl = " [EXCLUDED FROM HOLM FAMILY: D-046/D-047]" if r.get("excluded_from_holm_family") else ""
        holm_p = r.get("holm_adjusted_p", "-")
        reject = r.get("holm_reject_at_0.05", "-")
        ci = r.get("hl_ci95")
        ci_s = f"[{ci[0]:.4g}, {ci[1]:.4g}]" if ci else "-"
        lines.append(f"| {label}{excl} | YES | {r['n']} | {r['wilcoxon_p']:.4g} | {holm_p} | {reject} | "
                      f"{r['hodges_lehmann']:.4g} | {ci_s} | {r['cohens_dz']:.3g} | {r['rank_biserial_r']:.3g} |")

    lines.append("\n## Exploratory secondary metrics (unadjusted p-values, labelled exploratory)")
    sec = secondary_metrics_table(scenario_ids, run_root)
    if not sec:
        lines.append("(no data)")
    else:
        lines.append("| Scenario | Method | Metric | n | Mean | Median | Std |")
        lines.append("|---|---|---|---|---|---|---|")
        for row in sec:
            lines.append(f"| {row['scenario']} | {row['method']} | {row['metric']} | {row['n']} | "
                          f"{row['mean']:.4g} | {row['median']:.4g} | {row['std']:.4g} |")

    return "\n".join(lines) + "\n"


def render_csv(scenario_ids: list[str], run_root: str = "runs") -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["scenario", "criterion", "passed", "value", "blocked_by_D047", "detail", "kappa_R_status"])
    for sid in scenario_ids:
        rep = build_scenario_report(sid, run_root)
        for row in rep.criteria_rows:
            w.writerow([sid, row["criterion"], row["passed"], row["value"], row["blocked_by_D047"],
                        row["detail"], rep.kappa_R_status])
    return buf.getvalue()


def write_report(scenario_ids: list[str], out_dir: str, run_root: str = "runs", *, is_dry_run: bool = False,
                  master_seed: int = 0) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / "report.md"
    csv_path = out / "report.csv"
    md_path.write_text(render_markdown(scenario_ids, run_root, is_dry_run=is_dry_run, master_seed=master_seed))
    csv_path.write_text(render_csv(scenario_ids, run_root))
    return md_path, csv_path
