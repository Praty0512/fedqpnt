# Sensor models -- raw notes (WP-2.1/2.2/2.3), owned by QUANTUM-SENSOR

## Equations

Quantum accel (fedqpnt/sensors/quantum.py): phi = k_eff * a * T^2 (k_eff = 2*(2pi/780.24nm) ~= 1.6098e7 rad/m,
Rb-87 D2, two-photon Raman). Fringe ambiguity resolved via classical-sensor
hybridization: a_hybrid = a_wrapped_meas + fringe_period * round((a_coarse - a_wrapped_meas)/fringe_period),
fringe_period = 2pi/(k_eff*T^2) (Lautier 2014; Cheiney 2018). Contrast:
C(Omega) = C0*exp(-(Omega_perp/Omega_c)^2), valid=False if C<threshold or |a|>dynamic_range.
Response window (contract v0.2 C-2): triangular over [t-2T, t], peak at
t-T; degenerates to boxcar-of-1-sample when dt(0.01s)>2T (all grades here).
Bias: first-order Gauss-Markov (GM1), tuned so ADEV peak = 0.664*sigma_gm = B (cited floor).
Outlier/fringe-jump channel (D-019): 2-state Gilbert-Elliott Markov chain per axis,
added on top of (not instead of) shot noise; valid stays True in the bad state.

IMU (fedqpnt/sensors/imu.py): meas = misalign*(true*scale_factor) + turn_on_bias +
bias_gm(GM1) + bias_rrw(integrated white) + white(N/sqrt(dt)), then quantize+clip.

