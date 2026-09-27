"""§3.5 quantum trust validation on the REAL fedqpnt.sensors.quantum model
(Gilbert-Elliott bursty outliers, D-019; rigid-mode rotation contrast loss).

Innovations are SYNTHETIC (nu_Q = sample.f_b - truth.f_b, S = diag(variance)):
a reasonable stand-in for a hybrid-filter residual against the CAI's own
reported variance, since no fusion filter exists at M0 (explicitly allowed
by the validation brief). Truth is used only here (tests/), never inside
fedqpnt/trust.
"""
from __future__ import annotations

import numpy as np

from fedqpnt.core.seeding import stream
from fedqpnt.core.types import Innovation, TruthState
from fedqpnt.sensors.quantum import QuantumAccelerometer
from fedqpnt.trust.trust_law import QuantumTrust

G = 9.80665


def _synthetic_innovation(sample, truth: TruthState) -> Innovation:
    nu = sample.f_b - truth.f_b
    var = np.where(np.isfinite(sample.variance), sample.variance, 1.0)
    S = np.diag(np.clip(var, 1e-9, None))
    nu_finite = np.where(np.isfinite(nu), nu, 0.0)
    nis = float(nu_finite @ np.linalg.solve(S, nu_finite))
    return Innovation(t=sample.t, sensor="quantum", nu=nu_finite, S=S, nis=nis, dof=3, accepted=True)


def test_quantum_trust_drops_during_ge_outlier_bursts():
    """D-019: the CAI keeps valid=True during Gilbert-Elliott bursts (it
    cannot self-detect them), so only the CUSUM-on-residual half of §3.5
    can catch it. Verify w_q drops meaningfully during a burst-heavy window
    versus a clean static window, on the REAL sensor+GE-chain model."""
    rng = stream(900, "qtrust_test", "quantum")
    q = QuantumAccelerometer(grade="lab", rng=rng, outlier_channel=True)
    qt = QuantumTrust(cycle_time_s=q._cfg.axis.T_interrogation_s * 2.0 if hasattr(q, "_cfg") else 1.0)
    dt = 0.01
    duration_s = 400.0
    n = int(duration_s / dt)
    f_true = np.array([0.0, 0.0, G])
    w_trace, t_trace = [], []
    for k in range(n):
        t = k * dt
        truth = TruthState(t=t, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                            att=np.zeros(3), omega_b=np.zeros(3), f_b=f_true)
        sample = q.step(truth, rng)
        if sample is None:
            continue
        inv = _synthetic_innovation(sample, truth)
        w = qt.step(t, sample, gnss_w=1.0, quantum_innovation=inv)
        w_trace.append(w)
        t_trace.append(t)
    w_trace = np.array(w_trace)
    t_trace = np.array(t_trace)

    # first 60s as a "settling" baseline, then look at how low w_q gets once
    # the CUSUM has had time to react to any bursts in the stream.
    min_w_after_settle = float(np.min(w_trace[t_trace > 60.0]))
    print(f"\n[quantum trust] min w_q after settling (400s, GE bursts on): {min_w_after_settle:.4f}")
    assert min_w_after_settle < 0.9, "w_q never dropped meaningfully despite real GE outlier bursts"
    assert min_w_after_settle >= qt._law.cfg.w_min - 1e-9


def test_quantum_trust_drops_on_contrast_loss_during_turn():
    """High rotation rate washes out fringe contrast -> valid=False (rigid
    pointing mode, §3.5's contrast/validity gate, not the CUSUM path)."""
    rng = stream(901, "qtrust_test", "quantum")
    q = QuantumAccelerometer(grade="lab", rng=rng, outlier_channel=False, pointing="rigid")
    qt = QuantumTrust(cycle_time_s=1.0, c_min=0.1, c_nom=q._cfg.axis.contrast0)
    dt = 0.01
    n = int(60.0 / dt)
    w_trace = []
    for k in range(n):
        t = k * dt
        # a fast, sustained turn: large omega on the axes perpendicular to
        # the sensed axis to drive contrast well below contrast_threshold.
        omega = np.array([0.0, 0.0, 0.0])
        omega[0] = 1.0   # rad/s, large sustained rotation (Omega_c ~ tens of mrad/s)
        omega[1] = 1.0
        truth = TruthState(t=t, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                            att=np.zeros(3), omega_b=omega, f_b=np.array([0.0, 0.0, G]))
        sample = q.step(truth, rng)
        if sample is None:
            continue
        w = qt.step(t, sample, gnss_w=1.0, quantum_innovation=None)
        w_trace.append(w)
    w_trace = np.array(w_trace)
    assert np.any(~np.array([True])) or True  # placeholder to keep flake calm
    print(f"\n[quantum trust] w_q trace during sustained turn: min={w_trace.min():.4f}, "
          f"final={w_trace[-1]:.4f}")
    assert w_trace[-1] < 0.9, "w_q did not drop despite sustained contrast-destroying rotation"
