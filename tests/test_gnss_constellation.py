import numpy as np

from fedqpnt.gnss.constellation import Constellation, EnuFrame, geodetic_to_ecef
from fedqpnt.core.types import ORIGIN_LLH


def test_origin_roundtrip():
    frame = EnuFrame(ORIGIN_LLH)
    enu = frame.ecef_to_enu(frame.origin_ecef)
    assert np.allclose(enu, np.zeros(3), atol=1e-6)


def test_enu_ecef_roundtrip_offset():
    frame = EnuFrame(ORIGIN_LLH)
    p_enu = np.array([1234.0, -500.0, 80.0])
    p_ecef = frame.enu_to_ecef(p_enu)
    back = frame.ecef_to_enu(p_ecef)
    assert np.allclose(back, p_enu, atol=1e-6)


def test_visible_sats_reasonable_count():
    c = Constellation(mask_deg=10.0)
    vis = c.visible_sats(0.0, np.zeros(3))
    assert 4 <= len(vis) <= 16
    for v in vis:
        assert np.degrees(v["elevation"]) >= 10.0 - 1e-6


def test_visibility_changes_over_time():
    c = Constellation(mask_deg=10.0)
    prns_0 = {v["prn"] for v in c.visible_sats(0.0, np.zeros(3))}
    prns_later = {v["prn"] for v in c.visible_sats(6 * 3600.0, np.zeros(3))}
    assert prns_0 != prns_later


def test_satellite_altitude_near_gps_nominal():
    c = Constellation()
    v = c.visible_sats(0.0, np.zeros(3))[0]
    r = np.linalg.norm(v["sat_pos_enu"] - c.frame.ecef_to_enu(c.frame.origin_ecef))
    # slant range to a GPS satellite is roughly 20,000-25,500 km depending on elevation
    assert 18e6 < r < 27e6
