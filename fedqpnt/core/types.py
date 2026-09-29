"""FedQPNT shared data contracts (Master-owned, v0.3 — see DECISION_LOG D-009, D-022).

Every module exchanges data ONLY through the types defined here. Changing a
field requires a DECISION_LOG entry and a contract version bump.

Conventions (see DECISION_LOG D-003, D-009; ARCHITECTURE.md §0):
  * Navigation frame: local-level ENU (East, North, Up), metres, origin at
    ``ORIGIN_LLH``. Satellite geometry is computed in ECEF and projected to ENU.
  * Body frame: FLU (x forward, y left, z up).
  * Attitude: (roll φ, pitch θ, yaw ψ) in radians, strict ZYX composition
    C_nb = Rz(ψ)·Ry(θ)·Rx(φ), right-handed elementary rotations (ROS REP-103).
    Consequences — read carefully:
      ψ = 0  ⇒ nose points EAST;  ψ increases COUNTER-CLOCKWISE (towards North).
      θ > 0  ⇒ nose DOWN   (body x in ENU = [cψcθ, sψcθ, −sθ]).
      φ > 0  ⇒ left wing up.
  * Time: seconds since mission start, float64. Single global sim clock.
  * Specific force f_b = C_nbᵀ (a_n − g_n(p)); g_n from ``fedqpnt.core.world``
    (``"flat"``: (0,0,−G0); ``"schuler_tangent"``: see world.py).
  * IMU samples are POINT samples of f_b(t_k), ω_b(t_k) at tick time
    (not Δv/Δθ increments).
  * All arrays are float64 numpy arrays.
  * Node boundary: Environment half (truth, sensor models, GNSS signal, attacks)
    vs Agent half (receiver, fusion, trust, detector, FL client). Only sensor
    outputs cross. TruthState, AttackLabel and GnssEpoch.meta NEVER reach the Agent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

CONTRACT_VERSION = "0.3.0"

# Reference origin (lat_deg, lon_deg, height_m). Arbitrary mid-latitude site.
ORIGIN_LLH = (12.9716, 79.1588, 220.0)
G0 = 9.80665  # m/s^2, standard gravity (local gravity models may refine this)
C_LIGHT = 299_792_458.0  # m/s


# --------------------------------------------------------------------------
# Ground truth
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class TruthState:
    """True kinematic state of one node at time t (never leaves the simulator)."""

    t: float
    pos: np.ndarray        # (3,) ENU position [m]
    vel: np.ndarray        # (3,) ENU velocity [m/s]
    acc: np.ndarray        # (3,) ENU kinematic acceleration [m/s^2]
    att: np.ndarray        # (3,) roll, pitch, yaw [rad]
    omega_b: np.ndarray    # (3,) body angular rate [rad/s]
    f_b: np.ndarray        # (3,) body specific force [m/s^2]


@dataclass
class TruthTrajectory:
    """Vectorised truth for a whole mission (N samples at a fixed dt)."""

    t: np.ndarray          # (N,)
    pos: np.ndarray        # (N,3)
    vel: np.ndarray        # (N,3)
    acc: np.ndarray        # (N,3)
    att: np.ndarray        # (N,3)
    omega_b: np.ndarray    # (N,3)
    f_b: np.ndarray        # (N,3)
    meta: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return int(self.t.shape[0])

    def state(self, k: int) -> TruthState:
        return TruthState(
            t=float(self.t[k]), pos=self.pos[k], vel=self.vel[k], acc=self.acc[k],
            att=self.att[k], omega_b=self.omega_b[k], f_b=self.f_b[k],
        )


# --------------------------------------------------------------------------
# Inertial sensor samples
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ImuSample:
    """Classical (MEMS / tactical) IMU output."""

    t: float
    f_b: np.ndarray        # (3,) measured specific force [m/s^2]
    omega_b: np.ndarray    # (3,) measured angular rate [rad/s]
    sensor_id: str = "imu"


@dataclass(frozen=True)
class QuantumSample:
    """Cold-atom interferometric accelerometer output (one interferometer cycle).

    A sample integrates over the interrogation window [t - cycle_time, t].
    ``valid`` is False when the atom interferometer loses fringe contrast
    (e.g. excessive rotation / dynamics) or during dead time.
    """

    t: float
    f_b: np.ndarray        # (3,) measured specific force [m/s^2] (NaN on axes not sensed)
    variance: np.ndarray   # (3,) 1-sigma^2 measurement variance reported by the sensor model
    valid: bool
    cycle_time: float      # [s] total cycle duration (interrogation + dead time)
    contrast: float = 1.0  # fringe contrast in [0,1]; diagnostic
    sensor_id: str = "quantum"
    # v0.2 (C-2): true interrogation window. The CAI response to acceleration is
    # triangular over [t - 2T, t]; cycle_time additionally includes dead time.
    t_interrogation: float = float("nan")  # T [s]
    response: str = "triangular"           # "triangular" | "boxcar"


# --------------------------------------------------------------------------
# GNSS raw observables, receiver output
# --------------------------------------------------------------------------
@dataclass
class SatObs:
    prn: int
    pseudorange: float     # [m], includes receiver clock bias * c
    pseudorange_rate: float  # [m/s] (Doppler * -wavelength), includes clock drift * c
    cn0_dbhz: float        # carrier-to-noise density [dB-Hz]
    sat_pos: np.ndarray    # (3,) satellite position in ENU [m]
    sat_vel: np.ndarray    # (3,) satellite velocity in ENU [m/s]
    elevation: float       # [rad]
    azimuth: float         # [rad]
    tracked: bool = True   # False when the tracking loop has lost lock


@dataclass
class GnssEpoch:
    """Raw GNSS measurements at one receiver epoch (pre-PVT). Attacks act here.

    v0.2 (C-4): ``meta`` is ENVIRONMENT-PRIVATE (may hold true clock bias etc.).
    The environment must hand the receiver a copy with ``meta={}``; use
    ``GnssEpoch.for_agent()``. (Rename to ``sim_meta`` deferred to v0.3.)
    """

    t: float
    obs: list[SatObs]
    agc_db: float = 0.0    # automatic-gain-control level relative to nominal [dB]
    noise_floor_db: float = 0.0  # in-band noise power rise relative to thermal [dB]
    meta: dict[str, Any] = field(default_factory=dict)

    def for_agent(self) -> "GnssEpoch":
        """Copy safe to cross the Environment→Agent boundary (meta stripped)."""
        return GnssEpoch(t=self.t, obs=list(self.obs), agc_db=self.agc_db,
                         noise_floor_db=self.noise_floor_db, meta={})


@dataclass
class GnssFix:
    """Receiver PVT solution (what a fusion filter consumes)."""

    t: float
    pos: np.ndarray        # (3,) ENU [m]
    vel: np.ndarray        # (3,) ENU [m/s]
    clk_bias: float        # [m]
    clk_drift: float       # [m/s]
    cov_pos: np.ndarray    # (3,3) [m^2]
    cov_vel: np.ndarray    # (3,3) [(m/s)^2]
    residual_rms: float    # post-fit pseudorange residual RMS [m]
    num_sats: int
    mean_cn0: float        # [dB-Hz] over tracked sats
    std_cn0: float         # [dB-Hz]
    agc_db: float
    valid: bool
    raim_stat: float = 0.0  # chi-square test statistic (sum of squared normalised residuals)
    pdop: float = float("nan")  # v0.2 (C-7)
    # v0.3 (D-022): per-tracked-satellite C/N0 [dB-Hz] and elevation [rad],
    # keyed by PRN. Agent-side legitimate (a real receiver reports these); enables the
    # cross-satellite C/N0 correlation / elevation-slope spoofing features (D-018).
    cn0_per_sat: dict[int, float] = field(default_factory=dict)
    elev_per_sat: dict[int, float] = field(default_factory=dict)


# --------------------------------------------------------------------------
# Attacks (ground truth labels for evaluation only; never visible to nodes)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class AttackLabel:
    t: float
    spoofing: bool
    jamming: bool
    kind: str = "none"     # e.g. "none", "drift_spoof", "meaconing", "replay", "jam_cw", "jam_wideband"
    severity: float = 0.0  # attack-specific scalar in [0, 1]


# --------------------------------------------------------------------------
# Trust + fusion
# --------------------------------------------------------------------------
SENSORS = ("gnss", "imu", "quantum")


@dataclass(frozen=True)
class Innovation:
    """v0.2 (C-1): one measurement innovation computed by the fusion filter
    BEFORE correction, so the trust engine can use it without a circular call."""

    t: float
    sensor: str            # e.g. "gnss_pos", "gnss_vel", "quantum"
    nu: np.ndarray         # (m,) innovation z - h(x̂)
    S: np.ndarray          # (m,m) innovation covariance
    nis: float             # nuᵀ S⁻¹ nu
    dof: int               # m
    accepted: bool         # passed the NIS gate


@dataclass(frozen=True)
class TrustState:
    """Per-node trust weights at time t, each in [0, 1]."""

    t: float
    weights: dict[str, float]          # keys from SENSORS
    anomaly_scores: dict[str, float]   # raw detector outputs feeding the trust update
    attack_detected: bool
    # D-066 shadow probe: True while the GNSS trust law is in PROBE. The filter must then compute the
    # GNSS innovation/NIS but apply NO GNSS update (no state or covariance change).
    probe_shadow: bool = False


@dataclass(frozen=True)
class NavSolution:
    """Fused PNT output of one node."""

    t: float
    pos: np.ndarray        # (3,) ENU [m]
    vel: np.ndarray        # (3,) ENU [m/s]
    att: np.ndarray        # (3,) [rad]
    clk_bias: float        # [m]
    cov_pos: np.ndarray    # (3,3)
    trust: TrustState
    # v0.2 (C-3)
    cov_vel: np.ndarray = field(default_factory=lambda: np.full((3, 3), np.nan))
    acc_bias: np.ndarray = field(default_factory=lambda: np.zeros(3))
    gyro_bias: np.ndarray = field(default_factory=lambda: np.zeros(3))


# --------------------------------------------------------------------------
# Federated exchange (the ONLY thing that crosses the node boundary)
# --------------------------------------------------------------------------
@dataclass
class ModelUpdate:
    node_id: str
    round_idx: int
    params: dict[str, np.ndarray]   # model parameters or deltas; NO trajectories / raw data
    n_samples: int
    metrics: dict[str, float] = field(default_factory=dict)  # scalar local summaries only
    kind: str = "delta"             # "delta" | "full"


@dataclass
class GlobalModel:
    round_idx: int
    params: dict[str, np.ndarray]
    meta: dict[str, Any] = field(default_factory=dict)
