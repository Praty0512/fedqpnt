"""Continuous trust law + IMU/quantum rule-based trust + method-variant modes,
ARCHITECTURE.md §3.3-3.5, §5 (WP-4.2/4.3, TRUST agent).

One state-machine core (``_LawCore``) implements equations (1)-(6) of §3.3
(smoothing, asymmetric target, hysteresis+dwell detection flag D, recovery
gate G with anti-lockout). Every method variant of §5 is a config diff over
this ONE code path, selected by ``law_mode``:

  * "continuous"        -- FedQPNT / B-cont / -quantum / logreg / FedAvg / B'
                           (full eqs 1-6; only the *input* p differs for B',
                           handled upstream by ``p_source``, and only what
                           trains the detector differs for B-cont, outside
                           this module's scope).
  * "no_recovery_gate"  -- Abl -recovery-gate: G is forced True (eq 6's cap
                           logic is skipped, recovery always allowed).
  * "binary_hysteresis" -- Abl binary: w = w_min if D else 1 (only eq 3's D
                           is used; eqs 4/5/6 are not).
  * "detect_switch"     -- Baseline B-bin: hard exclude at w_excl while
                           D=1 or the recovery gate G has not yet re-fired,
                           hard w=1 once G fires (Pardhasaradhi-2022 class).
  * "fixed_exclude"     -- Baseline A: MEMORYLESS w = 1 if p_j<0.5 else 0
                           (no p̄, no hysteresis, no recovery gate at all).
  * "w_equals_1"        -- A0 / Abl fixed-trust: w == 1 always (alarm-only /
                           NIS-gate-only defence).

Quantum trust (§3.5) reuses the SAME ``_LawCore`` with different time
constants (``tau_d=T_c``, ``tau_r=60 s``, ``T_clean=5 T_c``), fed by the
rule-based ``p_q`` (contrast/validity gate + two-sided Page CUSUM on the
hybrid residual).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from scipy.stats import chi2

from fedqpnt.core.types import ImuSample, Innovation, QuantumSample

LawMode = Literal[
    "continuous", "no_recovery_gate", "binary_hysteresis",
    "detect_switch", "fixed_exclude", "w_equals_1",
]


@dataclass
class TrustLawConfig:
    """§3.3 defaults; all [ASSUMPTION unless stated], swept +-2x in the
    sensitivity study (per spec note). Quantum overrides tau_d/tau_r/T_clean
    per §3.5 (built by ``quantum_law_config``)."""

    tau_p: float = 0.5
    theta_lo: float = 0.2
    theta_hi: float = 0.8
    theta_on: float = 0.6
    theta_off: float = 0.3
    T_on: float = 0.5
    T_off: float = 5.0
    T_clean: float = 10.0
    tau_d: float = 0.5
    tau_r: float = 10.0
    w_min: float = 0.02
    w_excl: float = 0.05
    T_lock: float = 120.0
    w_cap: float = 0.5
    w_reacq: float = 0.5
    T_gap: float = 5.0
    frac_clean_threshold: float = 0.9
    nis_chi2_quantile: float = 0.95
    nis_dof: int = 3

    @property
    def nis_clean_threshold(self) -> float:
        """`chi2_3(0.95) / 3` -- the per-epoch x1 (already /dof) clean cutoff."""
        return float(chi2.ppf(self.nis_chi2_quantile, self.nis_dof)) / self.nis_dof


def quantum_law_config(cycle_time_s: float, base: TrustLawConfig | None = None) -> TrustLawConfig:
    base = base or TrustLawConfig()
    return TrustLawConfig(
        tau_p=base.tau_p, theta_lo=base.theta_lo, theta_hi=base.theta_hi,
        theta_on=base.theta_on, theta_off=base.theta_off, T_on=base.T_on, T_off=base.T_off,
        T_clean=5.0 * cycle_time_s, tau_d=cycle_time_s, tau_r=60.0,
        w_min=base.w_min, w_excl=base.w_excl, T_lock=base.T_lock, w_cap=base.w_cap,
        w_reacq=base.w_reacq, T_gap=base.T_gap,
        frac_clean_threshold=base.frac_clean_threshold,
        nis_chi2_quantile=base.nis_chi2_quantile, nis_dof=base.nis_dof,
    )


@dataclass
class _LawCore:
    """Shared p-bar/D/G state machine (eqs 1-4 + the anti-lockout timer of
    eq 6). Every ``law_mode`` except "fixed_exclude"/"w_equals_1" runs this
    core once per evidence event; only the final w-assignment differs."""

    cfg: TrustLawConfig
    p_bar: float = 1.0
    w: float = 1.0
    D: int = 0
    _last_t: float | None = field(default=None, repr=False)
    _on_timer: float = field(default=0.0, repr=False)
    _off_timer: float = field(default=0.0, repr=False)
    _t_last_exceed_off: float = field(default=float("-inf"), repr=False)
    _clean_buf: deque = field(default_factory=deque, repr=False)   # (t, nis_ok)
    _lock_timer: float = field(default=0.0, repr=False)
    _initialised: bool = field(default=False, repr=False)

    def reset(self, w0: float = 1.0) -> None:
        self.p_bar = w0
        self.w = w0
        self.D = 0
        self._last_t = None
        self._on_timer = 0.0
        self._off_timer = 0.0
        self._t_last_exceed_off = float("-inf")
        self._clean_buf.clear()
        self._lock_timer = 0.0
        self._initialised = False

    def _push_clean(self, t: float, nis_ok: bool) -> None:
        self._clean_buf.append((t, nis_ok))
        cutoff = t - self.cfg.T_clean
        while self._clean_buf and self._clean_buf[0][0] < cutoff:
            self._clean_buf.popleft()

    def _frac_clean(self) -> float:
        if not self._clean_buf:
            return 0.0
        oks = sum(1 for _, ok in self._clean_buf if ok)
        return oks / len(self._clean_buf)

    def advance(self, t: float, p: float, nis_ok: bool, features_nominal: bool) -> dict:
        """Runs eqs (1)-(4) + anti-lockout timer. Returns a dict with
        p_bar, tau_star, D, G, G_capped, target (post-cap), dt."""
        c = self.cfg
        if not self._initialised:
            self.p_bar = p
            self._initialised = True
            dt = 0.0
        else:
            dt = max(t - self._last_t, 0.0)
        self._last_t = t

        beta = 1.0 - np.exp(-dt / c.tau_p) if dt > 0 else 1.0
        self.p_bar = self.p_bar + beta * (p - self.p_bar)
        tau_star = c.w_min + (1.0 - c.w_min) * float(np.clip(
            (c.theta_hi - self.p_bar) / (c.theta_hi - c.theta_lo), 0.0, 1.0))

        if self.p_bar >= c.theta_on:
            self._on_timer += dt
        else:
            self._on_timer = 0.0
        if self.p_bar <= c.theta_off:
            self._off_timer += dt
        else:
            self._off_timer = 0.0
        if self._on_timer >= c.T_on:
            self.D = 1
        elif self._off_timer >= c.T_off:
            self.D = 0

        if self.p_bar > c.theta_off:
            self._t_last_exceed_off = t
        clean_dwell = t - self._t_last_exceed_off

        self._push_clean(t, nis_ok)
        frac_clean = self._frac_clean()

        G = (self.D == 0) and (clean_dwell >= c.T_clean) and (frac_clean >= c.frac_clean_threshold)

        blocked_only_by_nis = ((self.D == 0) and (clean_dwell >= c.T_clean)
                                and (frac_clean < c.frac_clean_threshold) and features_nominal)
        self._lock_timer = self._lock_timer + dt if blocked_only_by_nis else 0.0
        G_capped = (not G) and (self._lock_timer >= c.T_lock)

        return dict(dt=dt, p_bar=self.p_bar, tau_star=tau_star, D=self.D,
                    G=G, G_capped=G_capped)


@dataclass
class SensorTrustLaw:
    """One instance per sensor stream (gnss / quantum). Wraps ``_LawCore``
    with the final w-assignment for the configured ``law_mode``."""

    cfg: TrustLawConfig = field(default_factory=TrustLawConfig)
    law_mode: LawMode = "continuous"
    _core: _LawCore = field(init=False)
    # "detect_switch" (B-bin) needs one bit of extra state: are we currently excluded?
    _excluded: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        self._core = _LawCore(cfg=self.cfg)

    def reset(self, w0: float = 1.0) -> None:
        self._core.reset(w0)
        self._excluded = False

    @property
    def w(self) -> float:
        return self._core.w

    @property
    def p_bar(self) -> float:
        return self._core.p_bar

    @property
    def attack_detected(self) -> bool:
        return bool(self._core.D)

    def step(self, t: float, p: float, nis_ok: bool = True, features_nominal: bool = True) -> float:
        c = self.cfg

        if self.law_mode == "fixed_exclude":
            # Baseline A: memoryless, no state at all.
            self._core.D = 1 if p >= 0.5 else 0
            self._core.p_bar = p
            self._core.w = 0.0 if self._core.D else 1.0
            return self._core.w

        if self.law_mode == "w_equals_1":
            self._core.D = 1 if p >= 0.5 else 0
            self._core.p_bar = p
            self._core.w = 1.0
            return 1.0

        info = self._core.advance(t, p, nis_ok, features_nominal)
        dt, tau_star, D, G, G_capped = info["dt"], info["tau_star"], info["D"], info["G"], info["G_capped"]

        if self.law_mode == "no_recovery_gate":
            G_effective, target = True, tau_star
        elif G_capped:
            G_effective, target = True, min(tau_star, c.w_cap)
        else:
            G_effective, target = G, tau_star

        w = self._core.w
        if self.law_mode == "binary_hysteresis":
            w = c.w_min if D else 1.0
        elif self.law_mode == "detect_switch":
            if D == 1:
                self._excluded = True
            if self._excluded and G:
                self._excluded = False
            w = c.w_excl if self._excluded else 1.0
        else:  # "continuous"
            if target < w:
                w = w + (1.0 - np.exp(-dt / c.tau_d)) * (target - w) if dt > 0 else target
            elif target > w and G_effective:
                w = w + (1.0 - np.exp(-dt / c.tau_r)) * (target - w) if dt > 0 else target
            w = float(np.clip(w, c.w_min, 1.0))

        self._core.w = w
        return w

    def apply_reacquisition_cap(self) -> None:
        """§9/§5 table: first valid fix after an outage > T_gap gets its
        weight capped at ``w_reacq`` before normal recovery resumes."""
        self._core.w = min(self._core.w, self.cfg.w_reacq)


# --------------------------------------------------------------------------
# IMU trust (§3.4) -- rule-based, no attack targets it in v1.
# --------------------------------------------------------------------------
IMU_SATURATION_MPS2 = 156.9  # [ASSUMPTION] ~16 g, typical tactical-MEMS accelerometer full-scale range


@dataclass
class ImuTrust:
    w_min: float = 0.02
    saturation_mps2: float = IMU_SATURATION_MPS2
    w: float = 1.0

    def reset(self) -> None:
        self.w = 1.0

    def step(self, imu: ImuSample | None) -> float:
        if imu is None:
            self.w = self.w_min
        elif np.any(np.abs(imu.f_b) > self.saturation_mps2):
            self.w = self.w_min
        else:
            self.w = 1.0
        return self.w


# --------------------------------------------------------------------------
# Quantum trust (§3.5) -- rule-based p_q + two-sided Page CUSUM, then the
# same continuous law (with quantum time constants).
# --------------------------------------------------------------------------
@dataclass
class QuantumTrust:
    cycle_time_s: float = 1.0
    c_min: float = 0.1
    c_nom: float = 1.0
    nis_quantile: float = 0.999
    cusum_h: float = 8.0
    law_mode: LawMode = "continuous"
    _law: SensorTrustLaw = field(init=False)
    _splus: float = field(default=0.0, repr=False)
    _sminus: float = field(default=0.0, repr=False)
    _nu_mean: np.ndarray | None = field(default=None, repr=False)
    _nu_beta: float = field(default=0.1, repr=False)  # EWMA rate for causal E[nu_Q] (PROPOSED-DECISION, see module docstring)

    def __post_init__(self) -> None:
        self._law = SensorTrustLaw(cfg=quantum_law_config(self.cycle_time_s), law_mode=self.law_mode)

    def reset(self) -> None:
        self._law.reset(1.0)
        self._splus = 0.0
        self._sminus = 0.0
        self._nu_mean = None

    @property
    def w(self) -> float:
        return self._law.w

    @property
    def p_bar(self) -> float:
        return self._law.p_bar

    def step(self, t: float, quantum: QuantumSample | None, gnss_w: float,
             quantum_innovation: Innovation | None) -> float:
        if quantum is None:
            return self._law.w  # dead time: hold, no evidence event

        c = self._law.cfg
        contrast_term = float(np.clip((quantum.contrast - self.c_min) / max(self.c_nom - self.c_min, 1e-9), 0.0, 1.0))

        nis_ok_hi = True
        if quantum_innovation is not None:
            dof = max(quantum_innovation.dof, 1)
            nis_ok_hi = quantum_innovation.nis <= chi2.ppf(self.nis_quantile, dof)

        p_q = 1.0 - float(quantum.valid) * contrast_term * float(nis_ok_hi)

        # Two-sided Page CUSUM on the standardised hybrid residual, only
        # while GNSS itself is trustworthy (w_gnss > 0.9) so it independently
        # anchors the accelerometer bias the CAI's residual is checked against.
        if quantum_innovation is not None and gnss_w > 0.9:
            nu = quantum_innovation.nu
            S = quantum_innovation.S
            if self._nu_mean is None:
                self._nu_mean = np.zeros_like(nu)
            self._nu_mean = self._nu_mean + self._nu_beta * (nu - self._nu_mean)
            sd = np.sqrt(np.clip(np.diag(S), 1e-12, None))
            r_tilde = float(np.mean((nu - self._nu_mean) / sd))
            self._splus = max(0.0, self._splus + r_tilde - 0.5)
            self._sminus = max(0.0, self._sminus - r_tilde - 0.5)
            if self._splus >= self.cusum_h or self._sminus >= self.cusum_h:
                p_q = 1.0

        nis_ok_clean = True
        if quantum_innovation is not None:
            dof = max(quantum_innovation.dof, 1)
            nis_ok_clean = quantum_innovation.nis / dof <= c.nis_clean_threshold

        return self._law.step(t, p_q, nis_ok=nis_ok_clean, features_nominal=True)


# --------------------------------------------------------------------------
# TrustEngine (v0.2 protocol) -- wires features -> detector -> per-sensor law.
# --------------------------------------------------------------------------
from fedqpnt.core.types import GnssFix, NavSolution, TrustState  # noqa: E402
from fedqpnt.trust.detector import TrustDetector  # noqa: E402
from fedqpnt.trust.features import GnssFeatureExtractor  # noqa: E402


@dataclass
class TrustEngineConfig:
    """One config object = one row of ARCHITECTURE.md §5's method table."""

    method: str = "fedqpnt"
    law_mode: LawMode = "continuous"
    quantum_enabled: bool = True
    p_source: Literal["detector", "bprime"] = "detector"
    detector_arch: Literal["mlp", "logreg"] = "mlp"
    quantum_cycle_time_s: float = 1.0
    gnss_law_cfg: TrustLawConfig = field(default_factory=TrustLawConfig)
    detector_seed: int = 0


