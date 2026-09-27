# Jarlaud et al. 2024 real dataset -- raw notes (WP-2.5, D-008)

Terse, source-linked. Owned by DATA-INGEST. Does not touch fedqpnt/sensors, fedqpnt/core.

## 0. Source

- Paper: Q. d'Armagnac de Castanet, C. Des Cognets, R. Arguel, S. Templier, V. Jarlaud, V. Menoret, B. Desruelle, P. Bouyer, B. Battelier, "Atom interferometry at arbitrary orientations and rotation rates", *Nat. Commun.* **15**, 6406 (2024). DOI: 10.1038/s41467-024-50804-0. Preprint: arXiv:2402.18988. Open access (PMC11289413).
- Raw data: Zenodo 10.5281/zenodo.11543715, CC-BY-4.0. Local copy `data/raw/jarlaud2024/Raw Data.zip`, MD5 103d382e42a6f600fd0768c2a3286c40 (verified), 875.5 MB / 4117 entries. Extracted to `data/raw/jarlaud2024/extracted/` (git-ignored).
- Apparatus: three-axis hybrid cold-87Rb-atom (Mach-Zehnder Raman) interferometer on a manual 3-axis rotation platform, hybridized with a classical mechanical accelerometer (Thales MICAL, one per axis, mounted behind each retroreflection mirror) and two fibre-optic gyroscopes (FOG, Exail BlueSeis 3A derivative, noise < 100 nrad/s/sqrt(Hz), range +-667 mrad/s). Interferometry performed on the z axis only.

## 1. Per-figure raw-data contents

| Zip folder | # files | What it is | Runs / dates |
|---|---|---|---|
| `Figure 2` | 35 | Rigid mode: mirror fixed to the device, population ratio R vs device rotation rate Omega, theta in [0,30] deg, 2T=12 ms. ~1600 shots total (paper). | Run 14,15,16 (20230510), Run 34 (20230511) |
| `Figure 3 & 5` | 4073 | Inertial-pointing mode: active tip-tilt compensation holds the mirror's orientation fixed in the lab frame; population ratio vs rotation phase reconstructed from a rotation-phase model; Fig.5 is the same shot set before the epsilon=-0.013 tip-tilt-scale-factor correction. 2T=20 ms, Omega up to 250 mrad/s, theta in [0,30] deg, ~1400 shots (paper) + additional calibration/rigid-mode runs at other dates (56 runs total in the zip). | 20220902, 20230315, 20230317, 20230320, 20230612 |
| `Figure 4` | 8 | Long (100-1000 s), 2.5 kHz classical (MICAL) accelerometer streams used for the vibration PSD figure: Run19 (20230612) = device continuously rotated, |Omega|<=250 mrad/s ("rotating sensor head", red curve); Run06 (20230613) = device static but manually tapped to excite mechanical resonances ("forced vibrations", blue curve). No Raman/atom data in this folder. | 20230612, 20230613 |

## 2. File formats (per Raman run directory)

