# FUSION_NOTES (WP-4.1) — ES-EKF implementation notes

Owner: FUSION. Code: `fedqpnt/fusion/eskf.py`. Tests: `tests/test_fusion_eskf.py`,
`tests/test_fusion_outage.py`. Committed harness: `tests/_fusion_helpers.py`
(replaces the earlier scratchpad-only `fusion_runner.py` per Master D-023).
Committed validation scripts (not tests; run manually): `scripts/fusion_outage.py`,
`scripts/fusion_nis_diagnostic.py`, `scripts/fusion_profile.py`.

## D-023 verification response (this section only; rest of file predates it)

**Item 1 (S2 outage metric was invalid).** Confirmed and fixed. The old
`growth = err(t_end) - err(t_start)` metric differenced two noisy
INSTANTANEOUS point samples of a vector norm -- it can be negative or near
zero even under monotone-in-expectation open-loop drift, and is NOT what
"error growth" should mean. Replaced with (in `scripts/fusion_outage.py`,
committed): horizontal error strictly AT t0+T, max horizontal error over
the whole window, and the filter's own 3-sigma at t0+T, for 10 seeds
500-599 (tuning/characterisation range, not test-seed results), asserting
`gnss_innovations_in_outage == 0` (real withholding, not just gate
rejection). `tests/test_fusion_outage.py` is the committed fast regression
(2 seeds, asserts the same invariant, runs in CI).

Sanity check (tactical, no-CAI, T=300s, seed=500): configured
`turn_on_bias_std` = 2.77e-2 m/s^2 -> naive (never-corrected) 0.5*b*T^2 =
1248 m. The filter's OWN residual `|acc_bias_est - acc_bias_true|` at the
moment the outage begins (t=60s, after 50s of GNSS-aided flight) = 1.98e-2
m/s^2 -> realistic 0.5*b_resid*T^2 = 891 m. **Measured error at t0+T = 604
m** -- same order of magnitude as the realistic prediction, confirming the
mechanics are right. The residual is nearly as large as the never-corrected
value because **b_a is only weakly observable from GNSS position/velocity
alone without much specific-force-direction excitation** (exactly the
motivation for CAI hybridisation, Sec 2.5) -- this seed's pre-outage 50s
segment did not maneuver enough to pin down b_a. This also explains why the
OLD (1-5 seed, buggy-metric) sweep looked deceptively small: some seeds'
pre-outage trajectories happen to maneuver enough to converge b_a well,
others don't; the differencing bug then hid the real, large, seed-dependent
spread entirely. The corrected sweep (`industrial_mems`, no-CAI) confirms
this spread directly: T=60s across 10 seeds gives mean=103 m, median=38 m,
max=249 m; T=300s gives mean=3448 m, median=2197 m, max=14110 m (heavily
right-skewed -- exactly the "some seeds converge b_a, some don't" pattern).
Full 12-combo (6 configs x 2 T) sweep: only 3 of 12 completed within this
session's compute budget (background CPU contention made per-run wall time
5-10x the isolated benchmark: ~15-20 min per 10-seed combo instead of the
expected ~2-3 min). Completed: `industrial_mems|no CAI|T=60s` (above),
`industrial_mems|no CAI|T=300s` (above), and
`industrial_mems|CAI FIELD outlier OFF|T=60s`: mean=213.9 m, median=225.1 m,
max=493.5 m. The script is fully reproducible (`python
scripts/fusion_outage.py`) to get the rest; remaining combos (tactical x3,
industrial_mems CAI-outlier-ON x1, and the T=300s CAI rows) were not run to
completion here.

**Flagged concern (not yet resolved, needs follow-up):** the one CAI
outlier-OFF ("pure hybridisation") combo that DID complete is *worse* than
no-CAI at the same T (213.9 m vs 103.4 m mean, T=60s) -- the opposite of
the intended H3 benefit. A quick single-seed debug trace (seed=500,
continuous GNSS, no outage) shows `b_a` converging via CAI within ~2 updates
(t=10.85s->12.4s) to a magnitude (~0.093-0.16 m/s^2) consistent with the
configured industrial_mems turn-on-bias std (0.098 m/s^2) -- CAI's own
bias estimate looks numerically correct, not obviously buggy -- yet overall
position error at t=90s (10.2 m) is worse than the ~2-3 m RMSE this same
kappa_R=40 config achieves WITHOUT CAI in the S1 nominal runs. The likely
mechanism (not confirmed): GNSS-only aiding may be converging `b_a` to a
value that is "wrong but convenient" -- compensating for a DIFFERENT,
correlated unmodelled error (e.g. gyro turn-on bias/attitude) in a way that
happens to reduce net position error -- while CAI forces `b_a` to its true
physical value quickly, which can UNMASK that other error instead of fixing
it (a known bias/state confounding phenomenon in INS, not necessarily a
fusion bug, but not verified here). **This needs a dedicated follow-up
investigation before any H3 CAI-benefit claim is made in the paper** --
flagging explicitly rather than either hiding it or asserting it is
resolved.

