# FedQPNT — Decision Log

Format: ID · date · decision · rationale · alternatives considered · owner.

---

### D-001 · 2026-09-23 · Pure high-fidelity software simulation
- **Decision:** All sensing, attacks, fusion and FL run as a scientifically grounded Python simulation.
- **Rationale:** No quantum hardware or GNSS RF front-end available (proposal §7).
- **Alternatives:** GNSS SDR record/replay (gnss-sdr + recorded IQ) — rejected for now (no hardware, legal constraints on RF spoofing); may be reconsidered for a validation appendix using public spoofing datasets (e.g. TEXBAT) if they are accessible.
- **Owner:** Master

### D-002 · 2026-09-23 · Scientific integrity rule for results
- **Decision:** Results are reported exactly as measured. Baselines get the same tuning budget, same seeds, same scenarios, same fusion core as FedQPNT. No scenario may be dropped after results are seen; any exclusion is logged here with a reason. Every model parameter must cite a published source or be labelled "ASSUMPTION" with a sensitivity sweep.
- **Rationale:** The paper's claim ("beats both baselines") must survive reviewers. A simulation tuned to win is worthless as evidence.
- **Alternatives:** None acceptable.
- **Owner:** Master

### D-003 · 2026-09-23 · Frames, time, units
- **Decision:** Local-level ENU navigation frame (m), origin `ORIGIN_LLH`; satellites computed in ECEF then projected to ENU. Body frame FLU; ZYX Euler roll/pitch/yaw. Single global sim clock, base tick 0.01 s (100 Hz).
- **Rationale:** Missions span tens of km (vehicle/UAV); flat local frame keeps the fusion filter simple while ECEF satellite geometry keeps GNSS DOP and spoofing geometry realistic.
- **Alternatives:** Full ECEF/NED strapdown with Earth-rate and transport-rate — deferred; ARCHITECT to judge whether Earth-rate matters for the cold-atom bias levels (it may, since CAI bias is ~µg-level).
- **Owner:** Master

### D-004 · 2026-09-23 · GNSS modelled at the raw-observable (pseudorange / Doppler / C/N0 / AGC) level
- **Decision:** Attacks operate on `GnssEpoch` (per-satellite pseudorange, pseudorange-rate, C/N0, lock state, AGC/noise floor), then a receiver computes PVT + RAIM statistic.
- **Rationale:** Published spoofing/jamming signatures (Radoš 2024; Borhani-Darian 2024) are defined in terms of these observables (C/N0 jumps, AGC rise, code-phase/Doppler drag-off, clock-bias jumps). A position-level "add an offset" model would be unconvincing to reviewers.
- **Alternatives:** Position-level offset injection (too crude); IF-sample-level signal simulation (too expensive for multi-hour, multi-node runs).
- **Owner:** Master

### D-005 · 2026-09-23 · Hierarchical deterministic RNG streams
- **Decision:** `fedqpnt.core.seeding.stream(master_seed, node_id, component)` gives each component an independent, reproducible `np.random.Generator`.
- **Rationale:** Adding/removing a component (e.g. an ablation) must not change the noise realization of other components; enables paired statistical tests across methods.
- **Owner:** Master

### D-045 · 2026-09-27 · Git policy; paper on hold; paper tier = Sonnet
- **Git:** repository on `master`, initial commit `2da7fa0`. The Master commits after each accepted work package or milestone sign-off, with a message citing the D-/EXECUTION_LOG IDs and the co-author trailer. Agents stage but never commit. No pushes (no remote configured; outward-facing, so requires explicit user approval).
- **Excluded from git:** `data/raw/` (the 875 MB CC-BY archive; MD5 in the log), `runs/`, and caches. Derived `data/processed/` (8 MB) and `results/` (2 MB) are included for reproducibility.
- **Paper:** ON HOLD (user). When resumed, writing = Sonnet (resolves D-007).
- **Owner:** Master (user directives)

### D-043 · 2026-09-27 · FILTER-GNSS results: receiver cov_vel honest; D-036 excess = `_hygiene` additive floor (Master-proven)
- **Task 1a:** receiver cov_vel is HONEST. Reported/actual ratio [0.975, 1.010, 1.001] (E/N/U); normalized error² mean 3.03 vs χ²₃ 3.0; lag-1 s autocorrelation ≈ 0. **Master's D-038 prime suspect is refuted.**
- **Task 3 → Master root cause:**
  - The single-source excess persists with P0 = 0 in all other blocks (4.507 vs 3.000 at 300 s). Master reproduced it and showed that a pure-numpy recursion with identical F/Φ gives exactly 3.000/450.000, while the ESKF grows P_ψ to 6e-6 with all noise zero.
  - **Cause: `ESKF._hygiene()` adds 1e-12·I to the whole P whenever min eig < 1e-12.** In this degenerate test that fires continually, puts ≈1e-10 into P_bg, and propagates b_g → ψ (t²) → v through gravity (t⁴).
  - With the floor disabled (symmetrisation only) the ESKF matches the exact answer (3.0000 / 450.000).
  - The agent's earlier dismissal ("13 orders too small") ignored this t⁴ amplification.
- **Relevance:**
  - The floor can only *inflate* P, so it cannot explain the GNSS-aided *over*confidence.
  - It is still a latent defect: whenever P becomes near-singular (strongly correlated states after GNSS updates), it injects un-modelled noise at 1e-12 per step, which is ≈ 3× the real per-step gyro-bias process noise (q_bg·dt ≈ 3.4e-13).
  - **Decision:** replace the additive floor with an eigenvalue clip, P = V·max(Λ, 0)·Vᵀ applied only when min eig < 0, i.e. only negative eigenvalues are corrected. Apply after the D-038 analysis concludes, with a regression test (the single-source case must be exact).
- **Still open:** the cause of GNSS-aided overconfidence (κ_R = 1 → ANEES 23.6). Receiver pos and vel covariances are both honest and correlated GNSS errors are ruled out, so the remaining suspects are in the ESKF update itself (Joseph form/numerics, time alignment of fix vs propagate, the joint 6-D innovation ignoring the pos–vel cross-covariance of the fix). Awaiting task 1b / task 2 results.
- **Owner:** Master

### D-042 · 2026-09-27 · Baseline-paper behaviour confirmed via Consensus abstracts; new related work
- **Confirmed (Consensus, full abstracts):**
  - Khan 2025 = FL (SVM at an RSU) *detection only*, no post-detection navigation action. The Table II "Not stated (detection only)" cell is correct; Baseline A stays a class representative.
  - Chai 2025 = TCN-Transformer + accuracy-weighted FL aggregation, *detection only*.
  - Pardhasaradhi 2022 = after detection, the fused radar-track state replaces GPS as the control input (binary switch), which is **exactly B-bin**.
- **Also verified via Consensus:** Holm 1979 (Scand. J. Statist.), Demšar 2006 (JMLR 7), Blanchard 2017 Krum (NeurIPS).
- **New related work to verify (DOIs) and add in the next paper pass:**
  - Akram et al. 2026, FL GPS-spoofing IDS for consumer AVs (IEEE TCE);
  - Chen et al. 2025, LSTM detection + camera/map UKF fallback (IEEE TVT);
  - Wang et al. 2025, V2V detection + cooperative localisation (IEEE IoT J.);
  - Jung et al. 2024, PX4 innovation-test-evading spoofing (IEEE Access), which supports our RAIM-blind attack realism;
  - Deng et al. 2024, FL interference classification on TEXBAT (VTC-Fall).
  Chen 2025 and Wang 2025 are detect-then-switch systems, strengthening the B-bin class.
