# Active agents registry (Master-maintained)

Purpose: survive usage-limit and network cut-offs. On any interruption the Master resumes every agent listed here from its checkpoint file. Each agent keeps `docs/specs/raw/progress/<AGENT>.md` updated after every completed step (done / in-progress / next / background PIDs / output files).

_Last updated: 2026-09-29_

| Agent | Model | Task | Owns (files) | Checkpoint | Last known state | Resume instruction |
|---|---|---|---|---|---|---|
| H2-ABRUPT | Sonnet | Core FL claim H2/H4 with abrupt as the novel family (θ0 without abrupt), ≥ 5 seeds; ≤ 6 processes | scripts/h2_abrupt_*.py, results/fleet/h2_abrupt.json | progress/H2-ABRUPT.md | D-064 prereg + metric code done; applying node_runner telemetry (freeze window, golden test); re-run blocked until the core is frozen | "Resume from your checkpoint; don't redo; background runs + end turn" |
| CORE-ROBUST | Sonnet | D-043/D-057/D-058 shared-core fixes; overconfidence diag; κ_R re-tune; M1 + safety-principle re-verification; the b_a truth-definition test | fedqpnt/fusion/eskf.py, fedqpnt/trust/*, fedqpnt/node/* | progress/CORE-ROBUST.md | Core committed 906ae98. D-065 work: E drift/probe trace (top), A @180 fix, C post-jam proposal, B ClockKF holdover (after the H2 telemetry change), D trust-split note | "Resume from your checkpoint; don't redo; background runs + end turn" |
| PERF | Sonnet | Bit-identical speedups (sensors/gnss/sim/attacks; NOT eskf) | fedqpnt/sensors/*, fedqpnt/sim/rotations.py, trajectory.py, fedqpnt/gnss/*, fedqpnt/attacks/* (perf-only), scripts/perf_* | progress/PERF.md | **DONE; change REJECTED** (1-ulp mismatches for large rotations; patch kept in patches/; D-060) | — |
| CAMPAIGN-FLEET | Sonnet | Wire S5/S8/S9/S12/S15 into the campaign via the fleet runner | fedqpnt/eval/campaign.py, scenarios.py, report.py, fleet_adapter.py, scripts/run_campaign.py, tests/test_eval_campaign.py | progress/CAMPAIGN-FLEET.md | **DONE, accepted** (D-059 + lossless-comms addendum) | — |
| PATENT | Sonnet | Patent claim skeleton | patent/ | progress/PATENT.md | **DONE 2026-09-29, accepted** (3 independent + 17 dependent claims) | — |
| VIZ | Sonnet | Architecture / loop / trust-state / FL-protocol figures | figures/, scripts/make_figures_arch.py | progress/VIZ.md | **DONE 2026-09-29, accepted** after 2 QA rounds (minor polish at paper time: enlarge the internal-flow labels and add them to the legend) | — |
| REPRO | Haiku | README, requirements, REPRODUCE, DATA, CITATION | README.md, requirements.txt, docs/REPRODUCE.md, docs/DATA.md, CITATION.cff | progress/REPRO.md | **DONE 2026-09-29, accepted** (Master pinned scikit-learn==1.7.2) | — |
| DOCS | Haiku | FEDERATION / FLEET / EVALUATION / TRAINING docs | docs/FEDERATION.md, FLEET.md, EVALUATION.md, TRAINING.md, the docs/README.md index | progress/DOCS.md | **DONE 2026-09-29, accepted** | — |
| PAPER | Sonnet | Paper Sections IV–V (results-independent) | paper/main.tex, paper/NOTES.md | progress/PAPER.md | Started 2026-09-29 | same |
| DOCFIX | Haiku | ARCH §1.2 CAI cycle doc drift | docs/, README.md | — | Started 2026-09-29 | re-spawn |

## Queued (not started)
- H2/H4 re-run with abrupt as the novel family (θ0 without abrupt) plus drift/meaconing with the new E_s: **after CORE-ROBUST**.
- The pre-M4 gate decision (D-046/D-047) → the M4 campaign: after CORE-ROBUST + PERF + CAMPAIGN-FLEET.
- Paper: ON HOLD (user).
