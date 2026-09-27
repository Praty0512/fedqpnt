"""Classical IMU model (WP-2.2), IEEE Std 952-1997 / 1293-1998 style error terms.

Error budget per axis (accelerometer and gyroscope, symmetric treatment):
  * Turn-on bias      : constant-per-run offset, drawn ~ N(0, sigma_turn_on).
  * Bias instability  : first-order Gauss-Markov (GM1) process, tuned so its
                         Allan-deviation minimum matches the datasheet
                         "in-run bias stability" B (flicker-noise floor
                         approximation). Formula/tuning: El-Sheimy, Hou & Niu
                         (2008), IEEE Trans. Instrum. Meas. 57(1):140-149,
                         Table II: for a GM1 process with correlation time
                         tau_c, the Allan deviation reaches a minimum near
                         tau ~= 1.89*tau_c of magnitude ADEV_min ~= 0.664*sigma_gm
                         (sigma_gm = process stationary std). We invert this to
                         get sigma_gm = B / 0.664 for a chosen tau_c
                         (correlation time is not usually given on a
                         datasheet -> ASSUMPTION, see SENSOR_NOTES.md).
  * (Angle/Velocity) random walk : white noise on the rate/specific-force
                         sample, std = N / sqrt(dt), giving ADEV(tau) = N/sqrt(tau)
                         (IEEE Std 952-1997 Annex C).
  * Rate random walk  : integrated white noise (random walk of the bias),
                         driven by K [unit/s/sqrt(hr) or similar], giving
                         ADEV(tau) = K*sqrt(tau/3). Included but small/zero
                         for MEMS-grade parts where it is rarely specified
                         (ASSUMPTION = 0 unless cited).
  * Scale factor error : constant-per-run multiplicative error ~ N(0, sigma_sf).
  * Misalignment       : constant-per-run small-angle cross-axis coupling.
  * Quantization        : round to the datasheet resolution / LSB.
  * Saturation          : clip to the datasheet dynamic range.

Grades (see docs/specs/raw/SENSOR_NOTES.md for full citations):
  * "consumer_mems"  : Bosch BMI088 (automotive/consumer MEMS IMU).
  * "industrial_mems": Analog Devices ADIS16470.
  * "tactical"       : Honeywell HG1700 (AG58 variant, RLG + quartz RBA).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from fedqpnt.core.types import ImuSample, TruthState

DEG2RAD = np.pi / 180.0


def _gm1_theta(dt: float, tau_c: float) -> float:
    return float(np.exp(-dt / tau_c))


@dataclass
class AxisErrorParams:
    """Error-term parameters for one physical channel (accel xyz or gyro xyz),
    isotropic across the 3 axes (a common simplification; real parts have
    minor axis-to-axis spread not modelled here -> ASSUMPTION)."""

    turn_on_bias_std: float          # [unit], 1-run-constant bias std
    bias_instability: float          # [unit], ADEV flicker floor B
    bias_instability_tau_c: float    # [s], GM1 correlation time (ASSUMPTION unless cited)
    random_walk: float               # [unit * sqrt(s)] i.e. ADEV(tau) = N/sqrt(tau)
    rate_random_walk: float          # [unit / sqrt(s)] i.e. ADEV(tau) = K*sqrt(tau/3); 0 if unspecified
    scale_factor_std: float          # [-], 1-sigma relative scale factor error, constant per run
    misalignment_std: float          # [rad], 1-sigma small-angle cross-axis coupling, constant per run
    resolution: float                # [unit], quantization LSB
    range_max: float                 # [unit], saturation limit (symmetric +-)


@dataclass
class ImuGradeConfig:
    name: str
    rate_hz: float
    accel: AxisErrorParams
    gyro: AxisErrorParams
    sources: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Cited/assumed grade parameter tables. See docs/specs/raw/SENSOR_NOTES.md.
# ---------------------------------------------------------------------------

def _consumer_mems() -> ImuGradeConfig:
    # Bosch BMI088 (automotive-grade consumer MEMS IMU).
    # Accel noise density 180 ug/sqrt(Hz) up to 230 pg/sqrt(Hz) at +-24g range
    # (Bosch datasheet BST-BMI088-DS001, "Spectral noise density"); we use the
    # +-6g range figure of 180 ug/sqrt(Hz) as representative for a vehicle/UAV
    # platform. Accel bias instability ~10 mg and gyro bias instability
    # ~1.0 deg/h are vendor product-flyer figures (BST-BMI088-FL000), not the
    # formal datasheet table -> marked ASSUMPTION-grade in SENSOR_NOTES.
    # Gyro rate noise density 0.014 dps/sqrt(Hz) (datasheet).
    accel = AxisErrorParams(
        turn_on_bias_std=0.5 * 9.80665e-2,   # ~50 mg turn-on repeatability, ASSUMPTION
        bias_instability=10e-3 * 9.80665,     # 10 mg -> m/s^2 (vendor flyer, ASSUMPTION-grade)
        bias_instability_tau_c=100.0,          # ASSUMPTION (typical MEMS flicker knee ~ 10-300 s)
        random_walk=180e-6 * 9.80665,          # 180 ug/sqrt(Hz) -> (m/s^2)/sqrt(Hz) == m/s * sqrt(s) walk coeff (datasheet)
        rate_random_walk=0.0,                  # not specified -> ASSUMPTION 0
        scale_factor_std=0.001,                # 0.1% typical MEMS scale factor, ASSUMPTION
        misalignment_std=0.001,                # ~0.057 deg, ASSUMPTION (typical PCB mount)
        resolution=24 * 9.80665 / 2 ** 16,     # 16-bit over +-24g range (datasheet)
        range_max=24 * 9.80665,
    )
    gyro = AxisErrorParams(
        turn_on_bias_std=1.0 * DEG2RAD,        # ASSUMPTION, ~1 deg/s turn-on
        bias_instability=1.0 * DEG2RAD / 3600.0,   # 1.0 deg/h (vendor flyer, ASSUMPTION-grade)
        bias_instability_tau_c=100.0,          # ASSUMPTION
        random_walk=0.014 * DEG2RAD,            # 0.014 dps/sqrt(Hz) (datasheet); already in the ADEV(tau)=N/sqrt(tau) convention, NO sqrt(hr)->sqrt(s) conversion needed (unlike ADIS16470/HG1700 below, which are cited in deg/sqrt(hr))
        rate_random_walk=0.0,
        scale_factor_std=0.001,
        misalignment_std=0.001,
        resolution=2000 * DEG2RAD / 2 ** 16,   # 16-bit over +-2000 dps range (datasheet)
        range_max=2000 * DEG2RAD,
    )
    return ImuGradeConfig(
        name="consumer_mems", rate_hz=100.0, accel=accel, gyro=gyro,
        sources={
            "accel_random_walk": "Bosch BMI088 datasheet BST-BMI088-DS001, 'Spectral noise density' = 180 ug/sqrt(Hz) (+-6g range)",
            "gyro_random_walk": "Bosch BMI088 datasheet BST-BMI088-DS001, gyro rate noise density = 0.014 dps/sqrt(Hz)",
            "bias_instability": "ASSUMPTION-grade: Bosch BMI088 product flyer BST-BMI088-FL000 ('gyro bias instability < 2 deg/h', accel bias instability ~10 mg); not in the formal datasheet table",
        },
    )


def _industrial_mems() -> ImuGradeConfig:
    # Analog Devices ADIS16470 datasheet (Rev. C).
    # Gyro: bias instability 8 deg/h, ARW 0.34 deg/sqrt(hr), rate noise
    # density 0.008 dps/sqrt(Hz), range +-2000 dps.
    # Accel: bias instability 13 ug (in-run), range +-40 g.
    # Accel VRW not located in public excerpts -> ASSUMPTION, derived
    # consistent with 16-bit-class MEMS at this grade (see SENSOR_NOTES).
    arw_rad_sqrt_s = 0.34 * DEG2RAD / 60.0     # deg/sqrt(hr) -> rad/sqrt(s): /60 converts sqrt(hr)->sqrt(min)... see note below
    # deg/sqrt(hr) -> rad/sqrt(s): 1 sqrt(hr) = sqrt(3600 s) = 60 sqrt(s)
    arw_rad_sqrt_s = 0.34 * DEG2RAD / 60.0
    accel = AxisErrorParams(
        turn_on_bias_std=0.01 * 9.80665,       # ~10 mg, ASSUMPTION (industrial-grade turn-on)
        bias_instability=13e-6 * 9.80665,      # 13 ug in-run bias stability (datasheet)
        bias_instability_tau_c=200.0,          # ASSUMPTION
        random_walk=25e-6 * 9.80665,           # ASSUMPTION: ~25 ug/sqrt(Hz), typical for this class (see SENSOR_NOTES)
        rate_random_walk=0.0,
        scale_factor_std=0.0005,               # ASSUMPTION, 500 ppm typical
        misalignment_std=0.0003,               # ASSUMPTION, ~0.017 deg factory calibrated residual
        resolution=40 * 9.80665 / 2 ** 20,     # datasheet: +-40g range, 20-bit-equivalent resolution assumption
        range_max=40 * 9.80665,
    )
    gyro = AxisErrorParams(
        turn_on_bias_std=0.1 * DEG2RAD,        # ASSUMPTION
        bias_instability=8.0 * DEG2RAD / 3600.0,   # 8 deg/h in-run bias stability (datasheet)
        bias_instability_tau_c=200.0,          # ASSUMPTION
        random_walk=arw_rad_sqrt_s,            # 0.34 deg/sqrt(hr) (datasheet)
        rate_random_walk=0.0,
        scale_factor_std=0.0005,
        misalignment_std=0.0003,
        resolution=2000 * DEG2RAD / 2 ** 20,
        range_max=2000 * DEG2RAD,
    )
    return ImuGradeConfig(
        name="industrial_mems", rate_hz=100.0, accel=accel, gyro=gyro,
        sources={
            "gyro_bias_instability": "Analog Devices ADIS16470 datasheet Rev. C, Table 1: In-Run Bias Stability = 8 deg/hr",
            "gyro_random_walk": "ADIS16470 datasheet Rev. C, Table 1: Angular Random Walk = 0.34 deg/sqrt(hr)",
            "accel_bias_instability": "ADIS16470 datasheet Rev. C, Table 1: In-Run Bias Stability = 13 ug",
            "accel_random_walk": "ASSUMPTION: not located in accessible excerpt; plausible range 20-40 ug/sqrt(Hz) for this class",
        },
    )


def _tactical() -> ImuGradeConfig:
    # Honeywell HG1700 (AG58 variant): RLG gyro bias in-run stability
    # ~1 deg/h, angular random walk 0.125 deg/sqrt(hr) (Honeywell HG1700
    # datasheet M61-0115-000-003). Accelerometer (quartz RBA) figures not
    # located in accessible excerpts -> ASSUMPTION using representative
    # tactical-grade quartz-accelerometer figures (bias instability ~25-50
    # ug, VRW ~10-20 ug/sqrt(Hz)), documented in SENSOR_NOTES with the
    # plausible range.
    arw_rad_sqrt_s = 0.125 * DEG2RAD / 60.0
    accel = AxisErrorParams(
        turn_on_bias_std=0.002 * 9.80665,      # ASSUMPTION, ~2 mg
        bias_instability=30e-6 * 9.80665,      # ASSUMPTION, ~30 ug (tactical quartz RBA class)
        bias_instability_tau_c=300.0,          # ASSUMPTION
        random_walk=15e-6 * 9.80665,           # ASSUMPTION, ~15 ug/sqrt(Hz)
        rate_random_walk=0.0,
        scale_factor_std=0.0001,               # ASSUMPTION, 100 ppm
        misalignment_std=0.0001,               # ASSUMPTION
        resolution=20 * 9.80665 / 2 ** 20,
        range_max=20 * 9.80665,
    )
    gyro = AxisErrorParams(
        turn_on_bias_std=0.01 * DEG2RAD,       # ASSUMPTION
        bias_instability=1.0 * DEG2RAD / 3600.0,   # 1 deg/h in-run bias stability (Honeywell HG1700 AG58 datasheet)
        bias_instability_tau_c=300.0,          # ASSUMPTION
        random_walk=arw_rad_sqrt_s,            # 0.125 deg/sqrt(hr) (Honeywell HG1700 AG58 datasheet)
        rate_random_walk=0.0,
        scale_factor_std=0.0001,
        misalignment_std=0.0001,
        resolution=1000 * DEG2RAD / 2 ** 20,
        range_max=1000 * DEG2RAD,
    )
    return ImuGradeConfig(
        name="tactical", rate_hz=100.0, accel=accel, gyro=gyro,
        sources={
            "gyro_bias_instability": "Honeywell HG1700 datasheet M61-0115-000-003 (AG58 variant): Gyro Bias In-Run Stability = 1 deg/hr",
            "gyro_random_walk": "Honeywell HG1700 datasheet M61-0115-000-003 (AG58 variant): Gyro Angular Random Walk = 0.125 deg/sqrt(hr)",
            "accel_all": "ASSUMPTION: HG1700 accelerometer (quartz RBA) figures not located in accessible excerpts; representative tactical-grade quartz-accelerometer range used, see SENSOR_NOTES.md",
        },
    )


GRADES: dict[str, Any] = {
    "consumer_mems": _consumer_mems,
    "industrial_mems": _industrial_mems,
    "tactical": _tactical,
}


class _AxisChannel:
    """Stateful per-run error generator for one 3-axis channel (accel or gyro)."""

    def __init__(self, params: AxisErrorParams, dt: float, rng: np.random.Generator,
                 replay_source: Any | None = None):
        self.p = params
        self.dt = dt
        # Optional real-noise replay (Master D-014, item 3): when set,
        # REPLACES the white random_walk draw below with a block-bootstrap
        # replay of real residuals (e.g. Thales MICAL classical-accelerometer
        # data from Jarlaud et al. 2024) instead of the white-noise model.
        # Never used for the quantum sensor (that noise is classical-only,
        # per Master D-014).
        self.replay_source = replay_source
        self.theta = _gm1_theta(dt, params.bias_instability_tau_c)
        sigma_gm = params.bias_instability / 0.664 if params.bias_instability > 0 else 0.0
        self.sigma_gm = sigma_gm
        self.driving_std = sigma_gm * np.sqrt(max(0.0, 1.0 - self.theta ** 2))

        # per-run constants
        self.turn_on_bias = rng.normal(0.0, params.turn_on_bias_std, size=3)
        self.scale_factor = 1.0 + rng.normal(0.0, params.scale_factor_std, size=3)
        misalign = rng.normal(0.0, params.misalignment_std, size=(3, 3))
        np.fill_diagonal(misalign, 0.0)
        self.misalignment = np.eye(3) + misalign

        # process states
        self.bias_gm = rng.normal(0.0, sigma_gm, size=3) if sigma_gm > 0 else np.zeros(3)
        self.bias_rrw = np.zeros(3)

    def step(self, true_value: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        p = self.p
        # bias instability (GM1)
        self.bias_gm = self.theta * self.bias_gm + self.driving_std * rng.normal(size=3)
        # rate random walk (integrated white noise)
        if p.rate_random_walk > 0:
            self.bias_rrw = self.bias_rrw + p.rate_random_walk * np.sqrt(self.dt) * rng.normal(size=3)

        meas = self.misalignment @ (true_value * self.scale_factor)
        meas = meas + self.turn_on_bias + self.bias_gm + self.bias_rrw
        if self.replay_source is not None:
            meas = meas + self.replay_source.draw(rng, 3)
        elif p.random_walk > 0:
            meas = meas + (p.random_walk / np.sqrt(self.dt)) * rng.normal(size=3)

        if p.resolution > 0:
            meas = np.round(meas / p.resolution) * p.resolution
        meas = np.clip(meas, -p.range_max, p.range_max)
        return meas


class ClassicalImu:
    """Classical strapdown IMU model implementing ``ImuModel`` (contract v0.1)."""

    def __init__(
        self,
        grade: str = "industrial_mems",
        rng: np.random.Generator | None = None,
        rate_hz: float | None = None,
        sensor_id: str = "imu",
        world: str = "flat",
        accel_noise_source: Literal["model", "replay"] = "model",
        accel_replay_residuals: np.ndarray | None = None,
        accel_replay_sample_rate_hz: float | None = None,
        accel_replay_block_length: int = 20,
    ):
        if grade not in GRADES:
            raise ValueError(f"unknown IMU grade '{grade}', choose from {list(GRADES)}")
        self._grade_name = grade
        self._cfg = GRADES[grade]()
        self.rate_hz = float(rate_hz) if rate_hz is not None else self._cfg.rate_hz
        self._dt = 1.0 / self.rate_hz
        self.sensor_id = sensor_id
        # ``world`` (contract v0.2, C-5: fedqpnt.core.world) is accepted for
        # interface consistency / provenance logging only: gravity already
        # enters ``truth.f_b`` upstream (f_b = C_nb^T (a_n - g_n(p)),
        # computed by the trajectory generator via world.gravity_n), so the
        # IMU model itself is world-agnostic -- it never recomputes gravity.
        self.world = world
        self._rng_init = rng if rng is not None else np.random.default_rng()
        self.accel_noise_source = accel_noise_source
        accel_replay = None
        if accel_noise_source == "replay":
            if accel_replay_residuals is None or accel_replay_sample_rate_hz is None:
                raise ValueError("accel_noise_source='replay' requires accel_replay_residuals and accel_replay_sample_rate_hz")
            from fedqpnt.sensors.quantum import _ReplayNoiseSource  # real-noise block bootstrap, shared with the quantum sensor's replay mode
            accel_replay = _ReplayNoiseSource(
                accel_replay_residuals, accel_replay_sample_rate_hz, self.rate_hz,
                block_length=accel_replay_block_length, n_axes=3,
            )
        elif accel_noise_source != "model":
            raise ValueError(f"unknown accel_noise_source '{accel_noise_source}'")
        self._accel_ch = _AxisChannel(self._cfg.accel, self._dt, self._rng_init, replay_source=accel_replay)
        self._gyro_ch = _AxisChannel(self._cfg.gyro, self._dt, self._rng_init)
        # Tick-counter-based output gating (not float-time accumulation,
        # which drifts over long runs since dt=1/rate_hz is not exactly
        # representable in binary floating point). ``stride`` is inferred
        # from the first observed global tick interval; falls back to
        # "always output" if the global dt cannot be inferred yet or the
        # configured rate_hz exceeds the tick rate.
        self._tick_idx: int = -1
        self._prev_t: float | None = None
        self._global_dt: float | None = None
        self._stride: int = 1

    def _ekf_noise_block(self, p: AxisErrorParams) -> dict[str, float]:
        """EKF-ready noise parameters in SI units (Master contract v0.2,
        item 4): random walk (VRW for accel / ARW for gyro), bias-instability
        as a GM1 (sigma, correlation time) pair -- not just the datasheet
        ADEV-floor figure -- and rate random walk."""
        sigma_gm = p.bias_instability / 0.664 if p.bias_instability > 0 else 0.0
        return {
            "random_walk_per_sqrt_s": p.random_walk,       # ADEV(tau) = random_walk/sqrt(tau); SI: (m/s^2 or rad/s) * sqrt(s)
            "bias_instability_adev_floor": p.bias_instability,  # SI: m/s^2 or rad/s (datasheet-style figure)
            "bias_instability_gm1_sigma": sigma_gm,         # SI: m/s^2 or rad/s (GM1 process stationary std)
            "bias_instability_gm1_tau_c_s": p.bias_instability_tau_c,
            "rate_random_walk_per_sqrt_s": p.rate_random_walk,  # SI: (m/s^2 or rad/s) / sqrt(s)
            "turn_on_bias_std": p.turn_on_bias_std,
            "scale_factor_std": p.scale_factor_std,
            "misalignment_std_rad": p.misalignment_std,
            "resolution": p.resolution,
            "range_max": p.range_max,
        }

    def config(self) -> dict[str, Any]:
        return {
            "type": "ClassicalImu",
            "grade": self._grade_name,
            "rate_hz": self.rate_hz,
            "world": self.world,
            "accel_noise_source": self.accel_noise_source,
            "sources": self._cfg.sources,
            "accel": vars(self._cfg.accel),
            "gyro": vars(self._cfg.gyro),
            # EKF-facing summary, explicit SI units (Master contract v0.2 item 4)
            "accel_noise_SI": self._ekf_noise_block(self._cfg.accel),  # VRW etc, units m/s^2
            "gyro_noise_SI": self._ekf_noise_block(self._cfg.gyro),    # ARW etc, units rad/s
        }

    def step(self, truth: TruthState, rng: np.random.Generator) -> ImuSample | None:
        self._tick_idx += 1
        if self._prev_t is not None and self._global_dt is None:
            observed = truth.t - self._prev_t
            if observed > 1e-12:
                self._global_dt = observed
                self._stride = max(1, int(round(self._dt / self._global_dt)))
        self._prev_t = truth.t

        if self._tick_idx % self._stride != 0:
            return None

        f_b = self._accel_ch.step(truth.f_b, rng)
        omega_b = self._gyro_ch.step(truth.omega_b, rng)
        return ImuSample(t=truth.t, f_b=f_b, omega_b=omega_b, sensor_id=self.sensor_id)
