#!/usr/bin/env python
"""M3 results report (PREREG_M4.md, D-064/068/070/075/079/080/081). EVALUATOR-ONLY, read-only on results/.

Reads results/m4 (test-seed campaign), results/fleet/h2_abrupt_prereg_results_freeze4.json (H2/H4, D-081) and
results/sigma_nom.json; writes docs/M3_REPORT.md and results/m3/*.json.

Integrity (D-002): metrics, windows and tests are exactly those registered in fedqpnt.eval (report/scenarios/
metrics/stats). Nothing here changes a metric or a test. A confirmatory test whose input tasks are not all present
is marked INCOMPLETE -- pending and NO p-value is computed for it. Everything not in the 8-test family is labelled
exploratory. fedqpnt/ is not modified.

Usage:  python scripts/m3_report.py [--run-root results/m4] [--out-md docs/M3_REPORT.md] [--out-json results/m3]
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats as sps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fedqpnt.eval import campaign as CP          # noqa: E402
from fedqpnt.eval import metrics as M            # noqa: E402
from fedqpnt.eval import report as RP            # noqa: E402
from fedqpnt.eval import scenarios as SC         # noqa: E402
from fedqpnt.eval import stats as ST             # noqa: E402

H2_FREEZE4 = "results/fleet/h2_abrupt_prereg_results_freeze4.json"
GRADES = ("industrial_mems", "tactical")
H1_GRADE = "industrial_mems"     # unqualified "S2-med" in the registry/family = industrial_mems (the framework default)
TABLE_FIELDS = ("rmse_h_pre", "rmse_h_att", "rmse_h_post", "max_h_att", "far_per_hour", "latency_on",
                "rmse_t_ns")
DEFENDED, UNDEFENDED = "fedqpnt_local", "undefended"
N_SEEDS = 30


# ----------------------------------------------------------------------------------------------- utilities
def clean(o):
    """JSON-safe: numpy -> python, NaN/inf -> None."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not math.isfinite(float(o)) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    return o


def fmt(x, p=4):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "-"
    return f"{x:.{p}g}"


def seed_ranges(seeds):
    seeds = sorted(seeds)
    if not seeds:
        return ""
    out, s, prev = [], seeds[0], seeds[0]
    for x in seeds[1:]:
        if x == prev + 1:
            prev = x
            continue
        out.append((s, prev))
        s = prev = x
    out.append((s, prev))
    return ",".join(str(a) if a == b else f"{a}-{b}" for a, b in out)


def mean_ci(v):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    n = v.size
    if n == 0:
        return dict(n=0, mean=None, ci=None, sd=None)
    m = float(v.mean())
    if n < 2:
        return dict(n=n, mean=m, ci=None, sd=None)
    sd = float(v.std(ddof=1))
    hw = float(sps.t.ppf(0.975, n - 1) * sd / math.sqrt(n))
    return dict(n=n, mean=m, ci=hw, sd=sd)


def trim_common(results):
    """Pair by seed (D-005): keep only seeds present in EVERY method that has any record. No-op when complete."""
    if not results:
        return results, 0
    sets = [set(r["_seed"] for r in recs) for recs in results.values()]
    common = set.intersection(*sets)
    out = {m: sorted([r for r in recs if r["_seed"] in common], key=lambda r: r["_seed"])
           for m, recs in results.items()}
    return out, len(common)


# ----------------------------------------------------------------------------------------------- completeness
def completeness(manifest, run_root):
    exp = {}
    for t in manifest["tasks"]:
        exp.setdefault(t["rid"], {}).setdefault(t["method"], set()).add(t["seed"])
    missing, failed, claimed, present = {}, [], [], 0
    for rid, bym in exp.items():
        for method, seeds in bym.items():
            for sd in sorted(seeds):
                p = Path(run_root) / rid / method / f"seed_{sd}.json"
                ok = False
                if p.exists():
                    try:
                        ok = json.loads(p.read_text()).get("status") == "ok"
                    except Exception:
                        ok = False
                    if not ok:
                        failed.append(f"{rid}/{method}/seed_{sd}")
                if ok:
                    present += 1
                else:
                    missing.setdefault(rid, {}).setdefault(method, []).append(sd)
                    if Path(str(p) + ".claim").exists():
                        claimed.append(f"{rid}/{method}/seed_{sd}")
    total = sum(len(s) for b in exp.values() for s in b.values())
    return dict(expected=total, present=present, missing_n=total - present, missing=missing, failed=failed,
                in_progress_claims=claimed, expected_map={k: {m: sorted(s) for m, s in b.items()}
                                                          for k, b in exp.items()})


