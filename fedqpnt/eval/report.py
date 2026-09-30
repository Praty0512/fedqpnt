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
from fedqpnt.eval import metrics as M
from fedqpnt.eval import scenarios as SC
from fedqpnt.eval import stats as ST

# --------------------------------------------------------------------------
# Confirmatory family (D-068): EXACTLY 8 tests, fixed m = 8, Holm. A test that
# cannot be evaluated (missing data, blocked scenario, sigma_nom not frozen,
# H2 file absent) counts as NOT rejected (p = 1) and m NEVER shrinks.
#   H1 x {RMSE_h(att), latency_on} on S2-med vs Baseline A
#   H2 x {P_D@10 s, onset latency} (D-064 event-level primaries; the H2 RMSE test is dropped)
#   H3 x latency_eff vs abl_minus_quantum at {industrial_mems, tactical}
#   H4 x {P_D@10 s, onset latency} for the cold-start node (D-064 protocol)
# Each test is two-sided paired Wilcoxon; direction is read from the Hodges-Lehmann difference (arm_a - arm_b).
# --------------------------------------------------------------------------
FAMILY_M = 8
H2_RESULT_PATH = "results/fleet/h2_abrupt.json"
SIGMA_NOM_PATH = SC.SIGMA_NOM_PATH


@dataclass(frozen=True)
class ConfTest:
    label: str
    hypothesis: str
    source: str            # "campaign" (runs/<scenario>[@grade]/...) | "h2file" (H2 fleet result file)
    scenario: str          # campaign: scenario id; h2file: block name ("h2" | "h4")
    metric: str            # rmse_h_att | latency_on | latency_eff | pd10 | onset_latency
    arm_a: str
    arm_b: str
    grade: str | None = None


CONFIRMATORY_FAMILY: tuple[ConfTest, ...] = (
    ConfTest("H1_rmse_h_att_vs_A", "H1", "campaign", "S2-med", "rmse_h_att", "fedqpnt_local", "baseline_a"),
    ConfTest("H1_latency_on_vs_A", "H1", "campaign", "S2-med", "latency_on", "fedqpnt_local", "baseline_a"),
    ConfTest("H2_pd10_vs_Bcont", "H2", "h2file", "h2", "pd10", "fedqpnt", "baseline_b_cont"),
    ConfTest("H2_onset_latency_vs_Bcont", "H2", "h2file", "h2", "onset_latency", "fedqpnt", "baseline_b_cont"),
    ConfTest("H3_latency_eff_mems", "H3", "campaign", "S6", "latency_eff", "fedqpnt_local", "abl_minus_quantum",
             "industrial_mems"),
    ConfTest("H3_latency_eff_tactical", "H3", "campaign", "S6", "latency_eff", "fedqpnt_local",
             "abl_minus_quantum", "tactical"),
    ConfTest("H4_pd10_coldstart", "H4", "h2file", "h4", "pd10", "fedqpnt", "baseline_b_cont"),
    ConfTest("H4_onset_latency_coldstart", "H4", "h2file", "h4", "onset_latency", "fedqpnt", "baseline_b_cont"),
)
assert len(CONFIRMATORY_FAMILY) == FAMILY_M == 8


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


# D-068 uniform censoring. Event-level metrics (H2/H4 onset latency, D-064) are
# censored at 60 s; every other latency at t_off - t_on (the scenario's attack
# window). NEVER data-dependent (the former nanmax over the observed values is gone).
EVENT_LATENCY_FIELDS = ("onset_latency", "latency_onset")


def _latency_series(results: dict[str, list[dict]], method: str, field_name: str, scenario) -> np.ndarray:
    """Per-record censored latencies for ``method``."""
    from fedqpnt.eval import metrics as _M
    if method not in results:
        return np.array([])
    event = field_name in EVENT_LATENCY_FIELDS or scenario.id in ("S8",)
    window = (scenario.attack or {}).get("duration_s")
    out = []
    for r in results[method]:
        det = _M.detected_from_record(r, window)
        lat = r.get(field_name, np.nan)
        if event:
            out.append(_M.censor_event(lat, det))
        else:
            w = r.get("window_s", window)
            if w is None:
                raise ValueError(f"{scenario.id}: no attack window to censor {field_name} at")
            out.append(_M.censor_window(lat, det, float(w)))
    return np.array(out, dtype=float)


