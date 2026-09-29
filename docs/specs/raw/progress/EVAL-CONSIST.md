# EVAL-CONSIST checkpoint (D-067)
Updated 2026-09-29.
- PART 1 DONE (docs only): TRAINING.md (Platt logit form), FEDERATION.md (sign-flip x(-5) after local training; ALIE = A Little Is Enough; FedProx mu=0 == FedAvg, not evaluated), EVALUATION.md (S1-S15 rewritten to scenarios.py with CODE-vs-INTENT notes, seed range [10000,20000), sigma_nom 3 defs, S7 138 vs 52, report family), REAL_DATA_JARLAUD2024.md (48 mrad/s superseded by D-020), README.md + FLEET.md (FedProx notes).
- PART 2 IN PROGRESS: docs/specs/raw/EVAL_CONSIST_PROPOSALS.md
- PART 2 DONE: docs/specs/raw/EVAL_CONSIST_PROPOSALS.md written (6 items + summary table). No code/test/script/result/paper edits. Nothing committed.
- Extra finding: S2 P_D always 1.0 (isfinite on censored latency), H4 entry unevaluable, gate is `>= 10000` with no upper bound.
