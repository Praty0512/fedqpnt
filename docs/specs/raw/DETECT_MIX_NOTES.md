# DETECT-MIX (D-053a/b) implementation notes

Terse. All results below are kappa_R PROVISIONAL; tuning seeds (500-599,
plus a disjoint 9500-9699 block for the D-053b sweep/RMSE checks -- still
tuning-range, never test seeds). Design (detector arch, class-weight cap,
trust law v2, Platt calibration) is UNCHANGED per D-026/D-051; only the
training-mission mix and experiment parameters (jammer_eirp_dbw per level,
cn0_sig_scale) change.

## D-053a: root cause of the old "8 jamming-positive epochs" bug

Traced empirically (not just asserted): the old training-mission plan used
severity=0.5 on `jam_cw` with the class default jammer geometry
(`jammer_pos_enu=(500,0,0)`, `jammer_eirp_dbw=10`). At that geometry, FSPL
at 500 m is ~90 dB, so even severity=0.15 (the log10(severity) EIRP scaling
in `fedqpnt.attacks.jamming.Jamming.apply` only spans a few dB) drives
effective C/N0 (via `effective_cn0_dbhz`) to roughly -10 dB-Hz -- so far
below the receiver's 25 dB-Hz lock threshold
(`fedqpnt/gnss/receiver.py::CN0_LOCK_THRESHOLD_DBHZ`) that EVERY satellite
loses lock simultaneously for the whole [0,1] severity range. `Agent.step`
maps an invalid fix to `fix=None` (fedqpnt/node/agent.py), so the trust
extractor is never called that tick -- zero (feature,label) pairs get
captured, regardless of severity. This is a data-collection/experiment-
parameter issue, not a detector-design issue (nothing in fedqpnt/trust or
fedqpnt/node/agent.py changed).

Fix: vary `jammer_eirp_dbw` (already a supported AttackSpec `params` field,
zero code changes to fedqpnt/attacks/jamming.py) per severity level, chosen
by direct calibration against `effective_cn0_dbhz` and confirmed empirically
(fraction of the 180 s attack window, at 1 Hz, with a still-valid fix, out
of 181 possible epochs), at the class-default 500 m jammer distance:

| severity | jammer_eirp_dbw | fix-valid fraction (measured) |
|---|---|---|
| 0.15 | -55 | 181/181 (clean-ish) |
| 0.25 | -45 | 181/181 (mild) |
| 0.35 | -38 | 181/181 (partial) |
| 0.45 | -33 | 150/181 (partial, some drop) |
| 0.55 | -30 |  99/181 (transition) |
| 0.80 |  +5 |   ~0-2/181 (full denial) |
| 1.00 | +20 |   ~0-2/181 (full denial; matches the OLD default regime) |

`fedqpnt/training/build_supervised_dataset.py::JAM_LEVELS` (7 entries).
`jam_cw`/`jam_wideband`/`jam_then_spoof` each cycle through these by
`seed % 7`; `jam_then_spoof`'s spoof phase (after the jam phase, onset
100s, 60s after jam onset) contributes positive epochs regardless of
whether the jam phase itself captured anything.

## D-053a: 6-family rebalance

`FAMILY_NAMES = [drift, meaconing, abrupt, jam_cw, jam_wideband,
jam_then_spoof]` (was 4: drift/meaconing/abrupt/jamming=jam_cw only).
`plan_for` now assigns clean at `seed % 10 == 0` (~10%, was 1-in-5) and
round-robins the 6 families on the rest (`seed % 6`) -- same convention
reused unmodified across the disjoint TRAIN(500-549)/PLATT(550-574)/
HELDOUT(575-599) seed blocks. `jam_then_spoof` is built as TWO chained
AttackSpec dicts in one mission (jam_wideband 60-120s, drift_spoof 100-280s,
overlapping so the spoof captures the reacquiring receiver) rather than via
`fedqpnt.attacks.jamming.JamThenSpoof` directly, since that class isn't
wired into `NodeEnvironment`'s generic single-kind attack builder
(PROPOSED-DECISION already flagged in environment.py) -- equivalent effect,
zero environment.py edit.

Pre-registered estimate (from the calibration table above, before the real
run) of TRAIN-pool (500-549) positive epochs per family: all 6 families
estimated >=600 (jam_wideband lowest at ~617; see script console output
`train_pool_family_positive_counts` in the report JSON for the actual
measured counts).

## D-053a: train_supervised_v2.py

Same frozen pipeline as v1 (MLP arch, class-weight cap 10x D-050, per-head
runtime Platt) -- only inputs (mission mix above) and reporting change.
Added: per-family TRAIN-pool positive-epoch counts (evidences the >=500
target directly, not just asserted), and a per-head (spoof-only AUC vs
oracle y_spoof, jam-only AUC vs oracle y_jam) breakdown alongside the
existing combined (max(spoof,jam)) head, both per-family and overall.
Saves `results/m1/detector_weights_sup_v2.npz` /
`results/m1/detector_train_sup_v2_report.json`.

## D-053b: signature-strength scale factor

