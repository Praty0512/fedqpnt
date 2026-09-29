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

from fedqpnt.core.defaults import DEFAULT_KAPPA_R

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

# D-053a rebalance: 6 families (was 4; jamming had only 8 positive epochs
# under the old severity=0.5-only "jamming"=jam_cw plan). Root cause (traced
# empirically, see EXECUTION_LOG / DETECT_MIX_NOTES): at the default jammer
# geometry (jammer_pos_enu=(500,0,0), jammer_eirp_dbw=10), `severity` only
# rescales EIRP by 10*log10(severity) -- a few dB -- while free-space path
# loss at 500 m already yields a J/S so large that EVEN severity=0.15 drives
# effective C/N0 to roughly -10 dB-Hz (fedqpnt.attacks.jamming.
# effective_cn0_dbhz), far below the receiver's 25 dB-Hz lock threshold
# (fedqpnt/gnss/receiver.py CN0_LOCK_THRESHOLD_DBHZ) for every satellite at
# once -> `Agent.step` immediately maps the invalid fix to `fix=None`
# (fedqpnt/node/agent.py) -> the trust extractor is never called that tick
# -> zero captured (feature, label) pairs, regardless of `severity` in
# [0,1]. This is NOT the detector/trust-law design (frozen, D-026/D-051);
# it is an EXPERIMENT PARAMETER (jammer_eirp_dbw, already an AttackSpec
# param, no code change) that was previously left at a value which makes
# the whole [0,1] severity range saturate at "full denial". D-053a fixes
# this by choosing a `jammer_eirp_dbw` per severity level so the resulting
# J/S actually spans partial (fix stays valid, degraded C/N0) through full
# denial -- computed from the module's own effective_cn0_dbhz formula
# (verified numerically before use; see DETECT_MIX_NOTES). Distance is left
# at the class default (500 m); ASSUMPTION spacing/values otherwise.
FAMILY_NAMES = ["drift", "meaconing", "abrupt", "jam_cw", "jam_wideband", "jam_then_spoof"]
# (severity, jammer_eirp_dbw), empirically calibrated at distance=500m,
# env=1 (see DETECT_MIX_NOTES.md for the calibration run: fraction of the
# 180s attack window with a still-valid fix, out of 181 epochs at 1 Hz):
#   -55 dBW -> 181/181 valid (clean-ish)     -45 -> 181/181 valid (mild)
#   -38 dBW -> 181/181 valid (partial)       -33 -> 150/181 valid (partial, some drop)
#   -30 dBW ->  99/181 valid (transition)    +5/+20 dBW -> ~0-2/181 (full denial)
JAM_LEVELS = [
    (0.15, -55.0),
    (0.25, -45.0),
    (0.35, -38.0),
    (0.45, -33.0),
    (0.55, -30.0),
    (0.80,   5.0),
    (1.00,  20.0),
]


def _family_attacks(family: str, seed: int) -> list[dict]:
    sev_jam, eirp_jam = JAM_LEVELS[seed % len(JAM_LEVELS)]
    if family == "drift":
        return [dict(kind="drift_spoof", onset_s=60.0, duration_s=180.0, severity=0.5)]
    if family == "meaconing":
        return [dict(kind="meaconing", onset_s=60.0, duration_s=180.0, severity=0.5)]
    if family == "abrupt":
        return [dict(kind="abrupt_spoof", onset_s=60.0, duration_s=180.0, severity=0.5)]
    if family == "jam_cw":
        # duration bumped 180->240s vs the spoof families (D-053a): the
        # measured TRAIN-pool run (results/m1/detector_train_sup_v2_report
        # .json, first pass) landed jam_wideband at 397 positive epochs,
        # short of the >=500 target; +33% window on both jam families
        # restores headroom without touching seed assignment/severity mix.
        return [dict(kind="jam_cw", onset_s=60.0, duration_s=240.0, severity=sev_jam,
                     params=dict(jammer_eirp_dbw=eirp_jam))]
    if family == "jam_wideband":
        return [dict(kind="jam_wideband", onset_s=60.0, duration_s=240.0, severity=sev_jam,
                     params=dict(jammer_eirp_dbw=eirp_jam))]
    if family == "jam_then_spoof":
        # jam forces lock loss, spoof captures the reacquiring receiver once
        # jamming eases (Psiaki & Humphreys 2016, qualitative pattern; see
        # fedqpnt.attacks.jamming.JamThenSpoof docstring). Built here as two
        # chained AttackSpecs in NodeEnvironment's attack list (both apply()
        # each epoch, both label()s OR-combined by NodeEnvironment._label)
        # rather than via JamThenSpoof directly, since JamThenSpoof is not
        # wired into the environment's generic single-kind attack builder
        # (fedqpnt/node/environment.py PROPOSED-DECISION) -- equivalent
        # effect, no environment.py edit needed.
        return [dict(kind="jam_wideband", onset_s=60.0, duration_s=60.0, severity=sev_jam,
                     params=dict(jammer_eirp_dbw=eirp_jam)),
                dict(kind="drift_spoof", onset_s=100.0, duration_s=180.0, severity=0.5)]
    raise ValueError(f"unknown family {family!r}")


def _level_att(f_b_mean: np.ndarray) -> tuple[float, float]:
    fx, fy, fz = f_b_mean
    phi = float(np.arctan2(fy, fz))
    theta = float(np.arctan2(-fx, np.sqrt(fy ** 2 + fz ** 2)))
    return phi, theta


def plan_for(seed: int, pool: str) -> tuple[str, list[dict] | None]:
    """D-053a: 1-in-10 clean (seed % 10 == 0, or pool=="clean" literal), else
    round-robins the 6 attack families by seed % 6. Same seed->family
    assignment across TRAIN/PLATT/HELDOUT blocks (each is a disjoint
    contiguous seed range) so every block gets even family coverage."""
    if pool == "clean" or seed % 10 == 0:
        return "clean", None
    family = FAMILY_NAMES[seed % len(FAMILY_NAMES)]
    return family, _family_attacks(family, seed)


def collect_run(args: tuple[int, str, float]) -> dict:
    """Runs ONE real closed-loop mission and returns causal raw features
    (exactly what the deployed detector sees) alongside the ORACLE label
    per epoch, joined OFFLINE by timestamp after the mission completes.
    method='fixed_trust' (w==1, NIS gate on) so the mission itself is never
    perturbed by an in-training detector's own (as yet untrained) output --
    this is data COLLECTION, not evaluation of a trust law."""
    seed, pool, duration_s = args
    family, atk_list = plan_for(seed, pool)
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=HOLD_S,
                         heading_noise_deg=2.0, attacks=atk_list or [])
    env = NodeEnvironment(env_cfg, seed=seed, node_id="sup", dt=0.01, duration_s=duration_s)
    agent_cfg = make_agent_config("fixed_trust", kappa_R=DEFAULT_KAPPA_R, kappa_Q=1.0, world="flat",
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