**Item 2 (kappa_R=40 is provisional; diagnose the NIS lockout).** Ran
`scripts/fusion_nis_diagnostic.py` (ground, industrial_mems, seed=500,
kappa_R=1, plot at `results/fusion/nis_diagnostic.png`). Correlation between
log10(NIS) and the INSTANTANEOUS yaw rate / lateral specific force at each
GNSS epoch is essentially zero (-0.02 / +0.10), and stays weak even using a
rolling mean over the preceding 3/5/10 epochs (max +0.26 for lateral force
at W=10). Critically, NIS climbs steadily over SEVERAL CONSECUTIVE epochs
(1.8 -> 6.6 -> 24.8 -> 27.5, t=48-51s) while yaw_rate and lateral force are
EXACTLY CONSTANT across those same epochs (sustained coordinated turn, not
a sudden jerk) -- rejection begins at t=53s, one epoch AFTER the peak,
by which point the vehicle's own dynamics have already changed. This
pattern -- NIS growing across several epochs under CONSTANT vehicle
dynamics, weakly correlated with instantaneous or short-window-averaged
rate/force -- is inconsistent with (b) unmodelled scale-factor/misalignment
(which would track |f|/|omega| much more tightly, especially in the
rolling-window test) or (c) latency (which would show a lagged, rate-of-
change-dependent signature). It IS consistent with **(a): the GNSS signal
model's per-satellite iono/tropo/multipath residuals are genuine
Gauss-Markov processes (tau=600s/1800s/20s respectively,
`fedqpnt/gnss/signal.py`), so they barely change from one 1 Hz epoch to the
next -- a real, PERSISTENT common-mode position bias -- while the
receiver's WLS weights and reports `cov_pos` from the instantaneous
per-satellite UERE variance as if each epoch's error were an independent
white draw (`fedqpnt/gnss/receiver.py` docstring: weights = "inverse of the
SAME variance the signal model draws from", with no cross-epoch
correlation term). The ESKF then also treats `R = kappa_R * cov_pos` as
white per Sec 2.5. A persistent bias that P is shrinking against (each
epoch's Kalman gain treats the fix as fresh independent information) is
exactly what produces a NIS that ratchets upward over consecutive epochs
until it exceeds the gate. **Diagnosis: (a).** Not retuning kappa_R now per
instruction; final value is chosen at M1 with the real trust engine, on
seeds 500-599 only. A durable fix belongs in the GNSS/receiver layer (an
epoch-to-epoch correlated-error term in `cov_pos`, or a filter-side GM
GNSS-bias state per the very Sec 2.1 caveat the architecture itself flags
as a known LC weakness) rather than in kappa_R alone.

**Item 3 (runtime profile, R-3).** `scripts/fusion_profile.py`, one
simulated hour (360,000 ticks) under cProfile (NOTE: cProfile overhead
itself inflates absolute times several-fold; only the RELATIVE breakdown is
meaningful): total 326.7s / 99.26M calls. Top hotspots by self (tottime):
`ESKF.propagate` own body 98.2s (F/G/Phi/Qd construction + P update linear
algebra, several fresh 15x15/15x12 matrices and matmuls every tick);
`ClassicalImu._AxisChannel.step` 28.2s (called 2x/tick, accel+gyro);
`rotations.so3_exp` 22.1s; `np.linalg.eigvalsh` 11.4s (called every 500
ticks... no -- called on EVERY propagate+correct, i.e. 363,600 times, purely
for the P-PSD hygiene floor-check in `_hygiene()` -- full O(n^3)
eigendecomposition just to test one scalar bound is the clearest
low-hanging fruit); `np.cross` (coning term) 11.3s; `rotations.dcm_to_euler`
6.8s (called every tick to fill `NavSolution.att`); `numpy.moveaxis` 5.0s
(batched-rotation-API reshape overhead paid on every single-sample call,
since `so3_exp`/`dcm_to_euler` are the general (N,3)-batch-capable
functions in `fedqpnt/sim/rotations.py`, not owned by FUSION). Not
optimising per instruction; candidates for later, cheapest-first: replace
the per-tick `eigvalsh` PSD check with a cheaper test (diagonal floor or a
Cholesky attempt, which is O(n^3/3) and short-circuits on failure) or check
it every K ticks instead of every tick; hoist the static parts of F/G (zero
blocks, identity blocks) out of the per-tick allocation; consider a
single-sample fast path for `so3_exp`/`dcm_to_euler` (would need a
sim/rotations.py change, out of FUSION's ownership).

## Equations implemented (ARCHITECTURE.md section references)

* State (Sec 2.2): `delta x = [dp, dv, psi, dba, dbg]`, n=15. Nominal
  `(p, v, C in SO(3) as DCM, b_a, b_g)`.
* Mechanisation (Sec 2.3): causal trapezoid + coning,
  `C_{k+1} = C_k Exp(0.5(w_k+w_{k+1})dt + (1/12)(w_k x w_{k+1})dt^2)`,
  `v_{k+1} = v_k + (0.5(C_k f_k + C_{k+1} f_{k+1}) + g_n) dt`,
  `p_{k+1} = p_k + 0.5(v_k+v_{k+1}) dt`. Verified against noiseless truth
  f_b/omega_b over a 120 s ground trajectory: max position error 3.5 mm
  (pure numerical/coning-truncation error, not a bug).
* F/G/Phi/Qd exactly per Sec 2.4, `Phi = I + F dt + 0.5(F dt)^2`,
  `Qd = 0.5(Phi G Qc G^T + G Qc G^T Phi^T) dt`. `gravity_gradient(world)`
  from `fedqpnt.core.world` is added at F[3:6,0:3] (zero for flat, the
  Schuler block for `schuler_tangent`).
* VRW/ARW/q_ba/q_bg read from `ImuModel.config()["accel_noise_SI"/"gyro_noise_SI"]`
  (`random_walk_per_sqrt_s`, `bias_instability_gm1_sigma`,
  `bias_instability_gm1_tau_c_s`); `q_b = 2 sigma_BI^2 / tau_c`.
* Measurement models (Sec 2.5): GNSS pos+vel processed as **one joint 6-D
  update** (H=[I 0 0 0 0; 0 I 0 0 0], R=blkdiag(kappa_R*cov_pos, kappa_R*cov_vel));
  CAI hybridisation: window-matched IMU mean using `t_interrogation`/`response`
  (triangular over `[t-2T,t]` when the sensor reports `response=="triangular"`
  and finite `t_interrogation`, else boxcar over `[t-cycle_time,t]`),
  `H_Q` rows dropped for NaN axes, `R_Q = diag(variance) + VRW^2/T_W + sigma_win^2`,
  `sigma_win = 1e-5 * G0` (default, per Sec 2.5 sweep set {1e-6,1e-5,1e-4}).
  No quantum update if `valid==False`.
* Trust coupling (Sec 2.7): `R_eff = R / max(w, w_min)`, exclusion `w < w_excl`,
  NIS gate `chi2_dof(1 - alpha_gate)` evaluated with **R_eff** at correction
  time (the innovation returned by `innovations()` is gated with **nominal
  R** — a diagnostic/feature-facing flag, consistent with Sec 3.1 "features
  use nominal-R innovations"; the filter's own accept/reject decision inside
  `correct()` recomputes NIS with R_eff, per the literal Sec 2.7 wording).
  Defaults `w_min=0.02, w_excl=0.05, alpha_gate=1e-4`.
* Reset (Sec 2.8): `dx = K nu` (nu defined "estimate minus measurement"
  per Sec 2.5/0, so this is the standard-KF `K*innovation` with signs
  matching the literal reset equations); `p -= dx[:3]`, `v -= dx[3:6]`,
  `C <- Exp(dx[6:9]) C`, `b_a -= dx[9:12]`, `b_g -= dx[12:15]`; Joseph-form
  P update. Covariance hygiene (symmetrise, eigenvalue floor 1e-12) after
  every propagate and correct.
* Init (Sec 2.9): `initialize_static(t0, pos0, att0, vel0)` sets
  `P0 = diag(3^2,3^2,3^2, 0.1^2,0.1^2,0.1^2, 1mrad^2,1mrad^2,35mrad^2,
  sigma_ba_turnon^2 x3, sigma_bg_turnon^2 x3)`. Roll/pitch levelling and
  heading (truth + N(0,2deg^2)) are computed by the CALLER (validation
  harness), never inside the filter, since the filter must not see truth.
* `NavSolution.clk_bias` = clock bias of the last GNSS fix seen by
  `innovations()` (valid fixes only), NaN if none yet (C-3 compliant;
  `cov_vel`, `acc_bias`, `gyro_bias` filled).
* IMU dropout (Sec 1.4): ZOH on last sample, `Q *= kappa_zoh=10`; beyond
  `max_gap_s=0.1s` an extra x10 inflation (no external w_imu signal reaches
  fusion in this WP, since trust is fixed/external).
* Never imports `fedqpnt.sim.trajectory`/truth or `fedqpnt.attacks`/`AttackLabel`
  (enforced by `tests/test_fusion_eskf.py::test_never_imports_forbidden_modules`).
  It DOES import `fedqpnt.sim.rotations` (pure SO(3) math utility, not truth)
  and `fedqpnt.core.world` (contract, C-5).

## PROPOSED-DECISIONs

1. **GNSS innovation reported as one 6-D `Innovation(sensor="gnss")`**, not
   split into `gnss_pos`/`gnss_vel`, matching Sec 2.5's "processed as one
   6-D update" and `SENSORS=("gnss","imu","quantum")` (TrustState has no
   separate pos/vel weight). The `sensor` field's example strings in
   `types.py` ("gnss_pos","gnss_vel") are therefore illustrative, not
   normative; flagged for Master ratification.
2. **`Innovation.accepted` is nominal-R-gated** (diagnostic, matches Sec 3.1
   feature convention), while the filter's actual accept/reject inside
   `correct()` is R_eff-gated (matches Sec 2.7's literal wording that the
   gate "is evaluated with R_eff"). These two decisions can disagree by
   design (a low-trust sensor can be nominal-rejected but R_eff-accepted,
   or vice versa); this is intentional so a trust engine built against
   nominal-R features never sees a self-referential loop.
3. **30 s stationary/hover init segment shortened to 10 s** in the
   validation harness (10 s is the actual requirement for the roll/pitch
   levelling average; the extra 20 s in Sec 11.2 adds realism but not a
   different formula) — a validation-harness efficiency choice, not a
   filter-code change.
4. **Reacquisition cap** (Sec 1.4: `w_gnss <- min(w_gnss, 0.5)` after a
   >5s outage) is explicitly TRUST's responsibility per the architecture's
   own module table and is NOT implemented in `fedqpnt.fusion` — validated
   with fixed `TrustState(weights=1)` per the task brief, so this project's
   validation cannot exercise that recovery path (see Known limitation below).
5. **kappa_R tuned to 40** on seeds 500-502 (ground, industrial_mems, 300 s,
   no attack) to bring nominal ANEES_pos into/near the [0.5,2] S1 band; see
   Key Results for the seed-1..10 evaluation numbers this produced. This is
   an order of magnitude above the naive kappa_R=1 that the fix's own
   reported `cov_pos` would suggest, because a single-antenna WLS fix's
   reported covariance understates real-world-representative model
   mismatch during vehicle maneuvers substantially more than 1x (see Known
   limitation).

## Known limitation: NIS-gate lockout without a trust engine

At `kappa_R=1` (fix covariance taken at face value) the 6-DOF joint
NIS gate (`alpha_gate=1e-4`) permanently excludes GNSS once P has
converged small (few m^2) and a single aggressive-maneuver tick produces
an inconsistent-but-real innovation: rejection keeps P from being
corrected, the next tick's innovation is even larger, and the filter
diverges to km-scale error within minutes (reproduced: seed 500, ground,
industrial_mems, kappa_R=1 -> RMSE 1118 m over 300 s, vs 1.5 m at
kappa_R=3). This is exactly the failure mode Sec 3.3 item 6 ("anti-lockout")
and the Sec 1.4 reacquisition cap exist to prevent, both of which are
TRUST-engine mechanisms outside this WP's scope. With a **fixed trust=1**
(as required for this WP's isolated validation) there is no such
safety net, so a large kappa_R is doing double duty: it is nominally
"LC fixes have time-correlated/optimistic covariance" (Sec 2.1) inflation,
but here it is also load-bearing against gate lockout. **This is reported
honestly, not tuned away**: once fedqpnt.trust exists, re-run this sweep
with the real trust engine in the loop; kappa_R may drop substantially
because the reacquisition cap and anti-lockout logic will recover from
transient rejections that currently compound.

## Numbers (kappa_R=40, all other defaults; seeds as noted)

**S1 nominal, 30 min, kappa_R=40 (tuned on seeds 500-502):**

| platform | grade | seeds | RMSE_h mean [m] | ANEES_pos range |
|---|---|---|---|---|
| ground | industrial_mems | 1-6 (6) | 2.58 | 0.67 - 2.35 (1 of 6 slightly above 2) |
| ground | tactical | 1-5 (5) | 2.23 | 0.62 - 1.16 (all in band) |
| uav | industrial_mems | 1-3 (3), 600s | 2.22 | 0.68 - 3.18 (1 of 3 above band) |
| uav | tactical | 1-3 (3), 600s | 2.11 | 0.55 - 1.42 (all in band) |

ANEES_pos is mostly in the S1 [0.5,2] band; occasional excursions above 2
coincide with the vehicle's own aggressive-maneuver pulses (scale-factor/
misalignment error is briefly larger than the model accounts for). Given
more time budget, a per-maneuver kappa_R schedule or a slightly larger
kappa_R would tighten this further; not done here to avoid tuning on
non-tuning seeds.

**S2 GNSS outage (ground, seeds 1-5, kappa_R=40), horizontal error growth [m] over the outage:**

| grade | CAI | 60s growth (mean of 5) | 300s growth (mean of 5) |
|---|---|---|---|
| industrial_mems | no | 8.4 | -0.5 (bounded by re-acquisition after outage end; see note) |
| industrial_mems | yes (FIELD, outlier channel ON) | 70.2 (2 of 5 seeds >100m) | 3899 (2 of 5 seeds >6000m) |
| tactical | no | 0.87 | 0.79 |
| tactical | yes (FIELD) | -0.19 | 1.99 |

Read the industrial_mems+CAI row carefully (see Known limitation below): the
FIELD-grade Gilbert-Elliott outlier channel (D-019) injects large but
`valid=True` shots at ~14% rate; with **fixed trust=1** (required for this
WP) those shots are fully believed and corrupt `b_a`, producing occasional
catastrophic drift far worse than no-CAI. On tactical grade this doesn't
happen in the seeds tried (smaller absolute drift means the CAI's own
outliers don't dominate as easily). **This is the honest, undefended-quantum
answer**, analogous to Sec 2.5's own prediction that "the CAI benefit is
expected to be small for MEMS" -- here it can be actively negative without
quantum trust/CUSUM gating (Sec 3.5), which is out of this WP's scope.
The "-0.5"/"0.79" mean growth for the no-CAI 300s rows include some
negative values because the vehicle trajectory itself loops back toward
the origin during long outages on this particular ground course; growth is
reported as `err(t_end) - err(t_start)`, not integral drift rate.

FIELD grade, maneuver-heavy ground trajectory, 300 s: **172 valid / 28
invalid CAI samples (14.0% invalid)** -- consistent with the architecture's
expectation that Omega_c~17 mrad/s is exceeded often during real turns
(D-020).

**S3 trust coupling (unit tests, `tests/test_fusion_eskf.py`):** w_gnss=0
excludes a 100 m fix jump exactly (state unchanged to 1e-6); w_gnss=0.3
gives an intermediate correction strictly between w=0 and w=1's pulls
(0 < 0.46 < 1.0 m for a 2 m fix from the origin).

**S4 NIS gate / undefended spoof:** a 50 m abrupt GNSS jump is rejected
(NIS=555 vs chi2_6(0.9999)=27.9 threshold; state unchanged). `DriftInSpoof`
(medium severity 0.5, position mode) with trust fixed at 1 (undefended):
**max horizontal error 607.4 m** at t=410 s (ground, industrial_mems,
seed=3, kappa_R=40, 400 s run with a 200 s attack starting at t=100 s).

**S5 long-duration stability:** 4 sim-hours, schuler_tangent world, ground/
industrial_mems, seed=42, kappa_R=40: **P stayed finite, symmetric and PSD
at every checked tick (every 500 ticks, hard-asserted, no violation)**; max
horizontal error over the whole 4 h was **11.3 m** (bounded by Schuler
dynamics, not growing as t^2 -- consistent with Sec 2.6's prediction).
Determinism: same seed run twice (full pipeline: traj+IMU+GNSS+receiver+
ESKF) gives bit-identical `err` arrays; the ESKF-only determinism unit test
(`test_determinism_same_seed_same_trajectory`) also passes.

**S6 runtime:** ~3200 ticks/s single-process on this machine (measured in
isolation) => **~110-115 s of wall time per simulated hour at 100 Hz IMU**
(full ClassicalImu + GnssSignalModel + GnssReceiver + ESKF pipeline, no
quantum sensor). The 4-hour stability run (with periodic P-hygiene asserts
every 500 ticks) took 943 s wall for 4 sim-hours = 236 s/sim-hour under
light background load.

## Known limitation (restated with numbers)

kappa_R=1 (fix covariance at face value) diverges under the shared 6-DOF
NIS gate once P has converged during an aggressive ground maneuver: seed
500, ground, industrial_mems, 300 s -> RMSE_h = 1119 m (vs 1.5 m at
kappa_R=3). kappa_R in [20,80] avoids this for all seeds tried (500-502,
1-6). kappa_R=40 was selected as a mid-point; ANEES at kappa_R=80 is lower
across the board (more conservative) at the cost of slightly worse RMSE.
Once fedqpnt.trust exists with the reacquisition cap and anti-lockout
logic, this sweep should be redone with real trust in the loop.

## CAI-H3 investigation (follow-up to D-023's flagged concern)

Question: is CAI-outlier-OFF worse than no-CAI at 60s outage
(industrial_mems, 213.9m vs 103.3m mean) a bug in `fedqpnt/fusion/eskf.py`
or real estimation physics? Script: `scripts/cai_h3_investigation.py`
(seeds 500-509 only). Conclusion: **PHYSICS, no bug found.**

**Bug checks (all passed):** (a) CAI `H_Q` row/sign: `nu_Q = f_bar_Q -
f_bar_IMU ~= delta_b_a` (both instruments in body frame, quantum.step uses
`truth.f_b` directly, same frame as the IMU's `f_tilde`; no rotation
mismatch found), and `correct()` applies `b_a -= dx` -> pulls b_hat_a
toward truth, correct sign. (b) Noiseless-IMU + noiseless-CAI + injected
constant accel bias converges `|b_hat_a - b_true|` to 1.1e-7 m/s^2 in ~4s
and leaves attitude undisturbed (delta=0), confirming `H_Q`/`R_Q`
construction is correct in isolation. (c) `R_Q` unit check: `variance` is
`sigma^2` with `sigma = sensitivity_m_s2_per_sqrt_hz * sqrt(rate_hz)`
(`fedqpnt/sensors/quantum.py`), i.e. (m/s^2)^2, matching `vrw^2/T_W` and
`sigma_win^2` in `R_Q` -- no unit mismatch.

**Decomposition (industrial_mems, T=60s outage, seeds 500-509, at t0):**

| arm | \|dba\| mean | \|dpsi\| mean | P[ba,psi] cross-cov mean | measured err@t0+60s mean |
|---|---|---|---|---|
| no CAI | 1.086e-01 m/s^2 | 9.63e-3 rad | 1.94e-05 | 103.3 m |
| CAI (outlier OFF) | 4.19e-03 m/s^2 | 6.65e-3 rad | 1.59e-08 | 213.9 m |

CAI cuts the bias-estimate error ~26x but the tilt-estimate error only
~1.4x -- yet net drift gets WORSE. The naive independent-term predictions
(`0.5|dba|T^2`, `g|dpsi|T^3/6`, Sec 2.5) individually and their sum
massively OVERSHOOT the measured error in both arms (e.g. no-CAI: 3594m
predicted vs 103m measured) -- confirming the two error sources do not add,
they partially CANCEL in the true position-error dynamics
(`delta v_dot = [f_n x] psi - C delta_b_a`, Sec 2.4). The `P[b_a,psi]`
cross-covariance the GNSS-only filter builds up is ~1000x larger without
CAI than with it: GNSS-only aiding lets `b_a` and `psi` estimates settle
along a correlated ridge (large individual errors, small combined effect
on `dv`/`dp`), and the filter "knows" this correlation (large cross-P).
CAI's direct, dynamics-independent observation of `b_a` alone rapidly
collapses `Var(b_a)` (hence, since `|Cov| <= sqrt(Var_ba*Var_psi)`, also
collapses the cross-covariance) toward zero, destroying the correlation
structure that let the two individually-large errors cancel in the real
dynamics -- even though CAI's own bias estimate is much closer to truth in
isolation. This is a textbook bias/state-confounding effect, not a fusion
bug.

**Gyro-quality sweep (T=60s outage, industrial_mems accel, seeds 500-509,
mean horizontal error @t0+60s), confirming the corollary (CAI should help
once the gyro is good, per Sec 2.5's "honest expectation"):**

| gyro | no CAI | CAI (outlier OFF) |
|---|---|---|
| industrial_mems (native) | 103.35 m | 213.92 m |
| tactical (mixed w/ industrial_mems accel) | 103.71 m | 174.92 m |
| perfect (zero noise/bias, mixed w/ industrial_mems accel) | 146.93 m | 9.82 m |
| tactical (full grade, both channels) | 7.13 m | 3.49 m |

CAI's benefit strictly improves monotonically as gyro quality improves,
flipping from harmful (MEMS) to strongly beneficial (perfect gyro, tactical
full grade) -- exactly the qualitative and directional prediction of
Master's leading hypothesis and Sec 2.5. Plot:
`results/fusion/cai_h3_gyro_sweep.png`. `python -m pytest
tests/test_fusion_*.py -q` still green after this investigation (no
production code changed).

### CAI-H3 follow-up: NEES consistency check (Master's optimality challenge)

Master's point: a KF with a correct model cannot get expected-worse with an
extra correct measurement; if CAI-outlier-OFF makes MEMS worse, the filter
must be inconsistent for MEMS. Diagnostic (script:
`scripts/cai_h3_investigation.py::nees_diagnostic`, seeds 500-509, T=60s,
no code/parameter changes):

Horizontal position NEES (2 dof, ideal mean=2) and predicted-1sigma vs
actual horizontal error, at t0, t0+30s, t0+60s:

| arm | t0 H-NEES | t0+30s H-NEES | t0+60s H-NEES | t0+60s pred-1sig | t0+60s actual |
|---|---|---|---|---|---|
| industrial_mems, no CAI | 2.01 | 14.48 | 19.49 | 30.1 m | 103.3 m |
| industrial_mems, CAI | 2.07 | 41.45 | 46.83 | 40.5 m | 213.9 m |
| tactical, no CAI | 1.97 | 0.98 | 1.24 | 10.9 m | 7.1 m |
| tactical, CAI | 1.98 | 2.19 | 0.29 | 10.2 m | 3.5 m |

`[psi, b_a]` NEES at t0 against truth (6 dof, ideal mean=6):

| arm | [psi,b_a] NEES @t0 |
|---|---|
| industrial_mems, no CAI | 1107.16 |
| industrial_mems, CAI | 497.30 |
| tactical, no CAI | 68.15 |
| tactical, CAI | 65.39 |

**Both industrial_mems arms are badly inconsistent** (H-NEES up to 23x the
2-dof ideal by t0+60s; `[psi,b_a]` NEES ~100-185x the 6-dof ideal already
AT t0, i.e. before any outage propagation) **while both tactical arms stay
close to nominal** (H-NEES 0.3-2.2; `[psi,b_a]` NEES ~11x ideal, far
smaller than MEMS's ~100-185x). Per Master's interpretation rule: this is
**MODEL MISMATCH for MEMS grade**, not pure estimation-theoretic physics —
CAI is not "wrong" to trust its direct b_a measurement, but the ESKF's
(psi,b_a) joint covariance is already overconfident for MEMS before the
outage even starts, so collapsing it further (CAI) makes the pre-existing
inconsistency worse.

**Likeliest mismatched term:** gyro `scale_factor_std`/`misalignment_std`
(`fedqpnt/sensors/imu.py` `AxisErrorParams`, industrial_mems
gyro=5e-4/3e-4 rad vs tactical gyro=1e-4/1e-4 rad — 3-5x larger, on top of
an 8x larger bias-instability and ARW). These are per-run CONSTANT
multiplicative/cross-axis terms correlated with the vehicle's actual
turn-rate/specific-force history, not a random-walk or GM1 process; the
ESKF process model (Sec 2.4, `F`/`Q_c`) has no state for them (only
`delta_b_g` driven by white noise + GM1). During the 50s pre-outage
maneuvering (needed to excite `b_a` observability, per D-023 item 1), this
unmodelled, dynamics-correlated gyro error aliases into `psi` and, via the
`F[3:6,6:9]=skew(f_n)` / GNSS-update cross-covariance, into `b_a` too, in a
way `Q` cannot represent -- producing a `P` that is too small (overconfident)
for the true joint (psi,b_a) error, well before the outage begins. This is
proportionally much larger for MEMS (3-5x bigger misalignment/scale-factor,
plus 6-8x bigger baseline gyro noise) than for tactical, matching the NEES
gap observed. Not fixed here (no code/parameter changes made, per
instruction) -- flagged as the root-cause candidate for a follow-up: add a
gyro scale-factor/misalignment error state (extension flag analogous to
`fusion.scale_states`) or inflate `q_bg`/kappa_Q for MEMS grade specifically.

**Conclusion: MODEL MISMATCH** (for MEMS grade specifically; tactical grade
is consistent and its CAI benefit -- Sec 2.5's "honest expectation" -- is
on solid estimation-theoretic footing). The earlier "PHYSICS" framing
(cancellation of two correlated errors) is not wrong mechanically, but per
Master's optimality argument it describes a filter that is exploiting a
covariance structure that is itself inconsistent for MEMS -- "lucky
cancellation from an overconfident P", not evidence the CAI-worse-than-
no-CAI result is an unavoidable consequence of correct estimation physics.

### D-028: implemented Q-inflation fix, acceptance NOT met (numbers only, no tuning knob added)

Implemented in `fedqpnt/fusion/eskf.py` (only file touched): dynamics-
dependent process-noise inflation for unmodelled per-run-constant gyro/accel
scale-factor and misalignment error. Per body axis i, each propagate() step:
`extra_g[i] = (sigma_sf_g*|om_i|)^2 + (sigma_mis_g*|om_perp,i|)^2`,
`extra_a[i] = (sigma_sf_a*|f_i|)^2 + (sigma_mis_a*|f_perp,i|)^2`, added to
`Qc[0:3,0:3]` (accel/VRW block) and `Qc[3:6,3:6]` (gyro/ARW block) as
`extra*dt`. `sigma_sf_*`/`sigma_mis_*` read only from `imu.config()`'s
existing `accel_noise_SI`/`gyro_noise_SI` blocks (`scale_factor_std`,
`misalignment_std_rad` -- already exported by `fedqpnt/sensors/imu.py`, no
edit needed there). PSD conversion: a per-run CONSTANT error held over one
step contributes one-step variance `(sigma*x)^2*dt^2`; an equivalent
white-noise PSD `S` with `Qd ~= S*dt` reproduces that same one-step
variance for `S=(sigma*x)^2*dt`, i.e. correlation time = dt (shortest
defensible choice absent a fitted tau_c -- a conservative floor, not an
exact model of the persistent term). Switch `ESKFConfig.model_sf_mis`
(default True). No other file/parameter changed; `python -m pytest
tests/test_fusion_*.py tests/test_sensors_*.py -q` -> 43 passed.

**Numeric check (industrial_mems, typical driving rates om~0.2 rad/s,
f~2 m/s^2): `extra_g*dt=1.36e-10` vs baseline `arw^2=9.78e-9` (~70x
smaller); `extra_a*dt=1.36e-8` vs baseline `vrw^2=6.01e-8` (~4x smaller).**
The dt=0.01s correlation-time conversion (Master-suggested option,
no free constant) makes the added PSD contribution too small to move the
covariance at all.

Re-ran NEES diagnostic and 4-arm gyro sweep post-fix, seeds 500-509,
T=60s -- **numbers are unchanged to within seed noise** (e.g. industrial_mems
no-CAI [psi,ba] NEES @t0: 1107.16 pre-fix vs 1107.02 post-fix; t0+60s
H-NEES: 19.49 vs 19.49; gyro-sweep industrial_mems CAI mean: 213.92m
pre-fix vs 213.93m post-fix). **Acceptance criterion (MEMS H-NEES@t0+60s
<=4, [psi,b_a] NEES@t0<=18) NOT met** -- effectively no improvement.
CAI-effect-after-fix is therefore identical to before: still harmful for
industrial_mems (103.3m->213.9m), still helpful for tactical (7.1m->3.5m).

Per instruction, stopping here without adding a tuning knob. The
dt-based PSD conversion is provably too small at 100 Hz for a
per-run-constant (effectively tau_c=infinity) error: reproducing the true
NEES gap would need a correlation time close to the maneuver/outage
timescale (seconds, not 0.01s), which is exactly the free tuning constant
the instruction forbids introducing without justification from `config()`.
The unmodelled scale-factor/misalignment terms remain the leading model-
mismatch candidate qualitatively (their instantaneous magnitude ratio
between grades still matches the NEES gap's grade-dependence), but a
dt-scale white-noise Q inflation cannot capture a persistent, non-decaying
error's contribution -- a real fix likely needs an explicit scale-
factor/misalignment ESKF state (or a GM1 process with tau_c set to the
sensor's actual scale-factor/misalignment correlation time, which none of
the cited IMU literature specifies -- would itself need a new ASSUMPTION).

### D-030: truth-side ablation to localise the [psi,b_a] NEES mismatch

Master flagged the dt-correlation-time PSD choice in D-028 as wrong (a
per-run CONSTANT error can't be white-noise modelled) -- `ESKFConfig.model_sf_mis`
default flipped to **False** (code kept for ablation only; `fedqpnt/fusion/eskf.py`
is the only file touched). Before proposing any new state, ran a truth-side
ablation (industrial_mems, CAI off, T=60s outage, seeds 500-509,
`scripts/cai_h3_investigation.py::truth_side_ablation`) to localise the
mismatch. **Methodology note:** the first attempt overrode the truth accel/
gyro channel AFTER `ClassicalImu.__init__` had already built the default
one, double-drawing from the RNG stream and shifting noise realisations
between arms independent of the ablated parameter -- invalidated, and
fixed by registering each arm as its own single-construction `ImuGradeConfig`
(no edit to `fedqpnt/sensors/imu.py` itself; `GRADES` dict entries
added/restored at runtime only).

| arm | psi NEES (3dof, ideal 3) | psi roll/pitch (2dof, ideal 2) | psi yaw (1dof, ideal 1) | b_a NEES (3dof, ideal 3) | b_g NEES (3dof, ideal 3) | H-pos NEES @t0+60 (2dof, ideal 2) |
|---|---|---|---|---|---|---|
| (a) as-is | 54.1 | 45.3 | 2.9 | 159.3 | 12.1 | 19.5 |
| (b) scale_factor=0 | 54.2 | 45.3 | 2.9 | 157.8 | 12.0 | 19.7 |
| (c) misalignment=0 | 54.2 | 45.4 | 2.9 | 159.4 | 12.1 | 19.5 |
| (d) both=0 | 54.2 | 45.4 | 2.9 | 157.9 | 12.1 | 19.7 |
| (e) both=0 + no quant/sat | 54.2 | 45.4 | 2.9 | 157.9 | 12.1 | 19.7 |
| (f) bias=GM1+turn-on only | 54.1 | 45.3 | 2.9 | 159.3 | 12.1 | 19.5 |

**Conclusion: NONE of the ablated terms restore consistency** (target
<=3x ideal: psi<=9, b_a<=9, H-pos<=6; all arms stay at 45-70x ideal for
roll/pitch-of-psi and b_a, ~10x for H-pos). Scale-factor and misalignment
(individually and jointly), quantization, and saturation are **ruled out**
-- removing them changes nothing (differences are within seed noise).
Arm (f) is numerically identical to (a), confirming the truth bias process
already matches the filter's GM1+turn-on assumption exactly (as expected:
`rate_random_walk=0` for this grade, and `_AxisChannel`'s GM1 discretisation
already uses the same `sigma_gm`/`theta` the filter's `q_ba`/`tau_a` assume).
Also notable: the mismatch is concentrated in **roll/pitch** (45.3, ~23x its
2-dof ideal) not yaw (2.9, close to its 1-dof ideal) -- i.e. the tilt
components that couple to gravity/specific force via `[f_n x]psi`, not
heading. Per instruction, not proposing a fix or speculating further on the
source; the mismatch survives every truth-side error-budget term tested
here, so if it is a "model mismatch" it is not in the accel/gyro sensor
error terms ablated -- candidates outside this ablation's scope (not
tested): F/Phi second-order-Taylor discretisation error, coning/sculling
residual, the flat-world gravity-gradient term, or the GNSS receiver's
i.i.d.-per-epoch `cov_pos` vs the signal model's actually-correlated
Gauss-Markov residuals (D-023 item 2, same file family, already flagged as
a known LC weakness in ARCHITECTURE.md Sec 2.1).

### D-031: GNSS truth-side ablation (correlated iono/tropo/multipath vs white)

Master's hypothesis: the receiver/filter treat GNSS iono/tropo/multipath
residuals as i.i.d. white per epoch (D-023 item 2) when they are actually
correlated (Gauss-Markov, tau=600/1800/20s) -- a slow drift could look like
acceleration and get misattributed to tilt/b_a with overconfident P.
Tested (industrial_mems, CAI off, T=60s outage, seeds 500-509,
`scripts/cai_h3_investigation.py::gnss_truth_side_ablation`; module-level
function monkeypatch on `fedqpnt.gnss.signal` only -- `fedqpnt/gnss/signal.py`
and `receiver.py` NOT edited on disk; every arm calls the same `rng.normal()`
sites the same number of times, so the D-030 single-construction RNG
discipline holds without extra bookkeeping):

| arm | psi (3dof,ideal3) | psi roll/pitch (2dof,ideal2) | psi yaw (1dof,ideal1) | b_a (3dof,ideal3) | b_g (3dof,ideal3) | H-pos@t0+60 (2dof,ideal2) |
|---|---|---|---|---|---|---|
| (a) as-is, kR=40 | 54.1 | 45.3 | 2.9 | 159.3 | 12.1 | 19.5 |
| (g) iono/tropo/mp OFF (thermal only), kR=40 | 62.6 | 52.9 | 3.0 | 171.5 | 12.2 | 15.9 |
| (h) same as (g), kR=1 | 169.9 | 163.2 | 7.3 | 294.6 | 7.7 | 53.4 |
| (i) correlated ON, tau->1s (same sigma), kR=40 | 54.1 | 45.3 | 2.9 | 159.0 | 12.0 | 19.5 |

Fix-error honesty check (mean reported 1sigma horizontal vs actual horizontal
fix-error std, ordinary non-outage fixes):
`(a) as-is: reported=3.42m, actual=3.03m` (reasonably honest, ~13% high).
`(g) iono/tropo/mp OFF: reported=0.63m, actual=0.64m` (near-exact -- thermal-
only noise genuinely is white, and the receiver's `cov_pos` model matches it).

**Conclusion: correlated GNSS error is NOT the source.** Arm (i) is the
clean test (removes ONLY the temporal correlation, keeps the exact same
marginal sigma) and is **numerically identical to (a)** (54.1/45.3/2.9/
159.0/12.0/19.5 vs 54.1/45.3/2.9/159.3/12.1/19.5) -- collapsing tau from
600-1800s to 1s changes nothing, directly refuting the hypothesis that
epoch-to-epoch temporal correlation (vs. whiteness) drives the [psi,b_a]
inconsistency. Arms (g)/(h) (which also remove the correlated terms'
MAGNITUDE, not just their correlation) get WORSE, not better -- consistent
with `kappa_R=40` implicitly compensating for the larger raw covariance
that arm (g)/(h) removes, producing a new (opposite-direction) miscalibration
rather than a fix. The per-epoch magnitude-honesty check also comes out
reasonably close in the baseline (3.42 vs 3.03m), so the receiver's
`cov_pos` is not grossly dishonest about magnitude either. None of arms
(g)/(h)/(i) bring block-NEES to <=3x ideal. Per instruction, no fix
proposed; GNSS temporal correlation is ruled out as the [psi,b_a] mismatch
source alongside the IMU sensor-error terms ruled out in D-030.

### D-032: arm (i) verification + Q-consistency (pure-INS) test

**1. Arm (i) verification.** Directly confirmed the tau=1s monkeypatch IS
called and DOES change the true process (measured realised per-satellite
iono/tropo/multipath autocorrelation at lag 10s, seed 500, 8 satellites):
default (tau=600/1800/20s mix) = **0.75**; tau=1s override = **0.02** (near
0, as expected for tau=1s at a 10s lag). Re-ran arm (i)'s NEES with the
verified-active patch: psi3=54.1, b_a3=159.0, H-pos@t0+60=19.5 -- **still
numerically identical to (a)** (54.1/159.3/19.5). Not a caching/patch bug;
D-031's conclusion (GNSS temporal correlation is not the [psi,b_a] mismatch
source) stands, now with direct proof the ablation was real.

**2(a). Q parameter table** (`scripts/cai_h3_investigation.py::q_parameter_table`):
no unit-conversion mismatch found. VRW/ARW pass from `fedqpnt/sensors/imu.py`
into `eskf.vrw`/`eskf.arw` unchanged (ARW's deg/sqrt(hr)->rad/sqrt(s) is
already converted correctly in `imu.py`, `/60` for sqrt(hr)->sqrt(s), `*DEG2RAD`
for deg->rad). GM1 `sigma_gm=bias_instability/0.664`, `q_b=2*sigma_gm^2/tau_c`
matches ARCHITECTURE.md Sec 2.4 exactly for both grades. RRW=0 for both
grades (moot). Numbers: industrial_mems `vrw=2.45e-4 m/s^2*sqrt(s)`,
`arw=9.89e-5 rad/s*sqrt(s)`, `q_ba=3.69e-10 (m/s^2)^2/s`, `q_bg=3.41e-11
(rad/s)^2/s`; tactical `vrw=1.47e-4`, `arw=3.64e-5`, `q_ba=1.31e-9`,
`q_bg=3.55e-13` (same units). `Qd = 0.5*(Phi@G@Qc@G.T + G@Qc@G.T@Phi.T)*dt`,
`Phi = I + F*dt + 0.5*(F*dt)^2` (2nd-order Taylor, not exact `expm`).

**2(b). Pure-INS NEES** (no GNSS, no CAI; true initial error drawn from the
filter's own P0 -> exactly consistent prior by construction; seeds 500-519,
`scripts/cai_h3_investigation.py::pure_ins_sweep`; ideal means: psi3~3,
psi_rp~2, psi_yaw~1, v3~3, p3~3, ba3~3, bg3~3):

| grade / course | t | psi3 | psi_rp | psi_yaw | v3 | p3 | ba3 | bg3 |
|---|---|---|---|---|---|---|---|---|
| industrial_mems static | 10s | 6.0 | 4.7 | 1.3 | 8.0 | 6.4 | 8.3 | 8.7 |
| | 60s | 10.0 | 6.2 | 3.9 | 11.6 | 9.5 | 13.7 | 14.4 |
| | 300s | 29.3 | 18.2 | 13.2 | **1740.2** | 311.2 | 150.8 | 157.0 |
| industrial_mems maneuvering | 10s | 6.1 | 4.8 | 1.3 | 8.0 | 6.6 | 8.3 | 8.7 |
| | 60s | 10.0 | 6.1 | 3.9 | 11.4 | 9.5 | 13.7 | 14.4 |
| | 300s | 27.4 | 15.7 | 12.5 | 496.5 | 139.7 | 150.8 | 157.0 |
| tactical static | 10s | 4.6 | 3.5 | 1.1 | 5.7 | 3.0 | 6.3 | 5.9 |
| | 60s | 5.4 | 4.1 | 1.3 | 6.5 | 6.2 | 8.7 | 8.1 |
| | 300s | 11.9 | 8.4 | 3.5 | 14.7 | 10.2 | 43.4 | 40.5 |
| tactical maneuvering | 10s | 4.5 | 3.4 | 1.1 | 4.8 | 2.7 | 6.3 | 5.9 |
| | 60s | 5.3 | 4.0 | 1.3 | 6.2 | 5.6 | 8.7 | 8.1 |
| | 300s | 10.8 | 7.3 | 3.5 | 12.7 | 9.6 | 43.4 | 40.5 |

**DECISIVE: the filter's own Q/Phi discretisation is inconsistent, with NO
GNSS/CAI/receiver involved at all.** Already 1.5-3x ideal by t=10s for both
grades; by t=300s industrial_mems reaches ~10x (psi3), ~580x (v3, static!),
~100x (p3), ~50x (ba3/bg3) their ideal; tactical is milder but still ~4x
(psi3), ~5x (v3), ~3.4x (p3), ~14x (ba3/bg3). This confirms Master's
Q-consistency suspicion and, since it reproduces WITHOUT GNSS or CAI,
rules those out definitively as even a partial cause of the earlier
[psi,b_a] NEES blowup -- it is intrinsic to `fedqpnt/fusion/eskf.py`'s
process-noise model. **No unit-conversion bug found** in the raw
VRW/ARW/GM1 parameter table (2a) -- the mismatch is not "deg vs rad" or
"sigma vs sigma^2" style. The leading remaining candidate is the
**discretisation formula itself**: `Qd = 0.5*(Phi@GQGt + GQGt@Phi.T)*dt`
is a first-order/midpoint approximation to the exact (van Loan) integral
`Phi * Integral_0^dt[Phi(-s) G Qc G^T Phi(-s)^T] ds * Phi^T`; it may
under-count how `psi`/`b_a` process noise couples into `v`/`p` through
`F`'s off-diagonal blocks (`F[3:6,6:9]=skew(f_n)`, `F[3:6,9:12]=-C`) over
each of the ~30,000 accumulated steps -- consistent with `v3` (the state
furthest downstream of that coupling) being by far the worst offender
(580x vs psi3's 10x, static industrial_mems). Not confirmed as an exact
formula bug (no closed-form van Loan re-derivation done here); no fix
proposed or applied, per instruction.

### D-034: t=0 diagnostic check + filter-model-truth arm -> exact culprit found

**Item 1 -- t=0 check (industrial_mems static, seeds 500-519, pure INS):**
right after init/injection, before any propagation: `psi3=2.73 psi_rp=1.78
psi_yaw=0.95 v3=2.41 p3=2.79 ba3=7.51 bg3=7.91` (ideal ~3 for every 3-dof
block). p/v/psi are correctly ~ideal by construction; **b_a/b_g are NOT**
(~2.5x). Root cause found in the DIAGNOSTIC
(`scripts/cai_h3_investigation.py::pure_ins_nees`), not `eskf.py`:
`eskf.initialize_static()` leaves `b_a=b_g=0` (a real cold start has no
bias estimate), but the truth `ClassicalImu`'s `turn_on_bias + bias_gm(0)`
is already a nonzero realised draw at construction. The old code injected
`dx0` on top of `eskf.b_a=0` instead of on top of the TRUE b_a(t0), leaving
an unmatched baseline error of `-true_b_a(t0)` (variance ~`sigma_turnon^2`,
independent of `dx0`) that `P0` never accounted for -- roughly doubling the
b_a/b_g error variance vs what `P0` assumes (matches the observed
NEES ~7.5-7.9, close to 2x the ideal 3). **Fix (test-script only, applied):**
set `eskf.b_a = true_b_a(t0) + dx0[9:12]` (and same for `b_g`) before the
propagation loop. With the fix: `ba3=3.24 bg3=3.38` at t=0 (correct).

**Item 2 -- "filter-model truth" arm** (truth = white VRW/ARW + GM1 +
turn-on ONLY; scale-factor/misalignment/quantization/saturation all 0;
diagnostic bug fixed; industrial_mems static, seeds 500-519):

| t | psi3 | psi_rp | psi_yaw | v3 | p3 | ba3 | bg3 |
|---|---|---|---|---|---|---|---|
| 0s | 2.73 | 1.78 | 0.95 | 2.41 | 2.79 | 3.24 | 3.38 |
| 1s | 2.59 | 1.66 | 0.93 | 2.88 | 2.80 | 3.27 | 3.41 |
| 10s | 2.86 | 2.02 | 0.85 | 3.21 | 2.92 | 3.58 | 3.73 |
| 60s | 4.19 | 2.62 | 1.57 | 4.00 | 3.51 | 5.90 | 6.13 |
| 300s | 12.39 | 7.51 | 5.26 | **391.86** | 67.47 | 65.00 | 67.15 |

Even with truth EXACTLY matching the filter's assumed generative model
(and the diagnostic bug fixed), the filter still becomes badly
inconsistent by t=300s. This rules out SF/misalignment/quant/sat AND the
diagnostic init bug as even partial causes -- the remaining mismatch is
100% intrinsic to `fedqpnt/fusion/eskf.py`.

**Item 3 -- ratio (NEES/dof) vs time, first crossing >2x:** `ba3`/`bg3`
cross ~2x already at **t=60s** (5.90/3=1.97, 6.13/3=2.04); `psi3`/`v3`/`p3`
stay <2x until t=60s (1.40/1.33/1.17) and cross well past that toward
t=300s (4.13/130.6/22.5). **b_a/b_g are the FIRST block to go inconsistent.**

**Item 4 -- exact culprit.** Compared the filter's own `P` (not just NEES)
to the empirical error variance (same seeds): `P_diag(b_a)` at t=60s/300s
= `5.28e-3 -> 4.79e-4` (m/s^2)^2 (per axis) -- **the filter's own reported
b_a variance SHRINKS by ~11x from t=60 to t=300**, while the empirical
(true) error variance stays roughly flat (`1.23e-2 -> 1.24e-2` at one axis).
Same pattern for `b_g` (`1.67e-6 -> 1.55e-7`, ~11x shrink, vs flat empirical
`4.16e-6 -> 4.23e-6`). **This is the exact bug:** `F[9:12,9:12] = -I/tau_a`
and `F[12:15,12:15] = -I/tau_g` (`fedqpnt/fusion/eskf.py::propagate()`,
Sec 2.4) model the ENTIRE b_a/b_g error state as a single mean-reverting
GM1 process with time constant `tau_a`/`tau_g` (200s/200s for
industrial_mems) -- but `P0`'s b_a/b_g variance (Sec 2.9,
`sigma_ba_turnon^2`/`sigma_bg_turnon^2`) is DOMINATED by the turn-on-bias
budget, which in the truth model (`fedqpnt/sensors/imu.py::_AxisChannel`)
is a per-run PERSISTENT CONSTANT (drawn once, never decays) -- NOT part of
the GM1 (`bias_gm`) component. The filter has no state/mechanism to
separate "the turn-on share of the initial uncertainty" (which must NOT
decay) from "the GM1 share" (which correctly does decay with `tau_a`); it
applies GM1 decay to the WHOLE P0 budget, so `P_ba`/`P_bg` relax toward the
tiny GM1 stationary variance (`sigma_gm^2`, e.g. 3.7e-8 for industrial_mems
accel) over about one `tau_a`, while the TRUE error (still containing the
un-decayed turn-on constant) does not shrink correspondingly. `v`/`p` are
the worst-hit blocks (391x/67x by t=300s) because they INTEGRATE the
(increasingly underestimated) `b_a`/`b_g` uncertainty over time through
`F[3:6,9:12]=-C`, `F[3:6,6:9]=skew(f_n)`, `F[6:9,12:15]=C` -- the error
compounds downstream. This is a genuine per-Master-request "unambiguous"
finding, NOT the `Qd` discretisation formula Master already ruled out
(that would be a small, non-systematic per-step error; this is a
structural mismatch between what `P0` represents and what `F`'s decay
term assumes about it).

**Named culprit:** `fedqpnt/fusion/eskf.py`, function `propagate()` (and
by extension `ESKF.initialize_static()`'s `P0` construction, Sec 2.9),
term `F[9:12,9:12] = -I/tau_a` / `F[12:15,12:15] = -I/tau_g`.
**One-line fix (NOT applied, per instruction):** stop mean-reverting the
bias error state -- set `F[9:12,9:12] = 0` and `F[12:15,12:15] = 0` (treat
`b_a`/`b_g` as a pure random walk, matching ARCHITECTURE.md Sec 2.4's own
documented `tau_a=inf` option), since decaying an uncertainty budget that
is mostly a persistent, un-removable constant toward its small GM1
stationary value is not justified until that constant is actually
estimated out. (A more complete fix would split `P0`/`Q` into an explicit
non-decaying "turn-on" sub-budget and a decaying GM1 sub-budget, but the
one-line random-walk change removes the specific bug demonstrated here.)

### D-035: fix applied and revalidated + D-036 single-source check

**Fix applied to `fedqpnt/fusion/eskf.py`:** `ESKFConfig.bias_model: str =
"random_walk"` (new default; `"gm1"` keeps the old pre-D-035 behaviour for
ablation). `propagate()`'s `F[9:12,9:12]`/`F[12:15,12:15]` decay terms
(`-I/tau_a`, `-I/tau_g`) now only apply when `bias_model=="gm1"`; the
default leaves them at 0 (pure random walk). `q_ba`/`q_bg` unchanged.
`config()` reports `bias_model`. `python -m pytest tests/ -q`: 307 total,
305 passed, 2 failed (both pre-existing/unrelated: FL orchestrator timing,
config-hash fixture drift from Master's contract v0.3 bump -- both since
independently addressed by Master/the federation agent, confirmed not
caused by this change).

**2(a) pure-INS revalidation** (industrial_mems + tactical, static +
maneuvering, filter-model-truth + full-truth arms, seeds 500-519, fixed
diagnostic): `ba3`/`bg3` now ~3.1-3.4 at EVERY checkpoint incl. t=300s for
BOTH grades (essentially ideal, down from 65-67x pre-fix) -- **the D-034/
D-035 bug is fixed.** `psi3` also now ~2.6-3.5 at t=300s (down from 12.4x).
**However `v3`/`p3` remain badly inconsistent for industrial_mems at
t=300s: 134-135x (static) / 48-49x (maneuvering)** -- much improved from
before (391x/67x) but NOT meeting the <=2x target. **Tactical grade meets
target cleanly**: v3/p3 ~2.9-3.1 at t=300s, both arms, both courses.
Full numbers (t=0/10/60/300s, all 8 combos) in
`/tmp/d035_2a.log` (not committed; regenerate via
`scripts/cai_h3_investigation.py::pure_ins_nees(fix_init_bias=True, ...)`).

**2(b) 60s-outage NEES + CAI gyro sweep, post-fix, seeds 500-509:**
industrial_mems `[psi,ba]` NEES@t0 dropped from 1107(no-CAI)/497(CAI)
pre-fix to **852/377** post-fix (still far >18=3x-ideal target, consistent
with the residual v/p issue feeding back via 50s of pre-outage GNSS-aided
flight). H-NEES@t0+60s: 13.6(no-CAI)/16.9(CAI) (down from 19.5/46.8
pre-fix). Tactical: 1.15/0.27 (already consistent, unchanged). Outage
error (mean @t0+60s): industrial_mems no-CAI 103.3m->**85.6m**, CAI
213.9m->**107.3m** (CAI-vs-no-CAI gap narrows sharply, from ~2.1x worse to
~1.25x worse, but CAI is STILL worse for MEMS). Tactical: no-CAI 7.1->7.0m,
CAI 3.5->3.3m (CAI still helps, unchanged). 4-arm gyro sweep confirms the
same monotonic-with-gyro-quality pattern as before the fix (perfect gyro:
no-CAI 131.1m -> CAI 9.6m; tactical full grade: no-CAI 7.0m -> CAI 3.3m) --
**H3's qualitative story (CAI helps once gyro quality is adequate) is
unchanged by the fix; only the MEMS no-CAI/CAI magnitudes shrank.**

**2(c) nominal 600s GNSS-aided ANEES, industrial_mems, seeds 500-504:**
`kappa_R=40`: **ANEES=0.98** (ideal ~1.0 -- already excellent, unchanged by
this fix). `kappa_R=1`: **ANEES=23.6** (badly overconfident). **kappa_R
canNOT drop -- it should if anything increase**, the opposite of Master's
expectation; not choosing it, per instruction, just reporting.

**D-036 single-source check** (static, pure INS, one seed, noise-free IMU,
`fedqpnt/fusion/eskf.py`'s `bias_model="random_walk"` default confirmed
active at run time). **Provenance:** output at
`C:\Users\DELL\Downloads\FEDQPNT\results\fusion\d036_single_source_check.log`
(mtime 2026-09-27 14:27), produced by a standalone script
(`/tmp/d036_check.py`, not committed -- calls `fedqpnt.fusion.ESKF`
directly with a hand-built zero-noise `imu_config` dict, bypassing
`ClassicalImu`/`GnssSignalModel` entirely for full determinism).

State index map used by the diagnostic (`p=0:3 v=3:6 psi=6:9 b_a=9:12
b_g=12:15`) matches the ESKF's own layout EXACTLY -- **no index-mapping
bug**. Sign convention `err=est-true` throughout, confirmed consistent.

Results: (i) `delta_b_a_x=0.01`: actual `v_err`/`p_err` match
`-b*t`/`-0.5*b*t^2` to 3+ sig figs at all 3 checkpoints (mechanization is
exact). (iii) `delta_v_x=0.1`: actual matches `v0` (const)/`v0*t` exactly.
(ii) `delta_psi_x(roll)=1mrad`: **couples into Y-velocity**, not X --
`dv_y=-g*psi_x*t` (derived from `skew(f_n)@psi` with `f_n=[0,0,g]`);
magnitude matches `g*psi*t` exactly. **The nominal-state (deterministic)
error propagation is exactly correct in all three arms -- no bug there.**

**But the FILTER'S OWN REPORTED COVARIANCE (`sqrt(diag(P_v))`,
`sqrt(diag(P_p))`) does NOT match the same closed form**, despite this
(v,b_a) subsystem being EXACTLY solvable (F is time-invariant and
nilpotent for this arm: `F^2=0` exactly since psi/b_g stay exactly 0 and
`gravity_gradient('flat')=0`, so `Phi_k=I+F*dt` is the EXACT one-step
solution, and the 30000-fold composition should equal `expm(F*T)`
exactly, i.e. `sqrt(Pv)` should equal `b0*t` and `sqrt(Pp)` should equal
`0.5*b0*t^2` identically, with the SAME numbers as the deterministic
`v_err`/`p_err` above, since `b0` was set equal to the injected value).
Observed: `sqrt(Pv)` matches at t=10s (0.100 vs 0.1) and is close at t=60s
(0.608 vs 0.6, +1.4%), but is **50% too large by t=300s (4.51 vs 3.0)**;
`sqrt(Pp)` similarly diverges (551 vs 450, +22%, by t=300s). Ruled out as
causes: `Qc`/`Qd` contamination (Qc=0 identically in this test, so
Qd=0 exactly), `gravity_gradient` (0 for flat world), the `_hygiene()`
eigenvalue floor (adds 1e-12, ~13 orders of magnitude too small to
explain a 50% effect at P~O(1-500)), and 2nd-order-Taylor truncation
(provably exact here since `F^2=0`, so `Phi_k` is exact, not approximate,
at any `dt`). **The mismatch grows over time (near-exact at t<=60s, large
by t=300s) rather than being a fixed per-step error, and appears
consistently in BOTH `P_v` and `P_p` by a similar relative factor** --
consistent with Master's hypothesis "a coupling term is mis-scaled for
velocity" (item 2 of D-036's own two candidate explanations), but the
EXACT mis-scaled line/term was NOT isolated within this pass (budget
constraint) -- ruling out the candidates above narrows it to somewhere in
`propagate()`'s discrete `Phi`/`Qd` construction or composition for the
full 15x15 system (not reproducible from the isolated 2x2 (v,b_a) analytic
subsystem in symbolic terms, since that subsystem is provably exact; the
discrepancy must come from how the CODE composes/accumulates the full
matrix over the run, not from the (v,b_a) sub-block's own math). This
explains the residual v3/p3 NEES excess found in 2(a) for industrial_mems
(large `sigma_ba_turnon`) while tactical's much smaller values keep the
same relative excess numerically negligible at these time horizons. No
fix proposed or applied, per instruction.

### D-038 (FILTER-GNSS agent, seeds 500-504/509, script `scripts/filter_gnss_d038.py`)

**Item 3 (prime): receiver cov_vel honesty.** Bypassed the ESKF entirely
(GnssSignalModel + GnssReceiver only), 5 seeds x 600s, static and dynamic
industrial_mems: reported mean sqrt(diag cov_vel) vs actual (fix.vel-truth.vel)
std, ratio (E,N,U) = [0.975, 1.010, 1.001] -- **honest to ~2.5%**. Normalized
vel-err^2 (3dof diag) mean=3.033 vs ideal chi2_3 mean=3.0; lag-1s
autocorrelation of vel-error ~0.001 (white). Static and dynamic arms are
numerically identical (expected: WLS cov = inv(H^T W H) depends only on
geometry/weights, not on platform speed, for a linear-in-velocity Doppler
model). Code-level cross-check: `receiver.py::_weight_vel` weights by
`doppler_thermal_sigma_mps(cn0)^2` only (thermal), which matches
`signal.py`'s truth generator -- the ONLY per-epoch stochastic term added to
`pseudorange_rate` there is thermal Doppler noise (clock drift is a
jointly-estimated smooth state via the shared clock column, not injected
per-epoch noise; no satellite-velocity error term exists in the truth model
at all). **VERDICT: cov_vel is NOT the cause of GNSS-aided overconfidence --
the D-038 "prime suspect" is ruled out.**

**Item 3 continued: kappa_R sweep with honest-vel split** (5 seeds x 310s,
industrial_mems, ESKF block ANEES p/v/psi_rp/psi_yaw/ba/bg at 60s/300s, test-
local `_SplitKappaESKF` subclass -- `fedqpnt/fusion/eskf.py` NOT edited):
- kappa_R=1 (pos+vel): p=33.4/16.9, v=24.2/3.6, psi_rp=44.3/6.3, psi_yaw=7.7/5.8,
  ba and bg ANEES astronomically large (1e6-1e10) at both checkpoints.
- kappa_R=40 (pos+vel): p=0.92/0.77, v=1.71/0.32 (good), but psi_rp=12.4/10.4
  and ba/bg STILL huge (1e8-1e9) -- **the ANEES=0.98 headline number from
  D-035 is a 6-dof average dominated by well-behaved p/v; it masks severe,
  still-unresolved b_a/b_g (and psi) overconfidence even at kappa_R=40.**
  (ba/bg magnitudes in the 1e6-1e10 range likely reflect P_ba/P_bg collapsing
  toward the `_hygiene()` 1e-12 eigenvalue floor under sustained GNSS
  aiding while the true bias error stays ~1e-2; not independently verified
  this pass -- flagged, not confirmed, no fix proposed.)
- kappa_pos=1, kappa_vel=(measured ratio)^2=0.991 (near-unity, i.e. "honest"
  vel R, negligible extra inflation): p=33.5/17.0, v=24.3/3.6, psi_rp=44.3/6.3,
  ba/bg similarly huge -- **essentially IDENTICAL to kappa_R=1 on both.**
  **VERDICT: honest R_vel does NOT restore consistency at kappa_R~=1 on
  position. kappa_R=40 remains necessary for reasons unrelated to velocity
  covariance** (consistent with Item 3's honesty finding above -- there was
  never a velocity-covariance error to fix).

**Item 1 (D-038 hyp. 1, MEMS linearisation-limit): NOT confirmed -- test as
run is inconclusive, methodological gap found.** Pure-INS run initialised
`eskf.b_a`/`eskf.b_g` to the EXACT true bias at t=0 (no P0-consistent dx0
draw, unlike D-034's convention), which cancels the turn-on-bias
contribution to tilt by construction. Result: measured |tilt| at 300s is
only ~0.024 rad (native gyro) vs the ~0.5 rad assumed in the D-038 hypothesis
write-up, and is essentially UNCHANGED (0.025 rad) with gyro turn-on sigma
scaled /10 -- i.e. turn-on bias is NOT the driver of the measured tilt in
this setup, because the test cancelled it at init. v/p ANEES at 300s came
out ~0.00 for both arms (native and /10), which is an artifact of near-zero
injected error against large P0-turnon-derived P, not a meaningful
consistency measurement. **This item needs a re-run with a proper
P0-consistent dx0 draw (as in D-034/`pure_ins_nees`) before the
linearisation-limit hypothesis can be confirmed or refuted -- not done this
pass per Master's park directive (D-046); flagging only.**

**Owner's decision (D-046):** GNSS-aided overconfidence issue PARKED by
user; kappa_R=40 stays provisional. No fix applied to `fedqpnt/fusion/eskf.py`
or `fedqpnt/gnss/*` this pass. Script `scripts/filter_gnss_d038.py` staged
(git add, not committed); per-task JSON results under
`results/fusion/d038_*.json`.
