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

# D-066: shadow-probe / shadow-consistent-reacquisition acceptance bound on the (joint 6-D) NIS.
CHI2_6_99 = float(chi2.ppf(0.99, 6))

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

    # D-051 sec C: trust law v2 (evidence-bounded exclusion). Ignored unless
    # SensorTrustLaw(trust_law_version="v2", law_mode="continuous").
    T_ex: float = 60.0       # continuous time in DISTRUST before PROBE
    T_probe: float = 10.0    # PROBE duration
    w_probe: float = 0.3     # fixed w during PROBE, regardless of p
    T_sup: float = 120.0     # detector-suppression window after a successful PROBE->TRUST exit
    # physical spoof evidence E_s thresholds (see _physical_spoof_evidence
    # below): clock/clock-drift jump beyond es_clk_sigma (x8/x9, already in
    # units of the receiver's reported 1-sigma per features.py), xsat C/N0
    # correlation above the floored nominal band (D-024, reusing the
    # detector's own running normalizer as the "clean reference"), a
    # meaconing C/N0 bump >= es_cn0_band_excess_db, and an abrupt position
    # innovation (x1, dof-normalised) beyond the es_position_gate_quantile
    # chi2 gate.
    es_clk_sigma: float = 5.0
    es_xsat_quantile_z: float = 1.96
    es_cn0_band_excess_db: float = 3.0
    es_position_gate_quantile: float = 0.999
    # D-058: the position-evidence term is now a short-baseline GNSS-vs-INS
    # jump test, not the filter's own NIS (self-contaminated by the
    # filter's own P -- see _physical_spoof_evidence). es_ins_short_sigma_pos
    # is an [ASSUMPTION]-grade per-axis 1-sigma bound on how much a
    # short-baseline (one GNSS epoch, ~1 s) pure-INS position propagation
    # can drift by mechanisation/integration noise alone (MEMS-class,
    # conservative). It is a small, dt-independent-of-filter-history
    # physical constant, NOT read from the filter's P, so it cannot inherit
    # any filter self-divergence or overconfidence.
    es_ins_short_sigma_pos: float = 0.05
    # D-058 follow-up (Master-directed jam-recovery diagnostic): the
    # position-evidence baseline (_last_gnss_pos/_last_gnss_cov/
    # _last_p_prior) is only valid across ONE ordinary GNSS epoch. After a
    # gap (e.g. a jamming-induced GNSS outage), the baseline is stale by
    # the whole gap, not one epoch, so Delta p_INS wrongly includes the
    # entire outage's accumulated INS drift while Delta p_GNSS is a normal
    # one-epoch difference -- a huge, spurious mismatch that falsely fires
    # E_s on the very first fix after every outage (confirmed by trace:
    # scripts/core_robust_jam_recovery_trace.py). Any gap longer than
    # ``es_gap_reset_factor`` x this nominal epoch interval resets the
    # baseline instead of testing it (treated as "insufficient history",
    # matching the existing no-history case) -- the position term is
    # skipped for exactly one epoch (the first fix after the gap), then
    # resumes normally from a fresh baseline. [ASSUMPTION: 1.0 Hz matches
    # the project's standard nominal GNSS rate used throughout the eval
    # scripts/tests; 1.5x per Master's directive.]
    es_nominal_epoch_s: float = 1.0
    # D-066/D-067: acceptance bound on the mean joint shadow NIS (PROBE exit; reacquisition-cap waiver).
    # None -> chi2_6(0.99). Per-IMU-grade values (99th percentile of the CLEAN mean-shadow-NIS
    # distribution, frozen) are applied by fedqpnt/node/methods.py; see PROBE_NIS_BOUND_BY_GRADE.
    probe_nis_bound: float | None = None
    es_gap_reset_factor: float = 1.5

    @property
    def nis_clean_threshold(self) -> float:
        """`chi2_3(0.95) / 3` -- the per-epoch x1 (already /dof) clean cutoff."""
        return float(chi2.ppf(self.nis_chi2_quantile, self.nis_dof)) / self.nis_dof

    @property
    def position_gate_threshold(self) -> float:
        """dof-normalised x1 gate for E_s's 'abrupt position innovation
        beyond the gate' condition -- a stricter, less-frequently-crossed
        quantile than ``nis_clean_threshold`` (95%), since this is meant to
        be a rare physical-anomaly signature, not the routine clean/dirty
        split. PROPOSED-DECISION: the D-051 table names this condition but
        does not fix its quantile; 99.9% is chosen as a conservative "this
        essentially never happens on clean data" gate, matching the order
        of magnitude of this codebase's other rare-event thresholds (e.g.
        pseudolabel.py RAIM_PFA family)."""
        return float(chi2.ppf(self.es_position_gate_quantile, self.nis_dof)) / self.nis_dof


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
class _LawCoreV2:
    """D-051 sec C: TRUST/DISTRUST/PROBE evidence-bounded exclusion. Reuses
    ``_LawCore`` unchanged for the p-bar smoothing / hysteresis-D / tau_star
    / recovery-gate machinery (eqs 1-4, 6) -- v2 only changes what happens
    to w once D=1: instead of the old unbounded-time exclusion (the M1-CLOSE
    root cause, EXECUTION_LOG #83), DISTRUST is capped at T_ex before a
    bounded PROBE decides recovery or renewed exclusion.
    """

    cfg: TrustLawConfig
    core: _LawCore = field(init=False)
    state: str = field(default="TRUST", repr=False)  # "TRUST" | "DISTRUST" | "PROBE"
    w: float = 1.0
    _distrust_timer: float = field(default=0.0, repr=False)
    _probe_timer: float = field(default=0.0, repr=False)
    _probe_nis_sum: float = field(default=0.0, repr=False)
    _probe_nis_n: int = field(default=0, repr=False)
    _probe_es_any: bool = field(default=False, repr=False)
    _suppress_timer: float = field(default=0.0, repr=False)

    def __post_init__(self) -> None:
        self.core = _LawCore(cfg=self.cfg)

    def reset(self, w0: float = 1.0) -> None:
        self.core.reset(w0)
        self.state = "TRUST"
        self.w = w0
        self._distrust_timer = 0.0
        self._probe_timer = 0.0
        self._probe_nis_sum = 0.0
        self._probe_nis_n = 0
        self._probe_es_any = False
        self._suppress_timer = 0.0

    @property
    def D(self) -> int:
        return 0 if self.state == "TRUST" else 1

    @property
    def p_bar(self) -> float:
        return self.core.p_bar

    def _ramp(self, target: float, dt: float, G_effective: bool) -> None:
        c = self.cfg
        if target < self.w:
            self.w = self.w + (1.0 - np.exp(-dt / c.tau_d)) * (target - self.w) if dt > 0 else target
        elif target > self.w and G_effective:
            self.w = self.w + (1.0 - np.exp(-dt / c.tau_r)) * (target - self.w) if dt > 0 else target
        self.w = float(np.clip(self.w, c.w_min, 1.0))

    def advance(self, t: float, p: float, nis_ok: bool, features_nominal: bool,
                nis_value: float, es_evidence: bool, es_position: bool = False) -> float:
        c = self.cfg
        # D-066: es_evidence = clk/xsat/cn0 physical evidence (always vetoes, also in PROBE);
        # es_position = short-baseline jump test, SUPERSEDED during PROBE by the shadow-NIS test
        # (consistency with the coasting INS/CAI state is the stronger evidence, and it resolves
        # the false fire on a legitimate fix return after a spoof ends).
        es_pos_active = es_position and self.state != "PROBE"
        es_any = es_evidence or es_pos_active
        # T_sup (sec C item 4): while suppressed, the learned detector's p is
        # ignored (treated as clean) unless E_s itself fires -- E_s always
        # gets through, so a genuine physical spoof signature can still
        # re-trigger exclusion during the suppression window.
        effective_p = 0.0 if (self._suppress_timer > 0 and not es_any) else p
        # es_evidence is a PHYSICAL signature, not the learned detector: if
        # it fires, force the hysteresis core to see p=1 regardless of
        # suppression, so an evidenced spoof is never masked.
        if es_any:
            effective_p = 1.0

        info = self.core.advance(t, effective_p, nis_ok, features_nominal)
        dt = info["dt"]
        if self._suppress_timer > 0:
            self._suppress_timer = max(0.0, self._suppress_timer - dt)

        if self.state == "TRUST":
            if info["D"] == 1:
                self.state = "DISTRUST"
                self._distrust_timer = 0.0
            G_effective = info["G"] or info["G_capped"]
            target = min(info["tau_star"], c.w_cap) if info["G_capped"] else info["tau_star"]
            self._ramp(target, dt, G_effective)

        elif self.state == "DISTRUST":
            self._distrust_timer += dt
            G_effective = info["G"] or info["G_capped"]
            target = min(info["tau_star"], c.w_cap) if info["G_capped"] else info["tau_star"]
            self._ramp(target, dt, G_effective)
            if self._distrust_timer >= c.T_ex:
                self.state = "PROBE"
                self._probe_timer = 0.0
                self._probe_nis_sum = 0.0
                self._probe_nis_n = 0
                self._probe_es_any = False

        elif self.state == "PROBE":
            # sec C item 3: w fixed at w_probe regardless of p, for the whole probe; collect NIS +
            # E_s evidence. D-066 SHADOW PROBE: while in PROBE the filter applies NO GNSS update
            # (TrustState.probe_shadow); nis_value is the joint 6-D GNSS innovation NIS against
            # the coasting state (receiver's own covariance, chi2_6 under nominal conditions).
            # Known limit (paper limitation): a consistency-matched adversary that keeps the
            # spoof inside the coast uncertainty can pass the probe; the damage is bounded by the
            # coast covariance P (once admitted, the pull per epoch stays inside ~sqrt(S)).
            self.w = c.w_probe
            self._probe_timer += dt
            self._probe_nis_sum += nis_value
            self._probe_nis_n += 1
            self._probe_es_any = self._probe_es_any or es_evidence
            if self._probe_timer >= c.T_probe:
                mean_nis = self._probe_nis_sum / max(self._probe_nis_n, 1)
                bound = CHI2_6_99 if c.probe_nis_bound is None else c.probe_nis_bound
                if mean_nis <= bound and not self._probe_es_any:
                    # sec C item 4, success: TRUST, detector suppressed for
                    # T_sup, recovery continues via the normal ramp (next
                    # call, from w=w_probe) in the TRUST branch above.
                    self.state = "TRUST"
                    self._suppress_timer = c.T_sup
                    self._distrust_timer = 0.0
                else:
                    # sec C item 4, failure: back to DISTRUST for another T_ex.
                    self.state = "DISTRUST"
                    self._distrust_timer = 0.0

        return self.w


