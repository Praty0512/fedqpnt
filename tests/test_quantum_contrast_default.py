"""D-082: QuantumTrust contrast normalisation single-sourced from the configured CAI grade preset.

Bug (S6-coast diagnosis): c_nom was hard-coded to 1.0 while the FIELD CAI's nominal contrast is JARLAUD_C0=0.394, so
p_q = 1 - (0.394-0.1)/0.9 = 0.673 > theta_on on every healthy epoch and w_q sat at w_min (CAI update skipped)."""
import numpy as np

from fedqpnt.core.types import TruthState
from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import default_quantum_contrast_range, make_agent_config
from fedqpnt.sensors.quantum import GRADES, JARLAUD_C0, QuantumAccelerometer
from fedqpnt.core.seeding import stream
from fedqpnt.trust.trust_law import QuantumTrust

G = 9.80665


def test_preset_range_is_single_sourced():
    for g in GRADES:
        c_min, c_nom = default_quantum_contrast_range(g)
        ax = GRADES[g]().axis
        assert c_nom == ax.contrast0 and c_min == ax.contrast_threshold and 0.0 < c_min < c_nom <= 1.0
    assert default_quantum_contrast_range("field")[1] == JARLAUD_C0
    assert default_quantum_contrast_range(None) is None


def test_make_agent_config_applies_preset_and_legacy_default_without_grade():
    cfg = make_agent_config("fedqpnt_local", quantum_grade="field")
    assert cfg.trust.quantum_contrast_nom == JARLAUD_C0
    assert cfg.trust.quantum_contrast_min == GRADES["field"]().axis.contrast_threshold
    legacy = make_agent_config("fedqpnt_local")
    assert (legacy.trust.quantum_contrast_min, legacy.trust.quantum_contrast_nom) == (0.1, 1.0)


def _drive(omega, seconds, grade="field", seed=901):
    rng = stream(seed, "qtrust_test", "quantum")
    q = QuantumAccelerometer(grade=grade, rng=rng, outlier_channel=False, pointing="rigid")
    c_min, c_nom = default_quantum_contrast_range(grade)
    qt = QuantumTrust(cycle_time_s=q._cfg.axis.cycle_time_s, c_min=c_min, c_nom=c_nom)
    w, dt = [], 0.01
    for k in range(int(seconds / dt)):
        t = k * dt
        truth = TruthState(t=t, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3), att=np.zeros(3),
                           omega_b=np.array(omega, dtype=float), f_b=np.array([0.0, 0.0, G]))
        s = q.step(truth, rng)
        if s is not None:
            w.append(qt.step(t, s, gnss_w=1.0, quantum_innovation=None))
    return np.array(w)


def test_healthy_field_cai_keeps_wq_high_over_600s():
    w = _drive([0.0, 0.0, 0.0], 600.0)
    assert w.min() > 0.9, f"healthy FIELD CAI w_q dropped to {w.min():.3f}"


def test_contrast_collapse_still_lowers_wq():
    w = _drive([1.0, 1.0, 0.0], 120.0)
    assert w[-1] < 0.5, f"w_q did not drop under contrast collapse (final {w[-1]:.3f})"


def test_quantum_rq_includes_imu_sf_mis_aliasing():
    """D-083: the CAI measurement variance R_q (visible in S_q = P_ba + R_q) includes the IMU scale-factor /
    misalignment aliasing term sigma_sf*|f_i| (z axis ~ g at rest), from the IMU config -- not a tuning constant."""
    from fedqpnt.core.types import Innovation  # noqa: F401
    from fedqpnt.fusion.eskf import ESKF
    import fedqpnt.fusion.eskf as E
    env = NodeEnvironment(EnvConfig(platform="ground", world="flat", imu_grade="tactical", quantum_grade="field",
                                    gnss_rate_hz=1.0, hold_s=10.0, heading_noise_deg=2.0, attacks=[]),
                          seed=530, node_id="n", dt=0.01, duration_s=40.0)
    agent = Agent(make_agent_config("fedqpnt_local", world="flat", imu_grade="tactical", quantum_grade="field"),
                  env.imu.config(), node_id="n")
    es, fb, init, seen = agent.eskf, [], False, []
    orig = es.innovations
    def inn(t, fix, q):
        out = orig(t, fix, q)
        for iv in out:
            if iv.sensor == "quantum":
                var_q = q.variance
                base = var_q + es.vrw ** 2 / q.cycle_time + (es.cfg.sigma_win_g * 9.80665) ** 2
                seen.append(np.diag(iv.S) - np.diag(es.P[9:12, 9:12]) - base)
        return out
    es.innovations = inn
    for k in range(len(env)):
        tick = env.tick(k)
        if not init:
            if tick.t < env.hold_s:
                if tick.imu is not None:
                    fb.append(tick.imu.f_b)
                continue
            fm = np.mean(fb, axis=0)
            agent.initialize_static(tick.t, tick.truth.pos.copy(),
                                    np.array([np.arctan2(fm[1], fm[2]), np.arctan2(-fm[0], np.hypot(fm[1], fm[2])), 0.0]))
            init = True
            continue
        agent.step(tick.t, tick.imu, tick.quantum, tick.gnss_epoch)
    assert seen
    extra = np.mean(seen, axis=0)
    sig_sf = es.sigma_sf_a
    assert sig_sf > 0
    # z axis carries ~1 g: (sigma_sf * g)^2 dominates; x,y get the cross-axis misalignment term
    assert extra[2] > 0.5 * (sig_sf * 9.80665) ** 2, extra
    assert np.all(extra > 0.0)
