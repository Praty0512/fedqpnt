"""SS4.6 / SS8 comms model: sim-time uplink/downlink delay + Gilbert-Elliott
loss, RNG streams keyed exactly per spec.

Uplink: ``stream(seed, node_id, "comms_up")`` (SS4.6), one persistent
generator per node reused across rounds (the G-E chain is Markov across
rounds, so it must not be re-seeded every call).
Downlink: ``stream(seed, "server", "comms_down", node_id)`` (SS8 step 2),
one persistent generator per node, owned by the server.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from fedqpnt.core.seeding import stream


@dataclass
class CommsConfig:
    bitrate_bps: float = 1_000_000.0     # B = 1 Mbit/s
    d_max_s: float = 5.0                 # beyond this, message is lost
    delay_mu_ln: float = float(np.log(0.2))
    delay_sigma_ln: float = 0.5
    p_gb: float = 0.02                   # P(Good -> Bad)
    p_bg: float = 0.3                    # P(Bad -> Good)
    loss_g: float = 0.01
    loss_b: float = 0.9


@dataclass
class MessageOutcome:
    lost: bool
    delay_s: float


@dataclass
class CommsChannel:
    """One Gilbert-Elliott + lognormal-delay stream. Stateful: call ``send``
    once per message in causal order; the G-E chain state persists."""

    rng: np.random.Generator
    cfg: CommsConfig = field(default_factory=CommsConfig)
    state: str = "G"

    def send(self, msg_size_bytes: float = 4096.0) -> MessageOutcome:
        cfg = self.cfg
        if self.state == "G":
            lost = bool(self.rng.random() < cfg.loss_g)
            if self.rng.random() < cfg.p_gb:
                self.state = "B"
        else:
            lost = bool(self.rng.random() < cfg.loss_b)
            if self.rng.random() < cfg.p_bg:
                self.state = "G"
        delay = float(self.rng.lognormal(cfg.delay_mu_ln, cfg.delay_sigma_ln)
                      + msg_size_bytes * 8.0 / cfg.bitrate_bps)
        if delay > cfg.d_max_s:
            lost = True
            delay = cfg.d_max_s
        return MessageOutcome(lost=lost, delay_s=delay)


def uplink_channel(seed: int, node_id: str, cfg: CommsConfig | None = None) -> CommsChannel:
    return CommsChannel(rng=stream(seed, node_id, "comms_up"), cfg=cfg or CommsConfig())


def downlink_channel(seed: int, node_id: str, cfg: CommsConfig | None = None) -> CommsChannel:
    return CommsChannel(rng=stream(seed, "server", "comms_down", node_id), cfg=cfg or CommsConfig())
