# Reproduction Guide (round 3, core-freeze-6)

This guide reproduces the reported round-3 results from git tag `core-freeze-6` (commit `ca614b7`). The earlier rounds (`results/m4` = round 1, `results/m4r2` = round 2) are archived and superseded; their guide is in git history before this commit.

## 1. Environment

- Python 3.13 (the launchers use `Python313`). Other 3.11+ versions may work but are not what the results were produced with.
- Install: `python -m pip install -r requirements.txt` (numpy 2.3.4, scipy 1.16.2, matplotlib 3.10.7, pandas 2.3.3, torch 2.9.0, pytest 9.1.1, scikit-learn 1.7.2).
- Tests: `python -m pytest tests/ -q` (673 passed, 1 skipped at freeze).
- Paper build: MiKTeX (or TeX Live) with `pdflatex` and `bibtex`.
- Hardware used: Windows 11, 4 CPU workers for single-node runs. Each S14 run needs about 5 GB RAM.

## 2. Data

The Jarlaud et al. 2024 raw data is **not in git**. It is needed only for the real-data calibration (`data/processed/jarlaud2024/`).

1. Download `Raw Data.zip` from Zenodo (DOI 10.5281/zenodo.11543715):
   `wget https://zenodo.org/records/11543715/files/Raw%20Data.zip`
2. Check the MD5 `103d382e42a6f600fd0768c2a3286c40` (875,547,718 bytes).
3. Extract to `data/raw/jarlaud2024/` (about 2.9 GB unzipped).
4. Calibration outputs: `scripts/jarlaud2024_manifest.py` and `scripts/jarlaud2024_calibrate.py`. Details in `docs/DATA.md`.

The simulation campaign does not read the raw data once the calibrated constants and detector weights are in place (`results/m1/`, `results/fleet/`).

## 3. Check out the frozen code

```bash
git clone https://github.com/Praty0512/fedqpnt.git && cd fedqpnt
git checkout core-freeze-6          # ca614b7
git diff core-freeze-6 -- fedqpnt   # must be empty
```

Each run records its git provenance. A run is valid only if `fedqpnt/` is unchanged from the tag.

## 4. Pre-round artefacts (already committed)

These are in `results/` at the tag and do not need to be regenerated to reproduce the campaign:

| Artefact | Path |
|---|---|
| Detector v5 weights | `results/m1/detector_weights_sup_v5.npz` (report: `detector_train_sup_v5_report.json`) |
| Fleet θ0 f8 | `results/fleet/theta0_d054_f8.npz` (provenance: `theta0_d054_f8_provenance.json`) |
| H2/H4 θ0 | `results/fleet/theta0_noabrupt_v3.npz` |
| σ_nom (freeze-6) | `results/sigma_nom_freeze6.json` (1.0977 m MEMS, 1.1171 m tactical) |
| κ_Q calibration | `results/m1/kappa_q_f6_*.json` (selects κ_Q = 1) |

To rebuild them from scratch, use the commands in section 5.

## 5. Regenerate the inputs (optional)

Run from the repo root. Each script's arguments can be checked with `--help`.

```bash
# Detector v5 (tuning seeds 500-599, world schuler_tangent)
python scripts/train_supervised_v5.py --workers 4

# Fleet θ0: original weights + v5 normaliser (no retraining)
python scripts/build_theta0_f8.py

# H2/H4 θ0 (no-abrupt, v3)
python scripts/build_theta0_noabrupt_v3.py

# σ_nom on schuler_tangent (tuning seeds 560-579)
python scripts/core_robust_sigma_nom.py --world schuler_tangent --workers 4 --out results/sigma_nom_freeze6.json

# κ_Q rule (grid {1,2,3,5,8,12,20,30,50}, seeds 530-549, CAI on), one run per grade
python scripts/core_robust_kappa_q_calibration.py --grade industrial_mems --world schuler_tangent --workers 4 --out results/m1/kappa_q_f6_industrial_mems.json
python scripts/core_robust_kappa_q_calibration.py --grade tactical --world schuler_tangent --workers 4 --out results/m1/kappa_q_f6_tactical.json
```

