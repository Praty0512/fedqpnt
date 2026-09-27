import numpy as np

from fedqpnt.core.seeding import stream
from fedqpnt.gnss.signal import GnssSignalModel
from fedqpnt.gnss.receiver import GnssReceiver
from tests._helpers import static_truth, const_vel_truth, turning_truth


def _run(kind, duration_s=60.0, rate_hz=1.0, dt=0.01, seed=11):
    rng = stream(seed, "n", "gnss")
    model = GnssSignalModel(rate_hz=rate_hz)
    recv = GnssReceiver()
    fixes, truths = [], []
    n = int(duration_s / dt)
    fn = {"static": static_truth, "const_vel": const_vel_truth, "turning": turning_truth}[kind]
    for k in range(n):
        t = k * dt
        truth = fn(t)
        ep = model.step(truth, rng)
        if ep is None:
            continue
        fix = recv.solve(ep.for_agent())
        fixes.append(fix)
        truths.append(truth)
    return fixes, truths


def test_static_pvt_accuracy():
    fixes, truths = _run("static", duration_s=120.0)
    valid = [f for f in fixes if f.valid]
    assert len(valid) >= 100
    pos_err = np.array([np.linalg.norm(f.pos[:2] - t.pos[:2]) for f, t in zip(fixes, truths) if f.valid])
    # single-frequency standalone GPS horizontal accuracy: a few metres 1-sigma
    # (typical SPS spec ~<=7.8m 95%; open literature ~2-5m 1-sigma), Misra & Enge Ch.7 / GPS SPS PS 2020.
    assert pos_err.mean() < 5.0
    assert np.percentile(pos_err, 95) < 12.0
    hdops = [np.sqrt(f.cov_pos[0, 0] + f.cov_pos[1, 1]) for f in fixes if f.valid]
    assert np.mean(hdops) < 20.0  # sane HDOP-like spread, not blown up


def test_dynamic_const_vel_velocity_accuracy():
    fixes, truths = _run("const_vel", duration_s=60.0)
    valid_pairs = [(f, t) for f, t in zip(fixes, truths) if f.valid]
    assert len(valid_pairs) >= 40
    vel_err = np.array([np.linalg.norm(f.vel - t.vel) for f, t in valid_pairs])
    # velocity error expected cm/s to dm/s level
    assert vel_err.mean() < 0.5


def test_turning_trajectory_tracks_position():
    fixes, truths = _run("turning", duration_s=60.0)
    valid_pairs = [(f, t) for f, t in zip(fixes, truths) if f.valid]
    assert len(valid_pairs) >= 40
    pos_err = np.array([np.linalg.norm(f.pos[:2] - t.pos[:2]) for f, t in valid_pairs])
    assert pos_err.mean() < 8.0


def test_invalid_below_min_sats():
    recv = GnssReceiver(min_sats=4)
    rng = stream(1, "n", "gnss")
    model = GnssSignalModel(rate_hz=1.0)
    ep = model.step(static_truth(0.0), rng)
    ep.obs = ep.obs[:2]  # force too few sats
    fix = recv.solve(ep.for_agent())
    assert fix.valid is False
    assert fix.num_sats == 2
