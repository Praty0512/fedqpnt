"""One fleet node's real process entry point: real NodeEnvironment+Agent
(closed-loop ESKF + trust engine + receiver + CAI, via fedqpnt.node's public
API only -- no edits to fedqpnt/node/*.py) + one fedqpnt.fl.client.FLClient
wrapping the SAME live ``agent.trust.detector`` instance, so an installed
global model is used by the node's trust engine from the next tick on.
"""
from __future__ import annotations

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import torch

torch.set_num_threads(1)

from fedqpnt.core.types import GlobalModel
from fedqpnt.eval import metrics as M
from fedqpnt.fl.client import ClientConfig, FLClient
from fedqpnt.fl.comms import CommsConfig, uplink_channel
from fedqpnt.fl.poisoning import sign_flip, label_flip
from fedqpnt.fl.transport import NoUpdate, Lost, Failed
from fedqpnt.fleet.features import make_round_provider
from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config

G0 = 9.80665


@dataclass
class FleetNodeSpec:
    node_id: str
    master_seed: int
    duration_s: float = 600.0
    dt: float = 0.01
    platform: str = "ground"
    world: str = "flat"
    imu_grade: str = "industrial_mems"
    quantum_grade: str | None = "field"
    gnss_rate_hz: float = 1.0
    hold_s: float = 30.0
    heading_noise_deg: float = 2.0
    attack: dict | None = None
    kappa_R: float = 40.0
    kappa_Q: float = 1.0
    method: str = "fedqpnt_local"
    round_period_s: float = 60.0
    n_rounds: int = 10
    client_cfg: ClientConfig = field(default_factory=ClientConfig)
    join_round: int = 0
    failure_round: int | None = None
    delay_window: tuple[int, int] | None = None
    poison_kind: str | None = None    # "sign_flip" | "label_flip" (node-local only, see fl/poisoning.py)
    comms_seed: int = 500
    comms_cfg: CommsConfig = field(default_factory=CommsConfig)
    # D-052/D-050: this node's PRE-BUILT local FL training dataset (real
    # features, oracle labels, built offline by the orchestrator via
    # fedqpnt.fleet.local_data.build_node_local_dataset -- see that module's
    # docstring). Plain numpy arrays only; never built inside this process.
    local_X: np.ndarray | None = None
    local_y: np.ndarray | None = None


def _level_att(f_b_mean: np.ndarray) -> tuple[float, float]:
    fx, fy, fz = f_b_mean
    phi = float(np.arctan2(fy, fz))
    theta = float(np.arctan2(-fx, np.sqrt(fy ** 2 + fz ** 2)))
    return phi, theta


def _apply_local_poison(kind: Optional[str], update):
    if kind != "sign_flip" or update is None:
        return update
    model_keys = [k for k in update.params if k not in ("norm_mu", "norm_sd", "norm_count")]
    flipped = sign_flip({k: update.params[k] for k in model_keys}, factor=-5.0)
    new_params = dict(update.params)
    new_params.update(flipped)
    update.params = new_params
    return update


def run_fleet_node_process(spec: FleetNodeSpec, theta0: dict[str, np.ndarray], server_q, down_q,
                            node_result_q) -> None:
    """Real fleet node process entry point. Guarantees exactly one result is
    put on ``node_result_q`` even on a hard failure (construction error,
    metrics-computation error, etc.), so the orchestrator's join loop never
    hangs waiting on a node that crashed outside the mission tick loop."""
    try:
        _run_fleet_node(spec, theta0, server_q, down_q, node_result_q)
    except Exception as exc:  # noqa: BLE001 - last-resort guarantee, see docstring
        node_result_q.put(dict(node_id=spec.node_id, seed=spec.master_seed, n_ticks=0, wall_s=0.0,
                                round_installs=0, failed=True, crash=repr(exc)))


