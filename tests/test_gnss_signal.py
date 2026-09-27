import numpy as np

from fedqpnt.core.seeding import stream
from fedqpnt.gnss.signal import GnssSignalModel, cn0_nominal_dbhz
from tests._helpers import static_truth


def test_step_respects_rate():
    rng = stream(1, "t", "gnss")
    model = GnssSignalModel(rate_hz=1.0)
    got = [model.step(static_truth(k * 0.01), rng) for k in range(150)]
    n_epochs = sum(1 for e in got if e is not None)
    assert n_epochs == 2  # 1.5 s of data at 1 Hz -> epochs at t=0 and t=1.0


def test_cn0_increases_with_elevation():
    assert cn0_nominal_dbhz(np.radians(10)) < cn0_nominal_dbhz(np.radians(80))


def test_determinism_same_seed():
    rng1 = stream(7, "n", "gnss")
    rng2 = stream(7, "n", "gnss")
    m1 = GnssSignalModel(rate_hz=1.0)
    m2 = GnssSignalModel(rate_hz=1.0)
    e1 = m1.step(static_truth(0.0), rng1)
    e2 = m2.step(static_truth(0.0), rng2)
    assert len(e1.obs) == len(e2.obs)
    for o1, o2 in zip(e1.obs, e2.obs):
        assert o1.prn == o2.prn
        assert np.isclose(o1.pseudorange, o2.pseudorange)
        assert np.isclose(o1.cn0_dbhz, o2.cn0_dbhz)


def test_different_seed_differs():
    rngA = stream(7, "nA", "gnss")
    rngB = stream(8, "nB", "gnss")
    mA = GnssSignalModel(rate_hz=1.0)
    mB = GnssSignalModel(rate_hz=1.0)
    eA = mA.step(static_truth(0.0), rngA)
    eB = mB.step(static_truth(0.0), rngB)
    prs_A = [o.pseudorange for o in eA.obs]
    prs_B = [o.pseudorange for o in eB.obs]
    assert prs_A != prs_B


def test_pseudorange_close_to_geometric_range():
    rng = stream(3, "n", "gnss")
    model = GnssSignalModel(rate_hz=1.0)
    truth = static_truth(0.0)
    ep = model.step(truth, rng)
    for o in ep.obs:
        geo = np.linalg.norm(o.sat_pos - truth.pos)
        # pseudorange = geo + clock_bias(~0 initially) + iono/tropo/mp/noise, should be within ~50 m
        assert abs(o.pseudorange - geo) < 50.0
