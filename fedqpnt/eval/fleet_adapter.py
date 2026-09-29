"""CAMPAIGN-FLEET: routes the 5 fleet scenarios (S5/S8/S9/S12/S15,
ARCHITECTURE.md section 6.1) through the M2 fleet orchestrator
(``fedqpnt.fleet.orchestrator``, D-050) instead of the single-node
``fedqpnt.node.runner`` path used by ``fedqpnt.eval.campaign``. Its output
already matches the campaign schema (D-050 docstring), so it is written to
the SAME ``<run_root>/<scenario_id>/<method>/seed_<seed>.json`` layout as
single-node runs and consumed unchanged by
``fedqpnt.eval.campaign.load_results`` / ``fedqpnt.eval.report``.

EVALUATOR-ONLY: imports only ``fedqpnt.fleet.orchestrator``'s public
``FleetScenarioConfig`` / ``FleetResult`` / ``run_fleet`` /
``write_campaign_result`` and ``fedqpnt.node.methods.load_detector_weights``
-- no edits to ``fedqpnt/fleet/*`` internals (D-059's local-only fix is
built entirely from repeated calls to the existing ``run_fleet`` public
entry point, one per node, never a change to ``fleet/node_runner.py`` or
``fleet/orchestrator.py``'s own dispatch logic).

Method variants (D-054, task item 3), all starting from the SAME theta0
(``results/fleet/theta0_d054.npz``, D-054.1: pretrained on seeds 400-449,
restricted family set):
  - ``fedqpnt``          TRIM-NB-R aggregator, fedqpnt_local node/agent config
  - ``fedavg_ablation``  FedAvg aggregator (no trimming), same node config
  - ``baseline_a``       TRIM-NB-R aggregator, baseline_a (FL + detect-and-
                          exclude) node/agent config
  - ``baseline_b_cont`` / ``baseline_b_bin``  LOCAL-ONLY (D-059 fix): each
    node runs as its OWN 1-node federation (``node_ids=[node]``,
    ``aggregator="fedavg"`` -- with N=1 that IS local training: no
    clipping/trimming reference points exist, so the "aggregate" is the
    identity on that one update), same ``n_rounds``/``round_period_s`` as
    the ``fedqpnt`` arm, so the node keeps doing real local SGD every
    round. An N-node fleet scenario therefore runs N independent 1-node
    federations for these methods (``_run_local_only_fleet`` below), never
    one shared N-node federation -- no cross-node update ever happens by
    construction (each sub-federation's ``node_ids`` has exactly one
    entry). D-059 SUPERSEDES the earlier n_rounds=0 "frozen theta0"
    mapping (Master: that was a blocking bug -- see EXECUTION_LOG).

PROPOSED-DECISION: the mapping above (aggregator + node-config-method per
fleet "method" name) is this agent's own choice, made because D-054 names
the method roster but not this exact wiring; flag for Master review.
"""
from __future__ import annotations

from fedqpnt.core.defaults import DEFAULT_KAPPA_R

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from fedqpnt.eval import scenarios as SC
from fedqpnt.fl.client import ClientConfig
from fedqpnt.fl.comms import CommsConfig
from fedqpnt.fl.server import ServerConfig
from fedqpnt.fleet.orchestrator import FleetResult, FleetScenarioConfig, run_fleet, write_campaign_result
from fedqpnt.node.methods import load_detector_weights

FLEET_SCENARIO_IDS = ("S5", "S8", "S9", "S12", "S15")
THETA0_PATH = Path("results/fleet/theta0_d054.npz")
MAX_LOCAL_ONLY_PARALLEL = 8   # D-059: cap on concurrent 1-node federations for B-cont/B-bin

