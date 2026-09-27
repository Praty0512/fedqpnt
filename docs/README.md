# FedQPNT Documentation Index

Welcome to the FedQPNT documentation. This document is a 1-page index of the simulation specification, design architecture, and real-data calibration. For navigation and overview of the project, start here.

---

## Core documentation: simulation, fusion, attacks, and real data

### [SIMULATION.md](SIMULATION.md)
Trajectory generation and inertial strapdown integration. Covers:
- Piecewise-polynomial trajectory construction for ground vehicles and UAVs
- 2nd-order trapezoid-and-coning strapdown mechanization
- Closure validation (position/attitude error bounds)
- Runtime benchmarks and configuration

**Key spec changes:** D-017 (Master ruling on UAV vertical-channel smoothness fix).

### [GNSS_AND_ATTACKS.md](GNSS_AND_ATTACKS.md)
GNSS signal model, receiver, and attack scenarios. Covers:
- GPS constellation, clean-signal atmospheric error models
- Weighted-least-squares receiver, RAIM calibration, PDOP
- Spoofing (drift-in, meaconing), jamming (CW, wideband), combined attacks
- Attack signatures validated against Radoš et al. 2024 and Borhani-Darian et al. 2024
- Single-antenna C/N0 correlation collapse under spoofing

**Key spec changes:** D-018 (Master: model cross-satellite C/N0 correlation), D-010 (RAIM weights from unified UERE budget).

### [REAL_DATA_JARLAUD2024.md](REAL_DATA_JARLAUD2024.md)
Real cold-atom interferometer data calibration and validation. Covers:
- Jarlaud et al. 2024 (*Nat. Commun.* 15:6406) dataset structure and access
- Classical MICAL accelerometer static-record white-noise calibration
- Atom interferometer per-shot residual extraction and per-2T robust σ
- Rotation-rate sensitivity and contrast-loss vs rotation
- Outlier / fringe-jump process (bursty, 9.0% rate at 2T=20 ms)
- FIELD-grade recommendation: 2T=20 ms, σ_shot=5.60 µg (1.11× paper value)

**Key spec changes:** D-014 (Master: split classical vs atom noise), D-015 (per-2T robust stats, outliers modelled), D-019 (Gilbert–Elliott outlier channel for quiet-mode CAI).