`fedqpnt/attacks/spoofing.py::DriftInSpoof.cn0_sig_scale` (default 1.0,
config()-exposed). Scales BOTH the shared Gauss-Markov fluctuation sigma
(`common_cn0_fluct_sigma_db * cn0_sig_scale`) and the post-capture
convergence fraction toward the common spoofer level
(`cn0_sig_scale * conv_frac_full`) by the same factor s. s=1.0 reproduces
D-018 exactly (regression-tested: existing test_attacks_spoofing.py all
green, unchanged). s=0.0 means each spoofed PRN keeps its own individually-
boosted, still-elevation-dependent C/N0 -- no cross-PRN correlation induced
by this mechanism at all.

`scripts/sweep_signature_strength.py`: sweeps s in {0, 0.25, 0.5, 0.75, 1}
on drift-spoof, scores the FROZEN v2 detector (trained once at s=1) on
fresh held-out drift missions (seeds 9500-9504) and meaconing missions
(seeds 9505-9509, cn0_sig_scale-independent CONTROL -- meaconing's own
C/N0 bump is uniform across PRNs by construction, unrelated to this knob).
Also runs the s=0 FedQPNT-vs-undefended attack-phase RMSE_h comparison (3
seeds x 10 min, drift spoof, cn0_sig_scale=0) via the real closed-loop
runner (`fedqpnt.node.runner`), `rmse_h_att` metric.

## Results

First TRAIN pass landed jam_wideband at 397 positive epochs (<500 target);
bumped jam_cw/jam_wideband attack `duration_s` 180->240s (no seed/severity
change) and retrained once -- second pass cleared all 6 families. Final
TRAIN-pool positive-epoch counts (seeds 500-549):
drift 1092, meaconing 1448, abrupt 1246, jam_cw 836, jam_wideband 577,
jam_then_spoof 1368 spoof + 177 jam. All >=500. Oracle jam positives across
TRAIN pool: 1590 (vs the old pipeline's 8).

HELDOUT (575-599) per-family AUC (calibrated), v2 vs v1:
drift 0.998 (v1 0.999), meaconing 0.999 (v1 0.999), abrupt 0.691 (v1 0.754,
WORSE -- more jam/jam_then_spoof training data did not help abrupt, an
honest negative sub-result), jam_cw 0.996 (v1's single "jamming" family was
0.649), jam_wideband 0.988 (new family), jam_then_spoof 0.997 (new family).
Overall 0.953 (v1 0.923). Per-head: spoof 0.929, jam 0.988 overall (v1 jam
head was not separately reportable at n_pos=8). Brier calibrated 0.0676
(v1 0.0529 -- slightly worse; more heterogeneous jam data broadens the
calibration spread). Full table: `detector_train_sup_v2_report.json`.

D-053b sweep (v2 detector, frozen, trained at s=1; fresh seeds 9500-9509):
AUC(drift) vs s: s=0 -> 0.129 (WORSE than chance -- the detector doesn't
just lose signal, it inverts, since it was trained exclusively on s=1
missions and produces a systematically wrong-signed score off-distribution),
s=0.25 -> 0.524 (chance), s=0.5 -> 0.995, s=0.75 -> 0.999, s=1.0 -> 0.999.
AUC(meaconing), the s-independent control: 0.999 flat across every s (
correctly unaffected, since meaconing's C/N0 bump doesn't use this knob) --
confirms the effect is isolated to the drift signature as designed, not an
artifact of the sweep harness. Drift detection is thus almost entirely
carried by the D-018 single-antenna signature between s=0.25 and s=0.5;
below that it does not merely degrade, it fails outright.

D-053b s=0 RMSE (3 seeds x 10 min, drift spoof, cn0_sig_scale=0): FedQPNT
mean rmse_h_att = 2359.8 m vs undefended 107.7 m -- ratio 21.9x WORSE than
doing nothing. Per-seed: seed 9600 FedQPNT~undefended (115 vs 107 m, fine),
seeds 9601/9602 catastrophic (2876 m, 4088 m). Consistent with the AUC=0.129
inversion: an anti-correlated detector score feeds the trust law a
wrong-signed signal, and on 2/3 seeds this drives worse-than-undefended
tracking rather than merely "no benefit". Reported as-is per the Master's
instruction -- this is the honest answer to "where the method stops
working": below s~0.5, FedQPNT is actively harmful on drift, not neutral.

S1 v2 (5 seeds x 30 min, `detector_weights_sup_v2.npz`): FedQPNT FAR/h =
0.0 (PASS, threshold <=1/h), median RMSE ratio (fedqpnt/fixed_trust) =
0.9904 (PASS, threshold <=1.05; FedQPNT slightly BETTER than fixed-trust
here), ANEES_pos = 1.306 (in [0.5,2]). baseline_a/fixed_trust/undefended
each show FAR=1.6/h on ONE seed (504, 8 false alarms/h) -- a pre-existing
non-v2-specific clean-run false-alarm at that seed/method combo, carried
forward as-is (not a new v2 regression: it hits fixed_trust and undefended
too, methods v2 doesn't change the NIS-gate/trust-weight config of).

## Regression

`pytest tests/test_trust_*.py tests/test_attacks_*.py
tests/test_training_leakage_guard.py -q`: 66 passed.

## Permission denials

None.
