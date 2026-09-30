"""D-072 trust split: w_pos (ESKF GNSS update, shadow probe, reacquisition) and w_clk (ClockKF) are driven by
separate evidence; alias weights["gnss"] = min(w_pos, w_clk)."""
from __future__ import annotations

import numpy as np

from fedqpnt.core.types import GnssFix, TrustState
from fedqpnt.eval import metrics as M
from fedqpnt.trust.trust_law import TrustEngineImpl, make_method_config


def _fix(t, bias=0.0, drift=0.0):
    return GnssFix(t=t, pos=np.zeros(3), vel=np.zeros(3), clk_bias=bias, clk_drift=drift, cov_pos=np.eye(3),
                   cov_vel=np.eye(3), residual_rms=0.5, num_sats=8, mean_cn0=45.0, std_cn0=1.0, agc_db=0.0,
                   valid=True, raim_stat=1.0, pdop=2.0)


def _run_clock_step(steps=60):
    """A persistent 750 m clock-bias step from t=20 on, position perfectly clean (meaconing-like)."""
    eng = TrustEngineImpl(make_method_config("fedqpnt"))
    # Isolate the EVIDENCE routing: the (untrained) detector p drives BOTH weights by design (D-072), so it is
    # held at 0 here. NOTE: a TRAINED detector that itself flags the clock step (it did on meaconing: raw_p 0.98-0.999)
    # depresses w_pos as well; the effectiveness of the split against meaconing is an empirical question for the
    # combined re-verification, not for this routing unit test.
    eng._gnss_p = lambda raw: 0.0
    st = None
    for k in range(1, steps):
        bias = 0.0 if k < 20 else 750.0
        st = eng.update(float(k), _fix(float(k), bias), None, None, None, [])
    return st, eng


def test_weights_schema_and_alias():
    st, _ = _run_clock_step(5)
    w = st.weights
    assert {"gnss", "gnss_pos", "gnss_clk"} <= set(w)
    assert w["gnss"] == min(w["gnss_pos"], w["gnss_clk"])


def test_clock_only_anomaly_depresses_w_clk_not_w_pos():
    eng = TrustEngineImpl(make_method_config("fedqpnt"))
    eng._gnss_p = lambda raw: 0.0      # isolate evidence routing (see _run_clock_step)
    w_pos, w_clk = [], []
    for k in range(1, 40):
        st = eng.update(float(k), _fix(float(k), 0.0 if k < 20 else 750.0), None, None, None, [])
        if k >= 20:
            w_pos.append(st.weights["gnss_pos"])
            w_clk.append(st.weights["gnss_clk"])
    assert min(w_clk) < 0.5, min(w_clk)          # clk_event (x8=250 sigma) depresses the clock weight
    assert min(w_pos) > 0.9, min(w_pos)          # ... and costs the position weight nothing


def test_eskf_uses_w_pos_and_clock_uses_w_clk():
    from fedqpnt.fusion import ESKF
    from fedqpnt.sensors.imu import ClassicalImu
    kf = ESKF(ClassicalImu(grade="industrial_mems", rng=np.random.default_rng(0)).config())
    kf.initialize_static(0.0, np.zeros(3), np.zeros(3))
    fix = GnssFix(t=0.0, pos=np.array([2.0, 0.0, 0.0]), vel=np.zeros(3), clk_bias=0.0, clk_drift=0.0,
                  cov_pos=np.diag([9.0, 9.0, 25.0]), cov_vel=np.diag([0.01] * 3), residual_rms=0.0, num_sats=6,
                  mean_cn0=45.0, std_cn0=1.0, agc_db=0.0, valid=True, raim_stat=0.0)
    innov = kf.innovations(0.0, fix, None)
    # clock distrusted (w_clk tiny) but position trusted: the position update must still apply
    tr = TrustState(t=0.0, weights={"gnss": 0.02, "gnss_pos": 1.0, "gnss_clk": 0.02, "imu": 1.0, "quantum": 1.0},
                    anomaly_scores={}, attack_detected=True)
    kf.correct(0.0, innov, tr)
    assert kf.p[0] > 0.0


def test_mean_w_report_attack_window_and_whole_mission():
    t = np.arange(10.0)
    active = np.array([0, 0, 0, 1, 1, 1, 1, 0, 0, 0], dtype=bool)
    ph = M.compute_phases(t, active, t_align=0.0)
    w_pos = np.ones(10)
    w_clk = np.where(active, 0.02, 1.0)
    rep = M.mean_w_report(np.minimum(w_pos, w_clk), w_pos, w_clk, ph)
    assert rep["mean_w_pos"] == 1.0 and rep["mean_w_pos_att"] == 1.0
    assert abs(rep["mean_w_clk"] - (6 + 4 * 0.02) / 10) < 1e-12
    assert abs(rep["mean_w_clk_att"] - 0.02) < 1e-12
    assert rep["mean_w_gnss_att"] == rep["mean_w_clk_att"]
