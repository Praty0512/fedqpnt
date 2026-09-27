"""Validation tests for fedqpnt.sensors.quantum (WP-2.1), real runtime, no mocks."""
from __future__ import annotations

import pathlib
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pytest

from fedqpnt.core.seeding import stream
from fedqpnt.core.types import TruthState
from fedqpnt.sensors.allan import fit_white_and_bias_instability, overlapping_adev
from fedqpnt.sensors.quantum import GRADES, QuantumAccelerometer, fit_params_from_adev

RESULTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "results" / "sensors"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

G = 9.80665


def _run_static(grade: str, duration_s: float, seed: int = 42, **kwargs):
    rng = stream(seed, "test_node", "quantum")
    q = QuantumAccelerometer(grade=grade, rng=rng, **kwargs)
    dt = 0.01  # global base tick, D-003
    n_ticks = int(round(duration_s / dt))
    f_b_true = np.array([0.0, 0.0, G])
    omega_true = np.zeros(3)
    samples = []
    t0 = time.time()
    for k in range(n_ticks):
        truth = TruthState(
            t=k * dt, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
            att=np.zeros(3), omega_b=omega_true, f_b=f_b_true,
        )
        s = q.step(truth, rng)
        if s is not None:
            samples.append(s)
    elapsed = time.time() - t0
    return q, samples, elapsed


@pytest.mark.parametrize("grade", list(GRADES.keys()))
def test_quantum_static_adev_matches_cited_params(grade):
    duration_s = 3600.0  # 1 simulated hour
    # outlier_channel=False: this test validates the CLEAN shot-noise/bias
    # model against the cited "robust" (outlier-excluded) sigma figures.
    # The Gilbert-Elliott outlier channel is validated separately in
    # test_quantum_outlier_channel_reproduces_measured_statistics (its
    # heavy-tailed bursts would otherwise dominate the ADEV/white-noise fit).
    q, samples, elapsed = _run_static(grade, duration_s, outlier_channel=False)
    rate_per_sim_hour = elapsed / (duration_s / 3600.0)
    print(f"[Quantum {grade}] runtime per sim-hour: {rate_per_sim_hour:.2f} s, "
          f"n_cycles={len(samples)}")
    assert rate_per_sim_hour < 300.0
    assert all(s.valid for s in samples)  # static, low rotation -> always valid

    x = np.array([s.f_b[0] for s in samples])  # sensed axis, zero true mean
    cycle_time = q.cycle_time
    taus, adev, nclusters = overlapping_adev(x, cycle_time)
    fit = fit_white_and_bias_instability(taus, adev, nclusters)

    cited_sens = q.config()["params"]["sensitivity_m_s2_per_sqrt_hz"]
    cited_bias = q.config()["params"]["bias_instability_m_s2"]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.loglog(taus, adev, label="simulated ADEV")
    ax.loglog(taus, cited_sens / np.sqrt(taus), "--", label=f"cited sensitivity {cited_sens:.2g}/sqrt(tau)")
    ax.axhline(cited_bias, color="r", ls=":", label=f"cited bias instability {cited_bias:.2g}")
    ax.scatter([1.0], [cited_sens], color="k", zorder=5, label="cited @ tau=1s")
    ax.set_xlabel("tau [s]")
    ax.set_ylabel("Allan deviation [m/s^2]")
    ax.set_title(f"Quantum accelerometer ({grade})")
    ax.legend(fontsize=7)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / f"adev_quantum_{grade}.png", dpi=120)
    plt.close(fig)

    rel_err_sens = abs(fit["N_white"] - cited_sens) / cited_sens
    assert rel_err_sens < 0.30, f"{grade} white-noise sensitivity off by {rel_err_sens:.1%}"
    # NOTE: for every cited grade here, white-noise sensitivity >> bias
    # floor (e.g. lab: 2e-3 vs 7e-7 m/s^2, a ~2900x gap), so the ADEV curve
    # would only dip to the bias floor after ~(sensitivity/bias)^2 seconds
    # of continuous static operation (tens to hundreds of days) -- not
    # reachable in test time. The bias-instability (GM1) tuning is instead
    # validated in isolation below (test_quantum_bias_gm_process_isolated),
    # which reproduces exactly the same theta/sigma_gm construction used
    # inside QuantumAccelerometer.step but without the dominant shot noise.