_METHOD_TABLE: dict[str, dict] = {
    # trust-law-relevant config diffs only; detector-training source (local
    # vs FL) and aggregator choice are FEDERATED-agent concerns, not this
    # module's -- they do not change TrustEngine's runtime behaviour.
    "fedqpnt":              dict(law_mode="continuous", quantum_enabled=True, p_source="detector"),
    "baseline_a":           dict(law_mode="fixed_exclude", quantum_enabled=True, p_source="detector"),
    "a0":                   dict(law_mode="w_equals_1", quantum_enabled=True, p_source="detector"),
    "baseline_b_cont":      dict(law_mode="continuous", quantum_enabled=True, p_source="detector"),
    "baseline_b_bin":       dict(law_mode="detect_switch", quantum_enabled=True, p_source="detector"),
    "bprime":               dict(law_mode="continuous", quantum_enabled=True, p_source="bprime"),
    "abl_minus_quantum":    dict(law_mode="continuous", quantum_enabled=False, p_source="detector"),
    "abl_minus_fl":         dict(law_mode="continuous", quantum_enabled=True, p_source="detector"),
    "abl_fixed_trust":      dict(law_mode="w_equals_1", quantum_enabled=True, p_source="detector"),
    "abl_binary":           dict(law_mode="binary_hysteresis", quantum_enabled=True, p_source="detector"),
    "abl_minus_recovery_gate": dict(law_mode="no_recovery_gate", quantum_enabled=True, p_source="detector"),
    "abl_logreg":           dict(law_mode="continuous", quantum_enabled=True, p_source="detector", detector_arch="logreg"),
    "abl_fedavg":           dict(law_mode="continuous", quantum_enabled=True, p_source="detector"),
}


