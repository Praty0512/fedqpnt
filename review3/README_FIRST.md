# FedQPNT - Review 3 submission

Pratyaksh Gupta (23BCE0316) · Guide: Prof. Padma Priya R

Top level: `FedQPNT_Review3_Report.pdf` (Review-3 report) and `FedQPNT_Overview_Novelty_Plain_Summary.pdf` (overview, novelty, plain summary).

FedQPNT is a federated quantum-sensor navigation (PNT) framework: a fleet of platforms fuses quantum-inertial and GNSS data and learns, with a trust-split federated scheme, to detect and resist spoofing/meaconing attacks.
Simulations are calibrated on real cold-atom interferometer data (Jarlaud/d'Armagnac de Castanet et al. 2024).
The round-3 campaign (5,340 runs, 30 seeds) is the basis of the reported results.

## Folder map
- `code/` : full repository export (tracked files only)
  - `fedqpnt/` library, `scripts/` drivers, `tests/` test-suite
  - `results/` simulation outputs (`m4r3` = 5,340 round-3 runs as JSON; `minimatrix_f8`, `demo`, `m1`, `fleet`, `sigma_nom*.json`)
  - `figures/` figures, `paper/` outline, `docs/` (incl. REPRODUCE.md, DATA.md)
- `dataset/` : README with download source/MD5 of the third-party raw data (not included), plus derived calibration outputs in `derived/`

## Install (Python 3.13)
    cd code
    python -m pip install -r requirements.txt

## Run
- Tests: `python -m pytest tests -q` (some data tests need the raw data, see dataset/README.md)
- Demo (live displaced-meaconer attack, about 1 min): `python scripts/demo_attack.py` (`--help` for options); outputs go to `results/demo/`
- Regenerate the report/results: follow `docs/REPRODUCE.md`

## Withheld
The patent draft is withheld pending filing and is not part of this package. Some process/log documents may mention it in passing.