# D-059 addendum (Master): a local-only node trains on its own vehicle, with
# NO network -- it must never lose or delay an update to/from itself. S9's
# simulated comms faults model the FEDERATED methods' wireless link; they
# must not leak into B-cont/B-bin's 1-node federations regardless of what
# comms_cfg/server_cfg the calling scenario carries. Forced on BOTH legs:
# the node's uplink (FleetScenarioConfig.comms_cfg) and the server's own,
# SEPARATE downlink config (ServerConfig.comms, fl/server.py) -- these are
# two independent knobs and both must be zeroed (see tests/test_fleet_
# adapter.py's note on the same gotcha). delay_sigma_ln=0 makes the
# log-normal delay deterministic at exp(delay_mu_ln) (~1 microsecond);
# p_gb=0/p_bg=1 keeps the Gilbert-Elliott channel permanently in the "good"
# state, on top of loss_g=loss_b=0.0 belt-and-braces.
_LOSSLESS_COMMS = CommsConfig(delay_mu_ln=float(np.log(1e-6)), delay_sigma_ln=0.0, p_gb=0.0, p_bg=1.0,
                               loss_g=0.0, loss_b=0.0)

# fleet "method" name -> (aggregator, node/agent-config method name, local_only)
# local_only=True (D-059): run via _run_local_only_fleet (N independent
# 1-node federations, aggregator forced to "fedavg" per sub-federation)
# instead of run_fleet (one shared N-node federation). ``aggregator`` here
# is cosmetic bookkeeping on the outer "shape" FleetScenarioConfig for
# local_only methods -- the real per-node run always uses "fedavg".
_METHOD_MAP: dict[str, tuple[str, str, bool]] = {
    "fedqpnt": ("trim_nb_r", "fedqpnt_local", False),
    "fedavg_ablation": ("fedavg", "fedqpnt_local", False),
    "baseline_a": ("trim_nb_r", "baseline_a", False),
    "baseline_b_cont": ("fedavg", "baseline_b_cont", True),
    "baseline_b_bin": ("fedavg", "baseline_b_bin", True),
}

FLEET_METHOD_ALL = tuple(_METHOD_MAP.keys())


def is_local_only(method: str) -> bool:
    return _METHOD_MAP[method][2]


class FleetTheta0Error(RuntimeError):
    pass


def load_theta0() -> tuple[dict[str, np.ndarray], list[str]]:
    p = load_detector_weights(THETA0_PATH)
    if p is None:
        raise FleetTheta0Error(
            f"{THETA0_PATH} missing -- run scripts/pretrain_theta0_d054.py first (D-054.1 theta0)")
    return p, list(p.keys())


def _node_ids(n: int) -> list[str]:
    return [f"node{i}" for i in range(n)]


