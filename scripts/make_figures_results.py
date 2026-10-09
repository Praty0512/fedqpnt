#!/usr/bin/env python
"""Result figures for the M3 report. Reads ONLY results/m3/*.json (written by scripts/m3_report.py) and the H2/H4 D-081
file; writes figures/results_*.pdf + .png (IEEE single-column width 3.5 in, Okabe-Ito colour-blind-safe palette).
Figure (iv) (trust-weight trajectories) is skipped: the campaign result files hold scalar metrics only (no per-epoch
trust trace; RunSpec.record=False), see docs/M3_FIGURE_CAPTIONS.md.

Bars that rest on fewer than 30 seeds are tagged 'n=k' so a partial-data render can never be mistaken for final.
Usage: python scripts/make_figures_results.py [--m3 results/m3] [--out figures] [--h2 <H2 file>] [--sigma results/sigma_nom.json]
Round 2: --m3 results/m4r2/report/json --out results/m4r2/figures --sigma results/sigma_nom_freeze5.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
M3 = ROOT / "results" / "m3"
OUT = ROOT / "figures"
H2 = ROOT / "results" / "fleet" / "h2_abrupt_prereg_results_freeze4.json"
SIGMA3 = {}
GRADES = ("industrial_mems", "tactical")
GLABEL = {"industrial_mems": "Industrial MEMS", "tactical": "Tactical"}
COL = dict(fedqpnt_local="#0072B2", undefended="#D55E00", baseline_a="#009E73", abl_minus_quantum="#CC79A7",
           baseline_b_cont="#E69F00")
LAB = dict(fedqpnt_local="FedQPNT (defended)", undefended="Undefended", baseline_a="Baseline A",
           abl_minus_quantum="FedQPNT without CAI", baseline_b_cont="B-cont")
W = 3.5
plt.rcParams.update({"font.size": 7, "axes.labelsize": 7, "axes.titlesize": 7.5, "legend.fontsize": 6.2,
                     "xtick.labelsize": 6.2, "ytick.labelsize": 6.2, "font.family": "DejaVu Sans",
                     "axes.linewidth": 0.6, "pdf.fonttype": 42, "ps.fonttype": 42, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 150})


def load(name):
    return json.loads((M3 / name).read_text())


def save(fig, stem):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("wrote", OUT / f"{stem}.pdf/.png")


def cell(tab, rid, method, field):
    t = tab.get(rid, {}).get("table", {}).get(method, {}).get(field)
    n = tab.get(rid, {}).get("n_by_method", {}).get(method, 0)
    if not t or t.get("mean") is None:
        return None
    return t["mean"], (t.get("ci") or 0.0), n


def bars(ax, groups, methods, tab, grade, field, ylog=True):
    x = np.arange(len(groups))
    wd = 0.8 / len(methods)
    partial = False
    for k, m in enumerate(methods):
        for i, (gid, _) in enumerate(groups):
            c = cell(tab, f"{gid}@{grade}", m, field)
            if c is None:
                continue
            mean, ci, n = c
            lo = min(ci, mean * 0.9) if ylog else ci
            ax.bar(x[i] + (k - (len(methods) - 1) / 2) * wd, mean, wd * 0.92, color=COL[m],
                   label=LAB[m] if i == 0 else None, yerr=[[lo], [ci]], error_kw=dict(lw=0.6, capsize=1.2))
            if n < 30:
                partial = True
                ax.text(x[i] + (k - (len(methods) - 1) / 2) * wd, mean + ci, f"n={n}", fontsize=4.5, ha="center",
                        va="bottom", rotation=90)
    ax.set_xticks(x)
    ax.set_xticklabels([g[1] for g in groups])
    if ylog:
        ax.set_yscale("log")
    ax.set_title(GLABEL[grade], loc="left")
    return partial


def fig_defended_vs_undefended(tab):
    groups = [("S2-low", "S2\nlow"), ("S2-med", "S2\nmed"), ("S2-high", "S2\nhigh"), ("S2-DM", "S2\nDM"),
              ("S3", "S3\njam"), ("S4", "S4\njam+spoof"), ("S6", "S6\nSchuler")]
    methods = ("fedqpnt_local", "undefended", "baseline_a")
    fig, axs = plt.subplots(2, 1, figsize=(W, 4.3), sharex=True)
    for ax, g in zip(axs, GRADES):
        bars(ax, groups, methods, tab, g, "rmse_h_att")
        ax.set_ylabel("Attack-window RMSE$_h$ (m)")
        ax.grid(axis="y", lw=0.3, alpha=0.5)
    axs[0].legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.28), frameon=False, columnspacing=0.8,
                  handlelength=1.0)
    fig.tight_layout(h_pad=0.6)
    save(fig, "results_defended_vs_undefended")


def fig_coasting(tab):
    fig, axs = plt.subplots(1, 2, figsize=(W, 2.3))
    for ax, g in zip(axs, GRADES):
        rid = f"S6-coast@{g}"
        for k, m in enumerate(("fedqpnt_local", "abl_minus_quantum")):
            c = cell(tab, rid, m, "max_h_att")
            if c is None:
                continue
            ax.bar(k, c[0], 0.7, color=COL[m], yerr=c[1], error_kw=dict(lw=0.6, capsize=1.5))
            if c[2] < 30:
                ax.text(k, c[0] + c[1], f"n={c[2]}", fontsize=5, ha="center", va="bottom")
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["with\nCAI", "without\nCAI"])
        ax.set_title(GLABEL[g], loc="left")
        ax.grid(axis="y", lw=0.3, alpha=0.5)
    axs[0].set_ylabel("Max coasting error (m)")
    fig.tight_layout()
    save(fig, "results_cai_coasting")


def fig_timing(tab):
    methods = ("fedqpnt_local", "baseline_a", "undefended")
    fig, ax = plt.subplots(figsize=(W, 2.3))
    x = np.arange(len(GRADES))
    wd = 0.25
    for k, m in enumerate(methods):
        for i, g in enumerate(GRADES):
            c = cell(tab, f"S2-DM@{g}", m, "rmse_t_ns")
            if c is None:
                continue
            ax.bar(x[i] + (k - 1) * wd, c[0], wd * 0.92, color=COL[m], label=LAB[m] if i == 0 else None,
                   yerr=c[1], error_kw=dict(lw=0.6, capsize=1.5))
            if c[2] < 30:
                ax.text(x[i] + (k - 1) * wd, c[0] + c[1], f"n={c[2]}", fontsize=5, ha="center", va="bottom")
    ax.set_xticks(x)
    ax.set_xticklabels([GLABEL[g] for g in GRADES])
    ax.set_ylabel("Clock RMSE (ns)")
    ax.set_title("Displaced meaconer (S2-DM)", loc="left")
    ax.grid(axis="y", lw=0.3, alpha=0.5)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.18), columnspacing=0.8,
              handlelength=1.0)
    fig.tight_layout()
    save(fig, "results_timing_meaconing")


def fig_h2h4():
    d = json.loads(H2.read_text())
    fig, axs = plt.subplots(1, 2, figsize=(W, 2.5), sharey=True)
    for ax, blk, ttl in zip(axs, ("h2_abrupt", "h4_abrupt"), ("H2 (abrupt)", "H4 (cold start)")):
        ps = d["parts"][blk]["per_seed"]
        a = {r["seed"]: r["auc_n10"] for r in ps["fedqpnt_local"]}
        b = {r["seed"]: r["auc_n10"] for r in ps["baseline_b_cont"]}
        for s in sorted(a):
            ax.plot([0, 1], [a[s], b[s]], color="0.55", lw=0.6, zorder=1)
        ax.scatter(np.zeros(len(a)), [a[s] for s in sorted(a)], s=9, color=COL["fedqpnt_local"], zorder=2)
        ax.scatter(np.ones(len(a)), [b[s] for s in sorted(a)], s=9, color=COL["baseline_b_cont"], zorder=2)
        p = d["parts"][blk]["paired_wilcoxon_fedqpnt_vs_bcont"]["auc_n10"]["wilcoxon_p"]
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["FedQPNT", "B-cont"])
        ax.set_xlim(-0.4, 1.4)
        ax.set_title(f"{ttl}, p={p:.2f}", loc="left")
        ax.grid(axis="y", lw=0.3, alpha=0.5)
    axs[0].set_ylabel("Onset AUC (N=10)")
    fig.tight_layout()
    save(fig, "results_h2h4_auc_paired")


def fig_safety(safety):
    rids = [r for r in safety if safety[r]["hl_ci95"]]
    order = []
    for r in rids:
        base = r.split("@")[0]
        if base not in order:
            order.append(base)
    fig, ax = plt.subplots(figsize=(W, 0.22 * len(order) * 2 + 0.9))
    col = {"industrial_mems": "#0072B2", "tactical": "#E69F00"}
    mark = {"industrial_mems": "o", "tactical": "s"}
    yy = {b: i for i, b in enumerate(order)}
    for r in rids:
        base, g = r.split("@")
        s = safety[r]
        off = -0.17 if g == "industrial_mems" else 0.17
        y = yy[base] + off
        lo, hi = s["hl_ci95"]
        ax.plot([lo, hi], [y, y], color=col[g], lw=1.0)
        ax.plot([s["hl"]], [y], mark[g], color=col[g], ms=3, label=GLABEL[g] if base == order[0] or r == rids[0] else None)
        if s["partial"]:
            ax.text(hi, y, f" n={s['n']}", fontsize=4.5, va="center")
    ax.axvline(0, color="k", lw=0.6)
    for g_, v_ in SIGMA3.items():                   # pre-registered margin 3 sigma_nom per grade (from the sigma file)
        ax.axvline(v_, color=col[g_], lw=0.6, ls=":")
    ax.set_xscale("symlog", linthresh=10)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order)
    ax.invert_yaxis()
    ax.set_xlabel("HL difference, defended $-$ undefended (m), 95% BCa CI")
    ax.grid(axis="x", lw=0.3, alpha=0.5)
    h, l = ax.get_legend_handles_labels()
    uniq = dict(zip(l, h))
    ax.legend(uniq.values(), uniq.keys(), frameon=False, loc="upper left")
    fig.tight_layout()
    save(fig, "results_safety_overview")


def main():
    global M3, OUT, H2
    ap = argparse.ArgumentParser()
    ap.add_argument("--m3", default=str(M3))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--h2", default=str(H2))
    ap.add_argument("--sigma", default=str(ROOT / "results" / "sigma_nom.json"))
    a = ap.parse_args()
    M3, OUT, H2 = Path(a.m3), Path(a.out), Path(a.h2)
    sg = json.loads(Path(a.sigma).read_text())
    sg = sg.get("sigma_nom_m", sg)
    SIGMA3.update({g: 3 * float(sg[g]) for g in GRADES})
    OUT.mkdir(parents=True, exist_ok=True)
    tab = load("metrics_table.json")
    safety = load("safety.json")
    fig_defended_vs_undefended(tab)
    fig_coasting(tab)
    fig_timing(tab)
    print("figure (iv) trust trajectories: SKIPPED (no per-epoch trust data in results/m4 records)")
    fig_h2h4()
    fig_safety(safety)


if __name__ == "__main__":
    main()
