"""FIX7: COMPARE.md for up to three mini-matrix roots (first = current, e.g. f7; then f6; then f5). Medians over seeds.
Usage: python scripts/minimatrix_compare3.py OUT.md f7=results/minimatrix_f7 f6=results/minimatrix_f6 f5=../FEDQPNT_f5/results/minimatrix_f5
Writes: KEY table, FLAGS (defended worse than undefended / baseline_a in the FIRST root), M3 safety margin, ANOMALY scan
(NaN, status!=ok, km-scale error on short clean scenarios, fpr>0.5 on clean data), per-cell tables."""
import json, math, sys, glob
from pathlib import Path
import numpy as np
sys.path.insert(0, ".")
from fedqpnt.eval import scenarios as SC

OUT = Path(sys.argv[1])
ROOTS = [(a.split("=", 1)[0], Path(a.split("=", 1)[1])) for a in sys.argv[2:]]
SIG = json.load(open("results/sigma_nom_freeze5.json"))["sigma_nom_m"]
MET = ["rmse_h_pre", "rmse_h_att", "rmse_h_post", "max_h_att", "fpr", "latency_on", "t_rec", "mean_w_gnss_att", "round_installs", "auc"]
DEF = ("fedqpnt_local", "fedqpnt")
KEY = ["S1", "S2-low", "S2-med", "S2-high", "S2-DM", "S3", "S4", "S6", "S6-coast", "S7-p10", "S7-p60", "S11", "S13", "S14"]


def load(root):
    d = {}
    for f in glob.glob(str(root / "*" / "*" / "seed_*.json")):
        p = Path(f)
        try:
            r = json.load(open(f))
        except Exception:
            continue
        d.setdefault((p.parts[-3], p.parts[-2]), []).append(r)
    return d


def vals(rs, k):
    out = []
    for r in rs:
        x = (r.get("metrics") or {}).get(k)
        if isinstance(x, (int, float)) and r.get("status") == "ok":
            out.append(float(x))
    return out


def med(rs, k):
    v = vals(rs, k)
    if not v:
        return None
    a = np.array(v)
    return float("nan") if np.isnan(a).all() else float(np.nanmedian(a))


def mean_(rs, k):
    v = [x for x in vals(rs, k) if not math.isnan(x)]
    return float(np.mean(v)) if v else None


def fmt(x):
    if x is None:
        return "-"
    if isinstance(x, float) and math.isnan(x):
        return "nan"
    return f"{x:.3g}" if abs(x) < 1e4 else f"{x:.3e}"


data = {t: load(r) for t, r in ROOTS}
cur = ROOTS[0][0]
A = data[cur]
rids = sorted({k[0] for d in data.values() for k in d})
L = [f"# Mini-matrix COMPARE ({', '.join(t for t, _ in ROOTS)}; tuning seeds; medians over seeds; units m, s, ns)", "",
     "'nan' = undefined for all seeds (no such window), '-' = not run in that root. Current = " + cur + ".", ""]

# ---- KEY table
L += ["## KEY cells (fedqpnt_local / fedqpnt; undefended and baseline_a from the current root)", "",
      "| rid | grade | metric | " + " | ".join(t for t, _ in ROOTS) + " | undefended | baseline_a |", "|---|---|---|" + "---|" * (len(ROOTS) + 2)]
for base in KEY:
    for grade in ("industrial_mems", "tactical"):
        rid = f"{base}@{grade}"
        if not any(k[0] == rid for k in A):
            continue
        dm = next((m for m in DEF if (rid, m) in A), None)
        for k in ("rmse_h_pre", "rmse_h_att", "rmse_h_post", "max_h_att", "fpr"):
            row = []
            for t, _ in ROOTS:
                rs = data[t].get((rid, dm))
                row.append(fmt(med(rs, k)) if rs else "-")
            ud = A.get((rid, "undefended")); ba = A.get((rid, "baseline_a"))
            row += [fmt(med(ud, k)) if ud else "-", fmt(med(ba, k)) if ba else "-"]
            if all(c in ("-", "nan") for c in row):
                continue
            L.append(f"| {base} | {grade} | {k} | " + " | ".join(row) + " |")
L.append("")