## 6. Round-3 campaign (test seeds 10060-10089, n = 30 per cell)

Test seeds are run **once**. Do not re-run finished tasks to "improve" them. The campaign is resumable: finished runs are skipped.

```bash
# Phase 1: single-node, S14 excluded, 4 workers
python scripts/m4_campaign.py --phase 1 --exclude S14 --workers 4 --weights results/m1/detector_weights_sup_v5.npz

# Phase 2: fleet scenarios, one fleet at a time
python scripts/m4_campaign.py --phase 2 --weights results/m1/detector_weights_sup_v5.npz

# S14 (4-hour scenario), serial after phase 1
python scripts/m4_campaign.py --phase 1 --only S14 --workers 1 --weights results/m1/detector_weights_sup_v5.npz
```

Defaults already set in the script: `--tag core-freeze-6`, `--seeds 10060-10089`, `--root results/m4r3`. Dry run: add `--dry`. The Windows launchers are in `results/m4r3/` (`launch_phase1.cmd`, `launch_phase2.cmd`, `START_ROUND3*.cmd`).

**Expected runtime:** about 30 h for single-node on 4 workers, about 11 h for the fleet phase, and about 3-11 h for S14 run serially.

## 7. H2/H4 re-run (live seeds 10090-10099)

`results/m4r3/h2_r3_chain.cmd` runs three steps in order:

```bash
python -u scripts/h2_abrupt_h2h4_driver.py --parts h2,h4,control --live-seeds 10090-10099 --final --theta0 results/fleet/theta0_noabrupt_v3.npz --runs-dir results/fleet/h2_abrupt_runs_freeze6 --out results/fleet/h2_abrupt_freeze6.json --provenance-out results/fleet/h2_abrupt_provenance_freeze6.json
python -u scripts/h2_abrupt_calibrate_closedloop.py --live-seeds 10090-10099 --runs-dir results/fleet/h2_abrupt_runs_freeze6 --out-dir results/fleet/h2_abrupt_clean_closedloop_freeze6 --workers 2
python -u scripts/h2_abrupt_prereg_analysis.py --tau-mode closedloop --live-seeds 10090-10099 --runs-dir results/fleet/h2_abrupt_runs_freeze6 --clean-dir results/fleet/h2_abrupt_clean_closedloop_freeze6 --out results/fleet/h2_abrupt_prereg_results_freeze6.json
```

Fleets run one at a time (about 3-4 GB each). Do not run them alongside the 4-worker phase 1.

## 8. Report and figures

```bash
# Confirmatory family, safety, chattering, scenario criteria (Holm m = 8)
python scripts/m3_report.py --round3 --run-root results/m4r3 --summary-dir results/m4r3/report --out-md docs/M3_REPORT.md --out-json results/m4r3 --sigma results/sigma_nom_freeze6.json --h2 results/fleet/h2_abrupt_prereg_results_freeze6.json

# Figures
python scripts/make_figures_results.py --m3 results/m4r3 --out results/m4r3/figures --h2 results/fleet/h2_abrupt_prereg_results_freeze6.json --sigma results/sigma_nom_freeze6.json
```

The `m3_report.py` invocation is reconstructed from the script's flags and the committed output layout. Confirm it against `results/m4r3/report/SUMMARY.md` if the regenerated files differ.

Outputs: `results/m4r3/report/SUMMARY.md`, `HEADLINE.md`, `M3_REPORT.md`, `json/`.

## 9. Paper

```bash
cd paper
pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
```

Expect 21 pages. The abstract and results sections are in `paper/main.tex`.

## 10. Pre-registration

- `docs/specs/raw/PREREG_M4.md`, Amendment R3 (round 3), written before round-3 data existed.
- `docs/specs/raw/H2_PREREG.md`, Amendment 3 (H2/H4 re-run).
- Decisions: `DECISION_LOG.md` (D-085 to D-089).
- Execution trace: `EXECUTION_LOG.md` (rows 166 to 181).
