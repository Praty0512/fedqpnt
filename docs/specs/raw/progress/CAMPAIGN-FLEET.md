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

## D-059 FIX (applied, no longer a limitation)
Master ruled the earlier `n_rounds=0` mapping for `baseline_b_cont`/`baseline_b_bin` a BLOCKING bug
(frozen theta0, not "local training without federation" -- node_runner only calls
`client.local_round` from inside `_do_fl_round`, so 0 rounds meant 0 local training too). Fixed
WITHOUT touching `fedqpnt/fleet/node_runner.py`:
- `fedqpnt/eval/fleet_adapter.py`: `_METHOD_MAP` now carries a `local_only: bool` flag instead of an
  `n_rounds` override; local-only methods keep the SAME `n_rounds`/`round_period_s` as `fedqpnt`.
  New `_run_local_only_fleet(cfg, theta0, param_names, join_timeout_s)`: for each node in
  `cfg.node_ids`, builds its OWN 1-node `FleetScenarioConfig` (`node_ids=[node]`,
  `aggregator="fedavg"` -- with N=1 this IS local training, no trimming/clipping reference exists),
  carrying over that node's own fault-injection kwargs (join_round/failure_round/delay_window/
  poison_kind/attacks/local_train_seeds), runs all N sub-federations in parallel
  (`ThreadPoolExecutor`, capped at `MAX_LOCAL_ONLY_PARALLEL=8`), then merges the N independent
  `FleetResult`s into one fleet-shaped result (same schema `write_campaign_result` expects).
  An `assert` inside the merge enforces the no-cross-node-leak invariant per sub-result.
  `run_fleet_task` branches on `is_local_only(method)` to call this instead of `run_fleet`.
- New `tests/test_fleet_adapter.py` (2 tests, real multiprocessing, ~5-10s each):
  `test_local_only_no_update_leaves_its_1node_federation` (merge produces exactly the requested node
  ids, nothing leaked) and `test_local_only_detector_hash_changes_across_rounds` (asserts
  `hash_pre != hash_post_train` for at least one round -- the direct regression check for the D-059
  bug -- plus `round_installs >= 1` with comms loss zeroed out on both the node uplink AND the
  server's OWN downlink config (`ServerConfig.comms`, a separate knob from
  `FleetScenarioConfig.comms_cfg` -- tripped me up once, noted in the test file).
- Verified on a real run: S8 seed 500 `baseline_b_cont`, per-node provenance now shows `hash_pre !=
  hash_post_train` on 2-4 of 4 rounds per node (previously 0/4, frozen) and
  `mean(round_installs)=1.33/4` (previously 0/4 always).
- Re-ran the S8 + S15 dry-runs for `{fedqpnt, baseline_b_cont}` (seeds 500-501, N=3, 120s, 4 rounds):
  8/8 tasks `status="ok"`. `fedqpnt` results untouched (only `baseline_b_cont`'s old
  frozen-theta0 files were deleted and regenerated). Full report regenerated at
  `results/eval_fleet_dryrun/report.md` (still PLUMBING ONLY).
- `python -m pytest tests/test_eval_*.py tests/test_fleet_adapter.py -q`: **59 passed**.

## D-059 ADDENDUM (comms fairness, applied)
Master flagged a fairness defect: local-only sub-federations inherited the scenario's SIMULATED
comms loss/delay (`comms_cfg`/`ServerConfig.comms`), but a vehicle training locally has no network
and must never lose/delay its own update.
- `fedqpnt/eval/fleet_adapter.py`: `_run_local_only_fleet` now FORCES a lossless, zero-delay
  `CommsConfig` (`_LOSSLESS_COMMS`: `loss_g=loss_b=0.0`, `p_gb=0`/`p_bg=1` pinning the Gilbert-Elliott
  channel "good", `delay_sigma_ln=0` at `delay_mu_ln=log(1e-6)`) on BOTH the node uplink AND the
  server's own, separate downlink config, regardless of what the calling scenario's `comms_cfg`/
  `server_cfg` say -- S9's simulated faults now apply only to the federated arms.
- Added a documented, non-crashing note (not a runtime assert) at the merge loop: with comms fixed,
  the only reasons left for `round_installs < n_rounds - join_round` are scenario-scheduled
  (join/failure) OR `FLClient`'s pre-existing, legitimate SS4.2 `min_samples` heartbeat gate (a
  node's own accumulated local dataset not yet reaching `ClientConfig.min_samples=64` -- shared with
  the federated arms too, NOT a comms defect). A hard runtime assert of `round_installs==n_rounds`
  was deliberately NOT added to the library code: with the real default `min_samples=64` it would
  raise on every real campaign run whenever early rounds haven't accumulated enough data yet, which
  is correct, expected behaviour, not a bug.
- Two new tests in `tests/test_fleet_adapter.py` isolate the comms-fairness invariant with
  `ClientConfig(min_samples=1)` (removing the confound above) and assert it exactly:
  `test_local_only_installs_every_round_with_lossless_comms` (`round_installs == n_rounds` for every
  node) and `test_local_only_join_round_is_the_only_carve_out` (a cold-start node installs exactly
  `n_rounds - join_round`, the one legitimate carve-out). `python -m pytest tests/test_eval_*.py
  tests/test_fleet_adapter.py -q` -> **61 passed**.
- Re-ran the S8 seed-500 `baseline_b_cont` check (N=3, 120s, 4 rounds, real `min_samples=64`
  default): `round_installs` = 2/4 for every node (was 1.33/4 mean before this addendum). Per-node
  detail: veteran nodes (node0/node1) install rounds 2-3 only (rounds 0-1 have 30/60 cumulative
  local samples, below the real `min_samples=64` heartbeat -- NOT comms, confirmed by
  `n_local_samples` in provenance); the cold-start node (node2, `join_round=2`) installs both of its
  2 attempted rounds (2-3) -- exactly the fairness invariant (comms no longer drops or delays
  anything; only real data-availability and join scheduling limit installs now).

## Known limitation (unchanged, out of my owned scope)
- AUC-drop criteria (S5/S9/S12) still need "no-fault"/"no-loss"/"clean" reference arms that the
  plumbing dry-run does not execute (kept minimal per the task's exact method list); they report
  `passed=None` until those reference runs exist.

## Next
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
