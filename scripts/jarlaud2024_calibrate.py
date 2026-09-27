"""Calibration pipeline for the Jarlaud et al. 2024 real dataset (WP-2.5 /
D-008). Produces:

  data/processed/jarlaud2024/static_residuals.npz  -- noise-replay input
  data/processed/jarlaud2024/calibration.json       -- fitted parameters
  data/processed/jarlaud2024/contrast_vs_rotation.csv
  results/data/jarlaud2024_adev.png
  results/data/jarlaud2024_streaming_psd.png
  results/data/jarlaud2024_contrast_vs_rotation.png

Owned by DATA-INGEST (WP-2.5). Does not import fedqpnt.sensors or
fedqpnt.core.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from scipy.signal import welch

from fedqpnt.data import jarlaud2024 as j
from fedqpnt.data import allan

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed" / "jarlaud2024"
RESULTS = ROOT / "results" / "data"
PROCESSED.mkdir(parents=True, exist_ok=True)
RESULTS.mkdir(parents=True, exist_ok=True)

G0 = 9.80665  # standard gravity, for g-unit reporting only


def detrend_static_record(accel_mps2: np.ndarray, fs_hz: float) -> tuple[np.ndarray, dict]:
    """Detrend the static accelerometer record.

    The record is 373 s long (Run21, 20230320) -- far too short for a solid-
    Earth tide signal (dominant tidal periods are >= ~12 h) to be resolved or
    meaningfully fit, so no tidal model is applied here. PROPOSED-DECISION:
    detrending is limited to (1) subtracting the mean and (2) subtracting a
    fitted linear drift (captures slow thermal/mechanical drift of the MICAL
    accelerometer over the 373 s window). Document this explicitly since the
    Master's brief anticipated tidal removal for "long enough" records --
    this one is not long enough.
    """
    t = np.arange(len(accel_mps2)) / fs_hz
    mean = float(np.mean(accel_mps2))
    centered = accel_mps2 - mean
    # Linear drift fit.
    A = np.vstack([np.ones_like(t), t]).T
    coeff, *_ = np.linalg.lstsq(A, centered, rcond=None)
    intercept, slope = coeff
    linear_trend = intercept + slope * t
    residual = centered - linear_trend
    meta = {
        "mean_removed_mps2": mean,
        "linear_drift_intercept_mps2": float(intercept),
        "linear_drift_slope_mps2_per_s": float(slope),
        "duration_s": float(len(accel_mps2) / fs_hz),
        "detrend_method": "mean + linear drift (record too short for tidal model)",
    }
    return residual, meta


def gaussian_contrast(omega, c0, omega_c):
    return c0 * np.exp(-((omega / omega_c) ** 2))


def main() -> None:
    # ------------------------------------------------------------------
    # 1) Static record: detrend + Allan deviation + white-noise / floor fit
    # ------------------------------------------------------------------
    rec = j.load_static_record()
    residual, detrend_meta = detrend_static_record(rec.accel_z_mps2, rec.fs_hz)

    assert not np.any(np.isnan(residual))
    assert abs(np.mean(residual)) < 1e-10

    tau, adev, n_clusters = allan.overlapping_adev(residual, rec.fs_hz)
    white_noise_coeff, wn_mask = allan.fit_white_noise_coefficient(tau, adev)
    adev_floor, tau_floor = allan.find_floor(tau, adev)

    # Interferometer cycle rate: from the companion Raman run's RTData
    # timestamps directly (Figure 3 & 5 / 20230320 / Run 21), i.e. every
    # shot (both kD and kU Raman k-reversal directions interlaced -- see
    # "Raman Scan Mode: Phase kInterlaced" in Parameters.txt), NOT the
    # kD-only per-shot join used for the contrast analysis (which halves
    # the apparent rate) and NOT the 2.5 kHz classical-accelerometer stream
    # rate.
    rt_all = j._read_tsv(
        j._run_dir("Figure 3 & 5", "20230320", 21) / "Raman-Run21-RTData.txt"
    )
    ts_all = pd.to_datetime(
        rt_all["Date"] + " " + rt_all["Time"], format="%d/%m/%Y %H:%M:%S.%f"
    )
    t_all = (ts_all - ts_all.iloc[0]).dt.total_seconds().to_numpy()
    cycle_period_s = float(np.median(np.diff(t_all)))
    cycle_rate_hz = 1.0 / cycle_period_s

    # Save the replay input. D-014/PD1: this is CLASSICAL (MICAL)
    # accelerometer noise, not atom-interferometer noise -- renamed from
    # static_residuals.npz and explicitly labelled as such per the Master's
    # ruling. See atom_shot_residuals.npz (scripts/jarlaud2024_atom_residuals.py)
    # for the real atom-derived residuals.
    old_path = PROCESSED / "static_residuals.npz"
    if old_path.exists():
        old_path.unlink()
    np.savez(
        PROCESSED / "mical_static_residuals.npz",
        residual_mps2=residual,
        fs_hz=rec.fs_hz,
        sensor="classical_MICAL",
        source_file=j.STATIC_STREAMING_PATH.relative_to(j.EXTRACTED.parents[0]).as_posix(),
        axis="z (device z-axis, close to vertical/gravity-aligned; theta ~ 0 deg baseline shot)",
        detrend_mean_removed_mps2=detrend_meta["mean_removed_mps2"],
        detrend_linear_slope_mps2_per_s=detrend_meta["linear_drift_slope_mps2_per_s"],
        duration_s=detrend_meta["duration_s"],
    )

    # ADEV-floor confidence interval: the overlapping-ADEV estimator at a
    # given tau has an effective number of independent clusters roughly
    # equal to n_clusters (Riley, NIST SP 1065 Sec. 3.4.3, chi-square
    # approximation); at tau=25.5s (the floor) there are only ~14
    # essentially-independent tau-length segments in this 373s record, so
    # the floor estimate is LOW CONFIDENCE (D-014/PD1). 95% CI via the
    # chi-square distribution of the ADEV variance estimator.
    from scipy import stats

    edf_floor = float(tau_floor and 373.163 / tau_floor)  # ~ n independent segments
    edf_floor = max(edf_floor, 1.0)
    chi2_lo, chi2_hi = stats.chi2.ppf([0.025, 0.975], df=edf_floor)
    adev_floor_ci = [
        float(adev_floor * np.sqrt(edf_floor / chi2_hi)),
        float(adev_floor * np.sqrt(edf_floor / chi2_lo)),
    ]

    # ------------------------------------------------------------------
    # 2) Streaming PSD plot (static vs tapping vs rotating), cf. paper Fig.4
    # ------------------------------------------------------------------
    tapping = j.load_streaming(j.TAPPING_STREAMING_PATH)
    rotating = j.load_streaming(j.ROTATING_STREAMING_PATH)

    fig, ax = plt.subplots(figsize=(7, 5))
    for label, sig, fs, color in [
        ("Static (Run21, 20230320)", residual, rec.fs_hz, "tab:green"),
        ("Forced vibrations / tapping (Fig.4 Run06)", tapping.accel_z_mps2 - np.mean(tapping.accel_z_mps2), tapping.fs_hz, "tab:blue"),
        ("Rotating sensor head (Fig.4 Run19)", rotating.accel_z_mps2 - np.mean(rotating.accel_z_mps2), rotating.fs_hz, "tab:red"),
    ]:
        f, pxx = welch(sig, fs=fs, nperseg=min(8192, len(sig) // 4))
        ax.loglog(f, np.sqrt(pxx) / G0, label=label, color=color, alpha=0.8)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel(r"Acceleration noise ($g/\sqrt{Hz}$)")
    ax.set_title("Classical (MICAL) accelerometer noise -- real data, cf. paper Fig. 4")
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS / "jarlaud2024_streaming_psd.png", dpi=150)
    plt.close(fig)

    # ------------------------------------------------------------------
    # 3) ADEV plot
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.loglog(tau, adev, "o-", ms=3, color="tab:green", label="Overlapping ADEV (static residual)")
    ax.loglog(tau[wn_mask], adev[wn_mask], "o", ms=6, color="tab:orange", label="White-noise fit region")
    tau_fit = np.geomspace(tau[0], tau[-1], 50)
    ax.loglog(tau_fit, white_noise_coeff / np.sqrt(tau_fit), "--", color="tab:orange", label=f"N={white_noise_coeff:.3e} m/s^2/sqrt(Hz)")
    ax.axhline(adev_floor, color="tab:gray", ls=":", label=f"floor={adev_floor:.3e} m/s^2 @ tau={tau_floor:.2g} s")
    ax.set_xlabel("tau (s)")
    ax.set_ylabel("Allan deviation (m/s^2)")
    ax.set_title("Overlapping ADEV, real static classical-accelerometer record")
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS / "jarlaud2024_adev.png", dpi=150)
    plt.close(fig)

    # ------------------------------------------------------------------
    # 4) Contrast vs rotation rate (Figure 2, rigid mode)
    # ------------------------------------------------------------------
    all_omega = []
    all_ratio = []
    for figure, date, run in j.FIGURE2_RIGID_RUNS:
        rr = j.load_raman_run(figure, date, run)
        all_omega.append(rr.rotation_rate_x_rad_s)
        all_ratio.append(rr.ratio)
    omega = np.concatenate(all_omega)
    ratio = np.concatenate(all_ratio)
    r0 = float(np.median(ratio))  # fringe offset R0 (paper: R~0.5 at Omega=0)

    # Envelope extraction: bin |Omega|, take the 95th percentile of
    # |ratio - r0| in each bin as an estimate of C(Omega)/2 (matches the
    # paper's "envelope defined by R0 +/- C(Omega)/2", Fig. 2 caption).
    n_bins = 24
    omega_abs = np.abs(omega)
    bin_edges = np.linspace(0, omega_abs.max(), n_bins + 1)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    envelope = np.full(n_bins, np.nan)
    counts = np.zeros(n_bins, dtype=int)
    for i in range(n_bins):
        sel = (omega_abs >= bin_edges[i]) & (omega_abs < bin_edges[i + 1])
        counts[i] = sel.sum()
        if sel.sum() >= 3:
            envelope[i] = np.percentile(np.abs(ratio[sel] - r0), 95) * 2.0  # *2 -> contrast C

    valid = ~np.isnan(envelope)
    popt, pcov = curve_fit(
        gaussian_contrast,
        bin_centers[valid],
        envelope[valid],
        p0=[envelope[valid][0] if valid.any() else 0.5, 0.1],
        maxfev=10000,
    )
    c0_fit, omega_c_fit = popt
    perr = np.sqrt(np.diag(pcov))

    import csv

    with open(PROCESSED / "contrast_vs_rotation.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["omega_bin_center_rad_s", "n_points", "contrast_envelope"])
        for oc, n_, c_ in zip(bin_centers, counts, envelope):
            writer.writerow([oc, n_, c_])

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(omega, ratio, ".", ms=2, alpha=0.3, color="0.6", label="raw shots (Figure 2, rigid mode)")
    ax.plot(bin_centers[valid], envelope[valid] / 2 + r0, "o", color="tab:red", label="envelope (C/2 + R0)")
    ax.plot(bin_centers[valid], r0 - envelope[valid] / 2, "o", color="tab:red")
    omega_fit_x = np.linspace(0, omega_abs.max(), 200)
    c_fit_y = gaussian_contrast(omega_fit_x, c0_fit, omega_c_fit)
    ax.plot(omega_fit_x, r0 + c_fit_y / 2, "-", color="tab:blue", label=f"fit: C0={c0_fit:.3f}, Omega_c={omega_c_fit:.4f} rad/s")
    ax.plot(-omega_fit_x, r0 + c_fit_y / 2, "-", color="tab:blue")
    ax.plot(omega_fit_x, r0 - c_fit_y / 2, "-", color="tab:blue")
    ax.plot(-omega_fit_x, r0 - c_fit_y / 2, "-", color="tab:blue")
    ax.set_xlabel("Rotation rate Omega (rad/s)")
    ax.set_ylabel("Population ratio R")
    ax.set_title("Contrast loss vs rotation rate (real data, cf. paper Fig. 2)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS / "jarlaud2024_contrast_vs_rotation.png", dpi=150)
    plt.close(fig)

    # ------------------------------------------------------------------
    # 5) calibration.json
    # ------------------------------------------------------------------
    calibration = {
        "source": {
            "doi": "10.1038/s41467-024-50804-0",
            "zenodo": "10.5281/zenodo.11543715",
            "arxiv": "2402.18988",
        },
        # D-014/PD1: classical and atom-sensor numbers are now kept in
        # separate sections and must never be conflated. Classical =
        # Thales MICAL mechanical accelerometer (streaming files). Atom =
        # the interferometer's own population-ratio output, converted to an
        # acceleration residual per-shot (scripts/jarlaud2024_atom_residuals.py,
        # data/processed/jarlaud2024/atom_shot_residuals.npz).
        "classical_accel_mical": {
            "static_record": {
                "path": j.STATIC_STREAMING_PATH.relative_to(j.EXTRACTED.parents[0]).as_posix(),
                "fs_hz": rec.fs_hz,
                "duration_s": detrend_meta["duration_s"],
                "n_samples": int(len(residual)),
            },
            "white_noise_sensitivity_mps2_per_sqrt_hz": white_noise_coeff,
            "white_noise_sensitivity_ug_per_sqrt_hz": white_noise_coeff / G0 * 1e6,
            "adev_floor_mps2": adev_floor,
            "adev_floor_tau_s": tau_floor,
            "adev_floor_confidence": "LOW -- only ~%.0f independent %.1fs segments "
            "in a 373s record" % (edf_floor, tau_floor),
            "adev_floor_95pct_ci_mps2": adev_floor_ci,
            "residuals_file": "mical_static_residuals.npz",
        },
        "atom_interferometer": {
            "residuals_file": "atom_shot_residuals.npz",
            "noise_vs_rotation_file": "atom_noise_vs_rotation.csv",
            "note": "See atom_residual_summary.json (written by "
            "scripts/jarlaud2024_atom_residuals.py) for sigma_shot, n_shots, "
            "the per-run fringe fit, and the ADEV of the Run21 shot "
            "sequence; populated by a separate script run after this one.",
        },
        "cycle_rate_hz": cycle_rate_hz,
        "cycle_period_s": cycle_period_s,
        "paper_reference_values": {
            "single_shot_sensitivity_ug": 24.0,
            "single_shot_sensitivity_condition": "2T=20ms, inertial pointing mode, SNR=5.3",
            "static_snr_range": [20, 30],
            "gyro_noise_nrad_s_per_sqrt_hz": 100.0,
            "note": "The paper's 24 ug/shot and SNR 20-30 figures are "
            "ATOM INTERFEROMETER (hybrid, closed-loop) numbers -- compare "
            "them against atom_interferometer/sigma_shot_ug in "
            "atom_residual_summary.json, NOT against the classical MICAL "
            "white-noise density above. See docs/specs/raw/DATA_JARLAUD_NOTES.md.",
        },
        "contrast_fit": {
            "c0": float(c0_fit),
            "c0_sigma": float(perr[0]),
            "omega_c_rad_s": float(omega_c_fit),
            "omega_c_sigma_rad_s": float(perr[1]),
            "omega_c_mrad_s": float(omega_c_fit * 1e3),
            "r0_fringe_offset": r0,
            "n_shots": int(len(ratio)),
            "runs_used": [f"{f}/{d}/Run{r:02d}" for f, d, r in j.FIGURE2_RIGID_RUNS],
        },
        "PROPOSED_DECISION": [
            "Detrending is mean+linear-drift only (record is 373 s, far too "
            "short to fit or remove a tidal signal). [D-014/PD2: ACCEPTED]",
            "Contrast-vs-rotation fit uses only Figure 2 (rigid-mode) runs; "
            "Figure 3 & 5 (inertial-pointing) contrast requires per-Omega-bin "
            "sinusoidal fringe fitting which was judged out of scope for this "
            "pass -- flagged as a follow-up. [D-014/PD3: ACCEPTED for now]",
            "theta~=0 per-shot is not directly recorded for the pooled "
            "multi-run atom-residual set; Run21 (dedicated static/theta~0 "
            "calibration run) plus a per-run nominal Tilt X=Tilt Z=0 "
            "Parameters.txt proxy are used instead -- see "
            "scripts/jarlaud2024_atom_residuals.py docstring.",
        ],
    }
    with open(PROCESSED / "calibration.json", "w") as f:
        json.dump(calibration, f, indent=2)

    print("white_noise_coeff (m/s^2/sqrt(Hz)):", white_noise_coeff)
    print("adev_floor (m/s^2) @ tau:", adev_floor, tau_floor)
    print("cycle_rate_hz:", cycle_rate_hz)
    print("contrast fit c0, omega_c (rad/s):", c0_fit, omega_c_fit)


if __name__ == "__main__":
    main()