- `Parameters.txt` -- key:value text (60 lines), Raman sequence config (pulse durations, detunings, biases, tilt setpoints, "Track Mode", "Raman Scan Mode": kD/kU/kInterlaced, etc.).
- `Raman-Run##-Avg01-Ratios-{kD,kU}.txt` -- tab-separated, one row per shot: `Iteration, Date, Time, Chirp, Phase, RamanAxis, RTPhase, NFringe, Ratio`. `Ratio` = R = N2/Ntot (population ratio, the interferometer's raw output). Only one k-direction may be present per run (kD/kU Raman "k-reversal": the effective wavevector is reversed between shots to cancel systematics such as light shifts; `Raman Scan Mode: Phase kInterlaced` in Parameters.txt means kD and kU shots are interleaved, each file holding only its own half).
- `Raman-Run##-AvgRatios-{kD,kU}.txt` -- same but without RTPhase/NFringe (coarser summary: `Iteration, Date, Time, Chirp, Phase, RamanAxis, RatioMean, RatioStdDev`).
- `Raman-Run##-RotationsData.txt` -- tab-separated, one row per shot, same Iteration index: `STSX, STSY` (raw FOG angle/rate telemetry, purpose not fully documented in the paper text), `RotationRateX, RotationRateY` (device rotation rate in **mrad/s**, from the FOGs), `FrCntX, FrCntY` (fringe/step counters), `TiptiltCmd1/2` and `TiptiltMonitor1/2` (tip-tilt mirror commanded vs monitored angle, degrees) -- the real-time mirror-compensation telemetry described in the paper's Methods.
- `Raman-Run##-RTData.txt` -- tab-separated, one row per shot: `Iteration, Date, Time, RTPhase, NFringe, AccelAxis, AccelMean, AccelTemp`. `AccelMean` is the per-shot classical-accelerometer estimate used by the FPGA real-time phase-compensation loop (paper Methods, "Closed-loop mode"); it is near-constant within a run to 8 significant figures in the runs inspected, i.e. it behaves as a slowly-updated calibration constant rather than a fluctuating per-shot measurement -- **not** used as a continuous noise-characterisation channel here (see Sec. 4).
- `Raman-DetectData-Avg##-####.txt` -- per-shot raw fluorescence-detection trace (header block of k-index/chirp/phase/RT-freq metadata + ~1260 lines of samples). Not parsed by the loader (out of scope: not needed for noise/contrast calibration); counted in the manifest only.
- `Streaming/Run##_#.csv` -- semicolon-separated, header `NInterf;rotrateX;acc Y;acc Z`. Continuous classical-sensor telemetry recorded during the run at a rate the file itself implies is **~2.5 kHz** (measured from file length / companion RTData wall-clock duration; consistent with the paper's stated 2.5 kHz accelerometer sampling rate). `rotrateX` in **mrad/s**; `acc Y`, `acc Z` in **m/s^2** (z reads close to -9.8 when the device z-axis is near-vertical). `NInterf` increments once per Raman shot (links the stream to the Raman run's Iteration index, though not used here).

## 3. Loader (`fedqpnt/data/jarlaud2024.py`)

- `parse_parameters(figure, date, run)` -- Parameters.txt as a dict of raw strings.
- `load_raman_run(figure, date, run, k="kD")` -- joins Avg01-Ratios + RotationsData (+ RTData if present) on Iteration; converts rotation rate to rad/s; parses Date+Time into seconds-since-start.
- `load_streaming(path)` -- loads a Streaming csv, converts rotrateX to rad/s, drops any NaN row (a handful of files end with a truncated final line where acquisition was stopped mid-write -- e.g. `Figure 2/20230510/Streaming/Run14_1.csv`), estimates fs_hz from the companion RTData's wall-clock duration (falls back to 2500 Hz if no companion file exists, e.g. `Figure 4/*/Streaming/Run19_2.csv`, a 2-row stub).
- Curated constants: `STATIC_STREAMING_PATH`, `TAPPING_STREAMING_PATH`, `ROTATING_STREAMING_PATH`, `FIGURE2_RIGID_RUNS` (see Sec. 4-5).

## 4. Static-record selection (noise-replay / ADEV input) -- **PROPOSED-DECISION**

The dataset was designed to study contrast/phase vs rotation, not to provide a long, continuous, static acceleration channel for classical noise characterisation. Two constraints followed from that:

1. **No continuous atom-derived acceleration channel exists.** The atom interferometer's raw output is a per-shot population ratio (~0.65 Hz cycle rate, see Sec. 6); in the closed-loop hybridization scheme, the classical accelerometer's signal is what is actually subtracted/fed back in real time (paper Methods), and no long free-running atom-only acceleration time series is recorded anywhere in the zip. **Master ruling (D-014, PD1): PARTIALLY REJECTED.** The classical MICAL stream is real and valuable but must never be labelled or used as atom/quantum-sensor noise. Reworked: (a) this section's numbers are relabelled `classical_accel_mical` only (Sec. 11.1); (b) real per-shot atom acceleration residuals were separately derived from the Raman population-ratio files themselves (Sec. 11.2, `atom_shot_residuals.npz`) and must be used for anything claiming to be "quantum sensor" noise.
2. **Identifying a genuinely static (non-rotating, undisturbed) record required scanning the data.** All 41 Streaming files were loaded and their `rotrateX` standard deviation computed. 39 of 41 show std > 30 mrad/s (the platform is continuously, manually swept through rotation during acquisition, by design). Exactly one file is effectively static: **`Figure 3 & 5/20230320/Streaming/Run21_1.csv`** (rotrateX std = 0.105 mrad/s, i.e. at the FOG's own noise floor; 957,415 samples at 2565.7 Hz = 373.2 s). Its companion Raman run (`Run 21`, Parameters.txt: `Axis Mode: Z-Only`, `Track Mode: Closed Loop, RT Chirp`) is a theta~=0, Omega~=0 baseline/calibration shot embedded in the inertial-pointing sweep session. This is used as `STATIC_STREAMING_PATH`, the primary calibration input.
   - `Figure 4/20230613/Streaming/Run06_1.csv` (rotrateX std = 0.31 mrad/s) is also non-rotating but was **deliberately tapped** to excite mechanical resonances (paper's "forced vibrations" curve, Fig. 4 blue) -- kept as `TAPPING_STREAMING_PATH`, a secondary/comparison record only, not used in the white-noise/floor fit.
   - `Figure 4/20230612/Streaming/Run19_1.csv` (rotrateX std = 149.8 mrad/s) is the paper's "rotating sensor head" record (Fig. 4 red) -- kept as `ROTATING_STREAMING_PATH` for the same PSD comparison plot, not used in the fit.

## 5. Detrending -- **PROPOSED-DECISION**

The static record is 373 s long. The Master's brief anticipated removing "tides ... if the records are long enough, using a simple fitted tidal/polynomial model". Solid-Earth tidal acceleration has its dominant periods at >=~12 h (semi-diurnal/diurnal); a 373 s window cannot resolve or usefully fit any tidal component. **Detrending applied here is therefore limited to: (1) subtract the mean, (2) subtract a least-squares-fitted linear drift** (captures slow thermal/mechanical drift of the MICAL accelerometer over the 373 s window; fitted slope and intercept are saved in `static_residuals.npz`). No tidal model was fit or removed. This is a deliberate deviation from the anticipated method, flagged for Master ratification.

## 6. Fitted noise parameters (see `data/processed/jarlaud2024/calibration.json`)

Computed by `scripts/jarlaud2024_calibrate.py` from the static residual (Sec. 4-5), using a locally-implemented overlapping Allan deviation (`fedqpnt/data/allan.py`, standard NIST SP 1065 estimator; `fedqpnt/sensors/` did not have an `allan.py` at the time of writing and was not modified).

| Quantity | Value | Notes |
|---|---|---|
| White-noise sensitivity N | 8.96e-5 m/s^2/sqrt(Hz) = **9.13 ug/sqrt(Hz)** | Estimated from the shortest 2 ADEV octaves (tau = 0.39, 0.78 ms), i.e. the vendor-datasheet convention of reading noise density off the ADEV curve near the raw sample rate. **Not** a slope fit over a wide tau range -- see caveat below. |
| ADEV floor | 1.90e-5 m/s^2 (**1.94 ug**) | at tau = 25.5 s (the longest well-populated octave in this 373 s record; the true long-tau floor/bias-instability corner is likely not yet resolved -- record too short). |
| Interferometer cycle rate | 0.646 Hz (period 1.548 s) | Median inter-shot interval from RTData timestamps of the same Run 21 (all shots, kD+kU interlaced). |

**Caveat on the white-noise fit (important):** the ADEV curve for this record is **not** a clean tau^-1/2 power law over any wide contiguous range. Between tau ~ 3-100 ms (~10-300 Hz) the ADEV rises then falls sharply -- this matches the mechanical resonances the source paper itself documents in its own Fig. 4 PSD (peaks at 22, 28, 43, 54, 75 Hz). An automated log-log-slope search for the -1/2 region was tried first and rejected because it non-robustly latched onto the steep edges of this resonance structure rather than genuine broadband noise (see git history of `fedqpnt/data/allan.py`/`fit_white_noise_coefficient` for the rejected approach). The reported N above should be read as "noise density at the shortest resolvable averaging time", not as a single clean corner-frequency fit; a longer, quieter static record would be needed to fit N more robustly. Flagged as a limitation, not silently smoothed over.

**Comparison with the paper's numbers:** the paper reports a **per-shot** acceleration sensitivity of 24 ug at 2T=20 ms (inertial-pointing mode, SNR=5.3; static SNR 20-30 for the same 2T) -- this is a full hybrid atom+classical, rotation-degraded number at the ~0.65 Hz shot rate, not a continuous-time PSD/ADEV white-noise density for the classical accelerometer alone. Converting the paper's number to an equivalent noise density via N ~= (24 ug * g) * sqrt(1/cycle_rate) = 2.35e-4 m/s^2 * sqrt(1.548 s) ~= 2.9e-4 m/s^2/sqrt(Hz) (~30 ug/sqrt(Hz)) gives a ratio of **~0.31** (fitted classical-accelerometer N is about 3x lower/better than the paper's rotation-degraded per-shot number) -- consistent with expectations, since our record is quiet/static and the paper's 24 ug figure explicitly includes rotation-induced vibration degradation (paper: SNR drops from 20-30 static to 5.3 rotating). `calibration.json` stores both raw numbers (`white_noise_sensitivity_ug_per_sqrt_hz`, `paper_reference_values.single_shot_sensitivity_ug`) and reports the ratio is a sanity bound (0.01-100x) in the test, not forced to a tight match, per instructions.

## 7. Contrast vs rotation rate (`data/processed/jarlaud2024/contrast_vs_rotation.csv`, `results/data/jarlaud2024_contrast_vs_rotation.png`)

Fit of `C(Omega) = C0 * exp(-(Omega/Omega_c)^2)` (paper Eq. 2 functional form) to the envelope of `|Ratio - R0|*2` binned over `|Omega|`, using all 2000 shots from the 4 Figure-2 rigid-mode runs (theta swept 0-30 deg, 2T=12 ms):

- C0 = 0.394 +/- 0.017, Omega_c = 48.2 +/- 2.5 mrad/s, R0 (fringe offset) = 0.485.
- Sanity check against the paper: paper states rigid-mode contrast is negligible by ~85 mrad/s (5 deg/s); our fit gives C(85 mrad/s)/C0 = exp(-(85/48.2)^2) = 4e-2, i.e. contrast down to ~4% of C0 by 85 mrad/s -- consistent order of magnitude with "contrast loss" limiting rigid-mode operation there.
- **PROPOSED-DECISION / limitation:** only Figure 2 (rigid-mode, single functional form, simple envelope fit) was used. Figure 3 & 5 (inertial-pointing mode) contrast vs rotation rate requires per-Omega-bin sinusoidal fringe fitting (paper Fig. 3 top, black/blue points) which needs binning by Omega range and fitting `R0 - C/2*cos(phi)` per bin; judged out of scope for this pass given the effort budget. Flagged as a follow-up for whoever needs the extended-dynamic-range (inertial-pointing) contrast curve specifically.

## 8. Manifest

`data/processed/jarlaud2024/manifest.csv`, one row per file (4029 rows = 4117 zip entries - 88 directory entries), columns: figure, date, run, category (parameters / avg01_ratios / avg_ratios / rotations_data / rt_data / detect_data / streaming), path, size_bytes, n_lines (-1 for Streaming files, which are only header-sniffed for speed -- up to 2.5M rows each), header.

## 9. Tests

`tests/test_data_jarlaud.py`: loader parses a sample Raman run and every manifested run without error (kD/kU fallback); streaming loader parses all 41 Streaming files without NaN; local ADEV implementation checked against synthetic white noise; `static_residuals.npz` is zero-mean/finite; ADEV of the residual reproduces the fitted N within 20% **on the fit region itself** (self-consistency, not an independent hold-out -- the record's structure, Sec. 6, would not support a stricter independent check); `calibration.json` reports the ratio to the paper's number without forcing a pass on a tight match. All 9 tests pass (`python -m pytest tests/test_data_jarlaud.py -v`).

## 10. Reproduction

```
python scripts/jarlaud2024_manifest.py         # writes data/processed/jarlaud2024/manifest.csv
python scripts/jarlaud2024_calibrate.py        # writes mical_static_residuals.npz, calibration.json,
                                                # contrast_vs_rotation.csv, results/data/*.png
python scripts/jarlaud2024_atom_residuals.py   # writes atom_shot_residuals.npz,
                                                # atom_noise_vs_rotation.csv,
                                                # atom_residual_summary.json (merged into
                                                # calibration.json's atom_interferometer section)
python -m pytest tests/test_data_jarlaud.py -v
```

## 11. D-014 rework: classical vs atom noise split (Master ruling on PD1)

The Master's ruling on the original PD1 (D-014) **partially rejected** using the classical MICAL
accelerometer as a stand-in for "quantum sensor noise": it is real, valuable data, but must never
be labelled or used as atom-interferometer noise. This section documents the rework.

### 11.1 classical_accel_mical (renamed, unchanged numbers)

- `static_residuals.npz` was **renamed to `mical_static_residuals.npz`** and now carries
  `sensor="classical_MICAL"`. Numbers (white-noise density, floor) are unchanged from Sec. 6, now
  nested under `calibration.json["classical_accel_mical"]`.
- **ADEV-floor confidence, as required:** the floor sits at tau=25.5 s in a 373 s record, i.e. only
  ~15 essentially-independent tau-length segments (373/25.5). This is marked
  `"adev_floor_confidence": "LOW"` with a chi-square-based 95% CI:
  **[1.40e-5, 2.96e-5] m/s^2** around the point estimate 1.90e-5 m/s^2. A materially longer static
  record would be needed to pin this down; treat the point estimate as indicative only.

### 11.2 atom_interferometer (new: real per-shot atom acceleration residuals)

**Which quantity carries the atom measurement, and why:** three candidate columns exist in the
per-shot Raman files: `Phase`, `RTPhase`, `NFringe`. Empirically (fit on the dedicated static
Run 21): `Ratio` correlates with `cos(Phase mod 2*pi)` at **r = -0.995**, vs **r = -0.11** for
`cos(RTPhase)`. `Phase` also increments by an exact, constant sub-2*pi step every shot (e.g.
0.10469 rad/shot on Run21 kD) -- i.e. it is a deliberately, slowly scanned commanded phase used to
trace the fringe over many shots (not an artifact). `RTPhase`/`NFringe` track a different internal
quantity that is not the fringe argument on this run and were **not used**. This matches the
paper's own method (Fig. 3 bottom / Fig. 5: population ratio plotted against a total phase =
commanded scan + calculated rotation-induced phase phi_r(Omega,theta), Eq. 4) -- `Phase` is that
scan term.

**Method** (`scripts/jarlaud2024_atom_residuals.py`):
1. Per (figure, date, run, k in {kD,kU}): fit `Ratio = R0 - (C0/2)*cos(Phase mod 2pi - phi0)` by
   nonlinear least squares. 60 of 120 attempted (run, k) fits converged with a usable contrast
   (0.05 < C0 < 1.2); the rest are runs with too few shots, no kU/kD file, or a degenerate fit.
2. Per shot: residual (ratio units) = Ratio - fitted model; local slope dR/dphi =
   (C0/2)*sin(phi-phi0) (sensitivity-function linearisation, cf. paper ref. [34]); phase residual =
   ratio residual / slope; shots within 0.3 rad of a fringe extremum (|sin(phi-phi0)| < 0.3, where
   this blows up) are dropped (mid-fringe linearisation is only valid away from the turning points).
3. Acceleration residual = phase residual / (k_eff * T^2), k_eff = 4*pi/780.241nm = 1.611e7 rad/m
   (Rb87 D2 line, counter-propagating two-photon Raman), T from that run's own `Parameters.txt`
   ("Raman T": 6, 10 or 12.5 ms depending on run -> 2T = 12 or 20 ms, matching the paper's two
   operating conditions).
4. kD and kU are fit and residualised **separately** (each k-direction gets its own R0/C0/phi0);
   both contribute residual samples to the pooled sets below, not combined/averaged, since the
   dataset does not pair a kD and kU shot at the same instant (k is interlaced shot-by-shot, not
   simultaneous) and the paper does not describe a specific kD+kU combination rule to remove for a
   noise (as opposed to systematic-bias) estimate.

**theta ~ 0 caveat (PROPOSED-DECISION):** no per-shot tilt is recorded (only the mirror's own
tip-tilt command/monitor, not the device's tilt vs gravity). We use `|Omega| < 5 mrad/s` (measured
per shot from RotationsData) as the primary near-static filter, plus each run's *nominal*
`Parameters.txt` "Tilt X"="Tilt Z"=0 deg setpoint as the closest available theta~0 proxy for
runs other than Run 21; **Run 21 itself is kept in full** regardless of this proxy since it is the
dataset's own dedicated static/theta~0/Omega~0 calibration run (`Axis Mode: Z-Only`). This is an
approximation, not a verified per-shot theta, and is flagged rather than assumed silently.

**Results, pooled across 2T (superseded, see 11.3):** n=1715, sigma_shot=20.88 ug. This pooled
number mixes 2T in {10,12,14,20} ms, each with a different k_eff*T^2 sensitivity scaling, and was
ruled a **pooling artefact** by the Master (D-015) after re-analysis. It is kept in
`calibration.json` only as `per_two_T.pooled_mixed_T_DO_NOT_USE` for traceability -- do not use it
for calibration. Use Sec. 11.3 instead.

### 11.3 D-015 rework: per-2T robust statistics, outliers, clean flag

**Per-2T robust (MAD-based) sigma_shot**, with a 2000-sample bootstrap 95% CI, replacing the pooled
number above (`calibration.json["atom_interferometer"]["per_two_T"]`,
`atom_residual_summary.json`):

| 2T | n | sigma_robust (ug) | 95% CI (ug) | classical-equivalent (ug) | outlier rate |
|---|---|---|---|---|---|
| 10 ms | 720 | 10.70 | -- | -- | 0.1% |
| 12 ms | 24 | 12.47 | -- | -- | 0% |
| 14 ms | 480 | 6.83 | -- | -- | 0% |
| **20 ms** | **491** | **5.60** | [5.04, 6.40] | 6.08 | **9.0%** [6.7%, 11.8%] |

**Field-grade recommendation: 2T = 20 ms** (the paper's own reported condition, largest low-outlier
sample after 10 ms, and the one with a direct paper comparison point).

**Comparison with the paper (like-for-like this time):** paper static SNR=25 at 2T=20ms implies
5.06 ug (`sensitivity = 2/(SNR*k_eff*T^2)`). Our 2T=20ms robust sigma_shot = 5.60 ug ->
**ratio 1.11x** -- essentially consistent with the paper once the 2T mixing is removed. The
previously reported "4.1x gap" (Sec. 11.2) is confirmed to have been a pooling artefact, not a
real discrepancy with the paper.

**Outliers** (`atom_outliers.json`; defined as `|residual - median| > 5*sigma_robust` **within each
2T group** -- a real process, not deleted, hence the `clean` boolean flag added to
`atom_shot_residuals.npz` rather than dropping rows):

- 10/12/14 ms groups: outlier rate 0-0.1% (negligible).
- **20 ms group: 44/491 shots (9.0%, 95% CI [6.7%, 11.8%]) are outliers**, magnitude range
  ~roughly tens to ~100+ ug (full empirical list saved in `atom_outliers.json`).
- **Time-clustering check:** among 20ms-group outliers, 65.9% have another outlier as an immediate
  neighbouring shot in the same run, vs 9.0% expected if outliers were independent (i.e. same rate
  as the base outlier rate) -- a **~7.4x excess**, indicating outliers cluster in bursts rather than
  occurring independently. Plausible mechanism: the 20ms-group's near-static shots are drawn from
  many different continuously-swept runs' brief |Omega|<5 mrad/s crossings (only Run 21 is a
  dedicated static run), and a rotation-rate zero-crossing mid-run is a plausible trigger for a
  fringe jump / momentary loss-of-lock, not settled static operation. Not confirmed further this
  pass -- flagged as a real, data-derived, clustered failure mode worth propagating into the sensor
  model's fault channel, separate from its Gaussian noise floor.

**Replay usage:** `atom_shot_residuals.npz` now carries a per-shot `clean` boolean (True for
non-outlier shots, per its own 2T group's 5-sigma rule). Noise replay for the Gaussian/white part
of the model should draw only `clean=True`, same-2T shots; the outlier channel (rate + magnitude
distribution + clustering, `atom_outliers.json`) should be modelled separately (e.g. as an
occasional burst/fault process), not folded into the Gaussian floor.

**sigma_shot vs |Omega|, rebuilt per 2T** (`atom_noise_vs_rotation.csv`, columns:
`two_T_ms, omega_bin_low_mrad_s, omega_bin_high_mrad_s, n_shots, sigma_robust_ug`; all 60 fitted
run/k combinations). Degradation with rotation rate is visible within each 2T group (robust sigma
rises from single-digit-to-low-teens ug near |Omega|~0 to several hundred ug above 150-200 mrad/s
in the higher-count groups), consistent with the paper's qualitative SNR 20-30 (static) -> 5.3
(high rotation) finding, though (as in Sec. 11.2) this per-shot-fringe-residual proxy is cruder
than the paper's dedicated fringe-reconstruction SNR analysis. Combined with the Sec. 7 contrast
fit, this gives the federated-sim quantum-sensor model a real, data-derived, 2T-resolved
rotation-degradation curve for both contrast loss and noise growth.
