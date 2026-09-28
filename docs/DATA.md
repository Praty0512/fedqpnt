# Data Access and Reproduction

## Jarlaud et al. 2024 Dataset

### Source

**Dataset:** d'Armagnac de Castanet et al., "Atom interferometry at arbitrary orientations and rotation rates," *Nat. Commun.* **15**, 6406 (2024).
- **Paper DOI:** [10.1038/s41467-024-50804-0](https://doi.org/10.1038/s41467-024-50804-0)
- **Dataset DOI:** [10.5281/zenodo.11543715](https://doi.org/10.5281/zenodo.11543715)
- **License:** CC-BY-4.0

### Download and Setup

The dataset is **not included** in the repository. To reproduce real-data calibration:

1. Download from Zenodo:
   ```bash
   wget https://zenodo.org/records/11543715/files/Raw%20Data.zip
   ```

2. Verify MD5:
   ```bash
   echo "103d382e42a6f600fd0768c2a3286c40  Raw Data.zip" | md5sum -c -
   ```
   Expected: **103d382e42a6f600fd0768c2a3286c40** (875,547,718 bytes)

3. Extract to the repository:
   ```bash
   unzip -d data/raw/jarlaud2024 "Raw Data.zip"
   ```

### File Structure

- **`data/raw/jarlaud2024/`** – Extracted raw data (~2.87 GB unzipped)
  - `Raw Data/Figure 2/` – Rigid-mode contrast (4 runs, 35 files)
  - `Raw Data/Figure 3 & 5/` – Inertial-pointing mode (56 runs, 4073 files)
  - `Raw Data/Figure 4/` – Classical accelerometer PSD (2 runs, 8 files)

- **`data/processed/jarlaud2024/`** – Calibration outputs
  - `calibration.json` – Classical MICAL white-noise calibration (N = 9.13 µg/√Hz)
  - `atom_residual_summary.json` – Per-2T robust σ summary (2T=20 ms: σ = 5.60 µg)
  - `atom_outliers.json` – Fringe-jump outlier statistics (9.0% rate, 66% adjacency)

### Regenerate Processed Data

All processed files are regenerated from the raw dataset via:

```bash
# 1. Create file manifest
python scripts/jarlaud2024_manifest.py

# 2. Classical MICAL calibration
python scripts/jarlaud2024_calibrate.py

# 3. Atom interferometer per-shot residuals
python scripts/jarlaud2024_atom_residuals.py

# 4. Validation suite (12 tests)
python -m pytest tests/test_data_jarlaud.py -v
```

**Output locations:**
- `data/processed/jarlaud2024/calibration.json`
- `data/processed/jarlaud2024/atom_residual_summary.json`
- `data/processed/jarlaud2024/atom_outliers.json`

## Attribution

When using this dataset, cite:

> d'Armagnac de Castanet, Q.; Des Cognets, C.; Arguel, R.; Templier, S.; Jarlaud, V.; Menoret, V.; Desruelle, B.; Bouyer, P.; Battelier, B., "Atom interferometry at arbitrary orientations and rotation rates," *Nat. Commun.* **15**, 6406 (2024). https://doi.org/10.1038/s41467-024-50804-0

Dataset: https://zenodo.org/records/11543715 (CC-BY-4.0)

## Key Parameters

| Quantity | Value | Unit | Reference |
|----------|-------|------|-----------|
| Classical MICAL white-noise sensitivity (N) | 9.13e-5 | m/s²/√Hz | MICAL static record; Allan deviation |
| Atom interferometer per-2T robust σ (2T=20 ms) | 5.60 | µg | Per-shot residual extraction + robust MAD-based σ |
| Atom σ 95% CI | [5.04, 6.40] | µg | Bootstrap confidence interval |
| Outlier (fringe-jump) rate at 2T=20 ms | 9.0 | % | Gilbert–Elliott bursty channel model |

All values are from EXECUTION_LOG.md entries 18–29 (D-014 to D-019). For detailed methodology, see [REAL_DATA_JARLAUD2024.md](REAL_DATA_JARLAUD2024.md).

## Specification

Full technical specification of dataset structure, file formats, calibration procedures, and caveats is in [REAL_DATA_JARLAUD2024.md](REAL_DATA_JARLAUD2024.md).

---

**Last updated:** 2026-09-29
