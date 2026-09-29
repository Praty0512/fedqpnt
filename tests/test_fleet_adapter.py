"""D-059: B-cont/B-bin ("local-only") fleet methods must not be frozen at
theta0. fedqpnt.eval.fleet_adapter._run_local_only_fleet runs each node as
its OWN 1-node federation (aggregator="fedavg", N=1 => identity: exactly
local training, no clipping/trimming reference and no cross-node update
possible by construction) instead of the earlier n_rounds=0 mapping that
skipped node_runner's local training entirely (it is only invoked from
inside an FL round).

Spawns real multiprocessing (fedqpnt.fleet.orchestrator.run_fleet), so this
is a slower integration test, not a fast unit test -- kept in its own file
rather than tests/test_eval_campaign.py (which deliberately stays
subprocess-free). Short duration_s/hold_s/round_period_s keep it quick.
"""
from __future__ import annotations

import pytest

from fedqpnt.eval import fleet_adapter as FA
from fedqpnt.fl.client import ClientConfig
from fedqpnt.fl.comms import CommsConfig
from fedqpnt.fl.server import ServerConfig
from fedqpnt.fleet.orchestrator import FleetScenarioConfig

pytestmark = pytest.mark.skipif(not FA.THETA0_PATH.exists(),
                                 reason="results/fleet/theta0_d054.npz (D-054.1) not present")

# Loss-free comms for these tests: with N=1 there is no aggregation subtlety
# to exercise, and a lost uplink/downlink packet (simulated, per D-005
# seeded comms RNG) would make "did it install" flaky for reasons that have
# nothing to do with the D-059 local-training regression these tests guard.
# NOTE: uplink loss is governed by FleetScenarioConfig.comms_cfg (used by
# node_runner's uplink_channel), but DOWNLINK loss is a SEPARATE config on
# the server side (ServerConfig.comms, fl/server.py) -- both must be
# zeroed, or FLServer.aggregate_round's own `self._down(node_id).send(...)`
# can still report `outcome.lost=True` and the node correctly never installs.
_NO_LOSS_COMMS = CommsConfig(loss_g=0.0, loss_b=0.0)


def _theta0():
    return FA.load_theta0()


def _fast_cfg(node_ids: list[str], seed: int = 500, **overrides) -> FleetScenarioConfig:
    kwargs = dict(scenario_id="S8", method="baseline_b_cont", seed=seed, node_ids=node_ids,
                  n_rounds=2, round_period_s=4.0, duration_s=15.0, dt=0.01, aggregator="fedavg",
                  gnss_rate_hz=1.0, hold_s=2.0, comms_cfg=_NO_LOSS_COMMS,
                  server_cfg=ServerConfig(aggregator="fedavg", seed=seed, comms=_NO_LOSS_COMMS))
    kwargs.update(overrides)
    return FleetScenarioConfig(**kwargs)


def test_local_only_no_update_leaves_its_1node_federation():
    """Each sub-federation's node_ids has exactly one entry -- structurally
    nothing it produces can come from, or be sent to, another node. Also
    checks the merge: the combined result has exactly the requested node
    ids, nothing more/fewer."""
    theta0, param_names = _theta0()
    cfg = _fast_cfg(["node0", "node1"])
    result = FA._run_local_only_fleet(cfg, theta0, param_names, join_timeout_s=300.0)
    assert set(result.node_results.keys()) == {"node0", "node1"}
    assert not result.aborted, result.abort_reason


def test_local_only_detector_hash_changes_across_rounds():
    """D-059: a B-cont node must keep doing real local SGD every round (the
    bug this fixes: n_rounds=0 froze theta0, hash_pre == hash_post_train
    for every round). Assert the provenance hash actually changes."""
    theta0, param_names = _theta0()
    cfg = _fast_cfg(["node0"])
    result = FA._run_local_only_fleet(cfg, theta0, param_names, join_timeout_s=300.0)
    assert not result.aborted, result.abort_reason
    node = result.node_results["node0"]
    prov = node.get("provenance") or []
    assert len(prov) >= 1, "no FL rounds were recorded at all -- local training never ran"
    changed = [p for p in prov if p.get("hash_pre") != p.get("hash_post_train")]
    assert changed, (f"detector parameter hash never changed across any round "
                      f"(frozen theta0 -- the D-059 bug): provenance={prov}")
    # N=1 fedavg is the identity: the node always installs its own update.
    assert node.get("round_installs", 0) >= 1


def test_local_only_installs_every_round_with_lossless_comms():
    """D-059 addendum (Master): a local-only node trains on its own
    vehicle with NO network, so it must never lose or delay its own
    update. ``_run_local_only_fleet`` now forces lossless/zero-delay comms
    on both the node uplink and the server's own downlink regardless of
    what the calling scenario's comms_cfg/server_cfg say (S9's simulated
    faults are for the FEDERATED arms only). ``min_samples=1`` isolates
    that comms-fairness guarantee from FLClient's SEPARATE, legitimate
    SS4.2 "not enough accumulated local data yet" heartbeat gate (real
    data-availability behaviour shared with the federated arms too, not a
    comms defect -- see fedqpnt/eval/fleet_adapter.py's note at the merge
    loop): with real min_samples=64 the very first round or two can
    legitimately have nothing to send yet, which is NOT what this test is
    checking."""
    theta0, param_names = _theta0()
    cfg = _fast_cfg(["node0", "node1", "node2"], n_rounds=4, round_period_s=4.0, duration_s=25.0,
                     client_cfg=ClientConfig(min_samples=1))
    result = FA._run_local_only_fleet(cfg, theta0, param_names, join_timeout_s=300.0)
    assert not result.aborted, result.abort_reason
    for node_id, node in result.node_results.items():
        assert node.get("round_installs") == cfg.n_rounds, (
            f"{node_id}: installed {node.get('round_installs')}/{cfg.n_rounds} rounds despite "
            f"lossless comms and no join/failure scheduling -- {node.get('provenance')}")


def test_local_only_join_round_is_the_only_carve_out():
    """A cold-start local-only node (join_round > 0) legitimately installs
    fewer than cfg.n_rounds rounds -- exactly the rounds from join_round
    onward, never more, never fewer (comms is lossless)."""
    theta0, param_names = _theta0()
    cfg = _fast_cfg(["node0"], n_rounds=4, round_period_s=4.0, duration_s=25.0,
                     client_cfg=ClientConfig(min_samples=1), join_round={"node0": 2})
    result = FA._run_local_only_fleet(cfg, theta0, param_names, join_timeout_s=300.0)
    assert not result.aborted, result.abort_reason
    node = result.node_results["node0"]
    assert node.get("round_installs") == cfg.n_rounds - 2, node.get("provenance")
