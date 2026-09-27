"""M2 fleet integration (WP-6, FEDERATED agent, D-048): runs N REAL node
pipelines (fedqpnt.node Environment+Agent: real ESKF, real trust engine,
real receiver/CAI) as real processes, federated through fedqpnt.fl
(TRIM-NB-R default). Local training data is each node's own REAL hindsight
pseudo-labels (fedqpnt.trust.pseudolabel), matching the existing
fedqpnt.node.methods.pretrain_detector precedent for feature extraction
(x1/x2 innovation features unavailable without touching fedqpnt/fusion/
eskf.py -- out of scope; rely on x3..x15, same documented simplification).

Does NOT edit fedqpnt/fusion/eskf.py. Only additive to fedqpnt/node (nothing
in fedqpnt/node/*.py is modified by this package -- fedqpnt/fleet builds its
own tick loop against the existing public NodeEnvironment/Agent/
make_agent_config API).
"""
from __future__ import annotations

from fedqpnt.fleet.features import FleetFeatureTracker
from fedqpnt.fleet.node_runner import FleetNodeSpec, run_fleet_node_process
from fedqpnt.fleet.orchestrator import FleetScenarioConfig, FleetResult, run_fleet

__all__ = ["FleetFeatureTracker", "FleetNodeSpec", "run_fleet_node_process",
           "FleetScenarioConfig", "FleetResult", "run_fleet"]
