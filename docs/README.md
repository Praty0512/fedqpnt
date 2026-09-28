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

## Federated Learning and Training

### [FEDERATION.md](FEDERATION.md)
Federated learning transport layer, aggregators, and poisoning resilience. Covers:
- FL transport (bulk-synchronous, multiprocessing spawn, deterministic RNG)
- Aggregators: FedAvg, FedProx, TRIM-NB-R (with byzantine robustness)
- Communications model (Gilbert-Elliott fading, LogNormal delay)
- Poisoning attacks: sign-flip, label-flip, gaussian-noise, ALIE
- Cold-start and staleness handling
- Known bugs (server message buffering, model installation tuple unpacking) with fixes and regression tests
- S12 poisoning at N=5 and N=10 (TRIM-NB-R PASS at spec size)
- S5/S9 comms-loss results (both PASS)

**Key spec changes:** D-037 (real bugs found via multiprocess validation), D-039 (dead-zone fix at scale), D-050 (fleet infrastructure accepted).

### [FLEET.md](FLEET.md)
Fleet runner, θ0 pretraining protocol, and evaluation redesign. Covers:
- N-node federated loops (Environment + Agent) with live detector updates
- θ0 restricted-family pretraining (D-054): excludes novel family from pretraining so "never saw X" test is fair
- FL sanity check (D-056): FedAvg/TRIM-NB-R ≥ 0.95× centralised on IID data — **PASS** (AUC 0.996–0.998)
- H2/H4 evaluation protocol redesign: report learned-detector-only AUC separately from operational p_bar; novel family in sub-rule regime
- Fleet validation: infrastructure PASS, deterministic, 52–55 s per fleet-hour at N=5
- FedAvg uncapped-gradient anomaly diagnosis (designed vulnerability, not scoring bug)

**Key spec changes:** D-050 (fleet runner), D-054 (θ0 protocol and H2/H4 redesign), D-056 (sanity check).

### [EVALUATION.md](EVALUATION.md)
Evaluation framework: statistics, scenarios, campaign runner, and report generator. Covers:
- Statistical methods: Wilcoxon + conditional paired t-test, Hodges-Lehmann CI, Holm-Bonferroni, Friedman+Nemenyi, exact McNemar
- Scenario registry (S1–S15): acceptance criteria, blocking status (D-046/D-047 gate on CAI-related scenarios)
- Campaign runner: resumability, test-seed gate (≥ 10000), worker cap=4
- Dry-run plumbing verification (proved resumability)
- Report generator (Markdown + CSV, per-scenario tables, H1–H4 hypothesis tests)

**Key spec changes:** D-048 (σ_nom per-run measured, final offset used, S5/S8/S9/S12/S15 NOT_RUNNABLE until fleet/protocol finalized).

### [TRAINING.md](TRAINING.md)
Supervised detector training, trust law v2, and signature-strength validation. Covers:
- Supervised primary path (D-052): `fedqpnt/training/build_supervised_dataset.py` is ONLY place AttackLabel joins features; no label leakage at runtime
- Label-free pseudo-labelling relegated to ablation (D-049 gate A failed, D-052)
- Labeller v2 sigma floors; class-weight cap 10× (D-050/D-051); Platt calibration
- Signature-strength sweep (D-055): s < 0.5 failure boundary; s < 0.25 inverted (AUC 0.129); actively harmful RMSE (2.3 km vs 108 m undefended)
- 6-family rebalancing (D-053a): jammer EIRP calibrated per severity (old: 8 jam epochs; new: 1590 jam positives, all families ≥ 500)
- Detector v2 AUC: drift 0.998, meaconing 0.999, abrupt 0.691 (regressed, honest report), jam_cw 0.996, jam_wideband 0.988, jam_then_spoof 0.997, overall 0.953
- Trust law v2 state machine (TRUST/DISTRUST/PROBE/RECOVER, 70 s cycle bound)
- S1 v2: FAR 0.0/h, RMSE ratio 0.9904, ANEES 1.306 — **all PASS**
- E_s redesign (D-058): short-baseline jump test (independent of filter divergence artifacts)
- Core-robustness session planned (D-058): soft gating, E_s jump test, eigenvalue clip, overconfidence investigation