def make_method_config(method: str, **overrides) -> TrustEngineConfig:
    if method not in _METHOD_TABLE:
        raise ValueError(f"unknown method '{method}'; choose from {sorted(_METHOD_TABLE)}")
    kwargs = dict(_METHOD_TABLE[method])
    kwargs.update(overrides)
    return TrustEngineConfig(method=method, **kwargs)


_FEATURES_NOMINAL_Z = 1.96  # 95% two-sided normal quantile (x3..x11 "inside 95% nominal quantiles")


class TrustEngineImpl:
    """Implements the ``fedqpnt.core.interfaces.TrustEngine`` protocol."""

    def __init__(self, cfg: TrustEngineConfig | None = None, node_id: str = "node0"):
        self.cfg = cfg or TrustEngineConfig()
        self.node_id = node_id
        self.extractor = GnssFeatureExtractor()
        self.detector = TrustDetector(arch=self.cfg.detector_arch, seed=self.cfg.detector_seed)
        self.gnss_law = SensorTrustLaw(cfg=self.cfg.gnss_law_cfg, law_mode=self.cfg.law_mode)
        self.imu_trust = ImuTrust(w_min=self.cfg.gnss_law_cfg.w_min)
        self.quantum_trust = QuantumTrust(cycle_time_s=self.cfg.quantum_cycle_time_s,
                                           law_mode=self.cfg.law_mode) if self.cfg.quantum_enabled else None
        self._last_valid_gnss_t: float | None = None

    def config(self) -> dict:
        return dict(method=self.cfg.method, law_mode=self.cfg.law_mode,
                    quantum_enabled=self.cfg.quantum_enabled, p_source=self.cfg.p_source,
                    detector_arch=self.cfg.detector_arch)

    def reset(self) -> None:
        self.extractor.reset()
        self.gnss_law.reset(1.0)
        self.imu_trust.reset()
        if self.quantum_trust is not None:
            self.quantum_trust.reset()
        self._last_valid_gnss_t = None

    def _gnss_p(self, raw: np.ndarray) -> float:
        if self.cfg.p_source == "bprime":
            # B': "none: p_j = F_chi2_3(3*x1_j)" (Mehra 1970 innovation-chi2 adaptive rule).
            return float(chi2.cdf(3.0 * raw[0], df=3))
        p_spoof, p_jam, _u = self.detector.score(self.extractor._last_t or 0.0, raw)
        return max(p_spoof, p_jam)

    def update(self, t: float, fix: GnssFix | None, imu: ImuSample | None,
               quantum: QuantumSample | None, nav_prior: NavSolution | None,
               innovations: list[Innovation]) -> TrustState:
        imu_w = self.imu_trust.step(imu)

        gnss_w = self.gnss_law.w
        if fix is not None:
            raw = self.extractor.step(fix, innovations)
            if raw is not None and fix.valid:
                p = self._gnss_p(raw)
                nis_ok = raw[0] <= self.gnss_law.cfg.nis_clean_threshold
                xtilde = self.detector.normalizer.normalize(raw)
                features_nominal = bool(np.all(np.abs(xtilde[2:11]) <= _FEATURES_NOMINAL_Z))
                gnss_w = self.gnss_law.step(t, p, nis_ok=nis_ok, features_nominal=features_nominal)

                gap = float("inf") if self._last_valid_gnss_t is None else (t - self._last_valid_gnss_t)
                if gap > self.gnss_law.cfg.T_gap:
                    self.gnss_law.apply_reacquisition_cap()
                    gnss_w = self.gnss_law.w
                self._last_valid_gnss_t = t

        quantum_w = 1.0
        if self.quantum_trust is not None:
            gnss_innov = next((iv for iv in innovations if iv.sensor == "quantum"), None)
            quantum_w = self.quantum_trust.step(t, quantum, gnss_w=gnss_w, quantum_innovation=gnss_innov)

        weights = {"gnss": gnss_w, "imu": imu_w, "quantum": quantum_w}
        anomaly_scores = {
            "gnss": self.gnss_law.p_bar,
            "quantum": self.quantum_trust.p_bar if self.quantum_trust is not None else 0.0,
            "imu": 1.0 - imu_w,  # PROPOSED-DECISION: §3.3 defines p_bar only for the learned/rule-scored
                                 # gnss/quantum channels; the IMU rule (§3.4) has no probability, so we
                                 # report its binary anomaly indicator here for TrustState schema symmetry.
        }
        return TrustState(t=t, weights=weights, anomaly_scores=anomaly_scores,
                           attack_detected=self.gnss_law.attack_detected)
