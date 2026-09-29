"""Resumable, config-driven experiment campaign runner (scenario x method x
seed), ARCHITECTURE.md section 7/8 + D-002 (integrity), D-005 (seed
pairing), D-046/D-047 (kappa_R gate). EVALUATOR-ONLY: drives
``fedqpnt.node.runner`` as real subprocesses (its public
``python -m fedqpnt.node.runner '<json RunSpec>'`` CLI entry point) --
never imports ``fedqpnt.fusion/node/trust/fl/core/gnss/sensors`` directly
beyond that public surface.

One result file per run under ``runs/<scenario_id>/<method>/seed_<seed>.json``.
A run already present with ``status == "ok"`` is skipped on restart
(resumability); config hashes are logged alongside every result so a config
change is detectable. The TEST seed range (10000+, section 7.1) is refused
unless the caller passes both ``final=True`` and ``gate_cleared=True``, and
``gate_cleared`` is itself refused unless ``results/GATE_D047.json`` says
``{"cleared": true}`` (D-046/D-047: no M4/publication campaign before the
gate clears).
"""
from __future__ import annotations

from fedqpnt.core.defaults import DEFAULT_KAPPA_R

import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from fedqpnt.eval import scenarios as SC

TEST_SEED_MIN = 10000
GATE_D047_PATH = Path("results/GATE_D047.json")
DEFAULT_DETECTOR_WEIGHTS = "results/m1/detector_weights.npz"
# PROPOSED-DECISION: hard worker cap. Two other agents (FL, M1-CLOSE) share
# this machine; the evaluation brief caps this agent at <=4 worker
# processes, so the campaign runner enforces that ceiling regardless of
# what a caller requests.
MAX_WORKERS = 4


class CampaignGateError(RuntimeError):
    pass


def ensure_gate_file(path: Path | str = GATE_D047_PATH) -> dict:
    """Reads ``results/GATE_D047.json``; creates it with
    ``{"cleared": false}`` if missing (D-046/D-047: the gate defaults
    closed)."""
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"cleared": False}, indent=2))
    return json.loads(path.read_text())


def gate_cleared(path: Path | str = GATE_D047_PATH) -> bool:
    return bool(ensure_gate_file(path).get("cleared", False))


# --------------------------------------------------------------------------
# Run spec construction (Scenario -> fedqpnt.node.runner.RunSpec dict)
# --------------------------------------------------------------------------
def build_spec_dict(scenario: SC.Scenario, method: str, seed: int, *, duration_s: float | None = None,
                     kappa_R: float = DEFAULT_KAPPA_R, kappa_Q: float = 1.0,
                     detector_weights_path: str | None = DEFAULT_DETECTOR_WEIGHTS,
                     record: bool = False, record_root: str = "runs_raw") -> dict[str, Any]:
    return dict(
        name=f"{scenario.id}_{method}_{seed}", master_seed=seed, method=method,
        duration_s=float(duration_s if duration_s is not None else scenario.duration_s),
        dt=0.01, platform="ground", world=scenario.world, imu_grade="industrial_mems",
        quantum_grade=scenario.cai_grade, gnss_rate_hz=1.0, hold_s=30.0, heading_noise_deg=2.0,
        attack=scenario.attack, kappa_R=kappa_R, kappa_Q=kappa_Q,
        detector_weights_path=detector_weights_path, record=record, record_root=record_root,
        node_id="node0",
    )


def config_hash(spec_dict: dict[str, Any]) -> str:
    blob = json.dumps(spec_dict, sort_keys=True, default=str).encode("utf8")
    return hashlib.sha256(blob).hexdigest()[:16]


@dataclass(frozen=True)
class RunTask:
    scenario_id: str
    method: str
    seed: int
    spec: dict[str, Any]
    is_fleet: bool = False   # CAMPAIGN-FLEET: dispatch to fleet_adapter.run_fleet_task, not node.runner

    @property
    def hash(self) -> str:
        return config_hash(self.spec)

    def result_path(self, run_root: Path) -> Path:
        return Path(run_root) / self.scenario_id / self.method / f"seed_{self.seed}.json"