def _s5_kwargs(node_ids: list[str], n_rounds: int) -> dict[str, Any]:
    # S5: 30% of nodes fail at T/2 (mid-mission round); delays 1-3 rounds
    # for a further subset -- ARCHITECTURE.md S5 row.
    n_fail = max(1, round(0.3 * len(node_ids)))
    fail_nodes = node_ids[:n_fail]
    mid_round = max(1, n_rounds // 2)
    delay_nodes = node_ids[n_fail:n_fail + max(1, round(0.2 * len(node_ids)))]
    return dict(failure_round={nid: mid_round for nid in fail_nodes},
                delay_window={nid: (1, 3) for nid in delay_nodes})


def _s8_kwargs(node_ids: list[str], n_rounds: int) -> dict[str, Any]:
    # S8: one cold-start node joins at T/2 (round index), the rest are
    # veterans from round 0.
    join_round = max(1, n_rounds // 2)
    return dict(join_round={node_ids[-1]: join_round})


def _s9_kwargs(node_ids: list[str]) -> dict[str, Any]:
    # S9: comms dropouts, loss_B in {0.5, 0.9}, P(G->B) in {0.02, 0.1} --
    # ARCHITECTURE.md S9 row. Plumbing default picks the harsher end of
    # each range; a full sweep is a config axis for a later, larger run.
    return dict(comms_cfg=CommsConfig(loss_b=0.9, p_gb=0.1))


def _s12_kwargs(node_ids: list[str], poison_frac: float = 0.2,
                 poison_kind: str = "sign_flip") -> dict[str, Any]:
    # S12: f fraction of nodes poisoned (trust-score/model poisoning).
    n_poison = max(1, round(poison_frac * len(node_ids)))
    return dict(poison_kind={nid: poison_kind for nid in node_ids[:n_poison]})


def _s15_kwargs(node_ids: list[str], attack: dict, attack_frac: float = 0.3) -> dict[str, Any]:
    # S15: 30% of nodes spoofed simultaneously, same attack kind.
    n_attacked = max(1, round(attack_frac * len(node_ids)))
    return dict(attacks={nid: attack for nid in node_ids[:n_attacked]})


def build_fleet_scenario_config(scenario, method: str, seed: int, *, n_nodes: int | None = None,
                                 duration_s: float | None = None, n_rounds: int = 10,
                                 round_period_s: float | None = None, kappa_R: float = DEFAULT_KAPPA_R,
                                 kappa_Q: float = 1.0) -> FleetScenarioConfig:
    """Scenario -> FleetScenarioConfig, per ARCHITECTURE.md section 6.1's
    S5/S8/S9/S12/S15 rows (fault injection: failures, cold start, comms
    loss, poisoning, attacked-subset)."""
    if method not in _METHOD_MAP:
        raise ValueError(f"unknown fleet method {method!r}; expected one of {FLEET_METHOD_ALL}")
    aggregator, agent_method, _local_only = _METHOD_MAP[method]
    n = n_nodes or scenario.fleet_size
    node_ids = _node_ids(n)
    dur = float(duration_s if duration_s is not None else scenario.duration_s)
    rp = round_period_s if round_period_s is not None else max(10.0, dur / max(n_rounds, 1))
    # D-059: local-only methods keep the SAME n_rounds/round_period_s as
    # fedqpnt (no more forcing rounds=0 -- that froze theta0 and starved
    # node_runner's local training, which only fires from inside an FL
    # round). This cfg's own .n_rounds/.aggregator/.node_ids are used as
    # the outer "shape" (path/hash/duration/node-count bookkeeping); for
    # local_only methods the actual execution is N independent 1-node
    # federations, see _run_local_only_fleet.
    rounds = n_rounds

    kwargs: dict[str, Any] = {}
    if scenario.id == "S5":
        kwargs.update(_s5_kwargs(node_ids, rounds))
    elif scenario.id == "S8":
        kwargs.update(_s8_kwargs(node_ids, rounds))
    elif scenario.id == "S9":
        kwargs.update(_s9_kwargs(node_ids))
    elif scenario.id == "S12":
        kwargs.update(_s12_kwargs(node_ids))
    elif scenario.id == "S15":
        kwargs.update(_s15_kwargs(node_ids, scenario.attack or dict(kind="drift_spoof", onset_s=60.0,
                                                                      duration_s=dur - 60.0, severity=0.6)))

    return FleetScenarioConfig(scenario_id=scenario.id, method=agent_method, seed=seed, node_ids=node_ids,
                                n_rounds=rounds, round_period_s=rp, duration_s=dur, aggregator=aggregator,
                                kappa_R=kappa_R, kappa_Q=kappa_Q, **kwargs)


def _run_local_only_fleet(cfg: FleetScenarioConfig, theta0: dict[str, np.ndarray], param_names: list[str],
                           join_timeout_s: float, max_parallel: int = MAX_LOCAL_ONLY_PARALLEL) -> FleetResult:
    """D-059: run each of ``cfg.node_ids`` as its OWN 1-node federation
    (``node_ids=[node_id]``, ``aggregator="fedavg"``) instead of one shared
    N-node federation, so B-cont/B-bin nodes keep doing real local SGD
    every round (node_runner only calls ``client.local_round`` from inside
    an FL round) while structurally never exchanging an update with any
    other node -- a 1-node federation has no other node to exchange with.
    Sub-federations run in parallel (thread pool fanning out separate
    ``run_fleet`` calls, each of which does its own real multiprocessing
    spawn), capped at ``max_parallel``. Merges the N independent
    ``FleetResult``s into one fleet-shaped result so the rest of the
    pipeline (``write_campaign_result``, §6.1 criteria) sees the same
    shape as a real N-node federation."""
    def _one(node_id: str) -> tuple[str, FleetResult]:
        sub = FleetScenarioConfig(
            scenario_id=cfg.scenario_id, method=cfg.method, seed=cfg.seed, node_ids=[node_id],
            n_rounds=cfg.n_rounds, round_period_s=cfg.round_period_s, duration_s=cfg.duration_s,
            dt=cfg.dt, aggregator="fedavg",
            # D-059 addendum: force lossless/zero-delay comms on BOTH legs,
            # regardless of cfg.comms_cfg/cfg.server_cfg -- S9's simulated
            # faults are for federated methods only, never a local-only node
            # talking to itself.
            server_cfg=ServerConfig(aggregator="fedavg", seed=cfg.seed, comms=_LOSSLESS_COMMS),
            client_cfg=cfg.client_cfg, comms_cfg=_LOSSLESS_COMMS,
            attacks=({node_id: cfg.attacks[node_id]} if node_id in cfg.attacks else {}),
            join_round=({node_id: cfg.join_round[node_id]} if node_id in cfg.join_round else {}),
            failure_round=({node_id: cfg.failure_round[node_id]} if node_id in cfg.failure_round else {}),
            delay_window=({node_id: cfg.delay_window[node_id]} if node_id in cfg.delay_window else {}),
            poison_kind=({node_id: cfg.poison_kind[node_id]} if node_id in cfg.poison_kind else {}),
            kappa_R=cfg.kappa_R, kappa_Q=cfg.kappa_Q, gnss_rate_hz=cfg.gnss_rate_hz, hold_s=cfg.hold_s,
            local_train_seeds=({node_id: cfg.local_train_seeds[node_id]} if node_id in cfg.local_train_seeds
                                else {}),
            local_train_pool=({node_id: cfg.local_train_pool[node_id]} if node_id in cfg.local_train_pool
                               else {}),
            local_train_duration_s=cfg.local_train_duration_s, local_train_workers=cfg.local_train_workers)
        return node_id, run_fleet(sub, theta0, param_names, join_timeout_s=join_timeout_s)

    sub_results: dict[str, FleetResult] = {}
    with ThreadPoolExecutor(max_workers=min(max_parallel, max(1, len(cfg.node_ids)))) as ex:
        for node_id, res in ex.map(_one, cfg.node_ids):
            sub_results[node_id] = res

    # D-059 addendum fairness guarantee: with comms forced lossless/
    # zero-delay above, a local-only node's ONLY legitimate reasons to
    # install fewer than ``cfg.n_rounds - join_round`` rounds are
    # scenario-scheduled (a cold-start join_round delaying its first round,
    # a scheduled failure_round ending it early). It can still separately
    # get NoUpdate/ROUND_SKIPPED for a round where its own accumulated
    # local dataset hasn't yet reached ``ClientConfig.min_samples`` (SS4.2's
    # heartbeat gate, shared with the federated arms too, since it lives in
    # fedqpnt.fl.client.FLClient) -- that is real data-availability
    # behaviour, not a comms defect, so it is deliberately NOT asserted away
    # here (doing so would make every real campaign run raise). See
    # tests/test_fleet_adapter.py::test_local_only_installs_every_round_with_lossless_comms,
    # which isolates the comms-fairness invariant with ``min_samples=1`` and
    # asserts ``round_installs == n_rounds`` exactly.
    node_results: dict[str, dict] = {}
    server_log: list[dict] = []
    aborted = False
    abort_reasons: list[str] = []
    wall_s = 0.0
    for node_id, res in sub_results.items():
        # Invariant (D-059 test): a local-only sub-federation has exactly
        # ONE node, so nothing it produced could have come from -- or been
        # sent to -- any other node.
        assert list(res.node_results.keys()) in ([node_id], []), \
            f"local-only sub-federation for {node_id!r} leaked another node's result: {res.node_results.keys()}"
        node_results.update(res.node_results)
        for e in res.server_log:
            server_log.append(dict(e, node_id=node_id))
        aborted = aborted or res.aborted
        if res.abort_reason:
            abort_reasons.append(f"{node_id}: {res.abort_reason}")
        wall_s = max(wall_s, res.wall_s)   # ran in parallel: elapsed time, not the sum

    return FleetResult(node_results=node_results, server_log=server_log, aborted=aborted,
                        abort_reason="; ".join(abort_reasons), wall_s=wall_s, final_theta=None)


def run_fleet_task(scenario, method: str, seed: int, *, run_root: str = "runs",
                    duration_s: float | None = None, n_nodes: int | None = None, n_rounds: int = 10,
                    kappa_R: float = DEFAULT_KAPPA_R, kappa_Q: float = 1.0,
                    join_timeout_s: float = 1800.0) -> dict[str, Any]:
    """Runs one fleet (scenario, method, seed) via ``run_fleet`` and writes
    a campaign-schema result file. Mirrors
    ``fedqpnt.eval.campaign._execute_one``'s return shape
    ``{scenario_id, method, seed, status}`` for the campaign dispatcher."""
    out_path = Path(run_root) / scenario.id / method / f"seed_{seed}.json"
    if out_path.exists():
        try:
            rec = json.loads(out_path.read_text())
            if rec.get("status") == "ok":
                return dict(scenario_id=scenario.id, method=method, seed=seed, status="skipped_done")
        except (json.JSONDecodeError, OSError):
            pass

    try:
        theta0, param_names = load_theta0()
    except FleetTheta0Error as exc:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        record = dict(status="error", scenario_id=scenario.id, method=method, seed=seed,
                       config_hash="no_theta0", wall_s=0.0, metrics={}, stderr=str(exc))
        out_path.write_text(json.dumps(record, default=str, indent=2))
        return dict(scenario_id=scenario.id, method=method, seed=seed, status="error")

    cfg = build_fleet_scenario_config(scenario, method, seed, n_nodes=n_nodes, duration_s=duration_s,
                                       n_rounds=n_rounds, kappa_R=kappa_R, kappa_Q=kappa_Q)
    if is_local_only(method):
        result = _run_local_only_fleet(cfg, theta0, param_names, join_timeout_s=join_timeout_s)
    else:
        result = run_fleet(cfg, theta0, param_names, join_timeout_s=join_timeout_s)

    # write_campaign_result derives its output path from cfg.scenario_id/
    # cfg.method/cfg.seed, but cfg.method is the node/agent-config method
    # name (e.g. "fedqpnt_local", "baseline_a") used by
    # fedqpnt.fleet.node_runner.make_agent_config -- NOT this campaign's
    # method label ("fedqpnt", "fedavg_ablation" ...), and two campaign
    # methods can share one agent-config method (fedqpnt/fedavg_ablation
    # both use "fedqpnt_local", differing only in aggregator). So write via
    # a scratch subdir keyed by the agent-config method, then relabel and
    # move into place under the campaign method name -- reusing
    # write_campaign_result's metric-flattening unedited rather than
    # duplicating it here.
    tmp_root = Path(run_root) / "_fleet_scratch"
    write_campaign_result(cfg, result, run_root=str(tmp_root))
    tmp_path = tmp_root / scenario.id / cfg.method / f"seed_{seed}.json"
    rec = json.loads(tmp_path.read_text())
    rec["method"] = method
    rec["kappa_R_status"] = SC.KAPPA_R_STATUS
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rec, default=str, indent=2))
    tmp_path.unlink()

    status = "error" if result.aborted else "ok"
    return dict(scenario_id=scenario.id, method=method, seed=seed, status=status)
