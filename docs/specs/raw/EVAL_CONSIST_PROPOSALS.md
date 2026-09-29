# EVAL-CONSIST proposals for the Master (D-067) [updated 2026-09-29, D-067]

Author: EVAL-CONSIST agent (Sonnet). Status: PROPOSALS ONLY. No code, test, script, result or paper file was edited; the only files touched are the Part 1 docs and this file. Under D-002, every item below that could change a reported result is marked "CAN CHANGE RESULTS". Anything that alters a bound, family or definition after tuning data exists must be labelled as post hoc when reported (D-061).

Line numbers refer to the working tree on 2026-09-29 (HEAD 230c191 plus uncommitted changes).

---------------------------------------------------------------------------------------------------

## 1. sigma_nom: which definition, and what D-055 actually pre-registers

### 1.1 What D-055 says (quote)
DECISION_LOG.md:211 (D-055, "Safety principle (adopted)"): "a defended method must never be substantially worse than undefended across the stated threat envelope." D-055 contains **no** sigma_nom, no "3 sigma", and no numeric bound. So D-055 pre-registers a principle, not a definition.

The "undefended + 3 sigma_nom" form enters through other texts:
- ARCHITECTURE.md:565 (S2 row): "MAX_h(P_att) <= MAX_h(undefended) + 3 sigma_nom (defence never makes it worse)". sigma_nom is used but never defined (EVAL_NOTES.md:37-38: "no single frozen value found").
- DECISION_LOG.md:160 and :180 (D-057): "every defended method <= undefended + 3 sigma_nom, per the D-055 safety principle".
- DECISION_LOG.md:308 (D-048): "sigma_nom = 5 m: rejected. Use sigma_nom = RMSE_h(P_pre) measured in the same run (same seed and method); no assumed constant."
- DECISION_LOG.md:124 (D-061): "the D-055 bound (undefended + 3 sigma_nom) is kept as pre-registered and the FAILs are reported as measured. Note: sigma_nom comes from the nominal scenario (0.24 m), not from the spread of attack-phase RMSE across seeds; a revised criterion may only be pre-registered prospectively before M4, labelled as defined after the tuning data."

Honest reading: the *only* explicit, later, "pre-registered" statement is D-061's: sigma_nom is a nominal-scenario quantity (~0.24 m). D-061 attributes the bound to D-055, but D-055's text does not contain it; the attribution is D-061's.

### 1.2 The definitions actually in use (four, not three)

| # | Definition | Where | Value scale |
|---|---|---|---|
| a | constant 5 m ("[ASSUMPTION]") | `fedqpnt/eval/scenarios.py:162` (`sigma_nom_m = 5.0`), used only in S2-low `_damage` (lines 160-166) | 5 m -> 3 sigma = 15 m |
| b | per-run `RMSE_h(P_pre)` of the same seed and method | D-048 ruling text (DECISION_LOG.md:308); old docs/EVALUATION.md; **not implemented anywhere** | ~2.8 m (TRUST_V2_NOTES.md:126 quotes 2.77 m) -> 3 sigma ~ 8 m; and it depends on the method under test |
| c | across-seed std of the UNDEFENDED method's metric *in the scenario being compared* (nominal: rmse_h_pre; jam_cw: rmse_h_att) | `scripts/defended_vs_undefended_check.py:71` (its docstring says "measured per run" but the code is an across-seed std) | nominal ~0.82 m (TRUST_V2_NOTES.md:126); for jam_cw it is the spread of the attack-phase error itself |
| d | across-seed std of the UNDEFENDED method's *nominal* rmse_h_pre, measured once, applied to every attack condition | `scripts/core_robust_safety_principle_sweep.py:78-80`; D-061 note; paper main.tex Sec V.I | ~0.24 m (D-061) -> 3 sigma ~ 0.7 m (n = 3 seeds) |

They differ by roughly 10-20x. Every D-055 safety-principle FAIL reported so far (D-061, CORE_ROBUST_NOTES.md:92-100) used definition (d). Definitions (a)-(c) would each turn some of those FAILs into PASSes. Note also that (b) makes the bound depend on the defended method's own pre-attack error, so a method with worse nominal error gets a looser bound for itself.

### 1.3 Options
- **O1 (recommended): definition (d), measured properly.** sigma_nom = across-seed std of the undefended method's nominal RMSE_h(P_pre), computed once per (IMU grade, world) from >= 20 nominal undefended runs on disjoint tuning seeds (e.g. 9500-9519, tuning class; NOT the 30 test seeds), at the *frozen* core/kappa_R/trust law, recorded in the config hash before any test seed runs. Applied to every attack condition, every defended method.
- O2: definition (b). Rejected by its own logic (method-dependent; ~10x looser). Would be a post-hoc loosening.
- O3: constant 5 m. Already rejected by D-048; loosest.
- O4: relative bound (defended <= 1.05 x undefended). Not what was pre-registered; would be a post-hoc replacement. May be reported as a *labelled sensitivity analysis* only.

