# SIM_NOTES (WP-1.2, SIM-IMPL agent)

Implements `fedqpnt/sim/{rotations,trajectory,strapdown,config,recorder}.py`
exactly per ARCHITECTURE.md section 11, against contract v0.2 (core already
carries C-1..C-7; `fedqpnt/core/world.py` provides `gravity_n`/`gravity_gradient`
for `{"flat","schuler_tangent"}`, used directly by `strapdown.py`).

## What was built

* `rotations.py`: skew/vee, Euler<->DCM (ZYX, psi=0 East CCW, theta>0 nose-down),
  SO(3) exp/log (Taylor near 0, explicit axis extraction near pi), Hamilton
  quaternions, body-rate <-> Euler-rate conversions (section 0 formulas).
* `trajectory.py`: `GroundVehicleTrajectory` / `UavTrajectory`, channels built
  as `scipy.interpolate.PPoly` sums of non-overlapping quintic-smoothstep
  trapezoid pulses (`build_channel`), maneuver grammar with a forced
  one-of-each-kind prefix (guarantees the coverage criterion regardless of
  seed), position via 5-point Gauss-Legendre quadrature, UAV thrust-aligned
  attitude/rates per the brief's closed forms.
* `strapdown.py`: `strapdown_step` (causal, 2nd-order trapezoid+coning, exactly
  section 2.3), `integrate` with `method="causal"` (loops `strapdown_step`) and
  `method="rk4"` (classic RK4 with 4-point-cubic-interpolated midpoint inputs,
  section 11.3).
* `config.py`: `RunConfig` and nested dataclasses exactly per section 11.4;
  canonical-JSON sha256 config hash (name excluded); strict `from_dict`.
* `recorder.py`: `RunRecorder`/`load_run`/`save_trajectory`/`code_version`
  exactly per section 11.5; chunked npz series, jsonl events, manifest.

## PROPOSED-DECISIONs (brief silent or ambiguous; conservative choices taken)

1. **`generate(..., world="flat")` extra kwarg** on both trajectory
   generators (not in the brief's literal signature, which hard-codes
   `f_b = C^T(a_n - [0,0,-G0])`). Default preserves the brief exactly;
   passing `world="schuler_tangent"` makes `f_b`/`g_n` position-dependent via
   `core.world.gravity_n`, so the closure test the Master asked for
   (`world="schuler_tangent"`) is self-consistent (truth generation and
   strapdown integration share the same gravity model) rather than feeding
   flat-gravity truth into a Schuler-aware integrator, which would just
   measure model mismatch instead of the mechanisation.
2. **Grade pulse hold duration** (`Th`) for the ground vehicle's road-grade
   channel: not specified by the brief beyond "amplitude U[-grade_max,
   grade_max], ramp 5 s, only inside cruise segments with s > 3 m/s". Chosen
   to span the whole enclosing cruise segment (`Th = cruise_duration - 2*Tr`,
   skipped if the segment is shorter than `2*Tr`).
3. **Maneuver-grammar coverage**: instead of relying on the weighted random
   draw to hit every maneuver kind within 3600 s (brief's "seed-fixed check"
   implies the ARCHITECT already checked a specific seed), the planner
   shuffles all kinds into a forced prefix once (`rng.permutation`), then
   switches to the weighted draw. Guarantees the coverage acceptance test
   passes for any seed while still using the same weights/grammar afterward.
4. **UAV turn-rate cap** uses `min(yaw_rate_max, a_h_max/s, g*tan(tilt_max)/s)`
   exactly per brief; when `s` is (numerically) zero (e.g. loiter/turn right
   after hover) the cap falls back to `yaw_rate_max` via a `max(s, 1e-6)` floor
   to avoid division by zero — a turn commanded at zero forward speed is
   physically a stationary yaw, bounded only by `yaw_rate_max`.
