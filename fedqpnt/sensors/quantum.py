"""Cold-atom (light-pulse Raman) interferometric accelerometer model (WP-2.1).

Physics
-------
A Mach-Zehnder-type light-pulse atom interferometer accumulates a phase

    phi = k_eff * a * T^2

between the two interferometer arms, where ``a`` is the mean specific force
along the sensitive axis over the interrogation time ``T`` and ``k_eff`` is
the effective two-photon Raman wavevector (k_eff = 2*k_L for a counter-
propagating Raman pair; k_L = 2*pi/lambda). We use the Rb-87 D2 line,
lambda = 780.24 nm -> k_eff ~= 1.610e7 rad/m (standard atomic physics,
common to all cited references; not separately re-derived per source).

Fringe detection only recovers phi modulo 2*pi (equivalently, acceleration
modulo a "fringe period" a_fringe = 2*pi / (k_eff*T^2)): this is the
"fringe ambiguity" that a stand-alone cold-atom accelerometer suffers under
dynamics. Hybridization with a classical (mechanical/MEMS) accelerometer
resolves the correct fringe order and fills the dead time between cycles
(Lautier et al. 2014, Appl. Phys. Lett. 105:144102, DOI:10.1063/1.4897358;
Cheiney et al. 2018, Phys. Rev. Applied 10:034030, DOI:10.1103/
PhysRevApplied.10.034030; Templier et al. 2022, Sci. Adv. 8:eadd3854,
DOI:10.1126/sciadv.add3854).

Noise model
-----------
The white (shot-noise-limited) part of the measurement is driven directly by
a cited short-term sensitivity figure ``sensitivity_m_s2_per_sqrt_hz``
(rather than an unverified assumed atom number / contrast pair): the
per-cycle standard deviation is ``sensitivity * sqrt(rate_hz)``. A slow
correlated bias residual (after hybridization removes the classical
accelerometer's own drift) is modelled as a first-order Gauss-Markov (GM1)
process tuned, as in ``fedqpnt.sensors.imu``, so its Allan-deviation minimum
matches the cited bias-instability figure (El-Sheimy, Hou & Niu 2008).

Contrast loss
-------------
Rotation of the interferometer during T displaces the atoms relative to the
laser wavefronts (Coriolis effect), washing out fringe contrast; this is the
dominant, well-documented dynamic-range limiter for single cold-atom
accelerometers used on moving platforms (Cheiney et al. 2018; Templier et
al. 2022; Geiger et al. 2020, AVS Quantum Sci. 2:024702, DOI:10.1116/
5.0009093, review sec. on rotation sensitivity). We model
``contrast = C0 * exp(-(omega_perp_rms/omega_c)^2)`` where omega_perp is the
angular rate component orthogonal to the sensitive axis, averaged over the
interrogation window. The scale ``omega_c`` is NOT found with a citable
number in the accessible literature excerpts for this task and is marked
ASSUMPTION (plausible range 1-10 mrad/s for cm-scale clouds and T ~ 10-100
ms); see docs/specs/raw/SENSOR_NOTES.md. ``valid=False`` when contrast drops
below ``contrast_threshold`` or when |a| exceeds the sensor's specified
dynamic range.

Grades
------
  * "lab"         : best published single-axis / hybrid-triad figures
                     (Wright et al. 2022, Frontiers Phys. 10:994459,
                     DOI:10.3389/fphy.2022.994459; Templier et al. 2022).
  * "field"        : real airborne/marine deployment figures, degraded vs
                     lab (Bidel et al. 2018, J. Geodesy, DOI:10.1007/
                     s00190-020-01350-2, "Absolute airborne gravimetry with a
                     cold atom sensor").
  * "near_future"  : roadmap/compact high-data-rate systems (e.g. Wu et al.,
                     Nat. Commun. 13:1442 (2022), DOI:10.1038/s41467-022-
                     31410-4, 10 Hz compact interferometer); labelled as
                     lower-TRL and explicitly not a field-validated figure.

Pluggable stochastic core
--------------------------
``noise_source="model"`` (default) draws shot noise from the cited
sensitivity figure as above. ``noise_source="replay"`` instead replays a
supplied array of real, detrended acceleration residuals via block
bootstrap (resampled/decimated to the sensor's cycle rate), so the model can
later be calibrated against real measured cold-atom data without changing
the rest of the pipeline. Use ``fit_params_from_adev`` to derive
``sensitivity_m_s2_per_sqrt_hz`` / bias-instability parameters from a
measured Allan-deviation curve.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from fedqpnt.core.types import QuantumSample, TruthState
from fedqpnt.sensors.allan import fit_white_and_bias_instability

RB87_D2_LAMBDA_M = 780.241e-9
K_EFF_RB87 = 2.0 * (2.0 * np.pi / RB87_D2_LAMBDA_M)  # ~1.6098e7 rad/m, two-photon Raman

# ---------------------------------------------------------------------------
# Real measured data: Jarlaud/d'Armagnac de Castanet et al. 2024, Nat. Commun.
# 15:6406, DOI:10.1038/s41467-024-50804-0 (arXiv:2402.18988), Zenodo
# 10.5281/zenodo.11543715. Rigid-mode (mirror fixed to device) contrast vs
# rotation, C(Omega) = C0*exp(-(Omega/Omega_c)^2), fit to 2000 shots at
# 2T=12ms (Figure 2 runs); see data/processed/jarlaud2024/calibration.json
# and docs/specs/raw/DATA_JARLAUD_NOTES.md (owned by DATA-INGEST).
# ---------------------------------------------------------------------------
JARLAUD_C0 = 0.39409541100156253                 # measured, +-0.0175 (1-sigma)
JARLAUD_OMEGA_C_RAD_S = 0.04817828306192081      # measured, +-0.0025 rad/s (48.2 mrad/s), at T_REF
JARLAUD_T_REF_S = 0.006                          # 2T=12 ms -> T=6ms, the rigid-mode calibration condition
JARLAUD_CYCLE_TIME_S = 1.5480000000000018        # measured interferometer cycle period
JARLAUD_INERTIAL_POINTING_OMEGA_LIMIT_RAD_S = 0.25  # paper: inertial-pointing mode operates up to 250 mrad/s

# Master D-019 (final): measured robust per-shot shot-noise sigma [ug] by 2T,
# from data/processed/jarlaud2024/calibration.json ("atom_interferometer.
# per_two_T"), and per-2T outlier statistics from atom_outliers.json.
# Interpolated LINEARLY in 2T (D-019: "do NOT assume 1/T^2" -- measured
# 10ms->20ms is only ~1.9x, a vibration-limited regime, not a shot-noise-
# limited 1/T^2 law). The pooled/pre-D-019 sigma is explicitly NOT reused
# (calibration.json flags it "_DO_NOT_USE").
JARLAUD_SIGMA_SHOT_UG_BY_TWO_T = {
    0.010: 10.70417467292015,   # n=720
    0.012: 12.46910044092385,   # n=24, LOW CONFIDENCE (wide 95% CI)
    0.014: 6.830194488260799,   # n=480
    0.020: 5.603278733296871,   # n=491; FIELD grade condition; 95% CI [5.04, 6.40] ug, paper-implied 5.06 ug (ratio 1.11)
}
# Field-grade (2T=20ms) real outlier/fringe-jump statistics (Master D-019 item 2):
JARLAUD_OUTLIER_STATIONARY_RATE = 0.08961303462321792   # 9.0% (95% CI [6.7, 11.8]%)
JARLAUD_OUTLIER_PERSISTENCE = 0.6590909090909091        # P(bad|prev bad) ~= 66%


def _sigma_shot_ug_interp(T: float) -> float:
    """Linear interpolation (NOT 1/T^2, per D-019) of the measured robust
    per-shot sigma [ug] table over 2T; clamps to the table's endpoints
    outside the measured 2T in [10,20] ms range."""
    two_t_ms = np.array(sorted(JARLAUD_SIGMA_SHOT_UG_BY_TWO_T)) * 1000.0
    sig_ug = np.array([JARLAUD_SIGMA_SHOT_UG_BY_TWO_T[t / 1000.0] for t in two_t_ms])
    return float(np.interp(2.0 * T * 1000.0, two_t_ms, sig_ug))


def _load_outlier_magnitudes_ug(two_T_key: str = "20ms") -> np.ndarray:
    """Real empirical outlier magnitudes [ug] from atom_outliers.json
    (Master D-019 item 2). Falls back to a small synthetic log-normal-like
    placeholder (documented ASSUMPTION) if the data file is unavailable,
    e.g. in an environment without the data/ directory checked out."""
    import json
    path = (_this_dir().parent.parent / "data" / "processed" / "jarlaud2024" / "atom_outliers.json")
    try:
        with open(path) as f:
            d = json.load(f)
        return np.array(d[two_T_key]["outlier_magnitudes_ug"], dtype=np.float64)
    except Exception:
        # ASSUMPTION fallback only: order-of-magnitude match to the real
        # 20ms distribution (median ~100 ug, range ~30-270 ug), used only
        # if data/processed/jarlaud2024/atom_outliers.json is not present.
        rng = np.random.default_rng(20190)
        return np.exp(rng.normal(np.log(100.0), 0.5, size=44))


def _this_dir():
    import pathlib
    return pathlib.Path(__file__).resolve().parent


def _ge_transition_probs(stationary_bad_rate: float, persistence: float) -> tuple[float, float]:
    """Gilbert-Elliott two-state Markov chain transition probabilities
    (Master D-019 item 2) solved from the target stationary bad-state
    probability and bad-state persistence P(bad|prev bad):
        p_bad_bad = persistence
        p_good_bad = stationary_bad_rate*(1-persistence) / (1-stationary_bad_rate)
    (stationary distribution of a 2-state Markov chain: pi_bad =
    p_good_bad / (p_good_bad + p_bad_good), p_bad_good = 1-persistence).
    Returns (p_good_to_bad, p_bad_to_bad).
    """
    p_bad_good = 1.0 - persistence
    p_good_bad = stationary_bad_rate * p_bad_good / (1.0 - stationary_bad_rate)
    return p_good_bad, persistence


def _scale_omega_c(T: float, T_ref: float = JARLAUD_T_REF_S, omega_c_ref: float = JARLAUD_OMEGA_C_RAD_S) -> float:
    """Scale the measured rigid-mode Omega_c from its T_ref=6ms calibration
    condition to a different interrogation time T.

    Physics-derived 1/T^2 scaling from one measured point (Master D-020,
    correcting D-014): the rotation-induced Coriolis phase is
    2*k_eff*(Omega x v)*T^2, so contrast loss vs a velocity spread sigma_v
    gives C=C0*exp(-(Omega/Omega_c)^2) with
    Omega_c ∝ 1/(k_eff*sigma_v*T^2) at fixed k_eff and cloud temperature,
    i.e. ``omega_c(T) = omega_c_ref * (T_ref/T)^2``. (D-014's original 1/T
    law was a Master error -- self-contradictory with its own stated
    Omega*T^2 argument -- superseded here.) Only ONE measured (T, Omega_c)
    pair exists, so this scaling is unverified outside T~6ms.
    """
    return omega_c_ref * (T_ref / T) ** 2


def _inertial_pointing_omega_c(contrast0: float, contrast_threshold: float,
                                omega_limit: float = JARLAUD_INERTIAL_POINTING_OMEGA_LIMIT_RAD_S) -> float:
    """ASSUMPTION (Master D-014): the paper's inertial-pointing mode (active
    tip-tilt compensation nulls the Coriolis-induced wavefront/trajectory
    separation) is reported to operate up to Omega=250 mrad/s, but no
    Omega_c fit for this mode exists yet in the processed dataset (flagged
    as a follow-up in DATA_JARLAUD_NOTES.md sec.7). We back out an EFFECTIVE
    Omega_c for the same C0*exp(-(Omega/Omega_c)^2) functional form such
    that contrast crosses ``contrast_threshold`` exactly at ``omega_limit``:
    Omega_c = omega_limit / sqrt(ln(C0/contrast_threshold)). This is a
    placeholder consistent with the paper's stated operating envelope, NOT
    an independently fit contrast law -- NEAR_FUTURE-grade only.
    """
    ratio = contrast0 / contrast_threshold
    if ratio <= 1.0:
        return omega_limit
    return omega_limit / np.sqrt(np.log(ratio))


def _gm1_theta(dt: float, tau_c: float) -> float:
    return float(np.exp(-dt / tau_c))


@dataclass
class QuantumAxisParams:
    T_interrogation_s: float
    cycle_time_s: float
    sensitivity_m_s2_per_sqrt_hz: float
    bias_instability_m_s2: float
    bias_tau_c_s: float                 # ASSUMPTION unless cited
    scale_factor_std: float
    contrast0: float
    omega_c_rad_s: float                # rotation contrast-loss scale (rigid pointing)
    contrast_threshold: float
    dynamic_range_m_s2: float
    coarse_accel_noise_std_m_s2: float  # classical hybridization sensor noise (ASSUMPTION unless cited)
    coarse_accel_bias_std_m_s2: float
    omega_c_inertial_rad_s: float = float("nan")  # optional: inertial-pointing mode Omega_c (ASSUMPTION, see _inertial_pointing_omega_c)
    outlier_stationary_rate: float = 0.0          # Gilbert-Elliott bad-state stationary probability (Master D-019)
    outlier_persistence: float = 0.0              # P(bad | previous shot was bad)
    outlier_magnitudes_ug: tuple[float, ...] = ()  # empirical |outlier| magnitudes to sample from, random sign applied


@dataclass
class QuantumGradeConfig:
    name: str
    axis: QuantumAxisParams
    sources: dict[str, str] = field(default_factory=dict)


def _lab() -> QuantumGradeConfig:
    axis = QuantumAxisParams(
        T_interrogation_s=0.002,             # Lautier et al. 2014: sensitivity figure below is quoted at 2T=4ms -> T=2ms (kept consistent with the cited sensitivity so k_eff*T^2 and the shot-noise figure describe the same operating point)
        cycle_time_s=1.0,                    # Wright et al. 2022 (Frontiers Phys. 10:994459): lab cycle rate "0.5 Hz to a few Hz" -> cycle_time ~1 s representative
        sensitivity_m_s2_per_sqrt_hz=2e-3,   # Lautier et al. 2014 (arXiv:1410.0050 / APL 105:144102): sensitivity 2e-3 m/s^2/sqrt(Hz) at 2T=4ms (short-T operating point used for dynamic hybrid operation)
        bias_instability_m_s2=7e-7,          # Wright et al. 2022: cited lab bias stability 7e-7 m/s^2
        bias_tau_c_s=300.0,                  # ASSUMPTION
        scale_factor_std=1e-6,               # ASSUMPTION: AI scale factor set by laser frequency/wavevector, ppm-level (Geiger et al. 2020 review, qualitative claim of high scale-factor stability; exact number not cited)
        contrast0=JARLAUD_C0,                # measured (Jarlaud et al. 2024, D-014), reused across grades pending a lab-specific contrast measurement
        omega_c_rad_s=_scale_omega_c(0.002), # Jarlaud et al. 2024 rigid-mode Omega_c=48.2 mrad/s @ T_ref=6ms, scaled to T=2ms via physics-derived 1/T^2 law (D-020, see _scale_omega_c) -- ~434 mrad/s
        contrast_threshold=0.08,             # ASSUMPTION
        dynamic_range_m_s2=2.0 * 9.80665,    # ASSUMPTION: hybridized accel must comfortably track 1g standing gravity; ~2g headroom before hybrid fringe-tracking fails
        coarse_accel_noise_std_m_s2=1e-6,    # ASSUMPTION, per Lautier 2014 use of a low-noise seismometer-class classical accelerometer (exact model/number not confirmed -> ASSUMPTION)
        coarse_accel_bias_std_m_s2=1e-4,     # ASSUMPTION: classical sensor turn-on bias before AI-assisted correction
    )
    return QuantumGradeConfig(
        name="lab", axis=axis,
        sources={
            "bias_instability": "Wright et al. 2022, Frontiers in Physics 10:994459, DOI:10.3389/fphy.2022.994459 (cited lab bias stability 7e-7 m/s^2; long-integration accuracy approaching 1e-8 m/s^2)",
            "cycle_rate": "Wright et al. 2022: lab measurement frequency '0.5 Hz to a few Hz', duty cycle 0.3-0.5",
            "sensitivity": "Lautier et al. 2014, Appl. Phys. Lett. 105:144102 (arXiv:1410.0050): 2e-3 m/s^2/sqrt(Hz) sensitivity at total interrogation 2T=4ms",
            "hybridization": "Lautier et al. 2014; Cheiney et al. 2018, Phys. Rev. Applied 10:034030, DOI:10.1103/PhysRevApplied.10.034030 (EKF-based hybrid classical/quantum accelerometer)",
            "contrast_and_bias_improvement": "Templier et al. 2022, Science Advances 8:eadd3854, DOI:10.1126/sciadv.add3854 (hybrid triad, 1 kHz output, <10 ug absolute accuracy, 6e-8 g / 50x stability improvement over classical)",
            "contrast_and_omega_c": "Jarlaud/d'Armagnac de Castanet et al. 2024, Nat. Commun. 15:6406, DOI:10.1038/s41467-024-50804-0 (D-014): measured rigid-mode C0=0.394, Omega_c=48.2 mrad/s @ 2T=12ms; Omega_c scaled to this grade's T via physics-derived 1/T^2 law (D-020) -- ~434 mrad/s",
            "ASSUMPTIONS": "T_interrogation_s, bias_tau_c_s, scale_factor_std, contrast_threshold, dynamic_range_m_s2, coarse_accel_noise/bias_std -- see module docstring and SENSOR_NOTES.md",
        },
    )


def _field() -> QuantumGradeConfig:
    # Master D-019 (final, supersedes D-014/D-015 pooled numbers): FIELD
    # grade uses the paper's own 2T=20ms condition (the best-matched,
    # highest-n measured point), robust sigma_shot=5.60 ug. cycle_time is
    # the PER-SHOT combined interval (D-020, correcting D-014/D-019: 2.955s
    # was the per-k-direction interval; the instrument interlaces kD/kU
    # shots and each shot is itself an acceleration measurement -- Run 21
    # has 3.09s per k-direction and 1.548s combined per shot; our model
    # does not simulate k-dependent systematics, so the per-shot rate is
    # the correct one to use here) = JARLAUD_CYCLE_TIME_S.
    T = 0.010
    cycle_time = JARLAUD_CYCLE_TIME_S
    sigma_mps2 = JARLAUD_SIGMA_SHOT_UG_BY_TWO_T[0.020] * 1e-6 * 9.80665
    sensitivity = sigma_mps2 * np.sqrt(cycle_time)  # ADEV(tau)=N/sqrt(tau) convention
    axis = QuantumAxisParams(
        T_interrogation_s=T,
        cycle_time_s=cycle_time,
        sensitivity_m_s2_per_sqrt_hz=sensitivity,
        bias_instability_m_s2=3e-6,          # ASSUMPTION: no atom-only (vs. classical-MICAL) bias floor is resolvable from this shot count (calibration.json's classical_accel_mical ADEV floor is the CLASSICAL channel, not atom, per Master D-014 "MICAL residuals are classical-only"); placed between lab (7e-7) and previously-estimated field-degradation range
        bias_tau_c_s=300.0,                  # ASSUMPTION
        scale_factor_std=1e-5,               # ASSUMPTION, relaxed vs lab
        contrast0=JARLAUD_C0,                # measured (Jarlaud et al. 2024, D-014), rigid mode
        omega_c_rad_s=_scale_omega_c(T),     # Jarlaud et al. 2024 rigid-mode Omega_c=48.2 mrad/s @ T_ref=6ms, scaled to T=10ms via physics-derived 1/T^2 law (D-020) -- ~17.35 mrad/s
        contrast_threshold=0.08,             # ASSUMPTION
        dynamic_range_m_s2=2.0 * 9.80665,    # ASSUMPTION: must track 1g standing gravity; field platform dynamics headroom
        coarse_accel_noise_std_m_s2=1e-5,    # ASSUMPTION, field-grade classical accelerometer noisier than lab seismometer
        coarse_accel_bias_std_m_s2=5e-4,     # ASSUMPTION
        omega_c_inertial_rad_s=_inertial_pointing_omega_c(JARLAUD_C0, 0.08),  # ASSUMPTION, see helper docstring
        outlier_stationary_rate=JARLAUD_OUTLIER_STATIONARY_RATE,   # measured, 2T=20ms (Master D-019 item 2)
        outlier_persistence=JARLAUD_OUTLIER_PERSISTENCE,           # measured, 2T=20ms
        outlier_magnitudes_ug=tuple(_load_outlier_magnitudes_ug("20ms")),
    )
    return QuantumGradeConfig(
        name="field", axis=axis,
        sources={
            "sigma_shot_by_2T": "Jarlaud et al. 2024 (Master D-019, final): measured robust per-shot sigma by 2T, data/processed/jarlaud2024/calibration.json atom_interferometer.per_two_T: 10ms=10.70ug(n=720), 12ms=12.47ug(n=24,LOW CONFIDENCE), 14ms=6.83ug(n=480), 20ms=5.60ug(n=491,95%CI[5.04,6.40],paper-implied 5.06ug). FIELD grade uses 2T=20ms exactly (the paper's own static condition). Linear interpolation over 2T for other T (NOT 1/T^2 -- measured 10ms->20ms is only ~1.9x, a vibration-limited regime); see _sigma_shot_ug_interp.",
            "cycle_time": "Jarlaud et al. 2024: measured PER-SHOT interferometer cycle period, 1.548s (0.646 Hz), combining interlaced kD/kU shots (D-020, correcting D-014/D-019's use of the 2.955s per-k-direction interval)",
            "contrast_law": "Jarlaud et al. 2024 (D-014), rigid mode: C(Omega)=C0*exp(-(Omega/Omega_c)^2), C0=0.394+-0.017, Omega_c=48.2+-2.5 mrad/s @ 2T=12ms (2000 shots), scaled to this grade's T via physics-derived 1/T^2 law (D-020, _scale_omega_c)",
            "outlier_channel": "Jarlaud et al. 2024 (Master D-019 item 2): measured, 2T=20ms, data/processed/jarlaud2024/atom_outliers.json -- stationary outlier rate 9.0% (95% CI [6.7,11.8]%), P(outlier|prev outlier)=65.9% (bursty, Gilbert-Elliott 2-state Markov chain), 44 empirical magnitudes in tens-to-100+ug used with random sign. valid stays True in the bad state (realistic: sensor does not self-detect it). ASSUMPTION: no dynamics modulation of burst rate yet, though the dataset suggests bursts cluster near rotation-rate zero-crossings (noted, not modelled).",
            "bias_instability": "ASSUMPTION -- explicitly NOT the classical MICAL channel's ADEV floor (that is the classical hybridization accelerometer, not the atom channel, per Master D-014)",
            "inertial_pointing_limit": "Jarlaud et al. 2024: inertial-pointing mode (active tip-tilt compensation) operates up to Omega=250 mrad/s; Omega_c for this mode is an ASSUMPTION back-solved from that limit (see _inertial_pointing_omega_c), not an independently fit contrast law",
        },
    )


def _near_future() -> QuantumGradeConfig:
    axis = QuantumAxisParams(
        T_interrogation_s=0.0045,            # Wu et al. 2022 (Nat. Commun. 13:1442, DOI:10.1038/s41467-022-31410-4): compact cold-atom interferometer, T = 0-4.5 ms, 10 Hz data rate
        cycle_time_s=0.1,                    # Wu et al. 2022: 10 Hz measurement data rate
        sensitivity_m_s2_per_sqrt_hz=2e-5,   # derived from Wu et al. 2022: Delta g/g = 2.0e-6 at their reported operating point, treated as the tau=1s ADEV value -> N = ADEV(1s)*sqrt(1s) = g*2.0e-6 ~= 1.96e-5 m/s^2, rounded to 2e-5. NEAR_FUTURE/roadmap figure (single reported accuracy number reinterpreted as a sensitivity, not an independently cited ADEV curve) -- not for headline claims (D-002)
        bias_instability_m_s2=5e-6,          # ASSUMPTION (roadmap target, between lab 7e-7 and field-degraded values)
        bias_tau_c_s=200.0,
        scale_factor_std=1e-5,
        contrast0=JARLAUD_C0,                # measured (Jarlaud et al. 2024, D-014), reused pending a grade-specific measurement
        omega_c_rad_s=_scale_omega_c(0.0045),  # Jarlaud et al. 2024 rigid-mode Omega_c scaled to this grade's T=4.5ms via physics-derived 1/T^2 law (D-020) -- ~85.7 mrad/s
        contrast_threshold=0.08,
        dynamic_range_m_s2=3.0 * 9.80665,    # ASSUMPTION: higher dynamic range due to short T, high rate; must comfortably track 1g standing gravity
        coarse_accel_noise_std_m_s2=1e-6,
        coarse_accel_bias_std_m_s2=1e-4,
        omega_c_inertial_rad_s=_inertial_pointing_omega_c(JARLAUD_C0, 0.08),  # pointing="inertial" option, ASSUMPTION (see helper docstring)
    )
    return QuantumGradeConfig(
        name="near_future", axis=axis,
        sources={
            "T_and_rate": "Wu et al. 2022, Nature Communications 13:1442, DOI:10.1038/s41467-022-31410-4: compact grating-MOT cold-atom interferometer, T=0-4.5 ms interrogation, 10 Hz data rate, Delta g/g = 2.0e-6",
            "contrast_and_omega_c": "Jarlaud et al. 2024 (D-014): measured rigid-mode C0=0.394, Omega_c=48.2 mrad/s @ 2T=12ms, scaled to T=4.5ms via physics-derived 1/T^2 law (D-020) -- ~85.7 mrad/s; inertial-pointing option models the paper's 250 mrad/s operating envelope (ASSUMPTION Omega_c back-solve, see _inertial_pointing_omega_c)",
            "ASSUMPTIONS": "sensitivity_m_s2_per_sqrt_hz, bias_instability_m_s2, dynamic_range_m_s2 are roadmap-level ASSUMPTIONs extrapolated from the cited fractional accuracy figure, NOT independently measured/cited sensitivity numbers -- label NEAR_FUTURE, not for headline claims (D-002)",
        },
    )


GRADES: dict[str, Any] = {"lab": _lab, "field": _field, "near_future": _near_future}


# ---------------------------------------------------------------------------
# Pluggable stochastic core
# ---------------------------------------------------------------------------
class _ModelNoiseSource:
    """Physics-model shot noise, driven by the cited sensitivity figure."""

    def __init__(self, sensitivity_m_s2_per_sqrt_hz: float, rate_hz: float):
        self.sigma = sensitivity_m_s2_per_sqrt_hz * np.sqrt(rate_hz)

    def draw(self, rng: np.random.Generator, n_axes: int) -> np.ndarray:
        return rng.normal(0.0, self.sigma, size=n_axes)


class _ReplayNoiseSource:
    """Block-bootstrap replay of real, detrended acceleration residuals.

    ``residuals`` is a 1-D array of real (measured, mean-removed) sensor
    residuals sampled at ``sample_rate_hz``. It is decimated/resampled to
    the sensor's cycle rate (simple linear interpolation; adequate for a
    slowly varying noise envelope -- a full anti-aliased resample is left
    to the calibration agent producing the dataset) and then replayed by
    drawing random contiguous blocks of ``block_length`` samples (at the
    target rate), preserving short-range correlation structure of the real
    data. Each of the ``n_axes`` output channels gets an independently
    block-bootstrapped (but statistically identical) stream, all draws
    coming from the given ``rng`` for reproducibility.
    """

    def __init__(
        self,
        residuals: np.ndarray,
        sample_rate_hz: float,
        target_rate_hz: float,
        block_length: int = 20,
        n_axes: int = 3,
    ):
        residuals = np.asarray(residuals, dtype=np.float64)
        if residuals.ndim != 1 or residuals.size < 2:
            raise ValueError("residuals must be a 1-D array with >= 2 samples")
        if sample_rate_hz != target_rate_hz:
            n_src = residuals.size
            duration = n_src / sample_rate_hz
            n_dst = max(2, int(round(duration * target_rate_hz)))
            t_src = np.linspace(0.0, duration, n_src, endpoint=False)
            t_dst = np.linspace(0.0, duration, n_dst, endpoint=False)
            resampled = np.interp(t_dst, t_src, residuals)
        else:
            resampled = residuals
        self._pool = resampled
        self.block_length = max(1, min(block_length, self._pool.size))
        self.n_axes = n_axes
        self._streams = [np.zeros(0) for _ in range(n_axes)]

    def _refill(self, axis: int, rng: np.random.Generator, n_needed: int) -> None:
        chunks = []
        total = self._streams[axis].size
        while total < n_needed + self.block_length:
            start = int(rng.integers(0, self._pool.size - self.block_length + 1))
            chunks.append(self._pool[start:start + self.block_length])
            total += self.block_length
        if chunks:
            self._streams[axis] = np.concatenate([self._streams[axis]] + chunks)

    def draw(self, rng: np.random.Generator, n_axes: int) -> np.ndarray:
        out = np.zeros(n_axes)
        for ax in range(n_axes):
            self._refill(ax, rng, 1)
            out[ax] = self._streams[ax][0]
            self._streams[ax] = self._streams[ax][1:]
        return out


def fit_params_from_adev(taus: np.ndarray, adev: np.ndarray) -> dict[str, float]:
    """Derive ``sensitivity_m_s2_per_sqrt_hz`` and ``bias_instability_m_s2``
    from a measured Allan-deviation curve, so the quantum sensor model can be
    calibrated against real data (used together with ``noise_source="replay"``
    or to refit ``QuantumAxisParams`` for a new grade)."""
    fit = fit_white_and_bias_instability(taus, adev)
    return {
        "sensitivity_m_s2_per_sqrt_hz": fit["N_white"],
        "bias_instability_m_s2": fit["B_bias_instability"],
    }


class QuantumAccelerometer:
    """Cold-atom interferometric accelerometer implementing ``QuantumSensorModel``.

    ``axes``: which body axes (subset of (0,1,2) = x,y,z) are physically
    sensed; a 1-axis sensor passes e.g. ``axes=(2,)`` and reports NaN f_b /
    variance on the other two axes (PROPOSED-DECISION: the contract's
    ``QuantumSample.variance`` NaN-on-unsensed-axis convention is not
    explicit in ``core/types.py`` -- we mirror the ``f_b`` NaN convention
    for consistency; flagged for Master ratification).
    """

    def __init__(
        self,
        grade: str = "lab",
        axes: tuple[int, ...] = (0, 1, 2),
        rng: np.random.Generator | None = None,
        noise_source: Literal["model", "replay"] = "model",
        replay_residuals: np.ndarray | None = None,
        replay_sample_rate_hz: float | None = None,
        replay_block_length: int = 20,
        replay_two_T_s: np.ndarray | None = None,
        replay_clean: np.ndarray | None = None,
        sensor_id: str = "quantum",
        world: str = "flat",
        pointing: Literal["rigid", "inertial"] = "rigid",
        outlier_channel: bool = True,
    ):
        if grade not in GRADES:
            raise ValueError(f"unknown quantum grade '{grade}', choose from {list(GRADES)}")
        if not axes or any(a not in (0, 1, 2) for a in axes):
            raise ValueError("axes must be a non-empty subset of (0,1,2)")
        if pointing not in ("rigid", "inertial"):
            raise ValueError("pointing must be 'rigid' or 'inertial'")
        self._grade_name = grade
        self._cfg = GRADES[grade]()
        self._axes = tuple(sorted(set(axes)))
        self.sensor_id = sensor_id
        self.pointing = pointing
        if pointing == "inertial":
            if np.isnan(self._cfg.axis.omega_c_inertial_rad_s):
                raise ValueError(
                    f"grade '{grade}' has no inertial-pointing Omega_c configured "
                    "(NEAR_FUTURE-only feature per Jarlaud et al. 2024, D-014)"
                )
            self._omega_c_active = self._cfg.axis.omega_c_inertial_rad_s
        else:
            self._omega_c_active = self._cfg.axis.omega_c_rad_s
        # ``world`` (contract v0.2, C-5) accepted for interface consistency
        # only: like the IMU, this sensor consumes truth.f_b (gravity
        # already subtracted upstream via world.gravity_n) and never
        # recomputes gravity itself.
        self.world = world

        p = self._cfg.axis
        self.T = p.T_interrogation_s
        self.cycle_time = p.cycle_time_s
        self.rate_hz = 1.0 / self.cycle_time
        self.k_eff = K_EFF_RB87
        self.fringe_period_m_s2 = 2.0 * np.pi / (self.k_eff * self.T ** 2)

        init_rng = rng if rng is not None else np.random.default_rng()
        self._scale_factor_err = init_rng.normal(0.0, p.scale_factor_std, size=3)
        self._coarse_bias = init_rng.normal(0.0, p.coarse_accel_bias_std_m_s2, size=3)

        self._theta_bias = _gm1_theta(self.cycle_time, p.bias_tau_c_s)
        sigma_gm = p.bias_instability_m_s2 / 0.664 if p.bias_instability_m_s2 > 0 else 0.0
        self._sigma_gm = sigma_gm
        self._driving_std = sigma_gm * np.sqrt(max(0.0, 1.0 - self._theta_bias ** 2))
        self._bias_gm = init_rng.normal(0.0, sigma_gm, size=3) if sigma_gm > 0 else np.zeros(3)

        # Gilbert-Elliott outlier/fringe-jump channel (Master D-019 item 2).
        # Independent per-axis chain (each axis is a separate interferometer
        # in the real triad). Kept OFF (no-op) if the grade has no measured
        # outlier statistics (outlier_stationary_rate<=0) or if disabled.
        self.outlier_channel_enabled = bool(outlier_channel) and p.outlier_stationary_rate > 0
        if self.outlier_channel_enabled:
            self._p_good_to_bad, self._p_bad_to_bad = _ge_transition_probs(
                p.outlier_stationary_rate, p.outlier_persistence
            )
            self._outlier_magnitudes_m_s2 = np.asarray(p.outlier_magnitudes_ug, dtype=np.float64) * 1e-6 * 9.80665
            # start each axis's chain in its stationary distribution
            self._ge_state_bad = init_rng.random(3) < p.outlier_stationary_rate

        self.noise_source_kind = noise_source
        if noise_source == "model":
            self._noise = _ModelNoiseSource(p.sensitivity_m_s2_per_sqrt_hz, self.rate_hz)
            self._report_variance = np.full(3, self._noise.sigma ** 2)
        elif noise_source == "replay":
            if replay_residuals is None or replay_sample_rate_hz is None:
                raise ValueError("noise_source='replay' requires replay_residuals and replay_sample_rate_hz")
            residuals = np.asarray(replay_residuals, dtype=np.float64)
            # Master D-019 item 3: if raw per-shot arrays are passed (rather
            # than an already-filtered residual stream), keep only shots at
            # THIS sensor's own 2T and with clean=True (i.e. excluding the
            # dataset's own real outliers -- those are reintroduced
            # separately, and consistently, via the Gilbert-Elliott channel
            # above, so they are never double-counted).
            if replay_two_T_s is not None:
                two_t = np.asarray(replay_two_T_s, dtype=np.float64)
                mask = np.isclose(two_t, 2.0 * self.T, atol=1e-4)
                if replay_clean is not None:
                    mask &= np.asarray(replay_clean, dtype=bool)
                if not np.any(mask):
                    raise ValueError(f"no replay shots match 2T={2.0 * self.T:.4f}s (clean={replay_clean is not None})")
                residuals = residuals[mask]
            self._noise = _ReplayNoiseSource(
                residuals, replay_sample_rate_hz, self.rate_hz,
                block_length=replay_block_length, n_axes=3,
            )
            empirical_std = float(np.std(residuals))
            self._report_variance = np.full(3, empirical_std ** 2)
        else:
            raise ValueError(f"unknown noise_source '{noise_source}'")

        # cycle bookkeeping. Contract v0.2 (C-2): the CAI's acceleration
        # response is a TRIANGULAR weighting function over [t-2T, t] (t =
        # this sample's output time = end of cycle), peaking at the window
        # midpoint tau'=T -- the standard 3-pulse Mach-Zehnder sensitivity
        # function (Cheinet et al. 2008; used explicitly for hybridization
        # in Cheiney et al. 2018 / Lautier et al. 2014). The rest of the
        # cycle (cycle_time - 2T) is dead time before the window opens.
        self._cycle_start_t: float | None = None
        self._window_start_t: float | None = None
        self._cycle_end_t: float | None = None
        self._weighted_f = np.zeros(3)
        self._weight_sum = 0.0
        self._raw_f_sum = np.zeros(3)   # fallback boxcar accumulator, see note below
        self._raw_n = 0
        self._last_f_b = np.array([0.0, 0.0, 0.0])
        self._accum_omega_sq = np.zeros(3)
        self._n_accum = 0

    def config(self) -> dict[str, Any]:
        p = self._cfg.axis
        return {
            "type": "QuantumAccelerometer",
            "grade": self._grade_name,
            "world": self.world,
            "axes": self._axes,
            "rate_hz": self.rate_hz,
            "cycle_time_s": self.cycle_time,
            "T_interrogation_s": self.T,
            "k_eff_rad_per_m": self.k_eff,
            "fringe_period_m_s2": self.fringe_period_m_s2,
            "noise_source": self.noise_source_kind,
            "pointing": self.pointing,
            "omega_c_active_rad_s": self._omega_c_active,
            "outlier_channel_enabled": self.outlier_channel_enabled,
            "params": vars(p),
            "sources": self._cfg.sources,
        }

    def _start_new_cycle(self, t0: float) -> None:
        self._cycle_start_t = t0
        self._cycle_end_t = t0 + self.cycle_time
        self._window_start_t = self._cycle_end_t - 2.0 * self.T
        self._weighted_f = np.zeros(3)
        self._weight_sum = 0.0
        self._raw_f_sum = np.zeros(3)
        self._raw_n = 0
        self._accum_omega_sq = np.zeros(3)
        self._n_accum = 0

    def step(self, truth: TruthState, rng: np.random.Generator) -> QuantumSample | None:
        eps = 1e-9
        if self._cycle_start_t is None:
            self._start_new_cycle(truth.t)

        self._last_f_b = truth.f_b
        if truth.t >= self._window_start_t - eps:
            # triangular weight over [window_start, window_start+2T], peak
            # at the midpoint (tau'=T); normalized by the sum of weights
            # actually used (robust to the global tick dt being coarser
            # than 2T -- see PROPOSED-DECISION note in the module docstring
            # / SENSOR_NOTES.md: with the cited short-T operating points
            # here, dt=0.01s (D-003) is coarser than 2T, so in practice at
            # most one truth sample falls in-window and the weighting
            # degenerates to "use that sample", which is the documented
            # fallback below).
            tau = truth.t - self._window_start_t
            if tau <= 2.0 * self.T + eps:
                w = tau if tau <= self.T else (2.0 * self.T - tau)
                w = max(w, 0.0)
                self._weighted_f += w * truth.f_b
                self._weight_sum += w
                self._raw_f_sum += truth.f_b
                self._raw_n += 1
            self._accum_omega_sq += truth.omega_b ** 2
            self._n_accum += 1

        if truth.t < self._cycle_end_t - eps:
            return None

        # end of cycle: produce a sample
        if self._weight_sum > 1e-12:
            a_avg = self._weighted_f / self._weight_sum
        elif self._raw_n > 0:
            # dt (D-003: 0.01s) is coarser than the 2T response window for
            # every cited grade here, so triangular weighting degenerates
            # to at most one in-window sample; fall back to its raw value
            # (equivalent to a boxcar of 1 sample). See module docstring.
            a_avg = self._raw_f_sum / self._raw_n
        else:
            a_avg = self._last_f_b
        n_omega = max(1, self._n_accum)
        omega_rms = np.sqrt(self._accum_omega_sq / n_omega)

        # slow correlated bias residual (GM1), updated once per cycle
        self._bias_gm = self._theta_bias * self._bias_gm + self._driving_std * rng.normal(size=3)

        noise_a = self._noise.draw(rng, 3)

        # fringe wrap + hybridization to resolve fringe order
        fp = self.fringe_period_m_s2
        a_wrapped = a_avg - fp * np.round(a_avg / fp)
        a_wrapped_meas = a_wrapped + noise_a

        p = self._cfg.axis
        coarse_noise = rng.normal(0.0, p.coarse_accel_noise_std_m_s2, size=3)
        a_coarse = a_avg + self._coarse_bias + coarse_noise
        n_fringe = np.round((a_coarse - a_wrapped_meas) / fp)
        a_hybrid = a_wrapped_meas + fp * n_fringe

        a_hybrid = a_hybrid * (1.0 + self._scale_factor_err) + self._bias_gm

        # Gilbert-Elliott outlier/fringe-jump channel (Master D-019 item 2):
        # added SEPARATELY from the shot noise above (so real outliers in a
        # "clean=True"-filtered replay stream are never double-counted).
        # valid is NOT forced False here -- the sensor cannot self-detect
        # this failure mode; that is exactly what the trust engine must
        # catch downstream. ASSUMPTION: no dynamics modulation of burst
        # rate/timing yet, even though the dataset suggests bursts cluster
        # near rotation-rate zero-crossings (D-019 item 2, noted not modelled).
        if self.outlier_channel_enabled:
            prev_bad = self._ge_state_bad
            u = rng.random(3)
            p_to_bad = np.where(prev_bad, self._p_bad_to_bad, self._p_good_to_bad)
            self._ge_state_bad = u < p_to_bad
            if np.any(self._ge_state_bad):
                mags = rng.choice(self._outlier_magnitudes_m_s2, size=3)
                signs = rng.choice([-1.0, 1.0], size=3)
                a_hybrid = a_hybrid + np.where(self._ge_state_bad, mags * signs, 0.0)

        # contrast loss vs rotation: omega_perp for axis i = rms of the OTHER two omega components
        contrast = np.zeros(3)
        for i in range(3):
            other = [j for j in range(3) if j != i]
            omega_perp = np.sqrt(np.sum(omega_rms[other] ** 2))
            contrast[i] = p.contrast0 * np.exp(-(omega_perp / self._omega_c_active) ** 2)

        valid_axis = (contrast >= p.contrast_threshold) & (np.abs(a_avg) <= p.dynamic_range_m_s2)

        out_f = np.full(3, np.nan)
        out_var = np.full(3, np.nan)
        out_contrast_vals = []
        any_sensed_valid = False
        for i in self._axes:
            out_f[i] = a_hybrid[i]
            out_var[i] = self._report_variance[i]
            out_contrast_vals.append(contrast[i])
            any_sensed_valid = any_sensed_valid or bool(valid_axis[i])
        valid = bool(np.all(valid_axis[list(self._axes)]))

        sample = QuantumSample(
            t=truth.t,
            f_b=out_f,
            variance=out_var,
            valid=valid,
            cycle_time=self.cycle_time,
            contrast=float(np.mean(out_contrast_vals)) if out_contrast_vals else 0.0,
            sensor_id=self.sensor_id,
            t_interrogation=self.T,
            response="triangular",
        )
        self._start_new_cycle(truth.t)
        return sample
