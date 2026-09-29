"""Node Agent half (WP-8.1, ARCHITECTURE.md section 1.3, section 0 node
boundary): GnssReceiver -> ESKF (propagate -> innovations -> TrustEngine.update
-> correct) -> NavSolution, plus the standalone clock KF (D-025/D-027).

CONTRACT: this module and everything it imports must NEVER import
``fedqpnt.sim``, ``fedqpnt.attacks``, ``AttackLabel`` or ``TruthState``
(section 4.4 leakage guard item 2, extended here to the node boundary and
enforced by ``tests/test_node_leakage_guard.py``, which walks this module's
whole ``fedqpnt``-internal import graph, not just its direct imports).

Integration note (PROPOSED-DECISION, most-conservative reading of an
unspecified contract interaction): ``ESKF.innovations()`` (fedqpnt/fusion/
eskf.py, out of scope for this agent) emits ONE joint 6-D ``Innovation``
(sensor="gnss", dof=6) for the position+velocity GNSS update, but
``fedqpnt.trust.features.GnssFeatureExtractor`` (x1/x2) looks for two
SEPARATE 3-D innovations named "gnss_pos"/"gnss_vel" -- exactly the
per-block form ARCHITECTURE.md section 3.1 specifies
(``nu_p^T (H_p P^- H_p^T + R_p)^-1 nu_p``, using only the position block,
never the joint 6x6). ``_split_gnss_innovation`` below reproduces that
per-block split from the ESKF's joint innovation (dropping the pos/vel
cross-covariance block, which the spec's block formula never included
either) purely for the trust engine's feature input; the ESKF's own
``correct()`` still uses its own internal joint-6D pending state and ignores
the ``innovations`` list argument for anything but bookkeeping, so nothing
about the actual EKF correction is affected by this split.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from fedqpnt.core.defaults import DEFAULT_KAPPA_R
from fedqpnt.core.types import GnssFix, ImuSample, Innovation, NavSolution, QuantumSample, TrustState
from fedqpnt.fusion.eskf import ESKF, ESKFConfig
from fedqpnt.fusion.clock import ClockKF, ClockKFConfig, ClockSolution
from fedqpnt.gnss.receiver import GnssReceiver
from fedqpnt.trust.trust_law import TrustEngineConfig, TrustEngineImpl, make_method_config


def _split_gnss_innovation(innovations: list[Innovation]) -> list[Innovation]:
    """See module docstring. Passes quantum/other innovations through
    unchanged; the joint "gnss" (dof=6) innovation becomes "gnss_pos" +
    "gnss_vel" (dof=3 each, diagonal S blocks only)."""
    out: list[Innovation] = []
    for inv in innovations:
        if inv.sensor != "gnss":
            out.append(inv)
            continue
        nu, S = inv.nu, inv.S
        nu_p, nu_v = nu[0:3], nu[3:6]
        S_pp, S_vv = S[0:3, 0:3], S[3:6, 3:6]
        nis_p = float(nu_p @ np.linalg.solve(S_pp, nu_p))
        nis_v = float(nu_v @ np.linalg.solve(S_vv, nu_v))
        out.append(Innovation(t=inv.t, sensor="gnss_pos", nu=nu_p, S=S_pp, nis=nis_p, dof=3,
                               accepted=inv.accepted))
        out.append(Innovation(t=inv.t, sensor="gnss_vel", nu=nu_v, S=S_vv, nis=nis_v, dof=3,
                               accepted=inv.accepted))
    return out


@dataclass
class AgentConfig:
    world: str = "flat"
    kappa_R: float = DEFAULT_KAPPA_R  # D-061/D-067 (was PROVISIONAL 40) (D-023/D-027 tuning-seed procedure, section 7.6).
                                      # D-028: the ESKF process model is being changed concurrently
                                      # (dynamics-dependent Q inflation), which changes the P this
                                      # value was tuned against -- re-tune with scripts/tune_kappa_r.py
                                      # once that lands; see results/m1/kappa_r_frozen.json.
    kappa_Q: float = 1.0
    alpha_gate: float = 1e-4         # 0.0 disables the NIS gate ("undefended", section 6.1 S1 note)
    trust: TrustEngineConfig = field(default_factory=TrustEngineConfig)
    clock: ClockKFConfig = field(default_factory=ClockKFConfig)
    detector_weights: dict[str, np.ndarray] | None = None   # see methods.py: pretrained / locally-trained state

    def config(self) -> dict[str, Any]:
        return dict(world=self.world, kappa_R=self.kappa_R, kappa_Q=self.kappa_Q,
                    alpha_gate=self.alpha_gate, trust=dict(method=self.trust.method,
                    law_mode=self.trust.law_mode, quantum_enabled=self.trust.quantum_enabled,
                    p_source=self.trust.p_source, detector_arch=self.trust.detector_arch))


@dataclass(frozen=True)
class AgentTick:
    t: float
    nav: NavSolution
    trust: TrustState
    clock: ClockSolution | None
    fix: GnssFix | None


class Agent:
    """Agent half of one node: receiver -> ESKF -> trust -> clock KF."""

    def __init__(self, cfg: AgentConfig, imu_config: dict[str, Any], node_id: str = "node0"):
        self.cfg = cfg
        self.node_id = node_id
        self.receiver = GnssReceiver()
        eskf_cfg = ESKFConfig(world=cfg.world, kappa_R=cfg.kappa_R, kappa_Q=cfg.kappa_Q,
                               alpha_gate=cfg.alpha_gate)
        self.eskf = ESKF(imu_config, config=eskf_cfg)
        self.trust = TrustEngineImpl(cfg.trust, node_id=node_id)
        if cfg.detector_weights:
            self.trust.detector.set_params(cfg.detector_weights)
        self.clock = ClockKF(cfg.clock)
        self._last_nav: NavSolution | None = None

    def config(self) -> dict[str, Any]:
        return dict(agent=self.cfg.config(), eskf=self.eskf.config(), trust=self.trust.config(),
                    clock=self.clock.config())

    def initialize_static(self, t0: float, pos0: np.ndarray, att0: np.ndarray,
                           vel0: np.ndarray | None = None) -> None:
        self.eskf.initialize_static(t0, pos0, att0, vel0=vel0)
        self.clock.initialize(t0, bias0=0.0, drift0=0.0)

    def step(self, t: float, imu: ImuSample | None, quantum: QuantumSample | None,
             gnss_epoch) -> AgentTick:
        fix: GnssFix | None = None
        if gnss_epoch is not None:
            fix = self.receiver.solve(gnss_epoch)
            if not fix.valid:
                fix = None

        self.eskf.propagate(t, imu)
        innovations = self.eskf.innovations(t, fix, quantum)
        trust_state = self.trust.update(t, fix, imu, quantum, self._last_nav,
                                         _split_gnss_innovation(innovations))
        nav = self.eskf.correct(t, innovations, trust_state)
        clk = self.clock.step(t, fix, trust_state.weights.get("gnss", 1.0))
        self._last_nav = nav
        return AgentTick(t=t, nav=nav, trust=trust_state, clock=clk, fix=fix)