@pytest.mark.parametrize("grade", list(GRADES.keys()))
def test_quantum_bias_gm_process_isolated(grade):
    """Validates the GM1 bias-instability tuning (shared with the IMU model,
    El-Sheimy/Hou/Niu 2008) in isolation from the (much larger) shot noise,
    since the two cannot both be resolved from one finite-length ADEV curve
    (see note in test_quantum_static_adev_matches_cited_params)."""
    rng = stream(99, "iso", "quantum_bias")
    q = QuantumAccelerometer(grade=grade, rng=rng)
    cited_bias = q.config()["params"]["bias_instability_m_s2"]
    if cited_bias <= 0:
        pytest.skip("no bias-instability figure for this grade")
    tau_c = q.config()["params"]["bias_tau_c_s"]
    dt = q.cycle_time
    n = int(max(20000, 400 * tau_c / dt))  # plenty of cycles either side of tau_c

    theta = q._theta_bias
    driving_std = q._driving_std
    b = q._sigma_gm * rng.standard_normal() if q._sigma_gm > 0 else 0.0
    series = np.empty(n)
    for k in range(n):
        b = theta * b + driving_std * rng.standard_normal()
        series[k] = b

    taus, adev, nclusters = overlapping_adev(series, dt)
    fit = fit_white_and_bias_instability(taus, adev, nclusters)
    b_floor = fit["B_bias_instability"]
    rel_err = abs(b_floor - cited_bias) / cited_bias
    assert rel_err < 0.30, f"{grade} isolated bias-instability floor off by {rel_err:.1%}"


def test_quantum_cycle_based_sampling_and_dead_time():
    q, samples, _ = _run_static("lab", duration_s=20.0)
    dt = 0.01
    expected_n = int(round(20.0 / q.cycle_time))
    assert abs(len(samples) - expected_n) <= 1
    ts = np.array([s.t for s in samples])
    diffs = np.diff(ts)
    np.testing.assert_allclose(diffs, q.cycle_time, atol=1.5 * dt)
    for s in samples:
        assert s.cycle_time == q.cycle_time


def test_quantum_rotation_contrast_loss_marks_invalid():
    rng = stream(3, "n", "quantum")
    q = QuantumAccelerometer(grade="lab", rng=rng)
    dt = 0.01
    big_omega = np.array([0.0, 3.0, 0.0])  # >> lab omega_c_rad_s (~0.434 rad/s, D-020), perpendicular to axis 0 & 2
    f_b_true = np.array([0.0, 0.0, G])
    n_ticks = int(round(q.cycle_time / dt)) + 2
    s = None
    for k in range(n_ticks):
        truth = TruthState(t=k * dt, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                            att=np.zeros(3), omega_b=big_omega, f_b=f_b_true)
        out = q.step(truth, rng)
        if out is not None:
            s = out
    assert s is not None
    assert s.contrast < q.config()["params"]["contrast0"]
    assert s.valid is False


