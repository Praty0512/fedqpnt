# M1_CLOSE_NOTES -- WP M1-CLOSE (terse implementation record)

Reads: D-026 (detector design FROZEN), D-029 (retrain on real features),
D-035, D-043, D-046 (kappa_R=40 PROVISIONAL, overconfidence PARKED).
Reuses fedqpnt/node/{runner,methods,agent,environment}, scripts/run_m1_smoke.py,
scripts/tune_kappa_r.py. Did NOT edit fedqpnt/fusion/eskf.py, fedqpnt/core,
fedqpnt/gnss, fedqpnt/fl.

## Task 1: kappa_R = 40 PROVISIONAL -- CONFIRMED, no retune

`fedqpnt/node/agent.py::AgentConfig.kappa_R = 40.0` and
`fedqpnt/node/methods.py::DEFAULT_KAPPA_R = 40.0`, both commented PROVISIONAL
(D-023/D-027/D-046). Not touched.

## Task 2: detector retrained on REAL closed-loop features

New script `scripts/retrain_detector_real.py`. Design UNCHANGED (D-026:
xsat rule on, class-balanced local training). Runs the REAL Agent
(GnssReceiver.solve -> ESKF propagate/innovations/correct with FIELD CAI,
method="fixed_trust", kappa_R=40) over seeds 500-599, ground/industrial_mems,
300 s/run: 20 clean-calibration seeds (500-519, quantile reference, D-024/026
style, never self-referential), 60 training seeds (520-579, 1-in-5 clean +
4 attack families cycled), 20 disjoint held-out seeds (580-599, same mix).

Real features captured by wrapping (monkeypatch, not editing)
`TrustEngineImpl.extractor.step` on the running instance -- x1/x2 (nis_pos/
nis_vel) are now REAL ESKF innovations, not the always-zero placeholder the
old `methods.pretrain_detector` used. The hindsight divergence statistic fed
to `label_epochs` is `surrogate_s_cusum`'s SAME Page-CUSUM formula, now fed
REAL (nonzero, FIELD-CAI-aided) x1 -- per D-029 this is no longer a
surrogate: with a genuine running ESKF fusing CAI, nis_pos (innovation
before correction) literally IS "the CAI-aided-INS-vs-GNSS divergence" the
spec calls for. Weights + provenance (config hash, seeds, date, method,
kappa_R) -> `results/m1/detector_weights_real.npz` /
`results/m1/detector_retrain_report.json`. Labelled "tuning seeds, not for
publication" throughout.

Wall: 624 s collection (100 runs, 6 workers) + training/eval, 27072 epochs.

Pseudo-label precision/recall vs oracle (train pool, evaluator-only):
precision=0.602, recall=0.995, n_oracle_pos=4734.

AUC old (synthetic, D-026 frozen table) vs new (real closed-loop), held-out:

| family    | old (synthetic) AUC [CI]     | new (real) AUC [CI]           |
|-----------|-------------------------------|--------------------------------|
| overall   | 0.722 [0.697, 0.749]          | 0.835 [0.825, 0.845]           |
| drift     | 0.724 [0.652, 0.792]          | 0.924 [0.903, 0.941]           |
| meaconing | 0.575 [0.501, 0.652]          | 0.997 [0.995, 0.999]           |
| abrupt    | 0.749 [0.678, 0.817]          | 0.413 [0.380, 0.447]  (BELOW CHANCE) |
| jamming   | 0.515 [0.422, 0.603]          | 0.142 [0.038, 0.210]  (BELOW CHANCE) |

**Finding, not fixed (D-026 freeze forbids design changes; retrain-only
task):** abrupt/jamming regressed sharply below chance on real closed-loop
features despite drift/meaconing improving a lot. Overall AUC pooled across
families looks fine (0.835) but is dominated by drift+meaconing's large
sample counts; this masks the abrupt/jamming collapse -- report per-family,
never overall alone. Leading hypothesis (not verified): abrupt_spoof/jam_cw
epochs are the minority class in the real 60-seed training pool once
combined with balance=True 50% sampling, and/or "fixed_trust" data
generation (GNSS never excluded, kappa_R=40 R-inflation) shapes real x1/x14
differently for these two families than for drift/meaconing, whose signature
is dominantly C/N0-based (xsat rule) rather than innovation-based. Flagged
as a PROPOSED-DECISION for Master; no further iteration performed per the
D-026 stopping rule and this WP's retrain-only mandate.

## Task 3/4: smoke matrix + S1 -- see results/m1/smoke_matrix_real.json,
results/m1/s1_far_check.json (in progress / to be filled after runs finish).

## Task 5: CW jamming defended-worse-than-undefended -- see final report.
