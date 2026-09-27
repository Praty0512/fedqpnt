"""Generate validation plots (results/attacks/) and runtime benchmark for the
GNSS + attacks layer. Not a test; run manually / by CI as a validation step.
"""
from __future__ import annotations

import time
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fedqpnt.core.seeding import stream
from fedqpnt.gnss.signal import GnssSignalModel
from fedqpnt.gnss.receiver import GnssReceiver
from fedqpnt.attacks.spoofing import DriftInSpoof, MeaconingReplay, AbruptSpoof
from fedqpnt.attacks.jamming import Jamming, JamThenSpoof

from _helpers import static_truth

OUT = os.path.join(os.path.dirname(__file__), "..", "results", "attacks")
os.makedirs(OUT, exist_ok=True)


def run(attack, duration_s, dt=0.01, seed=123):
    """Solve TWO PARALLEL receivers per epoch: one on the clean epoch, one on
    the attacked epoch derived from that SAME clean epoch. This is the same
    paired-receiver methodology used by tests/test_gnss_raim_calibration.py's
    KS-blindness test -- it isolates the attack's own contribution to
    raim_stat from the (irrelevant, shared) correlated-noise background,
    instead of comparing two different time WINDOWS of a single receiver
    (which conflates the attack effect with the natural drift of the
    autocorrelated Gauss-Markov error processes -- see D-018 bug report:
    that confound made a pre-attack-window "clean" reference disagree with
    the properly-paired KS test by ~2x)."""
    rng_sig = stream(seed, "n", "gnss")
    rng_atk = stream(seed, "n", "attack")
    model = GnssSignalModel(rate_hz=1.0)
    recv_clean = GnssReceiver()
    recv_atk = GnssReceiver()
    n = int(duration_s / dt)
    T, POSERR, CN0, AGC, CLK, RAIM, NSAT, RAIM_CLEAN = [], [], [], [], [], [], [], []
    for k in range(n):
        t = k * dt
        truth = static_truth(t)
        ep = model.step(truth, rng_sig)
        if ep is None:
            continue
        ep2 = attack.apply(ep, truth, rng_atk) if attack is not None else ep
        fc = recv_clean.solve(ep.for_agent())
        fa = recv_atk.solve(ep2.for_agent())
        T.append(t)
        POSERR.append(np.linalg.norm(fa.pos[:2]) if fa.valid else np.nan)
        CN0.append(np.mean([o.cn0_dbhz for o in ep2.obs]) if ep2.obs else np.nan)
        AGC.append(ep2.agc_db)
        CLK.append(fa.clk_bias if fa.valid else np.nan)
        RAIM.append(fa.raim_stat if fa.valid else np.nan)
        RAIM_CLEAN.append(fc.raim_stat if fc.valid else np.nan)
        NSAT.append(fa.num_sats)
    return dict(t=np.array(T), poserr=np.array(POSERR), cn0=np.array(CN0), agc=np.array(AGC),
                clk=np.array(CLK), raim=np.array(RAIM), raim_clean=np.array(RAIM_CLEAN),
                nsat=np.array(NSAT))


def plot_attack(name, data, onset, duration):
    fig, axs = plt.subplots(5, 1, figsize=(9, 12), sharex=True)
    axs[0].plot(data["t"], data["cn0"]); axs[0].set_ylabel("mean C/N0 [dB-Hz]")
    axs[1].plot(data["t"], data["agc"]); axs[1].set_ylabel("AGC [dB]")
    axs[2].plot(data["t"], data["clk"]); axs[2].set_ylabel("clk bias [m]")
    axs[3].plot(data["t"], data["poserr"]); axs[3].set_ylabel("|pos err| [m]")
    axs[4].plot(data["t"], data["raim"]); axs[4].set_ylabel("RAIM chi2"); axs[4].set_xlabel("t [s]")
    for ax in axs:
        ax.axvspan(onset, onset + duration, color="red", alpha=0.1)
        ax.grid(alpha=0.3)
    fig.suptitle(name)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, f"{name}.png"), dpi=110)
    plt.close(fig)


