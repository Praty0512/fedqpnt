# CAMPAIGN (M4) checkpoint
- Pre-launch: `git diff core-freeze-4 HEAD -- fedqpnt` EMPTY; fedqpnt/ status clean. Gate D-080 cleared.
- Manifest: results/m4/manifest.json (5340 tasks = 4980 single-node [166 result ids x30 seeds... 2 grades] + 360 fleet: S5 90, S8, S9, S12-f20, S12-f40, S15). All single-node tasks carry v3 weights, seeds 10000-10029.
- Orchestration script (new, no fedqpnt edit): scripts/m4_campaign.py (run_campaign does not accept detector_weights_path, so it calls generate_tasks + _execute_one directly; resumable via _is_done; <=4 workers). Launch wrapper results/m4/launch_phase1.cmd.
- Launch 0 (00:56) crashed instantly (missing __main__ guard on Windows spawn); 0 runs executed; log kept as results/m4/phase1_launch0_noguard.log. Fixed guard.
- Launch 1: 00:58:53, detached via cmd Start-Process, 4 workers, log results/m4/phase1.log. Store: results/m4/<sid@grade>/<method>/seed_N.json.
- Note: my attempt to enumerate/kill stray python processes was denied by classifier (not retried); PIDs not recorded.
- Resume: rerun `results\m4\launch_phase1.cmd`. Phase 2 (fleet): `python scripts/m4_campaign.py --phase 2` only after Master says "H2 done".
- 01:02 progress ~12 runs, ~45-50 s/run/worker (S1) => ~5 runs/min, est. >=15 h for 4980 (other scenarios may differ). Handing back to Master with detached job running.
