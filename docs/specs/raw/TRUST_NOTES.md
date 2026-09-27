# TRUST_NOTES (WP-4.2/4.3) -- terse implementation record

## Files
`fedqpnt/trust/{features,detector,trust_law,pseudolabel}.py`, tests
`tests/test_trust_{features,detector,law_dynamics,quantum,pseudolabel,leakage_guard}.py`,
harness `tests/_trust_harness.py` (test-local, mirrors `tests/_helpers.py`).

## §3.1 features.py
13 raw features x1..x13 per GNSS epoch (`FEATURE_NAMES`), causal, Agent-side only.
x1/x2 = `Innovation.nis/dof` for sensor `"gnss_pos"`/`"gnss_vel"` (nominal-R, per C-1).
x3 = `raim_stat/max(num_sats-4,1)`. x4 = `mean_cn0 - 45.0` (MU_CN0_REF, [ASSUMPTION]).
x5=std_cn0. x6=cn0 rate. x7=agc_db. x8=`|clk_bias-pred|/3.0` (SIGMA_CLK_BIAS_M, [ASSUMPTION]).
x9=`|clk_drift delta|/0.2` (SIGMA_CLK_DRIFT_MPS, [ASSUMPTION]). x10=residual_rms.
x11=nsat_delta. x12=Page CUSUM of x1, k_c=1.5. x13=outage flag (previous epoch invalid/<4 sats).
On an outage epoch (`fix.valid=False` or `num_sats<4`): x1,x2,x4..x11 are reported as 0 (no
evidence to compute them); this epoch itself is NOT treated as an "evidence event" downstream
(see PROPOSED-DECISION list) -- only x13 on the NEXT epoch reflects it.
`EwmaStack`: u = `[x, EWMA_2s(x), EWMA_20s(x), x_j - x_{j-1}]` in R^52, `beta=1-exp(-dt/tau)`.

**PROPOSED-DECISION (contract gap):** §3.1's cross-satellite C/N0 correlation signature
(D-018) is not derivable from `GnssFix` (only mean/std C/N0 available, no per-PRN). Not
implemented; flagged for Master (`GnssFix.per_sat_cn0` in a v0.3, or accept std_cn0 as the
only weaker proxy).

## §3.2 detector.py
`TrustMLP`: 52->16(tanh)->2(sigmoid), 882 params (52*16+16 + 16*2+2 = 882). `LogRegDetector`:
52->2 linear+sigmoid (the `arch="logreg"` ablation). `torch.set_num_threads(1)` at import.
`FeatureNormalizer`: Welford running mean/std over raw (13,) features, `get_params()`/
`set_params()` expose `{"norm_mu","norm_sd","norm_count"}` (dict[str,ndarray], FL-ready).
`TrustDetector.train_local`: SGD, class-weighted BCE per head, optional FedProx term
`0.5*mu*||theta-theta_g||^2`. Metrics returned: `{n_pos,n_neg,loss,pl_rate}` only (§4.1).

## §3.3 trust_law.py -- continuous law
One state machine (`_LawCore`) implements eqs (1)-(4) + the anti-lockout timer; final
w-assignment is a `law_mode` switch (`SensorTrustLaw`), covering every §5 row as a config
diff over ONE code path:
- `continuous` (eqs 1-6, FedQPNT/B-cont/-quantum/logreg/FedAvg; B' differs only upstream in
  which `p` is fed in, via `TrustEngineConfig.p_source="bprime"`)
- `no_recovery_gate` (Abl -recovery-gate: G forced True)
- `binary_hysteresis` (Abl binary: `w = w_min if D else 1`, eqs 4-6 unused)
- `detect_switch` (Baseline B-bin: hard exclude at `w_excl` while D=1, hard w=1 once G fires)
- `fixed_exclude` (Baseline A: memoryless `w=1 if p<0.5 else 0`, no state at all)
- `w_equals_1` (A0 / Abl fixed-trust: w==1 always)

