# FedQPNT — Project State

_Last updated: 2026-09-30 by Master · repo: private https://github.com/Praty0512/fedqpnt (`master`, pushed, HEAD beb3561) · decisions up to D-072 · log up to #137 · live agent registry: `AGENTS_ACTIVE.md`_

## Identity
Federated learning across vehicle/UAV nodes. Each node fuses a cold-atom quantum accelerometer (CAI), GNSS and a classical IMU behind a continuous, attack-adaptive trust engine; the detector improves fleet-wide via FL, and no raw data leaves a node.
- **Baselines** (D-011): A = FL detection → detect-and-exclude; B-bin = single-node detect-and-switch; B-cont = single-node continuous trust without FL; B′ = innovation-χ² adaptive KF; plus undefended, fixed_trust and abl_minus_quantum.
- All results so far are on **tuning seeds**. Test seeds [10000, 20000) are untouched, gated in code (`fedqpnt/eval/seed_gate.py`, `results/GATE_D047.json` = not cleared).

## Milestones
| Milestone | Status |
|---|---|
| **M0 — Foundations** | ✅ Signed off 2026-09-26 |
| **M1 — Single-node closed loop** | 🔶 Re-opened on the new core. **All approved core fixes are implemented and committed** (D-061…D-072). The re-verification waits for detector v3 |
| **M2 — Federation** | 🔶 FL sanity PASS (D-056). H2/H4 are not yet demonstrated (the earlier run was invalid, D-062). Pre-registered event-level protocol (D-064); telemetry committed; the re-run waits for the freeze + θ0 retrain |
| **M3 — Eval/stats** | 🔶 Pipeline reconciled with the spec (D-067/D-068/D-070): bounded seed gate, a fixed 8-test Holm family, the scenario registry brought to intent, latency_eff, provenance checks, the IMU-grade dimension. The runner output additions (P1–P3) are in progress |
| **M4 — Full campaign** | ⛔ Gated (needs freeze → v3 → re-verification → σ_nom → gate decision) |
| **M5 — Deliverables** | 🔶 Done: patent skeleton, 4 architecture figures, repro docs, module docs, references (clock refs verified). **Paper:** Sections II–V drafted; 21 references await your verification; the trust-law section, results and abstract wait for data |

## Core changes since 2026-09-29 (all committed, Master-verified)
| Change | Why | Commit |
|---|---|---|
| κ_R = 60 single source of truth | D-061's value had never become the default (runs used 40) | 09a2b30 |
| ClockKF holdover + TCXO clock model (truth = filter; cited) | Timing was unprotected; the truth clock was ~4000× too stable | 3699c1d |
| Shadow probe + consistency-based reacquisition | Probing let a spoof drag the state; slow post-jam recovery | 18e3207 |
| Probe NIS bound calibrated per IMU grade on clean data | The pre-registered rule triggered (MEMS false-veto 3.3%) | 726bc35 |
| Clock-jump features normalised by predicted TCXO drift over gaps | Post-jam false alarms with the realistic clock | bb79915 |
| Position/clock trust split (w_pos, w_clk) | Meaconing (a clock anomaly) was costing position | c288e69 |
| Displaced meaconer attack + truth offset channel on all spoofs | New threat; needed for latency_eff | 0183f6e, ee7498c |
| Eval fixes: seed gate, S2 P_D bug, 8-test family, scenarios to intent, S6 = H3 | Spec/code audit | 352c920, 2165a17, de314b9 |

## Key results so far (tuning seeds; mostly measured BEFORE the latest fixes)
- **CAI coasting benefit** (180 s outage, max horizontal error): MEMS 1339 → 645 m; tactical 400 → 119 m (2.1–3.4×).
- **Post-jam recovery** (after the fixes, seed 500): tactical 5.1 m, MEMS 25.6 m (was 314 m, no recovery).
- **Stated limits found:**
  - on MEMS, spoofs under ~50 m can pass the consistency probe (damage bounded by the coast);
  - a 750 m clock step right after a 180 s outage is only 2.9σ for a TCXO;
  - the detector fails below signature strength s = 0.5.
- **Defended vs undefended:** the old numbers (worse in all attacks) are superseded. They are to be re-measured with detector v3.

## Running now
| Agent | Work |
|---|---|
| SCENARIO-FIX (Sonnet) | Runner additions: seed gate at the lowest level, detection/covariance/offset outputs, new RunSpec fields (bit-identity required) |
| DETECTOR-V3 (Sonnet) | Prepared; waits for "core frozen" |
| CORE-ROBUST (Sonnet) | Standby; re-verification plan ready |

## What is still left (in order)
1. **Finish the runner additions** (SCENARIO-FIX) → Master verification → **freeze the core** (git tag).
2. **Detector v3 retrain** (same protocol, 6 families) + S1 check + displaced-meaconer generalisation check.
3. **Combined M1 re-verification** with v3 at both IMU grades: smoke (7 methods), coasting, S1 false alarms, safety sweep, drift/jam traces, meaconing split effect. **This is the decisive test of whether defended ≥ undefended.** If it still fails, diagnose again or report it as a finding.
4. **H2/H4 (the core FL claim):** retrain θ0_noabrupt on the frozen core → τ calibration (seeds 580–599) → n = 10 fleet re-run → pre-registered D-064 metrics → M2 sign-off, or an honest null.
5. **σ_nom measurement** (seeds 560–579, per grade) and the S7 chattering bound re-derived from the frozen config → pre-registration file.
6. **Gate decision** → clear the test-seed gate.
7. **M4 campaign on test seeds:** 15+ scenarios × methods × 30 seeds × 2 IMU grades (the heaviest compute step; many hours).
8. **M3 report** (confirmatory Holm family + exploratory) and **result figures**.
9. **Paper completion:**
   - trust-law section, results, discussion, limitations, abstract;
   - verify 21 references (you, via Consensus);
   - compile (needs a LaTeX install; your approval).
10. **Patent revision** (shadow probe, split trust as claim candidates); filing timing is your decision.
11. **Reproducibility package:** final README/REPRODUCE refresh, pinned environment, results manifest, and a release tag.
12. Optional/deferred: ESKF speed-ups (after the freeze, bit-identical only).

## Waiting on the user
- Consensus verification of the 21 paper references (the query list was given in chat).
- Approval to install a LaTeX distribution (e.g. MiKTeX, several hundred MB) to compile the paper.
- Patent: filing timing and attorney review.
- Keep approving edit prompts as agents touch core files.
