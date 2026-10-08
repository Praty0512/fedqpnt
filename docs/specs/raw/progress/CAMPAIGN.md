# CAMPAIGN (M4) checkpoint
- Pre-launch: `git diff core-freeze-4 HEAD -- fedqpnt` EMPTY; fedqpnt/ status clean. Gate D-080 cleared.
- Manifest: results/m4/manifest.json (5340 tasks = 4980 single-node [166 result ids x30 seeds... 2 grades] + 360 fleet: S5 90, S8, S9, S12-f20, S12-f40, S15). All single-node tasks carry v3 weights, seeds 10000-10029.
- Orchestration script (new, no fedqpnt edit): scripts/m4_campaign.py (run_campaign does not accept detector_weights_path, so it calls generate_tasks + _execute_one directly; resumable via _is_done; <=4 workers). Launch wrapper results/m4/launch_phase1.cmd.
- Launch 0 (00:56) crashed instantly (missing __main__ guard on Windows spawn); 0 runs executed; log kept as results/m4/phase1_launch0_noguard.log. Fixed guard.
- Launch 1: 00:58:53, detached via cmd Start-Process, 4 workers, log results/m4/phase1.log. Store: results/m4/<sid@grade>/<method>/seed_N.json.
- Note: my attempt to enumerate/kill stray python processes was denied by classifier (not retried); PIDs not recorded.
- Resume: rerun `results\m4\launch_phase1.cmd`. Phase 2 (fleet): `python scripts/m4_campaign.py --phase 2` only after Master says "H2 done".
- 01:02 progress ~12 runs, ~45-50 s/run/worker (S1) => ~5 runs/min, est. >=15 h for 4980 (other scenarios may differ). Handing back to Master with detached job running.
- 10:35 Phase 1: S7-p2/p5 (240) failed with WinError 206. Added scripts/m4_run_spec_file.py + `--phase 1b` (spec via temp file, launcher="spec_file"), verified on 1 task (S7-p2@industrial_mems/fedqpnt_local/seed_10000 ok, 1155 s). Launched 1b detached, 2 workers: results/m4/launch_phase1b.cmd, log phase1b.log.
- 10:23 Phase 2 launched detached (1 fleet at a time): results/m4/launch_phase2.cmd, log phase2.log. `--reverse` option available (second instance NOT started).
- Claim files (`<result>.claim`, O_CREAT|O_EXCL, removed on completion) added to phase 1b and phase 2 in scripts/m4_campaign.py (+ `--clear-claims` to wipe stale claims after a crash; a crashed instance leaves its claim, so resume with --clear-claims only when no other instance is live). Already-running instances (old code) do not use claims.
- Autoscale waiter: scripts/m4_autoscale.sh via results/m4/launch_autoscale.cmd, log results/m4/autoscale.log: on phase1.log "DONE" -> 1b --reverse (2 workers, log phase1b_rev.log); then phase 2 --reverse if free RAM >= 3.5 GB (recheck every 10 min x13; log phase2_rev.log).

## Round 2 PREPARED (2026-10-08) - NOT launched; waiting for "round 2 go"
- scripts/m4_campaign.py rewritten (args --phase 1|2, --dry, --seeds 10030-10059, --weights REQUIRED, --root results/m4r2, --workers, --reverse, --clear-claims). Preflight: git diff core-freeze-5 HEAD -- fedqpnt empty + clean tree; manifest asserts (weights on every single-node task, seeds in range/contiguous, no duplicates, final, kappa 60/1).
- Phase 1: long specs (>30,000 chars; S7-p2/p5, 240 tasks) auto-use scripts/m4_run_spec_file.py with 7200 s timeout and run first; others via campaign._execute_one (3600 s). Claims for every task in both phases.
- Launchers in results/m4r2/: launch_all.cmd <weights> (starts phase1 x4 workers, phase2 x1 fleet, autoscale waiter, detached), launch_phase1/2/2_rev/autoscale.cmd; waiter scripts/m4r2_autoscale.sh (on phase1 DONE -> phase2 --reverse if free RAM >= 3.5 GB, recheck 10 min x13).
- Dry-run manifest results/m4r2/manifest.json (placeholder weights): 5340 tasks = 4980 single (240 long-spec) + 360 fleet. Round-1 files in results/m4 untouched.
- OPEN QUESTION for Master: fleet tasks use fleet_adapter.THETA0_PATH (results/fleet/theta0_d054.npz), not --weights.
- 2026-10-08: results/m4/ROUND1_STATUS.json written (5340 expected / 3602 done / 28 failed records / 1710 missing). Phase-2 preflight assertion for results/fleet/theta0_d054_freeze5_provenance.json added. Waiting for 'round 2 go'.