def build_scenario_report(scenario_id: str, run_root: str = "runs") -> ScenarioReport:
    scenario = SC.get(scenario_id.split("@")[0])
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


def load_h2_block(path: str, block: str, metric: str) -> dict[str, np.ndarray]:
    """Reads paired per-seed arrays for the H2 / H4 event-level metrics from the H2 fleet result file.

    TODO(D-068, interface only -- the data format of the re-run H2/H4 result file is NOT final): the expected
    schema is ``{block: {"seeds": [...], metric: {arm: [per-seed value, ...]}}}`` with ``block`` in
    {"h2", "h4"}, ``metric`` in {"pd10" (0/1 per seed, P_D@10 s at the calibrated tau),
    "onset_latency" (seconds, raw; censored HERE at 60 s, D-064)} and per-seed entries aligned across arms.
    Raises FileNotFoundError / KeyError / ValueError when the file or block is absent or malformed; the caller
    turns that into an unevaluable test (counts as not rejected).
    """
    import json
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"{p} not found (H2/H4 re-run result file not produced yet)")
    d = json.loads(p.read_text())[block]
    per_arm = d[metric]
    return {arm: np.array(v, dtype=float) for arm, v in per_arm.items()}


def _paired_stats(a_c: np.ndarray, b_c: np.ndarray, master_seed: int, **extra) -> dict[str, Any]:
    pt = ST.paired_test(a_c, b_c)
    diffs = a_c - b_c
    return dict(evaluable=True, n=pt.n, wilcoxon_p=pt.wilcoxon_p, t_p=pt.t_p,
                normal_by_shapiro=pt.normal_by_shapiro, hodges_lehmann=ST.hodges_lehmann(diffs),
                hl_ci95=ST.bca_bootstrap_ci(diffs, master_seed=master_seed),
                rank_biserial_r=ST.rank_biserial_matched(a_c, b_c), cohens_dz=ST.cohens_dz(a_c, b_c), **extra)


def _latency_eff_pair(results: dict[str, list[dict]], arm_a: str, arm_b: str, sigma_nom_m: float):
    """Paired latency_eff per seed. A seed is EXCLUDED if the attack never became effective (D-068); the
    truth-side offset is arm-independent (D-005), so the exclusion is the same for both arms, but it is
    applied to the pair (either arm excluded -> seed dropped). Returns (a, b, n_excluded)."""
    ra = {r.get("_seed"): r for r in results.get(arm_a, [])}
    rb = {r.get("_seed"): r for r in results.get(arm_b, [])}
    seeds = sorted(set(ra) & set(rb), key=lambda x: (x is None, x))
    a, b, excl = [], [], 0
    for sd in seeds:
        la = M.latency_eff_from_record(ra[sd], sigma_nom_m)
        lb = M.latency_eff_from_record(rb[sd], sigma_nom_m)
        if la["excluded"] or lb["excluded"]:
            excl += 1
            continue
        a.append(la["latency_eff"])
        b.append(lb["latency_eff"])
    return np.array(a), np.array(b), excl


def _evaluate_test(t: ConfTest, run_root: str, h2_path: str, sigma_path: str, master_seed: int) -> dict[str, Any]:
    """Never raises for missing inputs: returns ``evaluable=False`` with the reason."""
    try:
        if t.source == "h2file":
            per = load_h2_block(h2_path, t.scenario, t.metric)
            if t.arm_a not in per or t.arm_b not in per or per[t.arm_a].shape != per[t.arm_b].shape \
                    or per[t.arm_a].size == 0:
                return dict(evaluable=False, detail=f"H2 file lacks paired arms {t.arm_a}/{t.arm_b} for {t.metric}")
            a, b = per[t.arm_a], per[t.arm_b]
            if t.metric == "onset_latency":
                a = np.array([M.censor_event(x, np.isfinite(x)) for x in a])
                b = np.array([M.censor_event(x, np.isfinite(x)) for x in b])
            return _paired_stats(a, b, master_seed)

        sid = t.scenario if t.grade is None else f"{t.scenario}@{t.grade}"
        scenario = SC.get(t.scenario)
        if scenario.blocked_by_D047:
            return dict(evaluable=False, detail=f"{t.scenario} BLOCKED by D-046/D-047 (counted as not rejected)")
        results = CP.load_results(run_root, sid, [t.arm_a, t.arm_b])
        if t.metric == "latency_eff":
            g = t.grade or "industrial_mems"
            sig = M.load_sigma_nom(sigma_path)       # FileNotFoundError if not frozen -> caught below
            if g not in sig:
                return dict(evaluable=False, detail=f"sigma_nom has no entry for grade {g}")
            a, b, n_excl = _latency_eff_pair(results, t.arm_a, t.arm_b, sig[g])
            if a.size == 0:
                return dict(evaluable=False, detail=f"no effective paired runs in {sid} ({n_excl} excluded)")
            return _paired_stats(a, b, master_seed, n_excluded_never_effective=n_excl)
        is_lat = "latency" in t.metric
        a = _latency_series(results, t.arm_a, t.metric, scenario) if is_lat else _field(results, t.arm_a, t.metric)
        b = _latency_series(results, t.arm_b, t.metric, scenario) if is_lat else _field(results, t.arm_b, t.metric)
        if a.size == 0 or b.size == 0 or a.size != b.size:
            return dict(evaluable=False, detail=f"missing/mismatched {t.arm_a} vs {t.arm_b} in {sid}")
        return _paired_stats(a, b, master_seed)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        return dict(evaluable=False, detail=f"{type(exc).__name__}: {exc}")


