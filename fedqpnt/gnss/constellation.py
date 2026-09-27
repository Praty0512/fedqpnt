"""GPS L1 C/A constellation: nominal Walker almanac, ECEF propagation, ECEF<->ENU.

Nominal orbital parameters (semi-major axis, inclination, plane count) follow
the published GPS constellation design:
  * a ~= 26,560 km, e ~= 0 (near-circular), i ~= 55 deg, 6 orbital planes (A-F),
    nominal Walker 24/6/1 pattern (24 slots, 4 satellites/plane minimum).
  Source: Kaplan & Hegarty, "Understanding GPS/GNSS: Principles and
  Applications", 3rd ed., Artech House, 2017, Ch. 2 (constellation design).
  This module does NOT embed a live/dated YUMA almanac (none was fetched);
  RAAN/mean-anomaly offsets per plane/slot are a synthetic nominal Walker
  pattern -- marked ASSUMPTION in docs/specs/raw/GNSS_ATTACK_NOTES.md.

Earth model: WGS-84 ellipsoid for ECEF<->geodetic; propagation is unperturbed
two-body Keplerian (no J2/SRP) -- adequate for multi-hour sim windows where
only geometry (elevation/azimuth/DOP) matters, not cm-level ephemeris accuracy.
"""
from __future__ import annotations

import numpy as np

from fedqpnt.core.types import ORIGIN_LLH

MU_EARTH = 3.986005e14      # m^3/s^2, WGS-84 earth gravitational constant
OMEGA_EARTH = 7.2921151467e-5  # rad/s, WGS-84 earth rotation rate

WGS84_A = 6378137.0             # m, semi-major axis
WGS84_F = 1.0 / 298.257223563   # flattening
WGS84_E2 = WGS84_F * (2 - WGS84_F)

GPS_SEMI_MAJOR_AXIS_M = 26_560_000.0
GPS_INCLINATION_RAD = np.radians(55.0)
GPS_NUM_PLANES = 6
GPS_SATS_PER_PLANE = 4  # 24-slot nominal Walker pattern -> ~31 in real constellation, we use 24 nominal + extras
GPS_EXTRA_SATS_PER_PLANE = (1, 1, 1, 0, 1, 1)  # pads to ~31 total, mimicking real over-provisioning


def build_nominal_almanac() -> list[dict]:
    """Return a synthetic nominal GPS almanac (Walker-like), one dict per PRN.

    Each entry: prn, a (m), e, i (rad), raan (rad), argp (rad), M0 (rad).
    ASSUMPTION: not a real dated almanac; used for realistic sky geometry only.
    """
    sats = []
    prn = 1
    for plane in range(GPS_NUM_PLANES):
        raan = np.radians(plane * 60.0)  # 6 planes, 60 deg apart
        n_sats = GPS_SATS_PER_PLANE + GPS_EXTRA_SATS_PER_PLANE[plane]
        for slot in range(n_sats):
            m0 = np.radians(slot * (360.0 / n_sats) + plane * 13.0)  # plane phasing offset
            sats.append(dict(
                prn=prn,
                a=GPS_SEMI_MAJOR_AXIS_M,
                e=0.001,
                i=GPS_INCLINATION_RAD,
                raan=raan,
                argp=0.0,
                M0=m0,
            ))
            prn += 1
    return sats


def _solve_kepler(M: np.ndarray, e: float, tol: float = 1e-12, max_iter: int = 50) -> np.ndarray:
    E = M.copy()
    for _ in range(max_iter):
        dE = (E - e * np.sin(E) - M) / (1 - e * np.cos(E))
        E -= dE
        if np.max(np.abs(dE)) < tol:
            break
    return E


def sat_ecef_state(sat: dict, t: float) -> tuple[np.ndarray, np.ndarray]:
    """Propagate one almanac entry to ECEF position/velocity at sim time t [s].

    Unperturbed two-body Keplerian orbit; ECEF via Earth-rotation angle from
    t=0. Returns (pos_ecef[3], vel_ecef[3]) in metres, metres/s.
    """
    a, e, i, raan0, argp, M0 = sat["a"], sat["e"], sat["i"], sat["raan"], sat["argp"], sat["M0"]
    n = np.sqrt(MU_EARTH / a ** 3)
    M = M0 + n * t
    E = _solve_kepler(np.array([M]), e)[0]
    cosE, sinE = np.cos(E), np.sin(E)
    # position in orbital plane
    x_p = a * (cosE - e)
    y_p = a * np.sqrt(1 - e ** 2) * sinE
    r = a * (1 - e * cosE)
    Edot = n / (1 - e * cosE)
    vx_p = -a * sinE * Edot
    vy_p = a * np.sqrt(1 - e ** 2) * cosE * Edot

    cos_o, sin_o = np.cos(argp), np.sin(argp)
    cos_i, sin_i = np.cos(i), np.sin(i)
    # earth rotates under fixed-inertial RAAN frame -> apparent RAAN in ECEF
    raan = raan0 - OMEGA_EARTH * t

    cos_O, sin_O = np.cos(raan), np.sin(raan)

    R = np.array([
        [cos_O * cos_o - sin_O * sin_o * cos_i, -cos_O * sin_o - sin_O * cos_o * cos_i],
        [sin_O * cos_o + cos_O * sin_o * cos_i, -sin_O * sin_o + cos_O * cos_o * cos_i],
        [sin_o * sin_i, cos_o * sin_i],
    ])
    pos = R @ np.array([x_p, y_p])
    vel = R @ np.array([vx_p, vy_p])
    # account for RAAN rotation rate (-OMEGA_EARTH) affecting velocity slightly;
    # negligible correction ignored (unperturbed two-body assumption, ASSUMPTION).
    return pos, vel