def arms_complete(comp, rid, arms):
    miss = comp["missing"].get(rid, {})
    exp = comp["expected_map"].get(rid, {})
    bad = {a: len(miss.get(a, [])) for a in arms if a not in exp or miss.get(a)}
    return (not bad), bad


# ----------------------------------------------------------------------------------------------- confirmatory
def h2_arrays(d, block, arm_a, arm_b):
    part = d["parts"][block]["per_seed"]
    ra = {r["seed"]: r for r in part[arm_a]}
    rb = {r["seed"]: r for r in part[arm_b]}
    seeds = sorted(set(ra) & set(rb))
    return seeds, ra, rb


def eval_h2file(t, d, seed_master=0):
    """H2/H4 from the D-081 file (arms: fedqpnt_local = the registry's 'fedqpnt' FL arm; baseline_b_cont)."""
    block = {"h2": "h2_abrupt", "h4": "h4_abrupt"}[t.scenario]
    seeds, ra, rb = h2_arrays(d, block, "fedqpnt_local", "baseline_b_cont")
    if t.metric == "pd10":
        a = np.array([float(ra[s]["pd10"]) for s in seeds])
        b = np.array([float(rb[s]["pd10"]) for s in seeds])
    else:   # onset_latency, censored at 60 s (D-064/D-068)
        a = np.array([M.censor_event(float(ra[s]["latency_s"]), not ra[s]["censored"]) for s in seeds])
        b = np.array([M.censor_event(float(rb[s]["latency_s"]), not rb[s]["censored"]) for s in seeds])
    out = RP._paired_stats(a, b, seed_master)
    out["seeds"] = seeds
    out["source"] = H2_FREEZE4 + " (D-081; seeds 500-509 of the separate H2 fleet experiment, not the 10000+ range)"
    return out


def eval_h3(t, run_root, sigma_path, seed_master=0):
    """H3 per grade: paired latency_eff (D-068), never-effective seeds excluded. Own wrapper because the registry's
    stale blocked_by_D047 flag on S6 would make report._evaluate_test return unevaluable although the gate was
    cleared at D-080 (PREREG_M4 lists H3 as a confirmatory test)."""
    sid = f"{t.scenario}@{t.grade}"
    results = CP.load_results(run_root, sid, [t.arm_a, t.arm_b])
    sig = M.load_sigma_nom(sigma_path)
    a, b, n_excl = RP._latency_eff_pair(results, t.arm_a, t.arm_b, sig[t.grade])
    if a.size == 0:
        return dict(evaluable=False, detail=f"no effective paired runs in {sid} ({n_excl} excluded)")
    return RP._paired_stats(a, b, seed_master, n_excluded_never_effective=n_excl)


