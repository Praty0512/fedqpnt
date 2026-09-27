# FedQPNT — System Architecture Specification (WP-1.1)

_Author: ARCHITECT agent · 2026-09-23 · Spec v1.0 · against data contract v0.1 (`fedqpnt/core/*`)_

Status of every numeric default in this document: **[LIT]** = taken from the cited source;
**[DESIGN]** = derived from other defaults by the stated formula; **[ASSUMPTION]** = engineering
choice, must get a sensitivity sweep before the paper (D-002). Every default is a config field;
names in `code_font` are the config keys later agents must use.

Conventions follow D-003 and `types.py`. Throughout, `δx = x̂ − x` (estimate minus truth), `[a×]` is
the skew matrix, `Exp/Log` are the SO(3) exponential/logarithm, `C ≡ R_nb` (body→ENU).

---------------------------------------------------------------------------------------------------

## 0. Clarifications of contract v0.1 used by this spec (see §10 for proposed changes)

* **Euler convention (strict).** `C = Rz(ψ)·Ry(θ)·Rx(φ)`, right-handed elementary rotations.
  With FLU body axes this means: ψ = 0 ⇒ nose points **East**, ψ increases **counter-clockwise** (toward
  North); **θ > 0 ⇒ nose DOWN** (body x-axis in ENU is `[cψcθ, sψcθ, −sθ]`); φ > 0 ⇒ left wing up.
  This is the REP-103 convention (https://www.ros.org/reps/rep-0103.html). Body rates ↔ Euler rates:
  `p = φ̇ − ψ̇ sθ`, `q = θ̇ cφ + ψ̇ cθ sφ`, `r = −θ̇ sφ + ψ̇ cθ cφ` (pure algebra of the Z-Y-X
  composition, frame-name independent).
* **IMU samples are point samples** of `f_b(t_k)`, `ω_b(t_k)` at the tick time (not Δv/Δθ increments).
* **World model v1 = flat, non-rotating, uniform-gravity tangent plane** (§2.6 justifies it and says when to
  switch it off). Truth, sensor models and the filter all use the same world, so it adds no modelling error.
* **Node boundary.** A node has an **Environment** half (truth, sensor models, GNSS signal, attacks) and an
  **Agent** half (receiver, fusion, trust, detector, FL client). Only sensor outputs cross from Environment to
  Agent. `AttackLabel`, `TruthState` and `GnssEpoch.meta` never do (§4.4 says how this is enforced).

---------------------------------------------------------------------------------------------------

## 1. Module map and per-tick dataflow

### 1.1 Packages

| Package | Owner | Contents |
|---|---|---|
| `fedqpnt/core` | Master | contracts, seeding |
| `fedqpnt/sim` | ARCHITECT→impl agent | `rotations.py`, `trajectory.py`, `strapdown.py`, `config.py`, `recorder.py` (WP-1.2); later `node.py` (Environment + Agent step loop), `runner.py` (orchestrator, WP-8.1) |
| `fedqpnt/sensors` | QUANTUM-SENSOR | `ImuModel`, `QuantumSensorModel` |
| `fedqpnt/gnss`, `fedqpnt/attacks` | ATTACK | `GnssSignalModel`, `GnssReceiver`, `GnssAttack` |
| `fedqpnt/fusion` | FUSION+TRUST | `ekf.py` (ES-EKF §2), `features.py` (§3.1) |
| `fedqpnt/trust` | FUSION+TRUST | `detector.py` (torch model §3.2), `law.py` (trust dynamics §3.3), `pseudolabel.py` (§4.3) |
| `fedqpnt/fl` | FEDERATED | `client.py`, `server.py`, `aggregators.py`, `comms.py`, `proc.py` (§4, §8) |
| `fedqpnt/baselines` | BASELINE | method presets = config diffs only (§5) |
| `fedqpnt/eval` | EVALUATION | `metrics.py` (§6), `stats.py` (§7) |

### 1.2 Rates (defaults)

| Stream | Rate | Key | Source |
|---|---|---|---|
| Global tick / IMU | 100 Hz (`dt = 0.01`) | `sim.dt`, `imu.rate_hz` | D-003 |
| GNSS epoch → `GnssFix` | 1 Hz default; {1, 2, 5, 10} Hz | `gnss.rate_hz` | [ASSUMPTION] typical receiver PVT rates |
| Quantum (CAI) | 1/T_c, T_c ∈ [0.5, 2] s; default T_c = 1 s | `quantum.cycle_time` | [LIT] Cheiney 2018, Templier 2022 (sub-Hz to few-Hz cycle rates) |
| Nav output logged | 10 Hz (every 10th tick) | `rec.nav_decimation = 10` | [DESIGN] metrics are evaluated at 10 Hz |
| FL round | every `T_round = 60 s` sim time | `fl.round_period_s` | [ASSUMPTION] |

A component returns `None` when it has no output at a tick. Non-integer periods (e.g. T_c = 0.73 s): the
component emits at the first tick `t_k ≥ t_sched` and stamps the sample with its own `t`. Downstream code
**always uses `sample.t`**, never the tick index.

### 1.3 Per-tick sequence at tick k (t = k·dt), one node

```
ENVIRONMENT                                           AGENT
truth_k = traj.state(k)
imu_k  = imu.step(truth_k, rng_imu)        ─────────► (a) ekf.propagate(t, imu_k)
q_k    = quantum.step(truth_k, rng_q)      ─────────► (b) ekf.buffer / quantum innovation
ep_k   = gnss.step(truth_k, rng_gnss)
if ep_k: ep_k = attack_n(...attack_1(ep_k))
         label_k -> recorder ONLY
         ep_k' = replace(ep_k, meta={})    ─────────► (c) fix_k = receiver.solve(ep_k')
                                                       (d) innov = ekf.innovations(t, fix_k, q_k)   # ν, S, NIS; nominal R
                                                       (e) x_k  = features.update(t, fix_k, q_k, innov, nav_{k-1})
                                                       (f) p_k  = detector(x_k)  (at GNSS epochs only)
                                                       (g) trust_k = trust_law.update(t, p_k, innov, q_k)
                                                       (h) nav_k = ekf.correct(t, innov, trust_k)   # R_eff(w)
                                                       (i) pseudolabeler.push(t, x_k, innov); fl_client.buffer(...)
                                                       (j) if t crosses a round boundary: FL exchange (§4, §8)
recorder: truth_k, label_k (evaluation streams)        recorder: nav_k, trust_k, p_k, innov, features
```

Feedback into trust: the innovations (d) are computed against the INS prior, which carries all previous
trust-weighted corrections, so trust at k depends on trust at k−1 through the navigation state. Steps (d)–(h)
need the innovations before the correction. Contract v0.1 cannot express this (see §10, C-1).

### 1.4 How `None` and dropouts are handled

| Event | Rule |
|---|---|
| `imu_k is None` (dropout) | ZOH on the last IMU sample; `Q_d` scaled by `κ_zoh = 10` for that step; if gap > `imu.max_gap_s = 0.1 s` then event `IMU_GAP` and `w_imu` target → `w_min` for the gap. [ASSUMPTION] |
| `fix_k is None` (no epoch at this tick) | nothing; trust held. |
| `fix.valid == False` or no fix for > `max(3/f_gnss, 1 s)` | no GNSS update; `gnss_outage` feature = 1; trust frozen (no evidence either way); event `GNSS_OUTAGE`. |
| First valid fix after an outage longer than `T_gap = 5 s` | **reacquisition cap** `w_gnss ← min(w_gnss, w_reacq = 0.5)`, then normal recovery (§3.3). Rationale: reacquisition right after jamming is the classic spoofer capture moment (Psiaki & Humphreys 2016). |
| `q_k is None` | nothing. `q.valid == False` → no CAI update; the contrast feature still enters quantum trust. NaN axes in `q.f_b` → those rows are dropped from H. |
| Missing global model (comms) | the node keeps its last detector. Navigation never waits on comms. |

---------------------------------------------------------------------------------------------------

## 2. Fusion filter: error-state EKF (shared by ALL methods)

### 2.1 Coupling decision: loosely-coupled PVT + innovation/RAIM monitoring (v1). Tightly-coupled is the planned v1.5.

I **agree with loosely-coupled (LC) for v1**, with one caveat:

* For LC: the ATTACK agent's receiver already produces `GnssFix` with `raim_stat`, `residual_rms`, C/N0 and AGC.
  The attacks planned for v1 (full-constellation drift spoof, meaconing/replay, CW and wideband jamming)
  show up in PVT, clock and C/N0/AGC features. With LC the filter is 15-state, fast, and identical across
  methods. Innovation monitoring on position and velocity plus RAIM χ² gives both a per-fix consistency
  check and a within-fix one.
* Against LC, and why it matters here: (i) under partial jamming with fewer than 4 satellites, LC gets **no**
  aiding while TC still uses 1–3 pseudoranges; (ii) a spoofer that captures a **subset** of satellites is
  partly absorbed into the WLS fix. RAIM sees it, but the EKF cannot exclude individual satellites; (iii) LC
  fixes have time-correlated errors (troposphere, multipath). **Mitigation in v1:** the fix covariance is
  scaled by one factor `κ_R`, tuned on *tuning seeds only* for all methods alike so that nominal ANEES ≈ 1
  (§7.4). **No GNSS error-state (Gauss–Markov) is added**, because a slow drift spoof would be absorbed into
  it as "correlated error". That is a known way to become blind to spoofing, so it is deliberately avoided.
* **v1.5 (TC):** the state layout reserves indices 15–16 for receiver clock bias and drift `[δb_c (m), δḃ_c (m/s)]`.
  The trust interface is per-sensor, so switching to TC changes the measurement model only. Recommended as an
  extension only if S3 (partial jamming) shows LC outages dominate the error budget.

### 2.2 State

Nominal state: `p ∈ ℝ³` (ENU), `v ∈ ℝ³`, `C ∈ SO(3)` (stored as a unit quaternion), `b_a ∈ ℝ³`, `b_g ∈ ℝ³`.
Error state (n = 15):

```
δx = [ δp(0:3), δv(3:6), ψ(6:9), δb_a(9:12), δb_g(12:15) ]      ψ: nav-frame attitude error, Ĉ = (I − [ψ×]) C
optional: δk_a(15:18) accel scale factor   (fusion.scale_states = False by default)
TC extension: δb_c, δḃ_c appended          (fusion.coupling = "loose")
```

**No quantum-sensor bias state in v1.** CAI bias is ~1e-7–1e-8 g, below everything else in the budget.
It is weakly observable (only against GNSS-aided `b_a`), so it is folded into the CAI measurement noise.
CAI faults (S6) are handled by quantum trust (§3.5) instead. Extension flag `fusion.cai_bias_state`
adds `δb_Q (3)` as a random walk.

### 2.3 Mechanisation (IMU rate; same as `sim/strapdown.py` "causal" mode)

With `f̂ = f̃_k − b̂_a`, `ω̂ = ω̃_k − b̂_g`, `g_n = (0,0,−G0)`:

```
C_{k+1} = C_k · Exp( ½(ω̂_k + ω̂_{k+1}) Δt  +  (1/12)(ω̂_k × ω̂_{k+1}) Δt² )      # trapezoid + coning term
v_{k+1} = v_k + ( ½(C_k f̂_k + C_{k+1} f̂_{k+1}) + g_n ) Δt
p_{k+1} = p_k + ½ (v_k + v_{k+1}) Δt
```
In real time the filter only has sample k when it propagates k→k+1. The causal implementation therefore
integrates interval [k−1, k] on arrival of sample k, which adds one tick (10 ms) of latency. Offline validation
uses the 4th-order scheme in §11.3.

### 2.4 Process model (continuous time, δx = x̂ − x)

Using `f̂ = f + b_a + w_a − b̂_a = f − δb_a + w_a`, `ω̂ = ω − δb_g + w_g`, with `f_n = Ĉ f̂`:

```
δṗ   = δv
δv̇   = [f_n ×] ψ − Ĉ δb_a + Ĉ w_a
ψ̇    =  Ĉ δb_g − Ĉ w_g
δḃ_a = −δb_a/τ_a + w_ba          (τ_a = ∞ ⇒ random walk)
δḃ_g = −δb_g/τ_g + w_bg
```
```
F = [ 0  I  0        0      0    ]      G = [ 0   0   0  0 ]     w = [w_a, w_g, w_ba, w_bg]
    [ 0  0  [f_n×]  −Ĉ      0    ]          [ Ĉ   0   0  0 ]
    [ 0  0  0        0      Ĉ    ]          [ 0  −Ĉ   0  0 ]
    [ 0  0  0   −I/τ_a      0    ]          [ 0   0   I  0 ]
    [ 0  0  0        0  −I/τ_g   ]          [ 0   0   0  I ]
Φ_k = I + FΔt + ½(FΔt)²        Q_d = ½(Φ G Q_c Gᵀ + G Q_c Gᵀ Φᵀ) Δt
Q_c = blkdiag( VRW² I, ARW² I, q_ba I, q_bg I )
q_b = 2 σ_BI² / τ_c   (first-order Gauss–Markov with bias instability σ_BI, correlation time τ_c)
    = σ_RW²           (random walk with rate-random-walk density σ_RW)
```
VRW [m/s/√s], ARW [rad/√s], σ_BI and τ_c come from the IMU model's `config()` (QUANTUM-SENSOR owns the values
and their citations). The filter reads them and does not re-invent them. `Q_c` is scaled by `κ_Q = 1`
[ASSUMPTION; swept].

