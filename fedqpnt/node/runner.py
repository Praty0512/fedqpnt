"""Single-node run orchestrator (WP-8.1, ARCHITECTURE.md section 8 policy
applied to one node: "runs execute as real processes (multiprocessing
spawn, one process per run) so parallel seeds use the CPU").

``run_single`` ties ``NodeEnvironment`` + ``Agent`` together for one node,
one seed, one method, writes ``runs/<id>/`` via ``fedqpnt.sim.recorder``
(config + seeds + time series; truth/labels are a SEPARATE evaluator-only
stream, per section 0/4.4), and returns a metrics dict (``fedqpnt.eval.metrics``).
``run_many`` fans a list of run specs out across a real process pool
(``multiprocessing`` "spawn" context) so wall-clock scales with the CPU.
"""
from __future__ import annotations

import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from fedqpnt.core.seeding import stream
from fedqpnt.eval import metrics as M
from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config
from fedqpnt.sim.config import AttackSpec, FLConfig, NodeConfig, RunConfig
from fedqpnt.sim.recorder import RunRecorder
from fedqpnt.sim.rotations import euler_to_dcm

G0 = 9.80665


@dataclass
class RunSpec:
    name: str
    master_seed: int
    method: str
    duration_s: float = 600.0
    dt: float = 0.01
    platform: str = "ground"
    world: str = "flat"
    imu_grade: str = "industrial_mems"
    quantum_grade: str | None = "field"
    gnss_rate_hz: float = 1.0
    hold_s: float = 30.0
    heading_noise_deg: float = 2.0
    attack: dict | None = None          # {"kind","onset_s","duration_s","severity","params"}
    kappa_R: float = 40.0
    kappa_Q: float = 1.0
    detector_weights_path: str | None = None
    record: bool = False
    record_root: str = "runs"
    node_id: str = "node0"


def _level_att(f_b_mean: np.ndarray) -> tuple[float, float]:
    fx, fy, fz = f_b_mean
    phi = float(np.arctan2(fy, fz))
    theta = float(np.arctan2(-fx, np.sqrt(fy ** 2 + fz ** 2)))
    return phi, theta


def _to_run_config(spec: RunSpec) -> RunConfig:
    attacks = [AttackSpec(kind=spec.attack["kind"], t_start=spec.attack.get("onset_s", 30.0),
                           t_end=(spec.attack.get("onset_s", 30.0) + spec.attack["duration_s"])
                                 if spec.attack.get("duration_s") is not None else None,
                           severity=spec.attack.get("severity", 0.5), params=spec.attack.get("params", {}))] \
        if spec.attack else []
    node = NodeConfig(node_id=spec.node_id, platform=spec.platform,
                       imu={"grade": spec.imu_grade}, quantum={"enabled": spec.quantum_grade is not None,
                                                               "grade": spec.quantum_grade},
                       gnss={"rate_hz": spec.gnss_rate_hz}, attacks=attacks)
    return RunConfig(name=spec.name, master_seed=spec.master_seed, duration_s=spec.duration_s, dt=spec.dt,
                      method=spec.method, scenario=(spec.attack or {}).get("kind", "S1"),
                      world={"gravity": spec.world}, nodes=[node], fl=FLConfig(enabled=False),
                      fusion={"kappa_R": spec.kappa_R, "kappa_Q": spec.kappa_Q},
                      trust={"method": spec.method}, eval={})