def generate_tasks(scenario_ids: list[str], methods: list[str] | None, seeds: list[int], *,
                    duration_s: float | None = None, kappa_R: float = DEFAULT_KAPPA_R, kappa_Q: float = 1.0,
                    detector_weights_path: str | None = DEFAULT_DETECTOR_WEIGHTS,
                    n_rounds: int = 10, n_nodes: int | None = None) -> list[RunTask]:
    """Cross product scenario x method x seed, methods defaulting to each
    scenario's own declared method list (paired by seed per D-005: the same
    seed list is used for every method within a scenario). Scenarios with
    ``requires_fl=True`` (S5/S8/S9/S12/S15, D-050) get ``is_fleet=True``
    tasks: a lightweight config-dict spec (for hashing/resumability only --
    the real ``FleetScenarioConfig`` is built by
    ``fedqpnt.eval.fleet_adapter.build_fleet_scenario_config`` at execution
    time, in-process, not via a subprocess CLI)."""
    tasks: list[RunTask] = []
    for sid in scenario_ids:
        scenario = SC.get(sid)
        method_list = methods if methods is not None else list(scenario.methods)
        for method in method_list:
            for seed in seeds:
                if scenario.requires_fl:
                    spec = dict(scenario_id=sid, method=method, seed=seed,
                                duration_s=(duration_s if duration_s is not None else scenario.duration_s),
                                kappa_R=kappa_R, kappa_Q=kappa_Q, n_rounds=n_rounds,
                                fleet_size=(n_nodes if n_nodes is not None else scenario.fleet_size))
                    tasks.append(RunTask(scenario_id=sid, method=method, seed=seed, spec=spec, is_fleet=True))
                else:
                    spec = build_spec_dict(scenario, method, seed, duration_s=duration_s, kappa_R=kappa_R,
                                            kappa_Q=kappa_Q, detector_weights_path=detector_weights_path)
                    tasks.append(RunTask(scenario_id=sid, method=method, seed=seed, spec=spec))
    return tasks


