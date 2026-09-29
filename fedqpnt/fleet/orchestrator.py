"""M2 fleet orchestrator: spawns 1 Server process (REUSED, unchanged, from
``fedqpnt.fl.orchestrator._server_main`` -- the server side is 100% generic
over the data source, so no new server code is needed) + N real fleet-node
processes (``fedqpnt.fleet.node_runner.run_fleet_node_process``). Writes one
result file per (scenario_id, method, seed) matching
``fedqpnt.eval.campaign``'s schema (``status``/``scenario_id``/``method``/
``seed``/``config_hash``/``wall_s``/``metrics``) so
``fedqpnt.eval.campaign.load_results`` / the report generator can consume it.
"""
from __future__ import annotations

from fedqpnt.core.defaults import DEFAULT_KAPPA_R

import hashlib
import json
import multiprocessing as mp
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import torch

torch.set_num_threads(1)

from fedqpnt.fl.orchestrator import ScenarioConfig as FLScenarioConfig, _server_main
from fedqpnt.fl.server import ServerConfig
from fedqpnt.fl.client import ClientConfig
from fedqpnt.fl.comms import CommsConfig
from fedqpnt.fleet.local_data import build_node_local_dataset
from fedqpnt.fleet.node_runner import FleetNodeSpec, run_fleet_node_process


@dataclass
class FleetScenarioConfig:
    scenario_id: str
    method: str = "fedqpnt_local"
    seed: int = 500
    node_ids: list[str] = field(default_factory=list)
    n_rounds: int = 10
    round_period_s: float = 60.0
    duration_s: float = 600.0
    dt: float = 0.01
    aggregator: str = "trim_nb_r"
    server_cfg: ServerConfig | None = None
    client_cfg: ClientConfig = field(default_factory=ClientConfig)
    comms_cfg: CommsConfig = field(default_factory=CommsConfig)
    attacks: dict[str, dict] = field(default_factory=dict)          # node_id -> attack spec (S12/S15 subset)
    join_round: dict[str, int] = field(default_factory=dict)        # SS4.7 cold start
    failure_round: dict[str, int] = field(default_factory=dict)     # S5
    delay_window: dict[str, tuple[int, int]] = field(default_factory=dict)   # S5
    poison_kind: dict[str, str] = field(default_factory=dict)       # S12/S15 (node-local: sign_flip/label_flip)
    kappa_R: float = DEFAULT_KAPPA_R
    kappa_Q: float = 1.0
    gnss_rate_hz: float = 1.0
    hold_s: float = 30.0
    # D-052/D-050: each node's own local FL training dataset -- real
    # labelled TRAINING missions (fedqpnt.fleet.local_data), NOT the live
    # fleet mission this scenario evaluates. node_id -> training seeds /
    # attack-mix pool; a node absent from these dicts falls back to a
    # small deterministic default (below) so plumbing runs need not name
    # every node explicitly.
    local_train_seeds: dict[str, list[int]] = field(default_factory=dict)
    local_train_pool: dict[str, str] = field(default_factory=dict)     # "mixed" | "clean" (see plan_for)
    local_train_duration_s: float = 60.0
    local_train_workers: int = 1

    def to_fl_scenario(self, theta0_param_names: list[str]) -> FLScenarioConfig:
        return FLScenarioConfig(node_ids=self.node_ids, n_rounds=self.n_rounds, seed=self.seed,
                                 aggregator=self.aggregator, server_cfg=self.server_cfg,
                                 comms_cfg=self.comms_cfg, join_round=self.join_round,
                                 failure_round=self.failure_round, delay_window=self.delay_window,
                                 poison_kind=self.poison_kind)

    def config_hash(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True, default=str).encode("utf8")
        return hashlib.sha256(blob).hexdigest()[:16]