- **Consensus quota:** 1 search left until 1 Oct, reserved.
- **Owner:** Master

### D-041 · 2026-09-27 · Method-reference bibliography (REF-VERIFY-2) accepted, with verification tiers
- **Master-verified (20 of 29):**
  - 12 DOIs resolved on Crossref with titles matching: FLTrust, Page 1954, Wilcoxon 1945, IEEE Std 952, Lautier 2014, Cheiney 2018, Templier 2022, Geiger 2020, Bidel 2018, Klobuchar 1987, Saastamoinen 1972 (cite as 1972; Crossref lists a 2013 registration date), Parkinson & Axelrad 1988.
  - 8 arXiv IDs resolved via DataCite 10.48550: FedAvg, FedProx, Yin 2018, Sun 2019, ALIE (Baruch 2019), FedAsync, Solà 2017, Wang 2021.
- **Agent-verified only (catalogue check before submission):**
  - 5 book ISBNs: Anderson & Moore, Bar-Shalom, Groves, Kaplan & Hegarty 978-1-63081-058-0, Misra & Enge 978-0-9709544-0-4. OpenLibrary lookups failed for all five (a likely access issue, not evidence against them).
  - Krum (NeurIPS 2017, proceedings URL only).
  - 3 entries with no identifier: Holm 1979, Demšar 2006 (JMLR), TEXBAT 2012 (ION). Add stable URLs.
- **Agent report inconsistency:** it said "27 verified" but the file has 29 entries. The file content is what counts.
- **Next:** merge `docs/specs/raw/refs_methods.bib` into `paper/refs.bib` and add the entries to `docs/REFERENCES.md`, with the tier noted per entry. Mechanical work, for the next PAPER or DOCUMENTATION pass (Haiku for REFERENCES.md).
- **Owner:** Master