Defaults (all [ASSUMPTION], per §3.3 table, unchanged from spec):
`tau_p=0.5, theta_lo=0.2, theta_hi=0.8, theta_on=0.6, theta_off=0.3, T_on=0.5, T_off=5.0,
T_clean=10.0, tau_d=0.5, tau_r=10.0, w_min=0.02, w_excl=0.05, T_lock=120.0, w_cap=0.5,
w_reacq=0.5, T_gap=5.0` (T_gap from §9's reacquisition-cap row, not the eq table).
`frac_clean_threshold=0.9` (eq 4's `frac_{T_clean}(...) >= 0.9`).
`nis_clean_threshold = chi2.ppf(0.95,3)/3 ~= 2.6050` (the "x1 nominal" cutoff used by the
recovery gate's NIS-clean fraction and by the anti-lockout condition).

## §3.4 IMU trust
Rule-based: `w_imu = w_min` if IMU sample missing (gap) or `|f_b|` axis exceeds
`IMU_SATURATION_MPS2=156.9` ([ASSUMPTION], ~16g tactical-MEMS full-scale), else 1.0. No
smoothing (matches spec: "no attack in v1 targets the IMU").
**PROPOSED-DECISION:** §3.3 defines `TrustState.anomaly_scores["imu"]` as "p_bar_imu", but
§3.4's rule has no probability. Reported as `1 - w_imu` (binary 0/1 proxy) for schema symmetry.

## §3.5 Quantum trust
`p_q = 1 - valid * clip((contrast-c_min)/(c_nom-c_min),0,1) * [NIS_Q <= chi2_m(0.999)]`, then
two-sided Page CUSUM on the standardised hybrid residual while `w_gnss>0.9`:
`S+ = max(0,S+ + r~-0.5)`, `S- = max(0,S- - r~-0.5)`, alarm `h=8`; an alarm forces `p_q=1`.
Reuses `SensorTrustLaw` with `quantum_law_config`: `tau_d=T_c, tau_r=60s, T_clean=5*T_c,
c_min=0.1, c_nom` from sensor config (all else = gnss defaults).
**PROPOSED-DECISION:** the spec gives a scalar `r~` from a vector `nu_Q`; implemented as
`mean over sensed axes` of `(nu_i - EWMA(nu_i))/sqrt(S_ii)`, EWMA rate `beta=0.1` (not
spec'd) as the causal `E[nu_Q]` estimator. `R_Q` is approximated by the Innovation's own `S`
diagonal (nominal-R, per C-1) since a separate quantum-only R_Q is not exposed by the
contract.

## §5 method table -> `make_method_config(name)`
`fedqpnt, baseline_a, a0, baseline_b_cont, baseline_b_bin, bprime, abl_minus_quantum,
abl_minus_fl, abl_fixed_trust, abl_binary, abl_minus_recovery_gate, abl_logreg,
abl_fedavg` all map to a `TrustEngineConfig`. Detector-training source (FL vs local) and
aggregator choice are FEDERATED-agent config, outside this module's runtime behaviour --
`baseline_b_cont`/`abl_minus_fl`/`abl_fedavg` are therefore identical to `fedqpnt`'s
trust-law/detector-arch config here (as ARCHITECTURE.md's table structure implies: "config
diffs over ONE code path").

## §4.3 pseudolabel.py
`y_j=1` if in `[t_j,t_j+L=30s]`: surrogate/real S_cusum>=h1=20, or agc>=6dB for>=2s, or
raim>=chi2_{n-4}(1-1e-6), or clk_jump>=8. `y_j=0` if x1..x11 are "jointly nominal" (see
PROPOSED-DECISION) for >=90% of `[t_j-L,t_j+L]`. Else `nan` (abstain).

**PROPOSED-DECISION (measured, not cosmetic):** "lie inside their nominal 95% quantiles for
every epoch" was implemented first as-written (11 independent per-dim `|z|<=1.96` tests,
ANDed over every epoch in a 61-epoch window) and empirically produced **zero** negative
pseudo-labels across 25 real calibration runs (4 attack families x5 seeds + 5 clean, seeds
500-599) -- even fully clean runs got zero negatives, because `(0.95)^(11 dims) ~= 0.57` per
epoch, so `0.57^61 ~= 0` over the window: the rule is vacuous as literally read. Replaced
with (a) a JOINT chi2_11(0.95) Mahalanobis test per epoch instead of 11 independent tests,
and (b) a `>=90%` clean-fraction-of-window test instead of a literal 100% AND (mirrors the
recovery gate's own `frac_clean_threshold=0.9`, eq 4). After the fix: 692 negatives / 602
positives / 11 abstains over the same 25-run pool (was 0/1449/1276 abstain-dominated before).
Flagged for Master ratification; both changes are documented in-code at the exact line.

`surrogate_s_cusum` (Page CUSUM of x1) stands in for the real CAI-aided-INS hindsight
reference (fusion filter doesn't exist at M0); `pseudolabel_precision_recall` is evaluator-
only (oracle `AttackLabel`, never used by `label_epochs`).

## Validation results (`python -m pytest tests/test_trust_*.py -q`)
- Chattering (S7): 0 trust cycles observed at all 5 adversarial toggle periods {2,5,10,20,60}s
  and under near-threshold noise, over a 1-hour synthetic run each; formal bound allows up to
  `ceil(3600/26.1)=138`. **Mean w_gnss during the ON (attack) phase**: 0.020-0.024 (== floor
  `w_min`) at every period -- confirms "0 cycles" means it STAYS distrusted, not stuck trusting.
- Distrust latency: 1 epoch at 1 Hz (w<0.5 after 1s), matching the ~w=0.16 design value.
- Recovery: measured 20-45s window (design ~=32.9s = T_clean + tau_r*ln(0.98/0.1)), passes.
- Reacquisition cap: verified w<=w_reacq=0.5 on the first valid fix after a >T_gap outage,
  both directly on `SensorTrustLaw` and through `TrustEngineImpl.update`.
- Floor/boundedness: `w in [w_min, 1]` held over 5000 random adversarial steps.
- Determinism: identical trace on repeated runs from the same seed.
- Quantum trust (real `QuantumAccelerometer`, D-019 GE outlier chain): min w_q = 0.227 over a
  400s run with the outlier channel on (settled after 60s), vs. floor w_min=0.02 -- drops
  meaningfully but the CUSUM (h=8) takes some dwell to fire on isolated bursts, as designed.
  Sustained rotation (contrast loss, rigid pointing): w_q -> 0.02 (floor) within the turn.

## D-022 detector bug-fix round (Master ruling: detector NOT accepted pending root cause)

**Root cause of below-chance meaconing/jamming AUC, found and fixed:**
1. **Real bug (features.py):** `GnssFeatureExtractor.step` zeroed ALL of x1..x11 on ANY
   outage/invalid fix, including x4/x5/x6/x7/x11 (mean_cn0, std_cn0, cn0_rate, agc, nsat_delta)
   which ARE populated by `GnssReceiver.solve` even on an invalid fix -- these are exactly the
   strongest jamming evidence (near-zero C/N0, deeply negative AGC, sats dropping to 0). Fixed:
   only x1/x2 (no innovation without a fit), x3/x10 (raim/resid_rms are NaN below min_sats),
   x8/x9 (clk_bias/drift NaN on an invalid fix) are still zeroed; x4/x5/x6/x7/x11 are always
   computed from the real fix.
2. **Real bug (pseudolabel.py):** the `agc >= 6 dB` rule assumes AGC RISES under jamming, but
   this codebase's convention (contract docstring + `fedqpnt.attacks.jamming` module
   docstring: "AGC reduces reported gain...") has AGC DROP under jamming. The rule as written
   never fired on any jamming run (verified: 0/21 epochs). Fixed to `|agc| >= 6dB`.
3. **Harness fix:** `tests/_trust_harness.py` used to drop every invalid-fix epoch entirely
   (introduced during earlier debugging) -- combined with bug 1, this meant the ONLY jamming
   epochs surviving into train/eval were the mild, still-valid ones, which look nearly clean.
   Now that features carry real signal even on an invalid fix, these epochs are kept.

**Effect:** jamming AUC 0.430 -> 0.773 (CI [0.702,0.845]); overall AUC 0.688 -> 0.727 CI
[0.700,0.755].

**Meaconing (0.267 -> 0.246, CI [0.194,0.301] -- still significantly BELOW chance, diagnosed,
NOT a leftover bug):** MeaconingReplay is "delta-on-clean" (D-018 module docstring): it
rebroadcasts the REAL signal plus one common-mode delay. That delay is degenerate with the
receiver's clock-bias unknown, so once absorbed (1 epoch after onset) the WLS position
solution, residuals and NIS are statistically indistinguishable from clean GNSS for the
REMAINDER of the (60s) attack -- confirmed by direct feature-mean comparison on oracle-
positive vs oracle-negative meaconing epochs (seed 550): nis_pos 0.53 vs 0.45, raim 1.33 vs
1.36, resid_rms 1.95 vs 1.98 (all indistinguishable). ONLY the single onset-epoch clk_jump
transient (mean clk_jump 7.76 over the whole active window, diluted by ~59 near-zero epochs
-- i.e. one epoch far above the h=8 threshold) is caught by the current §4.3 y=1 rule set,
so the L=30s forward-looking pseudo-label window only marks ~5% of active epochs positive;
the rest are pseudo-labelled negative, correctly per the RULES but incorrectly per the ORACLE
(the attack is still active; the receiver just cannot tell from these features alone).
**However, two features DO carry a real, learnable steady-state meaconing signature that the
current y=1 rule set does not key on:** x4 `cn0_mean` (mean +0.47 active vs -3.48 clean, the
+4dB replay power bump) and x14 `cn0_xsat_corr` (mean +0.47 active vs -0.01 clean -- the
uniform additive C/N0 bump raises cross-satellite correlation). A detector trained on the
current pseudo-labels is taught to associate these elevated values with "clean" (since most
elevated-cn0/elevated-corr epochs are mislabelled y=0), which is precisely why the AUC goes
*below* 0.5 rather than sitting at ~0.5 (a "genuinely hard, no signal" case would sit near
0.5, not significantly under it). **Recommendation (not implemented -- outside this agent's
authorized scope: PD2 only covered the negative-rule fix):** add a §4.3 y=1 rule keyed to
sustained x4/x14 elevation (e.g. `cn0_mean` or `cn0_xsat_corr` outside its nominal band for
>= some dwell), which would let the hindsight labeller correctly mark meaconing's steady
state. Flagged for Master ruling.

**All detector numbers in this section are PROVISIONAL (synthetic truth-derived Innovations,
tests/_trust_harness.py -- no fusion filter exists at M0). Re-run at M1.**

- Detector (seeds 500-599 only), post-fix: pseudo-label precision=0.652, recall=0.735 (train
  pool, 25 runs, 902 pos/587 neg/11 abstain). Held-out (seeds 550-554/595-599) AUC vs oracle,
  95% bootstrap CI (1000 resamples):
  - overall:   AUC=0.727  CI=[0.700, 0.755]
  - drift:     AUC=0.801  CI=[0.748, 0.856]
  - meaconing: AUC=0.246  CI=[0.194, 0.301]  (diagnosed above -- pseudo-label blind spot, not
    a code bug; both CI bounds are below 0.5, so this is a real, systematic effect, not noise)
  - abrupt:    AUC=0.937  CI=[0.904, 0.964]
  - jamming:   AUC=0.773  CI=[0.702, 0.845]  (was 0.430 before the fix)

## D-024: xsat-replay pseudo-label rule (fixes the meaconing blind spot)

Added `_xsat_replay_condition` to `fedqpnt/trust/pseudolabel.py`: fires y=1 when EITHER x14
`cn0_xsat_corr` > its clean-population upper quantile (mu+1.96*sd) OR x4 `cn0_mean` exceeds
its clean-population band by >=3dB, sustained for >=10s, within the L=30s hindsight window.
Physical basis (cited in-code): Radoš, Brkić & Begušić 2024, Sensors 24(13):4210, Fig. 5
(D-018) -- a single-antenna spoofer/meaconer re-radiates every PRN from one chain, raising
cross-PRN C/N0 correlation and the aggregate C/N0 level. Reference mu/sd are calibrated ONLY
on clean runs, seeds 500-529 (`tests/test_trust_detector.py::clean_reference` fixture),
never self-referential -- the SAME reference is now also used for the existing joint-chi2_11
negative rule (previously self-referential per-run, which was itself a source of noise).

**Item 2 (false-positive check):** clean-run firing rate = **0.0%** (target <=1%, met).
Per-family firing rate (held-out seeds 550-554): drift=48.3%, meaconing=48.3%, abrupt=0.0%,
jamming=0.0%. Fires exactly on the two families that touch shared C/N0 structure (meaconing's
uniform power bump; DriftInSpoof's shared single-antenna Gauss-Markov C/N0 term, D-018 item 2)
and correctly does NOT fire on abrupt/jamming (neither has a single-antenna C/N0 signature).

**Item 3 (re-trained, PROVISIONAL, seeds 500-599 only):** meaconing AUC 0.246 -> **0.653**
(CI [0.576, 0.727]) -- crosses 0.5, per Master's stopping rule I do NOT iterate further on
labelling logic. Pseudo-label precision=0.649, recall=1.00 (train pool; recall rose because
the L=30s forward-window design flags essentially an ENTIRE short (60s), continuously-active
attack run once one epoch anywhere in it fires ANY rule -- verified structural, not new).

**Side effect observed, reported honestly (not iterated on further per the token-economy
instruction):** switching the joint-chi2_11 negative rule from self-referential per-run stats
to the fixed clean-only reference reduced the training pool's negative count 587->238 (83.8%
of labelled train epochs are now positive), and **jamming AUC regressed 0.773 -> 0.100** (CI
[0.066,0.144]) even though the xsat rule itself never fires on jamming (0% firing rate).
Diagnosis: detector output collapsed to a narrow, weakly-discriminative band (~0.42-0.49) for
jamming specifically, consistent with training on a much smaller/more homogeneous negative
pool under severe class imbalance (83.8% positive) rather than a labelling-polarity bug like
D-022's. Flagged for Master: likely needs either (a) a larger/more diverse clean-calibration
seed pool, or (b) an explicit negative-class floor/reservoir strategy in FL training (§4.2
already caps replay buffers at 50% positive for exactly this reason -- this local-only test
harness does not implement that cap). Overall AUC (all families pooled) = 0.671 CI
[0.645,0.697], down from 0.727 pre-D-024, driven entirely by the jamming regression.

## D-026: controlled 2x2 (calibration pool 500-549, class-balanced local training) -- FROZEN

Two changes at once (D-024) had confounded jamming's regression. D-026 isolated them:
1. Enlarged the clean calibration pool to seeds 500-549 (30->50 runs), as D-024 originally
   specified (I had used 500-529).
2. Class balance in LOCAL training mirrors §4.2's FL replay-buffer design rule ("at most 50%
   positives") via **SAMPLING** (down-sample the positive/majority class to the cap), not
   loss re-weighting -- `TrustDetector.train_local(..., balance=True, max_pos_fraction=0.5)`,
   `fedqpnt/trust/detector.py`. This is a design rule (unconditional when enabled), not a
   tuning knob.
3. 2x2 diagnostic, same held-out seeds, same 500-549 reference (`tests/test_trust_detector.py
   ::test_d026_2x2_diagnostic_and_frozen_design`):

| rule | balance | train pos/neg | AUC drift | AUC meaconing | AUC abrupt | AUC jamming | AUC overall |
|---|---|---|---|---|---|---|---|
| off | off | 902/295 | 0.727 [.656,.791] | 0.349 [.288,.414] | 0.822 [.765,.874] | 0.645 [.549,.733] | 0.711 [.684,.739] |
| off | on  | 295/295 | 0.653 [.585,.721] | 0.439 [.373,.511] | 0.782 [.716,.849] | 0.639 [.543,.726] | 0.704 [.678,.732] |
| on  | off | 1229/262| 0.747 [.680,.812] | 0.448 [.381,.515] | 0.819 [.765,.870] | 0.357 [.269,.442] | 0.691 [.665,.717] |
| **on** | **on** | 262/262 | 0.724 [.652,.792] | **0.575** [.501,.652] | 0.749 [.678,.817] | **0.515** [.422,.603] | 0.722 [.697,.749] |

**Item 5 diagnostic (labeller vs. classifier fault), jamming-ACTIVE epochs, ALL FOUR CELLS
IDENTICAL**: `{y0: 0, y1: 200, abstain: 0, n: 200}` -- every jamming-ACTIVE epoch gets
pseudo-labelled y=1 in every cell, regardless of rule/balance settings. **Conclusion: the
labeller was never at fault for jamming** (100% correct/consistent on the label side); the
D-024 jamming AUC collapse (0.773->0.100) was a CLASSIFIER-side effect of the smaller,
less-representative 500-529 calibration reference reducing/skewing the training negative
pool. With the enlarged 500-549 pool + 50%-cap balancing, jamming AUC recovered to
near-chance (0.515, CI straddles 0.5) rather than being inverted.

**FROZEN DESIGN (item 4): {rule on, balance on} adopted regardless of outcome. No further
rule/threshold/feature changes after this round; all numbers below are PROVISIONAL (synthetic
truth-derived innovations, no fusion filter until M1):**
- overall: 0.722 [0.697, 0.749]
- drift: 0.724 [0.652, 0.792]
- meaconing: 0.575 [0.501, 0.652] (accepted per D-026; 0% clean false-firing, physically
  grounded per Radoš et al. 2024 Fig. 5, D-018)
- abrupt: 0.749 [0.678, 0.817]
- jamming: 0.515 [0.422, 0.603] (near chance, no longer inverted; CI straddles 0.5 -- honestly
  reported as weak, not strong, detection for this family under the current feature set)

## v0.3 cross-satellite C/N0 features (D-022 item 2)
`GnssReceiver.solve` now fills `GnssFix.cn0_per_sat`/`elev_per_sat` from the tracked/locked
satellite list (both branches: valid fit and the n<min_sats early-return). New features:
- x14 `cn0_xsat_corr`: mean pairwise Pearson correlation of per-PRN C/N0 over a
  `CORR_WINDOW_EPOCHS=20` sliding window (a PRN must appear in >=60% of the window and a pair
  needs >=5 co-present samples to count; 0.0 if too few qualifying PRNs/pairs).
- x15 `cn0_elev_slope`: current-epoch OLS slope of C/N0 vs elevation across tracked PRNs
  (`cov(cn0,elev)/var(elev)`); 0.0 if <2 sats or no elevation spread.
`N_FEATURES` is now 15 (`STACK_DIM`=60 in detector.py, auto-derived). x14 shows a strong,
correctly-signed meaconing signature (see above) and is a useful lever for the recommended
new y=1 rule.
