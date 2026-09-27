# Real quantum-sensor data: Jarlaud et al. 2024

**Purpose.** This document specifies how real cold-atom interferometer data from Jarlaud et al. (d'Armagnac de Castanet et al., *Nat. Commun.* 15:6406, 2024) is used to calibrate and validate the quantum-sensor (cold-atom inertial, CAI) noise models in FedQPNT.

**Source data:**
- Paper: d'Armagnac de Castanet, Q.; Des Cognets, C.; Arguel, R.; Templier, S.; Jarlaud, V.; Menoret, V.; Desruelle, B.; Bouyer, P.; Battelier, B., "Atom interferometry at arbitrary orientations and rotation rates," *Nat. Commun.* **15**, 6406 (2024). DOI: 10.1038/s41467-024-50804-0. Preprint: arXiv:2402.18988.
- Raw data: Zenodo 10.5281/zenodo.11543715 (CC-BY-4.0 license). Local: `data/raw/jarlaud2024/Raw Data.zip` (875.5 MB, 4117 entries, MD5 verified).
- Apparatus: Three-axis hybrid cold-87Rb atom interferometer (Mach-Zehnder Raman, z-axis only) + three-axis classical accelerometer (Thales MICAL, 2.5 kHz) + two fiber-optic gyroscopes (Exail BlueSeis 3A, <100 nrad/s per √Hz noise).

---

## Dataset structure and file formats

### Per-figure contents

The raw-data zip is organized by paper figure:

| Folder | # files | What it contains | Runs / dates |
|--------|---------|---|---|
| Figure 2 | 35 | **Rigid-mode contrast.** Mirror fixed to device, population-ratio R vs device rotation rate Ω, θ ∈ [0, 30]°, 2T=12 ms. ~1600 shots (paper). | Runs 14, 15, 16 (20230510); Run 34 (20230511) |
| Figure 3 & 5 | 4073 | **Inertial-pointing mode.** Active tip-tilt compensation holds mirror fixed in lab frame; population ratio reconstructed from rotation-phase model; 2T=20 ms, Ω up to 250 mrad/s, θ ∈ [0, 30]°, ~1400 shots (paper) + 56 additional calibration/rigid runs. | 20220902, 20230315, 20230317, 20230320, 20230612 |
| Figure 4 | 8 | **Classical-accelerometer PSD.** Long MICAL streams (100–1000 s), 2.5 kHz sampling. Run19 (20230612) = continuously rotated, \|Ω\|≤250 mrad/s. Run06 (20230613) = static + manually tapped to excite mechanical resonances. No atom data. | 20230612, 20230613 |

### File types within each run folder

- **Parameters.txt** (60 lines, key:value): Raman pulse config, tilt setpoints, track mode (closed-loop vs open), scan mode (kD/kU/interlaced).
- **Raman-Run##-Avg01-Ratios-{kD,kU}.txt** (tab-separated): Per-shot `Ratio` (population ratio R = N₂/Ntot), phase (`Phase`), rotation rates from FOG, companion metadata.
- **Raman-Run##-RotationsData.txt** (tab-separated): Per-shot FOG telemetry (rotation rate X, Y in mrad/s), fringe counters, tip-tilt mirror command/monitor (deg).
- **Raman-Run##-RTData.txt** (tab-separated): Per-shot classical-accelerometer estimates (used by FPGA closed-loop, near-constant within run).
- **Streaming/Run##_#.csv** (semicolon-separated, ~2.5 kHz): Continuous classical sensor telemetry (`NInterf`, `rotrateX` in mrad/s, `acc Y`, `acc Z` in m/s²). Linkage to Raman shots via `NInterf` counter.

**Important note (D-014):** Classical MICAL stream is real measured classical-accelerometer noise, but must NEVER be labelled or used as "quantum sensor" noise. Quantum-sensor noise is extracted separately from the per-shot Raman population-ratio residuals (Sections 11.2–11.3).

---

## Classical accelerometer (MICAL) calibration

### Static record identification

**Dataset design goal:** Contrast vs. rotation, not long static acceleration. To locate a genuinely static record, all 41 Streaming files were scanned for rotation-rate std dev:
- 39 of 41: std > 30 mrad/s (platform manually swept, by design)
- **2 of 41: static to FOG noise floor**

**Selected static record:** `Figure 3 & 5/20230320/Streaming/Run21_1.csv`
- Rotation-rate std: 0.105 mrad/s (FOG noise floor)
- Duration: 373.2 s (957,415 samples at 2565.7 Hz)
- Companion Raman run: Run 21, Parameters.txt: `Axis Mode: Z-Only`, `Track Mode: Closed Loop`
- Status: Dedicated theta≈0, Omega≈0 baseline/calibration run

**Secondary records** (not used for calibration, kept for reference):
- Run06_1 (20230613): 0.31 mrad/s, deliberately tapped (forced vibrations, Fig. 4 blue)
- Run19_1 (20230612): 149.8 mrad/s (rotating sensor head, Fig. 4 red)

### Detrending

The 373 s record is far too short to resolve tidal components (12-hour period minimum). Detrending applied:
1. Subtract mean (remove DC offset)
2. Subtract least-squares-fitted linear drift (captures slow thermal/mechanical drift over the window)

No tidal model or removal. Result stored in `mical_static_residuals.npz` (renamed from `static_residuals.npz` per D-014).

### Fitted noise parameters

From `fedqpnt/data/allan.py` (NIST SP 1065 overlapping Allan deviation, locally implemented):

| Quantity | Value | Unit | Confidence | Notes |
|----------|-------|------|------------|-------|
| White-noise sensitivity (N) | 8.96e-5 | m/s²/√Hz = 9.13 µg/√Hz | [ASSUMPTION] | Read off ADEV curve at shortest tau (~0.39–0.78 ms), NOT slope-fitted over wide range |
| ADEV floor | 1.90e-5 | m/s² = 1.94 µg | **LOW** | τ = 25.5 s (longest well-populated octave in 373 s record); only ~15 independent segments; true floor likely unresolved |
| ADEV floor 95% CI | [1.40e-5, 2.96e-5] | m/s² | — | Chi-square bootstrap confidence interval |
| Cycle rate (Raman) | 0.646 Hz | — | — | Median inter-shot interval, Run 21 |

**Caveat on white-noise fit:** The ADEV curve is NOT a clean power-law (τ^{−1/2}) over a wide range. Between τ ≈ 3–100 ms (10–300 Hz), ADEV rises then falls sharply, matching the mechanical resonances in the paper's Fig. 4 PSD (peaks at 22, 28, 43, 54, 75 Hz). An automated log-log-slope fit for the power-law region was rejected (non-robust, latched onto resonance edges). The reported N is "noise density at shortest resolvable averaging time," not a single clean corner-frequency fit. A longer, quieter static record would be needed for robust N estimation — flagged as a limitation.

**Comparison with paper:** Paper reports 24 µg/shot (inertial-pointing, SNR=5.3, hybrid atom+classical). Converting to equivalent noise density: N ≈ (24 µg × g) × √(1/cycle_rate) ≈ 30 µg/√Hz. Our fitted classical MICAL N ≈ 9 µg/√Hz → **ratio 0.31**. This is consistent: our record is quiet/static; paper figure includes rotation-induced vibration degradation (SNR drops from 20–30 static to 5.3 rotating).

---

## Quantum-sensor (atom interferometer) calibration

### Per-shot atom residuals

Unlike the classical accelerometer, no long continuous atom-derived acceleration channel exists (paper uses closed-loop hybridization; only the classical signal is fed back in real time). Real per-shot atom noise is extracted from the Raman population-ratio files via fringe fitting.

**Extraction method** (`scripts/jarlaud2024_atom_residuals.py`):

1. Per (run, k ∈ {kD, kU}): fit `Ratio = R₀ − (C₀/2)cos(Phase − φ₀)` via nonlinear least squares (60 of 120 fits converged with usable contrast 0.05 < C₀ < 1.2).

2. Per shot: residual (ratio units) = Ratio − fitted model; linearise around fringe via local slope dR/dφ = (C₀/2)sin(φ − φ₀); drop shots within 0.3 rad of fringe extremum (|sin(φ − φ₀)| < 0.3, linearisation breaks down there).

3. Acceleration residual = phase residual / (k_eff × T²), where k_eff = 4π / λ = 1.611e7 rad/m (⁸⁷Rb D₂ line, 780.241 nm, counter-propagating two-photon Raman). T from run's own Parameters.txt (2T ∈ {10, 12, 14, 20} ms depending on run).

4. kD and kU are fit and residualised separately (each k-direction gets its own R₀/C₀/φ₀); both contribute to pooled residuals.

**Previously reported "4.1× gap" (old pooled number):** Mixes 2T values with different k_eff × T² scaling. Ruled a **pooling artefact by D-015** and must not be used.

### Per-2T robust statistics (D-015 rework)

A proper like-for-like comparison uses each 2T group's own robust (MAD-based) σ, with bootstrap 95% CI:

| 2T | n | σ_robust (µg) | 95% CI (µg) | Outlier rate | Outlier rate 95% CI |
|---|---|---|---|---|---|
| 10 ms | 720 | 10.70 | — | 0.1% | — |
| 12 ms | 24 | 12.47 | — | 0% | — |
| 14 ms | 480 | 6.83 | — | 0% | — |
| **20 ms** | **491** | **5.60** | **[5.04, 6.40]** | **9.0%** | **[6.7%, 11.8%]** |

**Field-grade recommendation: 2T = 20 ms** (paper's own operating point, largest clean-sample count, best CI). Comparison with paper static SNR=25 at 2T=20 ms:
- Paper-implied σ: 2/(SNR × k_eff × T²) = 5.06 µg
- Measured σ_robust: 5.60 µg
- **Ratio: 1.11× — essentially consistent** (the previously reported 4.1× was the pooling artefact)

### Outlier process (fringe jumps / loss-of-lock)

Outliers defined per-2T as |residual − median| > 5×σ_robust. NOT dropped; instead flagged with `clean` boolean in `atom_shot_residuals.npz`:

| 2T | n | n_outliers | Outlier rate | Adjacency of outliers | Interpretation |
|---|---|---|---|---|---|
| 10 ms | 720 | 1 | 0.14% | 0% | Independent |
| 12 ms | 24 | 0 | 0% | — | None |
| 14 ms | 480 | 0 | 0% | — | None |
| 20 ms | 491 | 44 | 9.0% | 65.9% | **Bursty** (7.4× excess adjacency vs independence) |

**20 ms outlier magnitudes:** Range ~30–270 µg. The 65.9% adjacency rate among outliers (vs 9.0% expected if independent) indicates **clustering / burst behavior**, not isolated heavy-tailed shot noise. Plausible trigger: rotation-rate zero-crossings during multi-run sweep (fringe jump / momentary loss-of-lock at rate turning points). Flagged as a real, data-derived fault mode worth propagating into the sensor's Gilbert–Elliott outlier channel (D-019). Not resolved further this pass; marked as a follow-up for whoever models the bursty-fault dynamics.

**Storage:** `atom_outliers.json` lists all 44 outlier magnitudes (µg), adjacency statistics, and interpretation per 2T group.

### Rotation-rate sensitivity (per-2T noise vs |Ω|)

Degradation with rotation is visible within each 2T group (file: `atom_noise_vs_rotation.csv`):
- Near |Ω|≈0 (static): single-digit to low-tens µg robust σ
- Above 150–200 mrad/s (high rotation): hundreds of µg

Consistent with paper's qualitative SNR degradation (20–30 static → 5.3 rotating), though per-shot-fringe-residual proxy is cruder than the paper's dedicated fringe-reconstruction SNR. Combined with contrast-vs-rotation fit (Section 7), this provides a real, data-derived, 2T-resolved rotation-degradation curve.

---

## Contrast loss vs. rotation rate

### Rigid-mode fit (Figure 2 runs)

All 2000 shots from the 4 rigid-mode runs (Figure 2, 2T=12 ms, θ swept 0–30°) fit to:
```
C(Ω) = C₀ exp(−(Ω/Ω_c)²)
```
per paper Eq. 2 (functional form).

| Parameter | Value | 95% CI | Source |
|-----------|-------|--------|--------|
| C₀ (peak contrast) | 0.394 | ±0.017 | Fit envelope of \|Ratio − R₀\| × 2 binned by \|Ω\| |
| Ω_c (roll-off rate) | 48.2 | ±2.5 (mrad/s) | — |
| R₀ (fringe offset) | 0.485 | — | — |

**Sanity check:** Paper states rigid-mode contrast is negligible by ~85 mrad/s. Our fit: C(85)/C₀ = exp(−(85/48.2)²) ≈ 0.04 → contrast down to ~4% by 85 mrad/s. Consistent order of magnitude.

**Limitation:** Only Figure 2 (rigid-mode, simple envelope fit) was used. Figure 3 & 5 (inertial-pointing mode) requires per-Ω-bin sinusoidal fringe fitting (paper Fig. 3 top, black/blue points), judged out of scope for this pass. Flagged as a follow-up for extended-dynamic-range (inertial-pointing) contrast if needed.

**File:** `data/processed/jarlaud2024/contrast_vs_rotation.csv` (also plotted in `results/data/jarlaud2024_contrast_vs_rotation.png`).

---

## Parameter table: quantum-sensor calibration (FIELD grade, 2T=20 ms)

| Quantity | Value | Unit | Source | Status |
|----------|-------|------|--------|--------|
| **Noise** | | | | |
| White-noise sensitivity | 8.96e-5 | m/s²/√Hz | Classical MICAL measurement, Section 2 | [ASSUMPTION] (robust fit, short record) |
| Per-shot σ (2T=20ms) | 5.60 | µg | Atom residuals, D-015, robust MAD | [LIT: matches paper 5.06 µg within 11%] |
| ADEV floor (τ=25.5s) | 1.90e-5 | m/s² | Classical MICAL, Section 2 | **[ASSUMPTION, LOW confidence]** |
| **Contrast loss** | | | | |
| C₀ (rigid-mode peak) | 0.394 | (unitless) | Figure 2 fit, Section 7 | [LIT: paper Fig. 2] |
| Ω_c (roll-off) | 48.2 | mrad/s | Figure 2 fit | [LIT] |
| **Rotation sensitivity** | | | | |
| σ_shot degradation | visible within each 2T | — | `atom_noise_vs_rotation.csv` | [LIT: paper qualitative] |
| Burst outlier rate (2T=20ms) | 9.0% | (per-shot) | Measured, D-015 | [UNVERIFIED: rate only; mechanism deferred] |

**Replay usage (D-019):**
- Draw **clean-only shots** (same 2T, `clean=True`) for Gaussian noise replay
- Model outlier bursts separately as a Gilbert–Elliott 2-state channel with measured rate (9.0%) and persistence (~66% burst durability, 7.4× adjacency excess)
- Sensor keeps `valid=True` during bursts (silently wrong, as in reality)

---

## Data manifest and reproduction

**Manifest:** `data/processed/jarlaud2024/manifest.csv` (4029 rows = 4117 zip entries − 88 directories), columns: figure, date, run, category, path, size_bytes, n_lines, header.

**Loader:** `fedqpnt/data/jarlaud2024.py`
- `parse_parameters(figure, date, run)` → Parameters.txt as dict
- `load_raman_run(figure, date, run, k="kD")` → Raman + rotation data joined
- `load_streaming(path)` → Streaming CSV with fs_hz estimate and NaN drops

**Reproduction:** Run these in order:
```bash
python scripts/jarlaud2024_manifest.py         # → manifest.csv
python scripts/jarlaud2024_calibrate.py        # → mical_static_residuals.npz, calibration.json, contrast_vs_rotation.csv, plots
python scripts/jarlaud2024_atom_residuals.py   # → atom_shot_residuals.npz, atom_noise_vs_rotation.csv, atom_residual_summary.json, plots
python -m pytest tests/test_data_jarlaud.py -v # → 12 tests (all PASS, D-015 rework)
```

**Validation:** `tests/test_data_jarlaud.py` (12 tests per D-015 rework)
- Loader parses all runs without error (kD/kU fallback)
- Streaming loader handles all 41 files, drops NaN rows
- `atom_shot_residuals.npz` carries per-shot `clean` boolean flag (True for non-outlier shots, per 2T group's 5-sigma rule); `mical_static_residuals.npz` separated (D-014)
- Per-2T robust σ_shot validated: 2T=20 ms → 5.60 µg ±CI [5.04, 6.40] (D-015)
- Outlier rate 9.0% at 2T=20 ms with 65.9% adjacency (bursty, 7.4× excess vs independence)
- ADEV of residuals reproduces fitted N within 20% (self-consistency on fit region, not held-out validation)
- `calibration.json` reports ratio to paper's number without forcing tight match (0.01–100× bounds)

---

## Related decisions and design notes

- **D-008 (Master):** Use real quantum-sensor data where it exists. Calibration/validation: fit noise model to real records, report agreement with data. Noise replay: remove known signals, replay leftover noise resampled in blocks. Fallback: digitise published ADEV figures if raw data unavailable.
- **D-014 (Master, PARTIAL REJECTION of original PD1):** Classical MICAL stream is valuable real data but must NEVER be labelled as atom/quantum-sensor noise. Quantum noise extracted separately from per-shot Raman residuals (this section, 11.2–11.3). Consequence: with the measured Ω_c ≈ 48 mrad/s (low rotation threshold), a rigid-mode CAI loses contrast during ordinary vehicle turns (~0.3 rad/s), so quantum aiding is intermittent in maneuvers. Kept as a real effect (honest limitation per D-002), weakens quantum benefit.
- **D-015 (Master, RE-ANALYSIS):** Per-2T robust statistics, outliers modelled not dropped, fringe jumps are a real process. Pooled "4.1× gap" confirmed as artefact. Measured 10→20 ms σ ratio ~2× (not 4×), suggests vibration-limited regime at shorter 2T, not assumed 1/T² law. Outlier process is bursty (65.9% adjacency vs 9.0% base rate) → Gilbert–Elliott model (D-019).
- **D-017 (Master ACCEPTED PROPOSED-DECISION 3):** theta~0 per-shot not directly recorded. Run 21 (dedicated static/theta~0) is kept in full; other runs use per-run nominal `Tilt X=Tilt Z=0` from Parameters.txt as theta~0 proxy. This is an approximation, flagged not silently assumed.
- **D-019 (Master):** FIELD-grade quantum-sensor model: 2T=20ms, σ_shot=5.60 µg measured (1.11× paper), outliers are a real bursty Gilbert–Elliott process (rate 9.0%, burst persistence 66%) modelled separately, not deleted. Silently-wrong (valid=True during bursts, as in reality) because closed-loop feedback uses the measurements, and fringe jumps do occur and must be handled by the trust engine, not hidden.

---

## Limitations and assumptions

- **Record length:** 373 s too short to resolve tidal components (12-hour minimum period); detrending limited to mean + linear drift.
- **Static-record selection:** 41 files scanned; exactly one is genuinely static (Run 21_1). All others manually swept, by experimental design.
- **Contrast-vs-rotation fit:** Rigid-mode (Figure 2) only; inertial-pointing (Figure 3 & 5) requires per-bin sinusoidal fitting, out of scope for this pass.
- **Outlier mechanism:** Suspected rotation-rate zero-crossings based on data-clustering pattern; not independently confirmed mechanically.
- **White-noise density:** ADEV curve non-monotonic (resonance structure 3–100 ms); reported N is "density at shortest tau" not a log-log slope fit. Longer static record needed for robust N.
- **Theta~0 proxy:** Per-run nominal Tilt X/Z from Parameters.txt is an approximation for non-Run-21 data; Run 21 itself (dedicated static) is exempt from this limitation.
