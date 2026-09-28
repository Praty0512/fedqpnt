"""D-052: supervised training-data builder.

Runs the REAL Agent pipeline (real ESKF innovations, real receiver, real
CAI; the exact feature extraction / normalizer / EWMA-stack the deployed
trust engine uses at runtime -- ``fedqpnt.trust.features`` /
``fedqpnt.trust.detector``) over mixed missions, and attaches the ORACLE
``AttackLabel`` OFFLINE, strictly after the mission (read from the
Environment's per-tick record, never passed into ``Agent``/
``TrustEngineImpl`` -- those keep scoring with the causal detector exactly
as they do at runtime; only THIS module, afterwards, zips the two arrays
together by timestamp to build (X, y) supervised training data).

This module -- and ONLY this module -- is where ``AttackLabel`` is joined
with the trust engine's feature stream. See
``tests/test_training_leakage_guard.py``, which asserts this statically
across the whole ``fedqpnt`` package, and confirms this module is outside
``fedqpnt/node/agent.py``'s import graph (agent.py does not import
``fedqpnt.training`` and never will: nothing in ``fedqpnt/node`` or
``fedqpnt/trust`` imports this package).
"""
from __future__ import annotations

import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config
from fedqpnt.trust.detector import TrustDetector
from fedqpnt.trust.features import EwmaStack

G0 = 9.80665
HOLD_S = 30.0

FAMILY_ATTACKS = [
    ("drift", dict(kind="drift_spoof", onset_s=60.0, duration_s=180.0, severity=0.5)),
    ("meaconing", dict(kind="meaconing", onset_s=60.0, duration_s=180.0, severity=0.5)),
    ("abrupt", dict(kind="abrupt_spoof", onset_s=60.0, duration_s=180.0, severity=0.5)),
    ("jamming", dict(kind="jam_cw", onset_s=60.0, duration_s=180.0, severity=0.5)),
]


def _level_att(f_b_mean: np.ndarray) -> tuple[float, float]:
    fx, fy, fz = f_b_mean
    phi = float(np.arctan2(fy, fz))
    theta = float(np.arctan2(-fx, np.sqrt(fy ** 2 + fz ** 2)))
    return phi, theta


def plan_for(seed: int, pool: str) -> tuple[str, dict | None]:
    """1-in-5 clean, else cycles the 4 attack families -- same convention as
    the earlier (pseudo-label) pipeline, scripts/recalibrate_and_retrain_v2.py,
    kept for continuity of the tuning-seed partitioning."""
    if pool == "clean":
        return "clean", None
    idx = seed % 5
    if idx == 0:
        return "clean", None
    return FAMILY_ATTACKS[(seed // 5) % 4]


def collect_run(args: tuple[int, str, float]) -> dict:
    """Runs ONE real closed-loop mission and returns causal raw features
    (exactly what the deployed detector sees) alongside the ORACLE label
    per epoch, joined OFFLINE by timestamp after the mission completes.
    method='fixed_trust' (w==1, NIS gate on) so the mission itself is never
    perturbed by an in-training detector's own (as yet untrained) output --
    this is data COLLECTION, not evaluation of a trust law."""
    seed, pool, duration_s = args
    family, atk = plan_for(seed, pool)
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=HOLD_S,
                         heading_noise_deg=2.0, attacks=[atk] if atk else [])
    env = NodeEnvironment(env_cfg, seed=seed, node_id="sup", dt=0.01, duration_s=duration_s)
    agent_cfg = make_agent_config("fixed_trust", kappa_R=40.0, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True, detector_weights_path=None)
    agent = Agent(agent_cfg, env.imu.config(), node_id="sup")

    captured: list[tuple] = []
    orig_step = agent.trust.extractor.step

    def _wrapped(fix, innovations):
        raw = orig_step(fix, innovations)
        if raw is not None:
            captured.append((fix.t, raw.copy()))
        return raw
    agent.trust.extractor.step = _wrapped

    f_b_hold: list[np.ndarray] = []
    initialized = False
    # Oracle bookkeeping lives ONLY in this local dict, read straight off the
    # Environment's tick (fedqpnt.node.environment.NodeEnvironment.tick) --
    # never passed to `agent`.
    oracle_by_t: dict[float, tuple[bool, bool]] = {}
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
        agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
        oracle_by_t[round(t, 6)] = (bool(tick.label.spoofing), bool(tick.label.jamming))

    ts = [c[0] for c in captured]
    raws = [c[1].tolist() for c in captured]
    y_spoof = [oracle_by_t.get(round(t, 6), (False, False))[0] for t in ts]
    y_jam = [oracle_by_t.get(round(t, 6), (False, False))[1] for t in ts]
    return dict(seed=seed, family=family, t=ts, raw=raws, y_spoof=y_spoof, y_jam=y_jam)


def run_pool(jobs: list[tuple[int, str, float]], n_workers: int) -> dict:
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=n_workers, mp_context=ctx) as ex:
        collected = list(ex.map(collect_run, jobs))
    return {c["seed"]: c for c in collected}


def stack_dataset(by_seed: dict, seeds: list[int], detector: TrustDetector,
                   update_normalizer: bool = True) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Stacks raw (15,) features -> u_60 with the SAME normalizer/EWMA-stack
    the deployed detector uses (``detector.normalizer``/``EwmaStack``),
    updating the running normalizer only on oracle-NEGATIVE samples --
    consistent with the pre-existing (pseudo-label-era) convention: the
    clean reference is never polluted by attack epochs. A fresh
    ``EwmaStack`` per seed (a mission boundary), the SAME (persistent, node-
    level) normalizer across seeds."""
    U, y_spoof, y_jam = [], [], []
    for s in seeds:
        c = by_seed[s]
        stack = EwmaStack()
        for j in range(len(c["t"])):
            raw = np.asarray(c["raw"][j], dtype=np.float64)
            ys, yj = bool(c["y_spoof"][j]), bool(c["y_jam"][j])
            if update_normalizer and not (ys or yj):
                detector.normalizer.update(raw)
            xtilde = detector.normalizer.normalize(raw)
            u = stack.step(c["t"][j], xtilde)
            U.append(u)
            y_spoof.append(1.0 if ys else 0.0)
            y_jam.append(1.0 if yj else 0.0)
    return np.array(U), np.array(y_spoof), np.array(y_jam)
