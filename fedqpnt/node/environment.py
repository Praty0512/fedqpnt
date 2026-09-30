"""Node Environment half (WP-8.1, ARCHITECTURE.md section 1.3, section 0 node
boundary).

Owns truth generation, IMU, CAI (quantum), GNSS signal and the chained
attacks. Per tick it emits ONLY sensor outputs to the Agent (``EnvTick.imu``,
``.quantum``, ``.gnss_epoch`` -- the latter already passed through
``GnssEpoch.for_agent()``, i.e. ``meta`` stripped, section 4.4 leakage guard
item 1). ``EnvTick.truth``, ``.label`` and the true clock
(``.true_clk_bias_m`` / ``.true_clk_drift_mps``, read from the environment's
private ``GnssEpoch.meta`` before stripping) are evaluator-only: the runner
must log them to a separate ``truth``/``labels`` recorder stream and never
hand them to ``fedqpnt.node.agent``.

This module is Environment-side and MAY import ``fedqpnt.sim``/
``fedqpnt.attacks`` freely -- unlike ``fedqpnt/node/agent.py``, which must
not (enforced by ``tests/test_node_leakage_guard.py``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from fedqpnt.core.seeding import stream
from fedqpnt.core.types import AttackLabel, GnssEpoch, ImuSample, QuantumSample, TruthState
from fedqpnt.sim.rotations import euler_to_dcm
from fedqpnt.sim.trajectory import make_trajectory
from fedqpnt.sensors.imu import ClassicalImu
from fedqpnt.sensors.quantum import QuantumAccelerometer
from fedqpnt.gnss.signal import GnssSignalModel
from fedqpnt.attacks.spoofing import AbruptSpoof, DriftInSpoof, MeaconingReplay
from fedqpnt.attacks.jamming import Jamming
from fedqpnt.attacks.meaconing_displaced import DisplacedMeaconing

G0 = 9.80665

# Attack-kind -> constructor. Keys match ``AttackSpec.kind``
# (fedqpnt.sim.config), values consume {onset_s, duration_s, severity, **params}.
# PROPOSED-DECISION: "jam_then_spoof" (fedqpnt.attacks.jamming.JamThenSpoof)
# needs two pre-built sub-attack objects, not scalar kwargs, so it is not
# wired into this generic single-kind builder; not needed by the M1 smoke
# matrix (single-attack-per-scenario). A future runner wanting it should
# construct it directly and pass it via a different code path.
_ATTACK_CTORS = {
    "drift_spoof": DriftInSpoof,
    "meaconing": MeaconingReplay,
    "meaconing_displaced": DisplacedMeaconing,
    "abrupt_spoof": AbruptSpoof,
    "jam_cw": lambda **kw: Jamming(kind="jam_cw", **kw),
    "jam_wideband": lambda **kw: Jamming(kind="jam_wideband", **kw),
}


def build_attack(kind: str, onset_s: float, duration_s: float | None, severity: float, params: dict | None = None):
    if kind in (None, "none", ""):
        return None
    if kind not in _ATTACK_CTORS:
        raise ValueError(f"unknown attack kind '{kind}'; choose from {sorted(_ATTACK_CTORS)}")
    params = dict(params or {})
    return _ATTACK_CTORS[kind](onset_s=onset_s, duration_s=duration_s, severity=severity, **params)


@dataclass
class EnvConfig:
    platform: str = "ground"                 # "ground" | "uav"
    world: str = "flat"
    imu_grade: str = "industrial_mems"
    quantum_grade: str | None = "field"       # None disables the CAI entirely (D-021: FIELD is primary)
    quantum_pointing: str = "rigid"
    quantum_outlier_channel: bool = True
    gnss_rate_hz: float = 1.0
    hold_s: float = 30.0                      # section 2.9 stationary alignment segment
    heading_noise_deg: float = 2.0
    # list of {"kind", "onset_s", "duration_s", "severity", "params": {}}
    attacks: list[dict] = field(default_factory=list)
    # D-068/S11: environment-side noise scaling, the filter is NOT told (its noise model is unchanged):
    # {"imu": k (x all IMU noise/bias magnitudes), "gnss": k (x pseudorange/Doppler sigma), "cai_contrast_div": k
    # (CAI shot noise x k, i.e. contrast / k)}. None = off (default; bit-identical to the pre-D-068 behaviour).
    noise_scale: dict | None = None

    def config(self) -> dict[str, Any]:
        d = dict(platform=self.platform, world=self.world, imu_grade=self.imu_grade,
                 quantum_grade=self.quantum_grade, quantum_pointing=self.quantum_pointing,
                 quantum_outlier_channel=self.quantum_outlier_channel, gnss_rate_hz=self.gnss_rate_hz,
                 hold_s=self.hold_s, heading_noise_deg=self.heading_noise_deg, attacks=list(self.attacks))
        if self.noise_scale:
            d["noise_scale"] = dict(self.noise_scale)
        return d


@dataclass(frozen=True)
class EnvTick:
    t: float
    imu: ImuSample | None
    quantum: QuantumSample | None
    gnss_epoch: GnssEpoch | None          # already ``.for_agent()``-stripped; safe to hand to the Agent
    # --- evaluator-only, MUST NOT reach fedqpnt.node.agent ---
    truth: TruthState
    label: AttackLabel
    true_clk_bias_m: float
    true_clk_drift_mps: float
    # D-068 (latency_eff): truth-side |reported - true| position offset injected by the attack chain on this
    # GNSS epoch (epoch.meta["injected_offset_m"], 0.0 when no attack reports it). NaN on ticks with no epoch.
    injected_offset_m: float = float("nan")


class NodeEnvironment:
    """Environment half of one node (section 0). ``len(env)`` = tick count."""

    def __init__(self, cfg: EnvConfig, seed: int, node_id: str = "node0", dt: float = 0.01,
                 duration_s: float = 600.0):
        self.cfg = cfg
        self.seed = seed
        self.node_id = node_id
        self.dt = float(dt)

        rng_traj = stream(seed, node_id, "traj")
        rng_init = stream(seed, node_id, "init")
        self._rng_imu = stream(seed, node_id, "imu")
        self._rng_q = stream(seed, node_id, "quantum")
        self._rng_gnss = stream(seed, node_id, "gnss")
        self._rng_attack = stream(seed, node_id, "attack")

        traj = make_trajectory(cfg.platform)
        self._states = self._build_truth_with_hold(traj, duration_s, dt, rng_traj, cfg.hold_s, cfg.world)

        self.imu = ClassicalImu(grade=cfg.imu_grade, rng=self._rng_imu, world=cfg.world)
        self.quantum = (QuantumAccelerometer(grade=cfg.quantum_grade, rng=self._rng_q, world=cfg.world,
                                              pointing=cfg.quantum_pointing,
                                              outlier_channel=cfg.quantum_outlier_channel)
                        if cfg.quantum_grade else None)
        self.gnss_signal = GnssSignalModel(rate_hz=cfg.gnss_rate_hz)
        self._attacks = [build_attack(a["kind"], a.get("onset_s", 30.0), a.get("duration_s"),
                                       a.get("severity", 0.5), a.get("params"))
                          for a in cfg.attacks]

        self.heading_noise_rad = np.radians(cfg.heading_noise_deg) * rng_init.normal()

        self._ns = dict(cfg.noise_scale) if cfg.noise_scale else None
        if self._ns:
            self._rng_ns = stream(seed, node_id, "noise_scale")
            k_imu = float(self._ns.get("imu", 1.0))
            if k_imu != 1.0:
                self._scale_imu_noise(k_imu)

    def _scale_imu_noise(self, k: float) -> None:
        """Replaces the IMU's error channels by copies with every noise/bias magnitude x k. The IMU's
        ``config()`` (what the filter reads) is left untouched: the filter is NOT told (S11)."""
        import dataclasses
        from fedqpnt.sensors.imu import _AxisChannel
        noisy = ("turn_on_bias_std", "bias_instability", "random_walk", "rate_random_walk")
        for name in ("accel", "gyro"):
            p0 = getattr(self.imu._cfg, name)
            p1 = dataclasses.replace(p0, **{f: getattr(p0, f) * k for f in noisy})
            ch = getattr(self.imu, f"_{name}_ch")
            setattr(self.imu, f"_{name}_ch",
                    _AxisChannel(p1, self.imu._dt, self.imu._rng_init, replay_source=ch.replay_source))

    def _apply_noise_scale(self, epoch, q_sample):
        """GNSS sigma x k and CAI contrast / k as extra ZERO-MEAN white noise of std sqrt(k^2-1) x the nominal
        sigma (independent draws from a dedicated RNG stream, so no other stream changes). For the correlated
        (Gauss-Markov) residuals this is an approximation (extra white rather than scaled correlated noise)."""
        import dataclasses
        from fedqpnt.gnss.signal import doppler_thermal_sigma_mps, uere_variance_m2
        kg = float(self._ns.get("gnss", 1.0))
        if epoch is not None and kg > 1.0:
            extra = np.sqrt(kg ** 2 - 1.0)
            for o in epoch.obs:
                o.pseudorange += self._rng_ns.normal(0.0, extra * np.sqrt(uere_variance_m2(o.elevation, o.cn0_dbhz)))
                o.pseudorange_rate += self._rng_ns.normal(0.0, extra * doppler_thermal_sigma_mps(o.cn0_dbhz))
        kc = float(self._ns.get("cai_contrast_div", 1.0))
        if q_sample is not None and kc > 1.0:
            extra = np.sqrt(kc ** 2 - 1.0)
            f = np.array(q_sample.f_b, dtype=float)
            sig = np.sqrt(np.asarray(q_sample.variance, dtype=float))
            ok = np.isfinite(f) & np.isfinite(sig)
            f[ok] += self._rng_ns.normal(0.0, 1.0, size=int(ok.sum())) * extra * sig[ok]
            q_sample = dataclasses.replace(q_sample, f_b=f)
        return epoch, q_sample

    @staticmethod
    def _build_truth_with_hold(traj, duration_s, dt, rng, hold_s, world):
        tt = traj.generate(duration_s, dt, rng, world=world)
        n_hold = int(round(hold_s / dt))
        att0, pos0 = tt.att[0], tt.pos[0]
        C0 = euler_to_dcm(att0)
        f_b0 = C0.T @ np.array([0.0, 0.0, G0])
        states: list[TruthState] = []
        for k in range(n_hold):
            states.append(TruthState(t=k * dt, pos=pos0, vel=np.zeros(3), acc=np.zeros(3), att=att0,
                                      omega_b=np.zeros(3), f_b=f_b0))
        for k in range(len(tt)):
            states.append(TruthState(t=hold_s + tt.t[k], pos=tt.pos[k], vel=tt.vel[k], acc=tt.acc[k],
                                      att=tt.att[k], omega_b=tt.omega_b[k], f_b=tt.f_b[k]))
        return states

    def __len__(self) -> int:
        return len(self._states)

    @property
    def hold_s(self) -> float:
        return self.cfg.hold_s

    def initial_heading_noise(self) -> float:
        return self.heading_noise_rad

    def _label(self, t: float) -> AttackLabel:
        if not self._attacks:
            return AttackLabel(t=t, spoofing=False, jamming=False)
        labels = [a.label(t) for a in self._attacks]
        active = [l for l in labels if l.spoofing or l.jamming]
        if not active:
            return AttackLabel(t=t, spoofing=False, jamming=False)
        return AttackLabel(t=t, spoofing=any(l.spoofing for l in active), jamming=any(l.jamming for l in active),
                            kind=active[0].kind, severity=max(l.severity for l in active))

    def tick(self, k: int) -> EnvTick:
        truth = self._states[k]
        t = truth.t
        imu_sample = self.imu.step(truth, self._rng_imu)
        q_sample = self.quantum.step(truth, self._rng_q) if self.quantum is not None else None

        epoch = self.gnss_signal.step(truth, self._rng_gnss)
        if self._ns:
            epoch, q_sample = self._apply_noise_scale(epoch, q_sample)
        true_clk_bias, true_clk_drift = float("nan"), float("nan")
        injected_offset = float("nan")
        epoch_for_agent = None
        if epoch is not None:
            for atk in self._attacks:
                epoch = atk.apply(epoch, truth, self._rng_attack)
            true_clk_bias = float(epoch.meta.get("clk_bias_m", float("nan")))
            true_clk_drift = float(epoch.meta.get("clk_drift_mps", float("nan")))
            injected_offset = float(epoch.meta.get("injected_offset_m", 0.0))    # read BEFORE for_agent() strips meta
            epoch_for_agent = epoch.for_agent()

        label = self._label(t)
        return EnvTick(t=t, imu=imu_sample, quantum=q_sample, gnss_epoch=epoch_for_agent,
                        truth=truth, label=label, true_clk_bias_m=true_clk_bias,
                        true_clk_drift_mps=true_clk_drift, injected_offset_m=injected_offset)

    def config(self) -> dict[str, Any]:
        return dict(env=self.cfg.config(), seed=self.seed, node_id=self.node_id, dt=self.dt,
                    duration_s=len(self) * self.dt)
