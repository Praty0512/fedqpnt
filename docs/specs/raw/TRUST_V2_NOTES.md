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

None. All edits were within fedqpnt/trust/* and fedqpnt/node/* (well,
node/* untouched this session) plus scripts/* and tests/*.