Allan deviation (fedqpnt/sensors/allan.py): standard overlapping estimator
(NIST SP1065). Noise-coefficient fit: nonlinear least squares of
AVAR=N^2/tau + AVAR_GM1(sigma,tau_c) + K^2*tau/3 to the curve (log-domain,
weighted by sqrt(n_clusters)). NOTE: AVAR_GM1(tau,sigma,tau_c) = 2*sigma^2*tau_c/tau*
[1-(tau_c/2tau)(3-4e^-x+e^-2x)], x=tau/tau_c -- the standard textbook formula
is missing this factor of 2 (verified here by Monte-Carlo simulation of a
GM1 process against overlapping_adev, matched to <1% once included; without
it every B estimate below was off by a self-consistent sqrt(2)=41%). Fitting
a flat term (linear regression) or reading the curve's raw minimum are BOTH
wrong for a GM1-dominated curve (it's a hump, not a bathtub); both were
tried and rejected (see git history) before the nonlinear GM1 fit.

## Parameter table (grade | value | unit | source | fig/page | lab/field/ASSUMPTION)

### Quantum accelerometer

| Param | lab | field | near_future | Source |
|---|---|---|---|---|
| T_interrogation | 2ms | 10ms | 4.5ms | lab: Lautier 2014 (2T=4ms); field: Jarlaud 2024 D-019 (2T=20ms, measured, paper's own static condition); near_future: Wu 2022 Nat.Commun 13:1442 (T=0-4.5ms) |
| cycle_time | 1s | 1.548s | 0.1s | lab: Wright 2022 "0.5Hz-few Hz" (representative); field: Jarlaud 2024, measured PER-SHOT combined kD/kU cycle period (D-020; corrects D-014/D-019's use of 2.955s, the per-k-direction interval -- our model does not simulate k-dependent systematics); near_future: Wu 2022 (10Hz) |
| sensitivity (m/s^2/sqrt(Hz)) | 2e-3 | 6.84e-5 | 2e-5 | lab: Lautier 2014 APL 105:144102 @2T=4ms; field: Jarlaud 2024 D-019/D-020 sigma_robust=5.60ug @2T=20ms (95%CI[5.04,6.40]ug, paper-implied 5.06ug ratio 1.11), N=sigma*sqrt(cycle) with cycle=1.548s PER-SHOT (D-020); near_future: derived from Wu 2022 Delta-g/g=2e-6, ASSUMPTION reinterpretation |
| bias_instability (m/s^2) | 7e-7 | 3e-6 | 5e-6 | lab: Wright 2022 Frontiers Phys 10:994459 (cited, lab); field/near_future: ASSUMPTION (no atom-only long-tau floor resolvable from available shot counts; explicitly NOT the classical-MICAL ADEV floor, D-014) |
| contrast0 | 0.394 | 0.394 | 0.394 | MEASURED, Jarlaud 2024, rigid mode, 2000 shots, Fig.2 runs (D-014); reused across grades pending grade-specific measurement |
| Omega_c (rigid) | 0.434 rad/s (scaled) | 0.01734 rad/s (scaled) | 0.0857 rad/s (scaled) | all scaled from MEASURED 48.2+-2.5 mrad/s @ T_ref=6ms, 2T=12ms (D-014) via Omega_c=Omega_c_ref*(T_ref/T)^2 (physics-derived 1/T^2 law, D-020: Coriolis phase ~ Omega*T^2, so Omega_c ~ 1/(k_eff*sigma_v*T^2); corrects D-014's self-contradictory 1/T law, a Master error; only one measured (T,Omega_c) pair exists) |
| Omega_c (inertial pointing) | n/a | 0.198 rad/s | 0.198 rad/s | ASSUMPTION: back-solved so C(0.25 rad/s)=threshold, matching paper's stated 250mrad/s inertial-pointing operating limit (D-014); no independent fit exists in the processed dataset |
| outlier stationary rate | 0 (off) | 0.0896 | 0 (off) | MEASURED, Jarlaud 2024, 2T=20ms, n=491, 44 outliers, 95%CI[6.7,11.8]% (D-019) |
| outlier persistence P(bad\|prev bad) | -- | 0.659 | -- | MEASURED, Jarlaud 2024, adjacency_rate_among_outliers, 2T=20ms (D-019) |
| outlier magnitudes | -- | 44 empirical values, 30-269 ug | -- | MEASURED, data/processed/jarlaud2024/atom_outliers.json (D-019) |
| scale_factor_std, dynamic_range, coarse-sensor noise/bias, bias_tau_c, contrast_threshold | various | various | various | ASSUMPTION (plausible ranges), not independently cited |

### Classical IMU

| Param | consumer (BMI088) | industrial (ADIS16470) | tactical (HG1700 AG58) | Source |
|---|---|---|---|---|
| accel VRW | 180 ug/sqrt(Hz) | 25 ug/sqrt(Hz) | 15 ug/sqrt(Hz) | consumer: Bosch datasheet BST-BMI088-DS001 (+-6g range); industrial/tactical: ASSUMPTION (not located in accessible excerpts) |
| accel bias instability | 10 mg | 13 ug | 30 ug | consumer: Bosch product flyer BST-BMI088-FL000 (ASSUMPTION-grade, not formal datasheet table); industrial: ADIS16470 datasheet Rev.C (cited); tactical: ASSUMPTION |
| gyro ARW | 0.014 dps/sqrt(Hz) | 0.34 deg/sqrt(hr) | 0.125 deg/sqrt(hr) | consumer: Bosch datasheet (cited); industrial: ADIS16470 datasheet Rev.C (cited); tactical: Honeywell HG1700 datasheet M61-0115-000-003 AG58 (cited) |
| gyro bias instability | 1.0 deg/h | 8 deg/h | 1 deg/h | consumer: Bosch flyer (ASSUMPTION-grade); industrial: ADIS16470 datasheet (cited); tactical: Honeywell datasheet AG58 (cited) |
| MICAL real-noise replay | -- | available (all grades) | -- | Jarlaud 2024 Thales MICAL classical accelerometer, data/processed/jarlaud2024/mical_static_residuals.npz, fs=2565.7Hz, std=6.86mg (D-014 item 3; classical-only, never used for the quantum sensor) |

## Validation numbers (this session, seed=42/various, real runtime)

- IMU: 8 simulated hours/grade/channel (6 combos), nonlinear GM1+white ADEV
  fit vs cited N (ARW/VRW) and B (bias instability): errN < 0.2%, errB < 6%
  (all 6 combos), well within +-30%. Runtime ~11-32s per simulated hour.
- Quantum: 1 simulated hour/grade for white-noise sensitivity (outlier
  channel off for this check): all 3 grades pass +-30%. Bias-instability
  floor validated in isolation (GM1 process alone, since white >> bias by
  ~50-2900x for the cited numbers -- the joint floor is only visible after
  tens to ~100 days of continuous operation, infeasible in test time; this
  is flagged, not hidden). Field-grade sigma_shot (model AND replay modes)
  within 15% of the measured 5.60 ug figure. Outlier channel: stationary
  rate and persistence reproduced within +-2%/+-10% over 22,000 shots.
  Runtime ~0.8-1.2s per simulated hour (field/lab), faster for near_future.
- `python -m pytest tests/test_sensors_quantum.py tests/test_sensors_imu.py`:
  27 passed in 429.5s.

## Limitations

- dt=0.01s (100Hz, D-003) is coarser than 2T for every quantum grade here,
  so the triangular response window degenerates to "use the nearest truth
  sample" in practice; the correct weighting code path exists but is
  effectively untested at 2T>dt.
- Field-grade quantum bias_instability has no atom-only measured floor;
  ASSUMPTION only.
- Omega_c 1/T^2 scaling (D-020) rests on a single measured (T, Omega_c) pair;
  unverified outside T~6ms.
- Outlier burst rate is not modulated by rotation dynamics even though the
  real dataset suggests bursts cluster near rotation zero-crossings
  (D-019 item 2, explicitly deferred, not modelled).
- IMU accel figures for tactical (HG1700) grade are ASSUMPTION (accelerometer
  spec sheet not located); gyro figures are cited.
- consumer_mems (BMI088) bias-instability figures are vendor-flyer, not the
  formal datasheet table (ASSUMPTION-grade per Bosch's own document split).