Covariance hygiene each step: symmetrise `P ← ½(P+Pᵀ)`; if `min eig(P) < 1e-12`, add `1e-12·I`.
Corrections use the Joseph form.

### 2.5 Measurement models

All innovations are formed as "measured error" `ν = z − H·0` (after each reset `δx̂⁻ = 0`).

**GNSS position (LC):** `ν_p = p̂⁻ − p_gnss`, `H_p = [I₃ 0 0 0 0]`, `R_p = κ_R · fix.cov_pos`
(fallback `diag(3², 3², 5²) m²` if `cov_pos` is not SPD).
**GNSS velocity:** `ν_v = v̂⁻ − v_gnss`, `H_v = [0 I₃ 0 0 0]`, `R_v = κ_R · fix.cov_vel` (fallback `(0.1 m/s)² I`).
Lever arm = 0 [ASSUMPTION]. Position and velocity are processed as one 6-D update.

**Cold-atom hybridisation (CAI → classical accel bias).** This follows the hybrid matter-wave / classical
accelerometer approach: the classical sensor gives bandwidth, and the atom interferometer's absolute,
low-bias output estimates the classical bias (Lautier et al. 2014, APL 105:144102,
doi:10.1063/1.4897358; Cheiney et al. 2018, Phys. Rev. Applied 10:034030,
doi:10.1103/PhysRevApplied.10.034030; 3-axis version: Templier et al. 2022, Sci. Adv. 8:eadd3854,
doi:10.1126/sciadv.add3854; INS-level study: Wang et al. 2021, arXiv:2103.09378). For a CAI sample over
window W with response weights `g(t)` (∫g = 1):

```
f̄_Q        = q.f_b                                     (CAI output, = ∫ g f_b dt + b_Q + η_Q)
f̄_IMU      = Σ_{t_i ∈ W} g(t_i) (f̃_i − b̂_a) Δt         (same-window weighted mean of corrected IMU samples)
ν_Q        = f̄_Q − f̄_IMU  ≈  δb_a + (b_Q + η_Q − η̄_IMU) (+ diag(f̄) δk_a if scale states on)
H_Q        = [0 0 0 I₃ 0]  (rows of NaN axes removed)
R_Q        = diag(q.variance) + (VRW²/T_W) I + σ_win² I
```
* `W`, `g`: if the CAI model exposes the interrogation time T (proposed C-2), use the Mach–Zehnder
  triangular sensitivity over `[t − 2T, t]`. Otherwise use a boxcar over `[t − cycle_time, t]`. The IMU buffer
  length is `max(5 s, 2·cycle_time)`.
* `σ_win = 1e-5·G0` [ASSUMPTION] covers the window/weighting mismatch and sensor misalignment. It is swept
  over {1e-6, 1e-5, 1e-4}·G0.
* **Key property:** both instruments sense the *same* specific force, so gravity-model error, attitude error
  and the trajectory all **cancel** in `ν_Q`. The measurement is a direct, dynamics-independent observation
  of the classical accelerometer bias.
* No update if `q.valid == False` or `w_q < w_excl`.
* **Honest expectation:** the CAI bounds `δb_a`. During GNSS denial, horizontal error from gyro-driven tilt
  grows as `g ε_g t³/6`, while accelerometer bias error grows as `δb_a t²/2`. For MEMS gyros (ε ≥ 10°/h)
  tilt dominates within about 60 s, so the CAI benefit is expected to be **small for MEMS and significant
  for tactical/navigation-grade gyros**. The evaluation must report both grades (`imu.grade ∈ {mems, tactical}`)
  and must not select the favourable one after the fact (D-002).

### 2.6 Earth rotation, transport rate, Schuler: do they matter at CAI bias levels?

Magnitudes, with Ω_ie = 7.292115e-5 rad/s, R⊕ = 6.371e6 m, v = 20 m/s:

| Effect | Size | vs CAI bias 1e-7 g ≈ 1e-6 m/s² |
|---|---|---|
| Coriolis `2Ω×v` | ≈ 2.9e-3 m/s² | ~3000× larger |
| Earth rate seen by gyros | 15 °/h | > tactical gyro bias (≈1 °/h) |
| Transport rate v/R⊕ | 3.1e-6 rad/s | ≈ 0.65 °/h |
| Horizontal gravity over 10 km (tangent-plane curvature) | g·10⁴/R⊕ ≈ 1.5e-2 m/s² | huge |
| Schuler period | 84.4 min | changes error growth from t² to bounded oscillation |

**Conclusion.** In the real world all of these matter at the CAI bias level. Coriolis and Earth rate are
deterministic and compensated in any real mechanisation, so they do not change the *comparison between
methods*. The flat, non-rotating world is therefore acceptable for v1 **only because truth, sensors and filter
share it exactly**. What it distorts is the **free-inertial error growth over long horizons**. Without Schuler
feedback, an accelerometer bias error b gives `½ b t²` (6.5 m after 1 h for b = 1e-6 m/s²) instead of a
bounded `b/ω_s² ≈ 0.65 m` oscillation. So the flat model is **pessimistic** about long outages and **optimistic**
about nothing we measure short-term.

**Decision (D-proposed A-3):** v1 uses the flat, non-rotating world for S1–S13 and S15. For **S6 (long-duration
CAI drift) and S14 (multi-hour)**, add a contract-v0.2 world option `world.gravity = "schuler_tangent"` in truth,
IMU generation and filter mechanisation:

```
g_n(p) = ( −G0·p_E/R⊕ ,  −G0·p_N/R⊕ ,  −G0·(1 − 2 p_U/R⊕) )
f_b    = Cᵀ (a_n − g_n(p))                                  (replaces constant g_n)
F gains: ∂δv̇/∂δp = diag(−G0/R⊕, −G0/R⊕, +2G0/R⊕)
```
This gives Schuler dynamics and the vertical-channel instability at the right magnitude, with a 3-line change.
Earth rate and Coriolis stay out; they are compensable, and adding them makes the ground truth ECEF-based,
which is disproportionate to the gain. This needs a contract change (§10, C-5).