### 1.4 Recommendation for M4
Adopt O1 as the confirmatory definition, because it (i) is what D-061 explicitly keeps "as pre-registered", (ii) is the strictest and so cannot be accused of being tuned to win, (iii) has been used for every reported number so far, and (iv) is measurable without touching test seeds. Two refinements are *new specifics* and must be recorded as pre-registered before M4: (1) n >= 20 seeds instead of 3, because a 3-seed std is a very noisy estimator; (2) one sigma_nom per IMU grade (D-063 made grade an evaluation dimension, and nominal RMSE differs by grade). The same sigma_nom must be reused for latency_eff's t_eff threshold (item 4), so there is only one free choice.

**Labelling rule.** Anything other than definition (d) is a post-hoc change relative to D-061 and must be reported as such, next to the (d) result, never instead of it. Also disclose that D-055's own text does not define sigma_nom.

**CAN CHANGE RESULTS: YES.** Switching from (d) to (a)/(b)/(c) changes PASS/FAIL of the safety principle (D-061 shows 1-5% RMSE excess "FAILs" under (d) that would PASS under a 3 sigma of several metres). The choice must be made before M4, and S2-low's code (constant 5 m) must be replaced or the S2 criterion must be dropped in favour of the safety-sweep metric.

Related implementation note (proposal, not done): `scenarios.py::_make_s2` should read sigma_nom from a frozen config value (e.g. `results/sigma_nom_<grade>.json`, hashed) rather than a literal.

---------------------------------------------------------------------------------------------------

## 2. The confirmatory hypothesis family

### 2.1 Current state
- `fedqpnt/eval/report.py:29-35` `CONFIRMATORY_FAMILY` = 5 tests: H1 x {rmse_h_att, latency_on} on S2-med vs baseline_a; H2 x {rmse_h_att, latency_on} on S2-med vs baseline_b_cont; **H4 latency_on only** on S8 with (fedqpnt_local, baseline_b_cont). `H3_ENTRY` (line 36) is S6 latency_on, computed but **excluded** from Holm (lines 102-113, "BLOCKED by D-046/D-047").
- ARCHITECTURE.md:580-587 (6.2) and :605 (7.5): family = {H1..H4} x {primary metrics RMSE_h(P_att), latency_on} x {scenarios where applicable}; H3's metric is latency_eff vs **-quantum**; H4 = cold-start node's **P_D and latency** vs B.
- D-056/D-064 redesigned H2/H4: the confirmatory H2/H4 evidence is the abrupt fleet experiment (theta0_noabrupt, N = 5, seeds 500-509 for the tuning-seed version) with **event-level primaries**: P_D@10 s at a per-arm tau calibrated to FAR 1/h, and onset latency censored at 60 s. `report.py` knows none of this.

### 2.2 Concrete inconsistencies (all in the code as written)
1. H3 is excluded from the family although ARCHITECTURE puts it in; H4 has latency but not P_D.
2. **The H4 entry can never be evaluated.** `report.py:29-35` loads S8 results with `list(scenario.methods)` = `("fedqpnt",)` (scenarios.py:381), yet asks for methods `fedqpnt_local` and `baseline_b_cont`, which are neither in S8's method list nor the fleet method naming (`fedqpnt`, `baseline_b_cont`, ...). It will always return `evaluable=False`.
3. H2 in code is a single-node S2-med comparison with a centrally trained detector; D-056/D-064 say the H2 claim is the learned contribution on a *novel* family in a fleet run. The coded H2 tests answer a different question.
4. H3's reference in `H3_ENTRY` is `baseline_b_cont`; ARCHITECTURE says -quantum (`abl_minus_quantum` exists in `trust_law._METHOD_TABLE` at trust_law.py:615 but is in no scenario's method list), and S6's attack is a GNSS drift spoof, not a CAI fault (item 6).
5. Holm (`report.py:102-113`) is applied only to the tests that happen to be evaluable at report time, so the family size m silently shrinks when data are missing (less conservative). m must be fixed in advance.
6. The censoring value in `_one` (report.py:89) is `nanmax` of the observed latencies (data-dependent); for S2 the runner already returns finite censored values (t_off - t_on = 300 s), so `censor_latencies` is a no-op there; D-064 pre-registers 60 s for the event-level metrics. Three different censoring conventions coexist.

