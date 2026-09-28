"""Wall-clock benchmark, seconds per SIMULATED hour, for the full node
pipeline and for the individual sensor/rotation components PERF touched.
Not a test; run manually. Times are wall-clock (no cProfile overhead).
"""
from __future__ import annotations

import sys, os, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config
from fedqpnt.sim.rotations import so3_exp, dcm_to_euler
from fedqpnt.sensors.imu import ClassicalImu
from fedqpnt.core.types import TruthState

DT = 0.01
SIM_HOUR_TICKS = int(3600.0 / DT)


def bench_node(duration_s: float = 120.0, seed: int = 1) -> float:
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=5.0,
                         heading_noise_deg=2.0, attacks=[])
    env = NodeEnvironment(env_cfg, seed=seed, node_id="node0", dt=DT, duration_s=duration_s)
    agent_cfg = make_agent_config("fedqpnt_local", kappa_R=40.0, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True)
    agent = Agent(agent_cfg, env.imu.config(), node_id="node0")
    f_b_hold, initialized = [], False
    t0 = time.perf_counter()
    for k in range(len(env)):
        tick = env.tick(k)
        t = tick.t
        if not initialized:
            if t < env.hold_s:
                if tick.imu is not None:
                    f_b_hold.append(tick.imu.f_b)
                continue
            f_mean = np.mean(f_b_hold, axis=0) if f_b_hold else np.array([0.0, 0.0, 9.80665])
            phi0 = float(np.arctan2(-f_mean[1], f_mean[2]))
            theta0 = float(np.arctan2(f_mean[0], np.sqrt(f_mean[1] ** 2 + f_mean[2] ** 2)))
            psi0 = float(tick.truth.att[2]) + env.initial_heading_noise()
            agent.initialize_static(t, tick.truth.pos.copy(), np.array([phi0, theta0, psi0]))
            initialized = True
            continue
        agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
    elapsed = time.perf_counter() - t0
    return elapsed * (3600.0 / duration_s)


def bench_imu(n_ticks: int = 200_000) -> float:
    rng = np.random.default_rng(0)
    imu = ClassicalImu(grade="industrial_mems", rng=rng, world="flat")
    truth = TruthState(t=0.0, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3), att=np.zeros(3),
                        f_b=np.array([0.0, 0.0, 9.80665]), omega_b=np.zeros(3))
    t0 = time.perf_counter()
    for i in range(n_ticks):
        truth = TruthState(t=i * imu._dt, pos=truth.pos, vel=truth.vel, acc=truth.acc, att=truth.att,
                            f_b=truth.f_b, omega_b=truth.omega_b)
        imu.step(truth, rng)
    elapsed = time.perf_counter() - t0
    return elapsed * (SIM_HOUR_TICKS / n_ticks)


def bench_rotations(n: int = 200_000) -> float:
    rng = np.random.default_rng(0)
    vecs = rng.normal(scale=0.01, size=(n, 3))
    t0 = time.perf_counter()
    for i in range(n):
        C = so3_exp(vecs[i])
        dcm_to_euler(C)
    elapsed = time.perf_counter() - t0
    return elapsed * (SIM_HOUR_TICKS / n)


def bench_gnss(n_ticks: int = 20_000, seed: int = 1) -> float:
    from fedqpnt.gnss.signal import GnssSignalModel
    from fedqpnt.sim.trajectory import TruthTrajectory  # noqa: F401 (import check only)
    rng = np.random.default_rng(seed)
    model = GnssSignalModel(rate_hz=1.0)
    truth = TruthState(t=0.0, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3), att=np.zeros(3),
                        f_b=np.array([0.0, 0.0, 9.80665]), omega_b=np.zeros(3))
    t0 = time.perf_counter()
    for i in range(n_ticks):
        truth = TruthState(t=i * DT, pos=truth.pos, vel=truth.vel, acc=truth.acc, att=truth.att,
                            f_b=truth.f_b, omega_b=truth.omega_b)
        model.step(truth, rng)
    elapsed = time.perf_counter() - t0
    return elapsed * (SIM_HOUR_TICKS / n_ticks)


def bench_cai(n_ticks: int = 50_000, seed: int = 1) -> float:
    from fedqpnt.sensors.quantum import QuantumAccelerometer
    rng = np.random.default_rng(seed)
    q = QuantumAccelerometer(grade="field", rng=rng, world="flat")
    truth = TruthState(t=0.0, pos=np.zeros(3), vel=np.zeros(3), acc=np.zeros(3), att=np.zeros(3),
                        f_b=np.array([0.0, 0.0, 9.80665]), omega_b=np.zeros(3))
    t0 = time.perf_counter()
    for i in range(n_ticks):
        truth = TruthState(t=i * DT, pos=truth.pos, vel=truth.vel, acc=truth.acc, att=truth.att,
                            f_b=truth.f_b, omega_b=truth.omega_b)
        q.step(truth, rng)
    elapsed = time.perf_counter() - t0
    return elapsed * (SIM_HOUR_TICKS / n_ticks)


if __name__ == "__main__":
    print("s / simulated-hour (wall clock, no cProfile overhead)")
    print(f"  rotations (so3_exp+dcm_to_euler, 1/tick): {bench_rotations():.3f}")
    print(f"  IMU (ClassicalImu.step):                  {bench_imu():.3f}")
    print(f"  GNSS (GnssSignalModel.step):               {bench_gnss():.3f}")
    print(f"  CAI (QuantumAccelerometer.step):            {bench_cai():.3f}")
    print(f"  full node (fedqpnt_local, incl. eskf):      {bench_node():.3f}")
