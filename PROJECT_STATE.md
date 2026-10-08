# FedQPNT — Project State

_Last updated: 2026-10-08 by Master · repo: private https://github.com/Praty0512/fedqpnt (`master`, pushed) · decisions up to D-083 · log up to #166 · latest freeze: `core-freeze-4` (`core-freeze-5` in preparation) · live agent registry: `AGENTS_ACTIVE.md`_

## Identity
Federated learning across vehicle/UAV nodes. Each node fuses a cold-atom quantum accelerometer (CAI), GNSS and a classical IMU behind a continuous, attack-adaptive trust engine; the detector improves fleet-wide via FL, and no raw data leaves a node.

## Milestones
| Milestone | Status |
|---|---|
| **M0 — Foundations** | ✅ |
| **M1 — Single-node closed loop** | 🔶 Freeze-4 characterised (D-080). A CAI-trust calibration bug was found (D-082), so **freeze-5 fixes are in progress** (D-083) |
| **M2 — Federation (H2/H4)** | ✅ **Confirmatory result (freeze-4): NULL by ceiling** (D-081). Both arms detect the abrupt onset at the first epoch (P_D@10 s = 1.0, latency 0 s); no FL benefit measurable. Reported as measured |
| **M3 — Eval/stats** | ✅ Pipeline + report generator + figures built (`scripts/m3_report.py`, `make_figures_results.py`); final run waits for round 2 |
| **M4 — Test-seed campaign** | 🔶 **Round 1** (freeze-4, seeds 10000–10029) STOPPED after the bug: partial record committed (3,775/4,980 single-node processed). **Round 2** (freeze-5, NEW seeds 10030–10059) is next (user decision, D-082) |
| **M5 — Deliverables** | 🔶 Paper Sections I–V + trust engine + limitations; **compiles with MiKTeX (15 pp, all references verified via Crossref/arXiv/manufacturer pages)**. Patent rev. 2. Repro docs. Results/abstract wait for round 2 |

## Key findings so far (honest status)
- **Works:**
  - no harm in normal operation (0 false alarms, accuracy equal to undefended);
  - jamming defence at both IMU grades;
  - drift-spoof defence with a tactical IMU (69 vs 108 m);
  - timing protection under meaconing (168 vs 2363 ns);
  - the detector generalises to an unseen attack (displaced meaconer AUC 0.9985);
  - Baseline A (detect-and-exclude) is beaten everywhere.
- **Limits (stated):**
  - MEMS-grade IMUs coast too fast for exclusion to pay against slow drift;
  - co-located meaconing costs position (timing protected);
  - post-attack re-admission is slow after long or weak attacks;
  - consistency-matched small spoofs on MEMS.
- **Bugs found and fixed before round 2** (all on tuning seeds):
  - the CAI-trust contrast calibration (FedQPNT had been ignoring the quantum sensor);
  - the flat-world scenarios (no Schuler bound);
  - the CAI measurement-noise model (missing IMU scale-factor/misalignment term);
  - a Windows command-line limit and a slow attack lookup (orchestration).
- **The FL claim (H2/H4) is null.** The paper reframes FL to what was shown: it matches centralised training, it is robust to poisoning, and the detector generalises.

## Running now
| Agent | Work |
|---|---|
| CORE-ROBUST | Freeze-5 fixes in worktree `FEDQPNT_freeze5`: R_q patch, gate-test update, sanity re-run, full suite, commit |

## What's left (in order)
1. Merge → **core-freeze-5** tag.
2. **Detector v4** retrain on the round-Earth world (~1.5 h).
3. Tuning sanity check (defended vs undefended, CAI on/off), then the **round-2 pre-registration** (seeds 10030–10059).
4. **Round 2 campaign:** ~1 day of compute (single-node + fleet scenarios).
5. **M3 report + figures** (pipeline ready), then **paper results, discussion and abstract**, then the final compile.
6. **Patent final pass** (shadow probe, split trust, CAI-aware claims); **release** (tag, results manifest, reproducibility).

**Estimate:** ~2 days, mostly unattended compute, plus usage-limit pauses.

## Waiting on the user
- **Keep the laptop awake and plugged in** during round 2 (round 1 died when the machine stopped on 2026-10-04). Set Windows sleep to "Never" while plugged in.
- Later:
  - review the paper draft;
  - patent filing timing and attorney review (prior-art search needed).
