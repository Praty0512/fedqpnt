# FedQPNT — Project State

_Last updated: 2026-09-29 by Master · repo: private https://github.com/Praty0512/fedqpnt (`master`, pushed) · decisions up to D-065 · log up to #120 · live agent registry: `AGENTS_ACTIVE.md`_

## Identity
Federated learning across vehicle/UAV nodes. Each node fuses a cold-atom quantum accelerometer (CAI), GNSS and a classical IMU behind a continuous, attack-adaptive trust engine; the detector improves fleet-wide via FL, and no raw data leaves a node.
- **Baselines** (D-011): A = FL detection → detect-and-exclude; B-bin = single-node detect-and-switch; B-cont = single-node continuous trust without FL; B′ = innovation-χ² adaptive KF; plus undefended and fixed_trust.
- All results so far are on **tuning seeds**. Test seeds (10000+) are untouched and gated (`results/GATE_D047.json` = not cleared).

## Milestones
| Milestone | Status |
|---|---|
| **M0 — Foundations** | ✅ Signed off 2026-09-26 |
| **M1 — Single-node closed loop** | ✅ Signed off 2026-09-28, with limitations (D-053). **Re-opened on the new core:** defended is worse than undefended in the smoke matrix (D-061/D-063/D-065); fixes are in progress |
| **M2 — Federation** | 🔶 Infrastructure done and FL sanity PASS (D-056). **H2/H4 not yet demonstrated.** The abrupt run was INVALID (D-062: mixed code; inverted full-window AUC explained physically). Event-level metrics are pre-registered (D-064); the re-run is parked until core freeze |
| **M3 — Eval/stats** | 🔶 The pipeline is done, including all 15 scenarios via the fleet adapter (D-059). The M3 report waits for M4 |
| **M4 — Full campaign** | ⛔ **GATED**: needs a frozen core where defended ≥ undefended is shown, or understood and stated |
| **M5 — Deliverables** | 🔶 Done: patent claim skeleton, 4 architecture figures, README/REPRODUCE/DATA/CITATION, module docs, bibliography. **Paper:** Sections II–III drafted; IV–V (method, protocol) in progress (PAPER agent); results wait for M4 |

## Key results so far (tuning seeds, κ_R = 60)
- **S1 (nominal):** FAR 0/h, ANEES_pos 0.875, RMSE ratio 0.988 vs fixed trust.
- **CAI coasting benefit** (180 s GNSS outage, max horizontal error): MEMS 1339 → 645 m; tactical 400 → 119 m (2.1–3.4×).
- **Detector:** drift/meaconing AUC ≥ 0.99 for signature strength s ≥ 0.5; inverted below (D-055).
- **Defended vs undefended on the new core (open problem):**
  - drift: 115 vs 108 m (tactical);
  - meaconing: 6.6 vs 2.5 m;
  - post-jam: 10.7 vs 3.1 m;
  - timing under meaconing is not protected (1.28 vs 1.36 µs).
- **Causes found so far:**
  - jam lockout: fixed;
  - scalar trust conflates position and clock: split approved;
  - ClockKF has no holdover: fix approved;
  - probing into an ongoing spoof: suspected, under trace.
- **FL:** tracks centralised training; S12 poisoning mean-PASS at N = 10 (CI inconclusive).

## Running now
| Agent | Work |
|---|---|
| CORE-ROBUST (Sonnet) | Drift/probe trace → fix proposal; ClockKF holdover; post-jam residual; trust-split design note |
| H2-ABRUPT (Sonnet) | Per-epoch fleet telemetry (freeze window, golden bit-identity test); then parked until core freeze |
| PAPER (Sonnet) | Sections IV (Method) + V (Evaluation protocol) |
| DOCFIX (Haiku) | ARCH §1.2 CAI cycle doc drift |

## Open issues (ranked)
1. Defended ≥ undefended not yet achieved (D-063/D-065): probe-during-spoof, trust split, clock holdover, post-jam residual.
2. H2/H4 core FL claim: pre-registered re-run after the core freezes.
3. Safety principle (D-055): the literal bound fails by 1–5%; kept as pre-registered and reported as measured.
4. b_a NEES residual ~6× (effective-bias truth); ψ/b_g mild overconfidence: stated limitations.
5. ESKF-level speedups (after freeze).

## Next
1. Freeze the core after the CORE-ROBUST fixes → re-verify M1 (smoke at both IMU grades, S1, safety sweep).
2. H2/H4 re-run under the pre-registration → M2 sign-off, or report the null.
3. Gate decision → M4 campaign on test seeds (15 scenarios × methods × 30 seeds × 2 IMU grades) → M3 report.
4. Result figures → complete the paper.

## Waiting on the user
- Patent: filing timing and attorney review (your decision).
- Keep approving edit prompts for fedqpnt/trust, node, fusion and clock as agents touch them.