### 2.3 Options
- **F-A: keep the coded 5-test family.** Fixes nothing above; H4 is dead code; H2 mis-specified. Not recommended.
- **F-B (recommended): a fixed, pre-registered family of 8 tests, Holm over all 8, m fixed = 8 regardless of availability (an unevaluable test counts as p = 1, i.e. not rejected).**
  - H1 vs A on S2-med (single-node): RMSE_h(P_att), latency_on -> 2 tests.
  - H2 vs B-cont on the D-064 abrupt fleet experiment (test seeds 10000-10029 in the M4 version): P_D@10 s at calibrated tau, latency censored at 60 s -> 2 tests. (H2's "RMSE_h(P_att)" from ARCHITECTURE 6.2 is dropped from the confirmatory set because D-064 declared event-level metrics primary; **this is a deviation from ARCHITECTURE 6.2 and needs the Master's explicit ruling and a stated reason, since dropping a test is a choice that affects results**.)
  - H3 vs -quantum on S2-med: latency_eff (item 4) -> 1 test per IMU grade = 2 tests (or 1 if the Master designates one grade; see D-063).
  - H4 vs B-cont on S8: cold-start node P_D and latency_on -> 2 tests.
  S2-high and other scenarios are secondary/exploratory replications.
- F-C: Holm within each hypothesis separately. Less conservative (per-hypothesis alpha); not recommended, the pre-registration says Holm over the whole family (ARCH 7.5).

### 2.4 Multiplicity correction
Holm-Bonferroni (Holm 1979), two-sided Wilcoxon p-values, alpha = 0.05, over the fixed family. `stats.holm_bonferroni` (stats.py:190-207) implements the standard step-down with monotone adjusted p; no change needed there. Secondary metrics: unadjusted, labelled EXPLORATORY (already so).

**CAN CHANGE RESULTS: YES.** Family size changes the Holm thresholds (5 -> 8 raises the strictest per-test threshold from 0.01 to 0.00625); dropping/adding a test changes which hypotheses are declared. Must be fixed before test seeds are touched. It also requires a report.py change (proposal, not done) and an S8/S6 method-list fix so H3/H4 can even be evaluated.

---------------------------------------------------------------------------------------------------

## 3. The S7 chattering bound: 138/h vs 52/h

### 3.1 Current state
- Code: `fedqpnt/eval/scenarios.py:316` `bound = 3600.0 / 26.1` (= 137.93, compared with `val <= bound`); `fedqpnt/eval/metrics.py:19` `N_CYC_BOUND_PER_HOUR = 3600.0/26.1`; ARCHITECTURE.md:570 (S7 row) "N_cyc <= ceil(3600/26.1) = 138 /h". tests/test_trust_law_dynamics.py:16,57,79 use ceil(3600/26.1) = 138 for the v1 law.
- Docs: old docs/EVALUATION.md, D-052 (DECISION_LOG.md:248), TRUST_DESIGN_V2.md:37 and tests/test_trust_law_dynamics.py:295-309 use ceil(3600/70) = 52 for the v2 law.
- Off-by-one nit: code compares the *real-valued* count/hour against 137.93, so a count of exactly 138 FAILs while ARCHITECTURE says <= 138 passes.

### 3.2 Derivation of each
**138/h (v1 law, ARCHITECTURE 3.3).** A trust cycle = downward crossing of w = 0.5, then upward crossing of w = 0.9. Upward motion requires the recovery gate G = 1, which requires p_bar <= theta_off continuously for T_clean = 10 s after the last p_bar > theta_off (a down-crossing of 0.5 needs tau* < 0.5, i.e. p_bar > ~0.51 > theta_off, so the T_clean clock is reset by the very event that started the cycle). Then w rises with time constant tau_r = 10 s toward at most 1: from 0.5 to 0.9 takes >= tau_r ln((1-0.5)/(1-0.9)) = 10 ln 5 = 16.09 s. So T_cyc >= T_clean + tau_r ln 5 = 26.09 -> "26.1 s", and N <= ceil(3600/26.1) = 138. Assumptions: single-channel w; every recovery passes the gate; no faster recovery path (the anti-lockout branch (6) caps the target at w_cap = 0.5, so it cannot reach 0.9 by itself).

**52/h (v2 law, TRUST_DESIGN_V2 C.7).** v2 adds evidence-bounded exclusion: DISTRUST for T_ex = 60 s, then PROBE for T_probe = 10 s, then TRUST via the recovery ramp. TRUST_DESIGN_V2 claims "a cycle is >= T_ex + T_probe = 70 s", hence ceil(3600/70) = ceil(51.4) = 52. **Caveat:** this is only valid if leaving DISTRUST is possible *only* through PROBE after a full T_ex dwell. If v2 also keeps the ordinary p_bar-clean exit (the section 3.3 D = 0 path), a short dip and recovery could cycle in ~26 s and the correct bound is still 138. The evidence for 52 is empirical: `test_v2_no_chattering_under_adversarial_toggling` at five toggle periods with p in {0, 1} (a hard, but not exhaustive, adversary), not a proof. The paper's "T_cyc >= 26.1 s proven" statement (abstract) is only the v1 derivation.

