# FedQPNT — Project State

_Last updated: 2026-10-03 by Master · repo: private https://github.com/Praty0512/fedqpnt (`master`, pushed) · decisions up to D-079 · log up to #152 · latest code freeze: `core-freeze-3` (`core-freeze-4` imminent) · live agent registry: `AGENTS_ACTIVE.md`_

## Identity
Federated learning across vehicle/UAV nodes. Each node fuses a cold-atom quantum accelerometer (CAI), GNSS and a classical IMU behind a continuous, attack-adaptive trust engine; the detector improves fleet-wide via FL, and no raw data leaves a node.
- All results so far are on **tuning seeds**. Test seeds [10000, 20000) are untouched and gated in code.

## Milestones
| Milestone | Status |
|---|---|
| **M0 — Foundations** | ✅ |
| **M1 — Single-node closed loop** | 🔶 Design iterated to freeze-3 (D-061…D-079). The final decisive re-check runs on freeze-4 |
| **M2 — Federation (H2/H4)** | 🔶 Pre-registered (D-064, Amendments 1–2). The freeze-2 run is PRELIMINARY (leak-exposed); the freeze-3 run was aborted. The confirmatory run happens on freeze-4 |
| **M3 — Eval/stats** | ✅ Pipeline reconciled with the spec: seed gate, 8-test Holm family, scenarios to intent, latency_eff, provenance |
| **M4 — Full campaign** | ⛔ **Pre-registered** (`docs/specs/raw/PREREG_M4.md`): 39 scenarios, 5,340 single-node tasks + fleet, test seeds 10000–10029, 2 IMU grades. Waits for freeze-4 → decisive → H2 → gate |
| **M5 — Deliverables** | 🔶 Patent rev. 2 (attorney-ready skeleton); paper Sections I–V + trust engine + limitations, **compiling with MiKTeX (15 pp)**; references being resolved via Crossref; repro docs refreshed. Results, figures and the abstract wait for M4 |

## Key results (tuning seeds, freeze-3, detector v3)
- **Detector v3:** AUC 0.953 overall (drift 0.998, meaconing 0.999, jam 0.99); **held-out displaced meaconer 0.9985** (generalisation); abrupt 0.688 (weak; the FL target).
- **False alarms:** 0/h for all 7 methods at both IMU grades (S1); nominal accuracy ratio 0.98.
- **CAI coasting benefit** (180 s outage, max error): MEMS 1339 → 645 m; tactical 400 → 119 m.
- **Timing under meaconing:** defended 168 ns vs undefended 2363 ns (14× better).
- **Post-jam recovery:** < 5 m within 4 s; full trust in 34 s.
- **Defended vs undefended (attack-window RMSE_h):**

| Attack | Tactical | MEMS |
|---|---|---|
| Drift | **69 vs 108 m (win)** | 250 vs 108 m (loss) |
| Jam | **71 vs 72 m (win)** | **260 vs 269 m (win)** |
| Co-located meaconing | 68 vs 2.5 m (loss, by design) | 248 vs 2.5 m (loss, by design) |

  - Baseline A (detect-and-exclude) is far worse than FedQPNT everywhere (e.g. MEMS drift 456 m).
- **Operating envelope (stated, D-079):**
  - the defence pays when the inertial (+CAI) coast is better than the spoof's drag rate (tactical), not on MEMS;
  - co-located meaconing costs position while protecting timing.

## Bugs found and fixed this round (all pre-test-seed)
- **Probe drag:** the shadow probe (D-066).
- **Probe bypass:** DISTRUST now pins w (D-075).
- **Clock-gap normalisation:** D-071, D-073.
- **Probe-exit leak:** a failed probe's fix was applied (D-076).
- **Start-up false alarm → permanent lockout:** fixed by the E_s window-validity rule (D-078/D-079), being finalised.
- **Process issues:**
  - a mixed-code run (D-062 rule added);
  - a crash after compute (per-run persistence added);
  - a stale-detector risk (v3 retrained on the frozen core).

## Running now
| Agent | Work |
|---|---|
| CORE-ROBUST | Finalising the E_s window-validity fix (worktree) → Master merges → **core-freeze-4** |
| REFS-2 | Resolving all remaining paper references via Crossref/arXiv (strict title/author/year match), preferring 2018+ sources; then recompile |
| H2-ABRUPT | Parked; confirmatory run on freeze-4 |

## What's left (in order)
1. **core-freeze-4** (hours) → **decisive re-check** (~3 h) ∥ **H2/H4 confirmatory fleet run** (~8–15 h).
2. **Gate decision** → **M4 campaign** on test seeds (~6–10 h).
3. **M3 report + result figures** (a few hours).
4. **Paper:** results, discussion, abstract, final references, compile (a few hours).
5. **Patent final pass; reproducibility release** (tag, results manifest).

**Estimate:** ~1.5–2 days, mostly unattended compute, plus usage-limit pauses.

## Waiting on the user
- **Nothing blocking right now.** References are being resolved via Crossref, so no further Consensus searches are needed.
- Later:
  - (a) review the final paper draft;
  - (b) patent filing timing and attorney review;
  - (c) approve any edit prompts that appear.
