# FedQPNT — Work Breakdown Structure

Legend: **Wave** = earliest wave a package can start. `→` = hard dependency.
Agent roles per master prompt. Every package ends with a structured agent report and Master verification.

## M0 — Foundations (Wave 1, parallel)
| ID | Package | Agent | Depends | Acceptance |
|---|---|---|---|---|
| WP-0.1 | Data contracts v0.1 (`core/types.py`, `interfaces.py`, `seeding.py`) | Master | — | **DONE** |
| WP-1.1 | System architecture spec: module map, trust-engine equations, fusion filter (error-state EKF) design, federated protocol, what is learned/shared, metric definitions, acceptance thresholds for test matrix | ARCHITECT | 0.1 | `docs/specs/ARCHITECTURE.md` reviewed by Master |
| WP-1.2 | Truth trajectory generators (ground vehicle, UAV) + run config/loader + run recorder | ARCHITECT | 0.1 | kinematic consistency tests pass |
| WP-2.1 | Cold-atom accelerometer model (Wright 2022 + 2023–26 literature), Allan variance validated | QUANTUM-SENSOR | 0.1 | model ADEV matches cited figures within tolerance |
| WP-2.2 | Classical IMU model (MEMS + tactical grade; IEEE-952 style ARW/VRW/bias-instability/RW) | QUANTUM-SENSOR | 0.1 | ADEV validation vs datasheet figures |
| WP-3.1 | GNSS constellation + clean observables + receiver PVT/RAIM/lock logic | ATTACK | 0.1 | static/dynamic PVT error, DOP sanity |
| WP-3.2 | Spoofing (drift-in / meaconing / replay) + jamming (CW, wideband) on raw observables | ATTACK | 3.1 | signatures match cited papers; labels exact |

## M1 — Single-node closed loop (Wave 2)
| WP-4.1 | Error-state EKF: IMU mechanisation + quantum aiding + GNSS updates, trust-scaled R | FUSION+TRUST | 1.1, 2.x, 3.1 | nominal RMSE bounded, NEES consistent |
| WP-4.2 | Anomaly detectors (innovation χ², C/N0/AGC, clock-jump, IMU/quantum consistency) + learnable trust model | FUSION+TRUST | 1.1 | — |
| WP-4.3 | Continuous trust update w/ hysteresis + anti-chattering + recovery | FUSION+TRUST | 4.2 | oscillation test passes |
| WP-8.1 | E2E harness v1 (real processes, real file I/O), scenario runner | TESTING | 1.2 | runs nominal + 1 attack end-to-end |

## M2 — Federation (Wave 3)
| WP-5.1 | Multi-process client/server (sockets or multiprocessing queues), comms delay/dropout sim | FEDERATED | 4.2 | — |
| WP-5.2 | Aggregators: FedAvg, FedProx, trust-aware robust aggregation (poisoning defence) | FEDERATED | 5.1 | poisoning test passes |
| WP-5.3 | Cold-start node join, partial failure, delayed updates | FEDERATED | 5.1 | — |

## M3 — Baselines + Evaluation (Wave 3–4)
| WP-6.1 | Baseline A: FL detection only, fixed trust (Khan/Chai style) | BASELINE | 5.1 | same fusion core |
| WP-6.2 | Baseline B: single-node adaptive fusion, no FL (Meng/Gu style) | BASELINE | 4.3 | same fusion core |
| WP-6.3 | Ablations: −quantum, −FL, −trust, fixed-vs-continuous trust | BASELINE | 6.1, 6.2 | — |
| WP-7.1 | Metrics + Monte-Carlo runner + paired significance tests | EVALUATION | 8.1 | — |

## M4 — Full test matrix (Wave 4) — 15 scenarios from master prompt, TESTING owns
## M5 — Visualization, paper, patent, reproducibility package (Wave 4–5)
| WP-9.x | Architecture/workflow diagrams, result figures | VISUALIZATION |
| WP-10.x | Paper (IEEE T-ITS target), patent claim skeleton | PAPER |
| WP-11.x | Reproducibility package, README, one-command reproduce | DOCUMENTATION |