def test_quantum_hybridization_keeps_output_continuous_across_fringes():
    """Large accelerations spanning several fringe periods must still be
    tracked continuously thanks to the classical-accelerometer hybridization
    (Lautier 2014 / Cheiney 2018), not wrapped/aliased to the wrong fringe."""
    rng = stream(5, "n", "quantum")
    q = QuantumAccelerometer(grade="lab", rng=rng)
    dt = 0.01
    fp = q.fringe_period_m_s2
    assert fp < 5.0  # sanity: several g of dynamic range needed to span multiple fringes in this test

    # a_true steps through several multiples of the fringe period across cycles
    accels = [0.0, 2.5 * fp, -1.5 * fp, 4.0 * fp, 0.5 * fp]
    accels = [min(max(a, -0.4 * G), 0.4 * G) for a in accels]  # stay within dynamic range
    dyn_range = q.config()["params"]["dynamic_range_m_s2"]
    accels = [np.clip(a, -0.9 * dyn_range, 0.9 * dyn_range) for a in accels]

    outputs = []
    t = 0.0
    for a in accels:
        f_b_true = np.array([a, 0.0, G])
        n_ticks = int(round(q.cycle_time / dt)) + 1
        for k in range(n_ticks):
            truth = TruthState(t=t, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                                att=np.zeros(3), omega_b=np.zeros(3), f_b=f_b_true)
            out = q.step(truth, rng)
            t += dt
            if out is not None:
                outputs.append((a, out))

    assert len(outputs) >= len(accels) - 1
    # the hybridized estimate must track the true acceleration to within a
    # small multiple of the sensor noise, NOT off by an integer number of
    # fringe periods (the failure mode hybridization is meant to prevent).
    noise_budget = 10.0 * q.config()["params"]["sensitivity_m_s2_per_sqrt_hz"] * np.sqrt(q.rate_hz)
    for a_true, out in outputs:
        assert out.valid
        err = abs(out.f_b[0] - a_true)
        assert err < max(noise_budget, 0.05 * fp), (
            f"hybridized output {out.f_b[0]} deviates from truth {a_true} by {err}, "
            f"suggesting an unresolved fringe ambiguity (fringe period={fp})"
        )


def test_quantum_dynamic_range_invalid():
    rng = stream(9, "n", "quantum")
    q = QuantumAccelerometer(grade="lab", rng=rng)
    dt = 0.01
    dyn_range = q.config()["params"]["dynamic_range_m_s2"]
    f_b_true = np.array([2.0 * dyn_range, 0.0, G])
    n_ticks = int(round(q.cycle_time / dt)) + 1
    s = None
    for k in range(n_ticks):
        truth = TruthState(t=k * dt, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                            att=np.zeros(3), omega_b=np.zeros(3), f_b=f_b_true)
        out = q.step(truth, rng)
        if out is not None:
            s = out
    assert s is not None
    assert s.valid is False


def test_quantum_determinism_same_seed():
    dt = 0.01
    f_b_true = np.array([0.3, -0.1, G])
    omega_true = np.array([1e-4, -2e-4, 1e-4])

    def run():
        rng = stream(11, "nodeB", "quantum")
        q = QuantumAccelerometer(grade="lab", rng=rng)
        out = []
        for k in range(500):
            truth = TruthState(t=k * dt, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                                att=np.zeros(3), omega_b=omega_true, f_b=f_b_true)
            s = q.step(truth, rng)
            if s is not None:
                out.append(s.f_b.copy())
        return out

    r1, r2 = run(), run()
    assert len(r1) == len(r2) and len(r1) > 0
    for a, b in zip(r1, r2):
        np.testing.assert_array_equal(a, b)


def test_quantum_1axis_reports_nan_on_unsensed_axes():
    rng = stream(13, "n", "quantum")
    q = QuantumAccelerometer(grade="lab", axes=(2,), rng=rng)
    dt = 0.01
    f_b_true = np.array([0.0, 0.0, G])
    n_ticks = int(round(q.cycle_time / dt)) + 1
    s = None
    for k in range(n_ticks):
        truth = TruthState(t=k * dt, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                            att=np.zeros(3), omega_b=np.zeros(3), f_b=f_b_true)
        out = q.step(truth, rng)
        if out is not None:
            s = out
    assert s is not None
    assert np.isnan(s.f_b[0]) and np.isnan(s.f_b[1])
    assert not np.isnan(s.f_b[2])


def test_quantum_replay_noise_source_matches_supplied_statistics():
    """Synthetic residual array (as a stand-in for a real measured dataset,
    per the coordinator's request): the replay-mode output noise should
    reflect the supplied residual statistics via block bootstrap."""
    rng_data = np.random.default_rng(123)
    true_std = 4e-3
    residuals = rng_data.normal(0.0, true_std, size=20000)
    sample_rate_hz = 50.0

    rng = stream(21, "n", "quantum")
    q = QuantumAccelerometer(
        grade="lab", rng=rng, noise_source="replay",
        replay_residuals=residuals, replay_sample_rate_hz=sample_rate_hz,
        replay_block_length=25,
    )
    assert q.noise_source_kind == "replay"

    dt = 0.01
    f_b_true = np.array([0.0, 0.0, G])
    n_cycles = 400
    n_ticks = int(round(q.cycle_time / dt))
    out_x = []
    t = 0.0
    for _ in range(n_cycles):
        for k in range(n_ticks):
            truth = TruthState(t=t, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                                att=np.zeros(3), omega_b=np.zeros(3), f_b=f_b_true)
            out = q.step(truth, rng)
            t += dt
            if out is not None:
                out_x.append(out.f_b[0])
    out_x = np.array(out_x)
    # loose sanity bound: replayed noise should be same order of magnitude
    # as the supplied residual std (bias GM + hybridization add some spread).
    assert 0.2 * true_std < np.std(out_x) < 5.0 * true_std