### 2.7 Trust → filter coupling

For sensor s with trust `w_s ∈ [w_min, 1]`:

```
R_eff,s = R_s / max(w_s, w_min)                                  (inflation, at most 1/w_min)
skip the update entirely if w_s < w_excl                          (exclusion)
NIS gate (all methods, part of the fusion core):
    reject if ν ᵀ (H P⁻ Hᵀ + R_eff)⁻¹ ν > χ²_{m}(1 − α_gate)
IMU trust (fault scenarios only): Q_c,eff = Q_c / max(w_imu, w_min)
defaults: w_min = 0.02 (σ×7.1), w_excl = 0.05, α_gate = 1e-4                         [ASSUMPTION; swept]
```
The NIS gate belongs to the shared fusion core, so every method, including "fixed trust", has it. This keeps
baselines from looking artificially weak. The gate is evaluated with R_eff, so a low-trust sensor can still
pass the gate and contribute a little.

### 2.8 Error reset (after each correction)

```
p̂ ← p̂ − δp̂;  v̂ ← v̂ − δv̂;  Ĉ ← Exp(ψ̂) Ĉ;  b̂_a ← b̂_a − δb̂_a;  b̂_g ← b̂_g − δb̂_g;  δx̂ ← 0
P ← G_r P G_rᵀ with G_r ≈ I (first-order reset Jacobian; Solà 2017, arXiv:1711.02508, §7)
```

### 2.9 Initialisation

Both platforms start with a **30 s stationary/hover segment** (§11.2). Levelling: roll and pitch from the mean
`f_b` over the first 10 s. Heading: truth ψ₀ + N(0, (2°)²) (magnetometer / previous-mission alignment
[ASSUMPTION]; a flat non-rotating world cannot gyrocompass). Position from the first valid fix; velocity 0.
`P₀ = diag((3 m)², (0.1 m/s)², (1 mrad, 1 mrad, 35 mrad)², σ_ba,turn-on², σ_bg,turn-on²)`.

`NavSolution.clk_bias` in LC = the clock bias of the last fix used, NaN if none.

---------------------------------------------------------------------------------------------------

## 3. Trust engine

### 3.1 Features (per GNSS epoch j, time t_j; Δt_j = t_j − t_{j−1})

All features are causal and use **nominal-R innovations** (w = 1). Using R_eff would make the feature
depend on its own output and create a self-reinforcing loop.

| # | Name | Definition |
|---|---|---|
| x1 | `nis_pos` | `ν_pᵀ (H_p P⁻ H_pᵀ + R_p)⁻¹ ν_p / 3` |
| x2 | `nis_vel` | same for velocity / 3 |
| x3 | `raim` | `fix.raim_stat / max(num_sats − 4, 1)` |
| x4 | `cn0_mean` | `fix.mean_cn0 − μ_cn0,ref` |
| x5 | `cn0_std` | `fix.std_cn0` |
| x6 | `cn0_rate` | `(mean_cn0_j − mean_cn0_{j−1}) / Δt_j` |
| x7 | `agc` | `fix.agc_db` (noise-floor rise folded in by the receiver) |
| x8 | `clk_jump` | `|b_j − (b_{j−1} + ḃ_{j−1}Δt_j)| / σ_b`, σ_b = 3 m [ASSUMPTION] |
| x9 | `drift_jump` | `|ḃ_j − ḃ_{j−1}| / σ_ḃ`, σ_ḃ = 0.2 m/s [ASSUMPTION] |
| x10 | `resid_rms` | `fix.residual_rms` |
| x11 | `nsat_delta` | `num_sats_j − num_sats_{j−1}` |
| x12 | `div_cusum` | Page CUSUM of the position NIS: `S_j = max(0, S_{j−1} + x1_j − k_c)`, k_c = 1.5 |
| x13 | `outage` | 1 if the previous epoch was an outage / invalid fix |

The CAI's contribution to detection comes through x1, x2 and x12. A CAI-aided INS drifts less, so `P⁻` stays
smaller and a spoofer's drag-off produces a larger NIS sooner. The ablation "−quantum" measures exactly this.

**Detector input.** `u_j = [x̃_j, EWMA_2s(x̃)_j, EWMA_20s(x̃)_j, x̃_j − x̃_{j−1}] ∈ ℝ^{52}`, where
`x̃ = (x − μ)/σ` uses the federated normalisation statistics (§4.2). EWMA constants are given in seconds,
`α = 1 − exp(−Δt_j/τ)`, so the detector does not depend on the GNSS rate.

### 3.2 Learnable detector

