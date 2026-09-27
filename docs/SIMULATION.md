# Trajectory and Strapdown Integration

**Purpose.** This document specifies the simulated vehicle trajectory generation and inertial integration (mechanisation) used by FedQPNT to produce ground-truth states for evaluation.

## Overview of simulation components

The simulation implements three separate but coordinated layers:

1. **Trajectory generation** (`fedqpnt/sim/trajectory.py`): produces smooth 6-DoF vehicle trajectories (position, velocity, attitude, rates) as functions of time via piecewise-polynomial construction. Two vehicle types: ground vehicles and quadrotor UAVs.
2. **Strapdown integration** (`fedqpnt/sim/strapdown.py`): numerically integrates simulated IMU samples (accelerometer and gyroscope) using the mechanised equations to propagate attitude and velocity, mimicking how a real inertial navigation system accumulates error. Two integration methods: causal 2nd-order trapezoid-and-coning (real-time eligible) and RK4 (offline, higher accuracy).
3. **Simulation configuration and recording** (`fedqpnt/sim/config.py`, `recorder.py`): standardizes run parameters, deterministic seeding, and storage of truth and attack labels in indexed numpy archives (npz) plus event logs.

## Trajectory generation

### Ground vehicle trajectories

A ground vehicle's trajectory is defined by a planar track (ENU x-y position and heading ψ) plus velocity magnitude s(t) = ds/dt (forward speed along the track). The vertical z and pitch θ are determined from a simulated road-grade channel (elevation change), kept below a configurable maximum slope.

**Components:**
- **Longitudinal (s) channel**: velocity magnitude, built as a sum of non-overlapping quintic-smoothstep trapezoid pulses. Each pulse spans a ramp period `ramp_s` from one velocity to another, followed by a constant-velocity cruise segment. A managed grammar ensures coverage of all maneuver types (accelerations, decelerations, constant-velocity straightaways) within each 3600 s scenario.
- **Heading (ψ) channel**: yaw angle change via turn-rate pulses. Overlays on the velocity channel; turns are coordinated so body-frame acceleration perpendicular to the track obeys vehicle dynamics (e.g., ψ̇ = (g/s) tan φ for a tyre-constrained ground vehicle with roll φ limited to ±30° by default).
- **Grade (z, θ) channel**: elevation and pitch. Built as a separate quintic-pulse channel, holds constant between maneuvers, with maximum slope grade_max ∈ [0.1, 0.4] (road gradient). Ramp time `ramp_s = 5 s` (fixed). Grade pulses occur only within cruise segments (constant-speed sections).

**Construction method:** All channels are `scipy.interpolate.PPoly` objects (piecewise polynomials, degree ≤ 5). Position is derived by numerical integration (5-point Gauss-Legendre quadrature on each segment) to ensure closure (p(t) is exactly the integral of v(t)).

### UAV trajectories

A UAV is modeled as a rigid body with thrust aligned with the body z-axis (nose), constrained by a maximum tilt angle `tilt_max = 45°` (pitch/roll magnitude), minimum forward speed `s_min = 2 m/s`, and maximum vertical velocity `vz_max` (typically 4 m/s).

