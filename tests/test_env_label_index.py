"""D-082 perf: the indexed active-attack lookup in NodeEnvironment._label is bit-identical to the linear scan."""
import numpy as np

from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.runner import RunSpec, run_single

ATK = ([dict(kind="abrupt_spoof", onset_s=30.0 + k * 4.0, duration_s=2.0, severity=0.5) for k in range(40)]
       + [dict(kind="drift_spoof", onset_s=60.0, duration_s=30.0, severity=0.5),      # overlaps abrupt segments
          dict(kind="jam_cw", onset_s=100.0, duration_s=None, severity=0.4),            # open-ended
          dict(kind="meaconing", onset_s=120.0, duration_s=10.0, severity=0.6),
          dict(kind="meaconing_displaced", onset_s=140.0, duration_s=20.0, severity=0.5)])


def _env(attacks, dur=200.0):
    return NodeEnvironment(EnvConfig(platform="ground", world="schuler_tangent", imu_grade="tactical",
                                     quantum_grade="field", attacks=list(attacks)), seed=530, dt=0.01, duration_s=dur)


def test_label_identical_to_linear_scan_on_boundaries_and_random_times():
    env = _env(ATK)
    rng = np.random.default_rng(0)
    ts = list(rng.uniform(-5.0, 200.0, 20000)) + list(np.arange(0.0, 200.0, 0.37))
    for a in ATK:
        for base in (a["onset_s"], a["onset_s"] + (a["duration_s"] or 0.0)):
            for d in (-1e-9, 0.0, 1e-9, 0.2, 2.0, 2.0 - 1e-12, 2.0 + 1e-12):
                ts.append(base + d)
    for t in ts:
        assert env._label(float(t)) == env._label_reference(float(t)), t


def test_no_attacks_and_single_attack():
    for atk in ([], [ATK[0]]):
        env = _env(atk, 40.0)
        for t in np.arange(0.0, 40.0, 0.25):
            assert env._label(float(t)) == env._label_reference(float(t))


def test_run_outputs_bit_identical_old_vs_new():
    spec = dict(name="x", master_seed=530, method="fedqpnt_local", duration_s=120.0, imu_grade="tactical",
                world="schuler_tangent", quantum_grade="field", attack=ATK[0], attacks=list(ATK[:30]))
    new = run_single(RunSpec(**spec))
    orig = NodeEnvironment._label
    NodeEnvironment._label = NodeEnvironment._label_reference
    try:
        old = run_single(RunSpec(**spec))
    finally:
        NodeEnvironment._label = orig
    new.pop("wall_s"), old.pop("wall_s")
    assert new.keys() == old.keys()
    for k in new:
        a, b = new[k], old[k]
        if isinstance(a, float) and np.isnan(a):
            assert np.isnan(b), k
        else:
            assert a == b, k