def test_quantum_replay_accepts_per_shot_residuals_at_cycle_rate():
    """Master D-014 item 3: replay must accept per-shot residuals already AT
    the sensor's cycle rate (not only a continuous higher-rate stream to be
    decimated). Uses a synthetic per-shot array pending the real extracted
    atom_shot_residuals.npz (per Master: "don't block on item 3")."""
    rng_data = np.random.default_rng(77)
    per_shot_std = 2e-4
    field_cfg = GRADES["field"]().axis
    cycle_rate_hz = 1.0 / field_cfg.cycle_time_s  # 0.646 Hz, Jarlaud et al. 2024 measured rate
    n_shots = 3000
    per_shot_residuals = rng_data.normal(0.0, per_shot_std, size=n_shots)

    rng = stream(31, "n", "quantum")
    q = QuantumAccelerometer(
        grade="field", rng=rng, noise_source="replay",
        replay_residuals=per_shot_residuals, replay_sample_rate_hz=cycle_rate_hz,
        replay_block_length=10,
    )
    dt = 0.01
    f_b_true = np.array([0.0, 0.0, G])
    n_ticks = int(round(q.cycle_time / dt)) * 50
    out_x = []
    for k in range(n_ticks):
        truth = TruthState(t=k * dt, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                            att=np.zeros(3), omega_b=np.zeros(3), f_b=f_b_true)
        out = q.step(truth, rng)
        if out is not None:
            out_x.append(out.f_b[0])
    assert len(out_x) >= 40
    assert 0.2 * per_shot_std < np.std(np.array(out_x)) < 5.0 * per_shot_std


def test_quantum_inertial_pointing_tolerates_higher_rotation():
    """Master D-014 item 1: inertial-pointing mode (NEAR_FUTURE) must
    tolerate much higher rotation rates than rigid-mode before losing
    validity; a rigid-mode sensor at the same rotation rate must NOT be
    suppressed into validity (the consequence -- a rigid-mode sensor
    dropping out under realistic vehicle turn rates -- must be visible)."""
    omega_ground_vehicle = np.array([0.0, 0.15, 0.0])  # ~0.15 rad/s (8.6 deg/s) turn rate, perpendicular to sensed axis: beyond rigid-mode's tolerance but within the paper's 250 mrad/s inertial-pointing envelope
    dt = 0.01
    f_b_true = np.array([0.0, 0.0, G])

    rng_rigid = stream(41, "n", "quantum")
    q_rigid = QuantumAccelerometer(grade="near_future", rng=rng_rigid, pointing="rigid")
    rng_inertial = stream(42, "n", "quantum")
    q_inertial = QuantumAccelerometer(grade="near_future", rng=rng_inertial, pointing="inertial")

    def run(q, rng):
        n_ticks = int(round(q.cycle_time / dt)) + 2
        s = None
        for k in range(n_ticks):
            truth = TruthState(t=k * dt, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                                att=np.zeros(3), omega_b=omega_ground_vehicle, f_b=f_b_true)
            out = q.step(truth, rng)
            if out is not None:
                s = out
        return s

    s_rigid = run(q_rigid, rng_rigid)
    s_inertial = run(q_inertial, rng_inertial)
    assert s_rigid.valid is False, "rigid-mode sensor must NOT be suppressed: a ~0.3 rad/s turn should break lock (Master D-014)"
    assert s_inertial.valid is True


