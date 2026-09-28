"""CAMPAIGN-FLEET: routes the 5 fleet scenarios (S5/S8/S9/S12/S15,
ARCHITECTURE.md section 6.1) through the M2 fleet orchestrator
(``fedqpnt.fleet.orchestrator``, D-050) instead of the single-node
``fedqpnt.node.runner`` path used by ``fedqpnt.eval.campaign``. Its output
already matches the campaign schema (D-050 docstring), so it is written to
the SAME ``<run_root>/<scenario_id>/<method>/seed_<seed>.json`` layout as
single-node runs and consumed unchanged by
``fedqpnt.eval.campaign.load_results`` / ``fedqpnt.eval.report``.

EVALUATOR-ONLY: imports only ``fedqpnt.fleet.orchestrator``'s public
``FleetScenarioConfig`` / ``run_fleet`` / ``write_campaign_result`` and
``fedqpnt.node.methods.load_detector_weights`` -- no edits to
``fedqpnt/fleet/*`` internals.

Method variants (D-054, task item 3), all starting from the SAME theta0
(``results/fleet/theta0_d054.npz``, D-054.1: pretrained on seeds 400-449,
restricted family set):
  - ``fedqpnt``          TRIM-NB-R aggregator, fedqpnt_local node/agent config
  - ``fedavg_ablation``  FedAvg aggregator (no trimming), same node config
  - ``baseline_a``       TRIM-NB-R aggregator, baseline_a (FL + detect-and-
                          exclude) node/agent config
  - ``baseline_b_cont`` / ``baseline_b_bin``  LOCAL-ONLY: n_rounds=0, so no
    FL round is ever exchanged (see node_runner._run_fleet_node's round
    loop: ``current_round < spec.n_rounds`` is false at n_rounds=0) -- the
    node still runs through the same fleet pipeline (comms/server spawned,
    0 rounds) so metrics stay directly comparable, rather than diverging
    onto a different code path for these methods.

PROPOSED-DECISION: the mapping above (aggregator + node-config-method per
fleet "method" name) is this agent's own choice, made because D-054 names
the method roster but not this exact wiring; flag for Master review.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from fedqpnt.eval import scenarios as SC
from fedqpnt.fl.client import ClientConfig
from fedqpnt.fl.comms import CommsConfig
from fedqpnt.fleet.orchestrator import FleetScenarioConfig, run_fleet, write_campaign_result
from fedqpnt.node.methods import load_detector_weights

FLEET_SCENARIO_IDS = ("S5", "S8", "S9", "S12", "S15")
THETA0_PATH = Path("results/fleet/theta0_d054.npz")

# fleet "method" name -> (aggregator, node/agent-config method name, n_rounds override or None)
_METHOD_MAP: dict[str, tuple[str, str, int | None]] = {
    "fedqpnt": ("trim_nb_r", "fedqpnt_local", None),
    "fedavg_ablation": ("fedavg", "fedqpnt_local", None),
    "baseline_a": ("trim_nb_r", "baseline_a", None),
    "baseline_b_cont": ("trim_nb_r", "baseline_b_cont", 0),   # local-only: 0 FL rounds
    "baseline_b_bin": ("trim_nb_r", "baseline_b_bin", 0),     # local-only: 0 FL rounds
}

FLEET_METHOD_ALL = tuple(_METHOD_MAP.keys())


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
                                 round_period_s: float | None = None, kappa_R: float = 40.0,
                                 kappa_Q: float = 1.0) -> FleetScenarioConfig:
    """Scenario -> FleetScenarioConfig, per ARCHITECTURE.md section 6.1's
    S5/S8/S9/S12/S15 rows (fault injection: failures, cold start, comms
    loss, poisoning, attacked-subset)."""
    if method not in _METHOD_MAP:
        raise ValueError(f"unknown fleet method {method!r}; expected one of {FLEET_METHOD_ALL}")
    aggregator, agent_method, n_rounds_override = _METHOD_MAP[method]
    n = n_nodes or scenario.fleet_size
    node_ids = _node_ids(n)
    dur = float(duration_s if duration_s is not None else scenario.duration_s)
    rp = round_period_s if round_period_s is not None else max(10.0, dur / max(n_rounds, 1))
    rounds = n_rounds if n_rounds_override is None else n_rounds_override

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


def run_fleet_task(scenario, method: str, seed: int, *, run_root: str = "runs",
                    duration_s: float | None = None, n_nodes: int | None = None, n_rounds: int = 10,
                    kappa_R: float = 40.0, kappa_Q: float = 1.0,
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