@dataclass
class FleetResult:
    node_results: dict[str, dict]
    server_log: list[dict]
    aborted: bool
    abort_reason: str
    wall_s: float
    final_theta: dict[str, np.ndarray] | None = None   # D-054: final global model, for offline eval


def _default_local_train_seeds(scenario: FleetScenarioConfig, node_id: str) -> list[int]:
    """A node absent from ``scenario.local_train_seeds`` gets 2 deterministic
    training seeds derived from the scenario seed + its position in
    ``node_ids``, so different nodes get different (but reproducible)
    training missions without every caller having to name them."""
    idx = scenario.node_ids.index(node_id) if node_id in scenario.node_ids else 0
    base = 100_000 + scenario.seed * 100 + idx * 10
    return [base, base + 1]


def _node_local_dataset(scenario: FleetScenarioConfig, node_id: str) -> tuple:
    """D-052/D-050: builds this node's own local FL training dataset from
    real labelled TRAINING missions -- in THIS (parent) process, before the
    node process is spawned. See ``fedqpnt.fleet.local_data`` module
    docstring for why this must not run inside the node process."""
    seeds = scenario.local_train_seeds.get(node_id) or _default_local_train_seeds(scenario, node_id)
    pool = scenario.local_train_pool.get(node_id, "mixed")
    return build_node_local_dataset(seeds, pool=pool, duration_s=scenario.local_train_duration_s,
                                     n_workers=scenario.local_train_workers)


def _node_spec_for(scenario: FleetScenarioConfig, node_id: str) -> FleetNodeSpec:
    local_X, local_y = _node_local_dataset(scenario, node_id)
    return FleetNodeSpec(
        node_id=node_id, master_seed=scenario.seed, duration_s=scenario.duration_s, dt=scenario.dt,
        gnss_rate_hz=scenario.gnss_rate_hz, hold_s=scenario.hold_s, kappa_R=scenario.kappa_R,
        kappa_Q=scenario.kappa_Q, method=scenario.method, round_period_s=scenario.round_period_s,
        n_rounds=scenario.n_rounds, client_cfg=scenario.client_cfg,
        join_round=scenario.join_round.get(node_id, 0), failure_round=scenario.failure_round.get(node_id),
        delay_window=scenario.delay_window.get(node_id), poison_kind=scenario.poison_kind.get(node_id),
        comms_seed=scenario.seed, comms_cfg=scenario.comms_cfg, attack=scenario.attacks.get(node_id),
        local_X=local_X, local_y=local_y,
    )


def run_fleet(scenario: FleetScenarioConfig, theta0: dict[str, np.ndarray], param_names: list[str],
              join_timeout_s: float = 1800.0) -> FleetResult:
    """Spawns 1 server + len(node_ids) real fleet-node processes, runs the
    full fleet mission with FL rounds interleaved, joins, and returns a
    ``FleetResult``. Federations/fleets must be run one at a time by the
    caller (this function itself only ever runs ONE)."""
    t0 = time.time()
    ctx = mp.get_context("spawn")
    server_q = ctx.Queue()
    down_qs = {nid: ctx.Queue() for nid in scenario.node_ids}
    result_q = ctx.Queue()
    node_result_q = ctx.Queue()

    fl_scenario = scenario.to_fl_scenario(param_names)
    server_proc = ctx.Process(target=_server_main,
                               args=(fl_scenario, param_names, theta0, server_q, down_qs, result_q))
    node_procs = {
        nid: ctx.Process(target=run_fleet_node_process,
                          args=(_node_spec_for(scenario, nid), theta0, server_q, down_qs[nid], node_result_q))
        for nid in scenario.node_ids
    }

    server_proc.start()
    for p in node_procs.values():
        p.start()

    result = None
    node_results: dict[str, dict] = {}
    deadline = time.time() + join_timeout_s
    while time.time() < deadline:
        if result is None and not result_q.empty():
            result = result_q.get()
        while not node_result_q.empty():
            nr = node_result_q.get()
            node_results[nr["node_id"]] = nr
        if result is not None and len(node_results) >= len(scenario.node_ids):
            break
        if not server_proc.is_alive() and result is None:
            break
        time.sleep(0.05)

    server_proc.join(timeout=30)
    for p in node_procs.values():
        p.join(timeout=30)
        if p.is_alive():
            p.terminate()
    if server_proc.is_alive():
        server_proc.terminate()
    while not node_result_q.empty():
        nr = node_result_q.get()
        node_results[nr["node_id"]] = nr

    aborted = result is None or result.get("aborted", False)
    abort_reason = "" if result is None else result.get("abort_reason", "")
    if result is None:
        abort_reason = abort_reason or "watchdog timeout / server crash before producing a result"
    return FleetResult(node_results=node_results, server_log=(result or {}).get("log", []),
                        aborted=aborted, abort_reason=abort_reason, wall_s=time.time() - t0,
                        final_theta=(result or {}).get("theta"))


