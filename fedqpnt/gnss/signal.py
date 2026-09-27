"""Clean GNSS raw-observable generator: pseudorange, pseudorange-rate, C/N0.

Error budget modelled explicitly (each a correlated or white process):
  * Receiver clock: two-state (bias, drift) random-walk driven by a TCXO-class
    Allan deviation. sigma_bias RW ~ h0-driven, sigma_drift RW ~ h_-2 driven.
    Typical TCXO: Allan deviation ~1e-9 to 1e-11 over 1-100s (freq stability).
    Source: J. Vig, "Introduction to Quartz Frequency Standards", Army
    Research Lab SLCET-TR-92-1 (rev 1992); typical TCXO short-term stability
    ~1e-9 at tau=1s (widely cited figure) -- exact device unspecified =>
    ASSUMPTION with parameter table entry.
  * Ionosphere: Klobuchar *residual* after single-frequency broadcast
    correction, modelled as a slowly-varying correlated (Gauss-Markov) process
    with elevation-dependent obliquity scaling; residual RMS ~1-3 m after
    correction. Source: Klobuchar, J.A., "Ionospheric Time-Delay Algorithm for
    Single-Frequency GPS Users", IEEE Trans. Aerosp. Electron. Syst., 1987.
  * Troposphere: Saastamoinen zenith delay + 1/sin(el) mapping (simplified
    Niell-like elevation mapping), residual after model ~0.1-0.5 m zenith.
    Source: Saastamoinen, J., "Atmospheric correction for the troposphere and
    stratosphere in radio ranging of satellites", Geophysical Monograph 15,
    1972.
  * Multipath: elevation-dependent Gauss-Markov process, larger at low
    elevation. Source: Kaplan & Hegarty 2017 Ch.7 (multipath vs elevation,
    qualitative shape; magnitude tuned to keep low-el multipath ~1-3 m,
    ASSUMPTION for exact coefficients).
  * Thermal noise (code + carrier tracking jitter) from C/N0 via standard DLL
    code-tracking-jitter and PLL phase-jitter formulas.
    Source: Kaplan & Hegarty 2017, Eq. 8.24 (non-coherent early-late DLL code
    jitter) and Eq. 8.35-ish (PLL thread jitter); Doppler/pseudorange-rate
    noise derived from PLL jitter via wavelength scaling.
  * C/N0 vs elevation: empirical nominal curve ~38 dB-Hz at 10 deg rising to
    ~48-50 dB-Hz at zenith, typical open-sky single-frequency L1 C/A receiver
    behaviour. Source: Kaplan & Hegarty 2017 Ch.5 (typical C/N0 ranges);
    exact curve shape here is a fitted ASSUMPTION.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from fedqpnt.core.types import GnssEpoch, SatObs, TruthState, C_LIGHT
from fedqpnt.gnss.constellation import Constellation

L1_FREQ_HZ = 1575.42e6
L1_WAVELENGTH_M = C_LIGHT / L1_FREQ_HZ
CHIP_RATE_CA_HZ = 1.023e6
CODE_CHIP_M = C_LIGHT / CHIP_RATE_CA_HZ  # ~293.05 m


@dataclass
class ClockState:
    """Two-state receiver clock: bias [m], drift [m/s]. Random-walk driven."""
    bias_m: float = 0.0
    drift_mps: float = 0.0
    # TCXO-class process noise (ASSUMPTION, see module docstring)
    sigma_bias_rw: float = 3.0e-2     # m/sqrt(s) equiv. white freq noise driving bias
    sigma_drift_rw: float = 3.0e-3    # m/s/sqrt(s) driving drift (freq aging/random walk)

    def step(self, dt: float, rng: np.random.Generator) -> None:
        self.drift_mps += rng.normal(0.0, self.sigma_drift_rw * np.sqrt(dt))
        self.bias_m += self.drift_mps * dt + rng.normal(0.0, self.sigma_bias_rw * np.sqrt(dt))


def _gauss_markov_step(x: float, dt: float, tau: float, sigma: float, rng: np.random.Generator) -> float:
    """First-order Gauss-Markov process update (steady-state variance = sigma^2)."""
    phi = np.exp(-dt / tau)
    w_sigma = sigma * np.sqrt(max(1.0 - phi ** 2, 0.0))
    return phi * x + rng.normal(0.0, w_sigma)


def cn0_nominal_dbhz(elevation_rad: float) -> float:
    """Nominal open-sky C/N0 vs elevation, ~38 dB-Hz @10deg -> ~48 dB-Hz @90deg."""
    el_deg = np.degrees(elevation_rad)
    el_deg = np.clip(el_deg, 0.0, 90.0)
    return 38.0 + 10.0 * (el_deg - 10.0) / 80.0


def tropo_delay_m(elevation_rad: float) -> float:
    """Saastamoinen zenith delay (~2.3 m nominal sea-level) with 1/sin(el) mapping."""
    zenith_delay = 2.3
    el = max(elevation_rad, np.radians(5.0))
    return zenith_delay / np.sin(el)


# --------------------------------------------------------------------------
# UERE error-budget functions -- SINGLE SOURCE OF TRUTH for both the clean
# signal generator (below) and the receiver's measurement-weighting /ARIM
# calibration (fedqpnt/gnss/receiver.py). Steady-state (marginal) sigmas of
# the Gauss-Markov residual processes plus the thermal tracking-jitter sigma.
# See module docstring for citations; magnitudes marked ASSUMPTION there.
# --------------------------------------------------------------------------
def iono_residual_sigma_m(elevation_rad: float) -> float:
    return 1.5 / max(np.sin(elevation_rad), 0.3)


def tropo_residual_sigma_m(elevation_rad: float) -> float:
    return 0.05 * tropo_delay_m(elevation_rad)


def multipath_sigma_m(elevation_rad: float) -> float:
    return 0.3 + 2.0 * np.exp(-elevation_rad / np.radians(20.0))


# thermal tracking-loop parameters (Kaplan & Hegarty 2017 Ch.8-style DLL/PLL
# jitter formulas); ASSUMPTION for the specific loop-bandwidth/correlator
# values (T_int, B_dll, d_spacing, B_pll), see module docstring.
T_INT_S = 0.02        # coherent integration time, s (20 ms C/A)
B_DLL_HZ = 1.0         # code loop noise bandwidth, Hz (narrow correlator)
D_SPACING_CHIPS = 0.1  # narrow-correlator early-late spacing, chips
B_PLL_HZ = 15.0        # phase loop noise bandwidth, Hz (FLL-assisted PLL)


def code_thermal_sigma_m(cn0_dbhz: float) -> float:
    """Non-coherent early-late DLL code-tracking jitter (1-sigma), metres."""
    cn0_lin = 10 ** (cn0_dbhz / 10.0)
    code_jitter_chip = np.sqrt((B_DLL_HZ / (2 * cn0_lin)) * D_SPACING_CHIPS *
                                (1.0 + 2.0 / (T_INT_S * cn0_lin * (2 - D_SPACING_CHIPS))))
    return code_jitter_chip * CODE_CHIP_M


def doppler_thermal_sigma_mps(cn0_dbhz: float) -> float:
    """PLL phase-jitter-derived pseudorange-rate (Doppler) noise, 1-sigma, m/s."""
    cn0_lin = 10 ** (cn0_dbhz / 10.0)
    phase_jitter_rad = np.sqrt((B_PLL_HZ / cn0_lin) * (1.0 + 1.0 / (2 * T_INT_S * cn0_lin)))
    return (phase_jitter_rad / (2 * np.pi)) * L1_WAVELENGTH_M / T_INT_S


def uere_variance_m2(elevation_rad: float, cn0_dbhz: float) -> float:
    """Total pseudorange measurement variance (excl. clock, which WLS
    estimates as a separate state): thermal + iono-residual + tropo-residual
    + multipath, all treated as independent contributions (each has an
    independent per-PRN Gauss-Markov / white-noise generating process)."""
    sig_thermal = code_thermal_sigma_m(cn0_dbhz)
    sig_iono = iono_residual_sigma_m(elevation_rad)
    sig_tropo = tropo_residual_sigma_m(elevation_rad)
    sig_mp = multipath_sigma_m(elevation_rad)
    return sig_thermal ** 2 + sig_iono ** 2 + sig_tropo ** 2 + sig_mp ** 2


@dataclass
class SatChannelState:
    iono_residual_m: float = 0.0
    tropo_residual_m: float = 0.0
    multipath_m: float = 0.0


@dataclass
class GnssSignalModel:
    """Clean-signal generator implementing GnssSignalModel protocol."""
    rate_hz: float = 1.0
    mask_deg: float = 10.0
    _constellation: Constellation = field(default=None, repr=False)
    _clock: ClockState = field(default_factory=ClockState)
    _chan: dict = field(default_factory=dict)   # prn -> SatChannelState
    _last_emit_t: float = field(default=-1e9)
    _last_pos: dict = field(default_factory=dict)  # prn -> (pos,vel,t) for tracked continuity

    def __post_init__(self):
        if self._constellation is None:
            self._constellation = Constellation(mask_deg=self.mask_deg)

    def config(self) -> dict:
        return dict(
            rate_hz=self.rate_hz, mask_deg=self.mask_deg,
            clock_sigma_bias_rw=self._clock.sigma_bias_rw,
            clock_sigma_drift_rw=self._clock.sigma_drift_rw,
            l1_wavelength_m=L1_WAVELENGTH_M, code_chip_m=CODE_CHIP_M,
            constellation=self._constellation.config(),
        )

    def step(self, truth: TruthState, rng: np.random.Generator) -> GnssEpoch | None:
        period = 1.0 / self.rate_hz
        if truth.t - self._last_emit_t < period - 1e-9:
            return None
        self._last_emit_t = truth.t
        dt = period

        self._clock.step(dt, rng)

        rx_pos = truth.pos
        rx_vel = truth.vel
        visible = self._constellation.visible_sats(truth.t, rx_pos)

        obs = []
        for sat in visible:
            prn = sat["prn"]
            elev = sat["elevation"]
            if prn not in self._chan:
                # Initialise each Gauss-Markov channel state at a draw from its
                # OWN stationary distribution (not 0), otherwise every newly-
                # risen satellite (and the whole sky at t=0) exhibits a multi-
                # time-constant warm-up transient (tau_tropo=1800s) that biases
                # residual variance low for the first ~30-90 min of any run --
                # this quietly miscalibrates RAIM chi-square (found during
                # Master WP-3.x review round 2: 30-min clean RAIM calibration
                # test failed with ratio ~0.6 before this fix).
                self._chan[prn] = SatChannelState(
                    iono_residual_m=rng.normal(0.0, iono_residual_sigma_m(elev)),
                    tropo_residual_m=rng.normal(0.0, tropo_residual_sigma_m(elev)),
                    multipath_m=rng.normal(0.0, multipath_sigma_m(elev)),
                )
            chan = self._chan[prn]

            # correlated residual processes (Gauss-Markov), steady-state sigma
            # from the shared UERE budget functions (single source of truth).
            chan.iono_residual_m = _gauss_markov_step(
                chan.iono_residual_m, dt, tau=600.0, sigma=iono_residual_sigma_m(elev), rng=rng)
            chan.tropo_residual_m = _gauss_markov_step(
                chan.tropo_residual_m, dt, tau=1800.0, sigma=tropo_residual_sigma_m(elev), rng=rng)
            chan.multipath_m = _gauss_markov_step(
                chan.multipath_m, dt, tau=20.0, sigma=multipath_sigma_m(elev), rng=rng)

            los = sat["sat_pos_enu"] - rx_pos
            rng_geo = float(np.linalg.norm(los))
            los_u = los / rng_geo
            range_rate = -float(np.dot(sat["sat_vel_enu"] - rx_vel, los_u))

            cn0 = cn0_nominal_dbhz(elev) + rng.normal(0.0, 0.3)

            code_noise_m = code_thermal_sigma_m(cn0)
            doppler_noise_mps = doppler_thermal_sigma_mps(cn0)

            pseudorange = (rng_geo + self._clock.bias_m
                           + chan.iono_residual_m + chan.tropo_residual_m + chan.multipath_m
                           + rng.normal(0.0, code_noise_m))
            pseudorange_rate = (range_rate + self._clock.drift_mps
                                 + rng.normal(0.0, doppler_noise_mps))

            obs.append(SatObs(
                prn=prn, pseudorange=pseudorange, pseudorange_rate=pseudorange_rate,
                cn0_dbhz=float(cn0), sat_pos=sat["sat_pos_enu"], sat_vel=sat["sat_vel_enu"],
                elevation=elev, azimuth=sat["azimuth"], tracked=True,
            ))

        return GnssEpoch(t=truth.t, obs=obs, agc_db=0.0, noise_floor_db=0.0,
                          meta=dict(clk_bias_m=self._clock.bias_m, clk_drift_mps=self._clock.drift_mps))