### 3.3 Re-derivation after the freeze (trust law is changing: D-066)
D-066 changes the ingredients: shadow probe (PROBE no longer applies partial trust; its duration/exit rule change), consistency-based reacquisition (reacq cap waived when first-fix NIS consistent and E_s silent), and the position/clock trust split with the alias `w_gnss = min(w_pos, w_clk)`. Proposed procedure, in order:
1. **Freeze the law**, then write the bound as a function of the frozen config: `min_cycle_time_s(cfg)` computed from `TrustLawConfig` (T_clean, tau_r, T_ex, T_probe or shadow window, w_cap, whether a non-PROBE exit exists) -- in the *evaluator*, so S7 reads the bound from the frozen config instead of a literal (removes the 26.1/70 hard-coding drift).
2. **Split-trust bound.** For the alias min(w_pos, w_clk): each min-cycle contains a full cycle of at least one channel (the channel that was < 0.5 at the down-crossing must rise through 0.9 before the min can), and successive min-cycles are time-disjoint, so N_min <= ceil(W / min(T_cyc,pos, T_cyc,clk)). (Sketch; to be checked when the split is implemented.)
3. **Property test, not just periodic toggling:** adversarial search over p(t) sequences (random switching, hypothesis-style, plus the five periods {2, 5, 10, 20, 60} s x duty cycles), plus a test that every path from DISTRUST to w >= 0.9 has duration >= the analytic bound, and a check of the "only exit is via PROBE" premise by exhaustive state-machine enumeration.
4. **Pre-register** the resulting number (with its derivation) before M4, together with the S7 acceptance rule (use `count <= ceil(W/T_cyc)` on integer counts, fixing the 137.93 nit). Register S7 with all five toggle periods (only 10 s is in `scenarios.py:S7`).
5. Update the paper's abstract/contribution claim only after step 4.

**CAN CHANGE RESULTS: YES for S7 pass/fail** (52 is a much tighter bound than 138; a run passing 138 could fail 52). It does not change any nav/detection metric. The bound must be chosen before looking at test-seed S7 output; running S7 against both and reporting the tighter, or reporting both, is acceptable if both are stated.

---------------------------------------------------------------------------------------------------

## 4. latency_eff: implementation spec

### 4.1 Current state
Pre-registered in ARCHITECTURE.md:542 (section 6): `latency_eff = t_det - t_eff, t_eff = first t with |spoof-induced PVT offset| > 3 sigma_nom (truth-side)`, primary for H3 (ARCH 6.2). **Not implemented**: no function in `fedqpnt/eval/metrics.py`; `fedqpnt/node/runner.py:181-196` emits only `latency_on`; `report.py:36` `H3_ENTRY` uses `latency_on` as a stand-in. There is also no truth-side spoof-offset channel: `attacks/spoofing.py` copies `epoch.meta` unchanged (lines 285/339/410) and `environment.py:168-172` only reads clk_bias/clk_drift from meta.