def _is_done(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        rec = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    return rec.get("status") == "ok"


def _execute_one_fleet(task: "RunTask", run_root: str) -> dict[str, Any]:
    """CAMPAIGN-FLEET: runs ONE fleet-scenario task (S5/S8/S9/S12/S15) via
    ``fedqpnt.eval.fleet_adapter.run_fleet_task``, in-process (the fleet
    orchestrator itself spawns its own real N+1 subprocess federation --
    see ``fedqpnt.fleet.orchestrator.run_fleet`` -- so this does not shell
    out to a second CLI). Kept out of ``_execute_one`` because fleet tasks
    are run strictly sequentially by ``run_campaign`` (see there), never
    inside the single-node ``ProcessPoolExecutor``."""
    from fedqpnt.eval import fleet_adapter as FA
    scenario = SC.get(task.scenario_id)
    return FA.run_fleet_task(scenario, task.method, task.seed, run_root=run_root,
                              duration_s=task.spec.get("duration_s"), kappa_R=task.spec.get("kappa_R", DEFAULT_KAPPA_R),
                              kappa_Q=task.spec.get("kappa_Q", 1.0), n_rounds=task.spec.get("n_rounds", 10),
                              n_nodes=task.spec.get("fleet_size"))


def _execute_one(task_dict: dict[str, Any], run_root: str, python_exe: str) -> dict[str, Any]:
    """Runs ONE task via ``python -m fedqpnt.node.runner '<json spec>'`` as
    a real subprocess (section 8 policy applied to the eval campaign: "runs
    execute as real processes"), writes the result file, returns a small
    status dict. Executed inside a worker process by ``run_campaign``."""
    task = RunTask(**task_dict)
    out_path = task.result_path(Path(run_root))
    if _is_done(out_path):
        return dict(scenario_id=task.scenario_id, method=task.method, seed=task.seed, status="skipped_done")

    if task.is_fleet:
        return _execute_one_fleet(task, run_root)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    spec_json = json.dumps(task.spec)
    t0 = time.time()
    try:
        proc = subprocess.run([python_exe, "-m", "fedqpnt.node.runner", spec_json],
                               capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired as exc:
        record = dict(status="timeout", scenario_id=task.scenario_id, method=task.method, seed=task.seed,
                       config_hash=task.hash, kappa_R_status=SC.KAPPA_R_STATUS, wall_s=time.time() - t0,
                       stderr=str(exc))
        out_path.write_text(json.dumps(record, default=str, indent=2))
        return dict(scenario_id=task.scenario_id, method=task.method, seed=task.seed, status="timeout")

    if proc.returncode != 0:
        record = dict(status="error", scenario_id=task.scenario_id, method=task.method, seed=task.seed,
                       config_hash=task.hash, kappa_R_status=SC.KAPPA_R_STATUS, wall_s=time.time() - t0,
                       returncode=proc.returncode, stderr=proc.stderr[-4000:])
        out_path.write_text(json.dumps(record, default=str, indent=2))
        return dict(scenario_id=task.scenario_id, method=task.method, seed=task.seed, status="error")

    try:
        metrics = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        metrics = dict(_parse_error=True, raw_stdout=proc.stdout[-2000:])

    record = dict(status="ok", scenario_id=task.scenario_id, method=task.method, seed=task.seed,
                   config_hash=task.hash, kappa_R_status=SC.KAPPA_R_STATUS, wall_s=time.time() - t0,
                   metrics=metrics)
    out_path.write_text(json.dumps(record, default=str, indent=2))
    return dict(scenario_id=task.scenario_id, method=task.method, seed=task.seed, status="ok")


def run_campaign(scenario_ids: list[str], seeds: list[int], *, methods: list[str] | None = None,
                  run_root: str = "runs", duration_s: float | None = None, kappa_R: float = DEFAULT_KAPPA_R,
                  kappa_Q: float = 1.0, n_workers: int | None = None, final: bool = False,
                  gate_cleared_flag: bool = False, python_exe: str | None = None,
                  n_rounds: int = 10, n_nodes: int | None = None) -> list[dict[str, Any]]:
    """Runs (or resumes) a campaign. Refuses the TEST seed range (>= 10000,
    section 7.1) unless ``final and gate_cleared_flag``; ``gate_cleared_flag``
    is itself refused unless ``results/GATE_D047.json`` says
    ``{"cleared": true}`` (D-046/D-047 gate)."""
    test_seeds = [s for s in seeds if s >= TEST_SEED_MIN]
    if test_seeds:
        if not (final and gate_cleared_flag):
            raise CampaignGateError(
                f"seeds {test_seeds} are in the TEST range (>= {TEST_SEED_MIN}); refusing without "
                "--final --gate-cleared (section 7.1: test seeds are looked at only once, at the end)")
        if not gate_cleared(GATE_D047_PATH):
            raise CampaignGateError(
                f"--final --gate-cleared was passed but {GATE_D047_PATH} says cleared=false; "
                "D-046/D-047: no M4/publication campaign before the kappa_R gate clears")

    tasks = generate_tasks(scenario_ids, methods, seeds, duration_s=duration_s, kappa_R=kappa_R,
                            kappa_Q=kappa_Q, n_rounds=n_rounds, n_nodes=n_nodes)
    fleet_tasks = [t for t in tasks if t.is_fleet]
    node_tasks = [t for t in tasks if not t.is_fleet]
    task_dicts = [asdict(t) for t in node_tasks]
    workers = max(1, min(n_workers or MAX_WORKERS, MAX_WORKERS))
    py = python_exe or sys.executable

    results = []
    # CAMPAIGN-FLEET: fleet tasks run strictly sequentially in THIS process
    # (never through the ProcessPoolExecutor below), because each one
    # already spawns its own N+1-process federation (fedqpnt.fleet.
    # orchestrator.run_fleet); running several concurrently would blow past
    # the MAX_WORKERS process-count intent on a machine shared with other
    # agents.
    for t in fleet_tasks:
        results.append(_execute_one_fleet(t, run_root))

    if workers == 1:
        for td in task_dicts:
            results.append(_execute_one(td, run_root, py))
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(_execute_one, td, run_root, py) for td in task_dicts]
            for f in futs:
                results.append(f.result())
    return results


def load_results(run_root: str, scenario_id: str, methods: list[str]) -> dict[str, list[dict]]:
    """Loads completed (status=='ok') result records for a scenario, grouped
    by method, as flat metric dicts (for ``fedqpnt.eval.scenarios``
    criteria / ``fedqpnt.eval.stats`` / ``fedqpnt.eval.report``)."""
    out: dict[str, list[dict]] = {}
    for method in methods:
        d = Path(run_root) / scenario_id / method
        if not d.exists():
            continue
        recs = []
        for p in sorted(d.glob("seed_*.json")):
            rec = json.loads(p.read_text())
            if rec.get("status") == "ok":
                m = dict(rec.get("metrics") or {})
                m["_seed"] = rec.get("seed")
                m["_kappa_R_status"] = rec.get("kappa_R_status")
                recs.append(m)
        if recs:
            out[method] = recs
    return out