### D-040 · 2026-09-27 · Resume with concurrency cap 3; parallelise unblocked work
- **Decision (user directive):** max 3 concurrent agents (supersedes D-016's cap of 2); continue all work not blocked by the open ESKF/GNSS-aided consistency issue.
- **Launched:**
  - FILTER-GNSS (Sonnet): D-038 items 1–3, with receiver cov_vel honesty the prime suspect.
  - FEDERATED (Sonnet, resumed): D-039, i.e. the balance-rule dead-zone fix plus S12 at N = 10.
  - PAPER (Sonnet): skeleton, full Related Work, System/Threat model, claim→evidence map. It must cite only the verified bibliography and states no results.
- **Still blocked on the filter:** κ_R re-tune, detector retrain on real features, M1 smoke/sign-off, runtime optimisation (touches eskf/receiver).
- **Paper tier:** Sonnet per the Master's earlier recommendation (D-007 open point). The user was informed and may override to Haiku.
- **Owner:** Master (user directive)

### D-039 · 2026-09-27 · S12 root cause fixed; TRIM-NB-R criterion FAILS at N=5 (re-test at spec N); training dead-zone in the balance rule
- **Accepted** (Master re-ran 42/42):
  - The root cause of the identical f=20%/40% results was a harness data bug. Some nodes had zero negative samples, so the frozen class-balance rule (`max_pos = n_neg`) discarded every sample, giving a zero delta, and poisoning a zero delta is a no-op. Harness fix: round 0 is forced clean.
  - A regression test proves FedAvg moves further as f grows, and TRIM-NB-R moves less than FedAvg at every f.
  - Full sweep (4 poisoning types × f × 2 aggregators × 5 seeds, malicious count asserted): TRIM-NB-R is better than FedAvg in 7/8 cells.
  - S5 PASS (drop 0.019 ≤ 0.02); S9 PASS (drop −0.004 ≤ 0.03).
  - Process discipline clean: no kills, ≤ 6 processes, 0 left behind.
- **S12 acceptance (TRIM-NB-R, f = 20%): FAIL, mean drop 0.063 > 0.05**, driven by one seed (502: 0.219). Recorded as FAIL (D-002).
  - Master note: N = 5 was forced by the Master's own ≤ 6-process instruction, and at N = 5 one attacker is exactly β = 20%, the trimmed-mean breakdown edge, so this is not the spec's operating point.
  - **Decision:** re-run S12 at N = 10 (the spec fleet size), sequentially, when heavy simulations aren't running. The N = 5 FAIL stays in the record either way.
  - Also flagged: non-monotone gaussian/ALIE drops (f = 40% < f = 20%) at 5 seeds, i.e. small-sample noise; report CIs at N = 10.
- **New design issue (D-026 frozen rule):** the class-balance cap yields **zero training** when a node has no negative samples, so a node seeing only attacked data never learns. In real missions nodes mostly see clean data, but a node under sustained attack would silently stop contributing.
  - Decision on resume: when n_neg < a minimum, train on the available samples with loss weighting instead of dropping all of them.
  - This is a correctness fix, not a tuning change, so D-026's freeze permits it. It goes in the M2-integration work package.
- **Owner:** Master

### D-038 · 2026-09-27 · D-035 accepted; remaining inconsistency reframed (analysis only; project paused)
- **Accepted (D-035 random-walk bias fix):**
  - pure-INS b_a/b_g NEES ≈ 3.1–3.4 and ψ ≈ 2.6–3.5 at 300 s, both grades;
  - tactical fully consistent including v/p;
  - MEMS outage error: no CAI 103 → 86 m, CAI 214 → 107 m (CAI still ≈ 1.25× worse for MEMS);
  - tactical: CAI 7.0 → 3.3 m; perfect gyro: 131 → 9.6 m;
  - nominal GNSS-aided ANEES = 0.98 at κ_R = 40 but **23.6 at κ_R = 1**, so κ_R cannot drop (contrary to Master's expectation).
- **Master analysis (hypotheses to verify on resume):**
  1. **Pure-INS 300 s MEMS v/p NEES (48–135×) is likely a linearisation-validity artefact, not a bug.** The industrial gyro turn-on bias of 0.1°/s gives a tilt of ≈ 0.5 rad at 300 s, far outside the small-angle ESKF regime. Tactical (0.01°/s → 0.05 rad) stays consistent, and MEMS is ≈ 1.3× at 60 s (tilt ≈ 0.1 rad). Verify by logging the true tilt magnitude, and by repeating with the gyro turn-on σ scaled down 10× (NEES should become consistent). The paper states the MEMS free-inertial horizon limit explicitly.
  2. **D-036's "P too large by 50% at 300 s" is likely a diagnostic artefact:** non-zero default P0 in the ψ/b_g blocks adds g-coupled growth. Verify by zeroing all P0 blocks except the injected one.
  3. **The real open issue is GNSS-aided overconfidence** (κ_R = 1 gives ANEES 23.6; [ψ, b_a] NEES 852 at outage start). The receiver position cov is verified honest (3.42 vs 3.03 m), but **the receiver VELOCITY cov (cov_vel) honesty was never checked**. Prime suspect: an under-stated Doppler-velocity covariance, which would make velocity updates drive ψ/b_a overconfident. Test: actual fix-velocity error std vs reported σ_vel; then a separate κ_R for position vs velocity, or a velocity-only R check.
- **H3 status:** the CAI benefit holds for tactical and better gyros. For MEMS it stays ≈ 1.25× worse pending item 3; no H3 claim for MEMS until then.
- **Deferred queue on resume:** item 3 first, since it gates κ_R, the detector retrain and M1; then items 1 and 2 (cheap confirmations).
- **Owner:** Master

### D-037 · 2026-09-27 · M2 FL infrastructure accepted; S12 poisoning result invalid (deferred fix)
- **Accepted** (Master re-ran 41/41):
  - the multi-process FL stack (spawn + queues, bulk-synchronous in sim time, node_id-ordered aggregation);
  - FedAvg, FedProx and TRIM-NB-R; comms; cold start; the leakage guard;
  - determinism (bit-identical), and no deadlock in S5, S8 and S9; 0 honest quarantines in S15;
  - two real bugs found by the validation runs and fixed with regression tests: future-round messages dropped (cold-start deadlock), and the `(GlobalModel, delay)` tuple never installed (staleness blow-up).
  - PDs 1–3 accepted for v1: staleness in metrics; S5 delays as a NoUpdate window; FIFO buffer plus train-time balancing.
  - PDs 4–5 accepted: server-side simulation of gaussian/ALIE poisoning via `malicious_ids` that never go on the wire, and the closed-form ALIE z.
- **Rejected: the S12 result.** f = 40% gives results *identical to full precision* to f = 20% for BOTH TRIM-NB-R and **FedAvg**. A doubled sign-flip fraction must change a plain average, so the poisoning fraction is almost certainly not applied (the agent's "trim-slot" explanation cannot cover FedAvg). The tiny FedAvg drop at 20% (0.009) corroborates this. Also incomplete: only 1 of the 4 §4.5 poisoning types was run, and the S5/S9 AUC criteria were not reported.
- **Process incident:** the agent killed a `pytest tests/ -q` process (PID 32732) it had not started, contrary to its instruction. It was likely the CAI-H3 full-suite run; CAI-H3 later completed its full run (305/307), so there was no lasting harm. Future agents must verify process ownership (parent PID) before killing.
- **Deferred (project paused):** fix S12 (verify `malicious_ids` count scales with f; all 4 attack types; per-type drop for FedAvg vs TRIM-NB-R); report the S5/S9 AUC criteria.
- **Owner:** Master

### D-035 · 2026-09-26 · ROOT CAUSE: GM1 decay applied to a turn-on-dominated bias prior → bias states become random walks
- **Finding** (CAI-H3 agent, D-034; Master-verified analytically):
  - ARCHITECTURE §2.4 models the b_a/b_g error states as GM1 with F = −I/τ (τ = 200 s, industrial). The §2.9 prior P0 = σ_turn-on², and the turn-on bias is a per-run CONSTANT in the truth (and in reality).
  - The filter therefore decays its bias variance as e^(−2t/τ) toward the tiny GM1 stationary level (≈ 11× by 300 s: measured 5.28e-3 → 4.79e-4), while the true error stays flat (1.23e-2).
  - The overconfidence propagates into v and p via −C·δb_a and skew(f)·ψ. Under a "filter-model truth" (SF/misalignment/quantization off, diagnostic fixed), NEES at 300 s is v 392, p 67, b_a 65.
  - **This single spec defect explains** the MEMS inconsistency, the "CAI hurts MEMS" artefact (D-027/D-028), and plausibly the need for κ_R = 40 (D-023).
- **Decision:** b_a/b_g error states are **random walks** (F-block = 0) with q = 2σ_gm²/τ.
  - This over-bounds the GM1 part slightly (≈ 144σ_gm² over 4 h, negligible vs σ_turn-on²), keeps 15 states and adds no runtime.
  - The old GM1 behaviour is kept as an ablation switch.
  - Rejected: separate turn-on (constant) and GM1 sub-states. More exact, but 6 extra states and runtime cost for a negligible gain.
- **Re-validation:** pure-INS NEES, outage NEES, the CAI gyro sweep, nominal ANEES at κ_R 40 vs 1, and the full suite. κ_R is then re-tuned once (D-029 sequence).
- **Accountability:** a spec error by the Opus ARCHITECT. The Master ratified §2.4 in D-009 without catching it. A lesson for spec review: always check that each state's process model matches the nature of its prior (constant vs stationary).
- **Owner:** Master

### D-034 · 2026-09-26 · The inconsistency is intrinsic to the ESKF/pure-INS path; pinpoint the first divergence
- **D-032 results:**
  - **Arm (i) verified effective:** realised GNSS-error autocorrelation at 10 s is 0.75 → 0.02, yet the NEES is unchanged. **Master's caching suspicion was wrong.** Correlated GNSS error is definitively ruled out.
  - **Q parameter table clean:** no unit or σ/σ² error.
  - **Pure INS (no GNSS, no CAI, prior drawn from P0):** already inconsistent at 10 s (b_a NEES 8.3, v 8.0, both 3× ideal). At 300 s, industrial static: v 1740, p 311, b_a 151, b_g 157. Tactical is milder (b_a 43 at 300 s).
- **Master assessment:**
  - Rejected the agent's leading candidate (midpoint Qd discretisation): its error is O(dt²) per step at dt = 0.01 s, insufficient by orders of magnitude.
  - b_a NEES ≈ 3× ideal at 10 s in pure INS is incompatible with a consistent prior and a slowly varying bias. It points to (i) a diagnostic truth-definition or initial-draw mismatch, or (ii) extra at-rest bias terms in the truth IMU (e.g. misalignment × g, scale factor × g) that the filter does not model.
- **Decision:**
  - Localise with a t = 0 NEES check, a "filter-model truth" arm, and the earliest-divergence time per block against analytic static variance growth.
  - A fix is applied only after the culprit is named.
  - Paused until then: κ_R re-tune, detector retraining, M1 sign-off.
- **Owner:** Master

### D-033 · 2026-09-26 · User directive: no scope trimming; parallelise work that is independent of the ESKF bug
- **Decision:**
  - Full scope retained: both platforms, 30 seeds, all 15 scenarios, a Q1 journal target.
  - Work independent of the ESKF consistency investigation proceeds in parallel under the concurrency cap of 2 (D-016).
  - First: **M2 federation infrastructure**. It is independent because it exchanges detector parameters only; local data comes from the existing trust harness behind a swappable `local_dataset_provider`, and it does not touch fusion, node or trust internals.
  - Next in queue when a slot frees: the paper skeleton plus Related Work from the verified bibliography (Sonnet), and the architecture/workflow diagrams (Sonnet).
- **Owner:** Master (user directive)

### D-032 · 2026-09-26 · Correlated-GNSS result held pending verification; test process-noise consistency directly
- **D-031 result:**
  - Removing GNSS correlated errors (g) or also κ_R (h) does not restore consistency; (h) is worse.
  - The receiver covariance is honest (reported 3.42 vs actual 3.03 m).
  - Arm (i) (τ → 1 s, same σ) reproduced (a) to 3 significant figures in all six metrics. A realisation change of that size cannot plausibly give identical numbers, so Master suspects the τ patch was ineffective. Verification is required via the realised autocorrelation.
- **Reasoning:** an honest receiver covariance plus the need for κ_R = 40 implies the filter's *own* predicted covariance is too small, i.e. the process noise Q is under-stated. That matches tilt/b_a/b_g overconfidence and is invisible to all prior ablations, which changed the truth, not the filter's Q.
- **Test:**
  - a parameter-by-parameter table of truth IMU noise vs the ESKF Q entries (units, σ vs σ², GM PSD form);
  - a pure-INS consistency test (no GNSS, no CAI, true initial errors drawn from P0), block NEES at 10/60/300 s, 20 seeds, industrial_mems and tactical.
- **Owner:** Master

### D-031 · 2026-09-26 · IMU error sources ruled out; test correlated-GNSS-error hypothesis
- **D-030 result** (truth-side IMU ablation, industrial_mems, seeds 500–509): removing scale factor, misalignment, both, quantization/saturation, or matching the bias model changes nothing. Block NEES at t0: ψ roll/pitch 45 (ideal 2), yaw 2.9 (ideal 1), b_a 158 (ideal 3), b_g 12 (ideal 3); horizontal position at t0+60 is 19.5 (ideal 2). The mismatch sits in the gravity-coupled tilt and b_a, not in heading.
- **Hypothesis:** time-correlated GNSS errors (iono/tropo/multipath GM, τ 20–1800 s) processed as white loosely coupled fixes are interpreted by the filter as horizontal acceleration, and absorbed into tilt/b_a with overconfident covariance.
- **Test:** GNSS truth-side ablation (correlated errors off; κ_R 40 vs 1; τ shrunk to 1 s at the same σ) plus a check of the receiver's covariance honesty.
- **If confirmed, reconsider D-009's "no GNSS error state" rule:** a GM error state sized to the physical σ (a few m) would absorb at most a few metres of a slow spoof. That is ≪ the 50–600 m offsets of S2, so detection would be preserved while tilt/b_a consistency is restored. The Master decides after the evidence.
- **Owner:** Master

### D-030 · 2026-09-26 · D-028 Q inflation failed; localise the MEMS mismatch before adding states
- **Result:** the dynamics-dependent Q inflation had no measurable effect (NEES 1107 → 1107; CAI MEMS 213.9 → 213.9 m). **Master error:** D-028 permitted a correlation time equal to dt. A per-run-constant error cannot be represented by dt-white noise; the added variance is 4–70× below the baseline ARW/VRW. The agent correctly stopped instead of adding a free constant. The switch now defaults to off; the code is kept for ablation.
- **Master check:** ESKF P0 for b_a correctly uses the IMU `turn_on_bias_std` (industrial 0.098 m/s²), so the prior is not the bug. The outage-start b_a error (≈ 0.108 m/s²) shows b_a is barely observable from GNSS on this course. The inconsistency must sit mainly in the ψ block or its cross-terms.
- **Decision:** run a truth-side ablation first. Remove SF, misalignment, quantization/saturation, and bias-model mismatch one at a time in the *truth* IMU, and report block-wise NEES. Add SF/misalignment states (or another fix) only for the source the ablation identifies. Pending that, H3 claims are restricted to the tactical grade, where the filter is consistent.
- **Owner:** Master

### D-029 · 2026-09-26 · M1 smoke results: not signed off; detector retrained on real closed-loop features
- **Findings** (M1 smoke, tuning seeds 500–504, not for publication):
  1. **Baseline A diverges on NOMINAL** (68 km; mean w_gnss 0.10). The shared locally pretrained detector false-alarms on real closed-loop inputs. **Master rejects the agent's framing "consistent with H1"**: all methods share this detector, so this is a detector calibration failure, not evidence for FedQPNT (D-002).
  2. FedQPNT-local nominal RMSE_h is 3.81 m vs 2.81 m undefended (fails the S1 ≤ 1.05× criterion). Drift-spoof RMSE is about 108 m for every method (detection ineffective).
  3. Under CW jamming the defended methods are worse than undefended (FedQPNT 964 m, B-bin 1612 m vs 358 m). Partially jammed GNSS is still usable, so distrust forces MEMS coasting, which D-028's overconfidence makes worse. This is a real finding about the trust law; re-evaluate after D-028.
  4. Timing: meaconing gives a ≈ 1350 ns clock error for all methods. The pipeline and clock KF are cross-checked.
  5. κ_R = 40 re-derived independently (ANEES 0.981), but PROVISIONAL pending D-028.
- **Cause of 1–2:** the detector was trained on the synthetic, truth-derived harness (surrogate CUSUM, synthetic innovations), so real ESKF innovations and features have shifted distributions.
- **Decision (sequence, after D-028 lands):**
  1. Re-tune κ_R via `scripts/tune_kappa_r.py`.
  2. Retrain the FROZEN detector design (D-026, design unchanged) on REAL closed-loop features and real pseudo-labels (the CAI-aided INS reference from the actual Agent), seeds 500–599 only.
  3. Re-run the smoke matrix plus a clean-run FAR/h per method (S1).
  4. Only then consider M1 sign-off.
- **Accepted PDs:**
  - Agent-side split of the joint 6-D GNSS innovation into pos/vel for trust features.
  - The leakage guard exempts `fedqpnt.sim.rotations` (pure math).
  - The forbidden-name check is scoped to node, fusion and trust.
- **Owner:** Master

### D-028 · 2026-09-26 · CAI-H3 resolved as MEMS model mismatch → dynamics-dependent Q inflation
- **Evidence** (seeds 500–509, 60 s outage):
  - MEMS horizontal NEES at t0+60 is 19.5 (no CAI) and 46.8 (CAI) against an ideal of 2.
  - MEMS [ψ, b_a] NEES *at outage start* is 1107 / 497 against an ideal of 6.
  - Tactical stays near-consistent (horizontal NEES 0.3–2.2; [ψ, b_a] ≈ 65–68).
  - Since an optimal KF cannot worsen with added correct information, the "CAI hurts MEMS" result was an artefact of an overconfident, mismatched filter. The no-CAI "cancellation" exploited an inconsistent P. It is not estimation physics.
- **Likely cause:** per-run-constant, dynamics-coupled gyro/accel scale-factor and misalignment errors (MEMS 5e-4 / 3e-4, 3–5× tactical) exist in the truth IMU model but have no ESKF counterpart.
- **Decision:**
  - Add dynamics-dependent Q inflation per axis, (σ_sf·|ω_i|)² + (σ_mis·|ω_⊥|)², and the same for f. σ is taken **only** from the IMU config (the truth model's own values), with **no free tuning constant**. Switchable (`model_sf_mis`) for ablation. Applied identically for all methods.
  - Acceptance: MEMS horizontal NEES ≤ 2× ideal and [ψ, b_a] NEES ≤ 3× ideal for both grades.
  - Rejected alternative: augmenting the state with 6–12 SF/misalignment states. More faithful, but it adds substantial runtime (R-3). Revisit if the Q inflation fails acceptance.
- **Consequences:**
  - κ_R must be re-chosen after this change, using the same committed procedure.
  - Runtime optimisation stays queued behind the eskf.py edits.
  - The H3 claim is re-evaluated after the fix and reported whatever its sign.
- **Owner:** Master

### D-027 · 2026-09-26 · WP-4.x acceptance; κ_R policy; CAI-H3 investigation; timing clock KF
- **TRUST ACCEPTED, frozen design** {xsat rule on, balanced sampling}:
  - provisional AUC: overall 0.722 [.697, .749], drift 0.724, meaconing 0.575, abrupt 0.749, jamming 0.515 (chance level, reported as weak);
  - all jamming-active epochs are pseudo-labelled y=1 in every cell, so the labeller is not at fault.
- **FUSION ACCEPTED, with the outage metric fixed:**
  - the committed `scripts/fusion_outage.py` asserts zero GNSS innovations in the window;
  - tactical sanity check: measured 604 m vs 891–1248 m predicted;
  - MEMS no-CAI: 60 s mean 103 m, 300 s mean 3448 m;
  - the sweep ran 3/12 combos; completion is deferred until the runtime is optimised.
- **κ_R root cause:** time-correlated GNSS errors (GM τ = 20–1800 s) are treated as white. The architect's no-GNSS-error-state rule stays, because it prevents slow-spoof absorption. So κ_R is chosen once on seeds 500–599 for ANEES = 1 ± 0.1 and applied identically to all methods (§7.6). This is a documented limitation in the paper.
- **H3 at risk:** CAI with the outlier channel OFF gave a *worse* 60 s MEMS outage drift than no CAI (214 m vs 103 m). The leading hypothesis is b_a / tilt decoupling (real physics: the CAI pins b_a alone, so MEMS gyro tilt error is no longer absorbed). A dedicated bug-vs-physics investigation is running. **No H3 claim until it resolves.**
- **Timing (D-025):** a standalone 2-state clock KF (`fusion/clock.py`), trust-weighted like GNSS, rather than ESKF states 15–16. It keeps the timing work independent of ESKF edits.
- **Scheduling:** runtime optimisation (hot spots: ESKF propagate, per-tick eigvalsh PSD check, so3_exp, IMU channel step) waits until the CAI-H3 investigation finishes, since both edit eskf.py.
- **Owner:** Master

### D-026 · 2026-09-26 · Freeze the detector design after one controlled round (anti-forking-paths)
- **Situation:**
  - The D-024 meaconing rule fixed meaconing: AUC 0.246 → 0.653 [0.576, 0.727], with 0% false firing on clean runs.
  - Moving the negative-rule reference to a clean-only pool at the same time shrank negatives 587 → 238 (84% positive), and jamming collapsed to AUC 0.100.
  - Two simultaneous changes cannot be attributed. Iterating further on a synthetic-innovation harness risks garden-of-forking-paths tuning (D-002).
- **Decision:** One final controlled round:
  - clean calibration pool = seeds 500–549;
  - class-balanced local training (≤ 50% positive, the same rule as the §4.2 FL replay buffer);
  - a 2×2 diagnostic {xsat rule} × {balancing}, plus the jamming pseudo-label distribution.
  - The {rule on, balancing on} configuration is then **frozen by design, independent of its numbers**. No further changes to labelling rules, thresholds or features before M1. Every later number is reported as-is.
- **Owner:** Master

### D-025 · 2026-09-26 · Add TIMING metrics (PNT includes "T")
- **Finding:** Meaconing in our model is effectively a pure timing attack: position error about 2.5 m, but a common-mode clock push. §6 metrics measure only position and velocity, so a timing attack would score as harmless.
- **Decision:** Add to ARCHITECTURE §6 (and to the evaluator, WP-7.1):
  - clock-bias error e_t(t) = |ĉ_b(t) − c_b,true(t)|/c [ns];
  - clock-drift error;
  - RMSE_t and MAX_t per phase;
  - time-to-distrust and recovery for timing.
  The truth clock is available to the *evaluator* from `GnssEpoch.meta` (environment-side, post-hoc only; never to the Agent).
  - Timing metrics are **secondary/exploratory**: the pre-registered primaries stay RMSE_h(P_att) and latency_on (§6.2). Adding a primary now would change the confirmatory family after design.
  - Exception: meaconing scenarios report RMSE_t alongside the primaries.
- **Consequence:** The fusion filter must estimate clock bias/drift, or the GNSS fix clock is used as the timing output; decide at M1 integration. The ES-EKF reserves indices 15–16 for the clock states.
- **Owner:** Master

### D-024 · 2026-09-26 · WP-4.2 detector fixes accepted; meaconing pseudo-label rule
- **Accepted fixes:**
  1. Features were zeroed on invalid fixes, erasing jamming evidence.
  2. The pseudo-label AGC rule had the wrong sign (AGC drops under jamming in this codebase).
  3. The harness dropped invalid-fix epochs.
  - Result: jamming AUC 0.430 → 0.773 [0.702, 0.845]; overall 0.727. PROVISIONAL.
- **Meaconing (0.246, CI entirely below 0.5):** diagnosed as a pseudo-label blind spot. The replay delay is absorbed by the clock unknown within 1 epoch, so only onset epochs get y=1, and the persistent C/N0 / cross-satellite-correlation signature is labelled y=0, teaching the inverse.
- **Decision:**
  - Add a y=1 hindsight rule on *sustained* elevation of x14 (cross-satellite C/N0 correlation) or x4 (mean C/N0 ≥ +3 dB over nominal), dwell ≥ 10 s. Physically motivated by the published single-antenna signature (Radoš 2024 Fig. 5).
  - Nominal quantiles are calibrated on clean runs from seeds 500–549 only.
  - Clean-run false firing must stay ≤ 1% of epochs.
  - If meaconing AUC is still < 0.5 after this, stop and report.
- **Owner:** Master

### D-023 · 2026-09-26 · WP-4.1 rulings: outage experiment redone; κ_R provisional
- **Accepted:**
  - ES-EKF core; mechanization closure (3.5 mm/120 s); trust coupling (w=0 excludes, w=0.3 intermediate); NIS gate; 4 h P-SPD in the Schuler world; bit-identical determinism;
  - undefended drift-spoof reference: max error 607 m at severity 0.5;
  - CAI invalid fraction 14% on a manoeuvring ground course (consistent with Ω_c ≈ 17 mrad/s);
  - PDs: joint 6-D GNSS innovation; `Innovation.accepted` nominal-R-gated vs correct-time R_eff gate; harness init 10 s.
- **Rejected:** the S2 outage metric (err_end − err_start including post-outage re-acquisition, negative "growth", an uncommitted script). Physically implausible values (MEMS 300 s ≈ 0 m; tactical < 2 m). The redo is specified in-window, with a CAI outlier-OFF arm to isolate the pure hybridization value (H3).
- **Provisional:** κ_R = 40 (GNSS R inflated 40×) prevents NIS lockout under *fixed* trust. Its root cause must be diagnosed, and the final value is chosen at M1 integration, on tuning seeds only, for all methods alike (D-002).
- **Noted honestly:** under fixed trust, FIELD-CAI with its real outlier channel made the MEMS outage *worse*. This is the undefended-quantum failure mode that §3.5 quantum trust exists to handle; it is kept as a reported result.
- **Risk R-3 escalated:** 110 s wall per sim-hour per node. A profile is requested before planning M3/M4 compute.
- **Owner:** Master

### D-022 · 2026-09-26 · Contract v0.3 (per-satellite C/N0) and WP-4.2/4.3 rulings
- **Contract v0.3:** `GnssFix.cn0_per_sat`, `GnssFix.elev_per_sat` (dicts keyed by PRN, default empty; additive). A real receiver reports these, so they are Agent-side legitimate. They enable the D-018 single-antenna spoofing features. `receiver.py` fills them (scoped edit by the TRUST agent).
- **Trust law ACCEPTED:**
  - S7 chattering: 0 cycles over 1 h at all toggle periods, against a bound of 138/h;
  - distrust within 1 epoch;
  - recovery 20–45 s (design 32.9 s);
  - reacquisition cap, floor, determinism;
  - quantum trust: min w_q = 0.227 in GE bursts, floor under contrast loss;
  - leakage AST guard passes.
- **Detector NOT accepted:** meaconing AUC 0.267 and jamming 0.430 are *below chance*. Systematic inversion is a bug signal (head/polarity/pseudo-label/invalid-epoch defaults), not a training-pool size effect, so a root-cause fix is required. All detector numbers are PROVISIONAL until integration with the real fusion filter (the current tests use truth-derived synthetic innovations).
- **PROPOSED-DECISIONs:**
  - PD2 accepted: the joint χ²₁₁ Mahalanobis test plus a 90% window clean fraction replaces the §3.1 per-dimension AND rule, which is statistically vacuous as written (0 negatives on clean data). This amends ARCHITECTURE §3.1.
  - PD3 accepted.
  - PD4 accepted for v1.
- **Owner:** Master

### D-021 · 2026-09-26 · Quantum-sensor grade semantics; FIELD is the primary grade
- **Finding:** The "lab" grade (Lautier 2014, 2T = 4 ms, cycle 1 s) has N ≈ 204 µg/√Hz, about 30× noisier than FIELD (6.97 µg/√Hz). The WP-2.1 brief defined LAB as "best published", but Lautier 2014 is a short-T, compact hybridization demonstrator, not a best-sensitivity instrument. The physics is fine; the label is misleading.
- **Decision:**
  - **All primary results use FIELD** (anchored to real Jarlaud 2024 data).
  - "lab" is documented and reported as **"short-T compact (Lautier 2014)"**: a high-dynamic-range, low-sensitivity operating point used only in sensitivity sweeps. The code key stays `lab` for stability. The paper must never call it "best lab performance".
  - NEAR_FUTURE (cycle 0.1 s, 2.04 µg/√Hz) is roadmap-only and labelled as such in every figure.
- **Owner:** Master

### D-020 · 2026-09-24 · CAI rotation scaling Ω_c ∝ 1/T² (corrects a Master error); per-shot cycle time 1.548 s
- **Correction:** In D-014 the Master's instruction to QUANTUM-SENSOR said "contrast loss ∝ Ω·T²·v, so Ω_c ∝ 1/T". That is internally inconsistent. Rotation phase 2k_eff(Ω×v)T² averaged over the velocity spread σ_v gives Ω_c ∝ 1/(k_eff σ_v T²), so **Ω_c ∝ 1/T²**. Field grade (T = 10 ms): Ω_c ≈ 17.4 mrad/s (was 28.9 under the wrong law). The field sensor therefore tolerates even less rotation, which strengthens the case for the trust engine handling quantum invalidity.
- **Cycle time:** 2.955 s was the per-k-direction interval (kD/kU interlaced). The instrument outputs one acceleration shot every 1.548 s. With k-dependent systematics not modelled, use per-shot output: cycle 1.548 s, σ_shot 5.60 µg, N = σ·√cycle ≈ 6.8 µg/√Hz. The old value overstated the noise density by ≈ 38%.
- **Ratified:** the GM1 AVAR leading factor 2σ²τ_c/τ is correct (∫R dt = 2σ²τ_c).
- **Owner:** Master

### D-019 · 2026-09-24 · Quantum-sensor noise = measured per-T Gaussian + bursty Gilbert–Elliott outlier channel
- **Decision:**
  - FIELD grade: 2T = 20 ms, robust σ_shot = 5.60 µg (95% CI 5.04–6.40), measured from real Jarlaud 2024 shots, 1.11× the paper-implied value. Other T values are interpolated from the measured table (10.70 / 12.47 / 6.83 / 5.60 µg at 10/12/14/20 ms), not from an assumed 1/T² law.
  - Outliers are modelled as a two-state Gilbert–Elliott chain fitted to the measured 9.0% rate (CI 6.7–11.8%) and ≈ 66% burst persistence (7.4× the independence rate), with magnitudes drawn from the empirical distribution. The sensor keeps `valid=True` during bursts, so it is silently wrong, as in reality.
  - Replay draws only same-T clean shots.
- **Rationale:**
  - The measured bursty faults are a genuine CAI failure mode. They make the quantum sensor itself a sensor the trust engine must watch (§3.5 quantum trust), which strengthens the scientific case for continuous trust over "quantum = ground truth".
  - Omitting them would overstate the quantum benefit (D-002).
- **Open:** Bursts may be triggered by rotation-rate zero-crossings (dataset hint). Modulating the burst rate by dynamics is deferred until there is evidence.
- **Owner:** Master

### D-018 · 2026-09-24 · Model the cross-satellite C/N0 correlation of single-antenna spoofers
- **Decision:** A single-antenna spoofer transmits all PRNs from one antenna, so per-satellite C/N0 values become strongly correlated and lose their elevation dependence (Radoš et al. 2024, 10.3390/s24134210, Fig. 5). Implement this in spoofing.py as a common-mode C/N0 fluctuation (a shared Gauss–Markov term across all spoofed PRNs, plus convergence of C/N0 toward the spoofer power level after capture). Expose no new detector feature in the attack layer; the FUSION+TRUST detector computes its own features from the observables.
- **Rationale:** This is a published signature that a real detector can use. Omitting it would make spoofing unrealistically hard to see for every method. Including it keeps fidelity high and is method-neutral.
- **Also:** fix the pre-attack RAIM reference window in `scripts/gen_gnss_attack_results.py` so the signature table matches the clean row and the KS test.
- **Owner:** Master

### D-017 · 2026-09-24 · WP-1.2 rulings (UAV smoothness, world kwarg)
- **UAV vertical channel:** this is a **spec defect** (ARCHITECTURE §11.2), not a tolerance problem. Redefine `v_u(t)` as the integral of a C² acceleration pulse (so v_u is C³, the same smoothness class as ground `s(t)`), sized so the configured `vz_max` and `ramp_s` are still met. The acceptance bounds stay unchanged (accel-consistency 1e-3, snap ≤ 10 m/s³). Adjusting bounds would hide a real non-smoothness that would inject IMU aliasing artefacts.
- **Accepted PROPOSED-DECISIONs:**
  - optional `world="flat"` kwarg on `generate()`;
  - the ground grade-pulse hold spans its cruise segment;
  - the manoeuvre grammar forces one of each kind early, then draws at random.
- **Noted:** RK4 strapdown runs at 33 s per sim-hour and causal mode at 19 s. Under 4 h × N nodes, the E2E harness must budget for this (risk R-3).
- **Owner:** Master

### D-016 · 2026-09-24 · Agent concurrency cap = 2 (user directive)
- **Decision:** At most 2 execution agents run at once. New work packages queue until a slot frees. The 3 agents already running at the time of the directive finish; they are not restarted.
- **Rationale:** 4 parallel Sonnet agents hit the account session limit (EXECUTION_LOG #19). The user prefers slower and steady ("no rush").
- **Owner:** Master

### D-015 · 2026-09-24 · Atom noise is calibrated per interrogation time with robust statistics; fringe jumps are modelled, not dropped
- **Finding (Master re-analysis of atom_shot_residuals.npz):** The pooled σ_shot of 20.9 µg mixes 2T ∈ {10, 12, 14, 20} ms and contains outlier shots. Per 2T, robust (MAD) σ is 10.7 µg (10 ms), 12.5 µg (12 ms, n = 24 only) and 6.8 µg (14 ms). At **2T = 20 ms** it is **5.6 µg**, and the individual static runs give 4.9–5.8 µg. The paper's static-SNR-implied figure is **5.06 µg**, a ratio of ≈ 1.1. The "4.1× gap" was a pooling artefact. The CSV's "9 µg" is a mean |r|, not σ.
- **Decision:**
  1. Calibrate σ_shot separately for each 2T with a robust estimator. The FIELD grade uses 2T = 20 ms, σ_shot ≈ 5.6 µg (measured, with CI). Other T values come from the measured per-T table, not from an assumed 1/T² law: the measured 10→20 ms ratio is about 2×, not 4×, which suggests a vibration-limited regime.
  2. The outlier shots (σ 35 µg vs robust 5.6 µg at 20 ms) are treated as a real **fringe-jump / outlier process**. Measure their rate and magnitude and model them in the sensor as an outlier channel, not deleted. This matters for the trust engine: the CAI can itself emit bad samples.
  3. Replay draws only from residuals with the same 2T. Pair kD/kU as unpaired samples (accepted).
  4. θ ≈ 0 proxy via the per-run Parameters.txt tilt: accepted, documented as an approximation.
- **Owner:** Master

### D-014 · 2026-09-23 · Keep classical and atom real-data channels strictly separate
- **Decision:**
  - The Jarlaud 2024 static streaming record (MICAL, 2.57 kHz, 373 s) is **classical accelerometer** noise. It is used only as a real-noise option for the classical accelerometer, never as quantum-sensor noise.
  - Quantum-sensor noise is calibrated from **real per-shot atom residuals** derived from the per-shot Raman population ratios / real-time phase at |Ω| < 5 mrad/s (static Run 21 plus the low-rotation shots of other runs), and replayed at the cycle rate.
  - The measured contrast-vs-rotation law C0 = 0.394 ± 0.017, Ω_c = 48.2 ± 2.5 mrad/s (rigid mode, 2T = 12 ms) becomes the FIELD-grade rigid-mode model. Inertial pointing (≤ 250 mrad/s) is an optional NEAR_FUTURE mode.
  - Accepted: no tidal removal (the record is too short). Contrast fit from Fig 2 only, for now.
- **Rationale:** The dataset has no continuous atom-acceleration channel. Presenting classical MICAL noise as "cold-atom noise" would misrepresent the paper's key evidence. Per-shot atom data does exist in the Raman files, so real atom noise is extractable, only at about 0.65 Hz with far fewer samples.
- **Consequence:** With the measured Ω_c, a rigid-mode CAI loses contrast during ordinary vehicle turns (about 0.3 rad/s), so the quantum aiding is intermittent in manoeuvres. It is kept as a real effect. It also weakens the quantum benefit, which is exactly the kind of honest limitation D-002 requires.
- **Source:** d'Armagnac de Castanet et al., *Nat. Commun.* 15:6406 (2024), 10.1038/s41467-024-50804-0. Data: 10.5281/zenodo.11543715 (CC-BY-4.0).
- **Owner:** Master

### D-013 · 2026-09-23 · Bibliography rulings (Master re-checked every DOI below against Crossref)
| # | Ruling | Citation to use |
|---|---|---|
| 1 Zhou 2023 | **Swap.** MVMAFOL is about IoV resource allocation, not positioning | Zhou et al., "Spatial–Temporal Federated Transfer Learning with multi-sensor data fusion for cooperative positioning", *Information Fusion*, 2023. 10.1016/j.inffus.2023.102182 |
| 2 Negru 2024 | **Keep, reframe.** "Federated fusion" = classical federated filter architecture, NOT federated learning. Move it to the fusion-architecture group of related work. This also sharpens the gap statement | *Sensors* 24(3):981. 10.3390/s24030981. Plus the origin of federated filtering: Carlson, PLANS'88, 10.1109/plans.1988.195473; Carlson, IEEE TAES 1990, 10.1109/7.106130 |
| 3/15 Khan 2025 | **Merge** into one reference | *Trans. Emerg. Telecom. Tech.* 36(4). 10.1002/ett.70138 |
| 4 Chai 2025 | **Verified** | *IEEE IoT J.* 2025. 10.1109/JIOT.2025.3588162 |
| 5 Meng 2025 | **Drop** (not found by two searches plus the user's tool) | replaced by Ren 2020 (below) as the adaptive-fusion representative |
| 6 Gu 2021 | **Drop** (not found) | replaced by Mehra 1970 (innovation-based adaptive KF, the root of B′), *IEEE TAC*, 10.1109/tac.1970.1099422 |
| 7 Pardhasaradhi 2022 | **Verified, reframe:** detect then switch to an independent radar track (binary; this is B-bin) | *IEEE Sensors J.* 22(11). 10.1109/JSEN.2022.3168940 |
| 8 Chehimi & Saad | **Reframe.** Real quantum-FL papers, but none does clock sync or positioning with quantum *sensors*. Cite as "FL over quantum networks/models", not as prior FL + quantum-sensor work | 10.1109/ICASSP43922.2022.9746622 (QFL/FedQLSTM line); 10.1109/MNET.2023.3327365 |
| 9 Tariq 2026 | **Reframe.** Multi-model fusion, not consensus-based. 97% is mission success; detection accuracy is about 99% | *PeerJ CS*. 10.7717/peerj-cs.3875 |
| 10 Kannamarlapudi 2025 | **Drop.** Zero hits (Crossref author search, checked by Master; OpenAlex, checked by the agent) | — |
| 11 Hazarika 2025 | **Verified, reframe:** quantum-*enhanced* FL (computation), not quantum sensing | *IEEE TCOM*. 10.1109/TCOMM.2024.3502667 |
| 12 Radoš 2024 | Verified | *Sensors* 24(13):4210. 10.3390/s24134210 |
| 13 Borhani-Darian | **Correct the citation.** The proposal's DOI belongs to Korium et al., an unrelated paper | "Detecting GNSS spoofing using deep learning", *EURASIP JASP* 2024. 10.1186/s13634-023-01103-1 |
| 14 Namagembe 2026 | Verified | *CMC*. 10.32604/cmc.2025.070316 |
| 16 Wright 2022 | Verified | *Front. Phys.* 10:994459. 10.3389/fphy.2022.994459 |
| new | **Add** as the closest robust-FL prior work; position our TRIM-NB-R aggregator against it | Liu et al., "G²FL: Robust FL for GNSS Spoofing Detection", ICC Workshops 2026. 10.1109/ICCWorkshops63917.2026.11586283 |
| new | **Add** as the adaptive-fusion representative (replaces Meng) | Ren et al. 2020, CVCI. 10.1109/CVCI51460.2020.9338655 |
- **Impact on novelty claim:**
  - With #10 dropped and #8 and #11 reframed, **no verified prior work implements FL together with physical-quantum-sensor models**. The gap is *stronger* than the proposal stated, but the proposal's positioning table must be rewritten.
  - G²FL overlaps with our robust aggregation. Our novelty there is limited to the trust-coupled closed loop, not robust FL itself.
- **Consequence for code/specs:** the ARCHITECTURE §5 baseline citations follow this table (A: Khan 2025, Chai 2025; B-bin: Pardhasaradhi 2022; B-cont: Ren 2020 class; B′: Mehra 1970). The ATTACK agent must cite Borhani-Darian via the EURASIP DOI.
- **Owner:** Master

### D-012 · 2026-09-23 · Reference-verification gate
- **Decision:** A reference may appear in the paper, patent or specs only once Crossref/OpenAlex or the publisher landing page confirms it exists (DOI resolves, metadata matches). A paper that exists but whose content differs from the proposal's description gets cited for what it actually does. Unfound references are dropped or replaced by verified papers on the same topic, and every such change is logged. Paper drafting (M5) cannot start until `docs/specs/raw/REFERENCES_VERIFIED.md` shows no unresolved entries.
- **Rationale:** Two independent searches failed to find about 9 of the 16 proposal references as described. Citing a non-existent or misdescribed paper would be fatal at Q1 review.
- **Note:** Negru 2024's "federated fusion" may be the classical federated Kalman filter, not federated learning. If so, it moves in the related-work taxonomy.
- **Owner:** Master

### D-011 · 2026-09-23 · Baselines represent method classes, not re-implementations of specific papers
- **Decision:**
  - The baselines are defined as **mechanism classes**. Papers are cited as representatives of a class ("in the spirit of"), never as re-implementations.
  - **A (FL detection → detect-and-exclude):** unchanged. Representatives: ETT 2025 36(4) (proposal #15, DOI 10.1002/ett.70138, pending verification; "Khan 2025" may be this same paper), Khan 2025, Chai 2025.
  - **B is split into two variants:**
    - **B-bin (single-node detect-and-switch):** local detector; when an attack is flagged, exclude GNSS and coast on the INS until the recovery gate passes. Representatives: Pardhasaradhi 2022 (IEEE Sensors J. 22(11), DOI 10.1109/JSEN.2022.3168940, pending verification), a detect-then-switch-to-independent-source scheme.
    - **B-cont (single-node continuous trust):** our §3.3 law with a local-only detector. This is the *strongest* single-node competitor and isolates the FL contribution exactly. It is equivalent to the "−FL" ablation.
  - **B′ (innovation-χ² adaptive EKF):** stays, as the classical adaptive-Kalman representative (Gu 2021 class).
  - H2 is tested against **B-cont**, the harder baseline. B-bin is reported alongside it.
- **Rationale:** LIT-CHECK (WP-6.0) confirmed only Pardhasaradhi 2022 (high confidence) and the ETT 2025 paper (medium). Chai 2025, Meng 2025 and Gu 2021 could not be identified from surname and year. Full texts were paywalled (403), so no post-detection rule could be confirmed verbatim. Defining baselines by mechanism is honest, reproducible and reviewer-proof. Beating the strongest variant of each class is a stronger claim than beating a loose paper replica.
- **Open:**
  - Need exact bibliography entries for Chai 2025, Meng 2025 and Gu 2021 from the user or the proposal source.
  - Verify both DOIs against the publisher pages before paper drafting.
- **Owner:** Master

### D-010 · 2026-09-23 · Spoofed observables are deltas on clean observables; RAIM weights from the UERE budget
- **Decision:** Spoofed pseudorange = clean pseudorange + geometric delta (fake vs true position) + spoofer atmosphere-mismatch Gauss–Markov term (σ ≈ 0.5 m, τ ≈ 300 s, ASSUMPTION). Receiver thermal noise (rescaled to the spoofed C/N0) and victim multipath are kept. Meaconing is also a delta, equal to the replay delay. Attacks must never read `GnssEpoch.meta`. Receiver WLS/RAIM weights come from the signal model's own UERE error budget; acceptance is nominal mean χ² within ±30% of (n−4).
- **Rationale:** Master verification found that spoofed ranges were pure geometry plus the true clock read from `meta`, which made RAIM χ² exactly 0. That is a trivial giveaway and a leak of truth: any learned detector would exploit it and inflate every detection result.
- **Alternatives:** Keep the noise-free spoofer (rejected, unrealistic). Full signal-level spoofer (rejected, D-004).
- **Also ratified:** A1, a synthetic Walker almanac for v1 (real YUMA almanac possibly later). A2, `GnssAttack.apply` never mutates its input.
- **Owner:** Master

### D-009 · 2026-09-23 · Contract v0.2 and ratification of the ARCHITECTURE.md core design
- **Contract rulings on ARCHITECTURE.md §10:**
  - C-1 **accepted**: `Innovation` type; FusionFilter split into propagate / innovations / correct; TrustEngine takes innovations.
  - C-2 **accepted**: `QuantumSample.t_interrogation`, `response`.
  - C-3 **accepted**: `NavSolution.cov_vel`, `acc_bias`, `gyro_bias`.
  - C-4 **accepted, rename deferred**: `meta` is environment-private, stripped via the new `GnssEpoch.for_agent()`; renaming to `sim_meta` waits for v0.3 so the in-flight ATTACK work doesn't break.
  - C-5 **accepted**: `core/world.py` with `flat` and `schuler_tangent`; verified Schuler period 84.4 min.
  - C-6 **accepted**: strict ZYX, FLU (REP-103), θ>0 = nose down, documented in the types.py docstring.
  - C-7 **accepted**: `GnssFix.pdop`.
  - All changes are additive with defaults; the smoke test passed.
- **Architecture ratified as specified:**
  - 15-state loosely-coupled ES-EKF, with indices 15–16 reserved for tight coupling.
  - CAI used as a direct observation of the classical accel bias.
  - Trust → filter: `R_eff = R / max(w, 0.02)`, sensor excluded when w < 0.05, NIS gate in the shared core.
  - Asymmetric continuous trust law with hysteresis and a proven chatter bound of ≤ 1 cycle per 26.1 s.
  - MLP detector trained by FL on hindsight pseudo-labels; no ground-truth labels at nodes.
  - TRIM-NB-R robust aggregator; FedAvg and FedProx as references.
  - Baselines A, B and B′ and the ablations defined as config diffs over one code path.
  - Pre-registered hypotheses H1–H4 kept separate from the S1–S15 acceptance criteria.
  - 30 paired seeds, Wilcoxon + Holm; disjoint pre-train / tune / test seed ranges.
  - `multiprocessing` spawn + queues, bulk-synchronous in sim time.
- **Master open items:**
  - Verify that Baselines A/B faithfully represent Khan 2025, Chai 2025, Meng 2025, Gu 2021 and Pardhasaradhi 2022 before any result exists.
  - Architect's risk note: with MEMS gyros, tilt dominates within about 60 s, so the CAI benefit may be small. Report both MEMS and tactical grades.
- **Owner:** Master

### D-008 · 2026-09-23 · Use real quantum-sensor data where it exists
- **Decision:** Any real measured cold-atom accelerometer or gravimeter data we find is used in two ways. (1) Calibration/validation: fit the model's noise parameters to the Allan deviation (ADEV) of the real records and report how well model and data agree. (2) Noise replay: remove known signals (e.g. tides) from real static records and replay the leftover noise, resampled in blocks, as the random part of the simulated sensor (`noise_source="replay"`). The vehicle's true motion stays simulated.
- **Rationale:** User asked for real data. No public dataset has a quantum sensor on a moving vehicle under GNSS attack, so a fully replayed mission is impossible. The data can still ground every stochastic number in the paper.
- **Fallback:** If no raw data exists, digitise the ADEV figures published in the cited papers and calibrate to those.
- **Alternatives:** Pure parametric model from paper numbers (weaker evidence). Replaying data from other quantum sensors such as magnetometers (wrong sensor physics; kept only as a labelled fallback).
- **Owner:** Master

### D-007 · 2026-09-23 · Model-tier delegation policy (user directive)
- **Decision:** Opus = Master only (management, decomposition, all design/scientific decisions, verification, sign-off) — never execution. Sonnet = all implementation, testing, experiments, research extraction. Haiku = all documentation (spec write-ups from raw notes, README, reproducibility docs). Execution agents write terse `docs/specs/raw/*_NOTES.md`; Haiku turns them into polished docs. Any design choice an execution agent meets is marked `# PROPOSED-DECISION:` and ratified by Master here.
- **Rationale:** User directive to save usage while keeping decision quality at Opus level.
- **Consequence:** ARCHITECT (Opus) restricted to WP-1.1 design spec (a decision task) + an implementation brief; WP-1.2 code moved to a Sonnet agent. Wave-1 Opus QUANTUM-SENSOR and ATTACK agents stopped before writing any files and relaunched on Sonnet. Small edits to the three living logs remain Master-owned (spawning an agent per log line would cost more than it saves).
- **Open:** Paper drafting tier (Sonnet vs Haiku) to confirm with user — Haiku may be too weak for a Q1 manuscript.
- **Owner:** Master

### D-006 · 2026-09-23 · Stepped, closed-loop component interfaces (contract v0.1)
- **Decision:** Each sensor/attack/receiver/trust/fusion component is stepped once per global tick and returns `None` when it has no output. Only `ModelUpdate` crosses a node boundary. See `fedqpnt/core/types.py`, `fedqpnt/core/interfaces.py`.
- **Rationale:** Supports free-run and stepped execution, sample-rate mismatch, dropouts, cold-start, and enforces "no raw data leaves the node" at the type level.
- **Alternatives:** Batch vectorised pipelines (faster, but cannot express closed-loop trust feedback).
- **Owner:** Master
