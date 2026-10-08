"""Methods as config diffs over ONE code path (WP-8.1, ARCHITECTURE.md
section 5). All rows share the same ESKF (with the NIS gate) and the same
trust-law core (``fedqpnt.trust.trust_law``); only ``AgentConfig`` fields
differ. The FL part (server-trained detector, TRIM-NB-R aggregation) is
DEFERRED to M2 (out of scope for WP-8.1): "FedQPNT-local" here uses a
DETECTOR TRAINED LOCALLY on the tuning seeds (500-599) via
``pretrain_detector`` below and loaded from a weights file, standing in for
what the FL-trained detector will later provide. This is flagged explicitly
so nobody mistakes the M1 smoke numbers for the FL-integrated FedQPNT.

Method keys implemented (the M1 smoke-matrix subset):
  "fedqpnt_local"   -- continuous trust law, learned MLP detector (local),
                        CAI on.                                    (FedQPNT, M1 stand-in)
  "baseline_a"      -- memoryless detect-and-exclude (Baseline A).
  "baseline_b_bin"  -- detect_switch / hard exclude+recover (B-bin).
  "baseline_b_cont" -- continuous law, local-only detector (B-cont, == Abl -FL).
  "bprime"          -- continuous law, p from chi2_3(3*x1) rule, no learned detector (B').
  "fixed_trust"     -- w == 1 always, NIS gate ON (Abl fixed-trust / A0-style; also
                        the method the D-023/D-027 kappa_R tuning procedure uses).
  "undefended"      -- w == 1 always, NIS gate OFF (section 6.1 S1 acceptance-test
                        baseline: "fixed-trust w == 1 with the NIS gate off").
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from fedqpnt.core.seeding import stream
from fedqpnt.node.agent import AgentConfig
from fedqpnt.fusion.clock import ClockKFConfig
from fedqpnt.trust.trust_law import TrustEngineConfig, make_method_config

from fedqpnt.core.defaults import DEFAULT_KAPPA_R  # noqa: E402  (D-061/D-067: kappa_R = 60, single source)
# D-028: fedqpnt/fusion/eskf.py's process model is being changed concurrently
# (dynamics-dependent Q inflation for unmodelled IMU scale-factor/misalignment,
# another agent). That changes the propagated P this value was tuned against,
# so DEFAULT_KAPPA_R stays PROVISIONAL and MUST be re-chosen with the same
# procedure once D-028 lands -- see results/m1/kappa_r_frozen.json.

# D-066/D-067 pre-registered calibration of the shadow-probe / reacquisition acceptance bound. The
# chi2_6(0.99)=16.81 bound gave a clean false-veto of 3.3% (1/30 windows, seeds 500-509) at
# industrial_mems, above the pre-registered 1% limit, so the bound is replaced, per IMU grade, by the
# 99th percentile of the CLEAN mean shadow NIS over the first 10 s after a 60 s outage with no update
# applied, measured on disjoint tuning seeds 510-529 (n=60 windows/grade; results/m1/
# shadow_nis_calib_510_529.json, scripts/core_robust_shadow_nis_check.py) and FROZEN. Clean data only.
PROBE_NIS_BOUND_BY_GRADE = {"industrial_mems": 25.07, "tactical": 6.74}

# trust_law._METHOD_TABLE key + whether it needs a (locally-)trained detector.
_METHOD_TRUST_KEY = {
    "fedqpnt_local": "fedqpnt",
    "baseline_a": "baseline_a",
    "baseline_b_bin": "baseline_b_bin",
    "baseline_b_cont": "baseline_b_cont",
    "bprime": "bprime",
    "fixed_trust": "abl_fixed_trust",
    "undefended": "abl_fixed_trust",   # section 6.1 S1: fixed-trust w=1 with the NIS gate OFF
}
# "fixed_trust"/"undefended" don't use the detector's p for the trust WEIGHT
# (w == 1 regardless), but TrustEngineImpl still scores it every epoch to
# report attack_detected/anomaly_scores (section 6 FAR/latency bookkeeping),
# so an untrained random-init network would make those numbers meaningless
# noise -- load the same trained weights for them too.
_NEEDS_TRAINED_DETECTOR = {"fedqpnt_local", "baseline_a", "baseline_b_bin", "baseline_b_cont",
                           "fixed_trust", "undefended"}
METHOD_NAMES = tuple(_METHOD_TRUST_KEY)


def load_detector_weights(path: str | Path) -> dict[str, np.ndarray] | None:
    path = Path(path)
    if not path.exists():
        return None
    npz = np.load(path, allow_pickle=False)
    return {k: npz[k] for k in npz.files}


def save_detector_weights(path: str | Path, params: dict[str, np.ndarray]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, **{k: np.asarray(v) for k, v in params.items()})


def default_quantum_cycle_time_s(quantum_grade: str | None) -> float:
    """D-074: cycle time of the configured quantum sensor grade from the sensor preset (lab 1.0 s,
    field 1.548 s, near_future 0.1 s); 1.0 s when no grade is given (legacy default)."""
    if quantum_grade is None:
        return 1.0
    from fedqpnt.sensors.quantum import GRADES
    return float(GRADES[quantum_grade]().axis.cycle_time_s)


def default_quantum_contrast_range(quantum_grade: str | None) -> tuple[float, float] | None:
    """D-082: (c_min, c_nom) for the quantum trust from the configured CAI grade preset: c_nom = the grade's
    nominal contrast (axis.contrast0; FIELD = JARLAUD_C0 = 0.394), c_min = the sensor's own validity threshold
    (axis.contrast_threshold, below which the sample is flagged invalid). None when no grade is given."""
    if quantum_grade is None:
        return None
    from fedqpnt.sensors.quantum import GRADES
    ax = GRADES[quantum_grade]().axis
    return float(ax.contrast_threshold), float(ax.contrast0)


def make_agent_config(method: str, *, kappa_R: float = DEFAULT_KAPPA_R, kappa_Q: float = 1.0,
                       world: str = "flat", quantum_enabled: bool = True,
                       quantum_cycle_time_s: float | None = None,
                       detector_weights_path: str | Path | None = None,
                       imu_grade: str | None = None,
                       quantum_grade: str | None = None) -> AgentConfig:
    if method not in _METHOD_TRUST_KEY:
        raise ValueError(f"unknown method '{method}'; choose from {METHOD_NAMES}")
    trust_key = _METHOD_TRUST_KEY[method]
    # D-074: the trust-side assumed CAI cycle time follows the configured quantum sensor grade (single source:
    # the sensor preset, e.g. FIELD = JARLAUD_CYCLE_TIME_S = 1.548 s); an explicit value (S10 mismatch axis) wins.
    if quantum_cycle_time_s is None:
        quantum_cycle_time_s = default_quantum_cycle_time_s(quantum_grade)
    trust_cfg: TrustEngineConfig = make_method_config(
        trust_key, quantum_enabled=quantum_enabled, quantum_cycle_time_s=quantum_cycle_time_s)
    # D-082: the quantum trust's contrast normalisation follows the configured CAI grade (healthy FIELD CAI has
    # contrast 0.394 < the legacy c_nom of 1.0, which made p_q = 0.67 > theta_on on every healthy epoch).
    _cr = default_quantum_contrast_range(quantum_grade)
    if _cr is not None:
        trust_cfg.quantum_contrast_min, trust_cfg.quantum_contrast_nom = _cr

    # D-066/D-067: frozen per-IMU-grade shadow-NIS acceptance bound (unknown grade -> chi2_6(0.99)).
    if imu_grade in PROBE_NIS_BOUND_BY_GRADE:
        trust_cfg.gnss_law_cfg.probe_nis_bound = PROBE_NIS_BOUND_BY_GRADE[imu_grade]

    alpha_gate = 0.0 if method == "undefended" else 1e-4

    detector_weights = None
    if method in _NEEDS_TRAINED_DETECTOR and detector_weights_path is not None:
        detector_weights = load_detector_weights(detector_weights_path)

    return AgentConfig(world=world, kappa_R=kappa_R, kappa_Q=kappa_Q, alpha_gate=alpha_gate,
                        trust=trust_cfg, clock=ClockKFConfig(), detector_weights=detector_weights)


# --------------------------------------------------------------------------
# Local detector pretraining (M1 stand-in for the FL-trained detector).
# --------------------------------------------------------------------------
def pretrain_detector(seeds: list[int], duration_s: float = 120.0, dt: float = 0.01,
                       platform: str = "ground", imu_grade: str = "industrial_mems",
                       quantum_grade: str | None = "field", detector_seed: int = 0,
                       epochs: int = 2, lr: float = 0.05, batch_size: int = 64) -> dict[str, np.ndarray]:
    """Trains one ``TrustDetector`` (mlp) offline over a small mix of clean
    and attacked short runs on the given (tuning) seeds, using the REAL
    hindsight pseudo-labeller (section 4.3) -- never ``AttackLabel`` -- via a
    surrogate INS-GNSS divergence CUSUM (``trust.pseudolabel.surrogate_s_cusum``;
    the real CAI-aided-INS divergence statistic requires a second running
    fusion instance, deferred as a PROPOSED-DECISION simplification given the
    WP-8.1 token/time budget -- flagged, not hidden).

    This function lives in ``fedqpnt/node/methods.py`` (Environment-adjacent:
    it imports ``fedqpnt.node.environment``, which itself imports
    ``fedqpnt.sim``/``fedqpnt.attacks``), never in ``fedqpnt/trust`` or
    ``fedqpnt/node/agent.py``, so it does not violate the leakage guard.
    """
    from fedqpnt.node.environment import EnvConfig, NodeEnvironment
    from fedqpnt.trust.detector import TrustDetector
    from fedqpnt.trust.features import GnssFeatureExtractor
    from fedqpnt.trust.pseudolabel import PseudoLabelConfig, label_epochs, surrogate_s_cusum

    detector = TrustDetector(arch="mlp", seed=detector_seed)
    extractor_template = GnssFeatureExtractor()

    attack_plans = [
        (None, "clean"),
        (dict(kind="drift_spoof", onset_s=20.0, duration_s=60.0, severity=0.5), "drift"),
        (dict(kind="meaconing", onset_s=20.0, duration_s=60.0, severity=0.6), "meaconing"),
        (dict(kind="jam_cw", onset_s=20.0, duration_s=60.0, severity=0.5), "jam"),
    ]

    all_U, all_ys, all_yj = [], [], []
    for i, seed in enumerate(seeds):
        atk_spec, _name = attack_plans[i % len(attack_plans)]
        env_cfg = EnvConfig(platform=platform, imu_grade=imu_grade, quantum_grade=quantum_grade,
                             gnss_rate_hz=1.0, hold_s=10.0,
                             attacks=[atk_spec] if atk_spec is not None else [])
        env = NodeEnvironment(env_cfg, seed=seed, node_id="pretrain", dt=dt, duration_s=duration_s)
        extractor = GnssFeatureExtractor()

        ts, raws, raims, nsats = [], [], [], []
        from fedqpnt.gnss.receiver import GnssReceiver
        recv = GnssReceiver()  # fresh receiver per seed: lock-state independent between runs
        for k in range(len(env)):
            tick = env.tick(k)
            if tick.gnss_epoch is None:
                continue
            fix = recv.solve(tick.gnss_epoch)
            raw = extractor.step(fix, [])   # x1/x2 unavailable without a fusion filter here; rely on x3..x15
            if raw is None:
                continue
            ts.append(tick.t)
            raws.append(raw)
            raims.append(fix.raim_stat if np.isfinite(fix.raim_stat) else 0.0)
            nsats.append(fix.num_sats)

        if not ts:
            continue
        t_arr = np.array(ts)
        raw_arr = np.array(raws)
        s_cusum = surrogate_s_cusum(raw_arr)
        y = label_epochs(t_arr, raw_arr, np.array(raims), np.array(nsats), s_cusum,
                          cfg=PseudoLabelConfig())

        keep = ~np.isnan(y)
        if not np.any(keep):
            continue
        for j in np.flatnonzero(keep):
            xtilde = detector.normalizer.normalize(raw_arr[j])
            if y[j] == 0.0:
                detector.normalizer.update(raw_arr[j])
            u = detector._stack.step(t_arr[j], xtilde)
            all_U.append(u)
            all_ys.append(y[j])
            all_yj.append(y[j])   # spoof/jam not distinguished by this hindsight rule set -> both heads share y

    if not all_U:
        return detector.get_params()

    U = np.array(all_U)
    y_spoof = np.array(all_ys)
    y_jam = np.array(all_yj)
    rng = stream(detector_seed, "pretrain", "sgd")
    detector.train_local(U, y_spoof, y_jam, epochs=epochs, lr=lr, batch_size=batch_size, rng=rng)
    return detector.get_params()
