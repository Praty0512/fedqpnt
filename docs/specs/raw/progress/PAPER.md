# PAPER progress (resume notes)

Task: draft results-independent Sections IV (Method) and V (Evaluation Protocol) in paper/main.tex; extend paper/NOTES.md.
Edit only paper/main.tex, paper/NOTES.md, this file. No pdflatex on PATH (checked with `which`); compile impossible unless installed.

## Status
- ALL DONE (2026-09-29): IV.A-E and V.A-I written in paper/main.tex; NOTES.md extended (claim map, 15 mismatches, stale statements, missing refs). Compile not possible (no pdflatex); static lint (env/brace/dollar balance, refs, cites) passed.
- Next (after core freeze): fill IV.D trust law (D-065), frozen kappa_R/config hash, results todos.
- Research phase DONE (read main.tex, NOTES.md, REAL_DATA doc, quantum.py, imu.py, eskf.py, clock.py, trust/features+detector, training builder,
  fl/*, fleet/*, eval/scenarios+stats+metrics, EVALUATION/FEDERATION/FLEET/TRAINING docs, H2_PREREG, DECISION_LOG D-011..D-065).
- IV.A: in-progress
- IV.B, IV.C, IV.D (skeleton only), IV.E: next
- V: next
- NOTES.md entries + Missing references + mismatch list: next

## Mismatches found (to put in NOTES.md)
1. Detector: code = 15 features, 60-d stack, 1010 params (spec/III.D said 13/52/882). Fixed III.D sentence.
2. kappa_R: D-061 = 60, code defaults (runner/campaign/fleet_adapter/methods.py/build_supervised_dataset) = 40, KAPPA_R_STATUS string says 40.
3. CAI cycle: ARCH 1.2 already updated (1.548 s); ARCH s1.2 fine; make_agent_config quantum_cycle_time_s default 1.0 vs FIELD 1.548 (trust quantum law).
4. Platt: docs say sigma(a p + b); code applies on logit(p).
5. S-numbering: EVALUATION.md (S4 outage legs, S5 single-node failure, S6 receiver aiding, S15 replay) vs scenarios.py (S4 jam+spoof label but attack = jam_wideband only, S5 partial failure, S6 CAI drift, S15 simultaneous attacks).
6. S7 bound: code/ARCH 3600/26.1=138/h; EVALUATION.md/D-052 say 52/h (v2 law, 70 s). Trust law pending.
7. sigma_nom: three definitions (S2 code 5 m const; EVALUATION.md per-run RMSE_pre; D-061/sweep script std across seeds of undefended nominal RMSE).
8. latency_eff pre-registered (ARCH 6, H3) but not implemented in eval/metrics.py; report.py H3 entry uses latency_on on S6.
9. Confirmatory family in report.py (5 tests, H3 excluded, H4 only latency) vs ARCH {H1..H4} x {primary}.
10. FedProx: implemented client-side, but no fleet method arm; frozen mu=0 == FedAvg. FEDERATION.md says sign_flip "x-5" (code x*(-5)) and ALIE "Automated Lie Injection" (it is A Little Is Enough).
11. ClockKF: D-065 w_excl holdover not yet in fusion/clock.py (working tree at HEAD).
12. Fleet local training default seeds 100000+... numerically >= 10000.
13. H2 abrupt live seeds 500-509 inside M1-detector train seeds 500-549 (H2 uses theta0 400-449, so ok, but note); tau seeds 580-599 overlap M1 heldout 575-599.
14. main.tex stale: abstract/intro claims T_cyc >= 26.1 s (trust law pending D-065); III.A mentions pseudo-labelling (demoted D-052).
