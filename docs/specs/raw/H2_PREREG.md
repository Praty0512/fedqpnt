# H2-ABRUPT pre-registered metrics (D-064, Master ruling)

Status: PRE-REGISTERED, fixed before any re-run. Do not change after seeing
results (D-002). PARKED until the core (`fedqpnt/trust/trust_law.py`) is
frozen -- CORE-ROBUST still has a post-jam fix and a position/clock trust
split coming, both of which change closed-loop features. No fleet missions
run until Master confirms the core is frozen.

## Fixed experimental parameters
- Novel family: **abrupt** (theta0 = `results/fleet/theta0_noabrupt.npz`,
  pretrained seeds 400-449, families {clean, drift, jam_cw, jam_wideband,
  jam_then_spoof} -- abrupt and meaconing excluded).
- Attack: `abrupt_spoof`, **severity = 0.15** (12 m jump; chosen in
  `scripts/h2_abrupt_es_firing_check.py`, 0% E_s firing over 900 attack
  epochs at seeds 500-504 under the CORE-ROBUST-fixed D-058 jump test).
- Chosen FL hyperparams (D-054.3/D-056): local_epochs=2, lr=0.05,
  prox_mu=0, R=10.
- N=5 nodes, live missions 600 s, round_period_s=60, n_rounds=10.
- **Live seeds: 500-509 (n=10, increased from n=5 for power).**
- **Tau-calibration seeds: 580-599 (>=5 h clean data per arm), disjoint from
  the live seeds.**

## Verbatim ruling (D-064)

> PRE-REGISTERED H2/H4 metrics for the abrupt family. They are fixed now,
> before any re-run; do not change them.
>
> - **Primary: event-level detection** of each attack onset.
>   - P_D@10s = the fraction of attack events where raw_p crosses threshold
>     tau within [t_on, t_on + 10 s].
>   - tau is set PER ARM so that the clean false-alarm rate is 1/h.
>     Calibrate it on clean missions from tuning seeds disjoint from the H2
>     seeds (use 580-599, >= 5 h of clean data per arm), with the arm's
>     final installed model. This gives an equal-FAR comparison.
>   - Also report onset latency (the time to the first crossing; censored
>     at 60 s, with the censoring count stated).
> - **Secondary:** AUC on onset-window positives [t_on, t_on + 10 s] vs
>   pre-onset negatives only. Disclose that N = 10 s was chosen after
>   seeing one seed's trace (N = 2/5/10 -> 0.10/0.46/0.57); report N = 5
>   alongside it.
> - **Tertiary (descriptive):** full-window AUC, with your explanation.
>   Report the post-attack window separately as a "recovery alarm rate",
>   not pooled into negatives.
> - Statistics: paired Wilcoxon on P_D@10s and latency across seeds,
>   increase to n = 10 seeds (500-509) for power. Also report the per-seed
>   values.
> - Disclose the sampling difference: the isolated check was 1 Hz epochs,
>   the live run 100 Hz ticks. Compute every metric on 1 Hz detector-update
>   epochs from now on.
>
> PARKED until the core is frozen. CORE-ROBUST still has a post-jam fix and
> a position/clock trust split coming, and both change closed-loop
> features. Do NOT run fleet missions now.
>
> Allowed now, cheap and <= 1 process:
> - (1) write docs/specs/raw/H2_PREREG.md containing the above verbatim,
>   plus seeds, severity 0.15, and theta0;
> - (2) implement the metric code: the tau calibration and P_D/latency
>   functions in your scripts, with small unit tests if you can do so
>   without touching fedqpnt/ internals;
> - (3) dry-run the metric code on the existing (invalid) h2_abrupt outputs
>   only to prove the code runs. Do not report those numbers as results.

## Implementation notes (added by H2-ABRUPT agent, not part of the ruling)
- Sampling fix: all metric code operates on **1 Hz detector-update epochs**
  (ticks where `tick.gnss_epoch is not None`, i.e. the same ticks
  `fedqpnt.trust.detector`'s `score()` is actually called and `last_raw_p`
  changes), NOT the 100 Hz IMU ticks `fedqpnt/fleet/node_runner.py`
  currently logs every metric from. This matches the isolated held-out
  check's sampling protocol exactly.
