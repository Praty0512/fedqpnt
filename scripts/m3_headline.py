#!/usr/bin/env python
"""Round-3 HEADLINE table (medians/IQR per scenario@grade). EVALUATOR-ONLY, read-only on results/.
Better/worse/equal: paired HL (defended - other) with 95% BCa CI over seeds with both values finite; all listed metrics are
lower-is-better. CI excludes 0 -> better (HL<0) / worse (HL>0); CI includes 0 -> equal (not distinguishable)."""
import json, sys, math
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fedqpnt.eval import report as RP
RUN = ROOT / "results" / "m4r3"
METRICS = ["rmse_h_pre", "rmse_h_att", "rmse_h_post", "fpr", "latency_on", "t_rec", "rmse_t_ns"]
SHORT = {"fedqpnt_local": "FQ", "undefended": "UD", "baseline_a": "BA", "abl_minus_quantum": "-Q"}
OTHERS = ["undefended", "baseline_a", "abl_minus_quantum"]

def load(sid, m):
    out = {}
    for f in (RUN / sid / m).glob("seed_*.json"):
        d = json.loads(f.read_text())
        if d.get("status") == "ok":
            out[d["seed"]] = d["metrics"]
    return out

def g(x):
    return f"{x:.3g}"

def cell(v):
    v = np.array([x for x in v if x is not None and np.isfinite(x)], float)
    if v.size == 0:
        return "-"
    q1, med, q3 = np.percentile(v, [25, 50, 75])
    return f"{g(med)} [{g(q1)}, {g(q3)}] (n={v.size})"

def verdict(a, b):
    ks = sorted(set(a) & set(b))
    x = np.array([a[k] for k in ks], float); y = np.array([b[k] for k in ks], float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if x.size < 5:
        return "n/a"
    if np.all(x == y):
        return "equal (identical)"
    r = RP._paired_stats(x, y, 0)
    hl, (lo, hi) = r["hodges_lehmann"], r["hl_ci95"]
    tag = "equal" if lo <= 0 <= hi else ("BETTER" if hi < 0 else "WORSE")
    return f"{tag} (HL {g(hl)}, CI [{g(lo)}, {g(hi)}])"

man = json.loads((RUN / "manifest.json").read_text())
sids = sorted(p.name for p in RUN.iterdir() if p.is_dir() and "@" in p.name and not p.name.startswith(("S10-", "S5@")) )
sids = [s for s in sids if (RUN / s / "fedqpnt_local").exists()]
L = ["# HEADLINE (round 3, core-freeze-6, seeds 10060-10089, detector v5)", "",
     "Cells: median [Q1, Q3] (n finite seeds). FQ = fedqpnt_local, UD = undefended, BA = baseline_a, -Q = abl_minus_quantum "
     "(S6 / S6-coast only). All metrics lower is better; rmse in m (rmse_t_ns in ns), latency_on in s, t_rec in s, fpr unitless. "
     "Verdict is FQ vs the named arm: paired Hodges-Lehmann (FQ - other) with 95% BCa CI over seeds where both are finite; "
     "BETTER/WORSE = CI excludes 0; equal = CI includes 0. Descriptive, unadjusted (not in the Holm family). "
     "t_rec cells/verdicts use only seeds where t_rec is finite (recovery observed) in both arms, so they are conditional on recovery. Single-arm scenarios (S11, S13, S14) list FQ only. Scenarios with no attack window have NaN attack/post metrics ('-'). Fleet scenarios (S5, S8, S9, S12, S15) and S10-* are not in this table.", ""]
for s in sids:
    meths = [m for m in ("fedqpnt_local", "undefended", "baseline_a", "abl_minus_quantum") if (RUN / s / m).exists()]
    data = {m: load(s, m) for m in meths}
    hdr = ["metric"] + [SHORT[m] for m in meths] + [f"FQ vs {SHORT[m]}" for m in meths[1:]]
    L += [f"## {s}", "", "| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for mt in METRICS:
        col = {m: {k: v.get(mt) for k, v in data[m].items()} for m in meths}
        if all(not any(x is not None and np.isfinite(x) for x in c.values()) for c in col.values()):
            continue
        row = [mt] + [cell(list(col[m].values())) for m in meths] + [verdict(col["fedqpnt_local"], col[m]) for m in meths[1:]]
        L.append("| " + " | ".join(row) + " |")
    L.append("")
out = RUN / "report" / "HEADLINE.md"
out.write_text("\n".join(L) + "\n", encoding="utf8")
print("wrote", out, len(sids), "scenario@grade")