### [REFERENCES.md](REFERENCES.md)
Verified bibliography (IEEE style, grouped by topic). Covers:
- Federated learning for GNSS security (Khan, Chai, Liu G²FL, Namagembe)
- Adaptive/fault-tolerant fusion (Ren, Mehra, Carlson, Pardhasaradhi, Negru)
- Quantum sensing, quantum-FL (Hazarika, Chehimi/Saad, Wright, d'Armagnac/Jarlaud)
- GNSS attacks (Radoš, Borhani-Darian, Psiaki & Humphreys, Humphreys et al.)
- Dropped references with rationale (Kannamarlapudi, Meng, Gu — not found or misattributed)

**Verification:** All 22 DOIs in REFERENCES.md were resolved against Crossref/DataCite by the Master on 2026-09-24. 3 DOI-less entries (a conference paper and textbooks) are still pending a catalogue check.

---

## Architecture and system design

### [specs/ARCHITECTURE.md](specs/ARCHITECTURE.md)
Full system architecture specification (WP-1.1). Covers:
- Module map and per-tick dataflow (environment ↔ agent half at node boundary)
- Sampling rates (100 Hz tick, 1–10 Hz GNSS, ~0.6 Hz quantum)
- 15-state loosely-coupled error-state EKF with quantum-sensor and GNSS observations
- Continuous trust law (continuous soft-weighting, not binary detect-and-exclude)
- Trust-coupled closed-loop detector (MLP trained by FL on hindsight pseudo-labels)
- TRIM-NB-R robust aggregator, FedAvg/FedProx baselines
- 30 paired seeds, Wilcoxon + Holm rank tests

**Contract v0.2 changes:** `Innovation` type, `QuantumSample.t_interrogation`, `GnssEpoch.for_agent()` (strips `meta`), `GnssFix.pdop`.

---

## Project state and decision logs

### [PROJECT_STATE.md](../PROJECT_STATE.md)
High-level project state summary. Covers:
- Completed work packages (WP-1.1, 1.2, 2.5, 3.1, 3.2)
- In-flight and pending work packages
- Known risks and mitigation (R-3: multi-hour runtime headroom needed for 4 h × N-node E2E harness)
- Deferred enhancements and follow-ups

### [DECISION_LOG.md](../DECISION_LOG.md)
Master's rulings and decisions (D-001 through D-019, plus ratified PROPOSED-DECISIONs). Key decisions:
- **D-001:** Pure software simulation (no GNSS RF, no quantum hardware)
- **D-002:** Results reported exactly as measured; all ASSUMPTION values get sensitivity sweeps
- **D-003:** ENU frame, 100 Hz tick, FLU body frame, ZYX Euler angles
- **D-013:** Bibliography verification gate (all DOIs cross-checked)
- **D-014:** Classical vs atom noise split (MICAL is classical, per-shot residuals are quantum)
- **D-015:** Per-2T robust statistics (5.6 µg at 2T=20 ms, outliers are real bursts)
- **D-017:** UAV vertical-channel smoothness fix (spec defect, not tolerance problem)
- **D-018:** Single-antenna C/N0 correlation signature modelling
- **D-019:** Quantum-sensor outlier / fringe-jump as Gilbert–Elliott bursty channel

### [EXECUTION_LOG.md](../EXECUTION_LOG.md)
Agent execution history and reproducibility trace. Records all WP runs, seeds, git commits, and integration checkpoints.

---

## Quick reference: where to find...

| Topic | Document |
|-------|----------|
| Trajectory generation, strapdown, integration runtime | [SIMULATION.md](SIMULATION.md) §2–4 |
| GPS constellation, GNSS receiver, WLS weight formula | [GNSS_AND_ATTACKS.md](GNSS_AND_ATTACKS.md) §1–3 |
| Spoofing carry-off, meaconing, jamming models | [GNSS_AND_ATTACKS.md](GNSS_AND_ATTACKS.md) §4–5 |
| RAIM calibration, attack blindness validation | [GNSS_AND_ATTACKS.md](GNSS_AND_ATTACKS.md) §3, test references |
| Quantum-sensor white-noise calibration (classical MICAL) | [REAL_DATA_JARLAUD2024.md](REAL_DATA_JARLAUD2024.md) §2 |
| Atom interferometer per-shot σ, 2T=20ms field grade | [REAL_DATA_JARLAUD2024.md](REAL_DATA_JARLAUD2024.md) §11.3, parameter table |
| Outlier fringe-jump process, Gilbert–Elliott model | [REAL_DATA_JARLAUD2024.md](REAL_DATA_JARLAUD2024.md) §11.3 |
| Verified bibliography with DOI links | [REFERENCES.md](REFERENCES.md) |
| System dataflow, per-tick sequence, filters | [specs/ARCHITECTURE.md](specs/ARCHITECTURE.md) §1–2 |
| Baseline method definitions (A, B-bin, B-cont, B′) | [specs/ARCHITECTURE.md](specs/ARCHITECTURE.md) §5 |
| Trust law, continuous weighting, hysteresis | [specs/ARCHITECTURE.md](specs/ARCHITECTURE.md) §3.3 |
| FL client, aggregator, comms, round timing | [specs/ARCHITECTURE.md](specs/ARCHITECTURE.md) §4, §8 |

---

## Data access and scripts

### Real data reproduction

```bash
# Fetch, parse, and validate Jarlaud et al. 2024 dataset
python scripts/jarlaud2024_manifest.py         # Create manifest.csv
python scripts/jarlaud2024_calibrate.py        # Classical MICAL calibration
python scripts/jarlaud2024_atom_residuals.py   # Atom per-shot residuals, per-2T stats
python -m pytest tests/test_data_jarlaud.py -v # Validation (9 tests)
```

### Simulation and attack validation

```bash
# Trajectory and strapdown
python -m pytest tests/test_sim_*.py -v                # Trajectory grammar, strapdown closure (113 tests)

# GNSS receiver and attacks
python -m pytest tests/test_gnss_receiver.py -v        # Receiver, PDOP, clean-signal validation (27 tests)
python -m pytest tests/test_gnss_raim_calibration.py -v # RAIM calibration and blindness under attack
python -m pytest tests/test_attacks_spoofing.py -v      # Attack signature checks
python scripts/gen_gnss_attack_results.py              # Generate signature_summary.txt
```

### Output files and results

- **Trajectories:** `results/trajectories/` (position, velocity, attitude over time)
- **GNSS signatures:** `results/attacks/signature_summary.txt`, `dop_distribution.txt`, `jamming_severity_sweep.png`
- **Data calibration:** `data/processed/jarlaud2024/calibration.json`, `atom_residual_summary.json`, `atom_outliers.json`
- **Plots:** `results/data/jarlaud2024_contrast_vs_rotation.png`, noise vs rotation, classical/atom ADEV

---

## Status and verification

**Documentation scope:**
- ✓ Trajectory simulation (WP-1.2, agents: SIM-IMPL → DOCUMENTATION)
- ✓ GNSS signal and attack models (WP-3.1, 3.2, agents: ATTACK → DOCUMENTATION)
- ✓ Real quantum-sensor data (WP-2.5, agents: DATA-INGEST → DOCUMENTATION)
- ✓ Bibliography curation (WP-10.0, agents: REF-VERIFY → DOCUMENTATION)
- ✓ System architecture (WP-1.1, ARCHITECT agent)
- ✓ Project state and decisions (Master-maintained DECISION_LOG.md, EXECUTION_LOG.md, PROJECT_STATE.md)

**Documentation verification:**
- All numeric values and DOI citations copied exactly from source files
- All ASSUMPTION and UNVERIFIED labels visible and preserved
- All decision-log cross-references (D-NNN) included with brief rationale
- Markdown structure and formatting per GitHub-flavored Markdown (GFM)
- No marketing language or filler; accurate, terse, source-linked

---

## Related documents (read-only for DOCUMENTATION agent)

- `docs/specs/ARCHITECTURE.md` (ARCHITECT, WP-1.1; read-only, not updated by DOCUMENTATION)
- `docs/specs/raw/*_NOTES.md` (terse agent output, now transformed into polished docs)

## Suggested next steps for other agents

1. **FUSION+TRUST (WP-4.x):** Implement the EKF (§2, ARCHITECTURE), trust law (§3.3), detector (§3.2), pseudolabeler (§4.3). Cross-validate signatures from [GNSS_AND_ATTACKS.md](GNSS_AND_ATTACKS.md) and quantum trust from [REAL_DATA_JARLAUD2024.md](REAL_DATA_JARLAUD2024.md).

2. **FEDERATED (WP-5.x):** Implement FL client, server, TRIM-NB-R aggregator (§4, §8 ARCHITECTURE). Test with paired seeds per baseline definitions (§5 ARCHITECTURE) and decision D-011.

3. **EVALUATION (WP-6.x/7.x):** Pre-register hypotheses (H1–H4), design acceptance criteria (S1–S15), implement metrics (§6 ARCHITECTURE, EVALUATION.md when ready).

4. **PAPER DRAFTING:** Use [REFERENCES.md](REFERENCES.md) bibliography. Baseline claims per D-011 (mechanism classes, not paper re-implementations). Quantum-sensor numbers from [REAL_DATA_JARLAUD2024.md](REAL_DATA_JARLAUD2024.md) (D-014 split: classical MICAL 9.1 µg/√Hz, atom 5.6 µg at 2T=20ms). Acknowledge all [ASSUMPTION] values and planned sensitivity sweeps (D-002).

---

**Last updated:** 2026-09-24 · **Documentation Agent:** Haiku 4.5 (DOCUMENTATION role)