`f_θ`: MLP 52 → 16 (tanh) → 2 (sigmoid), giving heads `p_spoof` and `p_jam`; `p_j = max(p_spoof, p_jam)`.
The model has 882 parameters, so updates are about 3.5 kB. Loss: class-weighted BCE per head over labelled
(pseudo-label) samples. torch float32, `torch.set_num_threads(1)` per process.
The reason for an MLP rather than logistic regression: the spoof signature is an interaction ("NIS up while
C/N0 does *not* drop"), which is non-linear in the features. Logistic regression (52→2) is a required
ablation (`detector.arch = "logreg"`). A GRU is deferred because the EWMA stack already supplies temporal
context at a fraction of the cost.

### 3.3 Continuous trust law (per sensor; GNSS shown)

At each evidence event j (a GNSS epoch with a valid fix):

```
(1) smoothing        p̄_j = p̄_{j−1} + β_j (p_j − p̄_{j−1}),                 β_j = 1 − e^{−Δt_j/τ_p}
(2) target           τ*_j = w_min + (1 − w_min) · clip( (θ_hi − p̄_j)/(θ_hi − θ_lo), 0, 1 )
(3) detection flag   D_j = 1  if p̄ ≥ θ_on continuously for ≥ T_on
                     D_j = 0  if p̄ ≤ θ_off continuously for ≥ T_off;   otherwise D_j = D_{j−1}
(4) recovery gate    G_j = [D_j = 0] ∧ [t_j − t_last(p̄ > θ_off) ≥ T_clean] ∧ [frac_{T_clean}(NIS_p ≤ χ²₃(0.95)/3) ≥ 0.9]
(5) update           if τ*_j < w_{j−1}:          w_j = w_{j−1} + (1 − e^{−Δt_j/τ_d}) (τ*_j − w_{j−1})   (fast distrust)
                     elif τ*_j > w_{j−1} ∧ G_j:   w_j = w_{j−1} + (1 − e^{−Δt_j/τ_r}) (τ*_j − w_{j−1})   (slow recovery)
                     else                         w_j = w_{j−1}
(6) anti-lockout     if G_j is blocked ONLY by the NIS term for ≥ T_lock while x3..x11 are all inside their 95%
                     nominal quantiles: allow the recovery update with the target capped at w_cap
```
Defaults [ASSUMPTION unless stated; all swept ±2× in the sensitivity study]:
`τ_p = 0.5 s, θ_lo = 0.2, θ_hi = 0.8, θ_on = 0.6, θ_off = 0.3, T_on = 0.5 s, T_off = 5 s, T_clean = 10 s,
τ_d = 0.5 s, τ_r = 10 s, w_min = 0.02, w_excl = 0.05, T_lock = 120 s, w_cap = 0.5, w_reacq = 0.5`.
`TrustState.anomaly_scores = {"gnss": p̄, "quantum": p̄_q, "imu": p̄_imu}`,
`TrustState.attack_detected = D_gnss`.

**Properties.**

* *Boundedness and stability.* (5) is a convex combination of `w_{j−1}` and `τ*_j ∈ [w_min, 1]`, so
  `w ∈ [w_min, 1]` always. For constant `τ*`, `|w_j − τ*| = e^{−Δt/τ}|w_{j−1} − τ*|`. This is a contraction:
  convergence is exponential, unconditional for any Δt > 0, with no overshoot. EKF stability: `R_eff ∈ [R, R/w_min]`
  is bounded above and below. With uniform complete observability of (Φ, H) whenever GNSS is used, and Q ≻ 0,
  the Riccati recursion stays bounded (Anderson & Moore, *Optimal Filtering*, 1979, Ch. 4, bounded time-varying
  noise). An excluded sensor (w < w_excl) just gives an open-loop INS phase, and P grows as the physical
  free-inertial error does.
* *No chattering (formal).* Call a **trust cycle** a downward crossing of w = 0.5 followed by an upward
  crossing of w = 0.9. Upward motion needs `G = 1`, which needs `p̄ ≤ θ_off` for T_clean. From w = 0.5 toward
  τ* ≤ 1, reaching 0.9 takes at least `τ_r ln(0.5/0.1) = 16.1 s`. So the cycle period satisfies
  **`T_cyc ≥ T_clean + τ_r ln 5 = 26.1 s`** for *any* input sequence p_j, adversarial ones included, and the
  number of cycles in a window W is at most `⌈W/26.1 s⌉`. The flag D uses a dead band `θ_on − θ_off = 0.3`
  plus dwell times, so two consecutive D transitions are at least `min(T_on, T_off) = 0.5 s` apart, and a
  full D cycle takes at least `T_on + T_off = 5.5 s`. This makes the behaviour Zeno-free with bounded
  switching frequency. It is the property S7 tests.
* *Latency from design.* For a step to p = 1 at 1 Hz GNSS: β = 1 − e^{−2} = 0.86, so p̄ = 0.86 > θ_hi after
  the first epoch, τ* = w_min, and w = 1 − 0.86·0.98 = 0.16. The design time-to-distrust (w < 0.5) is
  therefore **1 epoch** at ≤ 2 Hz (≤ 2 epochs at 5–10 Hz, where β is smaller per epoch but epochs are shorter). The recovery design time from w_min to 0.9 is **T_clean + τ_r ln(0.98/0.1) ≈ 33 s**.
* *The known weakness, stated up front.* A spoofer that keeps `p` below θ_lo (drift inside the noise) is
  never distrusted. The error it can induce is bounded by the detector's sensitivity, which is what the
  severity sweep in S2 measures.

### 3.4 IMU trust

IMU trust `w_imu` is rule-based: its target is w_min during IMU gaps or saturation (|f| > the model's range),
otherwise 1. No attack in v1 targets the IMU.

### 3.5 Quantum trust (rule-based, not federated in v1)

Per CAI sample: `p_q = 1 − valid · clip((contrast − c_min)/(c_nom − c_min), 0, 1) · [NIS_Q ≤ χ²_m(0.999)]`.
Two-sided Page CUSUM on the standardised hybrid residual while `w_gnss > 0.9` (GNSS observes b_a independently):
`S± = max(0, S± ± r̃ − 0.5)`, `r̃ = (ν_Q − E[ν_Q])/√R_Q`, alarm `h = 8` (Page 1954, Biometrika 41:100,
doi:10.1093/biomet/41.1-2.100). An alarm sets `p_q = 1`. The same law (3.3) applies with `τ_d = T_c`,
`τ_r = 60 s`, `T_clean = 5 T_c`, `c_min = 0.1`, `c_nom` taken from the sensor config.

---------------------------------------------------------------------------------------------------

## 4. Federated protocol

### 4.1 What is learned and what is shared

| Item | Learned where | Shared | Notes |
|---|---|---|---|
| Detector weights θ (882 floats) | locally (SGD) | **deltas `Δθ_i = θ_i − θ_g`** in `ModelUpdate.params` | the only trained object |
| Feature normalisation (μ, σ per feature, 13+13 floats) | local running moments over **pseudo-label-negative** samples | `params["norm_mu"]`, `params["norm_sd"]` | aggregated by coordinate-wise **median**, not mean, which resists poisoning |
| Trust-law hyper-parameters | **not learned in v1** (fixed, identical across methods) | — | keeps the ablations clean; learning them is a v2 extension |
| `metrics` | — | `{"n_pos", "n_neg", "loss", "pl_rate"}` scalars only | no trajectories, no timestamps, no labels |

`ModelUpdate.n_samples` is **self-reported**, so the robust aggregator must not weight by it: an attacker
could claim n = 10⁹. FedAvg does weight by it, which is part of why FedAvg is the vulnerable reference in S12.

### 4.2 Round schedule (sim time)

Round r closes at `t_r = r · T_round`, with `T_round = 60 s`. At `t_r` each live node:
1. trains locally for `E = 2` epochs over its replay buffer (at most 20 000 samples, class-balanced reservoir:
   at most 50% positives), minibatch 64, SGD lr 0.05, FedProx term `(μ/2)‖θ − θ_g‖²` with μ = 0.01
   (μ = 0 gives FedAvg);
2. sends `ModelUpdate(kind="delta")`, or a `NoUpdate` heartbeat if it has fewer than 64 labelled samples.

The server aggregates and broadcasts `GlobalModel(round_idx=r)`. The node swaps its detector at the first
GNSS epoch with `t ≥ t_r + d_down`. Trust state is never reset by a model swap.
**Pre-training:** every method starts from the same `θ₀`, pre-trained offline on training seeds 0–499
(simulator-labelled missions whose attack families are **disjoint from the test families**, e.g. train on
drift-spoof + CW jam and test also on meaconing + wideband). This is a fair common start. Only what happens
after θ₀ differs between methods.

### 4.3 Local training labels: hindsight pseudo-labels (self-supervised). This is the chosen option.

Simulator ground truth is **not** used online, because a real fleet has no attack labels. The pseudo-labeller
runs with lag `L = 30 s`. It labels epoch j once data up to `t_j + L` exists, using hindsight and very
conservative consistency tests:

```
y_j = 1  if  ∃ t ∈ [t_j, t_j+L]:  S_cusum(t) ≥ h₁ = 20        (sustained INS–GNSS divergence; CAI-aided INS as reference)
           or  agc ≥ 6 dB for ≥ 2 s   or  raim ≥ χ²_{n−4}(1 − 1e-6)   or  clk_jump ≥ 8
y_j = 0  if  all of x1..x11 lie inside their nominal 95% quantiles for every epoch in [t_j − L, t_j + L]
y_j = ∅  otherwise (not used for training)
```
**Why this and not simulated labels:** (a) it is realistic, since field nodes are unlabelled; (b) the test
has no label leakage, because training never reads `AttackLabel`; (c) it is where the quantum sensor adds
value to FL: a slowly drifting CAI-aided INS is a trustworthy hindsight reference. The learned detector is
still useful beyond the rules. It is **causal** (no L-second lag), it fires earlier on soft precursors
(C/N0 and clock shape before the divergence is large), and FL spreads what one node's rules labelled to nodes
that never saw that attack. **Required honesty check:** the evaluator (not the nodes) reports pseudo-label
precision and recall against `AttackLabel` per scenario. An oracle-label variant
(`fl.labels = "oracle"`) is reported as an upper bound only.

### 4.4 Leakage guards (enforced, tested)

1. The environment passes `dataclasses.replace(epoch, meta={})` to the receiver. **Currently `GnssEpoch.meta`
   carries the TRUE receiver clock bias and drift** (`fedqpnt/gnss/signal.py:179`, used by the attacks).
2. Agent-side packages (`fusion`, `trust`, `fl`, `baselines`) must not import `AttackLabel`, `TruthState` or
   `TruthTrajectory`. A pytest AST scan enforces this.
3. Labels and truth are written only to `truth/*` and `labels/*` recorder streams, read only by `eval`.
4. Test master seeds (10 000–10 029) are disjoint from pre-training (0–499), tuning (500–599) and
   FL-warm-up seeds.

### 4.5 Aggregators (`fl.aggregator`)

* **FedAvg** (McMahan et al. 2017, AISTATS, arXiv:1602.05629): `Δ = Σ n_i Δ_i / Σ n_i`.
* **FedProx** (Li et al. 2020, MLSys, arXiv:1812.06127): FedAvg aggregation plus the client-side proximal term.
* **TRIM-NB-R** (FedQPNT default, "trust-aware robust"):
  ```
  1 clip      Δ_i ← Δ_i · min(1, c · median_j‖Δ_j‖ / ‖Δ_i‖),       c = 2          (norm bounding; Sun et al. 2019, arXiv:1911.07963)
  2 exclude   drop nodes in quarantine
  3 aggregate coordinate-wise trimmed mean, trim β = 0.2 per side (N_live ≥ 5); coordinate-wise median if N_live < 5
                                                                                  (Yin et al. 2018, ICML, arXiv:1803.01498)
  4 reputation  r_i ← ρ r_i + (1−ρ) max(0, cos(Δ_i, Δ)),    ρ = 0.8,   r_i(0) = 1
  5 quarantine  r_i < r_q = 0.2 for 3 consecutive rounds → quarantined for 10 rounds (logged event)
  6 server step θ_g ← θ_g + η_s Δ,  η_s = 1
  ```
  Breakdown: the trimmed mean tolerates at most a fraction β = 20% of Byzantine nodes. S12 tests f = 20%
  (must pass) and f = 40% (expected to fail; reported). Attacks to evaluate: sign-flip ×(−5), Gaussian noise
  at 10× the median norm, label-flip, and "A Little Is Enough" (Baruch et al., NeurIPS 2019,
  https://proceedings.neurips.cc/paper/2019/hash/ec1c59141046cd1866bbbcdfb6ae31d4-Abstract.html).
  Krum (Blanchard et al., NeurIPS 2017) and FLTrust (Cao et al., NDSS 2021, arXiv:2012.13995) are optional
  comparators.

### 4.6 Comms model (`comms.*`, simulated in **sim time**, RNG `stream(seed, node, "comms_up"/"comms_down")`)

```
delay      d = min( LogNormal(ln 0.2 s, 0.5) + bytes·8/B,  d_max )     B = 1 Mbit/s, d_max = 5 s (beyond = lost)
loss       Gilbert–Elliott per message: P(G→B) = 0.02, P(B→G) = 0.3, loss_G = 0.01, loss_B = 0.9
staleness  an update built on global round r' arriving for round r: s = r − r';
           weight (1+s)^(−0.5)  (polynomial staleness, Xie et al. 2019 "FedAsync", arXiv:1903.03934);  discard if s > 3
quorum     aggregate only if ≥ ⌈0.5·N_live⌉ fresh updates; otherwise θ_g is unchanged (event ROUND_SKIPPED)
```
[ASSUMPTION for all numbers; S9 sweeps loss_B and P(G→B).]

### 4.7 Cold start (node joins at t_join)

The node boots with θ₀ and the pre-trained normalisation statistics. It requests the latest global model
(subject to downlink delay/loss) and uses it from the first GNSS epoch after arrival. Initial trust is w = 1
(it must bootstrap navigation from GNSS), with the detector active from the first epoch. Its uplink updates
count as normal. Under TRIM-NB-R its reputation starts at 1, but its first two rounds are clipped at
c = 1 × median (probation). In Baseline B the new node only ever has θ₀ plus its own data, and that
difference is exactly what S8 measures.

---------------------------------------------------------------------------------------------------

## 5. Methods: baselines and ablations (config diffs over ONE code path)

All methods share the sensors, the noise realisations (paired seeds, D-005), the ES-EKF (§2, including the
NIS gate), the features (§3.1), the detector architecture (§3.2), θ₀, and the tuning budget (20 random configs
on tuning seeds 500–599 per method; D-002).

| Method | Detector trained by | Trust law | CAI | Aggregator |
|---|---|---|---|---|
| **FedQPNT** | FL (pseudo-labels) | continuous §3.3 | on | TRIM-NB-R |
| **Baseline A** (FL detection, fixed trust; Khan 2025 / Chai 2025 style) | FL (same) | **fixed**: `w = 1` if `p_j < 0.5`, else `w = 0` (memoryless detect-and-exclude; no smoothing, hysteresis, asymmetric rates or recovery gate) | on | TRIM-NB-R (and FedAvg reported) |
| A0 (sanity) | FL | `w ≡ 1` (alarm only) | on | TRIM-NB-R |
| **Baseline B** (single-node adaptive; Meng 2025 / Gu 2021 / Pardhasaradhi 2022 style) | **local only** from θ₀ (same pseudo-labels, same epochs) | continuous §3.3 | on | — |
| B′ (literature-faithful rule variant) | none: `p_j = F_{χ²_3}(3·x1_j)` (innovation-based adaptive) | continuous §3.3 | on | — |
| Abl −quantum | FL | continuous | **off** (no CAI updates, no quantum trust) | TRIM-NB-R |
| Abl −FL | ≡ Baseline B (the same config, run once, reported under both names) | | | |
| Abl fixed-trust | FL | `w ≡ 1` + NIS gate | on | TRIM-NB-R |
| Abl binary | FL | `w = 1 − D·(1 − w_min)` (D from §3.3 (3), with hysteresis) | on | TRIM-NB-R |
| Abl −recovery-gate | FL | §3.3 with `G ≡ 1` | on | TRIM-NB-R |
| Abl logreg | FL, `detector.arch = logreg` | continuous | on | TRIM-NB-R |
| Abl FedAvg | FL | continuous | on | FedAvg |

> **Master ruling D-011 (supersedes the "UNVERIFIED" note below):** baselines are *mechanism classes*.
> Baseline B is split into **B-bin** (local detector → exclude GNSS / coast on INS until the recovery gate
> passes; Pardhasaradhi 2022 class) and **B-cont** (the row labelled "Baseline B" above, i.e. §3.3 trust law
> with a local-only detector; it is identical to "Abl −FL"). H2 is tested against B-cont. Papers are cited as
> class representatives, never as re-implementations. See `docs/specs/raw/BASELINE_LIT_NOTES.md`.
> **Verified citations (D-013):** A: Khan 2025 (10.1002/ett.70138), Chai 2025 (10.1109/JIOT.2025.3588162);
> B-bin: Pardhasaradhi 2022 (10.1109/JSEN.2022.3168940); B-cont: adaptive-fusion class, Ren 2020
> (10.1109/CVCI51460.2020.9338655); B′: Mehra 1970 (10.1109/tac.1970.1099422). Meng 2025 and Gu 2021 have been
> **dropped** (not found). Robust-FL prior work to position against: G²FL, Liu 2026 (10.1109/ICCWorkshops63917.2026.11586283).

Baseline citations (Khan 2025, Chai 2025, Meng 2025, Gu 2021, Pardhasaradhi 2022) come from the project
proposal. **UNVERIFIED here**: Master must insert their DOIs and confirm that A's "memoryless detect-and-exclude"
and B's "innovation-driven adaptive weighting" represent them faithfully. If a paper's fusion rule differs,
change A or B *before* any results exist.

---------------------------------------------------------------------------------------------------

## 6. Metrics

Evaluated on nav output at 10 Hz, per node and per run. Phases come from truth labels:
`t_on` is the first label with `spoofing ∨ jamming`, `t_off` is the last such label plus one epoch.
`P_pre = [t_align, t_on)` with `t_align = 60 s` (alignment transient excluded), `P_att = [t_on, t_off)`,
`P_post = [t_off, T]`.

```
e_h(t) = ‖p̂_EN(t) − p_EN(t)‖₂       e_3(t) = ‖p̂(t) − p(t)‖₂       e_v(t) = ‖v̂(t) − v(t)‖₂
RMSE_h(P) = sqrt( mean_{t∈P} e_h² )     MAX_h(P) = max_{t∈P} e_h     P95_h(P) = 95th percentile
(same for e_3, e_v)
ANEES(P)  = mean_{t∈P} δpᵀ P_pos⁻¹ δp / 3          (filter consistency; ideal 1)
Detection:   t_det = inf{ t ≥ t_on : attack_detected(τ) = 1 ∀τ ∈ [t, t + T_sus] },   T_sus = 1 s
             latency_on = t_det − t_on;  a miss if t_det ≥ t_off (latency censored at t_off − t_on)
             latency_eff = t_det − t_eff,  t_eff = first t with |spoof-induced PVT offset| > 3σ_nom (truth-side) — reported for gradual spoofs, where onset is physically undetectable
Detection prob. P_D = fraction of runs (node-attacks) with a hit
False alarms: FA events = rising edges of attack_detected with no label active within ±T_sus;
              FAR = FA events / clean hours;   also per-epoch FPR = Pr(p_j > 0.5 | clean)
Detector quality: ROC-AUC of p_j vs label (evaluator only)
Time-to-distrust: t_dist = inf{ t ≥ t_on : w_gnss(t) < 0.5 } − t_on
Recovery time:    t_rec = inf{ τ ≥ 0 : e_h(t) < E_thr ∀ t ∈ [t_off + τ, t_off + τ + T_hold] },
                  E_thr = max(2·RMSE_h(P_pre), 3 m),  T_hold = 10 s;  "no recovery" if none before T
Trust chattering:  N_cyc = number of trust cycles (§3.3) per hour;  TV_w = Σ|w_{j+1} − w_j| per hour in clean phases
Trust trajectories: w_s(t), p̄_s(t), D(t) logged at every evidence event
FL metrics:        global-model AUC per round on a fixed held-out labelled evaluation set (evaluator only),
                   rounds skipped, quarantined nodes, pseudo-label precision / recall
```

### 6.1 Acceptance criteria (functional; must pass before results are "valid")

These are **engineering acceptance tests** of the software and the design. They are *not* the scientific
hypotheses (§6.2). A method failing one is reported, not tuned away. Each criterion is evaluated over the 30
test seeds, with a Wilson 95% CI on proportions. "Undefended" = fixed-trust w ≡ 1 with the NIS gate off.

| # | Scenario | Pass criteria (FedQPNT; the same test is reported for every method) | Justification |
|---|---|---|---|
| S1 | Nominal | RMSE_h ≤ 1.05 × RMSE_h(fixed-trust) paired per seed, median ratio; FAR ≤ 1 /h/node; ANEES_pos ∈ [0.5, 2]; mean w_gnss ≥ 0.95 | Trust must cost ≤ 5% when nothing is wrong. 1/h is a lenient nuisance rate: RAIM-FDE design Pfa ≈ 1e-5/sample → 0.04/h at 1 Hz (RTCA DO-229, **UNVERIFIED exact value**); a learned uncertified detector gets 25× slack. The factor-2 ANEES band [ASSUMPTION] tolerates correlated GNSS errors. |
| S2 | Gradual spoof, severities {low, med, high} | For severities whose final offset ≥ 50 m: P_D ≥ 0.9 and MAX_h(P_att) ≤ 0.5 × MAX_h(undefended). For all severities: MAX_h(P_att) ≤ MAX_h(undefended) + 3σ_nom (defence never makes it worse) | "Halve the damage" is the minimum useful mitigation. 50 m is ≫ nominal error (several σ), so detectable in principle. |
| S3 | Sudden jamming | t_dist ≤ 2 GNSS epochs + 1 s; during the outage, `e_h ≤ 3σ_h(P_pos)` in ≥ 95% of 10 Hz samples (consistency); no GNSS update accepted while J/S makes fix.valid false | Derived from the §3.3 design latency. The coast error must be predicted honestly by P. |
| S4 | Combined (jam → spoof capture at reacquisition) | S2 and S3 criteria jointly; w_gnss ≤ w_reacq at reacquisition in 100% of runs | Tests the reacquisition cap. |
| S5 | Partial node failure / delayed updates (30% nodes fail at T/2; delays 1–3 rounds) | all rounds reach quorum or log ROUND_SKIPPED; no deadlock (harness timeout); final global AUC ≥ AUC(no failure) − 0.02 | FL must degrade gracefully. 0.02 AUC is within typical seed-to-seed spread [ASSUMPTION; check against measured spread]. |
| S6 | CAI bias drift, long duration (Schuler world) | RMSE_h ≤ 1.05 × RMSE_h(−quantum) paired; w_q < 0.5 within 10 cycles after the drift exceeds 5√R_Q | **Graceful degradation**: a faulty sensor must never make the system worse than not having it. |
| S7 | Trust chattering (spoof toggled with period ∈ {2, 5, 10, 20, 60} s; detector noise near threshold) | N_cyc ≤ ⌈3600/26.1⌉ = 138 /h (hard bound from §3.3; measured must not exceed it); in S1, TV_w ≤ 1 /h; MAX_h ≤ S2 bound | Checks the formal bound holds in code. |
| S8 | Cold-start node at T/2 | receives a global model within 2 rounds in ≥ 95% (nominal comms); its AUC on its first attack ≥ veteran AUC − 0.05 | Tests that FL knowledge transfers. |
| S9 | Comms dropouts (loss_B ∈ {0.5, 0.9}, P(G→B) ∈ {0.02, 0.1}) | no deadlock; final AUC ≥ no-loss AUC − 0.03; nav metrics differ from no-loss only through the detector | Robustness of the protocol. |
| S10 | Sample-rate mismatch (GNSS {1, 2, 5, 10} Hz × T_c {0.5, 0.73, 1, 2} s, ±1 tick jitter) | no crash; ANEES ∈ [0.5, 2] for every combination; RMSE_h(P_pre) non-increasing in GNSS rate within CI | Rate handling correct. |
| S11 | Extreme noise (IMU noise ×10, GNSS σ ×5, CAI contrast ÷3; the filter is NOT told) | 100% runs finite with P SPD; RMSE_h ≤ 1.5 × RMSE_h(GNSS-only fixes); FAR reported (no threshold) | Numerical robustness; no divergence below raw GNSS quality. |
| S12 | Trust-score / model poisoning (f ∈ {20%, 40%}; 4 attack types §4.5) | f = 20%: AUC drop ≤ 0.05 vs clean for TRIM-NB-R; f = 40%: reported only (beyond β breakdown) | Theory: the trimmed mean is robust for f < β. |
| S13 | Recovery after attack | t_rec ≤ 60 s in ≥ 90% of runs; ≤ 180 s in 100% (no lock-out) | Design recovery about 33 s (§3.3) + EKF reconvergence ≈ 20 s [ASSUMPTION] |
| S14 | Multi-hour stability (4 h, Schuler world) | P SPD and finite throughout; RMSE_h(last hour) ≤ 1.2 × RMSE_h(first hour); FAR ≤ 1 /h; process RSS growth < 10% from hour 1 to hour 4 | No slow numerical or statistical drift. |
| S15 | Simultaneous attacks on fleet subsets (30% of nodes spoofed at once, same kind) | attacked nodes meet S2; unattacked nodes' FAR ≤ S1 FAR + 0.5 /h; no quarantine of honest nodes caused by legitimately different updates (logged count = 0 in ≥ 90% of runs) | Checks that the robust aggregator does not punish honest heterogeneity. |

### 6.2 Scientific hypotheses (reported whatever the outcome; never pass/fail)

H1: FedQPNT < A on RMSE_h(P_att) and MAX_h(P_att). H2: FedQPNT < B on the same metrics and on detection
latency for attack families that node i has not yet experienced. H3: FedQPNT (CAI) < −quantum on
latency_eff for gradual spoofing. H4: FedQPNT < B on the cold-start node's P_D and latency (S8).
Primary metrics (pre-registered): RMSE_h(P_att) and latency_on. Everything else is secondary.

---------------------------------------------------------------------------------------------------

## 7. Statistical protocol

1. **Monte Carlo:** n = 30 test master seeds (10 000–10 029) per scenario × method, **paired** by seed.
   D-005 streams give identical sensor and attack noise across methods. With n = 30 a paired test has 80%
   power at α = 0.05 (two-sided) for a standardised effect d_z ≈ 0.53. If pilot runs (seeds 600–609) show
   d_z < 0.5 on a primary metric, increase n to `⌈(z_{.975}+z_{.8})²/d_z²⌉ + 2`, **decided before looking at
   test seeds**.
2. **Unit of analysis:** per-run value averaged over nodes (nodes within a run are not independent). A
   per-node analysis is secondary, using a mixed model with a random effect for run.
3. **Tests:** primary is the Wilcoxon signed-rank test, two-sided, on paired per-seed differences (Wilcoxon 1945,
   Biometrics Bull. 1:80, doi:10.2307/3001968). The paired t-test is reported in addition when Shapiro–Wilk on
   the differences gives p > 0.05. Multi-method per scenario: Friedman test, then Nemenyi post-hoc
   (Demšar 2006, JMLR 7:1–30). Binary outcomes (detected yes/no): exact McNemar. Censored latencies (misses)
   are set to the censoring value, which the rank tests handle.
4. **Effect sizes:** Hodges–Lehmann median of paired differences with a 95% BCa bootstrap CI (10 000
   resamples, RNG `stream(0, "eval", "bootstrap")`); matched-pairs rank-biserial r; Cohen's d_z.
5. **Multiplicity:** Holm–Bonferroni (Holm 1979, Scand. J. Statist. 6:65–70) over the confirmatory family
   {H1…H4} × {primary metrics} × {scenarios where applicable}. Secondary metrics are reported with unadjusted
   p-values labelled exploratory.
6. **Tuning discipline:** `κ_R`, `κ_Q` and the trust defaults are fixed using tuning seeds 500–599 **for all
   methods alike**, then frozen (config hash logged) before any test seed is run. For `κ_R` the target is
   nominal ANEES = 1 ± 0.1.

---------------------------------------------------------------------------------------------------

## 8. Federation execution model

**Recommendation: `multiprocessing` with the `spawn` context and `mp.Queue`, bulk-synchronous in sim time,
behind a `Transport` abstraction** (so localhost sockets can be swapped in later for a multi-host demo).
Queues are sufficient, portable on Windows and deterministic under the rules below. Sockets add framing,
ports and firewall prompts with no scientific benefit in v1.

```
orchestrator (main process)
 ├─ spawns  Server  (1 process)          inbox: server_q (MPSC)
 ├─ spawns  Node_i  (N processes)        inbox: node_q[i]
 │    Node_i = Environment + Agent + Recorder(runs/<id>/node_i/)
 ├─ holds   ground-truth-free orchestration; evaluator runs AFTER the mission on recorded files
 └─ watchdog: proc.is_alive() every 1 s wall time → notifies Server of real crashes (flags run non-deterministic)
```

**Determinism protocol (bulk-synchronous at round boundaries):**
1. Node i runs ticks until `t ≥ t_r`, then sends exactly one message for round r: `ModelUpdate`, `NoUpdate`,
   `Lost` (the uplink loss was *simulated* by the node's comms RNG) or `Failed` (scenario-scheduled failure;
   the node then exits). The simulated uplink delay d_up is attached to the message.
2. The Server blocks until it has one message per live node for round r (wall-clock timeout 600 s leads to
   ABORT). It aggregates the updates in **node_id order** (never arrival order), draws the downlink delay and
   loss per node from `stream(seed, "server", "comms_down", node)`, and replies `GlobalModel` + `d_down` or
   `Lost`.
3. Node i **blocks at t_r** until it gets the reply, then continues. It installs the model at the first
   GNSS epoch with `t ≥ t_r + d_up + d_down`. Latency is simulated in sim time, so wall-clock speed differences
   never change results.
4. Cold-start nodes are spawned at the start but stay dormant (they neither simulate nor send) until
   `t_join`. They join the barrier from the first round after t_join.
5. Each process sets `torch.set_num_threads(1)`, and `OMP_NUM_THREADS=1` before import.

Serialisation: `ModelUpdate` / `GlobalModel` are pickled dataclasses of numpy arrays (about 4 kB).
Throughput is irrelevant.

---------------------------------------------------------------------------------------------------

## 9. Default parameter summary (for `RunConfig` defaults)

`sim.dt=0.01; gnss.rate_hz=1; quantum.cycle_time=1.0; fl.round_period_s=60; fl.local_epochs=2;
fl.lr=0.05; fl.batch=64; fl.prox_mu=0.01; fl.aggregator="trim_nb_r"; fl.trim_beta=0.2; fl.clip_c=2;
fl.rep_rho=0.8; fl.rep_q=0.2; comms.* per §4.6; trust.* per §3.3; fusion.kappa_R (tuned), kappa_Q=1,
w_min=0.02, w_excl=0.05, alpha_gate=1e-4; pseudolabel.L=30, h1=20; eval.T_sus=1, T_hold=10, t_align=60`.

---------------------------------------------------------------------------------------------------

## 10. Proposed contract changes (v0.1 → v0.2). Master decides; ARCHITECT did not edit core.

| ID | Change | Rationale |
|---|---|---|
| **C-1** | New `Innovation` dataclass `{t, sensor:str, nu:(m,), S:(m,m), nis:float, dof:int, accepted:bool}`. Split `FusionFilter` into `propagate(t, imu) -> None`, `innovations(t, fix, quantum) -> list[Innovation]`, `correct(t, innovations, trust) -> NavSolution` (keep `step` as a convenience wrapper). `TrustEngine.update(t, fix, imu, quantum, nav_prior, innovations) -> TrustState`. | v0.1 has a circular dependency: trust needs innovations computed inside fusion *before* fusion uses trust. Without the change, trust must re-derive NIS from `nav_prior.cov_pos`, and a velocity NIS is impossible. |
| **C-2** | `QuantumSample` add `t_interrogation: float` (T, s) and `response: str = "triangular"`. | `cycle_time` includes dead time. The CAI response is triangular over 2T, not boxcar over the cycle. Exact hybridisation (§2.5) needs the true window. |
| **C-3** | `NavSolution` add `cov_vel (3,3)`, `acc_bias (3,)`, `gyro_bias (3,)`. | Needed by features x2 and quantum CUSUM, and for the evaluator's NEES on velocity. |
| **C-4** | Docstring rule: `GnssEpoch.meta` is environment-private; the environment passes `meta={}` to the receiver. Rename to `sim_meta` in v0.2. | It currently carries the true clock bias/drift (`gnss/signal.py:179`), which is a leak path to the Agent. |
| **C-5** | World option `world.gravity ∈ {"flat", "schuler_tangent"}`; `f_b = Cᵀ(a_n − g_n(p))` with §2.6 `g_n(p)`. Move `g_n` to a `core/world.py` function used by truth, IMU and filter. | Required for honest multi-hour / CAI-drift results (S6, S14). |
| **C-6** | `types.py` docstring: add the explicit Euler/heading convention of §0 (ψ = 0 East, CCW; θ > 0 nose-down) and "IMU samples are point samples". | Removes the ambiguity that could make agents disagree silently. |
| C-7 | `GnssFix` add optional `pdop: float = nan`. | Useful feature and diagnostic; not blocking. |

---------------------------------------------------------------------------------------------------

## 11. WP-1.2 implementation brief (for the implementation agent; no design decisions left open)

General rules: numpy float64; no global RNG (only the `rng` argument); every class has `config() -> dict`
(JSON-serialisable, including all defaults); files go in `fedqpnt/sim/`; tests in `tests/test_sim_*.py` run real
code with no mocks. Do not modify `fedqpnt/core`.

### 11.1 `fedqpnt/sim/rotations.py`

```python
def skew(v: np.ndarray) -> np.ndarray                         # (3,)->(3,3)
def vee(M: np.ndarray) -> np.ndarray                          # (3,3)->(3,), uses antisymmetric part ½(M−Mᵀ)
def euler_to_dcm(att: np.ndarray) -> np.ndarray               # (3,) or (N,3) -> (3,3) or (N,3,3); C = Rz(ψ)Ry(θ)Rx(φ)
def dcm_to_euler(C: np.ndarray) -> np.ndarray                 # inverse; φ=atan2(C21,C22), θ=−asin(clip(C20)), ψ=atan2(C10,C00)
def so3_exp(phi: np.ndarray) -> np.ndarray                    # Rodrigues; Taylor series for |phi|<1e-8
def so3_log(C: np.ndarray) -> np.ndarray                      # robust near 0 and near π
def quat_from_dcm(C) / dcm_from_quat(q) / quat_mul(a,b) / quat_normalize(q)   # q = [w,x,y,z], Hamilton
def body_rates_from_euler_rates(att, att_dot) -> np.ndarray   # p,q,r formulas of §0 (vectorised)
def euler_rates_from_body_rates(att, omega_b) -> np.ndarray
```
Tests: round trips (euler→dcm→euler, exp→log) to 1e-12 on 10⁴ random samples with |θ| < 89°;
`euler_to_dcm([0,0,ψ]) @ e_x = [cosψ, sinψ, 0]`; `euler_to_dcm([0,θ,0]) @ e_x` has z = −sinθ.

### 11.2 `fedqpnt/sim/trajectory.py`

**Signal representation.** Each scalar "channel" `u(t)` is a `scipy.interpolate.PPoly` built as a sum of
non-overlapping **smooth trapezoid pulses**:
`pulse(t; t0, Tr, Th, A)` = `A·S((t−t0)/Tr)` on the ramp-up, `A` on the hold, `A·(1 − S((t−t0−Tr−Th)/Tr))` on the
ramp-down, 0 elsewhere, with the quintic smoothstep `S(τ) = 10τ³ − 15τ⁴ + 6τ⁵`. S, S′, S″ are zero at the ends,
so u is C². Its exact integral is `.antiderivative()` and its exact derivatives are `.derivative(n)`. The pulse
area is `A·(Th + Tr)`. To change a quantity by Δ with peak |A| ≤ A_max: `Th = |Δ|/A_max − Tr`; if Th < 0 then
`Th = 0, A = Δ/Tr`. The jerk-type peak is `1.875·A/Tr`.

```python
@dataclass
class GroundVehicleParams:
    v_max: float = 25.0; a_acc_max: float = 2.5; a_brake_max: float = 3.5; a_lat_max: float = 3.0
    yaw_rate_max: float = 0.5; ramp_s: float = 1.5; grade_max: float = 0.06
    roll_gain: float = 0.006   # rad per m/s² lateral accel  [ASSUMPTION, ≈3.4°/g]
    pitch_gain: float = 0.003  # rad per m/s² longitudinal    [ASSUMPTION, ≈1.7°/g]
    t_static: float = 30.0; p_cruise=.35; p_speed=.25; p_turn=.25; p_stop=.15
    cruise_s=(10.,60.); turn_deg=(30.,120.); stop_hold_s=(5.,20.); speed_target=(8.,25.); min_turn_speed=3.0

@dataclass
class UavParams:
    v_max: float = 20.0; vz_max: float = 4.0; a_h_max: float = 3.0; a_z_max: float = 2.0
    tilt_max_deg: float = 30.0; yaw_rate_max: float = 0.6; ramp_s: float = 1.5
    alt_min: float = 30.0; alt_max: float = 300.0; alt0: float = 50.0; t_hover0: float = 30.0
    p_cruise=.25; p_speed=.2; p_turn=.2; p_climb=.15; p_loiter=.1; p_hover=.1
    cruise_s=(10.,60.); turn_deg=(30.,180.); loiter_turns=(1,2); hover_s=(5.,30.); speed_target=(5.,20.)

class GroundVehicleTrajectory:          # implements core.interfaces.TrajectoryGenerator
    def __init__(self, params: GroundVehicleParams | None = None, origin_enu=(0.,0.,0.), yaw0: float | None = None): ...
    def config(self) -> dict: ...
    def generate(self, duration_s: float, dt: float, rng: np.random.Generator) -> TruthTrajectory: ...
class UavTrajectory:  (same signatures, UavParams)
def make_trajectory(platform: str, params: dict | None = None) -> GroundVehicleTrajectory | UavTrajectory
```

**Ground vehicle.** Channels: longitudinal accel `a_s(t)` (so speed `s = ∫a_s ≥ 0`, horizontal), turn rate
`r(t)` (so `ψ = yaw0 + ∫r`, with yaw0 ~ U[−π, π) if None), road grade `γ(t)` (pulses of amplitude
U[−grade_max, grade_max], ramp 5 s, only inside cruise segments with s > 3 m/s).
Plan: `t_static` stationary, then maneuvers drawn from the grammar until duration is covered:
cruise (hold), speed change (to U(speed_target)), turn (Δψ = ±U(turn_deg), rate
`R = min(yaw_rate_max, a_lat_max/s)`; if s < min_turn_speed do a speed change first), stop (brake to 0, hold
U(stop_hold_s), accelerate to U(speed_target)). Maneuvers do not overlap in time (except grade), so the limits
hold by construction.
Kinematics: `v_n = s·[cosψ, sinψ, tanγ]`,
`a_n = [ṡcψ − sψ̇sψ, ṡsψ + sψ̇cψ, ṡ tanγ + s γ̇ sec²γ]`, jerk by differentiating again (analytic from PPoly derivatives).
Attitude: `ψ`; `θ = −(γ + pitch_gain·ṡ)`; `φ = roll_gain·(s·r)`. Euler rates analytic, then ω_b via
`body_rates_from_euler_rates`.

**UAV (multirotor/VTOL, thrust-aligned).** Channels: horizontal accel `a_s` (s = ∫a_s), turn rate r (ψ = ∫r),
vertical *velocity* `v_u(t)` (pulses of amplitude ≤ vz_max, so `a_u = v_u′`, `j_u = v_u″`). Plan: hover
`t_hover0` at alt0, then the grammar {cruise, speed change, turn, climb/descend (target alt ~
U[alt_min+10, alt_max−10]), loiter (turn of 2π·k at constant speed), hover (decelerate to 0, hold, optional
yaw turn)}. Turn rate `R = min(yaw_rate_max, a_h_max/s, g·tan(tilt_max)/s)`.
Kinematics: `v_n = [s cψ, s sψ, v_u]`, `a_n` as for the ground vehicle with a_u, and jerk `j_n` analytic.
Attitude: `f_n = a_n + [0,0,G0]`; `z_b = f_n/‖f_n‖`; `x_c = [cψ, sψ, 0]`; `y_b = (z_b × x_c)/‖·‖`;
`x_b = y_b × z_b`; `C = [x_b y_b z_b]`. Rates: `ż = (I − zzᵀ)ḟ/‖f‖` with `ḟ = j_n`;
`m = z × x_c`, `ṁ = ż × x_c + z × ẋ_c`, `ẋ_c = ψ̇[−sψ, cψ, 0]`; `ẏ = (I − yyᵀ)ṁ/‖m‖`; `ẋ = ẏ × z + y × ż`;
`ω_b = vee(Cᵀ[ẋ ẏ ż])`. att = `dcm_to_euler(C)`. (By construction `f_b = [0, 0, ‖f_n‖]`: coordinated flight.)

**Position** (both): `p(t_{k+1}) = p(t_k) + (h/2) Σ_{i=1..5} w_i v(t_k + (h/2)(1 + x_i))` with 5-point Gauss–Legendre
nodes and weights (exact to degree 9), evaluated vectorised in chunks of at most 10⁶ samples. UAV
`p_U = alt0 + ∫v_u` can use the PPoly antiderivative directly (it must agree with GL to 1e-9).

**Outputs.** `f_b = Cᵀ(a_n − [0,0,−G0])`; `TruthTrajectory(t = k·dt for k=0..N−1 with N = round(duration/dt)+1, …)`.
`meta = {"platform", "params": asdict, "maneuvers": [{"kind","t0","t1",…}], "yaw0", "limits": {...}}`.

**Validation (tests/test_sim_trajectory.py, both platforms, duration 600 s AND 3600 s, dt 0.01, 5 seeds):**
1. Consistency: `max|v − Δp/(2h)|` (central difference) ≤ 1e-3 m/s; `max|a − Δv/(2h)|` ≤ 1e-3 m/s²;
   `max|f_b − Cᵀ(a − g_n)|` ≤ 1e-9; `max‖ω_b(t_{k+½}) − Log(C_kᵀC_{k+1})/h‖` ≤ 1e-4 rad/s (ω at the midpoint = mean of k, k+1).
2. C² smoothness: `max‖a_{k+1} − a_k‖/h` ≤ 1.1 × (the jerk bound implied by params) and ≤ 10 m/s³.
3. Limits (+1% tolerance): ground `0 ≤ s ≤ v_max`, `−a_brake_max ≤ ṡ ≤ a_acc_max`, `|s·r| ≤ a_lat_max`,
   `|r| ≤ yaw_rate_max`, `|φ| ≤ 3°`, `|θ| ≤ 5°`; UAV `s ≤ v_max`, `|v_u| ≤ vz_max`, tilt `acos(z_b·e_U) ≤ tilt_max`,
   `alt_min ≤ p_U ≤ alt_max` after the initial hover, `|ṡ| ≤ a_h_max`.
4. Determinism: two calls with `np.random.default_rng(s)` for the same s give `np.array_equal` arrays; different
   s give different plans.
5. Coverage: each maneuver kind appears at least once in a 3600 s run (seed-fixed check).
6. Runtime: 3600 s at 100 Hz generates in < 10 s on the dev CPU (report the measured time).

### 11.3 `fedqpnt/sim/strapdown.py`

```python
@dataclass
class NavState: pos: np.ndarray; vel: np.ndarray; C: np.ndarray        # (3,), (3,), (3,3)
def gravity_n() -> np.ndarray                                           # (0,0,−G0); single place to swap for C-5
def strapdown_step(state: NavState, f0, w0, f1, w1, dt) -> NavState     # "causal" 2nd order, exactly §2.3
def integrate(t: np.ndarray, f_b: np.ndarray, omega_b: np.ndarray, init: NavState,
              method: str = "rk4") -> tuple[np.ndarray, np.ndarray, np.ndarray]   # pos (N,3), vel (N,3), att (N,3)
```
`method="rk4"`: classic RK4 on the state (quaternion, v, p) over each interval [t_k, t_{k+1}]. Midpoint inputs
come from 4-point cubic interpolation `u_{k+½} = (−u_{k−1} + 9u_k + 9u_{k+1} − u_{k+2})/16`, using one-sided
cubic `(5u_k + 15u_{k+1} − 5u_{k+2} + u_{k+3})/16` at the first interval and its mirror at the last.
Quaternion dynamics `q̇ = ½ q ⊗ [0, ω]`, renormalised each step. `method="causal"` loops `strapdown_step`.
**Validation:** starting from truth at k = 0, integrating the ideal `f_b, ω_b` of both generators
(600 s, dt = 0.01, 5 seeds): rk4 gives `max_t ‖p − p_true‖ < 1 m` (the required bound; expected ≪ 0.1 m)
and attitude error `max ‖Log(Ĉᵀ C)‖ < 1e-5 rad`. Causal gives **report only** (print the drift; no threshold,
because 2nd-order coning/sculling error over 600 s is expected to be metres). Also, for a 3600 s run, rk4
drift is reported (no threshold). Error theory, to put in the test docstring: the tilt error δθ gives
`½ g δθ t²`, so 1 m at 600 s needs a mean tilt error < 5.7e-7 rad, which is why a 4th-order scheme is required.

### 11.4 `fedqpnt/sim/config.py`

```python
@dataclass
class AttackSpec:  kind: str; t_start: float; t_end: float | None; severity: float = 0.0; params: dict = field(default_factory=dict)
@dataclass
class NodeConfig:
    node_id: str; platform: str = "ground"                  # "ground" | "uav"
    trajectory: dict = field(default_factory=dict)          # overrides of *Params
    imu: dict = field(default_factory=lambda: {"grade": "tactical"})
    quantum: dict = field(default_factory=lambda: {"enabled": True, "cycle_time": 1.0})
    gnss: dict = field(default_factory=lambda: {"rate_hz": 1.0})
    attacks: list[AttackSpec] = field(default_factory=list)
    join_time_s: float = 0.0; fail_time_s: float | None = None; byzantine: dict | None = None
@dataclass
class FLConfig:  enabled: bool = True; round_period_s: float = 60.; local_epochs: int = 2; lr: float = .05; batch: int = 64
                 prox_mu: float = .01; aggregator: str = "trim_nb_r"; trim_beta: float = .2; clip_c: float = 2.
                 rep_rho: float = .8; rep_q: float = .2; labels: str = "pseudo"; quorum_frac: float = .5
@dataclass
class CommsConfig: delay_median_s: float = .2; delay_sigma: float = .5; bandwidth_bps: float = 1e6; d_max_s: float = 5.
                   p_gb: float = .02; p_bg: float = .3; loss_g: float = .01; loss_b: float = .9; max_staleness: int = 3
@dataclass
class RunConfig:
    name: str; master_seed: int; duration_s: float; dt: float = 0.01; method: str = "fedqpnt"
    scenario: str = "S1"; world: dict = field(default_factory=lambda: {"gravity": "flat"})
    nodes: list[NodeConfig] = field(default_factory=list)
    fl: FLConfig = field(default_factory=FLConfig); comms: CommsConfig = field(default_factory=CommsConfig)
    fusion: dict = field(default_factory=dict); trust: dict = field(default_factory=dict); eval: dict = field(default_factory=dict)
    contract_version: str = CONTRACT_VERSION
    def to_dict(self) -> dict                       # nested plain dict (lists, not tuples)
    @classmethod
    def from_dict(cls, d: dict) -> "RunConfig"      # strict: unknown keys raise ValueError; rebuilds nested dataclasses
    def to_json(self, path) / from_json(path)       # utf-8, indent=2, sort_keys=True
    def to_yaml / from_yaml                         # only if PyYAML importable (it is in this env); JSON is canonical
    def config_hash(self) -> str                    # sha256(canonical_json)[:16]; canonical = json.dumps(to_dict(), sort_keys=True,
                                                    #   separators=(",",":"), allow_nan=False) with floats via repr; `name` EXCLUDED from hash
    def validate(self) -> None                      # dt>0; duration>0; unique node_ids; attack t_start<t_end; platform valid
```
Tests: round trip `from_dict(to_dict(c)) == c`; JSON file round trip; hash stable across processes
(check a hard-coded expected hash for a fixed config, then compute it in a `subprocess` too); hash changes when any
leaf changes; unknown key → ValueError.

### 11.5 `fedqpnt/sim/recorder.py`

```python
def code_version(root: Path | None = None) -> str   # sha256 over sorted (relative posix path + b"\0" + bytes) of fedqpnt/**/*.py, skipping __pycache__; [:16]
class RunRecorder:
    def __init__(self, root: str | Path, config: RunConfig, run_id: str | None = None, subdir: str | None = None)
        # run_id default: f"{utc:%Y%m%dT%H%M%SZ}_{config.name}_{config.config_hash()[:8]}"; dir = root/run_id[/subdir]
        # writes config.json immediately; refuses to overwrite an existing manifest.json (raises FileExistsError)
    run_dir: Path
    def log_seed(self, name: str, keys: tuple[str, ...]) -> None           # records (master_seed, keys) for manifest
    def log(self, stream: str, t: float, **fields: float | np.ndarray) -> None   # numeric only; fixed shapes per field per stream
    def log_event(self, t: float, kind: str, **data) -> None              # appended to events.jsonl immediately (json, flush)
    def flush(self) -> None     # writes series/<stream>.<chunk:05d>.npz (np.savez, fields + "t"); chunk every 10 000 rows or on flush
    def close(self, status: str = "ok") -> None   # flush + manifest.json {run_id, config_hash, code_version, contract_version,
                                                  #   python, numpy, scipy, torch (if importable), platform, seeds, t_start/t_end wall, status}
    __enter__/__exit__   # exit with exception → close(status="error: <type>")
def save_trajectory(rec: RunRecorder, traj: TruthTrajectory, stream: str = "truth") -> None
@dataclass
class RunData: config: RunConfig; manifest: dict; series: dict[str, dict[str, np.ndarray]]; events: list[dict]
def load_run(run_dir: str | Path) -> RunData      # concatenates chunks in index order; verifies config hash == manifest
```
Tests: log 25 000 rows × 3 streams (scalar, (3,), (3,3) fields) plus 10 events, close, `load_run` gives
exact (`np.array_equal`) round trip of every field, config equality, `manifest.code_version == code_version()`;
the context manager on an exception writes `status` starting with "error"; overwrite refusal; truth trajectory
round trip via `save_trajectory`.

### 11.6 Expected test command and output

`python -m pytest tests/test_sim_*.py -q` → all pass. Report runtime and the measured rk4/causal drifts.

---------------------------------------------------------------------------------------------------

## 12. References

Verified this session (title, venue and DOI checked online): Lautier et al. 2014 APL 105:144102
doi:10.1063/1.4897358 · Cheiney et al. 2018 Phys. Rev. Applied 10:034030 doi:10.1103/PhysRevApplied.10.034030 ·
Templier et al. 2022 Sci. Adv. 8:eadd3854 doi:10.1126/sciadv.add3854 · Wang et al. 2021 arXiv:2103.09378 ·
Baruch, Baruch & Goldberg 2019 NeurIPS 32 (URL in §4.5).

Standard references, not re-checked online this session (Master: spot-check the DOIs):
McMahan et al. 2017 AISTATS arXiv:1602.05629 · Li et al. 2020 MLSys arXiv:1812.06127 · Yin et al. 2018 ICML
arXiv:1803.01498 · Sun et al. 2019 arXiv:1911.07963 · Blanchard et al. 2017 NeurIPS ("Machine learning with
adversaries") · Cao et al. 2021 NDSS arXiv:2012.13995 · Xie et al. 2019 arXiv:1903.03934 · Solà 2017
arXiv:1711.02508 · Groves, *Principles of GNSS, Inertial, and Multisensor Integrated Navigation Systems*,
2nd ed., Artech House 2013 · Anderson & Moore, *Optimal Filtering*, Prentice-Hall 1979 · Bar-Shalom, Li &
Kirubarajan 2001, Wiley, doi:10.1002/0471221279 · Page 1954 Biometrika doi:10.1093/biomet/41.1-2.100 ·
Psiaki & Humphreys 2016 Proc. IEEE 104(6) doi:10.1109/JPROC.2016.2526658 · Wilcoxon 1945 doi:10.2307/3001968 ·
Demšar 2006 JMLR 7:1–30 · Holm 1979 Scand. J. Statist. 6:65–70 · Savage 1998 JGCD 21(1) doi:10.2514/2.4228 (strapdown algorithms).

UNVERIFIED: RTCA DO-229 exact RAIM Pfa figure (S1 justification); Baseline source papers (Khan 2025, Chai 2025,
Meng 2025, Gu 2021, Pardhasaradhi 2022; DOIs to be taken from the proposal); vehicle roll/pitch gradients
(labelled ASSUMPTION).