**Vertical channel specification (per D-017 correction):** The vertical **acceleration** `a_u(t)` is a C² quintic-pulse channel (same smoothness and construction as the ground vehicle's acceleration channel). Vertical velocity `v_u(t) = ∫ a_u dt` is therefore C³. This ensures smoothness parity with the ground vehicle's position channel (both C³).

- Climb/descend maneuvers are modeled as pairs of mirrored acceleration pulses: an accel-up bump (0 → peak) over duration `ramp_s`, followed by an optional constant-altitude hold at peak velocity, then an accel-down bump (peak → 0) mirror. If altitude change is small, both pulses alone span the change exactly (no hold).

- Commanded peak vertical velocity `vz_peak = min(vz_max, altitude_change / (2 * area_under_one_bump))`. Since the bump area scales linearly with peak, `vz_peak` is solved in closed form.

**Attitude kinematics:** At each instant, the UAV's body attitude (roll φ, pitch θ, yaw ψ) is determined by thrust alignment: body z-axis aligns with `(a_n - [0, 0, g0])` (net acceleration in body frame), keeping the body x-axis (nose) in the horizontal plane (zero roll, φ = 0) unless a yaw maneuver is active (turn-rate compensation adds roll to bank into turns).

**Turn-rate cap:** yaw_rate is limited by `min(yaw_rate_max, a_h_max/s, g*tan(tilt_max)/s)` where `a_h_max` is the maximum horizontal acceleration available and `s` is forward speed. When `s` is numerically zero (e.g., on transition from hover to forward flight), the denominator is protected with `max(s, 1e-6)` to avoid division by zero.

### Parameter table: trajectory generation

| Parameter | Value | Unit | Source | Status |
|-----------|-------|------|--------|--------|
| Longitudinal ramp time `ramp_s` | 5 | s | config (ASSUMPTION) | configurable per run |
| Ground grade_max | 0.3 | (unitless) | config (ASSUMPTION) | typical road grade |
| Ground max roll φ_max | 30 | deg | ARCHITECTURE §11.1 | config |
| UAV vz_max (default) | 4.0 | m/s | config (ASSUMPTION) | configurable |
| UAV tilt_max | 45 | deg | config (ASSUMPTION) | configurable |
| UAV yaw_rate_max | 90 | deg/s | ARCHITECTURE §11.2 | config |
| Scenario duration | 3600 | s | ARCHITECTURE §11.1 | per scenario |
| Global tick rate dt | 0.01 | s (100 Hz) | D-003 | fixed |

### Validation: trajectory generation runtime

**Configuration:** Windows 11, Python 3.13, numpy 2.3.

| Trajectory type | Duration | Runtime | Status |
|-----------------|----------|---------|--------|
| Ground vehicle 3600 s | 3600 s | 0.44 s | **PASS** (< 10 s requirement) |
| UAV 3600 s | 3600 s | 0.69 s | **PASS** |

**Maneuver grammar coverage:** The deterministic prefix (`rng.permutation`) of all maneuver types within the first ~10-15 min of each scenario ensures every scenario includes at least one instance of each of: constant-velocity straight, acceleration, deceleration, left turn, right turn, climb, descend, (ground only: grade change). This is an acceptance test (`test_trajectory_grammar_coverage`): **113 pytest tests pass**, including 20 prior UAV failures resolved by the D-017 fix (vertical-channel smoothness).

---

## Strapdown integration: mechanised equations

The strapdown algorithm propagates attitude and velocity using IMU measurements and gravity. The filter operates in the ENU (East-North-Up) local-level navigation frame.

### Coordinate frames

- **ENU (Earth-centered navigation):** local-level tangent plane, East (x), North (y), Up (z). Origin at `ORIGIN_LLH` (default 48.8566° N, 2.2922° E, Paris area).
- **Body frame (FLU):** Forward (x), Left (y), Up (z), origin at vehicle center-of-mass. Attitude: ZYX Euler angles (ψ yaw, θ pitch, φ roll) with `θ > 0 = nose down` (REP-103).
- **Gravity:** uniform in the flat-world model, `g0 = 9.80665 m/s²` (D-003). Specific force measured by accelerometer: `f_b = C^T(a_n + [0, 0, g0])` where `a_n` is the true acceleration in the ENU frame and `C = R_nb` is the body-to-ENU DCM.

### Mechanisation equations (2nd-order trapezoid + coning)

Per ARCHITECTURE.md §2.3, the strapdown step at tick k (timestep dt) computes:

1. **Incremental rotation (coning correction):**
   - Raw: `θ_k = ω_b dt` (small-angle body-rate increment)
   - Coning (2nd-order): `θ_k ← θ_k + (1/12) * θ_{k-1} × θ_k` (cross-product)
   - Update quaternion: `q_k ← q_{k-1} ⊗ Exp(θ_k / 2)`

2. **Incremental velocity (sculling correction):**
   - Raw: `Δv_k = f_b dt` (specific-force increment)
   - Sculling (2nd-order): `Δv_k ← Δv_k + (1/12) * θ_{k-1} × Δv_k`
   - Coriolis-free environment: velocity update `v_k = v_{k-1} + C_k * Δv_k + [0, 0, g0] dt`

3. **Position update:**
   - Trapezoidal: `p_k = p_{k-1} + (v_{k-1} + v_k) dt / 2`

where `×` is the cross product, `Exp/Log` are SO(3) exponential/logarithm, and `⊗` is quaternion multiplication.

**Time constants:**
- Per-tick integration: dt = 0.01 s (100 Hz)
- Typical run duration: 600–3600 s (10–60 min)

### Strapdown closure (accuracy validation)

**Offline validation:** integrate truth trajectory (no noise) through 600 s, using the ground truth as IMU input, and compare the re-integrated trajectory against the original. Five independent seeds, flat-world model:

| Vehicle | Test | Max position error | Max attitude error | Status |
|---------|------|--------------------|--------------------|--------|
| Ground | RK4, 600 s | < 1 m (observed: well under) | < 1e-5 rad (observed: well under) | **PASS** |
| UAV | RK4, 600 s | < 1 m (observed: well under) | < 1e-5 rad (observed: well under) | **PASS** |
| Ground | Causal, 600 s | 0.295 m | 2.9e-6 rad | (report-only, no requirement) |
| UAV | Causal, 600 s | 5.62 m | 1.7e-5 rad | (report-only; expected 2nd-order error) |
| Ground | RK4, 3600 s | 0.049 m | 1.3e-8 rad | (report-only) |
| UAV | RK4, 3600 s | 1.14 m | 2.3e-7 rad | (report-only) |

**Self-consistent Schuler model** (world="schuler_tangent", per D-017):
- Ground RK4, 600 s: max position error 8e-4 m (far tighter than flat, consistent with Schuler's bounded-oscillation theory).
- UAV RK4, 600 s: max position error 0.018 m.

### Parameter table: strapdown integration

| Parameter | Value | Unit | Source | Status |
|-----------|-------|------|--------|--------|
| Global tick dt | 0.01 | s | D-003 | fixed |
| Gravity g0 | 9.80665 | m/s² | WGS-84 standard | fixed |
| Coriolis (2D/3D) | off / on per `world` kwarg | — | ARCHITECTURE §2.6, D-017 | configurable |
| Quaternion algebra | Hamilton (wxyz order) | — | ARCHITECTURE §0 | fixed |
| Euler convention | ZYX, θ>0 nose-down, FLU | — | ARCHITECTURE §0, D-003 | fixed |

### Runtime benchmark

**Configuration:** Windows 11, Python 3.13, single ground-vehicle node, clean (no attack) GNSS epoch at 1 Hz.

| Method | Trajectory | Wall time per sim hour |
|--------|-----------|------------------------|
| Causal (2nd-order trapezoid) | 600 s ground | 19.1 s / sim-hour |
| RK4 | 600 s ground | 33.2 s / sim-hour |

Both are dominated by the tight loop's rotations arithmetic (skew, vee, exp, log). Prior to an internal optimization pass (replaced batch-capable calls with lean single-sample math in the hot loop), both were ~4× slower. For the S14 4-hour multi-node experiments, the 19–33 s/hour budget is feasible (E2E harness must schedule accordingly; see DECISION_LOG.md D-017 risk note).

---

## Configuration and recording

### Configuration (`fedqpnt/sim/config.py`)

A `RunConfig` dataclass specifies all simulation parameters: trajectory type and parameters, sensor noise models, attack scenario, GNSS rates, quantum-sensor cycle time, FL tuning, random seed, and output paths. Configuration is serialized to JSON (canonical ordering, no whitespace, SHA256 hash for content-based tracing).

**Key fields:**
- `name` (str): human-readable identifier (not included in hash)
- `seed` (int): master random seed (D-005: hierarchical RNG streams)
- `traj_config` (GroundVehicleConfig | UavConfig): vehicle type and parameters
- `gnss_config` (GnssConfig): signal model and attack parameters
- `quantum_config` (QuantumSensorConfig): CAI cycle time, noise source (synthetic/replay)
- `fl_config` (FLConfig): round period, aggregator type, learning rate
- `world` (str): "flat" (default) or "schuler_tangent" gravity model (D-017 PROPOSED-DECISION 1)

**Determinism guarantee:** same config + same seed = identical run (used for paired statistical tests, D-005).

### Recording (`fedqpnt/sim/recorder.py`)

A `RunRecorder` captures simulation outputs in real time:

- **Truth/labels** (environment-only, evaluation use only): truth state, attack labels, simulator version, config hash
- **Navigation/trust** (agent outputs): estimated state, trust weights, detector probability, innovations, features
- **Events** (jsonl per-line logs): anomalies (GNSS outage, IMU gap), FL rounds, detector state changes

**Format:** 
- Chunked numpy `.npz` archives (compressed, 100 samples per chunk for I/O efficiency)
- Manifest JSON (sample count, chunk offsets, field names)
- Event log (JSON Lines, one event per line)

**Code version tracking:** `code_version()` reads the git commit hash (or falls back to a `pyproject.toml` version string if .git is unavailable) and stores it in the run manifest, enabling post-hoc reproducibility checks.

---

## Related decisions and design notes

- **D-001:** Pure software simulation (no GNSS RF hardware, no quantum hardware). Realism grounded in published attack signatures and real quantum-sensor data (D-008, D-014, D-015).
- **D-002:** Results reported exactly as measured; no scenario dropping; all model parameters either sourced or labelled ASSUMPTION. Sensitivity sweeps mandatory for all ASSUMPTION values before paper submission.
- **D-003:** Local-level ENU frame, single global 100 Hz tick, body frame FLU with ZYX Euler angles.
- **D-005:** Hierarchical deterministic RNG streams (master_seed, node_id, component) for reproducibility and paired tests.
- **D-017 (Master ruling):** UAV vertical channel was a spec defect (v_u itself vs. a_u = dv_u/dt). Fixed: a_u is now C² pulse, so v_u is C³ (matching ground-vehicle s(t) smoothness). Acceptance bounds unchanged; no minimum ramp_s needed after fix.
- **PROPOSED-DECISION 1 (D-017 accepted):** `world="flat"` kwarg on trajectory generators for self-consistent Schuler-tangent gravity model if needed (pending ARCHITECT guidance on whether Earth-rate matters for cold-atom bias).

---

## Limitations and assumptions

- **Trajectory generation:** Maneuver grammar is deterministic after the permutation prefix, then weighted-random; true randomness only in the random draw's order, not the envelope/amplitude of maneuvers. Turning radius and acceleration limits are soft (vehicle dynamics are not modeled in closed-loop; truth is kinematic).
- **Strapdown integration:** Assumes zero Coriolis acceleration (valid for ~100 km spatial extent and <1000 s timescales typical of navigation scenarios). Earth rotation and gravity gradient not modeled in flat-world mode; toggled on via `world="schuler_tangent"` if sensitivity to those is needed (deferred pending ARCHITECT decision).
- **Coning and sculling corrections:** limited to 2nd-order. Higher-order terms (3rd-order sculling, gyroscopic effects) are neglected; adequate for IMU rates ≤ 100 Hz and step durations ≥ 1 ms.
- **Clock version tracking:** if `.git` is not a valid repository (e.g., code in a zip or shallow clone), `code_version()` falls back to `pyproject.toml` version and warns; determinism within a session is still guaranteed but reproducibility across machines may require manual intervention.