def confirmatory(run_root, comp, sigma_path, h2):
    rows, pvals = [], {}
    all_final = True
    for t in RP.CONFIRMATORY_FAMILY:
        row = dict(label=t.label, hypothesis=t.hypothesis, metric=t.metric, arm_a=t.arm_a, arm_b=t.arm_b,
                   status=None, p=None, hl=None, hl_ci=None, n=None, extra={})
        if t.source == "h2file":
            row["setting"] = f"{H2_FREEZE4}::{t.scenario}"
            try:
                r = eval_h2file(t, h2)
                row.update(status="EVALUATED", n=r["n"], p=r["wilcoxon_p"], hl=r["hodges_lehmann"],
                           hl_ci=r["hl_ci95"], extra=dict(rank_biserial_r=r["rank_biserial_r"],
                                                          cohens_dz=r["cohens_dz"], source=r["source"]))
            except Exception as exc:     # noqa: BLE001
                row.update(status=f"UNEVALUABLE ({type(exc).__name__}: {exc})")
        else:
            tt = dataclasses.replace(t, grade=t.grade or H1_GRADE)
            sid = f"{tt.scenario}@{tt.grade}"
            row["setting"] = sid
            ok, bad = arms_complete(comp, sid, [t.arm_a, t.arm_b])
            if not ok:
                row.update(status="INCOMPLETE — pending", extra=dict(missing_tasks_by_arm=bad))
            else:
                try:
                    if t.hypothesis == "H3":
                        r = eval_h3(tt, run_root, sigma_path)
                    else:
                        r = RP._evaluate_test(tt, run_root, RP.H2_RESULT_PATH, sigma_path, 0)
                    if r.get("evaluable"):
                        row.update(status="EVALUATED", n=r["n"], p=r["wilcoxon_p"], hl=r["hodges_lehmann"],
                                   hl_ci=r["hl_ci95"],
                                   extra=dict(rank_biserial_r=r["rank_biserial_r"], cohens_dz=r["cohens_dz"],
                                              n_excluded_never_effective=r.get("n_excluded_never_effective")))
                    else:
                        row.update(status=f"UNEVALUABLE ({r.get('detail')})")
                except Exception as exc:  # noqa: BLE001
                    row.update(status=f"UNEVALUABLE ({type(exc).__name__}: {exc})")
        if row["status"] == "INCOMPLETE — pending":
            all_final = False
        pvals[t.label] = float(row["p"]) if row["p"] is not None and math.isfinite(row["p"]) else 1.0
        rows.append(row)
    assert len(rows) == RP.FAMILY_M == 8
    if all_final:
        holm = ST.holm_bonferroni(pvals)
        for r in rows:
            adj, rej = holm[r["label"]]
            r["holm_p"] = adj
            r["decision"] = ("REJECT H0 (supported)" if (rej and r["status"] == "EVALUATED")
                             else "not rejected" + (" (unevaluable -> p=1)" if r["status"] != "EVALUATED" else ""))
    else:
        for r in rows:
            r["holm_p"] = None
            if r["status"] == "INCOMPLETE — pending":
                r["decision"] = "pending"
            elif r["p"] is not None and r["p"] >= 1.0:
                # with m = 8 fixed, a raw p of 1 has Holm-adjusted p = 1 whatever the others do
                r["holm_p"] = 1.0
                r["decision"] = "not rejected"
            else:
                r["decision"] = "pending (Holm needs all 8 p)"
    return rows, all_final


def h1_tactical_exploratory(run_root, comp, sigma_path):
    out = []
    for t in RP.CONFIRMATORY_FAMILY:
        if t.hypothesis != "H1":
            continue
        tt = dataclasses.replace(t, grade="tactical")
        sid = f"{tt.scenario}@tactical"
        ok, bad = arms_complete(comp, sid, [t.arm_a, t.arm_b])
        row = dict(label=t.label + "@tactical", label_class="EXPLORATORY (not in the family; unadjusted p)",
                   setting=sid, metric=t.metric)
        if not ok:
            row.update(status="INCOMPLETE — pending", missing_tasks_by_arm=bad)
        else:
            r = RP._evaluate_test(tt, run_root, RP.H2_RESULT_PATH, sigma_path, 0)
            row.update(status="EVALUATED" if r.get("evaluable") else f"UNEVALUABLE ({r.get('detail')})",
                       n=r.get("n"), p=r.get("wilcoxon_p"), hl=r.get("hodges_lehmann"), hl_ci=r.get("hl_ci95"))
        out.append(row)
    return out


# ----------------------------------------------------------------------------------------------- per-rid analysis
def crit_status(outcome, scen_blocked):
    p = outcome.get("passed")
    s = "not-evaluable" if p is None else ("PASS" if p else "FAIL")
    return s


def safety_field(scenario):
    return "max_h_att" if scenario.attack or scenario.attacks else "max_h_pre"


