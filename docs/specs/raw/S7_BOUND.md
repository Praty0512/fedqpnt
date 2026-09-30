# S7 "no chattering" bound, re-derived from the FROZEN config (D-068)

Status: derivation + adversarial evidence, written against core-freeze-1 (a7c8bf0). Numbers to be re-confirmed by
re-running `tests/test_trust_chattering_bound.py` once core-freeze-2 is announced (the law timers are untouched by the
features.py fix, so no change is expected). `fedqpnt/` was not edited.

## 1. Bottom line

| quantity | value |
|---|---|
| metric (metrics.py:402) | cycle = w down through 0.5, then w up through 0.9; applied to the alias `weights["gnss"] = min(w_pos, w_clk)` (runner.py:156) |
| min down-to-up time per law, any evidence, ANY fix timing | L = tau_r ln((1-0.5)/(1-0.9)) = 10 ln 5 = 16.094 s |
| **N_cyc/h bound, per law AND for the alias, no timing assumption** | **N <= floor(3600 / 16.094) = 223** |
| refinement, fixes on a regular 1 Hz grid (S7 default) | cycle >= 26 s, next fall >= 1 event -> N <= 133 |
| stale values | 138 (v1, 3600/26.1 = T_clean + tau_r ln5) and 52 (v2, 3600/70): both wrong for the frozen law |

Recommendation for the pre-registered S7 threshold: **N_cyc <= 223 per hour (integer count, `count <= 223`)**, with
133 reported as a secondary, non-gating annotation valid only under 1 Hz regular fixes. Rationale in section 6.

## 2. Definitions read from code

- Metric: `trust_cycles` (metrics.py:402-414): state "above": `w[k-1] >= 0.5 > w[k]` -> waiting; then
  `w[k-1] < 0.9 <= w[k]` -> count. `n_cyc_per_hour` divides by (t_end - t_0)/3600 (~1 h for S7).
- S7 (scenarios.py:532-573): 3600 s, toggled abrupt spoof, periods 2/5/10/20/60 s, 50 % duty, t0 = 60 s, methods
  fedqpnt_local; criterion `n_cyc_bound` currently `<= 3600/26.1` (real-valued, metrics.N_CYC_BOUND_PER_HOUR).
- Config (TrustLawConfig defaults): tau_p 0.5, theta_on 0.6 / theta_off 0.3, T_on 0.5, T_off 5, T_clean 10,
  tau_d 0.5, tau_r 10, w_min 0.02, w_cap 0.5, T_ex 60, T_probe 10, w_probe 0.3, T_sup 120, w_reacq 0.5, T_gap 5.
- Engine (TrustEngineImpl.update): `gnss_law` = position law, `clk_law` = independent clock law (same class, own
  state, own evidence routing), alias = `min`. Both are `_LawCoreV2` (fedqpnt uses trust_law_version = "v2").

## 3. How w can move (all paths, frozen code)

Downward:
1. `_ramp` with target < w: w += (1-e^{-dt/tau_d})(target-w), tau_d = 0.5 s (needs target = tau_star < w).
2. PROBE branch: `w = w_probe = 0.3` (jump, also upward if w < 0.3).
3. `apply_reacquisition_cap`: `w = min(w, 0.5)`.

Upward:
4. `_ramp` with target > w and `G_effective`: w += (1-e^{-dt/tau_r})(target-w), tau_r = 10 s, target <= 1.
   `G_effective = G or G_capped`. G = (D_core = 0) and clean_dwell >= T_clean and frac_clean >= 0.9;
   G_capped needs a 120 s lock timer AND caps the target at w_cap = 0.5, so it can never carry w to 0.9.
5. PROBE set-point 0.3 (< 0.5, so it never completes an up-crossing).

Nothing else writes w (force_w is a test hook). The reacquisition WAIVER (engine, D-066) only skips path 3; it adds no
upward path. State machine: TRUST -> DISTRUST (D_core = 1); DISTRUST -> PROBE only when `_distrust_timer >= T_ex`;
PROBE -> TRUST (mean shadow NIS <= bound and no E_s) or -> DISTRUST. There is no other exit from DISTRUST (verified by
`test_premise_distrust_exits_only_through_probe`).

## 4. Proof sketch

Assumptions (all explicit):
- A1. Frozen `TrustLawConfig` defaults, `trust_law_version="v2"`, `law_mode="continuous"`; w_probe < 0.5; w_cap <= 0.5.
- A2. w series is sampled at agent ticks and only changes at fix events (weights are latched between fixes); the
  metric's crossings are therefore at event times. (Finer sampling cannot create crossings, w is piecewise constant.)
- A3. Evidence (p, nis_ok, features_nominal, E_s, shadow NIS) and the event times are arbitrary (adversarial).
  Reset/force_w are not used. tau_r, target <= 1 are fixed parameters (target = tau_star <= 1 always).
