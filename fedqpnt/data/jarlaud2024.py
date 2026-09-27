"""Loader for the Jarlaud et al. 2024 raw dataset.

Paper: Q. d'Armagnac de Castanet et al., "Atom interferometry at arbitrary
orientations and rotation rates", Nat. Commun. 15, 6406 (2024),
DOI 10.1038/s41467-024-50804-0 (arXiv:2402.18988).
Raw data: Zenodo 10.5281/zenodo.11543715, CC-BY-4.0.

Dataset layout (relative to data/raw/jarlaud2024/extracted/Raw Data/):
  Figure 2/<date>/Raman/Run <n>/            -- rigid-mode rotation sweep
  Figure 2/<date>/Streaming/Run<n>_1.csv    -- companion classical IMU stream
  Figure 3 & 5/<date>/Raman/Run <n>/        -- inertial-pointing rotation sweep
  Figure 3 & 5/<date>/Streaming/Run<n>_1.csv
  Figure 4/<date>/Streaming/Run<n>_*.csv    -- long classical-accelerometer
                                                streams used for the vibration
                                                PSD figure (rotating head /
                                                forced-vibration tapping test)

All returned arrays use SI units (seconds, m/s^2, rad, rad/s) unless noted.
The raw files themselves are NOT SI for rotation rate (mrad/s) -- converted
here.

Owned by DATA-INGEST (WP-2.5). Must not import fedqpnt.sensors or
fedqpnt.core (owned by the QUANTUM-SENSOR work package).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EXTRACTED = ROOT / "data" / "raw" / "jarlaud2024" / "extracted" / "Raw Data"

MRAD_S_TO_RAD_S = 1e-3
DEG_TO_RAD = np.pi / 180.0


def _run_dir(figure: str, date: str, run: int) -> Path:
    return EXTRACTED / figure / date / "Raman" / f"Run {run:02d}"


def parse_parameters(figure: str, date: str, run: int) -> dict:
    """Parse a Parameters.txt file into a dict of raw strings.

    Numeric-looking values are left as strings (mixed formats: scalars,
    space-separated triplets, dates); callers that need floats should parse
    the specific key they want.
    """
    path = _run_dir(figure, date, run) / "Parameters.txt"
    out: dict[str, str] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or ":" not in line:
                continue
            key, _, val = line.partition(":")
            out[key.strip()] = val.strip()
    return out


def _read_tsv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t")
    df.columns = [c.lstrip("#") for c in df.columns]
    return df


@dataclass
class RamanRun:
    """One Raman run: population-ratio data joined with the classical
    rotation-stage / tip-tilt telemetry recorded at the same cycle rate.
    """

    figure: str
    date: str
    run: int
    k: str
    iteration: np.ndarray
    time_s: np.ndarray  # seconds since first sample of this run
    ratio: np.ndarray  # population ratio R = N2/Ntot, dimensionless
    phase_rad: np.ndarray  # commanded (scanned) Raman phase, NOT wrapped to
    # [0, 2pi) -- this is the deliberately-applied phase-scan variable used
    # to trace the interference fringe (confirmed empirically: increments by
    # a fixed sub-2pi step per shot, and Ratio correlates with cos(Phase mod
    # 2pi) at |corr| > 0.99 on dedicated fringe-scan runs -- see
    # docs/specs/raw/DATA_JARLAUD_NOTES.md Sec. 11). NOT the same as
    # rt_phase_rad below.
    rt_phase_rad: np.ndarray
    rotation_rate_x_rad_s: np.ndarray
    rotation_rate_y_rad_s: np.ndarray
    accel_mean_mps2: Optional[np.ndarray] = None
    parameters: dict = field(default_factory=dict)


def load_raman_run(figure: str, date: str, run: int, k: str = "kD") -> RamanRun:
    """Load one Raman run: per-shot ratio + rotation-rate + (if present)
    the closed-loop hybrid acceleration estimate, joined on Iteration.

    k: "kD" or "kU" (Raman k-reversal direction; not all runs have both).
    """
    d = _run_dir(figure, date, run)
    ratios_path = d / f"Raman-Run{run:02d}-Avg01-Ratios-{k}.txt"
    rot_path = d / f"Raman-Run{run:02d}-RotationsData.txt"
    rt_path = d / f"Raman-Run{run:02d}-RTData.txt"

    ratios = _read_tsv(ratios_path)
    rot = _read_tsv(rot_path)
    merged = ratios.merge(rot, on="Iteration", suffixes=("", "_rot"))

    accel_mean = None
    if rt_path.exists():
        rt = _read_tsv(rt_path)
        rt = rt[["Iteration", "AccelMean"]]
        merged = merged.merge(rt, on="Iteration", how="left")
        accel_mean = merged["AccelMean"].to_numpy(dtype=float)

    # Time: parse "Date"+"Time" -> seconds since first sample.
    ts = pd.to_datetime(
        merged["Date"] + " " + merged["Time"], format="%d/%m/%Y %H:%M:%S.%f"
    )
    t = (ts - ts.iloc[0]).dt.total_seconds().to_numpy()

    return RamanRun(
        figure=figure,
        date=date,
        run=run,
        k=k,
        iteration=merged["Iteration"].to_numpy(dtype=int),
        time_s=t,
        ratio=merged["Ratio"].to_numpy(dtype=float),
        phase_rad=merged["Phase"].to_numpy(dtype=float),
        rt_phase_rad=merged["RTPhase"].to_numpy(dtype=float),
        rotation_rate_x_rad_s=merged["RotationRateX"].to_numpy(dtype=float) * MRAD_S_TO_RAD_S,
        rotation_rate_y_rad_s=merged["RotationRateY"].to_numpy(dtype=float) * MRAD_S_TO_RAD_S,
        accel_mean_mps2=accel_mean,
        parameters=parse_parameters(figure, date, run),
    )


@dataclass
class StreamingRecord:
    """Classical accelerometer / FOG telemetry stream (Streaming/*.csv).

    Sampled at ~2.5 kHz (nominal accelerometer rate stated in the paper);
    fs_hz below is the value estimated from the file itself (see
    _estimate_streaming_fs), not assumed.
    """

    path: Path
    fs_hz: float
    n_interf: np.ndarray
    rotation_rate_x_rad_s: np.ndarray
    accel_y_mps2: np.ndarray
    accel_z_mps2: np.ndarray


def _estimate_streaming_fs(streaming_path: Path, n_samples: int) -> float:
    """Estimate the streaming sample rate from the companion RTData.txt
    file's wall-clock duration (same run, same acquisition session).
    Falls back to the paper-stated 2.5 kHz if no companion file is found.
    """
    # Streaming/Run<run>_1.csv -> Raman/Run <run>/Raman-Run<run>-RTData.txt
    date_dir = streaming_path.parents[1]
    m = re.match(r"Run(\d+)_", streaming_path.name)
    if not m:
        return 2500.0
    run = int(m.group(1))
    rt_path = date_dir / "Raman" / f"Run {run:02d}" / f"Raman-Run{run:02d}-RTData.txt"
    if not rt_path.exists():
        return 2500.0
    rt = _read_tsv(rt_path)
    ts = pd.to_datetime(rt["Date"] + " " + rt["Time"], format="%d/%m/%Y %H:%M:%S.%f")
    duration_s = (ts.iloc[-1] - ts.iloc[0]).total_seconds()
    if duration_s <= 0:
        return 2500.0
    return n_samples / duration_s


def load_streaming(path: Path) -> StreamingRecord:
    """Load a Streaming/*.csv classical-sensor file.

    Columns (raw file): NInterf;rotrateX;acc Y;acc Z
      - rotrateX is in mrad/s (converted to rad/s here)
      - acc Y, acc Z are in m/s^2 already (z-axis reads ~-9.8 = gravity when
        the device's z axis is close to vertical)
    """
    df = pd.read_csv(path, sep=";")
    # A small number of the raw streaming files end with a truncated final
    # line (the acquisition process was stopped mid-write); drop any row
    # with a NaN rather than silently propagating it downstream.
    n_before = len(df)
    df = df.dropna()
    if len(df) < n_before:
        pass  # documented in docs/specs/raw/DATA_JARLAUD_NOTES.md
    n = len(df)
    fs = _estimate_streaming_fs(path, n)
    return StreamingRecord(
        path=path,
        fs_hz=fs,
        n_interf=df["NInterf"].to_numpy(dtype=int),
        rotation_rate_x_rad_s=df["rotrateX"].to_numpy(dtype=float) * MRAD_S_TO_RAD_S,
        accel_y_mps2=df["acc Y"].to_numpy(dtype=float),
        accel_z_mps2=df["acc Z"].to_numpy(dtype=float),
    )


# ---------------------------------------------------------------------------
# Curated records used by the calibration pipeline (scripts/jarlaud2024_*.py)
# ---------------------------------------------------------------------------

#: The one Streaming record identified (by rotation-rate standard deviation
#: scan over all 41 Streaming files, see docs/specs/raw/DATA_JARLAUD_NOTES.md)
#: as genuinely static/non-rotating: rotrateX std ~0.1 mrad/s over the whole
#: run, i.e. below the FOG's own quoted noise floor of ~100 nrad/s/sqrt(Hz)
#: integrated over the run bandwidth. This is a calibration/baseline shot
#: (theta ~ 0, no rotation) embedded in the "Figure 3 & 5" (inertial-pointing)
#: rotation-sweep dataset, run on the manual rotation platform before/after a
#: sweep. PROPOSED-DECISION (see notes): this is the only long, high-rate,
#: undisturbed real record in the dataset and is used as the primary
#: real noise-replay source.
STATIC_STREAMING_PATH = (
    EXTRACTED / "Figure 3 & 5" / "20230320" / "Streaming" / "Run21_1.csv"
)

#: Figure 4's forced-vibration (tapping) test: device static (not rotating,
#: rotrateX std ~0.3 mrad/s) but deliberately excited to map out the
#: mechanical resonances (paper Fig. 4, blue curve). Elevated noise relative
#: to STATIC_STREAMING_PATH; used only as a secondary/comparison record, not
#: for the primary white-noise/ADEV-floor fit.
TAPPING_STREAMING_PATH = (
    EXTRACTED / "Figure 4" / "20230613" / "Streaming" / "Run06_1.csv"
)

#: Figure 4's rotating-head record (device continuously rotated at
#: |Omega| <= 250 mrad/s): source of the red "Rotating sensor head" PSD curve
#: in the paper's Fig. 4. NOT static; kept here for the rotating-vs-static
#: vibration comparison only.
ROTATING_STREAMING_PATH = (
    EXTRACTED / "Figure 4" / "20230612" / "Streaming" / "Run19_1.csv"
)

#: Figure 2 rigid-mode runs used for the contrast-vs-rotation-rate fit
#: (paper Fig. 2: population ratio vs rotation rate, theta in [0, 30] deg,
#: 2T = 12 ms).
FIGURE2_RIGID_RUNS = [
    ("Figure 2", "20230510", 14),
    ("Figure 2", "20230510", 15),
    ("Figure 2", "20230510", 16),
    ("Figure 2", "20230511", 34),
]


#: Effective two-photon Raman wavevector for the 87Rb D2 line (k_eff =
#: k1 + k2 ~= 2 * 2*pi/lambda for counter-propagating beams), lambda =
#: 780.241 nm. Used to convert phase residuals (rad) to acceleration
#: residuals (m/s^2) via delta_a = delta_phi / (k_eff * T^2).
RB87_D2_WAVELENGTH_M = 780.241e-9
K_EFF_RAD_PER_M = 4.0 * np.pi / RB87_D2_WAVELENGTH_M  # ~1.611e7 rad/m


def get_raman_T_s(parameters: dict) -> float:
    """Parse the "Raman T" field (interrogation half-time, seconds) from a
    parsed Parameters.txt dict."""
    return float(parameters["Raman T"])


MANIFEST_PATH = ROOT / "data" / "processed" / "jarlaud2024" / "manifest.csv"


def list_all_runs() -> list[tuple[str, str, int]]:
    """(figure, date, run) triples for every Raman run in the manifest."""
    manifest = pd.read_csv(MANIFEST_PATH)
    rows = manifest[manifest["category"] == "parameters"]
    return [
        (row["figure"], str(row["date"]), int(row["run"]))
        for _, row in rows.iterrows()
    ]


def load_static_record() -> StreamingRecord:
    """Load the curated static (non-rotating) classical-accelerometer record
    used as the input to the noise-replay / ADEV calibration pipeline.
    """
    return load_streaming(STATIC_STREAMING_PATH)
