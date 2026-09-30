# Active agents registry (Master-maintained)

Purpose: survive usage-limit and network cut-offs. On any interruption the Master resumes every agent listed here from its checkpoint file. Each agent keeps `docs/specs/raw/progress/<AGENT>.md` updated after every completed step (done / in-progress / next / background PIDs / output files).

_Last updated: 2026-09-29_

| Agent | Model | Task | Owns (files) | Checkpoint | Last known state | Resume instruction |
|---|---|---|---|---|---|---|
| H2-ABRUPT | Sonnet | Core FL claim H2/H4 with abrupt as the novel family (θ0 without abrupt), ≥ 5 seeds; ≤ 6 processes | scripts/h2_abrupt_*.py, results/fleet/h2_abrupt.json | progress/H2-ABRUPT.md | Telemetry committed 77d4ff7 (golden verified by Master). PARKED until core freeze → τ calibration (580–599), n = 10 re-run (500–509), D-064 metrics | "Resume from your checkpoint; don't redo; background runs + end turn" |
| CORE-ROBUST | Sonnet | D-043/D-057/D-058 shared-core fixes; overconfidence diag; κ_R re-tune; M1 + safety-principle re-verification; the b_a truth-definition test | fedqpnt/fusion/eskf.py, fedqpnt/trust/*, fedqpnt/node/* | progress/CORE-ROBUST.md | ALL core changes committed (c288e69). STANDBY: the combined re-verification waits for detector v3 (D-072) | "Resume from your checkpoint; don't redo; background runs + end turn" |
| PERF | Sonnet | Bit-identical speedups (sensors/gnss/sim/attacks; NOT eskf) | fedqpnt/sensors/*, fedqpnt/sim/rotations.py, trajectory.py, fedqpnt/gnss/*, fedqpnt/attacks/* (perf-only), scripts/perf_* | progress/PERF.md | **DONE; change REJECTED** (1-ulp mismatches for large rotations; patch kept in patches/; D-060) | — |
| CAMPAIGN-FLEET | Sonnet | Wire S5/S8/S9/S12/S15 into the campaign via the fleet runner | fedqpnt/eval/campaign.py, scenarios.py, report.py, fleet_adapter.py, scripts/run_campaign.py, tests/test_eval_campaign.py | progress/CAMPAIGN-FLEET.md | **DONE, accepted** (D-059 + lossless-comms addendum) | — |
| PATENT | Sonnet | Patent claim skeleton | patent/ | progress/PATENT.md | **DONE 2026-09-29, accepted** (3 independent + 17 dependent claims) | — |
| VIZ | Sonnet | Architecture / loop / trust-state / FL-protocol figures | figures/, scripts/make_figures_arch.py | progress/VIZ.md | **DONE 2026-09-29, accepted** after 2 QA rounds (minor polish at paper time: enlarge the internal-flow labels and add them to the legend) | — |
| REPRO | Haiku | README, requirements, REPRODUCE, DATA, CITATION | README.md, requirements.txt, docs/REPRODUCE.md, docs/DATA.md, CITATION.cff | progress/REPRO.md | **DONE 2026-09-29, accepted** (Master pinned scikit-learn==1.7.2) | — |
| DOCS | Haiku | FEDERATION / FLEET / EVALUATION / TRAINING docs | docs/FEDERATION.md, FLEET.md, EVALUATION.md, TRAINING.md, the docs/README.md index | progress/DOCS.md | **DONE 2026-09-29, accepted** | — |
| PAPER | Sonnet | Paper Sections IV–V (results-independent) | paper/main.tex, paper/NOTES.md | progress/PAPER.md | IV–V draft DONE, committed 8955a4a; 15 TODO refs await user verification; trust-law subsection waits for freeze — STOPPED 2026-09-30 (user: stop idle agents); re-spawn from checkpoint if needed | re-spawn
| DOCFIX | Haiku | ARCH §1.2 CAI cycle doc drift | docs/, README.md | — | DONE, committed d56b490 — STOPPED 2026-09-30 (user: stop idle agents); re-spawn from checkpoint if needed | re-spawn
| REFS | Haiku | Clock-model citations | docs/REFERENCES.md, paper/refs.bib | — | DONE (Master stripped the bib note fields), committed 8955a4a — STOPPED 2026-09-30 (user: stop idle agents); re-spawn from checkpoint if needed | re-spawn
| EVAL-CONSIST | Sonnet | D-067 eval spec/code audit + doc drift | docs/, docs/specs/raw/EVAL_CONSIST_PROPOSALS.md | progress/EVAL-CONSIST.md | DONE, committed a55d873; D-068 rulings — STOPPED 2026-09-30 (user: stop idle agents); re-spawn from checkpoint if needed | re-spawn
| MEACON | Sonnet | Displaced-meaconer attack kind (D-066) | fedqpnt/attacks/*, environment.py dispatch, tests/test_attack_meaconing_displaced.py | progress/MEACON.md | DONE (0183f6e, ee7498c) — STOPPED 2026-09-30 (user: stop idle agents); re-spawn from checkpoint if needed | re-spawn
| SCENARIO-FIX | Sonnet | D-068 code fixes (scenarios/metrics/report/campaign/seed gate) | fedqpnt/eval/* | progress/SCENARIO-FIX.md | P1–P3 DONE, committed a7c8bf0 (core-freeze-1). Idle — STOPPED 2026-09-30 (user: stop idle agents); re-spawn from checkpoint if needed | re-spawn
| DETECTOR-V3 | Sonnet | Detector v3 retrain on the frozen core (D-052/D-053 protocol) | scripts/train_supervised_v3.py, results/m1/*_v3* | progress/DETECTOR-V3.md | Phase B RUNNING on core-freeze-1 (v3 train → S1 FAR → displaced-meaconer generalisation) | same |

## Queued (not started)
- H2/H4 re-run with abrupt as the novel family (θ0 without abrupt) plus drift/meaconing with the new E_s: **after CORE-ROBUST**.
- The pre-M4 gate decision (D-046/D-047) → the M4 campaign: after CORE-ROBUST + PERF + CAMPAIGN-FLEET.
- Paper: ON HOLD (user).
