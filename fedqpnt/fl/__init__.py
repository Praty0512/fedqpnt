"""Federated learning protocol, ARCHITECTURE.md S4 + S8 (WP-5.1-5.3, FEDERATED agent).

Owned by the FEDERATED agent. Must NOT import fedqpnt.node / fedqpnt.fusion /
fedqpnt.trust internals beyond the public TrustDetector/FeatureNormalizer API,
and must never import fedqpnt.sim / fedqpnt.attacks or AttackLabel/TruthState
(same leakage guard as fedqpnt.trust, enforced by tests/test_fl_leakage_guard.py).
"""
from __future__ import annotations

from fedqpnt.fl.transport import (
    Transport, MpQueueTransport, NoUpdate, Lost, Failed, RoundSkipped,
    enforce_leakage_guard,
)
from fedqpnt.fl.comms import CommsConfig, CommsChannel, uplink_channel, downlink_channel
from fedqpnt.fl.aggregator import (
    fedavg, fedprox_aggregate, staleness_weight, TrimNbRConfig, TrimNbRState,
    trim_nb_r_aggregate,
)
from fedqpnt.fl.client import ClientConfig, FLClient, LocalDatasetProvider
from fedqpnt.fl.server import ServerConfig, FLServer
from fedqpnt.fl.poisoning import sign_flip, gaussian_noise, label_flip, alie, alie_z

__all__ = [
    "Transport", "MpQueueTransport", "NoUpdate", "Lost", "Failed", "RoundSkipped",
    "enforce_leakage_guard",
    "CommsConfig", "CommsChannel", "uplink_channel", "downlink_channel",
    "fedavg", "fedprox_aggregate", "staleness_weight", "TrimNbRConfig", "TrimNbRState",
    "trim_nb_r_aggregate",
    "ClientConfig", "FLClient", "LocalDatasetProvider",
    "ServerConfig", "FLServer",
    "sign_flip", "gaussian_noise", "label_flip", "alie", "alie_z",
]
