# TRUST-V2 (D-051) implementation notes

Terse; see EXECUTION_LOG.md for the full narrative, docs/specs/TRUST_DESIGN_V2.md
for the spec this implements.

## A. Labeller v2 sigma floors -- GATE FAILED, stopped here

Implemented `fedqpnt/trust/pseudolabel.py::SIGMA_FLOOR_15` / `apply_sigma_floor`,
wired into `label_epochs` (applies regardless of whether `quantile_sd` is
caller-supplied or computed in-function). Floor values per the D-051 table;
three features (resid_rms x10, div_cusum x12, outage x13) are not in that
table and are left un-floored (PROPOSED-DECISION, see the module docstring).
x1/x2/x3 (nis_pos/nis_vel/raim) are dof-normalised in this codebase already,
so the spec's literal "0.5*dof" floor is reinterpreted as 0.5 on the
already-normalised feature (PROPOSED-DECISION, dof-invariant).

Gate run: `scripts/gate_a_labeller_v2.py` (ref calib seeds 500-519 clean
1800s; held-out clean rate seeds 520-529, 600s; precision seeds 530-549
mixed, 600s). Result -> `results/m1/gate_a_labeller_v2.json`:

  clean_run_positive_label_rate = 0.0218  (target <= 0.01)   FAIL
  precision vs oracle           = 0.214   (target >= 0.80)   FAIL
  recall vs oracle              = 0.587   (not gated)

Per-seed clean rate is bimodal (7/10 seeds exactly 0.0, 3/10 seeds ~0.053-0.057),
suggesting a specific transient (not a uniformly-degenerate feature) still
trips the joint chi2_11 rule on some clean seeds even after flooring.
Precision is far below target -- since sigma floors only touch the NEGATIVE
rule (and, incidentally, the D-024 xsat/cn0 POSITIVE rule's shared quantile,
which floors made MORE conservative, not less), the precision failure
implicates the POSITIVE rules (agc dwell / raim / clk_jump / s_cusum), which
D-051 sec A left unchanged. Not investigated further -- STOP HERE per the
Master's instruction; no retrain, no iteration.

## B. Detector -- class-weight cap done + unit test; retrain NOT run (gate A failed)

`train_local`: class-weight cap at 10x (D-050), `w_pos`/`w_neg` now returned
in the metrics dict for testability. Unit test
`tests/test_trust_detector.py::test_class_weight_cap_bounds_update_norm_with_single_negative`
(a single negative in an all-positive batch, n=100 vs n=5000 -- weight and
update norm both stay bounded). Platt calibration wired into
`TrustDetector.score` (runtime path: `get_params`/`set_params` carry
`platt_a/b_{spoof,jam}`, identity by default) so the trust law consumes
calibrated p once weights are trained -- this part is code-complete and
does not depend on gate A's data outcome. The actual retrain-on-relabelled-
data / Platt-fit / heldout-AUC pipeline (spec steps 2-5) was NOT run: gate A
failing means the labels retraining would consume are not trustworthy yet.

## C. Trust law v2 -- complete, unit-tested

