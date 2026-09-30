# SCENARIO-FIX checkpoint (Sonnet), D-068

## Status
- Tasks 1-5: DONE, committed by Master (352c920).
- Tasks 6-8: DONE in eval/* + tests EXCEPT S6 (awaiting Master ruling on the proposal below) and everything needing
  runner/environment/core edits (P1-P3, windows to be opened by Master). Not committed.
- Files (this batch): eval/scenarios.py, eval/report.py, eval/campaign.py, eval/fleet_adapter.py, eval/metrics.py;
  tests/test_eval_scenarios_d068.py (new).

## Done in tasks 6-8
- 6 latency_eff: metrics.latency_eff / latency_eff_from_record (t_eff = first attack-window epoch with truth-side
  injected offset > 3 sigma_nom; misses censored t_off - t_eff; never-effective excluded, applied per pair in
  report._latency_eff_pair). sigma_nom read ONLY from results/sigma_nom.json (metrics.load_sigma_nom, loud
  FileNotFoundError; report turns it into "unevaluable = not rejected" with the message in the table). Offset
  channel = epoch.meta["injected_offset_m"] (Master msg); the eval side consumes record fields offset_t_s/offset_m.
- 7 confirmatory family (report.py): 8 ConfTest entries, FAMILY_M = 8 asserted, Holm at fixed m (unevaluable p=1,
  reject False). H2/H4 read results/fleet/h2_abrupt.json via load_h2_block (schema documented, TODO: format not final);
  onset latency censored at 60 s there. S8 methods now ("fedqpnt","baseline_b_cont").
  H3 tests are unevaluable while S6 is blocked_by_D047 or sigma_nom is unfrozen (counted as not rejected).
- 8 registry vs intent (scenarios.py): S2 gets damage_never_worse (frozen sigma_nom per grade, replaces the assumed 5 m)
  on all severities; S1 gets TV_w <= 1/h; S3 criterion implemented (t_dist <= 3 s all runs, consistency >= 95% each run,
  no update while jammed; still blocked_by_D047 => reported BLOCKED); S4 = jam(60-100 s)+drift-spoof(100-300 s) via
  Scenario.attacks, criteria S3+S2 legs+reacq cap (w_gnss <= 0.5 in 100% runs); S7 = 5 toggle variants S7-p{2,5,10,20,60}
  (abrupt_spoof segments, 50% duty; NOTE the old params.toggle_period_s was NOT a constructor argument of any attack, so
  the old S7 could not have run); S10 = rate grid S10-r{1,2,5,10} + cross-rate monotone check (lower-CI rule);
  S11 = noise_scale spec, no attack (intent has none; registry had an abrupt spoof); S12 = S12-f20 / S12-f40 sign_flip
  (f40 reported only); S14 criteria implemented (hour ratio, SPD, FAR, RSS); S15 attacked-node P_D leg added;
  S2-DM displaced meaconer registered (P_D + never-worse only, no halving claim); abl_minus_quantum method alias
  (= fedqpnt_local, quantum_grade None); IMU grade dimension: generate_tasks(imu_grades=[...]) -> result id "<sid>@<grade>".
  New helpers: SC.variants_of(family), SC.METHOD_ALIASES, Scenario.{base_id,gnss_rate_hz,attacks,noise_scale,poison_frac,group}.

## S6 PROPOSAL (Master to rule BEFORE I code it; currently S6 is left as registered = wrong)
Problem with the current S6: it is a GNSS drift_spoof (not a CAI fault) with no -quantum arm, so it cannot answer either
the ARCH S6 row or H3. Two facts: (a) ARCH S6 row (CAI *bias drift*, w_q < 0.5 within 10 cycles) needs a CAI-fault
injector that does not exist anywhere (sensors/quantum has no fault mode; attacks/ is GNSS-only) => narrow in paper
unless an injector is added (proposal below, optional); (b) H3 is defined in ARCH 6.2 as latency_eff for GRADUAL
spoofing, FedQPNT(CAI) < -quantum. So S6 should be re-registered as the H3 scenario.
Proposed exact definition:
  S6 = "CAI benefit under gradual spoofing (Schuler world)"
    world = schuler_tangent; duration 1500 s; cai_grade = field
    attack = drift_spoof, onset 300 s, duration 900 s, severity 0.3 (slow carry-off, the regime where the inertial/CAI
             coast quality limits how early the innovation becomes inconsistent -- the D-063 diagnosis (2): on MEMS, 180 s of
             inertial coasting is as bad as following the spoof; D-065: CAI cuts max coasting error 2.1-3.4x)
    arms   = fedqpnt_local, abl_minus_quantum (same node, quantum_grade=None), undefended (safety leg)
    grades = industrial_mems, tactical (result ids S6@industrial_mems, S6@tactical)
    primary (H3) = paired latency_eff, fedqpnt_local vs abl_minus_quantum, per grade (2 of the 8 confirmatory tests)
    secondary/criteria = never-worse (mean MAX_h(att) defended <= undefended + 3 sigma_nom, per grade); P_D reported.
  Reasoning: latency_eff isolates detection latency from the physically undetectable early phase; low severity keeps
  offset < the coast error for a long time so the CAI-aided predicted trajectory is what discriminates spoof from truth.
  Companion exploratory scenario S6-coast (NOT confirmatory): 180 s forced GNSS outage (jam_wideband, onset 600 s) with/without CAI,
  metric = max err_h during the outage (the D-065 coasting envelope, ratio reported), same arms and grades. Blocked by D-047 like S3.
  Severity/duration are my choices before any test data (labelled defined after tuning data); if you prefer S2-med's
  severity (0.6) tell me. The ARCH-literal "CAI bias drift" (w_q<0.5) leg = "narrow in paper" unless you approve a
  CAI-fault injector (sensors/quantum.py: add-on bias ramp, then eval reads w_quantum time-to-<0.5 in cycles).

## Runner/environment/core proposals (P1-P3; NOT applied: node/, fleet/, environment are in other agents' scope)
P1 (approved) seed gate at the lowest level:
   - git mv fedqpnt/eval/seed_gate.py fedqpnt/core/seed_gate.py; keep fedqpnt/eval/seed_gate.py as `from fedqpnt.core.seed_gate import *`
     (eval/campaign.py and fleet_adapter import eval.seed_gate -- unchanged).
   - node/runner.py, first line of run_single(spec):
         from fedqpnt.core.seed_gate import enforce_seed
         enforce_seed(spec.master_seed, final=spec.final)        # add RunSpec field: final: bool = False
     and campaign passes final=... into the spec ONLY when True (build_spec_dict(final=...)); test seeds then need final + open gate file.
   - fleet/orchestrator.py, first line of run_fleet(): enforce_seed(scenario.seed, final=getattr(scenario, "final", False)).
     (fleet local-training seeds 100000+scenario.seed*100+.. are FLEET_DERIVED and pass; their parent seed is gated.)
P2 (approved) runner outputs, node/runner.py run_single (all additive):
   - rows_cov.append(atick.nav.cov_pos.copy())   # (3,3) instead of np.diag(...); cov = np.array(rows_cov) (N,3,3)
     M.anees_pos(pos_est, pos_true, cov, phases.pre) / (..., cov)   (metrics.anees_pos already takes (N,3,3))
   - out = M.detection_outcome(t_arr, detected, phases); result.update(detected_on=out["detected"], window_s=out["window_s"],
     t_det=out["t_det"], t_on_s=phases.t_on, t_off_s=phases.t_off); keep latency_on=out["latency_on"].
   - offset channel: add to EnvTick a field `injected_offset_m: float = 0.0` (environment.py, MEACON scope), set in
     NodeEnvironment.tick from `epoch.meta.get("injected_offset_m", 0.0)` on GNSS epochs BEFORE for_agent(); runner appends
     (t, tick.injected_offset_m) at GNSS-epoch ticks -> result.update(offset_t_s=[...], offset_m=[...]) (1 Hz lists).
   - fleet/node_runner.py: same detected_on/window_s/t_det/t_on_s/t_off_s additions so H4/S15 per-node records carry the flag.
P3 (new) fields for scenario legs (metrics.py functions already exist: consistency_fraction, window_rmse):
   - RunSpec.attacks: list[dict]|None; runner: attacks = spec.attacks or ([spec.attack] if spec.attack else []) in EnvConfig
     (S4, S7 need it; eval emits spec["attacks"] only when the scenario has a schedule).
   - RunSpec.noise_scale: dict|None {"imu":10,"gnss":5,"cai_contrast_div":3} applied to the ENVIRONMENT sensors only (filter not told)
     (S11). RunSpec.quantum_cycle_time_s + tick jitter for the T_c axis of S10 (else "narrow in paper": only the GNSS-rate axis).
   - result fields: frac_e_le_3sigma_att = M.consistency_fraction(e_h, cov, phases.att); n_gnss_accepted_jammed (agent counter);
     w_gnss_reacq_max (max w_gnss in the 10 s after the jam ends, S4); p_spd_finite (all P eigenvalues > 0 & finite, every epoch);
     rmse_h_gnss_raw_pre (RMSE_h of raw GNSS fixes vs truth in P_pre, S11); rmse_h_hour_first/last = M.window_rmse(t,e_h,...)
     (S14); rss_growth_frac (psutil RSS hour1->end/hour1, S14).
   Until these land, the corresponding legs return passed=None ("not evaluable"), never a guessed value.

## Where the intent is infeasible / narrow in paper
- ARCH S6 CAI-bias-drift w_q leg (no CAI fault injector) -- see S6 proposal.
- S7 "detector noise near threshold" variation; S10 T_c axis and tick jitter (until P3); S12 other 3 poisoning types (covered by
  scripts/run_fl_s12_full.py outside the campaign); S15 attacked-node damage legs (no undefended fleet arm); S4/S3 numbers are
  computed on the UNION attack window (jam+spoof phases merge in compute_phases).
- Observation: fleet references fedqpnt_clean / fedqpnt_nofault / fedqpnt_noloss are read by S5/S9/S12 criteria but are not in
  fleet_adapter._METHOD_MAP, so those AUC-drop legs are unevaluable until added (not fixed: outside the D-068 list).
- S5 N=5 rounding gives 40% (documented as-is, D-068). S7 bound still 3600/26.1 = 137.9 (D-068: re-derive at the freeze).

## D-070 update (Master rulings applied, not committed)
- S6 re-registered as the H3 scenario exactly as proposed (rationale + "parameters fixed before test data" in Scenario.notes); S6-coast added EXPLORATORY (not in Holm family).
- CAI fault injector NOT approved: ARCH "CAI bias drift" w_q leg narrowed in the paper.
- fleet_adapter._METHOD_MAP += fedqpnt_clean (no poison/attacks), fedqpnt_nofault (no failure_round/delay_window),
  fedqpnt_noloss (lossless comms on both legs, D-059); S5/S9/S12 method lists include them so the AUC-drop legs are evaluable.
- P1-P3 still queued for the "runner window open" message.

## Runner window (P1-P3) APPLIED (not committed)
Files: core/seed_gate.py (git mv from eval; eval/seed_gate.py re-exports), node/runner.py, node/environment.py, fleet/orchestrator.py,
fleet/node_runner.py, eval/{campaign,fleet_adapter,scenarios,report}.py; tests/test_runner_d068.py (+ S10 test updated).
- P1: enforce_seed at top of run_single (RunSpec.final) and run_fleet (FleetScenarioConfig.final); campaign/fleet_adapter thread `final`.
- P2: run_single adds detected_on, window_s, t_det, t_on_s, t_off_s, offset_t_s/offset_m (EnvTick.injected_offset_m from
  epoch.meta before for_agent()), anees_pos_{pre,all}_full (full 3x3), fleet node_runner adds the detection keys.
  ANEES: old keys anees_pos_pre/all (diag) kept bit-identical; eval criteria (S1, S10) prefer the *_full keys.
- P3: RunSpec.attacks (S4/S7), noise_scale {imu,gnss,cai_contrast_div} (environment-side; imu.config() untouched = filter not told;
  GNSS/CAI as extra white noise sqrt(k^2-1)*sigma from a dedicated RNG stream), quantum_cycle_time_s (agent's ASSUMED cycle -> S10 T_c axis;
  S10 is now rate x T_c = 16 variants, default-T_c cells S10-r{r}); result fields frac_e_le_3sigma_att, p_spd_finite (position 3x3 block only),
  rmse_h_gnss_raw_pre, w_gnss_reacq_max (only if jamming), rmse_h_hour_first/last (only if span >= 2 h).
- NOT implemented (narrow in paper / unevaluable): S10 +-1 tick jitter; n_gnss_accepted_jammed (no filter-side counter without fusion/ edit);
  rss_growth_frac (psutil not installed); p_spd_finite covers only the position covariance block exposed in NavSolution.
- Golden check: 3 seeded run_single specs (drift_spoof/MEMS/120 s, abrupt/tactical/no-CAI/90 s, nominal 80 s) captured before edits;
  after edits all 31 pre-existing result keys have identical repr in all three (wall_s excluded).