- Each live mission has exactly ONE attack onset (one `abrupt_spoof` event
  per scenario), so "fraction of attack events" reduces to a per-seed
  binary detected/not-detected outcome, aggregated as a fraction across the
  10 live seeds -- no multi-event-per-mission splitting needed.
- Implementation: `scripts/h2_abrupt_metrics.py` (tau calibration,
  P_D@10s/latency, onset-window AUC, full-window AUC, recovery alarm
  rate) + `tests/test_h2_abrupt_metrics.py` (synthetic-array unit tests,
  no `fedqpnt/` internals touched beyond read-only imports of
  `fedqpnt.eval.metrics.compute_phases`/`roc_auc`, which are already used
  elsewhere in this task).
- A DRY RUN (`scripts/h2_abrupt_metrics_dryrun.py`) exercises the full
  pipeline end-to-end on one cheap single-node mission at the pre-registered
  attack config, to prove the code runs -- its printed numbers are NOT
  results (no valid frozen-core re-run has happened yet) and are labelled
  as such in the script's own output.

## AMENDMENT 1 (2026-09-30, made BEFORE any live H2/H4 run under this pre-registration)
theta0 = `results/fleet/theta0_noabrupt_v2.npz` (retrained on frozen core `core-freeze-2` = 845636e, same protocol/seeds/families as the
original theta0_noabrupt; zero-shot abrupt AUC at severity 0.15 = 0.834, 0.016 below the D-061a 0.85 low-headroom line, run as planned)
replaces `theta0_noabrupt.npz`. Everything else in this document is unchanged. The earlier (invalid, mixed-code) fleet run used the old theta0
and the pre-freeze core and is superseded.

## Implementation notes for the re-run (added before running; interpretation, not a metric change)
- Live seeds 500-509 (n=10), severity 0.15, kappa_R = DEFAULT_KAPPA_R at the freeze (60), 1 Hz epochs from node_runner epoch_* keys.
- tau calibration: per (arm, seed) using that run's FINAL installed model (`FleetResult.final_theta`), on clean-mission 1 Hz features from seeds
  580-599, 900 s each (= 5.0 h per model). DISCLOSED interpretation: clean features are collected once in the open-loop `fixed_trust`
  data-collection mode (`build_supervised_dataset.collect_run`, model-independent) and scored offline with each arm's model, instead of running a
  closed-loop clean mission per model. Live raw_p is computed under closed-loop trust; this feature-path difference is part of the disclosure.
- FAR = rising edges of raw_p > tau per clean hour (same definition as fedqpnt.eval.metrics.false_alarm_rate).

## AMENDMENT 2 (2026-10-02, dated BEFORE the confirmatory run; Master ruling D-077)
The core-freeze-2 H2/H4/control run is PRELIMINARY (leak-exposed). The CONFIRMATORY run is executed on core-freeze-3 (probe-exit fix merged). Changes
vs the preliminary analysis (all other pre-registered metrics/windows/seeds/theta0 = theta0_noabrupt_v2 unchanged):
1. tau calibration uses CLOSED-LOOP clean missions through the SAME runner as the live runs (`fedqpnt.fleet.node_runner._run_fleet_node`, n_rounds=0,
   no attack, kappa_R = DEFAULT_KAPPA_R, 1000 s, 1 Hz epoch_raw_p), replacing the open-loop `collect_run` feature path (whose raw_p did not match live
   closed-loop raw_p). Each arm's FINAL installed models (`FleetResult.final_theta` of that arm's 10 live seeds) are used: live-seed s's model is run on
   clean seeds 580+2(s-500) and 581+2(s-500) (all 20 clean seeds 580-599 used once per arm); first 60 s of each mission excluded; pooled = 20 x 910 s = 5.06 h
   per (part, arm). tau per (part, arm) = smallest threshold with FAR <= 1/h (rising edges per clean hour, same as `fedqpnt.eval.metrics.false_alarm_rate`).
2. Validity: a run is valid iff `git diff <start> <end> -- fedqpnt` is empty and `git status --porcelain fedqpnt/` is clean (not HEAD equality).
3. Confirmatory outputs: results/fleet/h2_abrupt_runs_freeze3/, results/fleet/h2_abrupt_clean_closedloop_freeze3/, results/fleet/h2_abrupt_prereg_results_freeze3.json
   (the preliminary freeze-2 files are not overwritten).