`_LawCoreV2` in `fedqpnt/trust/trust_law.py`: TRUST/DISTRUST/PROBE state
machine (T_ex=60s, T_probe=10s, w_probe=0.3, T_sup=120s), wraps the existing
`_LawCore` unchanged for p-bar/hysteresis/tau_star/G. E_s (physical spoof
evidence) reuses the detector's own running normalizer as the clean
reference, sigma-floored the same way as the labeller
(`TrustEngineImpl._physical_spoof_evidence`). Selected via
`TrustLawConfig`/`TrustEngineConfig.trust_law_version` ("v1" default,
"v2" only for `fedqpnt`/`baseline_b_cont` in `_METHOD_TABLE` -- baseline A,
B-bin, B' stay v1/unchanged as specified).

Unit tests (`tests/test_trust_law_dynamics.py`), all passing:
  - chronic false-positive detector on clean data: exclusion (DISTRUST+PROBE)
    never runs longer than T_ex+T_probe=70s continuously; recovers to w>0.9.
  - persistent E_s evidence (drift/xsat stand-in): stays <= w_probe through
    every probe, attack_detected stays True.
  - consistent partial jamming (elevated p, clean NIS, no E_s): recovers to
    TRUST within one 70s cycle.
  - S7 chattering re-verified for v2 (5 periods x 3600s): cycle bound
    ceil(3600/70)=52 holds (v1's own bound, ceil(3600/26.1)=138, also
    unaffected -- v1 path is untouched).

Full existing `test_trust_law_dynamics.py` suite: 25/25 (one pre-existing
test, `test_reacquisition_cap_via_trust_engine`, needed a version-agnostic
`SensorTrustLaw.force_w()` hook added since it used to poke `._core.w`
directly, which is now the WRONG core once "fedqpnt" defaults to v2).

## D. M1 acceptance -- NOT RUN (gate A failed, per the Master's stop rule)

## Regression

`tests/test_trust_pseudolabel.py` 5/5, `tests/test_trust_detector.py` 7/7,
`tests/test_trust_law_dynamics.py` 25/25, `tests/test_trust_features.py` /
`test_trust_quantum.py` / `test_trust_leakage_guard.py` / `test_node_clock.py`
/ `test_node_leakage_guard.py` all green, `test_node_e2e.py` 7/7. Final
`pytest tests/test_trust_*.py tests/test_node_*.py tests/test_eval_*.py -q`
run at end of session -- see EXECUTION_LOG for the number.

## Permission denials

None (session 1: gate A). None (session 2: D-052).

## D-052 update: supervised primary path (session 2)

Master ruling: pseudo-labelling becomes an ablation; primary detector
training is SUPERVISED on oracle AttackLabel, joined OFFLINE after each
mission (never inside Agent/TrustEngineImpl at runtime).

New: `fedqpnt/training/build_supervised_dataset.py` (the ONLY place
AttackLabel is joined with features -- statically enforced by
`tests/test_training_leakage_guard.py`, 3 tests, green), reusing the real
Agent/Environment pipeline. `scripts/train_supervised_v1.py`: train (seeds
500-549) / Platt (550-574, oracle-labelled, natural ratio) / heldout eval
(575-599). Saved `results/m1/detector_weights_sup_v1.npz` +
`detector_train_sup_v1_report.json`.

Heldout family AUCs (oracle-vs-calibrated-score, bootstrap CI):
  jamming   0.649 [0.562, 0.747]
  drift     0.999 [0.997, 1.000]
  meaconing 0.999 [0.997, 1.000]
  abrupt    0.751 [0.735, 0.773]  (calibrated)
  overall   0.923 [0.917, 0.930]
All four families > 0.5 -- PASS. Brier: raw 0.075, calibrated 0.053.

M1 acceptance (trust law v2 + supervised detector, tuning seeds,
kappa_R=40 PROVISIONAL):
  S1 (5 seeds x 30 min): FAR=0/h for fedqpnt_local and baseline_b_cont
    (criterion <=1/h) -- PASS. RMSE_h ratio median 0.990 (<=1.05) -- PASS.
    ANEES_pos 1.30 (in [0.5,2]) -- PASS. No divergence (RMSE_h ~2-4m
    throughout, all seeds) -- PASS.
  Smoke matrix (4 scenarios x 7 methods, seeds 500-504): complete, no
    crashes/NaNs outside the expected nominal-scenario "no attack phase"
    cells. fedqpnt_local: drift 121m, meaconing 20m, jam_cw 246m RMSE
    (attack-phase) -- far better than baseline_a (642-658m on spoof
    families) and comparable to baseline_b_cont (identical law, expected).
  Defended-vs-undefended (D-048, sigma_nom measured per run): fedqpnt_local
    PASSES both nominal (2.77 vs 2.82 undefended mean, sigma_nom=0.82) and
    jam_cw (245.8 vs 236.8 undefended mean +3*63.7=427.8 threshold) --
    PASS. (baseline_a fails jam_cw: 658 > 427.8 -- a known baseline
    weakness, not fedqpnt/B-cont, out of scope to fix per "don't tune
    beyond spec".)

Ablation-for-the-record: gate-A (label-free/pseudo-label) run from session
1 -- clean-run positive rate 0.0218 (target <=0.01, FAIL), precision 0.214
(target >=0.80, FAIL) vs oracle. Superseded as primary path by D-052; kept
only as the ablation number.

Regression: full `pytest tests/test_trust_*.py tests/test_node_*.py
tests/test_eval_*.py tests/test_training_leakage_guard.py -q` = 122 passed.