@dataclass
class SensorTrustLaw:
    """One instance per sensor stream (gnss / quantum). Wraps ``_LawCore``
    with the final w-assignment for the configured ``law_mode``."""

    cfg: TrustLawConfig = field(default_factory=TrustLawConfig)
    law_mode: LawMode = "continuous"
    # D-051 sec C: "v2" (evidence-bounded exclusion) only has an effect when
    # law_mode == "continuous"; every other law_mode ignores it. Default
    # "v1" keeps the OLD (unbounded-DISTRUST-time) law selectable for
    # ablation, per the Master's instruction.
    trust_law_version: Literal["v1", "v2"] = "v1"
    _core: _LawCore = field(init=False)
    _core_v2: _LawCoreV2 = field(init=False, repr=False)
    # "detect_switch" (B-bin) needs one bit of extra state: are we currently excluded?
    _excluded: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        self._core = _LawCore(cfg=self.cfg)
        self._core_v2 = _LawCoreV2(cfg=self.cfg)

    def reset(self, w0: float = 1.0) -> None:
        self._core.reset(w0)
        self._core_v2.reset(w0)
        self._excluded = False

    @property
    def _uses_v2(self) -> bool:
        return self.law_mode == "continuous" and self.trust_law_version == "v2"

    @property
    def w(self) -> float:
        return self._core_v2.w if self._uses_v2 else self._core.w

    @property
    def p_bar(self) -> float:
        return self._core_v2.p_bar if self._uses_v2 else self._core.p_bar

    @property
    def attack_detected(self) -> bool:
        return bool(self._core_v2.D) if self._uses_v2 else bool(self._core.D)

    @property
    def probe_shadow(self) -> bool:
        """D-066: True while the v2 law is in PROBE (GNSS evaluated, not applied)."""
        return bool(self._uses_v2 and self._core_v2.state == "PROBE")

    def step(self, t: float, p: float, nis_ok: bool = True, features_nominal: bool = True,
             nis_value: float | None = None, es_evidence: bool = False,
             es_position: bool = False) -> float:
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

        if self._uses_v2:
            # nis_value: the actual (dof-normalised) NIS, needed for the
            # PROBE mean-NIS exit test (sec C item 4). Falls back to a
            # value consistent with nis_ok when the caller doesn't have it
            # (e.g. existing v1-style call sites / tests).
            nv = nis_value
            if nv is None:
                nv = 0.0 if nis_ok else 2.0 * CHI2_6_99
            return self._core_v2.advance(t, p, nis_ok, features_nominal, nv, es_evidence, es_position)

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
        if self._uses_v2:
            self._core_v2.w = min(self._core_v2.w, self.cfg.w_reacq)
        else:
            self._core.w = min(self._core.w, self.cfg.w_reacq)

    def force_w(self, w0: float) -> None:
        """Version-agnostic direct override of the current weight (test /
        harness hook -- e.g. to force a fully-trusted pre-outage state
        before exercising the reacquisition cap). Writes whichever core
        (``_core`` or ``_core_v2``) actually backs ``.w`` for this
        instance's ``law_mode``/``trust_law_version``."""
        if self._uses_v2:
            self._core_v2.w = w0
        else:
            self._core.w = w0


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
from fedqpnt.trust.pseudolabel import apply_sigma_floor  # noqa: E402