def test_quantum_replay_with_real_jarlaud_atom_residuals():
    """Integration check with the real extracted per-shot atom residuals
    (Master D-014 item 3, now available), if present on disk."""
    path = pathlib.Path(__file__).resolve().parents[1] / "data" / "processed" / "jarlaud2024" / "atom_shot_residuals.npz"
    if not path.exists():
        pytest.skip("data/processed/jarlaud2024/atom_shot_residuals.npz not present")
    data = np.load(path, allow_pickle=True)
    residuals = data["residual_mps2"]
    cycle_rate_hz = 1.0 / float(np.median(data["cycle_s"]))

    rng = stream(61, "n", "quantum")
    q = QuantumAccelerometer(
        grade="field", rng=rng, noise_source="replay",
        replay_residuals=residuals, replay_sample_rate_hz=cycle_rate_hz,
        replay_block_length=10,
    )
    dt = 0.01
    f_b_true = np.array([0.0, 0.0, G])
    n_ticks = int(round(q.cycle_time / dt)) * 60
    out_x = []
    for k in range(n_ticks):
        truth = TruthState(t=k * dt, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                            att=np.zeros(3), omega_b=np.zeros(3), f_b=f_b_true)
        out = q.step(truth, rng)
        if out is not None:
            out_x.append(out.f_b[0])
    real_std = float(np.std(residuals))
    assert len(out_x) >= 30
    assert 0.2 * real_std < np.std(np.array(out_x)) < 5.0 * real_std


def test_quantum_field_sigma_shot_matches_measured_within_15pct():
    """Master D-019 item 4: in model mode, the robust sigma at 2T=20ms is
    within +-15% of 5.60 ug (i.e. the FIELD grade's configured sensitivity,
    which is set directly from the measured table -- this is a
    self-consistency check that the sensitivity->per-cycle-noise conversion
    used inside the sensor reproduces that same number from simulated data)."""
    from fedqpnt.sensors.quantum import JARLAUD_SIGMA_SHOT_UG_BY_TWO_T
    q, samples, _ = _run_static("field", duration_s=3600.0, outlier_channel=False)
    x = np.array([s.f_b[0] for s in samples])
    sigma_shot_ug = np.std(x) / (9.80665 * 1e-6)
    cited_ug = JARLAUD_SIGMA_SHOT_UG_BY_TWO_T[0.020]
    rel_err = abs(sigma_shot_ug - cited_ug) / cited_ug
    assert rel_err < 0.15, f"field grade sigma_shot {sigma_shot_ug:.2f} ug vs measured {cited_ug:.2f} ug, off by {rel_err:.1%}"


def test_quantum_field_sigma_shot_replay_mode_matches_measured_within_15pct():
    """Same check as above, but noise_source='replay' using the real
    per-shot atom residuals filtered to 2T=20ms & clean=True (Master D-019
    item 3), if the data file is present."""
    from fedqpnt.sensors.quantum import JARLAUD_CYCLE_TIME_S, JARLAUD_SIGMA_SHOT_UG_BY_TWO_T
    path = pathlib.Path(__file__).resolve().parents[1] / "data" / "processed" / "jarlaud2024" / "atom_shot_residuals.npz"
    if not path.exists():
        pytest.skip("data/processed/jarlaud2024/atom_shot_residuals.npz not present")
    data = np.load(path, allow_pickle=True)
    # D-020: the per-row "cycle_s" field is the PER-K-DIRECTION interval
    # (e.g. ~2.955-3.09s), not the combined per-shot rate; feeding that in
    # here would force _ReplayNoiseSource to resample (since it would then
    # differ from the sensor's own rate_hz=1/1.548s), and the interpolation
    # this triggers measurably biases the reproduced sigma low (~23% in an
    # earlier run of this test). Use the same JARLAUD_CYCLE_TIME_S the field
    # grade itself uses, so sample_rate_hz == q.rate_hz and no resampling
    # (and its variance bias) occurs.
    cycle_rate_hz = 1.0 / JARLAUD_CYCLE_TIME_S

    rng = stream(81, "n", "quantum")
    q = QuantumAccelerometer(
        grade="field", rng=rng, noise_source="replay", outlier_channel=False,
        replay_residuals=data["residual_mps2"], replay_sample_rate_hz=cycle_rate_hz,
        replay_two_T_s=data["two_T_s"], replay_clean=data["clean"],
        replay_block_length=10,
    )
    dt = 0.01
    f_b_true = np.array([0.0, 0.0, G])
    n_ticks = int(round(q.cycle_time / dt)) * 300
    out_x = []
    for k in range(n_ticks):
        truth = TruthState(t=k * dt, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                            att=np.zeros(3), omega_b=np.zeros(3), f_b=f_b_true)
        out = q.step(truth, rng)
        if out is not None:
            out_x.append(out.f_b[0])
    assert len(out_x) >= 30
    sigma_shot_ug = np.std(np.array(out_x)) / (9.80665 * 1e-6)
    cited_ug = JARLAUD_SIGMA_SHOT_UG_BY_TWO_T[0.020]
    rel_err = abs(sigma_shot_ug - cited_ug) / cited_ug
    assert rel_err < 0.15, f"field grade replay sigma_shot {sigma_shot_ug:.2f} ug vs measured {cited_ug:.2f} ug, off by {rel_err:.1%}"