### 4.2 Proposed definition
- Offset series: `o(t)` = horizontal norm of the position offset the spoofer *injects* into the GNSS PVT solution, in metres, evaluated at each GNSS epoch, truth/evaluator-only (never reaches the Agent).
- `t_eff = min{ t >= t_on : o(t) > 3 sigma_nom }` (strict >), on the GNSS-epoch time base (1 Hz default), with the *same* pre-registered sigma_nom as the S2/safety bound (item 1, one sigma_nom per IMU grade).
- `t_det` exactly as in `metrics.detection_latency`: first t >= t_on such that `attack_detected` holds for T_sus = 1 s.
- `latency_eff = t_det - t_eff`, **signed** (negative = detected before the spoofer's effect exceeded 3 sigma_nom). Do not clamp to 0: clamping destroys the pairing and rank information.

### 4.3 Edge cases and censoring
1. **Never effective** (o(t) never exceeds 3 sigma_nom before t_off, e.g. the drift is too slow/short): t_eff undefined -> `latency_eff = NaN`, excluded from the paired test, count reported. This exclusion is method-independent: under D-005 pairing the injected offset depends only on (seed, attack), not on the method, so it cannot bias the comparison. Report n_excluded per cell.
2. **Miss** (no sustained detection before t_off): censored at `t_off - t_eff` (the same convention as `latency_on`'s `t_off - t_on`); flag `censored=True`; also report detection probability P_D,eff = fraction not censored. Hits are `latency_eff_raw < t_off - t_eff`; do **not** test `isfinite` (see item 6a for exactly this bug in S2's P_D).
3. **Abrupt spoof**: o jumps at t_on, so t_eff = t_on and latency_eff = latency_on (consistency check unit test).
4. **Detector already on at t_on** (carry-over false alarm): `_sustained_true` gives a latency of ~0; report `alarm_at_onset` separately (also affects latency_on).
5. **GNSS outage/jam** during the attack: o(t) undefined at missing epochs; use the last available epoch (spoofer offset is piecewise smooth) and flag; for jam->spoof hybrids define o(t) on spoof epochs only.
6. **Multiple/overlapping attacks**: define o(t) as the norm of the summed injected offset; t_on stays the first labelled sample.
7. **Time resolution**: t_eff and t_det are resolved to the epoch spacing (1 s); state it; no interpolation.

### 4.4 Implementation sketch (for whoever implements; nothing was edited)
- Attacks (`attacks/spoofing.py`): write the injected offset vector into `epoch.meta["spoof_offset_en_m"]` (evaluator-only, dropped by `for_agent()`, as clk_bias already is).
- Environment/runner: carry it in `EnvTick` (like `true_clk_bias_m`) and store the 1 Hz series and `t_det`, `t_on`, `t_off` in the result JSON.
- `eval/metrics.py`: `effective_onset(t, offset, sigma_nom)` and `detection_latency_eff(...)` returning `(latency_eff, censored, excluded)`; the runner should NOT bake sigma_nom in (it is a pre-registered constant applied by the evaluator), so store the offset series and compute post hoc.
- Cross-check option without any sim change: counterfactual pairing (run the *undefended* method with and without the attack on the same seed; o(t) = horizontal norm of the difference of the two nav outputs). It is model-free but includes filter response, so it is a validation of the direct channel, not the definition.
- Tests: abrupt (t_eff = t_on); linear ramp (analytic t_eff); never-effective -> NaN; miss -> censored value; negative latency preserved; signed pairing through `stats.paired_test`.
- Method list: add `abl_minus_quantum` to S2-med's methods (it is in `trust_law._METHOD_TABLE` but in no scenario list) so H3's reference exists.

### 4.5 Sensitivity to sigma_nom
t_eff moves with the threshold: 3 sigma_nom = 0.7 m under definition (d) vs 8 m under (b) vs 15 m under (a). For a slow drift this shifts t_eff by many seconds to minutes and hence shifts latency_eff by the same amount for *all* methods (paired differences are less affected, but not invariant because of censoring and negative values). Hence latency_eff must use the same single pre-registered sigma_nom; report a sensitivity table over sigma_nom in {D-061 value, 2x, 5 m/3} labelled exploratory.

**CAN CHANGE RESULTS: YES for H3 only** (adds the pre-registered primary metric; nothing existing changes). The new specifics (signed values, censor value, exclusion rule, shared sigma_nom) must be fixed before M4.

---------------------------------------------------------------------------------------------------

## 5. Seed gate

### 5.1 Verified current behaviour
- `fedqpnt/eval/campaign.py:32` `TEST_SEED_MIN = 10000`; `run_campaign` (lines 205-219): `test_seeds = [s for s in seeds if s >= TEST_SEED_MIN]`; if any, require `final and gate_cleared_flag`, then `gate_cleared(GATE_D047_PATH)`. **The gate is `>= 10000` with no upper bound**, exactly the pattern D-067 forbids. Consequences:
  1. A seed >= 20000 (e.g. 25000 or 100500) is treated as a "test seed": it needs the same flags, and once the gate is cleared it runs happily. Nothing stops a campaign seed from landing inside the derived fleet namespace (>= 100000) once the gate is open.
  2. Conversely nothing marks 20000+ as "unregistered"; it is silently part of "test".
  3. `docs/EVALUATION.md`, `run_campaign.py:13` and the campaign docstring all say ">= 10000".
- The gate lives only in `run_campaign`. Scripts that call `RunSpec`/`run_single`/`run_many` or `fleet.orchestrator.run_fleet` directly (every `scripts/*.py`) bypass it entirely: a script could run seed 10007 today without any flag. (The policy currently relies on convention; consider having `node.runner`/`run_fleet` call a shared `assert_seed_allowed`.)
- `results/GATE_D047.json` = `{"cleared": false}` (verified).
- Tests (`tests/test_eval_campaign.py:42-57`) use 10000/10001/10005 only for refusal; nothing tests an upper bound or a seed >= 20000.

### 5.2 Proposed code change (not applied)
In `fedqpnt/eval/campaign.py`:
```python
TEST_SEED_MIN = 10000
TEST_SEED_MAX_EXCL = 20000          # D-067: test range is [10000, 20000)
DERIVED_SEED_MIN = 100000           # fleet local-training missions etc.; never a campaign/master seed

def classify_seed(s: int) -> str:
    if TEST_SEED_MIN <= s < TEST_SEED_MAX_EXCL:
        return "test"
    if s >= TEST_SEED_MAX_EXCL:
        return "unregistered"       # 20000+ : no namespace owns it; includes DERIVED_SEED_MIN+
    return "tuning"                 # < 10000 (400-449 pretrain, 500-599 tuning, 600-609 pilot, 9500-9699 sweeps)

# in run_campaign, replacing lines 211-219:
bad = [s for s in seeds if classify_seed(s) == "unregistered"]
if bad:
    raise CampaignGateError(f"seeds {bad} are outside every registered range (tuning < 10000, test "
                            f"[{TEST_SEED_MIN}, {TEST_SEED_MAX_EXCL})); derived seeds >= {DERIVED_SEED_MIN} "
                            "are not campaign seeds")
test_seeds = [s for s in seeds if classify_seed(s) == "test"]
# ... existing final / gate_cleared logic unchanged
```
Tests to add to `tests/test_eval_campaign.py`:
```python
@pytest.mark.parametrize("seed", [20000, 25000, 100500, 1_100_000])
def test_run_campaign_refuses_seeds_outside_registered_ranges(tmp_path, seed, monkeypatch):
    gate = tmp_path / "GATE_D047.json"; gate.write_text(json.dumps({"cleared": True}))
    monkeypatch.setattr(CP, "GATE_D047_PATH", gate)
    with pytest.raises(CP.CampaignGateError, match="outside every registered range"):
        CP.run_campaign(["S1"], seeds=[seed], run_root=str(tmp_path), final=True, gate_cleared_flag=True)

@pytest.mark.parametrize("seed,cls", [(9999, "tuning"), (10000, "test"), (19999, "test"), (20000, "unregistered")])
def test_classify_seed_boundaries(seed, cls):
    assert CP.classify_seed(seed) == cls

def test_fleet_default_training_seeds_disjoint_from_test_range():
    from fedqpnt.fleet.orchestrator import _default_local_train_seeds, FleetScenarioConfig
    for s in list(range(500, 600)) + list(range(9500, 9700)) + list(range(10000, 20000, 137)):
        cfg = FleetScenarioConfig(scenario_id="x", method="fedqpnt_local", seed=s, node_ids=[f"node{i}" for i in range(10)], ...)
        for nid in cfg.node_ids:
            assert all(v >= 100_000 for v in _default_local_train_seeds(cfg, nid))
```
(The last test needs the correct `FleetScenarioConfig` constructor arguments; adjust when written.) Optionally add `assert base >= 100_000` inside `_default_local_train_seeds` and a guard that node index < 10 (see 5.3).

**CAN CHANGE RESULTS: NO** (a stricter refusal only; it prevents runs, it never alters a computed value). The existing tests stay green (10000/10001/10005 remain "test").

### 5.3 Every place seeds are allocated, and overlap check with [10000, 20000)

| Namespace / range | Where allocated | Overlaps [10000, 20000)? |
|---|---|---|
| 400-449 pre-training theta0 | scripts/pretrain_theta0_d054.py:52, h2_abrupt_pretrain_theta0.py:40 (`restricted_seeds(400, 449)`) | no |
| 500-549 detector training; 550-574 Platt; 575-599 held-out | scripts/train_supervised_v1.py:38-40, train_supervised_v2.py:39-41, recalibrate_and_retrain_v2.py:55-60 (500-519 clean calib, 520-549 train, 550-574 Platt, 575-599 held-out), gate_a_labeller_v2.py:44-48 (500-549) | no |
| 500-504/509 live H2/H4/S12/S5-S9 tuning runs | h2_abrupt_h2h4_driver.py:54, h2_h4_full_d054.py:37, h2_h4_subrule_d056.py:60, run_fl_s12_full.py, run_fl_s12_n10.py (500-509), run_fl_s5_s9_auc.py, many core_robust_*.py | no (benign overlap with 500-549 detector training, as D-067 states) |
| 580-599 tau calibration (D-064) | H2_PREREG / D-064 | no (benign overlap with M1 held-out 575-599, stated in D-067) |
| 600-609 pilot | ARCHITECTURE 7.1 | no |
| 9500-9699 tuning-class sweeps (9600-9602 used) | core_robust_safety_principle_sweep.py:33, diag_s0_gate_localization.py:37; docs/EVALUATION.md | no (below 10000; correctly ungated) |
| Ad hoc single seeds 123, 700, 999, 5xx | gen_gnss_attack_results.py:28 (123), diag_provenance_fleet.py:34 (700), h2_abrupt_metrics_dryrun.py:90 (999) | no |
| **Test [10000, 20000)** | ARCHITECTURE 7.1 (10000-10029 for 30-seed cells); nothing in code runs them yet | it is the range |
| Fleet default local-training missions | `fleet/orchestrator.py:98`: `100_000 + scenario.seed*100 + idx*10` (+1) | no: minimum 100000; for test scenario seeds 10000-10029 the values are 1,100,000-1,103,000 |
| Script-side fleet training bases | run_fleet_validate.py:108/134/160 (`200_000 + seed*100 + i*10`, `300_000 + ...`, `400_000 + ...`); h2_abrupt_h2h4_driver.py:168-196, h2_h4_full_d054.py:93/118, h2_h4_subrule_d056.py:153-184 (`300_000/400_000 + seed*100 + i*1000`); h2_abrupt_golden_run.py:27 (`[500001, 500002]`) | no (all >= 200000) |
| Hash-derived internal RNG seeds | `fl/orchestrator.py:36-38` `_seed_from_node_id` (31-bit integers for detector init) | numerically could equal a value in the range with probability ~1e-5 but is an RNG seed for weight initialisation, not a mission seed; not a namespace, note only |
| Server/client default `seed: int = 500` | fl/orchestrator.py:45, fl/server.py:28 | no |
| Tests with 5-digit seeds | tests/test_eval_campaign.py:44,49,57 (10000, 10005, 10001: refusal tests, never executed); tests/test_sim_config.py:17 `master_seed=12345` (config test, no evaluation run) | inside the range but do not run an evaluation; harmless, mention for completeness |

**Confirmed: no allocated tuning, training, pilot, calibration, derived or fleet seed lies in [10000, 20000).** Two caveats: (1) namespaces are disjoint by convention only (nothing asserts it); derived bases 100000/200000/300000/400000 + `seed*100 + i*(10 or 1000)` can collide with one another for large seeds (e.g. fleet default seed s and script base 200000+s'*100 collide when s' = s - 1000; not hit by any registered seed); (2) `_default_local_train_seeds` allots only 100 numbers per scenario seed, so a fleet with N >= 11 nodes (idx*10 >= 100) would collide with the next scenario seed's block; current scenarios cap at N = 10, and there is no assertion.

---------------------------------------------------------------------------------------------------

## 6. Other spec / code / paper disagreements found

(Items marked (!) can change a reported result and should be looked at first.)

a. **(!) S2 P_D is always 1.0.** `scenarios.py:144-150` computes `hit = np.isfinite(latency_on)`; `metrics.detection_latency` returns the *finite* censoring value `t_off - t_on` for a miss (metrics.py:149). So `P_D = mean(isfinite) = 1` for every seed, and the "P_D >= 0.9" leg of S2-med/high can never fail. Correct test: `latency_on < t_off - t_on` (S2: 300 s), as `metrics.detection_probability` does (metrics.py:153-157). Options: fix the criterion; or have the runner also emit `detected: bool`. Any S2 P_D value computed so far (including the smoke/campaign dry-runs) is invalid. CAN CHANGE RESULTS.

b. **(!) H4 entry is unevaluable** (item 2.2-2) and H2's coded design conflicts with D-056/D-064.

c. **S2 criteria deviate from ARCH and D-048**: 3 sigma_nom bound applied only to low severity (ARCH: all severities); "final offset >= 50 m" is the nominal mapping hard-coded per severity (`_make_s2` argument), D-048 requires the measured final offset per run; the code's low-severity bound is on median(MAX_h_d - MAX_h_u), the safety principle (D-055/D-061) and sweep use mean RMSE_h(P_att). Three different metrics for "never worse". CAN CHANGE RESULTS. Recommend one pre-registered statement: primary safety metric = mean RMSE_h(P_att) over seeds (as D-061/sweep), MAX_h reserved for the "halve the damage" leg.

d. **Safety sweep is not the S2 scenario.** `core_robust_safety_principle_sweep.py:69`: onset 120 s, duration 180 s, severity 0.5, industrial_mems only, 3 seeds, 10 min, versus S2-med (onset 60, duration 300, severity 0.6, 600 s). The threat envelope in D-055 is "stated" only through this sweep. Recommend registering the s-sweep as its own scenario (S2-sweep) with both IMU grades and n >= 20 for M4.

e. **`scripts/defended_vs_undefended_check.py`** docstring and D-048 say "measured per run", but the code takes an across-seed std of the scenario metric (fourth sigma_nom definition, item 1); for jam_cw that std is the spread of the attack-phase error, exactly what D-061 says not to use.

f. **Registry vs intent** (also in the rewritten docs/EVALUATION.md): S4 jam leg only; S6 "CAI bias drift" is a GNSS drift spoof with no -quantum arm and only 0.05 severity (S6/H3 tests as coded cannot answer the H3 question); S10 no rate grid; S11 abrupt spoof only, no noise scaling; S7 one toggle period (ARCH: five); S12 sign_flip at 20% only; S15 "attacked nodes meet S2" leg missing; S3/S14 consistency and stability criteria are stubs. Each is a scenario the paper must not describe as evaluated for its stated intent. Proposal: either register the missing legs before M4 or state the narrower scenario in the paper. Any addition after tuning data is design-after-data and must be labelled.

g. **S5 arithmetic**: `round(0.3*5) = 2` (Python banker's rounding), so N = 5 fails 40%, not 20% (docs said 20%); fleet_adapter `_s5_kwargs`. N = 10 (the spec size) is unaffected (3 nodes = 30%).

h. **kappa_R status stamp still says 40.** `scenarios.py:34` `KAPPA_R_STATUS = "PROVISIONAL_D047_kappa_R=40"`; `campaign.py`, `fleet_adapter.py` default `kappa_R=40.0` (D-067's CORE-ROBUST change 0 fixes the default; the stamp/config-hash literals must follow, otherwise every row is stamped "kappa_R=40" while running 60). Also the detector v3/theta0 retrain (D-067).

i. **ANEES_pos uses the diagonal of P** (`metrics.py:102-113`), ARCH section 6 writes the full-P form; the ANEES-in-[0.5, 2] criterion (S1, S10) is evaluated on the diagonal approximation. Stated in the code docstring but not in ARCH or the paper's criterion; correlated position errors make the diagonal NEES not equal to the true NEES.

j. **w metrics whole-mission only.** `runner.py:197` emits `mean_w_gnss` over the entire run; D-066 (4) requires per attack window and whole mission (and the split w_pos/w_clk). S4's reacquisition-cap criterion needs w at reacquisition. Add `mean_w_gnss_att`, `w_gnss_at_reacq`.

k. **Latency censoring conventions differ** (S2: t_off - t_on = 300 s; D-064 event-level: 60 s; report.py: `nanmax` of the observed values). Pre-register one rule per metric family before M4.

l. **Sample-size step not wired.** ARCH 7.1 requires a pilot on seeds 600-609 and `n = ceil((z_.975+z_.8)^2/d_z^2)+2` decided before test seeds; `stats.required_sample_size` exists and is unit-tested, but no script/campaign step computes d_z from pilot runs or records the decision. Add a pilot step that writes `results/pilot_d_z.json` (hash-logged).

m. **Gate scope.** `run_campaign` is the only gate (item 5). D-062's clean-tree/revision recording ("valid only if clean and unchanged") is not implemented in `campaign.py` (`config_hash` covers config only). Paper NOTES #V.F already says "not verified".

n. **ALIE docstring/author error.** `fl/poisoning.py:43` writes "Baruch, Baruch & Yehuda Alon Alon 2019"; the paper is Baruch, Baruch & Goldberg, NeurIPS 2019 (cite entry in paper/NOTES). The implementation is the "standard simplification" (closed-form z), documented as PROPOSED-DECISION. `alie()` shifts `mu - z*sd`, the sign convention should be checked against the paper when the S12 ALIE results are written up (results show ALIE has little effect: FEDERATION.md table).

o. **Reference doc drift outside my mandate** (not edited): docs/EVALUATION.md status line "9/15 scenarios runnable"; ARCHITECTURE section 4.1 detector size (13/52/882 vs 15/60/1010, paper NOTES #1); TRAINING.md/EVALUATION.md still carry "kappa_R = 40 PROVISIONAL" in places; docs/FLEET.md mentions FedProx mu = 0 (now annotated).

p. **S7 nit:** `scenarios.py:316` compares against 137.93, not the integer 138 stated in ARCH (item 3).

---------------------------------------------------------------------------------------------------

## Summary table (one line each)

| # | Topic | Recommendation | Can change results? |
|---|---|---|---|
| 1 | sigma_nom | Definition (d): across-seed std of undefended nominal RMSE_h(P_pre), measured once on >= 20 disjoint tuning seeds per IMU grade, frozen and hashed before M4; D-055 itself defines no sigma_nom (only D-061 does); anything else is post hoc | Yes |
| 2 | Confirmatory family | Fixed 8-test family (H1 x2, H2 event-level x2, H3 latency_eff x2 grades, H4 x2), Holm with fixed m; fix H4 dead entry; H2 dropping RMSE needs Master ruling | Yes |
| 3 | S7 bound | Bound is a function of the frozen trust config (min cycle time); 138 (v1) vs 52 (v2, needs the "exit only via PROBE" premise verified); re-derive after D-066 freeze incl. min(w_pos, w_clk) alias; pre-register with integer count rule | Yes (S7 only) |
| 4 | latency_eff | Signed t_det - t_eff, t_eff = first epoch with injected offset > 3 sigma_nom (same sigma_nom), censor at t_off - t_eff, never-effective excluded (method-independent), needs a truth-side offset channel | Yes (H3 only) |
| 5 | Seed gate | Gate is `>= 10000`: change to [10000, 20000) + refuse unregistered >= 20000, with tests; verified no allocated seed overlaps the range; derived fleet seeds are >= 100000 | No |
| 6 | Other | S2 P_D bug (always 1.0), H4 unevaluable, three "never worse" metrics, sweep != S2, stale kappa_R stamp, w metrics window, censoring conventions, pilot step and D-062 tree check unimplemented | Several yes (a, b, c, d) |