# raw-feature indices used by _physical_spoof_evidence (features.FEATURE_NAMES order)
_IDX_NIS_POS, _IDX_CN0_MEAN, _IDX_CLK_JUMP, _IDX_DRIFT_JUMP, _IDX_XSAT_CORR = 0, 3, 7, 8, 13


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
    # D-051 sec C: v2 (evidence-bounded exclusion) applies ONLY to
    # fedqpnt/baseline_b_cont (see _METHOD_TABLE); every other method,
    # baseline A/B-bin/B' included, stays on the old law ("v1").
    trust_law_version: Literal["v1", "v2"] = "v1"


_METHOD_TABLE: dict[str, dict] = {
    # trust-law-relevant config diffs only; detector-training source (local
    # vs FL) and aggregator choice are FEDERATED-agent concerns, not this
    # module's -- they do not change TrustEngine's runtime behaviour.
    "fedqpnt":              dict(law_mode="continuous", quantum_enabled=True, p_source="detector", trust_law_version="v2"),
    "baseline_a":           dict(law_mode="fixed_exclude", quantum_enabled=True, p_source="detector"),
    "a0":                   dict(law_mode="w_equals_1", quantum_enabled=True, p_source="detector"),
    "baseline_b_cont":      dict(law_mode="continuous", quantum_enabled=True, p_source="detector", trust_law_version="v2"),
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

_FALLBACK_COV_POS = np.diag([9.0, 9.0, 25.0])  # matches ESKF's fallback_cov_pos default


def _p_prior_from_innovations(fix: GnssFix, innovations: list[Innovation]) -> np.ndarray | None:
    """D-058: this epoch's PRE-correction filter position estimate,
    p_prior = fix.pos + nu_pos (nu_pos = p_prior - fix.pos, the nominal-R
    "gnss_pos" innovation already computed by the filter). None if there is
    no gnss_pos innovation this tick."""
    inv = next((iv for iv in innovations if iv.sensor == "gnss_pos"), None)
    if inv is None:
        return None
    return np.asarray(fix.pos, dtype=float) + np.asarray(inv.nu, dtype=float)


def _spd_cov_or_fallback(cov: np.ndarray) -> np.ndarray:
    """D-058: symmetrise a fix's cov_pos for the short-baseline jump test;
    fall back to a conservative diagonal if it's missing/non-finite/wrong
    shape (mirrors ``fedqpnt.fusion.eskf._spd_or_fallback``'s contract,
    reimplemented here since this module must stay independent of the
    filter)."""
    cov = np.asarray(cov, dtype=float)
    if cov.shape != (3, 3) or not np.all(np.isfinite(cov)):
        return _FALLBACK_COV_POS.copy()
    return 0.5 * (cov + cov.T)


class TrustEngineImpl:
    """Implements the ``fedqpnt.core.interfaces.TrustEngine`` protocol."""

    def __init__(self, cfg: TrustEngineConfig | None = None, node_id: str = "node0"):
        self.cfg = cfg or TrustEngineConfig()
        self.node_id = node_id
        self.extractor = GnssFeatureExtractor()
        self.detector = TrustDetector(arch=self.cfg.detector_arch, seed=self.cfg.detector_seed)
        self.gnss_law = SensorTrustLaw(cfg=self.cfg.gnss_law_cfg, law_mode=self.cfg.law_mode,
                                       trust_law_version=self.cfg.trust_law_version)
        self.imu_trust = ImuTrust(w_min=self.cfg.gnss_law_cfg.w_min)
        self.quantum_trust = QuantumTrust(cycle_time_s=self.cfg.quantum_cycle_time_s,
                                           law_mode=self.cfg.law_mode) if self.cfg.quantum_enabled else None
        self._last_valid_gnss_t: float | None = None
        # D-058: previous accepted GNSS epoch's raw fix position/cov_pos,
        # kept ONLY for the short-baseline jump test (Delta p_GNSS side) --
        # never the filter's own state/P.
        self._last_gnss_pos: np.ndarray | None = None
        self._last_gnss_cov: np.ndarray | None = None
        # D-058: previous epoch's PRE-correction filter estimate p_prior =
        # fix.pos + nu_pos, exactly one GNSS epoch old by construction
        # (unlike nav_prior, which is only one IMU tick old -- see
        # _physical_spoof_evidence's docstring for why that distinction
        # matters).
        self._last_p_prior: np.ndarray | None = None
        # D-058 follow-up: number of upcoming epochs (including the current
        # one, if just triggered) for which the position-evidence term is
        # forced off, set by a gap-reset (see update()). One epoch was not
        # enough on its own: the FIRST post-gap epoch typically applies a
        # large corrective pull (soft gating never fully rejects it), and
        # since ``_last_p_prior`` stores the PRE-correction estimate, the
        # epoch AFTER that pull sees an artificially huge Delta p_INS (the
        # pull itself, not real INS growth) and false-fires again -- traced
        # empirically (scripts/core_robust_jam_recovery_trace.py: post-gap
        # epoch recovers cleanly, but the NEXT epoch still fired,
        # stat=763 vs gate=16.27). Quarantining 2 epochs covers the pull
        # epoch and the one immediately after it.
        self._es_position_quarantine: int = 0
        # D-056 metric logging ONLY (item 1): the raw calibrated detector p
        # (E_s excluded) and whether E_s fired, for the tick just processed.
        # Read-only side channel -- never fed back into any control flow, so
        # it cannot change runtime behaviour (detector/trust-law design).
        self.last_raw_p: float | None = None
        self.last_es_evidence: bool = False

    def config(self) -> dict:
        return dict(method=self.cfg.method, law_mode=self.cfg.law_mode,
                    quantum_enabled=self.cfg.quantum_enabled, p_source=self.cfg.p_source,
                    detector_arch=self.cfg.detector_arch, trust_law_version=self.cfg.trust_law_version)

    def reset(self) -> None:
        self.extractor.reset()
        self.gnss_law.reset(1.0)
        self.imu_trust.reset()
        if self.quantum_trust is not None:
            self.quantum_trust.reset()
        self._last_valid_gnss_t = None
        self._last_gnss_pos = None
        self._last_gnss_cov = None
        self._last_p_prior = None
        self._es_position_quarantine = 0
        self.last_raw_p = None
        self.last_es_evidence = False

    def _gnss_p(self, raw: np.ndarray) -> float:
        if self.cfg.p_source == "bprime":
            # B': "none: p_j = F_chi2_3(3*x1_j)" (Mehra 1970 innovation-chi2 adaptive rule).
            return float(chi2.cdf(3.0 * raw[0], df=3))
        p_spoof, p_jam, _u = self.detector.score(self.extractor._last_t or 0.0, raw)
        return max(p_spoof, p_jam)

    def _physical_spoof_evidence(self, raw: np.ndarray, fix: GnssFix,
                                  nav_prior: NavSolution | None,
                                  innovations: list[Innovation],
                                  skip_position: bool = False, split: bool = False):
        """D-051 sec C: E_s, the physical spoof-evidence set. Uses the
        detector's own running normalizer (updated only on pseudo-label-
        negative samples) as the "clean reference" mu/sd -- the same idea
        as the labeller's quantile_mu/sd, but the node-local, runtime
        version of it, with the same D-051 sigma floors applied so a
        near-degenerate sd here cannot make this evidence spuriously easy
        to trigger either.

        D-058: the position term is the short-baseline GNSS-vs-INS jump
        test, not the filter's own NIS (raw[_IDX_NIS_POS]) -- that NIS uses
        S = H P H^T + R, so it is self-contaminated by the filter's own
        (possibly wrong, possibly attack-shrunk) P and cannot tell a real
        spoof jump apart from filter self-divergence/overconfidence. The
        replacement, d = Delta p_GNSS - Delta p_INS over ONE GNSS epoch,
        depends only on: this epoch's and the previous epoch's raw GNSS fix
        position (Delta p_GNSS), and this epoch's and the previous epoch's
        PRE-correction filter estimate p_prior = fix.pos + nu_pos (Delta
        p_INS -- the filter's own continuous propagation between the two
        epochs, entirely independent of what either epoch's correction
        then does with it) -- never the filter's accumulated P.

        IMPORTANT: this must NOT use ``nav_prior`` (the previous AGENT
        TICK's corrected NavSolution) as the Delta p_INS baseline -- GNSS
        ticks are sparse relative to IMU ticks (e.g. 1 Hz vs 100 Hz), so
        ``nav_prior`` is only ONE IMU dt (~0.01s) older than this tick, not
        one GNSS epoch (~1s) older. Using it as the baseline was tried and
        measured to fire on ~80% of clean nominal epochs (the "Delta p_INS"
        it produced covered only the last ~0.01s while "Delta p_GNSS"
        covered the full ~1s epoch, so d was dominated by ordinary vehicle
        motion, not spoofing) -- see docs/specs/raw/CORE_ROBUST_NOTES.md.
        The fix: track this engine's OWN previous-epoch p_prior
        (``_last_p_prior``), which is exactly one GNSS epoch old by
        construction, regardless of the IMU tick rate.

        A slow drag stays small epoch-to-epoch (no fire); an abrupt jump
        appears entirely in this one epoch's Delta p_GNSS (fires); filter
        self-divergence accumulated over many epochs does not show up in a
        ONE-epoch delta at all (no fire).

        ``skip_position`` (D-058 follow-up): forces this term off for
        epochs quarantined after a gap reset -- see
        ``_es_position_quarantine``'s docstring."""
        c = self.gnss_law.cfg
        clk_event = (raw[_IDX_CLK_JUMP] >= c.es_clk_sigma) or (raw[_IDX_DRIFT_JUMP] >= c.es_clk_sigma)
        mu = self.detector.normalizer.mu
        sd = apply_sigma_floor(self.detector.normalizer.sd)
        xsat_event = raw[_IDX_XSAT_CORR] > (mu[_IDX_XSAT_CORR] + c.es_xsat_quantile_z * sd[_IDX_XSAT_CORR])
        cn0_event = raw[_IDX_CN0_MEAN] > (mu[_IDX_CN0_MEAN] + c.es_xsat_quantile_z * sd[_IDX_CN0_MEAN]
                                          + c.es_cn0_band_excess_db)

        position_event = False
        p_prior = _p_prior_from_innovations(fix, innovations)
        if (not skip_position and p_prior is not None and self._last_p_prior is not None
                and self._last_gnss_pos is not None and self._last_gnss_cov is not None):
            delta_ins = p_prior - self._last_p_prior
            delta_gnss = np.asarray(fix.pos, dtype=float) - self._last_gnss_pos
            d = delta_gnss - delta_ins
            cov_pos_now = _spd_cov_or_fallback(fix.cov_pos)
            cov_ins_short = (c.es_ins_short_sigma_pos ** 2) * np.eye(3)
            S_d = cov_pos_now + self._last_gnss_cov + cov_ins_short
            stat = float(d @ np.linalg.solve(S_d, d))
            position_event = stat > chi2.ppf(c.es_position_gate_quantile, 3)

        other_event = bool(clk_event or xsat_event or cn0_event)
        if split:
            return bool(position_event), other_event
        return bool(other_event or position_event)

    def update(self, t: float, fix: GnssFix | None, imu: ImuSample | None,
               quantum: QuantumSample | None, nav_prior: NavSolution | None,
               innovations: list[Innovation]) -> TrustState:
        imu_w = self.imu_trust.step(imu)

        gnss_w = self.gnss_law.w
        if fix is not None:
            raw = self.extractor.step(fix, innovations)
            if raw is not None and fix.valid:
                gap = float("inf") if self._last_valid_gnss_t is None else (t - self._last_valid_gnss_t)
                gap_reset_threshold = (self.gnss_law.cfg.es_gap_reset_factor
                                       * self.gnss_law.cfg.es_nominal_epoch_s)
                if gap > gap_reset_threshold:
                    # D-058 follow-up: the position-evidence baseline is
                    # stale by the whole gap (e.g. a jamming outage), not
                    # one epoch -- reset it so the position term is skipped
                    # this epoch (treated as insufficient history) instead
                    # of comparing a multi-epoch Delta p_INS against a
                    # one-epoch Delta p_GNSS (see TrustLawConfig.es_gap_
                    # reset_factor's docstring for the false-fire this
                    # prevents).
                    self._last_gnss_pos = None
                    self._last_gnss_cov = None
                    self._last_p_prior = None
                    # 2 epochs: this one (naturally skipped, no history) and
                    # the next one (the epoch after this one's large
                    # corrective pull -- see _es_position_quarantine's
                    # docstring for why one epoch alone is not enough).
                    self._es_position_quarantine = 2

                skip_position = self._es_position_quarantine > 0
                if skip_position:
                    self._es_position_quarantine -= 1

                p = self._gnss_p(raw)
                nis_ok = raw[0] <= self.gnss_law.cfg.nis_clean_threshold
                xtilde = self.detector.normalizer.normalize(raw)
                features_nominal = bool(np.all(np.abs(xtilde[2:11]) <= _FEATURES_NOMINAL_Z))
                if self.gnss_law._uses_v2:
                    es_pos, es_other = self._physical_spoof_evidence(
                        raw, fix, nav_prior, innovations, skip_position=skip_position, split=True)
                else:
                    es_pos = es_other = False
                # D-066: joint 6-D shadow NIS of this fix against the coasting state.
                shadow_inv = next((iv for iv in innovations if iv.sensor == "gnss_shadow"), None)
                shadow_nis = float(shadow_inv.nis) if shadow_inv is not None else 3.0 * float(raw[_IDX_NIS_POS])
                was_probe = self.gnss_law.probe_shadow
                self.last_raw_p = p              # D-056 metric (a): logging only, not consumed downstream
                # D-056 metric (d): logging only (position term is superseded while in PROBE)
                self.last_es_evidence = bool(es_other or (es_pos and not was_probe))
                gnss_w = self.gnss_law.step(t, p, nis_ok=nis_ok, features_nominal=features_nominal,
                                             nis_value=shadow_nis, es_evidence=es_other, es_position=es_pos)

                if gap > self.gnss_law.cfg.T_gap:
                    # D-066 shadow-consistent reacquisition: the cap exists because the first fix after
                    # an outage is untrusted; waive it only when this first fix is CONSISTENT with the
                    # coasting state (shadow NIS <= chi2_6(0.99)) AND E_s is silent. Otherwise keep the
                    # cap. tau_r is NOT changed. (Same consistency-matched-adversary limit as the probe.)
                    bound = (CHI2_6_99 if self.gnss_law.cfg.probe_nis_bound is None
                             else self.gnss_law.cfg.probe_nis_bound)
                    consistent = (self.gnss_law._uses_v2 and shadow_inv is not None and shadow_nis <= bound
                                  and not (es_other or es_pos))
                    if not consistent:
                        self.gnss_law.apply_reacquisition_cap()
                        gnss_w = self.gnss_law.w
                self._last_valid_gnss_t = t
                # D-058: keep this epoch's raw fix pos/cov for NEXT epoch's
                # short-baseline test (stored after use above, so the test
                # above still compares against the PREVIOUS epoch).
                self._last_gnss_pos = np.asarray(fix.pos, dtype=float).copy()
                self._last_gnss_cov = _spd_cov_or_fallback(fix.cov_pos)
                p_prior_now = _p_prior_from_innovations(fix, innovations)
                if p_prior_now is not None:
                    self._last_p_prior = p_prior_now

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
                           attack_detected=self.gnss_law.attack_detected,
                           probe_shadow=self.gnss_law.probe_shadow)