flags, anomalies, safety, scan = [], [], [], []
body = []
for rid in rids:
    base, grade = (rid.split("@") + ["industrial_mems"])[:2]
    methods = sorted({k[1] for d in data.values() for k in d if k[0] == rid})
    body += [f"## {rid}", "", "| method | ver | n(ok/tot) | " + " | ".join(MET) + " |", "|---|---|---|" + "---|" * len(MET)]
    for m in methods:
        for t, _ in ROOTS:
            rs = data[t].get((rid, m))
            if not rs:
                continue
            ok = sum(r.get("status") == "ok" for r in rs)
            for r in rs:
                if r.get("status") != "ok":
                    anomalies.append(f"{t} {rid} {m} seed {r.get('seed')}: status={r.get('status')} {str(r.get('stderr', ''))[-160:]!r}")
            body.append(f"| {m} | {t} | {ok}/{len(rs)} | " + " | ".join(fmt(med(rs, k)) for k in MET) + " |")
    body.append("")
    dm = next((m for m in DEF if (rid, m) in A), None)
    if dm is None:
        continue
    for ref in ("undefended", "baseline_a", "baseline_b_cont"):
        if (rid, ref) not in A:
            continue
        for k in ("rmse_h_pre", "rmse_h_att", "rmse_h_post"):
            x, y = med(A[(rid, dm)], k), med(A[(rid, ref)], k)
            if x is None or y is None or math.isnan(x) or math.isnan(y):
                continue
            if x > y and x - y > 0.5:
                flags.append(f"{cur} {rid}: {dm} {k} {fmt(x)} > {ref} {fmt(y)} (x{x / max(y, 1e-9):.1f})")
    if (rid, "undefended") in A:
        sc = SC.get(base)
        fld = "max_h_att" if (sc.attack or sc.attacks) else "max_h_pre"
        md, mu = mean_(A[(rid, dm)], fld), mean_(A[(rid, "undefended")], fld)
        if md is not None and mu is not None:
            b = 3 * SIG[grade]
            safety.append((rid, fld, md, mu, md - mu, b, md - mu <= b))
    # anomaly scan on the current root, defended method, per seed
    sc = SC.get(base)
    clean = not (sc.attack or sc.attacks)
    for r in A[(rid, dm)]:
        m = r.get("metrics") or {}
        for k, x in m.items():
            if isinstance(x, float) and math.isnan(x) and k in ("rmse_h_pre", "rmse_h_att", "rmse_h_post") and k != "rmse_h_att" and k != "rmse_h_post" and clean:
                scan.append(f"NaN {k}: {rid} {dm} seed {r.get('seed')}")
        if clean and isinstance(m.get("fpr"), (int, float)) and m["fpr"] > 0.5:
            scan.append(f"LOCKOUT fpr={m['fpr']:.3f} on clean {rid} {dm} seed {r.get('seed')}")
        for k in ("rmse_h_pre", "max_h_pre", "rmse_h_att", "max_h_att", "rmse_h_post"):
            x = m.get(k)
            if isinstance(x, (int, float)) and not math.isnan(x) and x > 1000.0 and (clean or k.endswith("pre")) and sc.duration_s <= 700:
                scan.append(f"KM-SCALE {k}={x:.0f} m on short ({sc.duration_s:.0f} s) {'clean ' if clean else ''}{rid} {dm} seed {r.get('seed')}")

L += ["## FLAGS: defended worse than undefended / baseline (median, strict >) in " + cur, ""] + (["- " + f for f in flags] or ["(none)"]) + [""]
L += ["## M3 safety margin (" + cur + "): mean(defended) - mean(undefended) vs 3 sigma_nom", "",
      "| rid | field | mean def | mean undef | margin | 3sigma_nom | pass |", "|---|---|---|---|---|---|---|"]
L += [f"| {r} | {f} | {fmt(a)} | {fmt(b)} | {fmt(c)} | {fmt(d)} | {'PASS' if e else 'FAIL'} |" for r, f, a, b, c, d, e in safety]
L += ["", "## ANOMALY scan (" + cur + ", defended method, per seed)", ""] + (["- " + x for x in scan] or ["(none)"])
L += ["", "## STATUS != ok", ""] + (["- " + x for x in anomalies] or ["(none)"]) + ["", "---", ""] + body
OUT.write_text("\n".join(L), encoding="utf8")
print("wrote", OUT, len(flags), "flags", len(scan), "scan", len(anomalies), "status-anomalies")
