# FedQPNT — Project State

_Last updated: 2026-09-28 by Master · repo: private https://github.com/Praty0512/fedqpnt (`master`) · decisions up to D-053 · log up to #88_

## Identity
Federated learning across vehicle/UAV nodes. Each node fuses a cold-atom quantum accelerometer (CAI), GNSS and a classical IMU behind a continuous, attack-adaptive trust engine; the detector improves fleet-wide via FL, and no raw data leaves a node.
- **Baselines** (D-011): A = FL detection → detect-and-exclude; B-bin = single-node detect-and-switch; B-cont = single-node continuous trust without FL; B′ = innovation-χ² adaptive KF.
- **Hypotheses:** H1–H4 (ARCHITECTURE §6.2). All results so far are on **tuning seeds (500–599)**; test seeds (10000+) are untouched.

## Milestones
| Milestone | Status |
|---|---|
| **M0 — Foundations** | ✅ Signed off 2026-09-26 (186/186) |
| **M1 — Single-node closed loop** | ✅ **Signed off 2026-09-28, with stated limitations** (D-053). Trust law v2 + supervised detector. S1 PASS; defended ≤ undefended PASS; all four detector families > 0.5 |
| **M2 — Federation** | 🔶 Infrastructure done: fl stack (42 tests), fleet runner (real node pipelines). Next: fleet local data = labelled training missions (D-052), rebalanced mission mix, FL runs with the new detector |
| **M3 — Baselines/eval/stats** | 🔶 Pipeline done: stats.py, 15-scenario registry, resumable campaign runner with a test-seed gate, report generator. Not yet run at scale |
| **M4 — Full 15-scenario campaign** | ⛔ **GATED** (D-046/D-047): needs the κ_R/filter issue fixed or formally accepted, plus runtime optimisation |
| **M5 — Paper/patent/figures/repro** | ⏸ **Paper ON HOLD** (user); Sonnet when resumed. Skeleton + Related Work + verified references exist. Patent outline not started |

## M1 evidence (tuning seeds, κ_R = 40 PROVISIONAL; Master-verified: 120 tests passed)
- **Detector** (supervised, Platt-calibrated, held-out seeds 575–599): AUC overall 0.923; drift 0.999; meaconing 0.999; abrupt 0.751; jamming 0.649. Brier 0.053.
- **S1** (5 × 30 min, nominal): FedQPNT FAR 0.0/h; RMSE_h ratio vs fixed trust 0.990 (limit 1.05); ANEES_pos 1.30; mean w_gnss 0.97.
- **Smoke** (attack-phase RMSE_h, FedQPNT vs Baseline A): drift 121 vs ~650 m; meaconing 20 vs ~650 m; CW jamming 246 vs 658 m. The undefended CW jamming reference is 237 m, and FedQPNT is within the 3σ_nom bound.
- **Limitations carried forward:**
  1. κ_R = 40 provisional; attitude/bias overconfidence (issue #1).
  2. The jam head was trained on only 8 positive epochs (the mission mix must be rebalanced).
  3. Drift/meaconing AUC ≈ 0.999 depends on the strength of the simulated single-antenna C/N0 signature (an ASSUMPTION), so a sensitivity sweep is required.
  4. Baseline A fails the defended ≤ undefended bound under CW jamming (a property of that baseline, reported as-is).

## Open issues (ranked)
| # | Issue | Status / decision |
|---|---|---|
| 1 | **ESKF overconfidence under GNSS aiding.** κ_R = 40 fixes p/v only; ψ/b_a/b_g are still overconfident | **PARKED** (D-046). **Gate** (D-047): outage/CAI-H3/S6/S14 claims blocked. Pre-M4 session: GNSS/filter time alignment; CAI-update on/off block NEES; `_hygiene` floor → eigenvalue clip (D-043) |
| 2 | Detector training mix (jamming 8 positives) + signature-strength dependence | Next work package (D-053) |
| 3 | CAI benefit for MEMS IMUs | PRELIMINARY / blocked by #1. Tactical: CAI halves outage drift (7.0 → 3.3 m) |
| 4 | S12 poisoning at N = 10 | PASS on mean (0.032), CI inconclusive; M4 decides |
| 5 | Runtime ≈ 55 s per sim-hour per node | Optimisation queued |
| 6 | Label-free (pseudo-label) FL | Ablation only (D-052): precision 0.21 |

## Work queue (cap 3 agents)
1. Detector training-mix rebalance + a signature-strength sensitivity sweep (D-053).
2. M2: fleet local data = labelled training missions; shared real feature path (D-050); FL runs (H2/H4 plumbing on tuning seeds).
3. Runtime optimisation (no agent may be running the pipeline at the same time).
4. Pre-M4 filter session (issue #1) → gate decision.
5. M4 campaign → M5 (paper resumes on user go-ahead).

## Waiting on the user
- Paper stays on hold until you say otherwise.
- Keep approving edit prompts for `fedqpnt/trust/*` and `fedqpnt/node/*` when agents touch them.
