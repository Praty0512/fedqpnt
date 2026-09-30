# PAPER-2 progress
Task: IV.D trust engine (frozen core-freeze-1), IV.B pre-freeze facts, Discussion/Limitations, stale statements. Edit only paper/main.tex, paper/NOTES.md.
- [x] read code/decisions (trust_law, features, eskf, clock, agent, methods, defaults; D-051..D-072)
- [ ] IV.D written (scratchpad/ivd.tex -> spliced into main.tex lines of old skeleton)
- [ ] IV.B / IV.C x8x9 wording / abstract / contributions / FedProx / table cell / Discussion bullets
- [ ] NOTES.md IV.D entries + mismatches + missing refs
- [ ] static check (envs, braces, refs)
## DONE (2026-09-30)
IV.D written (spliced), IV.B clock/kappa/coupling updated, IV.C x8/x9 wording, abstract/contributions/FedProx/table cell fixed, Discussion & Limitations rewritten (Discussion subsection = todo; Limitations 12 bullets), NOTES.md updated (IV.D map, VI map, mismatches 16-23). Static lint OK (envs, braces, refs; no new missing cites).
Found: uncommitted D-073 features.py change post-freeze (x8/x9 dt from last valid clock fix); paper describes the corrected behaviour.
