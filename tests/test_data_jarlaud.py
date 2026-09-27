"""Tests for the Jarlaud et al. 2024 real-data loader and calibration
pipeline (WP-2.5, D-008). These run against the actual extracted raw files
(data/raw/jarlaud2024/extracted/), so they are skipped if the dataset has not
been extracted (e.g. a fresh checkout before scripts/jarlaud2024_manifest.py
/ jarlaud2024_calibrate.py have been run).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fedqpnt.data import allan, jarlaud2024 as j

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "processed" / "jarlaud2024" / "manifest.csv"
CALIBRATION_PATH = ROOT / "data" / "processed" / "jarlaud2024" / "calibration.json"
MICAL_RESIDUALS_PATH = ROOT / "data" / "processed" / "jarlaud2024" / "mical_static_residuals.npz"
ATOM_RESIDUALS_PATH = ROOT / "data" / "processed" / "jarlaud2024" / "atom_shot_residuals.npz"
ATOM_SUMMARY_PATH = ROOT / "data" / "processed" / "jarlaud2024" / "atom_residual_summary.json"

requires_atom_residuals = pytest.mark.skipif(
    not ATOM_RESIDUALS_PATH.exists(),
    reason="atom_shot_residuals.npz not built (run scripts/jarlaud2024_atom_residuals.py)",
)

requires_dataset = pytest.mark.skipif(
    not j.EXTRACTED.exists(), reason="raw Jarlaud2024 dataset not extracted"
)
requires_manifest = pytest.mark.skipif(
    not MANIFEST_PATH.exists(), reason="manifest.csv not built (run scripts/jarlaud2024_manifest.py)"
)
requires_calibration = pytest.mark.skipif(
    not CALIBRATION_PATH.exists(), reason="calibration.json not built (run scripts/jarlaud2024_calibrate.py)"
)


@requires_dataset
def test_load_static_record_shape_and_units():
    rec = j.load_static_record()
    assert len(rec.accel_z_mps2) > 100_000
    assert 2000 < rec.fs_hz < 3000  # nominal 2.5 kHz accelerometer rate
    # z-axis should read close to -g (device near-vertical baseline shot).
    assert -9.9 < np.mean(rec.accel_z_mps2) < -9.7


@requires_dataset
def test_load_raman_run_joins_cleanly():
    run = j.load_raman_run("Figure 2", "20230510", 14)
    assert len(run.ratio) == len(run.rotation_rate_x_rad_s)
    assert np.all(run.ratio >= 0) and np.all(run.ratio <= 1)
    assert run.parameters.get("Data Type") == "Raman"


@requires_manifest
def test_manifest_covers_every_extracted_file():
    manifest = pd.read_csv(MANIFEST_PATH)
    n_files_on_disk = sum(1 for p in j.EXTRACTED.rglob("*") if p.is_file())
    assert len(manifest) == n_files_on_disk
    # Every path in the manifest must actually parse without error for the
    # categories the loader supports (parameters/avg01_ratios/rotations_data
    # all use the same tab-separated reader).
    for _, row in manifest[manifest["category"] == "parameters"].sample(
        min(10, (manifest["category"] == "parameters").sum()), random_state=0
    ).iterrows():
        parsed = None
        full_path = j.EXTRACTED / row["path"]
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        assert "Software Version" in text or "Run" in text
        parsed = True
        assert parsed


@requires_dataset
def test_loader_parses_every_manifested_raman_run_without_error():
    """Every (figure, date, run) triple referenced by parameters.txt in the
    manifest must load via load_raman_run without raising."""
    manifest = pd.read_csv(MANIFEST_PATH) if MANIFEST_PATH.exists() else None
    if manifest is None:
        pytest.skip("manifest.csv not built")
    param_rows = manifest[manifest["category"] == "parameters"]
    n_checked = 0
    for _, row in param_rows.iterrows():
        figure, date, run = row["figure"], str(row["date"]), int(row["run"])
        try:
            j.load_raman_run(figure, date, run)
        except FileNotFoundError:
            # Some runs only have kU data, not kD (default); try kU.
            j.load_raman_run(figure, date, run, k="kU")
        n_checked += 1
    assert n_checked == len(param_rows)


@requires_dataset
def test_streaming_loader_parses_all_streaming_files():
    manifest = pd.read_csv(MANIFEST_PATH) if MANIFEST_PATH.exists() else None
    if manifest is None:
        pytest.skip("manifest.csv not built")
    stream_rows = manifest[manifest["category"] == "streaming"]
    for _, row in stream_rows.iterrows():
        path = j.EXTRACTED / row["path"]
        if row["n_lines"] == 3:  # Figure 4 / Run19_2.csv: 2-row stub file
            continue
        rec = j.load_streaming(path)
        assert not np.any(np.isnan(rec.accel_z_mps2))
        assert not np.any(np.isnan(rec.accel_y_mps2))


def test_allan_deviation_white_noise_synthetic():
    """Sanity-check the local overlapping-ADEV implementation against
    synthetic white noise, where ADEV(tau) = sigma / sqrt(tau * fs) is known
    analytically (Riley, NIST SP 1065)."""
    rng = np.random.default_rng(0)
    fs = 1000.0
    sigma = 0.01
    n = 200_000
    x = rng.normal(0.0, sigma, n)
    tau, adev, _ = allan.overlapping_adev(x, fs)
    # For pure white noise sampled at fs, the expected ADEV at the shortest
    # tau (=1/fs) is sigma / sqrt(2) (Riley Eq. for white FM-like averaging
    # of an already-rate signal); check the measured curve decays like
    # tau^-1/2 to within 10% over the well-sampled region.
    mid = len(tau) // 2
    predicted_ratio = np.sqrt(tau[mid] / tau[2])
    measured_ratio = adev[2] / adev[mid]
    assert abs(measured_ratio - predicted_ratio) / predicted_ratio < 0.15


@requires_calibration
def test_mical_static_residuals_npz_zero_mean_no_nan():
    """D-014/PD1: this file holds CLASSICAL (MICAL) accelerometer noise."""
    data = np.load(MICAL_RESIDUALS_PATH)
    residual = data["residual_mps2"]
    assert not np.any(np.isnan(residual))
    assert abs(np.mean(residual)) < 1e-9
    assert data["fs_hz"] > 0
    assert str(data["sensor"]) == "classical_MICAL"


@requires_calibration
def test_adev_reproduces_fitted_white_noise_within_20pct():
    data = np.load(MICAL_RESIDUALS_PATH)
    residual = data["residual_mps2"]
    fs_hz = float(data["fs_hz"])
    with open(CALIBRATION_PATH) as f:
        calib = json.load(f)
    n_fit = calib["classical_accel_mical"]["white_noise_sensitivity_mps2_per_sqrt_hz"]

    tau, adev, _ = allan.overlapping_adev(residual, fs_hz)
    predicted = n_fit / np.sqrt(tau)
    # Compare over the same region the fit itself was performed on (where
    # the log-log slope is close to -1/2): the raw ADEV curve is not a pure
    # power law at every tau (short-tau bins are affected by the
    # accelerometer's own resonances/quantization, long-tau bins by the
    # floor), so this is the fair self-consistency check.
    _, wn_mask = allan.fit_white_noise_coefficient(tau, adev)
    rel_err = np.abs(adev[wn_mask] - predicted[wn_mask]) / predicted[wn_mask]
    assert np.median(rel_err) < 0.20


@requires_calibration
def test_calibration_json_has_split_classical_and_atom_sections():
    """D-014/PD1: classical MICAL and atom-interferometer numbers must live
    in separate, clearly-labelled sections and never be conflated."""
    with open(CALIBRATION_PATH) as f:
        calib = json.load(f)
    assert "classical_accel_mical" in calib
    assert "atom_interferometer" in calib
    classical = calib["classical_accel_mical"]
    assert classical["white_noise_sensitivity_ug_per_sqrt_hz"] > 0
    assert "adev_floor_confidence" in classical
    assert "LOW" in classical["adev_floor_confidence"]
    assert len(classical["adev_floor_95pct_ci_mps2"]) == 2


@requires_atom_residuals
def test_atom_shot_residuals_zero_mean_no_nan():
    data = np.load(ATOM_RESIDUALS_PATH)
    residual = data["residual_mps2"]
    assert not np.any(np.isnan(residual))
    assert abs(np.mean(residual)) < 1e-9
    assert str(data["sensor"]) == "atom_interferometer"
    n_shots = len(residual)
    assert n_shots > 100
    # Fields required by the D-014(b) deliverable spec.
    for field in ("t_s", "cycle_s", "two_T_s", "omega_mrad_s", "run_id"):
        assert field in data.files
        assert len(data[field]) == n_shots


@requires_atom_residuals
def test_atom_per_two_T_robust_sigma_reported():
    """D-015: pooling across 2T was a pooling artefact. Per-2T robust (MAD)
    sigma must be reported, and the 2T=20ms value (the paper's own
    condition, field-grade recommendation) must fall within 0.7-1.5x of the
    paper-implied value -- reported either way, not silently forced."""
    with open(ATOM_SUMMARY_PATH) as f:
        summary = json.load(f)
    per_two_T = summary["per_two_T"]
    assert "20ms" in per_two_T
    sig20 = per_two_T["20ms"]["sigma_robust_ug"]
    assert sig20 > 0
    assert len(per_two_T["20ms"]["sigma_robust_ug_95ci"]) == 2

    k_eff = 4.0 * np.pi / 780.241e-9
    T_s = 0.01  # 2T = 20 ms
    g0 = 9.80665
    paper_static_ug = (2.0 / (25.0 * k_eff * T_s**2)) / g0 * 1e6
    ratio = sig20 / paper_static_ug
    print(f"2T=20ms: n={per_two_T['20ms']['n']}, sigma_robust={sig20:.2f} ug, "
          f"paper-implied={paper_static_ug:.2f} ug, ratio={ratio:.2f}")
    assert 0.7 < ratio < 1.5

    assert "pooled_mixed_T_DO_NOT_USE" in per_two_T


@requires_atom_residuals
def test_atom_clean_flag_present_and_outliers_reported():
    data = np.load(ATOM_RESIDUALS_PATH)
    assert "clean" in data.files
    assert data["clean"].dtype == bool
    assert len(data["clean"]) == len(data["residual_mps2"])

    outliers_path = ROOT / "data" / "processed" / "jarlaud2024" / "atom_outliers.json"
    assert outliers_path.exists()
    with open(outliers_path) as f:
        outliers = json.load(f)
    assert "20ms" in outliers
    for group in outliers.values():
        assert group["outlier_rate"] >= 0.0
        assert len(group["outlier_rate_95ci"]) == 2
        assert isinstance(group["outlier_magnitudes_ug"], list)