def confirmatory_tests(run_root: str = "runs", master_seed: int = 0, *, h2_path: str = H2_RESULT_PATH,
                       sigma_path: str = SIGMA_NOM_PATH) -> dict[str, dict[str, Any]]:
    """The 8-test confirmatory family with Holm correction at FIXED m = 8 (D-068). Unevaluable tests get
    p = 1.0 (never rejected) and stay in the family, so m never shrinks."""
    raw: dict[str, dict[str, Any]] = {}
    pvals: dict[str, float] = {}
    for t in CONFIRMATORY_FAMILY:
        r = _evaluate_test(t, run_root, h2_path, sigma_path, master_seed)
        r["hypothesis"] = t.hypothesis
        raw[t.label] = r
        p = r.get("wilcoxon_p") if r.get("evaluable") else None
        pvals[t.label] = float(p) if p is not None and np.isfinite(p) else 1.0
    assert len(pvals) == FAMILY_M
    for label, (adj_p, reject) in ST.holm_bonferroni(pvals).items():
        raw[label]["holm_adjusted_p"] = adj_p
        raw[label]["holm_reject_at_0.05"] = bool(reject and raw[label].get("evaluable"))
    return raw


def secondary_metrics_table(scenario_ids: list[str], run_root: str = "runs") -> list[dict[str, Any]]:
    rows = []
    for sid in scenario_ids:
        scenario = SC.get(sid.split("@")[0])
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
    pv = CP.provenance_valid(run_root)
    if pv is False:
        lines.append("**INVALID RUN (D-062): source tree was dirty or changed during the campaign; "
                     f"see `{run_root}/{CP.PROVENANCE_FILE}`. Do not cite these numbers.**")
    elif pv is None:
        lines.append(f"Provenance: no `{CP.PROVENANCE_FILE}` (unknown; not a D-062-validated run).")
    lines.append("")

    lines.append("## Section 6.1 acceptance criteria")
    for sid in scenario_ids:
        rep = build_scenario_report(sid, run_root)
        scenario = SC.get(sid.split("@")[0])
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

    s10 = [sid for sid in scenario_ids if sid.startswith("S10-r") and "-c" not in sid]   # default-T_c cells only
    if len(s10) >= 2:
        by_rate = {SC.get(sid).gnss_rate_hz: CP.load_results(run_root, sid, ["fedqpnt_local"]) for sid in s10}
        mono = SC.s10_rmse_monotone(by_rate)
        lines.append(f"\nS10 cross-rate check (RMSE_h(P_pre) non-increasing in GNSS rate): "
                     f"passed={mono['passed']} -- {mono['detail']}")

    lines.append("\n## Section 6.2/7 confirmatory family (8 tests, fixed m = 8, Holm; unevaluable = not rejected)")
    conf = confirmatory_tests(run_root, master_seed=master_seed)
    lines.append("| Hypothesis | Evaluable | n | Wilcoxon p | Holm-adj p | Reject@.05 | HL diff | 95% BCa CI | "
                  "d_z | rank-biserial r |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for label, r in conf.items():
        if not r.get("evaluable"):
            lines.append(f"| {label} | NO ({r.get('detail')}) | - | - | {r.get('holm_adjusted_p', 1.0):.4g} | "
                          f"False | - | - | - | - |")
            continue
        excl = ""
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