def test_quantum_outlier_channel_reproduces_measured_statistics():
    """Master D-019 item 2 & 4: over >=20,000 shots, the Gilbert-Elliott
    outlier channel reproduces a stationary bad-state rate of 9% +-2% and
    burst persistence P(bad|prev bad) of 66% +-10%."""
    rng = stream(91, "n", "quantum")
    q = QuantumAccelerometer(grade="field", rng=rng, outlier_channel=True)
    dt = 0.01
    f_b_true = np.array([0.0, 0.0, G])
    n_shots = 22000
    n_ticks = int(round(q.cycle_time / dt))
    states = []
    t = 0.0
    for _ in range(n_shots):
        for k in range(n_ticks):
            truth = TruthState(t=t, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                                att=np.zeros(3), omega_b=np.zeros(3), f_b=f_b_true)
            q.step(truth, rng)
            t += dt
        states.append(bool(q._ge_state_bad[0]))
    states = np.array(states)
    stationary_rate = states.mean()
    prev_bad = states[:-1]
    curr = states[1:]
    persistence = curr[prev_bad].mean() if prev_bad.any() else 0.0

    assert abs(stationary_rate - 0.09) < 0.02, f"stationary outlier rate {stationary_rate:.3f} not within 9%+-2%"
    assert abs(persistence - 0.66) < 0.10, f"burst persistence {persistence:.3f} not within 66%+-10%"


def test_quantum_field_grade_ground_vehicle_turn_breaks_rigid_lock():
    """Master D-014: 'a ground vehicle turning at ~0.3 rad/s drives the
    rigid-mode sensor to valid=False. This is realistic and important, so
    do not suppress it.' Explicit regression test for that exact claim,
    field grade (measured Jarlaud et al. 2024 rigid-mode Omega_c=48.2 mrad/s)."""
    rng = stream(51, "n", "quantum")
    q = QuantumAccelerometer(grade="field", rng=rng, pointing="rigid")
    dt = 0.01
    omega_turn = np.array([0.0, 0.3, 0.0])
    f_b_true = np.array([0.0, 0.0, G])
    n_ticks = int(round(q.cycle_time / dt)) + 2
    s = None
    for k in range(n_ticks):
        truth = TruthState(t=k * dt, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3),
                            att=np.zeros(3), omega_b=omega_turn, f_b=f_b_true)
        out = q.step(truth, rng)
        if out is not None:
            s = out
    assert s is not None
    assert s.valid is False


def test_fit_params_from_adev_recovers_known_white_and_bias():
    n_white_true = 3e-3
    b_true = 8e-7
    taus = np.geomspace(0.5, 2000.0, 40)
    adev_synth = np.sqrt((n_white_true / np.sqrt(taus)) ** 2 + b_true ** 2)
    fit = fit_params_from_adev(taus, adev_synth)
    assert abs(fit["sensitivity_m_s2_per_sqrt_hz"] - n_white_true) / n_white_true < 0.35
    assert fit["bias_instability_m_s2"] > 0
