# Position/Clock Trust Split - Design Note (D-063 task D)

Status: DESIGN ONLY. Not implemented; needs Master approval first. Author: CORE-ROBUST.

## 1. Problem
`TrustState.weights["gnss"]` is one scalar consumed by ESKF.correct (6-D pos+vel update, with
w_excl hard exclusion) and by ClockKF.step (R/max(w,w_min)). Meaconing (co-located model: one
common-mode range delay) shows up as a clock-bias jump (x8 = 250 sigma) with a clean position
innovation (nis_pos 0.001-0.37). E_s clk_event drives w to w_min, so position updates are excluded
too: fedqpnt_local meaconing RMSE 22.3 m (MEMS) / 6.6 m (tactical) vs undefended 2.5 m.

## 2. Proposal: w_pos and w_clk
- w_pos -> ESKF GNSS update. w_clk -> ClockKF update.
- Keep `weights["gnss"]` as alias = min(w_pos, w_clk) for metrics/back-compat (decide at
  implementation; `mean_w_gnss` in runner.py and several scripts read it).

## 3. Evidence routing
| Evidence | Drives |
|---|---|
| E_s position_event (short-baseline jump test) | w_pos |
| E_s clk_event (x8/x9 sigma jump) | w_clk |
| E_s xsat_event, cn0_event | both (single-antenna signature is domain-ambiguous: a consistent forged PVT forges the clock too) |
| Detector p (15-feature vector, mixes domains: C/N0, AGC, RAIM, nsat) | both (not separable without new labels/heads; splitting heads is out of scope) |
| NIS hysteresis inputs | one _LawCore per weight; w_pos fed gnss_pos NIS, w_clk fed a clock-innovation NIS |
Effect on meaconing: clk_event depresses w_clk only; position_event silent, so w_pos stays high.

## 4. State-machine implications
_LawCoreV2 (TRUST/DISTRUST/PROBE) duplicated: independent timers (T_ex, T_probe, T_sup) and PROBE
exit tests per weight; the two may be in different states. Reacquisition cap and the D-058
gap-reset/2-epoch quarantine (`_es_position_quarantine`, `_last_p_prior`) are position-specific and
attach to w_pos; a clock analogue after outages needs its own trace. The D-065 ClockKF w<w_excl
hard holdover (free-run on the oscillator model, Q not trust-scaled) is a prerequisite so that w_clk
actually protects the clock (task B: R-inflation alone lets q_bias-driven P re-open the gain).
Open interaction: drift-spoof PROBE drag (D-065 item E) applies to w_pos only.

## 5. Files and tests
Code: fedqpnt/trust/trust_law.py (two law cores, evidence split, weights schema), fedqpnt/core/types.py
(TrustState.weights keys), fedqpnt/fusion/eskf.py (read w_pos), fedqpnt/fusion/clock.py (read w_clk +
holdover), fedqpnt/node/agent.py (route weights), fedqpnt/node/methods.py + fedqpnt/eval/metrics.py
(mean_w_gnss convention). Tests: test_trust_law_dynamics.py, test_trust_law_es_position.py (+ clock
sibling), test_fusion_eskf.py, new test_fusion_clock.py, test_trust_leakage_guard.py, smoke/M1 scripts
reading mean_w_gnss.

## 6. Patent impact (patent/CLAIMS_SKELETON.md, read only)
- Claim 1(vi) recites one trust value and one measurement-noise covariance: broaden to "one or more"
  (keeps single-value as special case) or add the split as a new dependent claim (lower risk).
- Claim 12 (clock-bias jump as physical evidence) does not tie it to a separate trust value for the
  clock state: a dependent claim "second continuous trust value from the clock-bias jump, independent of
  the trust value applied to the navigation fix, applied to the clock-state covariance" is the main
  novelty gain.
- Claims 14 (reacquisition cap) and 15 (suppression window) must be scoped to the position trust value
  (or widened if a clock cap is added). Claim skeleton section 5 item 3 (E_s independence) needs its own
  validation pass for the clock evidence once implemented.
- No change to FL/aggregation claims (1(vii), 8, 9, 13, 18) or CAI claims (1(iv), 11, 16).

## 7. Meaconing model realism
Current MeaconingReplay is effectively co-located (common-mode delay, near-degenerate with clock bias),
so position is barely disturbed. A displaced meaconer pins position toward the meaconer antenna and is a
distinct, documented threat. The scenario set cannot exercise it, so the split's benefit can only be
evaluated on the co-located variant. Recommendation: add a displaced variant (fixed ENU offset, own
scenario entry) before validating the split. Not implemented; awaiting decision.
