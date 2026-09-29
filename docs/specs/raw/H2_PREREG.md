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
