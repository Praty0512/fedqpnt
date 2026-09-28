# FedQPNT — Project State

_Last updated: 2026-09-29 by Master · repo: private https://github.com/Praty0512/fedqpnt (`master`, pushed) · decisions up to D-058 · log up to #106 · live agent registry: `AGENTS_ACTIVE.md`_

## Identity
Federated learning across vehicle/UAV nodes. Each node fuses a cold-atom quantum accelerometer (CAI), GNSS and a classical IMU behind a continuous, attack-adaptive trust engine; the detector improves fleet-wide via FL, and no raw data leaves a node.
- **Baselines** (D-011): A = FL detection → detect-and-exclude; B-bin = single-node detect-and-switch; B-cont = single-node continuous trust without FL; B′ = innovation-χ² adaptive KF.
- **Hypotheses:** H1–H4 (ARCHITECTURE §6.2). All results so far are on **tuning seeds**; test seeds (10000+) are untouched and gated (`results/GATE_D047.json` = not cleared).

## Milestones
| Milestone | Status |
|---|---|
| **M0 — Foundations** | ✅ Signed off 2026-09-26 |
| **M1 — Single-node closed loop** | ✅ Signed off 2026-09-28, with limitations (D-053). **Re-verification running** on the new core (CORE-ROBUST) |
| **M2 — Federation** | 🔶 Infrastructure done and **FL sanity PASS** (FL 0.996–0.998 vs centralised 0.997, D-056). **H2/H4 not yet demonstrated**: the previews were invalid (D-054) or measured the E_s rules instead of FL (D-056); the sub-rule regime was unreachable because E_s is self-contaminated (D-058). The re-run waits for the core fixes; abrupt is the rule-quiet novel-family candidate |
| **M3 — Eval/stats** | 🔶 The pipeline is done (stats, 15-scenario registry, resumable runner with a test-seed gate, report). **Fleet scenarios S5/S8/S9/S12/S15 are being wired in** (CAMPAIGN-FLEET) |
| **M4 — Full campaign** | ⛔ **GATED**: needs CORE-ROBUST (overconfidence + soft gate + safety principle), PERF, CAMPAIGN-FLEET, and the gate decision |
| **M5 — Deliverables** | 🔶 Done: patent claim skeleton, 4 architecture figures, README/requirements/REPRODUCE/DATA/CITATION, module docs, verified bibliography. **Paper ON HOLD** (user; Sonnet when resumed). Result figures wait for M4 |

## Key results so far (tuning seeds; κ_R = 40 PROVISIONAL)
- **Detector v2** (supervised, 6 families, Platt): AUC overall 0.953; drift 0.998; meaconing 0.999; jam 0.988–0.997; abrupt 0.691 (regressed).
- **S1:** FedQPNT FAR 0/h, RMSE ratio 0.990, ANEES 1.31; no divergence. Smoke: FedQPNT beats Baseline A on spoofing (drift 121 vs ~650 m).
- **Signature-strength limit (D-055):** drift detection works for s ≥ 0.5 and fails below (inverted at s = 0), where **every gated method** (not only FedQPNT) is far worse than undefended, because of the shared-core hard-gate lockout (D-057).
- **FL:** tracks centralised training; S12 poisoning mean-PASS at N = 10 (CI inconclusive).
- **CAI:** halves outage drift on tactical-grade IMUs (7.0 → 3.3 m); MEMS still preliminary.
- **New-core overconfidence diagnostic** (CORE-ROBUST, 2026-09-29): p/v NEES ≈ ideal; ψ_rp 4.6 (CAI on) vs 17.6 (off); b_a NEES 522 with CAI on (suspected truth-definition artefact; a test is running); CAI R honest.

## Running now (see `AGENTS_ACTIVE.md` for resume details)
| Agent | Work |
|---|---|
| CORE-ROBUST | Eigenvalue clip; soft gating; E_s short-baseline jump test; overconfidence diagnosis (+ the b_a effective-bias test); κ_R re-tune; re-verify M1 + the safety principle across s ∈ {0, 0.25, 0.5, 1} |
| PERF | Bit-identical speedups (sensors/GNSS/sim) |
| CAMPAIGN-FLEET | Route S5/S8/S9/S12/S15 through the fleet runner in the campaign |

## Open issues (ranked)
| # | Issue | Status |
|---|---|---|
| 1 | Shared-core robustness: hard-gate lockout (D-057), E_s self-contamination (D-058), ψ/b overconfidence (D-046/47) | **In progress** (CORE-ROBUST) |
| 2 | H2/H4 (the core FL claim) not yet shown | After #1: abrupt as the novel family, plus drift/meaconing with the new E_s |
| 3 | Signature-strength envelope (s ≥ 0.5) | A paper-stated assumption; re-check the safety principle after #1 |
| 4 | Abrupt AUC regression (0.754 → 0.691) | Follow-up |
| 5 | CAI benefit for MEMS | Blocked by #1 |
| 6 | Runtime (~55 s/node-hour; fleet ~300 s/fleet-hour) | PERF running |
| 7 | Doc drift: ARCH §1.2 CAI cycle default (1.0 s vs the FIELD 1.548 s) | Doc cleanup |

## Next (after the running agents)
1. Accept CORE-ROBUST → gate decision (clear, or accept κ_R as a stated limitation).
2. H2/H4 re-run (fleet) → if positive, M2 sign-off.
3. M4 campaign on test seeds (all 15 scenarios × methods × 30 seeds) → M3 report.
4. M5: result figures; paper (on the user's go-ahead); patent filing decision (user + attorney).

## Waiting on the user
- Paper stays on hold until you say otherwise.
- Patent: filing timing and attorney review (your decision).
- Keep approving edit prompts (eskf/trust/node/sensors) when agents touch them.
- Optional: close the 6 orphaned idle `python.exe` workers (started ~2026-09-28 midday) in Task Manager.