def write_campaign_result(scenario: FleetScenarioConfig, result: FleetResult,
                           run_root: str = "runs_fleet") -> Path:
    """Writes ``<run_root>/<scenario_id>/<method>/seed_<seed>.json`` matching
    ``fedqpnt.eval.campaign``'s per-run schema (status/scenario_id/method/
    seed/config_hash/wall_s/metrics), so the report generator (or
    ``fedqpnt.eval.campaign.load_results``) can consume it. ``metrics`` is a
    flat dict of the per-node mean of each scalar metric (report-compatible)
    plus ``metrics["nodes"]`` with the full per-node breakdown and
    ``metrics["fleet"]`` with fleet-only fields (rounds skipped, quarantine
    events, wall time per fleet-hour)."""
    out_path = Path(run_root) / scenario.scenario_id / scenario.method / f"seed_{scenario.seed}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    node_metrics = result.node_results
    # CAMPAIGN-FLEET additive hook (D-054/D-056 §6.1 fleet criteria need
    # per-run AUC and install-count aggregates alongside the existing
    # nav/trust scalars; backward compatible -- purely appends keys, never
    # removes or renames any existing one):
    scalar_keys = [k for k in ("rmse_h_pre", "rmse_h_att", "rmse_h_post", "rmse_3_att", "rmse_v_att",
                                "anees_pos_pre", "latency_on", "t_dist", "mean_w_gnss", "auc",
                                "auc_detector_only", "round_installs", "far_per_hour", "fpr")
                   if any(k in v for v in node_metrics.values())]
    flat: dict[str, float] = {}
    for k in scalar_keys:
        vals = [v[k] for v in node_metrics.values() if k in v]
        vals = [v for v in vals if isinstance(v, (int, float)) and np.isfinite(v)]
        if vals:
            flat[k] = float(np.mean(vals))

    n_skipped = sum(1 for e in result.server_log if e.get("event") == "ROUND_SKIPPED")
    n_quarantine = sum(1 for e in result.server_log if e.get("event") == "QUARANTINE")
    fleet_hours = (scenario.duration_s * max(len(scenario.node_ids), 1)) / 3600.0
    flat.update(dict(nodes=node_metrics,
                      fleet=dict(rounds_skipped=n_skipped, quarantine_events=n_quarantine,
                                  wall_s=result.wall_s,
                                  wall_s_per_fleet_hour=(result.wall_s / fleet_hours) if fleet_hours > 0 else None,
                                  n_nodes=len(scenario.node_ids), aborted=result.aborted,
                                  abort_reason=result.abort_reason, server_log=result.server_log)))

    record = dict(status="ok" if not result.aborted else "error", scenario_id=scenario.scenario_id,
                   method=scenario.method, seed=scenario.seed, config_hash=scenario.config_hash(),
                   wall_s=result.wall_s, metrics=flat)
    out_path.write_text(json.dumps(record, default=str, indent=2))
    return out_path