- A4. Window W = 3600 s.

**Lemma 1 (timing-free rise bound).** Let u = 1 - w. Between events u can only (i) shrink by ramp: u' >= u e^{-dt/tau_r}
(target <= 1), (ii) grow (paths 1, 3), (iii) be set to 1 - w_probe = 0.7 by the PROBE branch. Claim: for any interval
starting at a down-crossing (u(t_d) > 0.5), u(t) >= 0.5 e^{-(t-t_d)/tau_r} for all t >= t_d. Induction over events:
ramp preserves the inequality (composition of exponentials, independent of how the interval is split into events);
(ii) only increases u; (iii) sets u = 0.7 >= 0.5 >= RHS. An up-crossing needs u <= 0.1, so
t_u - t_d >= tau_r ln(0.5/0.1) = 10 ln 5 = 16.094 s. Note this uses no property of G, of D or of the event spacing.
(Test: `test_premise_rise_only_via_ramp_or_probe_setpoint` checks the invariant on every event of adversarial runs.)

**Theorem 1 (per law).** Cycle intervals [t_d, t_u] are disjoint (the metric returns to "above" only at t_u, and the
next down-crossing is at a later sample), each has length >= L, so N <= floor(W / L) = floor(3600/16.094) = 223.

**Theorem 2 (alias).** Alias a = min(x, y). A down-crossing of a means some channel X < 0.5 at t_d; an up-crossing of a
at t_u means both >= 0.9, in particular X >= 0.9. Lemma 1 applied to X alone gives t_u - t_d >= L, whichever channel
plays X, and whether or not the two laws interleave. The cycle intervals of a are disjoint, hence N_alias <= 223.
Interleaving (X dips, then Y dips right after X is back) cannot beat this: Y's dip may only start after the alias
returns to "above", i.e. after t_u (the metric is not armed while waiting for 0.9), and t_d' > t_u. The alias can
therefore reach, but not exceed, the per-law figure. Tightness under sparse timing (section 5) shows 223 is nearly attained.

**Theorem 3 (regular cadence D, S7 = 1 Hz).** With events every D seconds, at the down-crossing event
t_last_exceed_off = t_d (target < 0.5 needs p_bar > 0.506 > theta_off = 0.3, and `_t_last_exceed_off` is updated before
G is evaluated), so G is first possible at t_d + 10 s and that first ramp step spans only one interval D. Ramp time
accrues D per event, so t_u - t_d >= (ceil(T_clean/D) + ceil(L/D) - 1) D = (10 + 17 - 1) * 1 = 26 s at D = 1
(this is the v1 "T_clean + 16.09 = 26.1" figure, valid only when events are dense). Falling again needs >= 1 more event:
period >= 27 s, N <= floor((3600 - 26)/27) + 1 = 133. PROBE-driven cycles (w set to 0.3, ramp 0.3 -> 0.9 needs 10 ln 7 =
19.46 s ~ 20 steps, and a DISTRUST dwell >= T_ex before) are longer than 26 s and are dominated by the evidence-driven ones.

**Why the sparse-timing case is not covered by 133.** `_ramp` applies `1 - e^{-dt/tau_r}` for the *whole* dt since the
previous event at the moment G first evaluates true. One shallow-dip event followed by a single clean event 16.2 s later
receives the entire ramp with G satisfied at that instant (the T_clean buffer holds only the current event), so
the T_clean = 10 s wait is bypassed. In S7 this needs fixes to be withheld, which the scenario does not do, but the
law itself permits it, so the registered bound cannot assume dense fixes unless the cadence is pinned.

## 5. Answers to the specific questions

- Fastest down-and-up sequence: shallow dip (p_bar just above 0.506, w just under 0.5; with dt = 1 s p_bar must land in
  (0.597, 0.600) so D stays 0), then p = 0. w recovers in TRUST with no DISTRUST at all. Deep dips only lengthen the rise.
- **RESOLVED by D-075 (core-freeze-2, 2026-09-30):** DISTRUST now PINS w at w_min and the ramp is suspended, so the
  "surprise" below no longer holds (the only way up from DISTRUST is PROBE -> success -> TRUST). The premise test was
  inverted (`test_premise_w_pinned_inside_distrust_without_probe`) and the greedy non-vacuity floor lowered 20 -> 10. The
  bound is UNCHANGED at 223 cycles/h (timing-free, L = 16.094 s) and 133/h on a regular 1 Hz grid; the derivation (w rises
  only via the ramp or the w_probe = 0.3 < 0.5 set-point) is unchanged. Adversary counts after the pin
  (`scratchpad/greedy_counts_d075.log`): greedy delta = 1.0 s 132/h, delta = 0.5 s 19/h; sparse-timing (gap 16.2 / 17 / 25 s)
  208 / 199 / 137 per hour. The worst adversaries use shallow TRUST-state dips (w < 0.5 without D = 1), so the worst-case
  count is essentially unchanged; the "state cycle >= T_ex + T_probe = 70 s" argument now also holds for cycles that pass
  through DISTRUST. Historical text follows.
