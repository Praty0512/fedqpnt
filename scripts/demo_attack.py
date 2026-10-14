"""Live demo: FedQPNT under the registry scenario S2-DM (displaced meaconer), one TUNING seed.

  python scripts/demo_attack.py [--seed N] [--grade industrial_mems|tactical] [--outdir results/demo]

Runs fedqpnt_local, undefended and baseline_a on the same seed (3 processes in parallel), re-traces the
per-epoch signals with the SAME loop/metric functions as fedqpnt.node.runner.run_single (no frozen code is
modified; the runner only returns summary scalars, so the traces are re-collected here), and writes a
three-panel figure + JSON summary. Test seeds (>= 10000) are refused.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

SCEN = "S2-DM"
WEIGHTS = REPO / "results" / "m1" / "detector_weights_sup_v5.npz"
METHODS = ["fedqpnt_local", "undefended", "baseline_a"]
LABEL = {"fedqpnt_local": "FedQPNT", "undefended": "Undefended", "baseline_a": "Baseline A (detect-and-exclude)"}
COLOR = {"fedqpnt_local": "#1b6ca8", "undefended": "#c0392b", "baseline_a": "#7f8c8d"}


def trace(args):
    """One run; returns per-epoch traces (same loop as runner.run_single)."""
    method, seed, grade = args
    from fedqpnt.core.seed_gate import enforce_seed
    from fedqpnt.eval import campaign as C, metrics as M, scenarios as SC
    from fedqpnt.node.agent import Agent
    from fedqpnt.node.environment import EnvConfig, NodeEnvironment
    from fedqpnt.node.methods import make_agent_config
    from fedqpnt.node.runner import RunSpec, _level_att, G0

    enforce_seed(seed, final=False)
    sc = SC.get(SCEN)
    spec = RunSpec(**C.build_spec_dict(sc, method, seed, detector_weights_path=str(WEIGHTS), imu_grade=grade))
    env = NodeEnvironment(EnvConfig(platform=spec.platform, world=spec.world, imu_grade=spec.imu_grade,
                                    quantum_grade=spec.quantum_grade, gnss_rate_hz=spec.gnss_rate_hz,
                                    hold_s=spec.hold_s, heading_noise_deg=spec.heading_noise_deg,
                                    attacks=[spec.attack], noise_scale=None),
                          seed=seed, node_id=spec.node_id, dt=spec.dt, duration_s=spec.duration_s)
    cfg = make_agent_config(spec.method, kappa_R=spec.kappa_R, kappa_Q=spec.kappa_Q, world=spec.world,
                            quantum_enabled=spec.quantum_grade is not None,
                            detector_weights_path=spec.detector_weights_path, imu_grade=spec.imu_grade,
                            quantum_grade=spec.quantum_grade)
    agent = Agent(cfg, env.imu.config(), node_id=spec.node_id)
    hold, init = [], False
    R = {k: [] for k in ("t", "pos", "tpos", "w_pos", "w_clk", "p", "det", "state", "clk_e", "clk_t", "act")}
    for k in range(len(env)):
        tick = env.tick(k)
        t = tick.t
        if not init:
            if t < env.hold_s:
                if tick.imu is not None:
                    hold.append(tick.imu.f_b)
                continue
            fm = np.mean(hold, axis=0) if hold else np.array([0.0, 0.0, G0])
            ph, th = _level_att(fm)
            agent.initialize_static(t, tick.truth.pos.copy(),
                                    np.array([ph, th, float(tick.truth.att[2]) + env.initial_heading_noise()]))
            init = True
            continue
        a = agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
        w = a.trust.weights
        R["t"].append(t)
        R["pos"].append(a.nav.pos.copy())
        R["tpos"].append(tick.truth.pos.copy())
        R["w_pos"].append(w.get("gnss_pos", w.get("gnss", 1.0)))
        R["w_clk"].append(w.get("gnss_clk", w.get("gnss", 1.0)))
        R["p"].append(a.trust.anomaly_scores.get("gnss", 0.0))
        R["det"].append(bool(a.trust.attack_detected))
        st = "n/a"
        try:   # read-only peek at the GNSS trust law's state machine (TRUST/DISTRUST/PROBE)
            st = agent.trust.gnss_law._core_v2.state
        except Exception:
            pass
        R["state"].append(st)
        R["clk_e"].append(a.clock.bias_m if a.clock is not None else np.nan)
        R["clk_t"].append(tick.true_clk_bias_m)
        R["act"].append(bool(tick.label.spoofing or tick.label.jamming))
    t = np.array(R["t"])
    act = np.array(R["act"])
    ph = M.compute_phases(t, act)
    e_h = M.horizontal_error(np.array(R["pos"]), np.array(R["tpos"]))
    e_clk = M.clock_bias_error_ns(np.array(R["clk_e"]), np.array(R["clk_t"]))
    return dict(method=method, t=t, e_h=e_h, e_clk=e_clk, w_pos=np.array(R["w_pos"]), w_clk=np.array(R["w_clk"]),
                p=np.array(R["p"]), det=np.array(R["det"]), state=np.array(R["state"]),
                t_on=ph.t_on, t_off=ph.t_off,
                rmse_h_pre=M.rmse(e_h, ph.pre), rmse_h_att=M.rmse(e_h, ph.att), rmse_h_post=M.rmse(e_h, ph.post),
                max_h_att=M.max_err(e_h, ph.att), rmse_t_ns=M.rmse_t_ns(e_clk),
                rmse_t_ns_att=M.rmse(e_clk, ph.att))


def first_t(t, mask, after=-np.inf):
    idx = np.flatnonzero(mask & (t >= after))
    return float(t[idx[0]]) if idx.size else None


def make_figure(res, seed, grade, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D

    fq = res["fedqpnt_local"]
    t = fq["t"]
    t_on, t_off = fq["t_on"], fq["t_off"]
    fig, ax = plt.subplots(3, 1, figsize=(12, 11.5), sharex=True,
                           gridspec_kw=dict(height_ratios=[3, 3, 2.2], hspace=0.10))
    for a in ax:
        a.axvspan(t_on, t_off, color="#f5b7b1", alpha=0.35, lw=0, zorder=0)
        a.grid(alpha=0.25, lw=0.6)
    # --- top: position error
    for m in METHODS:
        r = res[m]
        ax[0].plot(r["t"], np.maximum(r["e_h"], 0.1), color=COLOR[m], lw=1.8 if m == "fedqpnt_local" else 1.3,
                   label=f"{LABEL[m]}  (attack RMSE {r['rmse_h_att']:.0f} m)", zorder=3 if m == "fedqpnt_local" else 2)
    ax[0].set_yscale("log")
    ax[0].set_ylabel("Horizontal position error (m)")
    ax[0].set_ylim(0.3, ax[0].get_ylim()[1] * 2.5)
    ax[0].legend(loc="upper left", fontsize=9.5, framealpha=0.95)
    ax[0].text(0.5 * (t_on + t_off), 0.45, "ATTACK WINDOW", ha="center", va="bottom", color="#922b21",
               fontsize=10, weight="bold")
    # --- middle: trust
    state, w = fq["state"], fq["w_pos"]
    cols = dict(TRUST="#d5f5e3", DISTRUST="#fadbd8", PROBE="#fdebd0")
    have_state = bool(np.all(state != "n/a"))
    if not have_state:   # derive from the documented law: w pinned at w_min=0.02 => DISTRUST/PROBE
        state = np.where(w <= 0.021, "DISTRUST", "TRUST")
    i0 = 0
    for i in range(1, len(t) + 1):
        if i == len(t) or state[i] != state[i0]:
            ax[1].axvspan(t[i0], t[min(i, len(t) - 1)], color=cols.get(state[i0], "#eeeeee"), alpha=0.9, lw=0, zorder=0)
            i0 = i
    ax[1].plot(t, w, color="#154360", lw=2.0, zorder=4)
    ax[1].plot(t, np.clip(fq["p"], 0, 1), color="#7d3c98", lw=0.8, alpha=0.8, zorder=3)
    ax[1].set_ylim(-0.04, 1.30)
    ax[1].set_ylabel("Trust weight / score (0..1)")
    ax[1].legend(handles=[Line2D([], [], color="#154360", lw=2, label="$w_{pos}$ (GNSS position trust)"),
                          Line2D([], [], color="#7d3c98", lw=1, label="detector score $p$"),
                          Patch(color=cols["TRUST"], label="TRUST"),
                          Patch(color=cols["DISTRUST"], label="DISTRUST (GNSS excluded, coasting)"),
                          Patch(color=cols["PROBE"], label="PROBE")], loc="upper left", ncol=5, fontsize=8.5,
                 framealpha=0.95, columnspacing=1.0, handlelength=1.4)
    t_drop = first_t(t, w < 0.1, t_on)
    t_probe = first_t(t, state == "PROBE", t_on)
    t_back = first_t(t, state == "TRUST", t_off) if t_drop else None   # first TRUST epoch after the attack ends
    ann = [(t_on, "attack starts", 1.10)]
    if t_drop is not None:
        ann.append((t_drop, "trust drops: GNSS excluded,\ncoasting on INS + quantum", 0.74))
    if t_probe is not None:
        ann.append((t_probe, "probe check\n(after ~60 s)", 0.50))
    if t_back is not None:
        ann.append((t_back, "GNSS re-admitted\n(probe passed)", 0.45))
    for x, txt, y in ann:
        ax[1].axvline(x, color="k", lw=0.9, ls=":", zorder=5)
        ax[1].annotate(txt, xy=(x, y), xytext=(x + 5, y), fontsize=9, ha="left", va="center", zorder=6,
                       bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.5", alpha=0.95))
    # --- bottom: clock
    for m in METHODS:
        r = res[m]
        ok = np.isfinite(r["e_clk"])   # clock estimate exists on 1 Hz GNSS epochs only
        ax[2].plot(r["t"][ok], np.maximum(r["e_clk"][ok], 1.0), color=COLOR[m], lw=1.8 if m == "fedqpnt_local" else 1.3,
                   label=f"{LABEL[m]}  (RMSE {r['rmse_t_ns']:.0f} ns)")
    ax[2].set_yscale("log")
    ax[2].set_ylabel("Clock (timing) error (ns)")
    ax[2].set_xlabel("Time (s)  -  navigation starts after a 30 s static alignment")
    ax[2].legend(loc="center right", fontsize=9, framealpha=0.95)
    ax[2].set_xlim(t[0], t[-1])
    fig.suptitle(f"FedQPNT under a displaced-meaconer attack (seed {seed}, "
                 f"{'industrial MEMS' if grade == 'industrial_mems' else grade})", fontsize=15, weight="bold", y=0.975)
    cap = ("Attack-window RMSE (m): " + ", ".join(f"{LABEL[m].split(' (')[0]} {res[m]['rmse_h_att']:.0f}" for m in METHODS)
           + "  |  Clock RMSE (ns): " + ", ".join(f"{LABEL[m].split(' (')[0]} {res[m]['rmse_t_ns']:.0f}" for m in METHODS)
           + f"\nS2-DM, single tuning seed; trust-state bands {'read from the trust law' if have_state else 'derived from w_pos'}."
             " Red band = attack window.")
    fig.text(0.5, 0.012, cap, ha="center", va="bottom", fontsize=9.5)
    fig.subplots_adjust(top=0.945, bottom=0.095, left=0.075, right=0.985)
    fig.savefig(out_png, dpi=200)
    fig.savefig(Path(out_png).with_suffix(".pdf"))
    plt.close(fig)
    return dict(t_drop=t_drop, t_probe=t_probe, t_readmit=t_back, state_from_law=have_state)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=531)
    ap.add_argument("--grade", choices=["industrial_mems", "tactical"], default="industrial_mems")
    ap.add_argument("--outdir", default=str(REPO / "results" / "demo"))
    a = ap.parse_args()
    assert a.seed < 10000, "demo uses TUNING seeds only (< 10000)"
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print(f"FedQPNT demo: scenario {SCEN} (displaced meaconer: onset 60 s, 300 s, 500 m drift), "
          f"{a.grade}, seed {a.seed}, methods {', '.join(METHODS)}", flush=True)
    print("running 3 methods in parallel (~1-3 min)...", flush=True)
    with ProcessPoolExecutor(max_workers=3) as ex:
        outs = list(ex.map(trace, [(m, a.seed, a.grade) for m in METHODS]))
    res = {r["method"]: r for r in outs}
    suffix = "" if a.grade == "industrial_mems" and a.seed == 531 else f"_{a.grade}_s{a.seed}"
    png = out / f"demo_attack_S2DM{suffix}.png"
    ev = make_figure(res, a.seed, a.grade, png)
    keys = ("rmse_h_pre", "rmse_h_att", "max_h_att", "rmse_h_post", "rmse_t_ns", "rmse_t_ns_att")
    summ = dict(scenario=SCEN, seed=a.seed, imu_grade=a.grade, world="schuler_tangent",
                detector_weights=str(WEIGHTS.relative_to(REPO)),
                attack_window_s=[res["fedqpnt_local"]["t_on"], res["fedqpnt_local"]["t_off"]], fedqpnt_events_s=ev,
                methods={m: {k: float(res[m][k]) for k in keys} for m in METHODS}, wall_s=time.time() - t0)
    (out / (png.stem + "_summary.json")).write_text(json.dumps(summ, indent=2))
    print(f"\nAttack window {summ['attack_window_s'][0]:.0f}-{summ['attack_window_s'][1]:.0f} s")
    print(f"{'method':<16}{'RMSE pre':>10}{'RMSE att':>10}{'max att':>10}{'RMSE post':>11}{'clock RMSE ns':>15}")
    for m in METHODS:
        r = summ["methods"][m]
        print(f"{m:<16}{r['rmse_h_pre']:>10.1f}{r['rmse_h_att']:>10.0f}{r['max_h_att']:>10.0f}"
              f"{r['rmse_h_post']:>11.0f}{r['rmse_t_ns']:>15.0f}")
    print(f"FedQPNT events: {ev}")
    print(f"Figure: {png}\nWall time {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
