"""Build COMPARE.md from minimatrix result roots (f6 vs f5). Medians over seeds; flags defended-worse cells."""
import json, math, sys, glob, os
from pathlib import Path
import numpy as np
sys.path.insert(0, ".")
from fedqpnt.eval import scenarios as SC

F6, F5 = Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None
OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else F6 / "COMPARE.md"
SIG = json.load(open("results/sigma_nom_freeze5.json"))["sigma_nom_m"]
MET = ["rmse_h_pre", "rmse_h_att", "rmse_h_post", "max_h_att", "fpr", "latency_on", "t_rec", "mean_w_gnss_att",
       "round_installs", "rmse_t_ns"]
DEF = ("fedqpnt_local", "fedqpnt")


def load(root):
    d = {}
    if root is None or not root.exists():
        return d
    for f in glob.glob(str(root / "*" / "*" / "seed_*.json")):
        p = Path(f)
        rid, meth = p.parts[-3], p.parts[-2]
        try:
            r = json.load(open(f))
        except Exception:
            continue
        d.setdefault((rid, meth), []).append(r)
    return d


def med(rs, k):
    v = []
    for r in rs:
        m = r.get("metrics") or {}
        x = m.get(k)
        if isinstance(x, (int, float)) and r.get("status") == "ok":
            v.append(float(x))
    if not v:
        return None, 0
    a = np.array(v)
    n_nan = int(np.isnan(a).sum())
    return (float(np.nanmedian(a)) if n_nan < len(a) else float("nan")), n_nan


def mean_(rs, k):
    v = [float((r.get("metrics") or {}).get(k, np.nan)) for r in rs if r.get("status") == "ok"]
    v = [x for x in v if not math.isnan(x)]
    return float(np.mean(v)) if v else None


def fmt(x):
    if x is None:
        return "-"
    if isinstance(x, float) and math.isnan(x):
        return "nan"
    return f"{x:.3g}" if abs(x) < 1e4 else f"{x:.3e}"


a6, a5 = load(F6), load(F5)
rids = sorted({k[0] for k in a6} | {k[0] for k in a5})
L = ["# Mini-matrix COMPARE (tuning seeds; medians over seeds; f6 = freeze6 branch, f5 = core-freeze-5)", "",
     "Units m, s, ns. 'nan' = metric undefined for all seeds (e.g. no pre-attack/post-attack window). Status!=ok are listed under ANOMALIES.", ""]
flags, anomalies, safety = [], [], []
body = []
for rid in rids:
    base, grade = (rid.split("@") + ["industrial_mems"])[:2]
    methods = sorted({k[1] for k in a6 if k[0] == rid} | {k[1] for k in a5 if k[0] == rid})
    body += [f"## {rid}", "", "| method | ver | n(ok/tot) | " + " | ".join(MET) + " |", "|---|---|---|" + "---|" * len(MET)]
    for m in methods:
        for tag, a in (("f6", a6), ("f5", a5)):
            rs = a.get((rid, m))
            if not rs:
                continue
            ok = sum(r.get("status") == "ok" for r in rs)
            for r in rs:
                if r.get("status") != "ok":
                    anomalies.append(f"{tag} {rid} {m} seed {r.get('seed')}: status={r.get('status')} {str(r.get('stderr',''))[-160:]!r}")
            body.append(f"| {m} | {tag} | {ok}/{len(rs)} | " + " | ".join(fmt(med(rs, k)[0]) for k in MET) + " |")
    body.append("")
    # defended vs undefended / baseline_a (f6 and f5)
    for tag, a in (("f6", a6), ("f5", a5)):
        dm = next((m for m in DEF if (rid, m) in a), None)
        if dm is None:
            continue
        for ref in ("undefended", "baseline_a", "baseline_b_cont"):
            if (rid, ref) not in a:
                continue
            for k in ("rmse_h_pre", "rmse_h_att", "rmse_h_post"):
                x, y = med(a[(rid, dm)], k)[0], med(a[(rid, ref)], k)[0]
                if x is None or y is None or math.isnan(x) or math.isnan(y):
                    continue
                if x > y * 1.0 and x - y > 0.5:
                    flags.append(f"{tag} {rid}: {dm} {k} {fmt(x)} > {ref} {fmt(y)} (x{x/max(y,1e-9):.1f})")
        if (rid, "undefended") in a:
            sc = SC.get(base)
            fld = "max_h_att" if (sc.attack or sc.attacks) else "max_h_pre"
            md, mu = mean_(a[(rid, dm)], fld), mean_(a[(rid, "undefended")], fld)
            if md is not None and mu is not None:
                b = 3 * SIG[grade]
                safety.append((tag, rid, fld, md, mu, md - mu, b, md - mu <= b))
L += ["## FLAGS: defended worse than undefended / baseline (median, strict >)", ""] + (["- " + f for f in flags] or ["(none)"]) + [""]
L += ["## M3 safety margin: mean(defended) - mean(undefended) vs 3 sigma_nom (field max_h_att, or max_h_pre when no attack window)", "",
      "| ver | rid | field | mean def | mean undef | margin | 3sigma_nom | pass |", "|---|---|---|---|---|---|---|---|"]
L += [f"| {t} | {r} | {f} | {fmt(a)} | {fmt(b)} | {fmt(c)} | {fmt(d)} | {'PASS' if e else 'FAIL'} |" for t, r, f, a, b, c, d, e in safety]
L += ["", "## ANOMALIES (status != ok)", ""] + (["- " + x for x in anomalies] or ["(none)"]) + ["", "---", ""] + body
OUT.write_text("\n".join(L), encoding="utf8")
print("wrote", OUT, len(flags), "flags", len(anomalies), "anomalies")
