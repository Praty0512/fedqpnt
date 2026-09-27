# FedQPNT — Project State

> **▶ RESUMED 2026-09-27, concurrency cap = 3 (D-040).** Running: FILTER-GNSS (queue item 1), FEDERATED (item 8), PAPER (item 6, text only). Queue:
> 1. D-038 item 3 (gating): receiver cov_vel honesty + GNSS-aided per-block NEES → fixes κ_R = 40 / MEMS overconfidence. Then D-038 items 1–2 (MEMS tilt-linearisation confirmation; D-036 P0 artefact check). (D-036 itself is done.)
> 2. κ_R re-tune (`scripts/tune_kappa_r.py`).
> 3. Retrain the detector on real closed-loop features.
> 4. Re-run the M1 smoke matrix plus FAR/h → M1 sign-off.
> 5. Runtime optimisation.
> 6. Paper skeleton + Related Work; architecture diagrams.
> 7. M2 integration of FL with the real node pipeline.
> 8. D-039: re-run S12 at N = 10 (the N = 5 run FAILED at 0.063 > 0.05; root cause fixed); fix the class-balance zero-negative dead zone at M2 integration.

_Last updated: 2026-09-26 by Master_

## Identity
Federated learning across vehicle/UAV nodes. Each node fuses a cold-atom quantum accelerometer, GNSS and a classical IMU behind a **continuous, attack-adaptive trust engine**. Trust/detection models improve fleet-wide via FL, and no raw sensor data leaves a node. The system must beat (A) FL detection → detect-and-exclude, (B-bin) single-node detect-and-switch, and (B-cont) single-node continuous trust without FL, under realistic spoofing/jamming (D-011).

## Milestones
| Milestone | Status |
|---|---|
| **M0 — Foundations** | ✅ **Signed off 2026-09-26** (186/186 tests; EXECUTION_LOG #36) |
| M1 — Single-node closed loop (ES-EKF, detector, trust law, E2E harness v1) | 🔄 Wave 2 starting |
| M2 — Federation (multi-process, aggregators, comms, cold start) | ⏳ |
| M3 — Baselines, ablations, evaluation, statistics | ⏳ |
| M4 — Full 15-scenario test matrix | ⏳ |
| M5 — Figures, paper, patent, reproducibility package | ⏳ (reference gate D-012 cleared) |

## Module status
| Module | WP | Status | Owner |
|---|---|---|---|
| Core contracts | 0.1 | ✅ v0.2 (D-009) | Master |
| Architecture spec | 1.1 | ✅ ratified (D-009, D-011) | ARCHITECT (Opus) |
| Trajectories, strapdown, config, recorder | 1.2 | ✅ 115 tests | SIM-IMPL (Sonnet) |
| Quantum sensor + IMU + ADEV | 2.1–2.3 | ✅ 27 tests; FIELD = primary grade (D-021) | QUANTUM-SENSOR (Sonnet) |
| Real data: Jarlaud 2024 | 2.4–2.5 | ✅ 12 tests (D-014, D-015, D-019) | DATA-INGEST (Sonnet) |
| GNSS + receiver + attacks | 3.1–3.2 | ✅ 32 tests (D-010, D-018) | ATTACK (Sonnet) |
| Verified bibliography | 10.0 | ✅ D-013; 3 DOI-less entries still need a catalogue check | REF-VERIFY (Sonnet) |
| Docs | 11.1 | ✅ `docs/` | DOCUMENTATION (Haiku) |
| ES-EKF fusion | 4.1 | 🔄 Wave 2 | FUSION (Sonnet) |
| Features, detector, trust law | 4.2–4.3 | 🔄 Wave 2 | TRUST (Sonnet) |
| E2E harness v1 + leakage guard | 8.1 | ⏳ next slot | TESTING (Sonnet) |

## Key measured/decided numbers
- **CAI FIELD grade** (real data): 2T = 20 ms, σ_shot = 5.60 µg (1.11× paper), cycle 1.548 s, N = 6.97 µg/√Hz, C0 = 0.394, Ω_c = 17.3 mrad/s (1/T² scaling from 48.2 at 2T = 12 ms); bursty outliers 9% with 66% persistence.
- **GNSS**: clean horizontal error ~3.5 m; RAIM χ² calibrated (0.96–1.09 × (n−4)); consistent spoofing is RAIM-blind (KS p = 0.99).

## Open risks
| ID | Risk | Mitigation |
|---|---|---|
| R-1 | The rigid-mode CAI loses contrast in normal turns (Ω_c ≈ 17 mrad/s), so quantum aiding is intermittent | Report honestly (D-014, D-020); include inertial-pointing NEAR_FUTURE as a sensitivity case |
| R-2 | FL may add little over local adaptive fusion (B-cont) | Pre-registered H2/H4; cold-start and novel-attack scenarios; report whatever the outcome (D-002) |
| R-3 | Runtime: IMU 11–32 s, strapdown 19–33 s, GNSS 7–88 s per sim-hour per node | Budget in the harness; accelerate hot loops if the 4 h × N-node runs are too slow |
| R-4 | Agent output overstates verification | Master re-runs tests and re-resolves DOIs on every report (done so far) |
| R-5 | Usage-limit interruptions | Concurrency cap of 2 (D-016); resume agents in place |
| R-6 | MEMS gyro tilt may dominate over the CAI benefit | Report MEMS and tactical grades separately |

## Work queue (cap = 2), as of EXECUTION_LOG #47
- Done: FUSION (WP-4.1), TRUST (WP-4.2/4.3, detector design frozen per D-026), node integration (WP-8.1).
- Running: D-028 ESKF fix (dynamics-dependent Q inflation for unmodelled IMU SF/misalignment).
1. After D-028: re-tune κ_R (`scripts/tune_kappa_r.py`) → retrain the frozen detector on REAL closed-loop features (seeds 500–599) → re-run the M1 smoke plus clean-run FAR/h (D-029). Resume the integration agent.
2. Runtime optimisation (ESKF propagate, eigvalsh PSD check, so3_exp, IMU channel step), after the eskf.py edits settle.
3. M1 sign-off, then M2 (federation).
3. User actions: full-text check of Khan 2025, Chai 2025 and Pardhasaradhi 2022 (paywalled); catalogue check of the 3 DOI-less references.
