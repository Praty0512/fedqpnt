# FedQPNT — Project State

_Date: 2026-10-13 · Status: **COMPLETE** · repo: private https://github.com/Praty0512/fedqpnt (`master`) · decisions up to D-089 · log up to #181_

## Identity
Federated learning across vehicle/UAV nodes. Each node fuses a cold-atom quantum accelerometer (CAI), GNSS and a classical IMU behind a continuous, attack-adaptive trust engine. The detector is trained across the fleet with FL, and no raw data leaves a node.

## Final code
- **Tag `core-freeze-6` = commit `ca614b7`.** Detector v5, fleet θ0 f8, κ_Q = 1, σ_nom 1.0977 m (MEMS) / 1.1171 m (tactical).
- Suite at freeze: 673 passed, 1 skipped, 0 failures (D-089).

## Milestones
| Milestone | Status |
|---|---|
| M0 — Foundations | ✅ Done |
| M1 — Single-node closed loop | ✅ Done (freeze-6, detector v5; limitations stated) |
| M2 — Federation (H2/H4) | ✅ Done. Null by ceiling, as measured on round 3 |
| M3 — Eval/stats | ✅ Done. Round-3 report `1bb82d18` |
| M4 — Test-seed campaign | ✅ Done. Round 3 (seeds 10060–10089) is the reported result. Rounds 1 and 2 are archived and superseded |
| M5 — Deliverables | ✅ Paper 21 pp (`c32f0d0d`), patent rev 3 (`e94f72b2`), reproduction guide |

## Round-3 results
Source: `results/m4r3/report/SUMMARY.md`. n = 30 per cell, 5,340/5,340 tasks ok, 0 errors.

- **Confirmatory family (Holm, m = 8):** only **H1 latency rejected** (S2-med MEMS vs Baseline A, Holm p = 0.0037). H1 RMSE not rejected (p = 1). **H2, H3, H4 null** (p = 1).
- **Safety (3σ_nom rule):** PASS at S1 and S3 (both grades) and at S2-DM MEMS. FAIL at the other spoofing cells (S2 levels, S4, S6, S7 at both grades; S2-DM tactical).
- **Chattering (S7):** at most 29 cycles/h against the 223/h bound. PASS everywhere.
- **S14 (4-h):** 60/60 done. Its no-slow-drift criterion is not evaluable in SUMMARY, so no drift claim is made.

**Where FedQPNT wins (as stated in the round-3 report):** faster detection (H1 latency); displaced-meaconer position (MEMS) and timing protection; no cost in nominal operation or under jamming; chattering far below the bound.

**Where it loses:**
- Worse than undefended under ordinary spoofing (the 3σ safety rule fails there).
- Slow re-admission of GNSS after the attack ends (designed T_ex = 60 s dwell plus the re-admission path).
- Lockout when GNSS noise is at least 2× the reported value (S11; stated limitation).

**CAI and FL:** no measurable effect (H3 null; H2/H4 null).

## Deliverables
- Paper: `paper/main.tex` (21 pp; `paper/main.pdf`; references `paper/refs.bib`). Results, discussion and abstract committed at `c32f0d0d`.
- Patent: `patent/CLAIMS_SKELETON.md` rev 3 (37 claims: 3 independent, 34 dependent). Draft for attorney review.
- Results: `results/m4r3/report/SUMMARY.md`, `HEADLINE.md`, `M3_REPORT.md`, `json/`; figures in `results/m4r3/figures/`.
- Pre-registration: `docs/specs/raw/PREREG_M4.md` (Amendment R3, written before round-3 data); `docs/specs/raw/H2_PREREG.md` (Amendment 3).
- Reproduction: `docs/REPRODUCE.md`. Logs: `DECISION_LOG.md` (D-089 latest), `EXECUTION_LOG.md` (#181).

## What is left for the user
1. Review the paper (`paper/main.tex`), especially the adverse results and the limitations sections.
2. Patent: attorney review and a prior-art search before any filing. The repo makes no filing recommendation.
3. Choose the publication venue.
4. Decide the license. The README still says "License: TBD".