def _run_fleet_node(spec: FleetNodeSpec, theta0: dict[str, np.ndarray], server_q, down_q,
                     node_result_q) -> None:
    torch.set_num_threads(1)
    t_wall0 = time.time()

    env_cfg = EnvConfig(platform=spec.platform, world=spec.world, imu_grade=spec.imu_grade,
                         quantum_grade=spec.quantum_grade, gnss_rate_hz=spec.gnss_rate_hz,
                         hold_s=spec.hold_s, heading_noise_deg=spec.heading_noise_deg,
                         attacks=[spec.attack] if spec.attack else [])
    env = NodeEnvironment(env_cfg, seed=spec.master_seed, node_id=spec.node_id, dt=spec.dt,
                           duration_s=spec.duration_s)
    agent_cfg = make_agent_config(spec.method, kappa_R=spec.kappa_R, kappa_Q=spec.kappa_Q,
                                   world=spec.world, quantum_enabled=spec.quantum_grade is not None)
    agent = Agent(agent_cfg, env.imu.config(), node_id=spec.node_id)
    agent.trust.detector.set_params({k: np.asarray(v) for k, v in theta0.items()})

    _round_provider = make_round_provider(spec.local_X, spec.local_y, spec.n_rounds)

    def _provider(nid, r):
        X, y = _round_provider(nid, r)
        if spec.poison_kind == "label_flip" and X is not None and len(X) > 0:
            y = label_flip(np.asarray(y, dtype=float))
        return X, y

    client = FLClient(spec.node_id, _provider, agent.trust.detector, spec.client_cfg,
                       rng=np.random.default_rng(spec.master_seed))
    client.last_installed_round = -1
    up = uplink_channel(spec.comms_seed, spec.node_id, spec.comms_cfg)

    f_b_hold: list[np.ndarray] = []
    initialized = False
    rows_t, rows_pos, rows_vel, rows_cov = [], [], [], []
    rows_w_gnss, rows_detected, rows_true_pos, rows_true_vel, rows_active = [], [], [], [], []
    rows_score: list[float] = []   # H2/H4 preview: max detector anomaly score per tick (AUC)
    round_installs = 0
    current_round = 0

    def _do_fl_round(r: int) -> None:
        nonlocal round_installs
        if r < spec.join_round:
            return
        if spec.failure_round is not None and r == spec.failure_round:
            server_q.put((spec.node_id, r, Failed(node_id=spec.node_id, round_idx=r)))
            raise _NodeFailed()
        if spec.delay_window is not None and spec.delay_window[0] <= r <= spec.delay_window[1]:
            server_q.put((spec.node_id, r, NoUpdate(node_id=spec.node_id, round_idx=r, reason="scripted_delay")))
        else:
            update = client.local_round(r)
            if update is None:
                server_q.put((spec.node_id, r, NoUpdate(node_id=spec.node_id, round_idx=r)))
            else:
                update = _apply_local_poison(spec.poison_kind, update)
                outcome = up.send()
                if outcome.lost:
                    server_q.put((spec.node_id, r, Lost(node_id=spec.node_id, round_idx=r, direction="up")))
                else:
                    server_q.put((spec.node_id, r, update))
        try:
            _recv_round, reply = down_q.get(timeout=600.0)
        except Exception:
            raise _NodeFailed()
        if isinstance(reply, tuple):
            global_model, _delay_s = reply
            client.install_global(global_model.params, global_model.round_idx)
            round_installs += 1
        # Lost / RoundSkipped: keep the currently-installed model.

    class _NodeFailed(Exception):
        pass

    failed = False
    try:
        for k in range(len(env)):
            tick = env.tick(k)
            t = tick.t

            if not initialized:
                if t < env.hold_s:
                    if tick.imu is not None:
                        f_b_hold.append(tick.imu.f_b)
                    continue
                f_mean = np.mean(f_b_hold, axis=0) if f_b_hold else np.array([0.0, 0.0, G0])
                phi0, theta0_ = _level_att(f_mean)
                psi0 = float(tick.truth.att[2]) + env.initial_heading_noise()
                pos0 = tick.truth.pos.copy()
                agent.initialize_static(t, pos0, np.array([phi0, theta0_, psi0]))
                initialized = True
                continue

            atick = agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)

            rows_t.append(t)
            rows_pos.append(atick.nav.pos.copy())
            rows_vel.append(atick.nav.vel.copy())
            rows_cov.append(np.diag(atick.nav.cov_pos).copy())
            rows_w_gnss.append(atick.trust.weights.get("gnss", 1.0))
            rows_detected.append(bool(atick.trust.attack_detected))
            rows_true_pos.append(tick.truth.pos.copy())
            rows_true_vel.append(tick.truth.vel.copy())
            rows_active.append(bool(tick.label.spoofing or tick.label.jamming))
            scores = atick.trust.anomaly_scores
            rows_score.append(float(max(scores.values())) if scores else 0.0)

            target_round = min(int(t // spec.round_period_s), spec.n_rounds)
            while current_round < target_round:
                _do_fl_round(current_round)
                current_round += 1
    except Exception:
        failed = True

    while not failed and current_round < spec.n_rounds:
        try:
            _do_fl_round(current_round)
        except Exception:
            failed = True
            break
        current_round += 1

    t_arr = np.array(rows_t)
    result: dict[str, Any] = dict(node_id=spec.node_id, seed=spec.master_seed, n_ticks=len(t_arr),
                                   wall_s=time.time() - t_wall0, round_installs=round_installs, failed=failed)
    if len(t_arr) > 0:
        pos_est, pos_true = np.array(rows_pos), np.array(rows_true_pos)
        vel_est, vel_true = np.array(rows_vel), np.array(rows_true_vel)
        cov_diag = np.array(rows_cov)
        w_gnss = np.array(rows_w_gnss)
        active = np.array(rows_active, dtype=bool)
        detected = np.array(rows_detected, dtype=bool)
        scores = np.array(rows_score, dtype=float)
        e_h = M.horizontal_error(pos_est, pos_true)
        e_3 = M.full3d_error(pos_est, pos_true)
        e_v = M.velocity_error(vel_est, vel_true)
        phases = M.compute_phases(t_arr, active)
        rmse_h_pre = M.rmse(e_h, phases.pre)
        result.update(dict(
            rmse_h_pre=rmse_h_pre, max_h_pre=M.max_err(e_h, phases.pre),
            rmse_h_att=M.rmse(e_h, phases.att), max_h_att=M.max_err(e_h, phases.att),
            rmse_h_post=M.rmse(e_h, phases.post),
            rmse_3_att=M.rmse(e_3, phases.att), rmse_v_att=M.rmse(e_v, phases.att),
            anees_pos_pre=M.anees_pos(pos_est, pos_true, cov_diag, phases.pre),
            latency_on=M.detection_latency(t_arr, detected, phases),
            t_dist=M.time_to_distrust(t_arr, w_gnss, phases),
            mean_w_gnss=float(np.mean(w_gnss)),
            auc=M.roc_auc(scores, active),
            **M.false_alarm_rate(t_arr, detected, active),
        ))
    node_result_q.put(result)