def main():
    scenarios = {
        "clean": (None, 0, 0),
        "drift_spoof": (DriftInSpoof(onset_s=20, align_s=8, duration_s=80, severity=0.8), 20, 80),
        "meaconing": (MeaconingReplay(onset_s=20, duration_s=60, replay_delay_m=1500, severity=1.0), 20, 60),
        "abrupt_spoof": (AbruptSpoof(onset_s=20, duration_s=60, severity=0.8), 20, 60),
        "jam_cw": (Jamming(onset_s=20, duration_s=60, kind="jam_cw",
                            jammer_pos_enu=np.array([1000.0, 0.0, 0.0]), jammer_eirp_dbw=-40.0, severity=1.0), 20, 60),
        "jam_wideband": (Jamming(onset_s=20, duration_s=60, kind="jam_wideband",
                                  jammer_pos_enu=np.array([1000.0, 0.0, 0.0]), jammer_eirp_dbw=-40.0, severity=1.0), 20, 60),
        "jam_wideband_strong": (Jamming(onset_s=20, duration_s=60, kind="jam_wideband",
                                  jammer_pos_enu=np.array([80.0, 0.0, 0.0]), jammer_eirp_dbw=20.0, severity=1.0), 20, 60),
    }
    jam = Jamming(onset_s=15, duration_s=15, kind="jam_wideband",
                  jammer_pos_enu=np.array([400.0, 0.0, 0.0]), jammer_eirp_dbw=5.0, severity=0.6)
    spoof = DriftInSpoof(onset_s=32, align_s=3, duration_s=50, severity=0.6)
    scenarios["jam_then_spoof"] = (JamThenSpoof(jam=jam, spoof=spoof), 15, 67)

    def mstd(x):
        x = x[~np.isnan(x)]
        return (float(x.mean()), float(x.std())) if x.size else (float("nan"), float("nan"))

    header = ("scenario | cn0_clean_pre-onset(mean+-std) | cn0_attacked(mean+-std) | "
              "poserr_attacked(mean+-std) | raim_clean_PAIRED_same_window(mean+-std) | raim_attacked(mean+-std) | note")
    summary_lines = [header]

    # dedicated clean-only run for a stable clean RAIM/poserr/cn0 reference row
    clean_data = run(None, duration_s=200.0)
    cn0_c = mstd(clean_data["cn0"])
    poserr_c = mstd(clean_data["poserr"])
    raim_c = mstd(clean_data["raim"])
    summary_lines.append(
        f"clean | {cn0_c[0]:.2f}+-{cn0_c[1]:.2f} | -- | {poserr_c[0]:.2f}+-{poserr_c[1]:.2f} | "
        f"{raim_c[0]:.3f}+-{raim_c[1]:.3f} | -- | reference (no attack)")

    for name, (atk, onset, duration) in scenarios.items():
        if name == "clean":
            continue
        data = run(atk, duration_s=max(onset + duration + 20, 130))
        plot_attack(name, data, onset, duration)
        mask_pre = data["t"] < max(onset - 2, 1)          # for the cn0 "before" column only
        mask_atk = (data["t"] >= onset + 3) & (data["t"] < onset + duration)
        cn0_clean = mstd(data["cn0"][mask_pre])
        cn0_atk = mstd(data["cn0"][mask_atk])
        poserr_atk = mstd(data["poserr"][mask_atk])
        # paired reference: clean receiver's raim over the SAME window as the
        # attack, not an earlier pre-attack window (D-018 fix -- see run()).
        raim_clean_local = mstd(data["raim_clean"][mask_atk])
        raim_atk = mstd(data["raim"][mask_atk])
        note = "TOTAL DENIAL (no valid fix)" if mask_atk.any() and np.all(np.isnan(data["poserr"][mask_atk])) else ""
        summary_lines.append(
            f"{name} | {cn0_clean[0]:.2f}+-{cn0_clean[1]:.2f} | {cn0_atk[0]:.2f}+-{cn0_atk[1]:.2f} | "
            f"{poserr_atk[0]:.2f}+-{poserr_atk[1]:.2f} | {raim_clean_local[0]:.3f}+-{raim_clean_local[1]:.3f} | "
            f"{raim_atk[0]:.3f}+-{raim_atk[1]:.3f} | {note}")

    with open(os.path.join(OUT, "signature_summary.txt"), "w") as f:
        f.write("\n".join(summary_lines))
    print("\n".join(summary_lines))

    # A1 (ratified): DOP-distribution sanity print for the synthetic Walker
    # almanac -- PDOP should be a sane, bounded, elevation-mask-consistent
    # spread (not blown up / not degenerate), sampled across the sim window.
    dop_data = run(None, duration_s=1800.0)
    pdops = []
    rng_sig_dop = stream(777, "dop", "gnss")
    model_dop = GnssSignalModel(rate_hz=1.0)
    recv_dop = GnssReceiver()
    for k in range(1800):
        t = k * 1.0
        truth = static_truth(t)
        ep = model_dop.step(truth, rng_sig_dop)
        if ep is None:
            continue
        fix = recv_dop.solve(ep.for_agent())
        if fix.valid and not np.isnan(fix.pdop):
            pdops.append(fix.pdop)
    pdops = np.array(pdops)
    dop_lines = [
        "PDOP distribution sanity (synthetic Walker almanac, 10 deg mask, 30 min static, 1 Hz):",
        f"  n={len(pdops)}  mean={pdops.mean():.2f}  std={pdops.std():.2f}  "
        f"min={pdops.min():.2f}  max={pdops.max():.2f}  p95={np.percentile(pdops, 95):.2f}",
    ]
    with open(os.path.join(OUT, "dop_distribution.txt"), "w") as f:
        f.write("\n".join(dop_lines))
    print("\n".join(dop_lines))

    # severity sweep: jamming C/N0 drop vs severity
    sev_list = [0.2, 0.4, 0.6, 0.8, 1.0]
    cn0_drops = []
    for s in sev_list:
        atk = Jamming(onset_s=10, duration_s=20, jammer_pos_enu=np.array([80.0, 0.0, 0.0]),
                      jammer_eirp_dbw=20.0, severity=s)
        data = run(atk, duration_s=40)
        cn0_clean = np.nanmean(data["cn0"][data["t"] < 8])
        cn0_atk = np.nanmean(data["cn0"][(data["t"] >= 13) & (data["t"] < 28)])
        cn0_drops.append(cn0_clean - cn0_atk)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(sev_list, cn0_drops, marker="o")
    ax.set_xlabel("severity"); ax.set_ylabel("mean C/N0 drop [dB]"); ax.grid(alpha=0.3)
    ax.set_title("Jamming severity sweep")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "jamming_severity_sweep.png"), dpi=110)
    plt.close(fig)

    # runtime benchmark: per simulated hour at 1 Hz and 10 Hz
    bench_lines = ["rate_hz | sim_hours | wall_s | wall_s_per_sim_hour"]
    for rate_hz in (1.0, 10.0):
        rng_sig = stream(555, "bench", "gnss")
        model = GnssSignalModel(rate_hz=rate_hz)
        recv = GnssReceiver()
        dt = 0.01
        sim_hours = 0.05  # 3 minutes simulated, scaled to per-hour
        n = int(sim_hours * 3600 / dt)
        t0 = time.perf_counter()
        for k in range(n):
            t = k * dt
            truth = static_truth(t)
            ep = model.step(truth, rng_sig)
            if ep is None:
                continue
            recv.solve(ep.for_agent())
        wall = time.perf_counter() - t0
        wall_per_hour = wall / sim_hours
        bench_lines.append(f"{rate_hz} | {sim_hours} | {wall:.3f} | {wall_per_hour:.3f}")
    with open(os.path.join(OUT, "runtime_benchmark.txt"), "w") as f:
        f.write("\n".join(bench_lines))
    print("\n".join(bench_lines))


if __name__ == "__main__":
    main()