5. `code_version()`'s implicit project root is `Path(__file__).resolve()
   .parents[2]` (i.e. `fedqpnt/sim/recorder.py -> .. -> .. `), matching this
   repo's layout (`fedqpnt/` directly under the project root); overridable via
   the `root` argument, as specified.

## Validation numbers (measured on this machine, Windows 11 / Python 3.13)

Trajectory generation (3600 s @ 100 Hz, brief requires < 10 s):
* ground: 0.44 s; uav: 0.69 s.

Strapdown runtime (measured on the ground-vehicle 600 s case, scaled to
s/simulated-hour):
* rk4: 33.2 s/hour; causal: 19.1 s/hour.
(Both were ~4x slower before an internal optimisation pass that replaced the
batch-capable `rotations.py` calls with lean single-sample math inside the
RK4/causal hot loop -- needed headroom for the later 4-hour S14 runs.)

Strapdown closure (rk4, offline validation scheme, 5 seeds, flat world,
required bounds: pos < 1 m, att < 1e-5 rad):
* ground 600 s: all seeds pass (max observed well under bound).
* uav 600 s: all seeds pass (max observed well under bound).

Strapdown closure, report-only (no threshold per brief):
* causal, 600 s: ground max pos err 0.295 m / att err 2.9e-6 rad; uav max pos
  err 5.62 m / att err 1.7e-5 rad (2nd-order coning/sculling error, as
  expected -- uav's larger error reflects its generally larger and
  faster-varying angular rates from the thrust-aligned attitude model).
* rk4, 3600 s: ground max pos err 0.049 m / att err 1.3e-8 rad; uav max pos
  err 1.14 m / att err 2.3e-7 rad (uav exceeds the 600 s-scale 1 m bound
  brief only requires at 600 s; not a hard failure since 3600 s is
  explicitly "report only").
* rk4, 600 s, `world="schuler_tangent"` (self-consistent truth+integration,
  PROPOSED-DECISION 1): ground max pos err 8e-4 m; uav max pos err 0.018 m --
  both far tighter than flat, consistent with Schuler's bounded-oscillation
  error growth vs flat's unbounded t^2 growth (ARCHITECTURE.md section 2.6).

`pytest tests/test_sim_*.py -q`: **113 passed** (see D-017 fix below; the
prior 20 UAV failures are resolved, not tolerance-loosened).

## D-017 (Master ruling): UAV vertical channel was a spec defect, now fixed

The original section-11.2 reading built the UAV vertical channel as `v_u(t)`
*itself* being the C^2 quintic-pulse channel ("vertical velocity v_u(t)
(pulses of amplitude <= vz_max)"), one order less smooth than ground's
`s(t) = integral(a_s)` (C^3, since `a_s` is the C^2 pulse and integration
raises smoothness by one order). Measured consequences before the fix: the
finite-difference accel-consistency check (`<=1e-3 m/s^2`) was exceeded by
~15-20% at climb/descend pulse boundaries (10/20 uav param combos), and the
snap bound (`<=10 m/s^3`) was exceeded by ~2.6% at full-amplitude climb
pulses with `UavParams(vz_max=4.0, ramp_s=1.5)` (10/20 combos) -- both exact,
deterministic, seed-independent consequences of that one-order smoothness
gap, not implementation bugs.

**Master ruling D-017**: this is a spec defect, not a bounds problem -- fix
the generator, keep the bounds. Implemented in `trajectory.py`:

* The vertical channel is now `a_u(t)` (vertical **acceleration**), a C^2
  quintic-pulse channel, same design as `a_s`. `v_u(t) = a_u.antiderivative()`
  is therefore C^3, matching ground's `s(t)` exactly. Altitude is
  `alt0 + a_u.antiderivative().antiderivative()(t)` (exact PPoly double
  antiderivative, no hand calculus).
* Each climb/descend maneuver is now two Th=0 ("bump") pulses on `a_u`: an
  accel-up bump (0 -> vz_peak over ramp `ramp_s`, i.e. `ramp_s` is the
  accel-pulse's own ramp/duration, per D-017's guidance) and, after an
  optional zero-acceleration hold (constant-`vz_peak` cruise-climb), a
  mirrored accel-down bump (vz_peak -> 0). `vz_peak = vz_max` when the
  altitude change is large enough for both full-amplitude bumps to fit;
  otherwise `vz_peak` is reduced so the two bumps alone cover the whole
  altitude change exactly (no hold) -- altitude gained by one bump is exactly
  linear in `vz_peak` for fixed `ramp_s` (the bump shape only rescales), so
  this reduction is a closed-form division, not a search.
* `a_z_max` (`UavParams`) is still unused, unchanged from before this fix --
  the brief's own narrative never wires it into a formula either (only the
  dataclass declares it); D-017 did not ask for it to be enforced here.
* No acceptance bound was changed. At the brief's literal defaults
  (`vz_max=4.0, ramp_s=1.5`) the snap bound is no longer binding (measured
  peak snap ~3.8 m/s^3, well under 10), so **no minimum `ramp_s` needed to be
  reported** -- the D-017-directed fix alone resolved both findings without
  touching `ramp_s`.