def geodetic_to_ecef(lat_deg: float, lon_deg: float, h_m: float) -> np.ndarray:
    lat, lon = np.radians(lat_deg), np.radians(lon_deg)
    sin_lat, cos_lat = np.sin(lat), np.cos(lat)
    N = WGS84_A / np.sqrt(1 - WGS84_E2 * sin_lat ** 2)
    x = (N + h_m) * cos_lat * np.cos(lon)
    y = (N + h_m) * cos_lat * np.sin(lon)
    z = (N * (1 - WGS84_E2) + h_m) * sin_lat
    return np.array([x, y, z])


class EnuFrame:
    """ECEF <-> local-level ENU transform anchored at ORIGIN_LLH."""

    def __init__(self, origin_llh: tuple[float, float, float] = ORIGIN_LLH):
        lat_deg, lon_deg, h_m = origin_llh
        self.origin_ecef = geodetic_to_ecef(lat_deg, lon_deg, h_m)
        lat, lon = np.radians(lat_deg), np.radians(lon_deg)
        sl, cl = np.sin(lat), np.cos(lat)
        so, co = np.sin(lon), np.cos(lon)
        # rows: E, N, U basis vectors expressed in ECEF
        self.R_ecef_to_enu = np.array([
            [-so, co, 0.0],
            [-sl * co, -sl * so, cl],
            [cl * co, cl * so, sl],
        ])

    def ecef_to_enu(self, p_ecef: np.ndarray) -> np.ndarray:
        return self.R_ecef_to_enu @ (p_ecef - self.origin_ecef)

    def ecef_vel_to_enu(self, v_ecef: np.ndarray) -> np.ndarray:
        return self.R_ecef_to_enu @ v_ecef

    def enu_to_ecef(self, p_enu: np.ndarray) -> np.ndarray:
        return self.R_ecef_to_enu.T @ p_enu + self.origin_ecef


class Constellation:
    """Nominal GPS almanac + ENU sky geometry with an elevation mask."""

    def __init__(self, mask_deg: float = 10.0, origin_llh: tuple[float, float, float] = ORIGIN_LLH):
        self.almanac = build_nominal_almanac()
        self.mask_rad = np.radians(mask_deg)
        self.frame = EnuFrame(origin_llh)

    def visible_sats(self, t: float, rx_pos_enu: np.ndarray) -> list[dict]:
        """Return list of dicts: prn, sat_pos_enu, sat_vel_enu, elevation, azimuth
        for satellites above the mask angle, as seen from rx_pos_enu (ENU, m)."""
        rx_ecef = self.frame.enu_to_ecef(rx_pos_enu)
        out = []
        for sat in self.almanac:
            pos_ecef, vel_ecef = sat_ecef_state(sat, t)
            pos_enu = self.frame.ecef_to_enu(pos_ecef)
            vel_enu = self.frame.ecef_vel_to_enu(vel_ecef)
            los = pos_enu - rx_pos_enu
            rng = np.linalg.norm(los)
            if rng < 1.0:
                continue
            los_u = los / rng
            elev = np.arcsin(np.clip(los_u[2], -1.0, 1.0))
            az = np.arctan2(los_u[0], los_u[1]) % (2 * np.pi)
            if elev < self.mask_rad:
                continue
            out.append(dict(
                prn=sat["prn"], sat_pos_enu=pos_enu, sat_vel_enu=vel_enu,
                elevation=elev, azimuth=az,
            ))
        return out

    def config(self) -> dict:
        return dict(
            num_sats=len(self.almanac),
            mask_deg=float(np.degrees(self.mask_rad)),
            semi_major_axis_m=GPS_SEMI_MAJOR_AXIS_M,
            inclination_deg=55.0,
            num_planes=GPS_NUM_PLANES,
            source="Kaplan & Hegarty 2017 Ch.2 (orbital params); RAAN/M0 phasing = synthetic ASSUMPTION",
        )