def analyse_rid(rid, methods, run_root, sigma):
    base, grade = (rid.split("@") + [None])[:2] if "@" in rid else (rid, None)
    scenario = SC.get(base)
    grade_eff = grade or "industrial_mems"
    results = CP.load_results(run_root, rid, methods)
    n_by_method = {m: len(v) for m, v in results.items()}
    paired, n_paired = trim_common(results)

    # (b) criteria
    crits = []
    for c in scenario.criteria:
        try:
            o = c.check(paired)
        except Exception as exc:    # noqa: BLE001
            o = dict(passed=None, value=None, detail=f"{type(exc).__name__}: {exc}")
        crits.append(dict(criterion=c.name, status=crit_status(o, scenario.blocked_by_D047 or c.blocked_by_D047),
                          value=o.get("value"), detail=o.get("detail"),
                          registry_blocked_flag=bool(scenario.blocked_by_D047 or c.blocked_by_D047)))

    # (b) safety principle
    safety = None
    if DEFENDED in paired and UNDEFENDED in paired and n_paired >= 1:
        fld = safety_field(scenario)
        a = np.array([r.get(fld, np.nan) for r in paired[DEFENDED]], float)
        u = np.array([r.get(fld, np.nan) for r in paired[UNDEFENDED]], float)
        ok = np.isfinite(a) & np.isfinite(u)
        a, u = a[ok], u[ok]
        if a.size:
            sg = sigma[grade_eff]
            margin = float(a.mean() - u.mean())
            hl = ci = None
            if a.size >= 5:
                d = a - u
                hl = ST.hodges_lehmann(d)
                ci = ST.bca_bootstrap_ci(d, master_seed=0)
            safety = dict(field=fld, n=int(a.size), mean_def=float(a.mean()), mean_undef=float(u.mean()),
                          margin=margin, bound_3sigma=3 * sg, sigma_nom=sg, primary_pass=bool(margin <= 3 * sg),
                          hl=hl, hl_ci95=ci, partial=bool(a.size < N_SEEDS))

    # (c) metric table (all methods; per-method n, no trimming)
    table = {}
    for m, recs in results.items():
        row = {}
        for f in TABLE_FIELDS:
            if f == "latency_on":
                try:
                    v = RP._latency_series(results, m, "latency_on", scenario)
                except Exception:   # noqa: BLE001
                    v = np.array([])
            else:
                v = np.array([r.get(f, np.nan) for r in recs], float)
            row[f] = mean_ci(v)
        table[m] = row

    # exploratory helpers: per-seed vectors for coast / DM
    extra = {}
    if base == "S6-coast" and set(("fedqpnt_local", "abl_minus_quantum")) <= set(paired) and n_paired:
        a = np.array([r.get("max_h_att", np.nan) for r in paired["fedqpnt_local"]], float)
        b = np.array([r.get("max_h_att", np.nan) for r in paired["abl_minus_quantum"]], float)
        ok = np.isfinite(a) & np.isfinite(b) & (a > 0)
        if ok.sum() >= 1:
            ratio = b[ok] / a[ok]
            d = a[ok] - b[ok]
            extra["coast"] = dict(n=int(ok.sum()), median_ratio_minusq_over_cai=float(np.median(ratio)),
                                  hl_cai_minus_minusq=ST.hodges_lehmann(d) if ok.sum() >= 1 else None,
                                  hl_ci95=ST.bca_bootstrap_ci(d, 0) if ok.sum() >= 5 else None)
    return dict(rid=rid, base=base, grade=grade_eff, title=scenario.title, n_by_method=n_by_method,
                n_paired=n_paired, criteria=crits, safety=safety, table=table, extra=extra,
                requires_fl=scenario.requires_fl)


