"""M2 fleet integration (WP-6, FEDERATED agent, D-048): runs N REAL node
pipelines (fedqpnt.node Environment+Agent: real ESKF, real trust engine,
real receiver/CAI) as real processes, federated through fedqpnt.fl
(TRIM-NB-R default). Local training data is each node's own labelled
TRAINING missions, built OFFLINE (in the orchestrator process, before node
processes are spawned) via fedqpnt.fleet.local_data, which reuses
fedqpnt.training.build_supervised_dataset's real-feature / oracle-label
path (D-052/D-050) -- superseding the earlier hindsight-pseudo-label /
surrogate-feature path (REJECTED, D-050).

Does NOT edit fedqpnt/fusion/eskf.py. Only additive to fedqpnt/node (nothing
in fedqpnt/node/*.py is modified by this package -- fedqpnt/fleet builds its
own tick loop against the existing public NodeEnvironment/Agent/
make_agent_config API).

Deliberately NO submodule imports here (package __init__ stays empty of
them). ``fedqpnt.fleet.orchestrator`` imports ``fedqpnt.fleet.local_data``,
which reaches ``fedqpnt.training.build_supervised_dataset`` (the label
join) -- if this __init__ re-exported orchestrator eagerly, resolving
``fedqpnt.fleet.node_runner.run_fleet_node_process`` for a spawned node
process (which must first import the ``fedqpnt.fleet`` package) would pull
that whole chain into the node process too. Import each submodule directly,
e.g. ``from fedqpnt.fleet.orchestrator import run_fleet`` or
``from fedqpnt.fleet.node_runner import FleetNodeSpec``.
"""
from __future__ import annotations
