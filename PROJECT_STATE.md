# FedQPNT — Project State

_Last updated: 2026-09-29 by Master · repo: private https://github.com/Praty0512/fedqpnt (`master`, pushed, HEAD 062360a) · decisions up to D-066 (+ clock addendum) · log up to #121 · live agent registry: `AGENTS_ACTIVE.md`_

## Identity
Federated learning across vehicle/UAV nodes. Each node fuses a cold-atom quantum accelerometer (CAI), GNSS and a classical IMU behind a continuous, attack-adaptive trust engine; the detector improves fleet-wide via FL, and no raw data leaves a node.
- **Baselines** (D-011): A = FL detection → detect-and-exclude; B-bin = single-node detect-and-switch; B-cont = single-node continuous trust without FL; B′ = innovation-χ² adaptive KF; plus undefended and fixed_trust.
- All results so far are on **tuning seeds**. Test seeds (10000+) are untouched and gated (`results/GATE_D047.json` = not cleared).

## Milestones
| Milestone | Status |
|---|---|
| **M0 — Foundations** | ✅ Signed off 2026-09-26 |
| **M1 — Single-node closed loop** | ✅ Signed off 2026-09-28 (D-053), **re-opened**: on the new core, defended is worse than undefended in the smoke matrix. All causes are now diagnosed and the fixes approved (D-066); implementation starts next |
| **M2 — Federation** | 🔶 FL sanity PASS (D-056). **H2/H4 not yet demonstrated**: the abrupt run was invalid (D-062). Event-level metrics are pre-registered (D-064, `docs/specs/raw/H2_PREREG.md`); the per-epoch fleet telemetry is being added; the re-run waits for core freeze |
| **M3 — Eval/stats** | 🔶 Pipeline done (15 scenarios, fleet adapter, stats, report). The report waits for M4 |
| **M4 — Full campaign** | ⛔ **GATED** until the core is frozen and defended ≥ undefended is shown (or understood and stated) |
| **M5 — Deliverables** | 🔶 Done: patent claim skeleton, 4 architecture figures, README/REPRODUCE/DATA/CITATION, module docs, bibliography, ARCH CAI-cycle doc fix. **Paper:** Sections II–III drafted; IV–V in progress. The patent revision (shadow probe, split trust) comes after implementation |

## Key results so far (tuning seeds, κ_R = 60)
- **S1 (nominal):** FAR 0/h, ANEES_pos 0.875, RMSE ratio 0.988 vs fixed trust.
- **CAI coasting benefit** (180 s GNSS outage, max horizontal error): MEMS 1339 → 645 m; tactical 400 → 119 m (**2.1–3.4×**).
- **Detector:** drift/meaconing AUC ≥ 0.99 for signature strength s ≥ 0.5; inverted below (D-055).
- **Defended vs undefended (tactical smoke, before the D-066 fixes):**

| Attack | Defended | Undefended |
|---|---|---|
| drift | 115 m | 108 m |
| meaconing | 6.6 m | 2.5 m |
| post-jam | 10.7 m | 3.1 m |
| meaconing timing | 1.28 µs | 1.36 µs |

## Root causes found → approved fixes (D-061 … D-066)
| Symptom | Root cause | Fix | Status |
|---|---|---|---|
| No recovery after jamming (314 m) | Stale E_s jump-test baseline across the outage | Gap reset + 2-epoch quarantine | ✅ Committed (906ae98) |
| Drift: defended worse than coasting | PROBE (w = 0.3) re-admits the spoof and drags the state | **Shadow probe**: test GNSS against the coast without applying it | Approved, next |
| Slow post-jam re-admission | Reacquisition cap + τ_r ramp | Waive the cap when the first fix agrees with the coast | Approved, next |
| Meaconing costs position | One scalar trust for position and clock | **Position/clock trust split** | Approved, next |
| Timing not protected | ClockKF has no holdover; the clock model was unrealistic | ClockKF holdover + **TCXO clock model** (truth and filter matched) | Approved, first |

## Running now
| Agent | Work |
|---|---|
| H2-ABRUPT (Sonnet) | Per-epoch fleet telemetry in node_runner.py (golden bit-identity test); running the suite. Then parked until core freeze |
| CORE-ROBUST (Sonnet) | Waiting for the telemetry to land → (i) clock holdover + TCXO, (ii) shadow probe + reacquisition, (iii) trust split → one combined re-verification at both IMU grades |
| PAPER (Sonnet) | Sections IV (Method) + V (Evaluation protocol) |

## Next
1. Land the H2 telemetry → CORE-ROBUST implements (i) → (ii) → (iii) → combined re-verification (smoke with 7 methods × 2 IMU grades, coasting, S1, safety sweep).
2. Freeze the core → H2/H4 re-run under the pre-registration → M2 sign-off, or report the null.
3. Add the displaced-meaconer scenario (MEACON agent); revise the patent claims.
4. Gate decision → M4 campaign on test seeds (15 scenarios × methods × 30 seeds × 2 IMU grades) → M3 report → result figures → complete the paper.

## Waiting on the user
- **Please verify via Consensus:** Brown & Hwang, *Introduction to Random Signals and Applied Kalman Filtering*, 4th ed. (Wiley, 2012), TCXO clock values h₀ ≈ 2×10⁻¹⁹ and h₋₂ ≈ 2×10⁻²⁰.
- Patent: filing timing and attorney review (your decision).
- Keep approving edit prompts for fedqpnt/trust, fusion, gnss and node as agents touch them.
