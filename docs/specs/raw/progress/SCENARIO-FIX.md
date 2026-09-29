# SCENARIO-FIX checkpoint (Sonnet), D-068
Tasks 1-5: DONE (pending full-suite confirmation + Master commit). Next: tasks 6-8 after commit.
Files: eval/seed_gate.py (new), campaign.py, fleet_adapter.py, metrics.py, report.py, scenarios.py; tests/test_eval_seed_gate.py, tests/test_eval_d068.py, test_eval_campaign.py (stub signature).
Proposals for Master (outside my edit scope):
 P1 node/runner.run_single and fleet/orchestrator.run_fleet: call seed gate (move eval/seed_gate.py to core/, or import lazily) -- I enforce in _execute_one/_execute_one_fleet/run_fleet_task only.
 P2 node/runner metrics: emit detected_on (M.detection_outcome), window_s, t_det, full cov via M.anees_pos with (N,3,3) cov (currently diag logged), and 1 Hz offset series (t, injected_offset_m) for latency_eff. Until then detected_from_record falls back to latency < attack.duration_s - 0.05.
Task 6-8 notes: sigma_nom read via metrics.load_sigma_nom (results/sigma_nom.json, absent -> loud error).