# ----------------------------------------------------------------------------------------------- rendering
def md_confirmatory(rows, all_final, h1_tac):
    L = []
    if not all_final:
        L.append("> **At least one confirmatory test is INCOMPLETE — pending.** No p-value is computed for such tests "
                 "and Holm-adjusted p-values (fixed m = 8) are withheld until all eight raw p-values exist, "
                 "except where a raw p = 1 (adjusted p = 1 regardless). An unevaluable test would count as "
                 "not rejected (p = 1; m never shrinks).\n")
    L.append("| # | Test | Setting | Metric (A vs B) | n | Raw p | Holm p (m=8) | Decision | HL (A−B) | 95% BCa CI |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        ci = f"[{fmt(r['hl_ci'][0])}, {fmt(r['hl_ci'][1])}]" if r["hl_ci"] else "-"
        st = r["status"]
        L.append(f"| {i} | {r['label']} | {r['setting']} | {r['metric']} ({r['arm_a']} vs {r['arm_b']}) | "
                 f"{r['n'] if r['n'] is not None else '-'} | "
                 f"{fmt(r['p']) if st == 'EVALUATED' else st} | {fmt(r['holm_p']) if r['holm_p'] is not None else 'pending'} | "
                 f"{r['decision']} | {fmt(r['hl'])} | {ci} |")
    L.append("")
    L.append("Notes. A = first-named arm; HL is the Hodges–Lehmann estimate of the paired difference A − B (negative "
             "favours FedQPNT for the error/latency metrics; for P_D@10 s positive favours FedQPNT). Test: two-sided "
             "paired Wilcoxon, α = 0.05 family-wise (Holm, fixed m = 8; PREREG_M4 §4).  \n"
             f"H1 grade: PREREG_M4/D-068 name the setting 'S2-med' without an IMU grade; the registry's unqualified "
             f"`S2-med` is the `{H1_GRADE}` grade (framework default), which is therefore the confirmatory H1 setting. "
             "The tactical-grade H1 comparison is reported below as EXPLORATORY.  \n"
             "H2/H4 rows come from the D-081 result file (seeds 500–509 of the separate fleet experiment); the FL arm "
             "is `fedqpnt_local` in that file, B-cont is `baseline_b_cont`; onset latency censored at 60 s.  \n"
             "H3 uses the registered `latency_eff` (D-068; seeds where the attack never became effective are "
             "excluded pairwise). The registry still carries `blocked_by_D047=True` on S6; the gate was cleared in "
             "D-080 and PREREG_M4 lists H3 as confirmatory, so the flag is treated as stale (see §2 note).")
    L.append("")
    L.append("**Exploratory (not in the family, unadjusted):** H1 on the tactical grade")
    L.append("")
    L.append("| Test | Setting | Status | n | raw p | HL | 95% CI |")
    L.append("|---|---|---|---|---|---|---|")
    for r in h1_tac:
        ci = f"[{fmt(r['hl_ci'][0])}, {fmt(r['hl_ci'][1])}]" if r.get("hl_ci") else "-"
        L.append(f"| {r['label']} | {r['setting']} | {r['status']} | {r.get('n') or '-'} | {fmt(r.get('p'))} | "
                 f"{fmt(r.get('hl'))} | {ci} |")
    return "\n".join(L)


def md_criteria(an_list):
    L = ["| Scenario@grade | n (per method; paired) | Criterion | Result | Value | Detail |", "|---|---|---|---|---|---|"]
    for a in an_list:
        nb = ", ".join(f"{m}:{n}" for m, n in a["n_by_method"].items()) or "no data"
        first = True
        for c in a["criteria"]:
            flag = " †" if c["registry_blocked_flag"] else ""
            det = (c["detail"] or "").replace("|", "/")
            L.append(f"| {a['rid'] if first else ''} | {(nb + '; paired ' + str(a['n_paired'])) if first else ''} | "
                     f"{c['criterion']} | {c['status']}{flag} | {fmt(c['value'])} | {det} |")
            first = False
    L.append("")
    L.append("† The registry still flags this criterion `blocked_by_D047` (pre-gate flag). The D-047 gate was cleared in "
             "D-080 (results/GATE_D047.json), so the criterion's own outcome is shown instead of 'BLOCKED'. "
             "'not-evaluable' = a needed arm/seed is missing, the criterion is descriptive only, or it needs data not "
             "yet produced (pending tasks).")
    return "\n".join(L)


def md_safety(an_list):
    L = ["Primary: mean_defended ≤ mean_undefended + 3σ_nom (σ_nom: MEMS 1.180 m, tactical 1.122 m). Secondary: paired HL "
         "difference (defended − undefended) with 95% BCa CI. Defended = `fedqpnt_local`, undefended = `undefended`; "
         "field = `max_h_att` (the registry's never-worse field; `max_h_pre` for the attack-free S1).\n",
         "| Scenario@grade | field | n | mean def | mean undef | margin | 3σ_nom | Primary | HL (def−undef) | 95% BCa CI | CI excludes 0 |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in an_list:
        s = a["safety"]
        if not s:
            continue
        ci = f"[{fmt(s['hl_ci95'][0])}, {fmt(s['hl_ci95'][1])}]" if s["hl_ci95"] else "-"
        ex = "-"
        if s["hl_ci95"]:
            ex = "yes" if (s["hl_ci95"][0] > 0 or s["hl_ci95"][1] < 0) else "no"
        part = " (PARTIAL)" if s["partial"] else ""
        L.append(f"| {a['rid']} | {s['field']} | {s['n']}{part} | {fmt(s['mean_def'])} | {fmt(s['mean_undef'])} | "
                 f"{fmt(s['margin'])} | {fmt(s['bound_3sigma'])} | {'PASS' if s['primary_pass'] else 'FAIL'} | "
                 f"{fmt(s['hl'])} | {ci} | {ex} |")
    return "\n".join(L)


def md_metrics(an_list):
    L = ["Entries are mean ± 95% t-interval half-width over the seeds available per method (n shown); RMSE/max in metres "
         "(`rmse_h_*`, `max_h_att`), FAR per hour, `latency_on` in s (censored at t_off − t_on for misses, D-068), "
         "`rmse_t_ns` in ns (timing). '-' = not defined/not available.\n"]
    for a in an_list:
        if not a["table"]:
            L.append(f"#### {a['rid']} — {a['title']}\n\n_no data yet_\n")
            continue
        L.append(f"#### {a['rid']} — {a['title']}\n")
        L.append("| method | n | " + " | ".join(TABLE_FIELDS) + " |")
        L.append("|---|---|" + "---|" * len(TABLE_FIELDS))
        for m, row in a["table"].items():
            cells = []
            for f in TABLE_FIELDS:
                c = row[f]
                if c["mean"] is None:
                    cells.append("-")
                else:
                    cells.append(f"{fmt(c['mean'], 4)} ± {fmt(c['ci'], 3)}" if c["ci"] is not None else fmt(c["mean"], 4))
            L.append(f"| {m} | {a['n_by_method'].get(m, 0)} | " + " | ".join(cells) + " |")
        L.append("")
    return "\n".join(L)


def md_exploratory(an_by_rid, h2, h1_tac):
    L = ["All of this section is EXPLORATORY (PREREG_M4 §6): no multiplicity control, no pass/fail beyond what the "
         "registry defines, not part of the Holm family.\n"]
    # S6-coast
    L.append("### 4.1 S6-coast — CAI coasting benefit (180 s forced outage; max horizontal coasting error)\n")
    L.append("| grade | n | median max-error (−quantum) | median max-error (CAI) | median ratio (−quantum / CAI) | HL (CAI − −quantum) | 95% BCa CI |")
    L.append("|---|---|---|---|---|---|---|")
    for g in GRADES:
        a = an_by_rid.get(f"S6-coast@{g}")
        if not a or "coast" not in a["extra"]:
            L.append(f"| {g} | pending | - | - | - | - | - |")
            continue
        c = a["extra"]["coast"]
        t = a["table"]
        ci = f"[{fmt(c['hl_ci95'][0])}, {fmt(c['hl_ci95'][1])}]" if c["hl_ci95"] else "-"
        L.append(f"| {g} | {c['n']} | {fmt(t['abl_minus_quantum']['max_h_att']['mean'])} (mean) | "
                 f"{fmt(t['fedqpnt_local']['max_h_att']['mean'])} (mean) | {fmt(c['median_ratio_minusq_over_cai'])} | "
                 f"{fmt(c['hl_cai_minus_minusq'])} | {ci} |")
    L.append("\n(Table cells for the two arms are means of the per-seed max error; see §3 for full rows.)\n")
    # S2-DM
    L.append("### 4.2 S2-DM — displaced meaconer (defended vs undefended vs Baseline A)\n")
    L.append("Criteria and safety rows for S2-DM are in §2/§3 per grade; position and timing RMSE below.\n")
    L.append("| grade | method | n | rmse_h_att | rmse_t_ns | latency_on |")
    L.append("|---|---|---|---|---|---|")
    for g in GRADES:
        a = an_by_rid.get(f"S2-DM@{g}")
        if not a:
            continue
        for m in ("fedqpnt_local", "baseline_a", "undefended"):
            if m not in a["table"]:
                continue
            r = a["table"][m]
            f = lambda k: (f"{fmt(r[k]['mean'])} ± {fmt(r[k]['ci'], 3)}" if r[k]["mean"] is not None and r[k]["ci"] is not None
                           else fmt(r[k]["mean"]))
            L.append(f"| {g} | {m} | {a['n_by_method'].get(m, 0)} | {f('rmse_h_att')} | {f('rmse_t_ns')} | {f('latency_on')} |")
    # timing
    L.append("\n### 4.3 Timing RMSE (clock/time error, ns) across attacked scenarios — defended vs undefended\n")
    L.append("| scenario@grade | n def | rmse_t_ns defended | n undef | rmse_t_ns undefended |")
    L.append("|---|---|---|---|---|")
    for rid, a in an_by_rid.items():
        t = a["table"]
        if DEFENDED in t and UNDEFENDED in t and t[DEFENDED]["rmse_t_ns"]["mean"] is not None:
            d, u = t[DEFENDED]["rmse_t_ns"], t[UNDEFENDED]["rmse_t_ns"]
            L.append(f"| {rid} | {d['n']} | {fmt(d['mean'])} ± {fmt(d['ci'], 3)} | {u['n']} | "
                     f"{fmt(u['mean'])} ± {fmt(u['ci'], 3)} |")
    # H2 secondaries
    L.append("\n### 4.4 H2/H4 secondary and tertiary metrics (D-081 file; uncorrected, exploratory)\n")
    L.append("| part | metric | FedQPNT mean | B-cont mean | paired diff (mean) | Wilcoxon p (uncorrected) |")
    L.append("|---|---|---|---|---|---|")
    for blk in ("h2_abrupt", "h4_abrupt", "control_drift"):
        part = h2["parts"][blk]
        for mk in ("auc_n10", "auc_n5", "full_window_auc", "recovery_alarm_rate"):
            sa = part["summary"]["fedqpnt_local"][mk]
            sb = part["summary"]["baseline_b_cont"][mk]
            w = part["paired_wilcoxon_fedqpnt_vs_bcont"][mk]
            L.append(f"| {blk} | {mk} | {fmt(sa['mean'])} ± {fmt(sa['ci95'], 3)} | {fmt(sb['mean'])} ± {fmt(sb['ci95'], 3)} | "
                     f"{fmt(w['diff_mean'])} | {fmt(w['wilcoxon_p'])} |")
    L.append("\nPer-family detection AUC (PREREG §6): the campaign records carry no per-family AUC for the single-node "
             "scenarios; the only AUC values available are the H2/H4 onset AUCs above and the fleet `auc` fields of the "
             "fleet scenarios (S5, S8, S9, S12, S15; pending).")
    return "\n".join(L)


def md_completeness(comp, all_final):
    L = ["## DATA COMPLETENESS", "",
         f"Generated {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} from `results/m4` against `results/m4/manifest.json`.",
         "",
         f"- Expected tasks: **{comp['expected']}**; present (status ok): **{comp['present']}**; "
         f"**missing: {comp['missing_n']}** ({100 * comp['missing_n'] / max(1, comp['expected']):.1f}%).",
         f"- Result files with status != ok (failed): {len(comp['failed'])}",
         f"- Missing tasks with a live `.claim` file (in progress): {len(comp['in_progress_claims'])}",
         f"- Confirmatory family complete (all 8 tests have final inputs): **{'YES' if all_final else 'NO — INCOMPLETE — pending'}**",
         ""]
    if comp["missing_n"]:
        L += ["Every missing task, grouped by result id and method (seed ranges; full list in `results/m3/completeness.json`):", "",
              "| result id | method | #missing | missing seeds |", "|---|---|---|---|"]
        for rid in sorted(comp["missing"]):
            for m, sds in sorted(comp["missing"][rid].items()):
                L.append(f"| {rid} | {m} | {len(sds)} | {seed_ranges(sds) if len(sds) < N_SEEDS else 'all (10000-10029)'} |")
    if comp["failed"]:
        L += ["", "Failed (status != ok):", ""] + [f"- {x}" for x in comp["failed"]]
    return "\n".join(L)



def provenance_lines(prov):
    """Summarise results/m4/_provenance.json and independently re-check that fedqpnt/ is unchanged."""
    import subprocess
    L = []
    entries = prov if isinstance(prov, list) else ([prov] if prov else [])
    if not entries:
        return ["`results/m4/_provenance.json` not written yet (campaign running)."]
    for i, e in enumerate(entries):
        L.append(f"- record {i}: valid={e.get('valid')}; reasons={e.get('reasons')}; start HEAD "
                 f"`{str(e.get('start', {}).get('head'))[:10]}` -> end HEAD `{str(e.get('end', {}).get('head'))[:10]}`; "
                 f"dirty files at start/end: {e.get('start', {}).get('dirty_files')} / {e.get('end', {}).get('dirty_files')}")
    try:
        st, en = entries[0]["start"]["head"], entries[-1]["end"]["head"]
        d = subprocess.run(["git", "diff", "--stat", st, en, "--", "fedqpnt"], cwd=ROOT, capture_output=True, text=True)
        g = subprocess.run(["git", "status", "--porcelain", "--", "fedqpnt"], cwd=ROOT, capture_output=True, text=True)
        L.append(f"- independent check (this script): `git diff --stat {st[:10]} {en[:10]} -- fedqpnt` is "
                 f"{'EMPTY' if not d.stdout.strip() else 'NOT EMPTY: ' + d.stdout.strip()[:300]}; "
                 f"`git status --porcelain -- fedqpnt` is {'clean' if not g.stdout.strip() else 'DIRTY: ' + g.stdout.strip()[:300]}.")
    except Exception as exc:     # noqa: BLE001
        L.append(f"- independent fedqpnt/ diff check failed: {exc}")
    return L

# ----------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-root", default="results/m4")
    ap.add_argument("--out-md", default="docs/M3_REPORT.md")
    ap.add_argument("--out-json", default="results/m3")
    ap.add_argument("--sigma", default="results/sigma_nom.json")
    ap.add_argument("--h2", default=H2_FREEZE4)
    args = ap.parse_args()
    run_root = args.run_root
    out_json = Path(args.out_json)
    out_json.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((Path(run_root) / "manifest.json").read_text())
    sigma = M.load_sigma_nom(args.sigma)
    h2 = json.loads(Path(args.h2).read_text())
    prov = {}
    pp = Path(run_root) / "_provenance.json"
    if pp.exists():
        prov = json.loads(pp.read_text())

    comp = completeness(manifest, run_root)
    rows, all_final = confirmatory(run_root, comp, args.sigma, h2)
    h1_tac = h1_tactical_exploratory(run_root, comp, args.sigma)

    methods_by_rid = {rid: list(bym) for rid, bym in comp["expected_map"].items()}
    an_list, an_by_rid = [], {}
    for rid in methods_by_rid:
        a = analyse_rid(rid, methods_by_rid[rid], run_root, sigma)
        an_list.append(a)
        an_by_rid[rid] = a
        print(f"[m3] {rid}: n={a['n_by_method']} paired={a['n_paired']}", flush=True)

    # ---- JSON outputs
    (out_json / "completeness.json").write_text(json.dumps(clean({k: v for k, v in comp.items() if k != "expected_map"}), indent=1))
    (out_json / "confirmatory.json").write_text(json.dumps(clean(dict(family_complete=all_final, m=8, tests=rows,
                                                                       exploratory_h1_tactical=h1_tac)), indent=1))
    (out_json / "scenario_criteria.json").write_text(json.dumps(clean({a["rid"]: dict(n_by_method=a["n_by_method"], n_paired=a["n_paired"], criteria=a["criteria"]) for a in an_list}), indent=1))
    (out_json / "safety.json").write_text(json.dumps(clean({a["rid"]: a["safety"] for a in an_list if a["safety"]}), indent=1))
    (out_json / "metrics_table.json").write_text(json.dumps(clean({a["rid"]: dict(n_by_method=a["n_by_method"], table=a["table"]) for a in an_list}), indent=1))
    (out_json / "exploratory.json").write_text(json.dumps(clean({a["rid"]: a["extra"] for a in an_list if a["extra"]}), indent=1))

    # ---- Markdown
    L = ["# M3 results report — FedQPNT test-seed campaign (M4)", "",
         f"_Generated by `scripts/m3_report.py`; PREREG_M4.md is binding (D-002: reported as measured; nothing post-hoc)._", ""]
    L.append(md_completeness(comp, all_final))
    L += ["", "### Provenance (D-062/D-077)", ""] + provenance_lines(prov)
    L += ["", f"kappa_R_status stamp: `{SC.KAPPA_R_STATUS}`. Code `core-freeze-4`; detector `results/m1/detector_weights_sup_v3.npz`; "
              "test seeds 10000-10029.", ""]
    L += ["## 1. Confirmatory family (8 tests, Holm, fixed m = 8)", "", md_confirmatory(rows, all_final, h1_tac), ""]
    L += ["## 2. Scenario acceptance criteria per scenario × grade", "", md_criteria(an_list), ""]
    L += ["## 3. Safety principle and main metric tables", "", "### 3.1 Safety principle (defended vs undefended)", "",
          md_safety(an_list), "", "### 3.2 Per-scenario metric tables (all methods)", "", md_metrics(an_list), ""]
    L += ["## 4. Exploratory analyses", "", md_exploratory(an_by_rid, h2, h1_tac), ""]
    L.append("## 5. Provenance of constants\n\nσ_nom = " + ", ".join(f"{g}: {v:.4f} m" for g, v in sigma.items()) +
             " (D-068, frozen); S7 chattering bound 223 trust cycles/h (D-075); censoring 60 s (event) / t_off−t_on (other), D-068.")
    Path(args.out_md).write_text("\n".join(L) + "\n", encoding="utf8")
    print(f"[m3] wrote {args.out_md} and {out_json}/*.json; family_complete={all_final}; missing={comp['missing_n']}")


if __name__ == "__main__":
    main()