**Key spec changes:** D-026 (freeze), D-029 (real features), D-049 (recalibration and anti-lockout), D-051 (trust law v2), D-052 (supervised primary), D-053 (6-family rebalance), D-055 (safety principle + s < 0.5 boundary), D-058 (E_s redesign).

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
| FL transport, determinism, aggregators (FedAvg/FedProx/TRIM-NB-R) | [FEDERATION.md](FEDERATION.md) §1–5 |
| Poisoning attacks (sign-flip, label-flip, ALIE), S12 results | [FEDERATION.md](FEDERATION.md) §5–6 |
| Known FL bugs (server buffering, model installation) and fixes | [FEDERATION.md](FEDERATION.md) §5 |
| Fleet runner, θ0 pretraining protocol, novel-family evaluation | [FLEET.md](FLEET.md) §2–3 |
| FL sanity check (IID data, FedAvg 0.996, TRIM-NB-R 0.998) | [FLEET.md](FLEET.md) §3 |
| H2/H4 evaluation protocol (learned-only vs operational p_bar AUC) | [FLEET.md](FLEET.md) §4 |
| Statistical methods (Wilcoxon, Hodges-Lehmann, Holm-Bonferroni) | [EVALUATION.md](EVALUATION.md) §1 |
| Scenario registry (S1–S15), acceptance criteria, blocking status | [EVALUATION.md](EVALUATION.md) §2 |
| Campaign runner, resumability, test-seed gate, dry-run validation | [EVALUATION.md](EVALUATION.md) §3–4 |
| Supervised detector training, label sourcing, leakage guard | [TRAINING.md](TRAINING.md) §1–2 |
| Platt calibration, class-weight cap, labeller sigma floors | [TRAINING.md](TRAINING.md) §3 |
| Signature-strength sweep (s < 0.5 failure boundary, inversion at s=0) | [TRAINING.md](TRAINING.md) §4 |
| 6-family rebalance, jammer EIRP calibration (D-053a) | [TRAINING.md](TRAINING.md) §5 |
| Detector v2 AUC per family, S1 results (all PASS) | [TRAINING.md](TRAINING.md) §6–7 |
| Trust law v2 state machine (TRUST/DISTRUST/PROBE/RECOVER) | [TRAINING.md](TRAINING.md) §8 |
| E_s short-baseline jump test redesign, core-robustness session | [TRAINING.md](TRAINING.md) §9 |

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
- ✓ Federated learning stack (WP-5.1–5.3, FEDERATED agent → DOCUMENTATION)
- ✓ Fleet infrastructure and evaluation protocol (WP-5.3, M2 integration → DOCUMENTATION)
- ✓ Evaluation framework (WP-8.x, EVALUATION agent → DOCUMENTATION)
- ✓ Detector training and trust law (WP-4.x/6.x, TRUST/M1-CLOSE/DETECT-MIX agents → DOCUMENTATION)

**Documentation verification:**
- All numeric values and DOI citations copied exactly from source files
- All ASSUMPTION and UNVERIFIED labels visible and preserved; unclear items marked "(unclear in source)"
- All decision-log cross-references (D-NNN) included with brief rationale; DECISION_LOG overrides raw notes on conflicts
- Markdown structure and formatting per GitHub-flavored Markdown (GFM)
- No marketing language or filler; accurate, terse, source-linked
- Negative results (failures, regressions) reported honestly without softening
- Test counts and seed ranges (500–599 tuning, 9500–9699 sweep, ≥10000 test) preserved exactly

---

## Related documents (read-only for DOCUMENTATION agent)

- `docs/specs/ARCHITECTURE.md` (ARCHITECT, WP-1.1; read-only, not updated by DOCUMENTATION)
- `docs/specs/raw/*_NOTES.md` (terse agent output, now transformed into polished docs)

## Suggested next steps for other agents

1. **CORE-ROBUSTNESS SESSION (D-058, post H2-SUBRULE):** Soft covariance-scaling gating (D-057), E_s short-baseline jump test (D-058), eigenvalue clip (D-043), ψ/b overconfidence investigation (D-046/D-047), re-verify S1 + smoke matrix + κ_R re-tune, then re-attempt H2 sub-rule with new E_s.

2. **H2/H4 EVALUATION (post core-robustness, using revised evaluation protocol D-056):**
   - Report three separate quantities: learned-detector-only AUC (calibrated p, E_s excluded), operational p_bar AUC (fused), detection latency
   - Novel family in sub-rule regime (drift s ∈ {0.5, 0.75}, meaconing C/N0 bump < 3 dB)
   - θ0 pretrained on restricted families (e.g. jamming+abrupt; drift/meaconing novel)
   - ≥ 5 seeds with CIs
   - See [FLEET.md](FLEET.md) §4 for protocol details; [EVALUATION.md](EVALUATION.md) for campaign execution

3. **M4 FILTER SESSION (D-046/D-047):** Investigate ψ/b overconfidence (ANEES issues, S1 margin); κ_R re-tuning; parked eigenvalue hysteresis and outlier handling.

4. **PAPER DRAFTING:** Use [REFERENCES.md](REFERENCES.md) bibliography. Baseline claims per D-011. Quantum-sensor numbers from [REAL_DATA_JARLAUD2024.md](REAL_DATA_JARLAUD2024.md). **Acknowledge:**
   - All [ASSUMPTION] values and planned sensitivity sweeps (D-002)
   - κ_R = 40 PROVISIONAL (D-046/D-047 parked)
   - Minimum signature strength s ≳ 0.5 operating assumption; s < 0.5 failure boundary (D-055)
   - S5/S8/S9/S12/S15 scenarios: NOT_RUNNABLE until core-robustness session (D-048)
   - Abrupt AUC regression (0.754→0.691, D-055 honest report)
   - Anti-lockout mechanism not fully effective (D-049 diagnosis, awaiting core session fix)

---

**Last updated:** 2026-09-29 · **Documentation Agent:** Haiku 4.5 (DOCUMENTATION role) · **Files added:** FEDERATION.md, FLEET.md, EVALUATION.md, TRAINING.md
