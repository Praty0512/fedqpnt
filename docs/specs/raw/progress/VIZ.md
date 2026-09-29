# VISUALIZATION agent — progress log

_Owner: VISUALIZATION agent. Scope: `figures/` and `scripts/make_figures_arch.py` only._

## Environment note
`graphviz` is not installed in this Python 3.13 env and nothing was installed to add it
(per instructions). All figures are generated with matplotlib only
(`scripts/make_figures_arch.py`, patches + FancyArrowPatch, no external layout engine).

## Figures done (2026-09-29)
All four deliverables generated, vector PDF + 300-dpi PNG, IEEE widths
(3.5 in single-column / 7.16 in full-width), Okabe-Ito colour-blind-safe palette:

| Figure | File | Width | Status |
|---|---|---|---|
| 1. Fleet / node boundary / FL server | `figures/fig_architecture.{pdf,png}` | 7.16 in | done |
| 2. Per-tick closed loop | `figures/fig_closed_loop.{pdf,png}` | 7.16 in | done |
| 3. Trust law v2 state machine | `figures/fig_trust_state_machine.{pdf,png}` | 3.5 in | done |
| 4. FL round protocol timeline | `figures/fig_fl_protocol.{pdf,png}` | 7.16 in | done |

All labels/parameters taken from `docs/specs/ARCHITECTURE.md` (§0–§4, §8) and
`docs/specs/TRUST_DESIGN_V2.md` (trust law v2 supersedes ARCHITECTURE §3.3 per D-051);
nothing invented. Passed a manual visual QA pass (rendered PNGs re-read after generation);
fixed label/box collisions in the trust-FSM and FL-protocol figures (moved a legend out of
the caption's way in fig_fl_protocol, separated the two right-side transition labels in
fig_trust_state_machine, removed a stray ellipsis glyph in fig_architecture).

## Next
Nothing queued. Re-run `python scripts/make_figures_arch.py` if ARCHITECTURE.md or
TRUST_DESIGN_V2.md numeric defaults change (e.g. κ_R, T_ex, T_probe, rates) — the script
is the only source of these PDFs/PNGs, so edits should go there, not to the images.

## Open spec ambiguities noted while building (not resolved here)
- RESOLVED (2026-09-29 doc drift fix): §1.2 table updated to show default cycle times per grade: T_c = 1 s (lab), 1.548 s (field, Jarlaud 2024), 0.1 s (near_future). The "closed loop" fig showing CAI ≈ 0.65 Hz (T_c ≈ 1.548 s) is now recognized as the correct FIELD-grade default, calibrated to real Jarlaud/d'Armagnac 2024 data. This matches the task-brief requirement and the code (fedqpnt/sensors/quantum.py line 103).
- Trust law v2 (TRUST_DESIGN_V2.md §C) does not restate w_min, w_excl, the reacquisition cap
  or the asymmetric ramp rates (τ_d, τ_r) — it says they're "unchanged" from ARCHITECTURE
  §3.3. fig_trust_state_machine therefore only labels the v2-specific quantities
  (T_ex, T_probe, w_probe, T_sup, E_s) plus the v1 hysteresis condition for TRUST→DISTRUST;
  it does not show τ_d/τ_r/w_min numerically to avoid mixing v1/v2 sourcing in one label.