def run_single(spec: RunSpec) -> dict[str, Any]:
    t_wall0 = time.time()
    env_cfg = EnvConfig(platform=spec.platform, world=spec.world, imu_grade=spec.imu_grade,
                         quantum_grade=spec.quantum_grade, gnss_rate_hz=spec.gnss_rate_hz,
                         hold_s=spec.hold_s, heading_noise_deg=spec.heading_noise_deg,
                         attacks=[spec.attack] if spec.attack else [])
    env = NodeEnvironment(env_cfg, seed=spec.master_seed, node_id=spec.node_id, dt=spec.dt,
                           duration_s=spec.duration_s)

    agent_cfg = make_agent_config(spec.method, kappa_R=spec.kappa_R, kappa_Q=spec.kappa_Q,
                                   world=spec.world, quantum_enabled=spec.quantum_grade is not None,
                                   detector_weights_path=spec.detector_weights_path)
    agent = Agent(agent_cfg, env.imu.config(), node_id=spec.node_id)

    rec = None
    if spec.record:
        rec = RunRecorder(spec.record_root, _to_run_config(spec))
        rng_init = stream(spec.master_seed, spec.node_id, "init")
        rec.log_seed("init", ("master_seed", "node_id"))

    f_b_hold: list[np.ndarray] = []
    initialized = False

    rows_t, rows_pos, rows_vel, rows_cov = [], [], [], []
    rows_w_gnss, rows_w_quantum, rows_detected, rows_pbar = [], [], [], []
    rows_true_pos, rows_true_vel, rows_active = [], [], []
    rows_clk_est, rows_clk_true = [], []

    for k in range(len(env)):
        tick = env.tick(k)
        t = tick.t

        if not initialized:
            if t < env.hold_s:
                if tick.imu is not None:
                    f_b_hold.append(tick.imu.f_b)
                continue
            f_mean = np.mean(f_b_hold, axis=0) if f_b_hold else np.array([0.0, 0.0, G0])
            phi0, theta0 = _level_att(f_mean)
            psi0 = float(tick.truth.att[2]) + env.initial_heading_noise()
            pos0 = tick.truth.pos.copy()
            agent.initialize_static(t, pos0, np.array([phi0, theta0, psi0]))
            initialized = True
            continue

        atick = agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)

        rows_t.append(t)
        rows_pos.append(atick.nav.pos.copy())
        rows_vel.append(atick.nav.vel.copy())
        rows_cov.append(np.diag(atick.nav.cov_pos).copy())
        rows_w_gnss.append(atick.trust.weights.get("gnss", 1.0))
        rows_w_quantum.append(atick.trust.weights.get("quantum", 1.0))
        rows_detected.append(bool(atick.trust.attack_detected))
        rows_pbar.append(atick.trust.anomaly_scores.get("gnss", 0.0))
        rows_true_pos.append(tick.truth.pos.copy())
        rows_true_vel.append(tick.truth.vel.copy())
        rows_active.append(bool(tick.label.spoofing or tick.label.jamming))
        if atick.clock is not None:
            rows_clk_est.append((atick.clock.bias_m, atick.clock.drift_mps))
        else:
            rows_clk_est.append((np.nan, np.nan))
        rows_clk_true.append((tick.true_clk_bias_m, tick.true_clk_drift_mps))

        if rec is not None:
            rec.log("nav", t, pos=atick.nav.pos, vel=atick.nav.vel, cov_pos_diag=np.diag(atick.nav.cov_pos))
            rec.log("trust", t, w_gnss=atick.trust.weights.get("gnss", 1.0),
                     w_quantum=atick.trust.weights.get("quantum", 1.0),
                     attack_detected=float(atick.trust.attack_detected))
            rec.log("truth", t, pos=tick.truth.pos, vel=tick.truth.vel)
            rec.log_event(t, "label", spoofing=tick.label.spoofing, jamming=tick.label.jamming,
                          kind=tick.label.kind, severity=tick.label.severity) if (
                tick.label.spoofing or tick.label.jamming) else None

    if rec is not None:
        rec.close(status="ok")

    t_arr = np.array(rows_t)
    result = dict(
        name=spec.name, method=spec.method, seed=spec.master_seed, attack=spec.attack,
        n_ticks=len(t_arr), wall_s=time.time() - t_wall0,
    )
    if len(t_arr) == 0:
        return result

    pos_est, pos_true = np.array(rows_pos), np.array(rows_true_pos)
    vel_est, vel_true = np.array(rows_vel), np.array(rows_true_vel)
    cov_diag = np.array(rows_cov)
    w_gnss = np.array(rows_w_gnss)
    active = np.array(rows_active, dtype=bool)
    detected = np.array(rows_detected, dtype=bool)
    clk_est = np.array(rows_clk_est)
    clk_true = np.array(rows_clk_true)

    e_h = M.horizontal_error(pos_est, pos_true)
    e_3 = M.full3d_error(pos_est, pos_true)
    e_v = M.velocity_error(vel_est, vel_true)

    phases = M.compute_phases(t_arr, active)
    rmse_h_pre = M.rmse(e_h, phases.pre)

    e_t_ns = M.clock_bias_error_ns(clk_est[:, 0], clk_true[:, 0])

    result.update(dict(
        rmse_h_pre=rmse_h_pre, max_h_pre=M.max_err(e_h, phases.pre),
        rmse_h_att=M.rmse(e_h, phases.att), max_h_att=M.max_err(e_h, phases.att),
        rmse_h_post=M.rmse(e_h, phases.post), max_h_post=M.max_err(e_h, phases.post),
        rmse_3_att=M.rmse(e_3, phases.att), rmse_v_att=M.rmse(e_v, phases.att),
        anees_pos_pre=M.anees_pos(pos_est, pos_true, cov_diag, phases.pre),
        anees_pos_all=M.anees_pos(pos_est, pos_true, cov_diag),
        latency_on=M.detection_latency(t_arr, detected, phases),
        t_dist=M.time_to_distrust(t_arr, w_gnss, phases),
        t_rec=M.recovery_time(t_arr, e_h, phases, rmse_h_pre),
        n_cyc_per_hour=M.trust_cycles_per_hour(t_arr, w_gnss),
        tv_w_per_hour=M.total_variation_per_hour(t_arr, w_gnss),
        mean_w_gnss=float(np.mean(w_gnss)),
        rmse_t_ns=M.rmse_t_ns(e_t_ns), max_t_ns=M.max_t_ns(e_t_ns),
        **M.false_alarm_rate(t_arr, detected, active),
    ))
    return result


def _run_worker(spec_dict: dict[str, Any]) -> dict[str, Any]:
    return run_single(RunSpec(**spec_dict))


def run_many(specs: list[RunSpec], n_workers: int | None = None) -> list[dict[str, Any]]:
    """One real OS process per run (spawn context, per ARCHITECTURE.md
    section 8's federation execution-model policy applied here to plain
    Monte Carlo fan-out)."""
    ctx = mp.get_context("spawn")
    dicts = [dict(spec.__dict__) for spec in specs]
    if n_workers is None:
        n_workers = max(1, min(len(specs), mp.cpu_count()))
    with ProcessPoolExecutor(max_workers=n_workers, mp_context=ctx) as ex:
        results = list(ex.map(_run_worker, dicts))
    return results


def _main() -> None:
    """CLI entry: ``python -m fedqpnt.node.runner '<json spec>'`` runs one
    ``RunSpec`` in THIS (real, separate) process and prints the resulting
    metrics dict as JSON on stdout. Used by ``tests/test_node_e2e.py`` to
    exercise one short end-to-end run per method as a real subprocess."""
    import json
    import sys

    spec_dict = json.loads(sys.argv[1])
    result = run_single(RunSpec(**spec_dict))
    print(json.dumps(result, default=lambda o: None))


if __name__ == "__main__":
    _main()
