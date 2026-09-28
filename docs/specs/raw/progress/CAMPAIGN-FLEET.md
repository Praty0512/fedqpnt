# CAMPAIGN-FLEET progress

## Done
- Read D-048, D-050, D-052, D-054, D-056, EVAL_NOTES.md, FL_NOTES.md, ARCHITECTURE section 6.1/7.2/8.
- `fedqpnt/eval/fleet_adapter.py` (new, thin adapter): routes S5/S8/S9/S12/S15 to
  `fedqpnt.fleet.orchestrator.run_fleet`/`write_campaign_result`, writes campaign-schema result files
  into the SAME `<run_root>/<scenario_id>/<method>/seed_<seed>.json` layout as single-node runs.
  Method variants (D-054, from the shared theta0 `results/fleet/theta0_d054.npz`): `fedqpnt`
  (TRIM-NB-R), `fedavg_ablation` (FedAvg), `baseline_a` (TRIM-NB-R + detect-and-exclude node config),
  `baseline_b_cont`/`baseline_b_bin` (local-only: `n_rounds=0`).
- `fedqpnt/fleet/orchestrator.py`: one additive, backward-compatible edit -- `write_campaign_result`'s
  `scalar_keys` tuple extended with `auc`, `auc_detector_only`, `round_installs`, `far_per_hour`, `fpr`
  (previously not flattened; needed by the new S5/S8/S9/S12/S15 criteria). No removed/renamed keys.
- `fedqpnt/eval/scenarios.py`: S5/S8/S9/S12/S15 now have real executable `Criterion.check` functions
  implementing the ARCHITECTURE.md section 6.1 pass bounds (quorum/no-deadlock, AUC-drop bounds,
  cold-start install-within-2-rounds via per-node `provenance`, quarantine/FAR-margin for S15).
  `requires_fl=True` now means "dispatched to the fleet orchestrator", not NOT_RUNNABLE.
  AUC-drop criteria that need a "no-fault"/"no-loss"/"clean" reference arm (not run in the plumbing
  dry-run) correctly report `passed=None` with a detail naming the missing reference method, same
  idiom as the rest of the file's missing-data handling.
- `fedqpnt/eval/campaign.py`: `RunTask.is_fleet`; `generate_tasks` builds a lightweight fleet spec for
  `requires_fl` scenarios; `run_campaign` runs fleet tasks strictly sequentially in-process (never
  through the `ProcessPoolExecutor`, since each fleet task already spawns its own N+1-process
  federation) before the existing single-node pool logic. D-046/D-047 test-seed gate check is
  unchanged and applies to `seeds` before task generation, so it covers fleet scenarios too.
- `fedqpnt/eval/report.py`: `requires_fl` message updated to describe fleet dispatch instead of
  NOT_RUNNABLE.
- Dry run: TUNING seeds 500-501, N=3, 120s, 4 FL rounds, S5/S8/S9/S12/S15 x {fedqpnt, baseline_b_cont}
  (20/20 tasks `status="ok"`), labelled "PLUMBING ONLY" -- see
  `results/eval_fleet_dryrun/{report.md,report.csv}`, raw files under `runs/dryrun_fleet/`.
  Quorum/no-deadlock and cold-start-install-within-2-rounds criteria evaluated PASS on the plumbing
  data (expected -- N=3 short missions, not evidence); AUC-drop criteria correctly `n/a` (no
  reference arm run); S15's FAR-margin criterion FAILED on the plumbing data (30/h vs bound 1.5/h,
  as expected for an untuned 120s short run -- same caveat EVAL_NOTES.md already documents for the
  single-node dry run).
- `python -m pytest tests/test_eval_*.py -q` at the end: **57 passed** (1 pre-existing unrelated scipy
  RuntimeWarning in test_eval_stats.py, not from this session's changes).

## Known limitation (flagged, not fixed here -- out of my owned scope)
- `baseline_b_cont`/`baseline_b_bin` mapped to `n_rounds=0` skips FL rounds entirely inside
  `node_runner._run_fleet_node`'s tick loop, which ALSO skips that node's local `client.local_round`
  training call (it's invoked only from `_do_fl_round`). So these "local-only" fleet runs currently
  mean "frozen theta0, no local adaptation at all", not "local training without federation" as D-054
  intends. Fixing this needs a small additive hook in `fedqpnt/fleet/node_runner.py` (out of my owned
  files without a PD) -- flagged to Master.
- AUC-drop criteria (S5/S9/S12) need "no-fault"/"no-loss"/"clean" reference arms that the plumbing
  dry-run does not execute (kept minimal per the task's exact method list); they report
  `passed=None` until those reference runs exist.

## Next
- Master/FL-agent: decide on the `baseline_b_cont` local-training hook.
- Run the paired reference arms (`fedqpnt_nofault`, `fedqpnt_noloss`, `fedqpnt_clean`) once compute
  budget allows, to make the AUC-drop criteria evaluable.
- Widen the dry run to full tuning-seed range once M2/M3 compute budget is confirmed free.

## Background PIDs / output paths
- No long-running background processes left; the dry-run campaign was run to completion in the
  foreground. Outputs: `runs/dryrun_fleet/**`, `results/eval_fleet_dryrun/{report.md,report.csv}`.

## Resume command
The dry run used `run_campaign(..., n_rounds=4, n_nodes=3)`, which `scripts/run_campaign.py`'s CLI
does not yet expose (only `campaign.run_campaign`'s Python API takes them) -- call it directly:
```
python -c "
from fedqpnt.eval.campaign import run_campaign
run_campaign(['S5','S8','S9','S12','S15'], seeds=[500,501], methods=['fedqpnt','baseline_b_cont'],
             run_root='runs/dryrun_fleet', duration_s=120.0, n_rounds=4, n_nodes=3, n_workers=1)
"
```
(Already complete and skip-on-resume for this exact command; re-running just reports
`skipped_done` for all 20.) A CLI `--n-rounds`/`--n-nodes` flag pair would be a small, safe follow-up
to `scripts/run_campaign.py` if Master wants fleet dry-runs driven from the CLI.