- Can DISTRUST be exited other than through PROBE? No (label). BUT surprise (STALE, see the D-075 note above): the DISTRUST label does not pin w. The
  ramp runs in DISTRUST too (`_LawCoreV2.advance` DISTRUST branch), and G only needs the core hysteresis D_core = 0
  (5 s of p_bar <= 0.3). So w can climb back to 0.9 while the state is still DISTRUST
  (`test_premise_w_recovers_inside_distrust_without_probe`). The "cycle >= T_ex + T_probe = 70 s" argument behind 52/h
  is therefore FALSE for w-cycles (it bounds state cycles, not the metric).
- PROBE can produce a down-crossing without any evidence (w = 0.3 after >= T_ex of DISTRUST); it does not speed cycles
  (needs 19.46 s of ramp afterwards plus >= 60 s of DISTRUST before).
- Reacquisition waiver: only removes a downward clamp (min(w, 0.5)); it cannot create an up-crossing, so it cannot
  shorten a cycle (`test_premise_reacquisition_cap_never_raises_w`, `test_engine_reacquisition_waiver_cannot_speed_cycles`).
- Alias interleaving: no gain beyond the per-law bound (Theorem 2). Engine wiring: both channels get the same p and the
  same event times; they differ only in E_s routing (position vs clock) and NIS statistic, which changes only *when* a
  channel dips, not the rise rate.
- Is chattering possible at all? The number of trust cycles per hour is bounded (223 worst case, 132 measured against the
  greedy 1 Hz adversary, 208 measured against the sparse-timing adversary). Chattering in the sense of frequent
  cycles cannot exceed that; at 1 Hz fixes, one cycle per ~27 s is attainable by an adversary that chooses p_bar to sit
  in the narrow 0.597..0.600 band. None of S7's periodic toggles (2-20 s) achieves it: measured 0 cycles for periods <= 20 s
  and 17 for the 60 s period through the law core.

## 6. Test evidence (tests/test_trust_chattering_bound.py)

Run: `python -m pytest tests/test_trust_chattering_bound.py -q -p no:warnings` -> 132 passed, 0 failed (dots counted; see
checkpoint for the full-suite count). hypothesis is not installed: random adversaries are seeded numpy generators.
Content: periodic toggles (periods 1/2/5/10/20/60 s x grids 1, 0.5, 0.25 s), E_s toggles, NIS at chi2_6(0.99) +/- 1e-9,
greedy look-ahead shallow-dip adversary (regular and sparse events), 36 random-event runs, 24 random-regime runs,
two-independent-laws alias runs, an alternating-interleave adversary, engine-level runs (TrustEngineImpl with injected
p / E_s / NIS, gaps > T_gap for reacquisition), and the state-machine and monotonicity premises. Every run asserts
(a) each observed cycle interval >= 16.094 s, (b) count <= 223 (<= 133 when events are on the 1 Hz grid).

Measured maxima (single hour): greedy 1 Hz: 132 (min cycle interval 26.0 s, i.e. Theorem 3 is tight);
greedy 0.5 s grid: 57; sparse-event greedy: 208 at gap 16.2 (min interval 16.2 s, Lemma 1 tight to 0.1 s), 199 at 17 s, 137
at 25 s; regime-random: 34; engine grid random: 24; periodic S7 toggles: 0 (<= 20 s), 17 (60 s). No sequence exceeded either bound; no
derivation change was needed.

## 7. Recommendation

1. Pre-register N_cyc <= 223 per hour (alias `weights["gnss"]`; integer comparison `count <= 223`, fixing the 137.93
   real-valued comparison nit). It is a theorem for arbitrary fix timing, whereas 133 is only a theorem for 1 Hz regular fixes.
2. Report 133 as an annotation (expected regime for S7 at 1 Hz), never as the pass line, unless the Master pins the fix
   cadence (no withheld/dropped fixes and gnss_rate_hz = 1) in the S7 registration; then 133 is the tighter valid integer.
3. Derive both from config via `L = tau_r ln(5)` and `floor(W/L)` in the evaluator instead of literals.
4. Retire 138 and 52 from ARCHITECTURE / EVALUATION / metrics.N_CYC_BOUND_PER_HOUR and the v1/v2 tests' comments.
   The existing `test_v2_no_chattering_under_adversarial_toggling` bound of ceil(3600/70) = 52 passes only because its
   adversary is weak, not because 52 is valid.
5. The bound is a *sanity* bound (does the law chatter beyond what its own timers allow); it is intentionally loose
   relative to typical S7 behaviour (0-17 cycles/h).
