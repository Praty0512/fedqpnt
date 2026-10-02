"""Full raw tables from the persisted decisive runs (results/m1/decisive_v3_raw/<grade>/*.json).
Per grade x scenario x method (7 methods): rmse_h pre/att/post + max (att, post), FAR/h, mean_w_gnss/pos/clk (whole mission and
attack window), rmse_t_ns (whole mission), D-068 primary criterion (mean_defended <= mean_undefended + 3 sigma_nom; metric
rmse_h_pre for nominal scenarios, rmse_h_att otherwise) and the paired Hodges-Lehmann difference with a 95% BCa CI.
Usage: python scripts/core_robust_decisive_report.py [--raw-dir results/m1/decisive_v3_raw]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fedqpnt.eval.metrics import load_sigma_nom  # noqa: E402
from fedqpnt.eval.stats import bca_bootstrap_ci, hodges_lehmann  # noqa: E402
from fedqpnt.node.methods import METHOD_NAMES  # noqa: E402

SCEN_ORDER = ["nominal", "drift_spoof", "meaconing", "jam_cw", "safety_nominal", "safety_drift_s0.0",
              "safety_drift_s0.25", "safety_drift_s0.5", "safety_drift_s1.0"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=str(ROOT / "results" / "m1" / "decisive_v3_raw"))
    a = ap.parse_args()
    sig_all = load_sigma_nom(str(ROOT / "results" / "sigma_nom.json"))
    for gdir in sorted(Path(a.raw_dir).iterdir()):
        if not gdir.is_dir():
            continue
        grade = gdir.name
        sig = sig_all[grade]
        runs = {}
        for f in gdir.glob("*.json"):
            stem = f.stem
            # <scenario>_<method>_<seed>; method names contain underscores, scenario from the known list
            sc = next((s for s in sorted(SCEN_ORDER, key=len, reverse=True) if stem.startswith(s + "_")), None)
            if sc is None:
                continue
            rest = stem[len(sc) + 1:]
            method, seed = rest.rsplit("_", 1)
            runs.setdefault((sc, method), {})[int(seed)] = json.loads(f.read_text(encoding="utf8"))

        def col(sc, m, key):
            d = runs.get((sc, m), {})
            return np.array([float(d[s][key]) if d[s].get(key) is not None else np.nan for s in sorted(d)])

        def seeds(sc, m):
            return sorted(runs.get((sc, m), {}))

        print(f"\n================ GRADE {grade}  sigma_nom={sig:.4f} m (D-068 frozen) ================")
        for sc in SCEN_ORDER:
            if not any(k[0] == sc for k in runs):
                continue
            key = "rmse_h_pre" if "nominal" in sc else "rmse_h_att"
            und = col(sc, "undefended", key)
            thr = float(np.nanmean(und)) + 3.0 * sig
            print(f"\n[{sc}] n_seeds={len(seeds(sc, 'undefended'))}  primary metric={key}  undefended mean={np.nanmean(und):.3f}  "
                  f"threshold={thr:.3f}")
            print(f"  {'method':16s} {'pre':>8s} {'att':>9s} {'max_att':>9s} {'post':>9s} {'max_post':>9s} {'FAR/h':>6s} "
                  f"{'wG':>6s} {'wP':>6s} {'wC':>6s} {'wG_att':>7s} {'wP_att':>7s} {'wC_att':>7s} {'t_ns':>8s} "
                  f"{'prim':>5s} {'HL':>8s} {'95% BCa CI':>20s}")
            for m in METHOD_NAMES:
                if (sc, m) not in runs:
                    continue
                x = col(sc, m, key)
                d = x - und
                ok = np.isfinite(d)
                if m != "undefended" and ok.sum() >= 3 and len(x) == len(und):
                    hl = float(hodges_lehmann(d[ok]))
                    try:
                        lo, hi = bca_bootstrap_ci(d[ok])
                        ci = f"[{lo:8.2f},{hi:8.2f}]"
                    except Exception:
                        ci = "n/a"
                else:
                    hl, ci = float("nan"), "-"
                nm = lambda k: float(np.nanmean(col(sc, m, k))) if len(col(sc, m, k)) else float("nan")
                print(f"  {m:16s} {nm('rmse_h_pre'):8.2f} {nm('rmse_h_att'):9.2f} {nm('max_h_att'):9.1f} {nm('rmse_h_post'):9.2f} "
                      f"{nm('max_h_post'):9.1f} {nm('far_per_hour'):6.2f} {nm('mean_w_gnss'):6.3f} {nm('mean_w_pos'):6.3f} "
                      f"{nm('mean_w_clk'):6.3f} {nm('mean_w_gnss_att'):7.3f} {nm('mean_w_pos_att'):7.3f} {nm('mean_w_clk_att'):7.3f} "
                      f"{nm('rmse_t_ns'):8.1f} {str(bool(np.nanmean(x) <= thr)):>5s} {hl:8.2f} {ci:>20s}")


if __name__ == "__main__":
    main()
