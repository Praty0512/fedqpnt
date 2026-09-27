"""Real atom-interferometer per-shot acceleration residuals (WP-2.5, D-014
rework of PD1).

The Master's ruling (D-014) rejected using the classical MICAL accelerometer
stream as a stand-in for "quantum sensor noise". This script derives REAL
per-shot acceleration residuals from the atom interferometer's own output
(the population ratio R), using the fringe model actually present in the
data, and separately reports the classical accelerometer numbers in
calibration.json under a distinct "classical_accel_mical" section (see
jarlaud2024_calibrate.py).

Method (see docs/specs/raw/DATA_JARLAUD_NOTES.md Sec. 11 for the empirical
justification):

  1. The raw "Phase" column (Avg01-Ratios-{kD,kU}.txt) is a deliberately
     scanned commanded Raman phase: it increments by a fixed sub-2*pi step
     every shot (verified: constant diff, e.g. 0.10469 rad/shot on Run21
     kD), so Phase mod 2*pi slowly traces out the full interference fringe
     over many shots. This is confirmed empirically: corr(Ratio, cos(Phase
     mod 2pi)) = -0.995 on the dedicated static run (Run21), vs -0.11 for
     RTPhase. RTPhase/NFringe are therefore NOT used here (they track a
     different, less-fringe-correlated internal quantity on this run).
  2. Per (figure, date, run, k-direction), fit
       R(phi) = R0 - (C0/2) * cos(phi - phi0),  phi = Phase mod 2*pi
     by nonlinear least squares. This gives the deterministic fringe model
     for that run/k-direction.
  3. Per shot: residual_ratio = Ratio - R(phi); local slope dR/dphi =
     (C0/2) sin(phi - phi0); phase residual = residual_ratio / slope
     (standard sensitivity-function linearisation, cf. paper ref. [34]
     Cheinet et al. 2008); shots within 0.3 rad of a fringe extremum
     (|sin(phi-phi0)| < 0.3, where the linearisation is ill-conditioned)
     are dropped.
  4. Acceleration residual = phase residual / (k_eff * T^2), with T from
     that run's Parameters.txt ("Raman T") and k_eff for the Rb87 D2 line.

Two independent products:
  - atom_shot_residuals.npz: shots with |Omega| < 5 mrad/s (near-static),
    pooled across every run/k-direction that has them, PLUS the dedicated
    static Run 21 (all shots). This is the D-014(b) deliverable.
  - atom_noise_vs_rotation.csv: per-shot |accel residual| binned by |Omega|
    across ALL runs (not just the near-static subset). This is the
    D-014(c) deliverable.

PROPOSED-DECISION (theta ~ 0 criterion): per-shot tilt theta is not directly
recorded in the Raman/RotationsData files (only TiptiltCmd/Monitor, which
are the mirror's own two-axis tip-tilt angle, not the device's tilt relative
to gravity). Parameters.txt has a per-RUN nominal "Tilt X"/"Tilt Z" setpoint
(not per-shot). We use |Omega| < 5 mrad/s as the primary near-static
selection criterion (directly measurable per shot from RotationsData) and
additionally require the run's nominal Tilt X = Tilt Z = 0.000 deg from
Parameters.txt as the closest available proxy for theta ~ 0 across the
pooled multi-run set; Run 21 is used in full regardless since it is the
dataset's own dedicated theta~0, Omega~0 calibration run (Axis Mode: Z-Only).
This is an approximation, not a per-shot verified theta, and is documented
as such rather than silently assumed.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

from fedqpnt.data import jarlaud2024 as j

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed" / "jarlaud2024"

OMEGA_STATIC_THRESHOLD_RAD_S = 5e-3  # 5 mrad/s
SIN_MASK_THRESHOLD = 0.3


def fringe_model(phi, r0, c0, phi0):
    return r0 - 0.5 * c0 * np.cos(phi - phi0)


def fit_and_residualize(run) -> dict | None:
    """Fit the fringe model for one loaded RamanRun and return per-shot
    acceleration residuals + metadata, or None if the fit is unusable
    (too few shots, or the fit does not converge / gives a degenerate
    contrast)."""
    if len(run.ratio) < 20:
        return None
    phi = np.mod(run.phase_rad, 2 * np.pi)
    ratio = run.ratio
    try:
        popt, pcov = curve_fit(
            fringe_model, phi, ratio, p0=[0.5, 0.3, 0.0], maxfev=20000
        )
    except RuntimeError:
        return None
    r0, c0, phi0 = popt
    if not (0.05 < c0 < 1.2) or not np.isfinite(pcov).all():
        return None
    resid_ratio = ratio - fringe_model(phi, r0, c0, phi0)
    slope = 0.5 * c0 * np.sin(phi - phi0)
    mask = np.abs(np.sin(phi - phi0)) > SIN_MASK_THRESHOLD
    if mask.sum() < 5:
        return None

    T_s = j.get_raman_T_s(run.parameters)
    two_T_s = 2 * T_s
    phase_residual = resid_ratio[mask] / slope[mask]
    accel_residual = phase_residual / (j.K_EFF_RAD_PER_M * T_s**2)
    omega = np.sqrt(
        run.rotation_rate_x_rad_s[mask] ** 2 + run.rotation_rate_y_rad_s[mask] ** 2
    )
    tilt_x = float(run.parameters.get("Tilt X", "nan"))
    tilt_z = float(run.parameters.get("Tilt Z", "nan"))

    return {
        "run_id": f"{run.figure}/{run.date}/Run{run.run:02d}/{run.k}",
        "r0": r0,
        "c0": c0,
        "phi0": phi0,
        "n_shots_total": len(run.ratio),
        "n_shots_used": int(mask.sum()),
        "T_s": T_s,
        "two_T_s": two_T_s,
        "accel_residual_mps2": accel_residual,
        "omega_rad_s": omega,
        "t_s": run.time_s[mask],
        "tilt_x_deg": tilt_x,
        "tilt_z_deg": tilt_z,
        "cycle_s": float(np.median(np.diff(run.time_s))) if len(run.time_s) > 1 else np.nan,
    }


def main() -> None:
    runs = j.list_all_runs()
    all_fits = []
    for figure, date, run_no in runs:
        for k in ("kD", "kU"):
            try:
                rr = j.load_raman_run(figure, date, run_no, k=k)
            except FileNotFoundError:
                continue
            fit = fit_and_residualize(rr)
            if fit is not None:
                all_fits.append(fit)

    print(f"fitted {len(all_fits)} (run, k) fringe models out of {2*len(runs)} attempted")

    # ------------------------------------------------------------------
    # D-014(b): near-static pooled shot residuals.
    # ------------------------------------------------------------------
    static_residual = []
    static_omega = []
    static_t = []
    static_two_T = []
    static_cycle = []
    static_run_id = []

    for fit in all_fits:
        near_static = np.abs(fit["omega_rad_s"]) < OMEGA_STATIC_THRESHOLD_RAD_S
        is_run21 = "20230320/Run21" in fit["run_id"]
        tilt_zero = (
            np.isfinite(fit["tilt_x_deg"])
            and np.isfinite(fit["tilt_z_deg"])
            and abs(fit["tilt_x_deg"]) < 1e-6
            and abs(fit["tilt_z_deg"]) < 1e-6
        )
        keep = near_static & (tilt_zero | is_run21)
        if is_run21:
            keep = near_static  # Run 21 is the dedicated static calibration run; keep in full.
        n = int(keep.sum())
        if n == 0:
            continue
        static_residual.append(fit["accel_residual_mps2"][keep])
        static_omega.append(fit["omega_rad_s"][keep] * 1e3)  # mrad/s
        static_t.append(fit["t_s"][keep])
        static_two_T.append(np.full(n, fit["two_T_s"]))
        static_cycle.append(np.full(n, fit["cycle_s"]))
        static_run_id.append(np.array([fit["run_id"]] * n))

    residual_mps2 = np.concatenate(static_residual)
    omega_mrad_s = np.concatenate(static_omega)
    t_s = np.concatenate(static_t)
    two_T_s = np.concatenate(static_two_T)
    cycle_s = np.concatenate(static_cycle)
    run_id = np.concatenate(static_run_id)

    # Remove the mean per-run-id before pooling residuals across runs whose
    # fitted R0/phi0 may carry small independent calibration offsets; the
    # quantity of interest is the shot-to-shot scatter, not a cross-run DC
    # level (each run's residual is already zero-mean by construction of
    # the per-run fit, so this is a light re-centering safeguard only).
    residual_mps2 = residual_mps2 - np.mean(residual_mps2)

    sigma_shot = float(np.std(residual_mps2))
    g0 = 9.80665
    print(f"n_shots (near-static pool) = {len(residual_mps2)}")
    print(f"pooled (mixed-2T) sigma_shot = {sigma_shot:.4e} m/s^2 = {sigma_shot/g0*1e6:.2f} ug -- DO NOT USE, see per_two_T")

    # ------------------------------------------------------------------
    # D-015: per-2T robust (MAD) sigma, bootstrap CI, outlier detection.
    # Pooling across 2T in {10,12,14,20} ms mixes different sensitivities
    # (accel residual = phase residual / (k_eff*T^2)) and was flagged by the
    # Master as a pooling artefact (D-015). Per-2T stats below are the
    # field-usable numbers; the pooled sigma_shot above is kept only for
    # traceability, explicitly labelled "do not use".
    # ------------------------------------------------------------------
    rng = np.random.default_rng(0)
    clean = np.ones(len(residual_mps2), dtype=bool)
    per_two_T = {}
    outlier_report = {}
    unique_two_T = sorted(set(two_T_s.tolist()))

    # Classical (MICAL) white-noise density, for the per-2T equivalent-sigma
    # comparison column (converts N [m/s^2/sqrt(Hz)] to a per-shot sigma
    # using that group's own average cycle time).
    with open(PROCESSED / "calibration.json") as f:
        classical_n = json.load(f)["classical_accel_mical"]["white_noise_sensitivity_mps2_per_sqrt_hz"]

    for T in unique_two_T:
        gmask = two_T_s == T
        vals = residual_mps2[gmask]
        n = len(vals)
        median = float(np.median(vals))
        mad = float(np.median(np.abs(vals - median)))
        sigma_robust = 1.4826 * mad

        # Bootstrap 95% CI on sigma_robust.
        boots = np.empty(2000)
        for b in range(2000):
            sample = rng.choice(vals, size=n, replace=True)
            m = np.median(sample)
            boots[b] = 1.4826 * np.median(np.abs(sample - m))
        ci = np.percentile(boots, [2.5, 97.5])

        # Outliers: |r - median| > 5*sigma_robust (a real process -- flagged,
        # not deleted; see atom_outliers.json).
        is_outlier_local = np.abs(vals - median) > 5.0 * sigma_robust
        n_out = int(is_outlier_local.sum())
        p_hat = n_out / n if n else 0.0
        # Wilson score 95% CI for the outlier rate.
        z = 1.959964
        denom = 1 + z**2 / n
        center = (p_hat + z**2 / (2 * n)) / denom
        half = (z * np.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))) / denom
        rate_ci = [max(0.0, center - half), min(1.0, center + half)]

        clean[gmask] = ~is_outlier_local

        cycle_avg = float(np.mean(cycle_s[gmask]))
        classical_equiv_ug = classical_n / np.sqrt(cycle_avg) / g0 * 1e6 if cycle_avg > 0 else None

        source_runs = sorted(set(run_id[gmask].tolist()))
        per_two_T[f"{T*1000:.0f}ms"] = {
            "two_T_s": T,
            "n": n,
            "sigma_robust_mps2": sigma_robust,
            "sigma_robust_ug": sigma_robust / g0 * 1e6,
            "sigma_robust_ug_95ci": [float(ci[0] / g0 * 1e6), float(ci[1] / g0 * 1e6)],
            "median_mps2": median,
            "classical_equivalent_sigma_ug": classical_equiv_ug,
            "n_outliers": n_out,
            "outlier_rate": p_hat,
            "outlier_rate_95ci": rate_ci,
            "source_runs": source_runs,
        }

        # Time-clustering check: fraction of outlier shots that have another
        # outlier as an immediate neighbour (previous/next shot) WITHIN THE
        # SAME RUN, vs the rate expected if outliers were independent
        # (~p_hat). A ratio >> 1 suggests bursts (fringe jumps /
        # loss-of-lock) rather than independent heavy-tailed noise.
        t_g = t_s[gmask]
        run_g = run_id[gmask]
        out_g = is_outlier_local
        n_adjacent = 0
        n_out_checked = 0
        for rid in set(run_g.tolist()):
            rmask = run_g == rid
            order = np.argsort(t_g[rmask])
            out_seq = out_g[rmask][order]
            idxs = np.where(out_seq)[0]
            for idx in idxs:
                n_out_checked += 1
                neigh = False
                if idx > 0 and out_seq[idx - 1]:
                    neigh = True
                if idx < len(out_seq) - 1 and out_seq[idx + 1]:
                    neigh = True
                if neigh:
                    n_adjacent += 1
        adjacency_rate = n_adjacent / n_out_checked if n_out_checked else 0.0
        outlier_report[f"{T*1000:.0f}ms"] = {
            "two_T_s": T,
            "n_shots": n,
            "n_outliers": n_out,
            "outlier_rate": p_hat,
            "outlier_rate_95ci": rate_ci,
            "outlier_magnitudes_ug": (np.abs(vals[is_outlier_local] - median) / g0 * 1e6).tolist(),
            "adjacency_rate_among_outliers": adjacency_rate,
            "expected_adjacency_rate_if_independent": p_hat,
            "clustering_interpretation": (
                "adjacency_rate >> expected_adjacency_rate_if_independent suggests bursts "
                "(fringe jumps / loss-of-lock); comparable values suggest independent "
                "heavy-tailed shot noise, not clustered bursts."
            ),
        }

    per_two_T["pooled_mixed_T_DO_NOT_USE"] = {
        "n": int(len(residual_mps2)),
        "sigma_shot_mps2": sigma_shot,
        "sigma_shot_ug": sigma_shot / g0 * 1e6,
        "warning": "Mixes 2T in {10,12,14,20} ms with different k_eff*T^2 "
        "scaling -- a pooling artefact per D-015. Use per-2T entries above.",
    }
    per_two_T["field_grade_recommendation"] = "20ms"

    with open(PROCESSED / "atom_outliers.json", "w") as f:
        json.dump(outlier_report, f, indent=2)

    np.savez(
        PROCESSED / "atom_shot_residuals.npz",
        residual_mps2=residual_mps2,
        t_s=t_s,
        cycle_s=cycle_s,
        two_T_s=two_T_s,
        omega_mrad_s=omega_mrad_s,
        run_id=run_id,
        clean=clean,
        sensor="atom_interferometer",
    )
    print(f"clean shots: {int(clean.sum())}/{len(clean)}")
    for k_, v_ in per_two_T.items():
        if "sigma_robust_ug" in v_:
            print(f"  2T={k_}: n={v_['n']}, sigma_robust={v_['sigma_robust_ug']:.2f} ug, "
                  f"outlier_rate={v_['outlier_rate']:.3f}")

    # ADEV of the atom shots vs tau, as far as the (irregularly sampled,
    # cross-run) shot sequence allows: use the dominant single run (Run21,
    # by far the largest contiguous, evenly-sampled near-static sequence)
    # for a proper time-ordered ADEV; report it separately.
    run21_mask = np.array(["20230320/Run21" in r for r in run_id])
    tau_adev = None
    adev_vals = None
    if run21_mask.sum() > 20:
        order = np.argsort(t_s[run21_mask])
        res21 = residual_mps2[run21_mask][order]
        t21 = t_s[run21_mask][order]
        dt21 = float(np.median(np.diff(t21)))
        from fedqpnt.data import allan

        tau_adev, adev_vals, _ = allan.overlapping_adev(res21, 1.0 / dt21)

    # ------------------------------------------------------------------
    # D-014(c) / D-015(3): per-shot noise vs |Omega|, rebuilt PER 2T with
    # robust (MAD-based) sigma columns (D-015: mixing 2T is a pooling
    # artefact -- do not report a single cross-2T sigma here either).
    # ------------------------------------------------------------------
    all_resid = []
    all_omega = []
    all_T = []
    for fit in all_fits:
        r = fit["accel_residual_mps2"] - np.median(fit["accel_residual_mps2"])
        all_resid.append(r)
        all_omega.append(np.abs(fit["omega_rad_s"]) * 1e3)
        all_T.append(np.full(len(r), fit["two_T_s"]))
    all_resid = np.concatenate(all_resid)
    all_omega = np.concatenate(all_omega)
    all_T = np.concatenate(all_T)

    bin_edges = np.array([0, 5, 20, 50, 100, 150, 200, 250, 400])
    rows = []
    for T in unique_two_T:
        tmask = all_T == T
        for i in range(len(bin_edges) - 1):
            sel = tmask & (all_omega >= bin_edges[i]) & (all_omega < bin_edges[i + 1])
            n = int(sel.sum())
            if n < 5:
                sigma_robust_ug = np.nan
            else:
                med = np.median(all_resid[sel])
                mad = np.median(np.abs(all_resid[sel] - med))
                sigma_robust_ug = float(1.4826 * mad / g0 * 1e6)
            rows.append(
                {
                    "two_T_ms": round(T * 1000, 1),
                    "omega_bin_low_mrad_s": bin_edges[i],
                    "omega_bin_high_mrad_s": bin_edges[i + 1],
                    "n_shots": n,
                    "sigma_robust_ug": sigma_robust_ug,
                }
            )
    with open(PROCESSED / "atom_noise_vs_rotation.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # ------------------------------------------------------------------
    # Summary numbers for calibration.json / notes / report.
    # ------------------------------------------------------------------
    summary = {
        "n_shots_static_pool": int(len(residual_mps2)),
        "sigma_shot_mps2": sigma_shot,
        "sigma_shot_ug": sigma_shot / g0 * 1e6,
        "n_run_k_fits": len(all_fits),
        "run21_fit": next((f for f in all_fits if "20230320/Run21/kD" in f["run_id"]), None),
    }
    with open(PROCESSED / "atom_residual_summary.json", "w") as f:
        json.dump(
            {
                "n_shots_static_pool": summary["n_shots_static_pool"],
                "sigma_shot_mps2_pooled_DO_NOT_USE": summary["sigma_shot_mps2"],
                "sigma_shot_ug_pooled_DO_NOT_USE": summary["sigma_shot_ug"],
                "n_run_k_fits": summary["n_run_k_fits"],
                "run21_kD_fit": {
                    k: v
                    for k, v in (summary["run21_fit"] or {}).items()
                    if k not in ("accel_residual_mps2", "omega_rad_s", "t_s")
                },
                "adev_tau_s": tau_adev.tolist() if tau_adev is not None else None,
                "adev_mps2": adev_vals.tolist() if adev_vals is not None else None,
                "per_two_T": per_two_T,
            },
            f,
            indent=2,
        )

    # Also merge per_two_T directly into calibration.json's atom_interferometer
    # section (D-015 item 1).
    calib_path = PROCESSED / "calibration.json"
    with open(calib_path) as f:
        calib = json.load(f)
    calib["atom_interferometer"]["per_two_T"] = per_two_T
    calib["atom_interferometer"]["field_grade_recommendation_two_T"] = "20ms"
    calib["atom_interferometer"].pop("sigma_shot_mps2", None)
    calib["atom_interferometer"].pop("sigma_shot_ug", None)
    if "20ms" in per_two_T:
        sig20 = per_two_T["20ms"]["sigma_robust_ug"]
        paper_static_ug = calib["atom_interferometer"].get("paper_comparison", {}).get(
            "paper_static_sigma_ug_at_snr25_2T20ms", 5.06
        )
        calib["atom_interferometer"]["paper_comparison"] = {
            "paper_static_snr_range": [20, 30],
            "paper_static_sigma_ug_at_snr25_2T20ms": paper_static_ug,
            "field_grade_sigma_robust_ug_at_2T20ms": sig20,
            "ratio_field_grade_to_paper_static": round(sig20 / paper_static_ug, 2),
            "note": "D-015 correction: previously reported a pooled (mixed-2T) "
            "ratio of ~4.1x, which was a pooling artefact. Comparing like-for-like "
            "at 2T=20ms (the paper's own condition) instead.",
        }
    with open(calib_path, "w") as f:
        json.dump(calib, f, indent=2)

    print("wrote atom_shot_residuals.npz, atom_noise_vs_rotation.csv, atom_residual_summary.json, "
          "atom_outliers.json, and merged per_two_T into calibration.json")


if __name__ == "__main__":
    main()
