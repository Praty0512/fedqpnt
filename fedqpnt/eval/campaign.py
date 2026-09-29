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
from fedqpnt.eval import seed_gate as SG

TEST_SEED_MIN = SG.TEST_MIN   # D-068: test range is [10000, 20000), not ">= 10000"
GATE_D047_PATH = Path("results/GATE_D047.json")
DEFAULT_DETECTOR_WEIGHTS = "results/m1/detector_weights.npz"
# PROPOSED-DECISION: hard worker cap. Two other agents (FL, M1-CLOSE) share
# this machine; the evaluation brief caps this agent at <=4 worker
# processes, so the campaign runner enforces that ceiling regardless of
# what a caller requests.
MAX_WORKERS = 4


class CampaignGateError(SG.SeedGateError):
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
                     record: bool = False, record_root: str = "runs_raw",
                     imu_grade: str = "industrial_mems") -> dict[str, Any]:
    # D-068: method aliases (e.g. abl_minus_quantum = fedqpnt_local with the CAI off)
    alias = SC.METHOD_ALIASES.get(method, {})
    node_method = alias.get("method", method)
    quantum_grade = alias["quantum_grade"] if "quantum_grade" in alias else scenario.cai_grade
    gnss_rate = float(scenario.gnss_rate_hz)
    spec = dict(
        name=f"{scenario.id}_{method}_{seed}", master_seed=seed, method=node_method,
        duration_s=float(duration_s if duration_s is not None else scenario.duration_s),
        dt=0.01, platform="ground", world=scenario.world, imu_grade=imu_grade,
        quantum_grade=quantum_grade, gnss_rate_hz=gnss_rate, hold_s=30.0, heading_noise_deg=2.0,
        attack=scenario.attack, kappa_R=kappa_R, kappa_Q=kappa_Q,
        detector_weights_path=detector_weights_path, record=record, record_root=record_root,
        node_id="node0",
    )
    # D-068 optional RunSpec fields; emitted ONLY when the scenario uses them so legacy spec hashes are
    # unchanged. These need the runner-side support listed in the SCENARIO-FIX checkpoint (P3).
    if scenario.attacks:
        spec["attacks"] = [dict(a) for a in scenario.attacks]
    if scenario.noise_scale:
        spec["noise_scale"] = dict(scenario.noise_scale)
    return spec


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
                    n_rounds: int = 10, n_nodes: int | None = None,
                    imu_grades: list[str] | None = None) -> list[RunTask]:
    """D-063/D-068: ``imu_grades`` adds the IMU-grade dimension for single-node
    scenarios: each (scenario, grade) gets result id ``"<sid>@<grade>"``
    (``None`` keeps the legacy id and the industrial_mems default). Fleet
    scenarios have no grade axis and are generated once.

    Cross product scenario x method x seed, methods defaulting to each
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
        grades: list[str | None] = [None] if (imu_grades is None or scenario.requires_fl) else list(imu_grades)
        for grade in grades:
            rid = sid if grade is None else f"{sid}@{grade}"
            for method in method_list:
                for seed in seeds:
                    if scenario.requires_fl:
                        spec = dict(scenario_id=sid, method=method, seed=seed,
                                    duration_s=(duration_s if duration_s is not None else scenario.duration_s),
                                    kappa_R=kappa_R, kappa_Q=kappa_Q, n_rounds=n_rounds,
                                    fleet_size=(n_nodes if n_nodes is not None else scenario.fleet_size))
                        tasks.append(RunTask(scenario_id=rid, method=method, seed=seed, spec=spec, is_fleet=True))
                    else:
                        spec = build_spec_dict(scenario, method, seed, duration_s=duration_s, kappa_R=kappa_R,
                                                kappa_Q=kappa_Q, detector_weights_path=detector_weights_path,
                                                imu_grade=grade or "industrial_mems")
                        tasks.append(RunTask(scenario_id=rid, method=method, seed=seed, spec=spec))
    return tasks


def _is_done(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        rec = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    return rec.get("status") == "ok"


def _enforce_task_seed(seed: int, final: bool) -> None:
    """D-068 lowest-level gate at task execution (cannot be bypassed by
    scripts that call _execute_one / run_fleet_task directly)."""
    try:
        SG.enforce_seed(seed, final=final, gate_path=GATE_D047_PATH)
    except SG.SeedGateError as exc:
        raise CampaignGateError(str(exc)) from exc


def _execute_one_fleet(task: "RunTask", run_root: str, final: bool = False) -> dict[str, Any]:
    """CAMPAIGN-FLEET: runs ONE fleet-scenario task (S5/S8/S9/S12/S15) via
    ``fedqpnt.eval.fleet_adapter.run_fleet_task``, in-process (the fleet
    orchestrator itself spawns its own real N+1 subprocess federation --
    see ``fedqpnt.fleet.orchestrator.run_fleet`` -- so this does not shell
    out to a second CLI). Kept out of ``_execute_one`` because fleet tasks
    are run strictly sequentially by ``run_campaign`` (see there), never
    inside the single-node ``ProcessPoolExecutor``."""
    from fedqpnt.eval import fleet_adapter as FA
    _enforce_task_seed(task.seed, final)
    scenario = SC.get(task.scenario_id.split("@")[0])
    return FA.run_fleet_task(scenario, task.method, task.seed, run_root=run_root, final=final,
                              duration_s=task.spec.get("duration_s"), kappa_R=task.spec.get("kappa_R", DEFAULT_KAPPA_R),
                              kappa_Q=task.spec.get("kappa_Q", 1.0), n_rounds=task.spec.get("n_rounds", 10),
                              n_nodes=task.spec.get("fleet_size"))


def _execute_one(task_dict: dict[str, Any], run_root: str, python_exe: str, final: bool = False) -> dict[str, Any]:
    """Runs ONE task via ``python -m fedqpnt.node.runner '<json spec>'`` as
    a real subprocess (section 8 policy applied to the eval campaign: "runs
    execute as real processes"), writes the result file, returns a small
    status dict. Executed inside a worker process by ``run_campaign``."""
    task = RunTask(**task_dict)
    _enforce_task_seed(task.seed, final)
    out_path = task.result_path(Path(run_root))
    if _is_done(out_path):
        return dict(scenario_id=task.scenario_id, method=task.method, seed=task.seed, status="skipped_done")

    if task.is_fleet:
        return _execute_one_fleet(task, run_root, final)

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


# --------------------------------------------------------------------------
# D-062 provenance: a run is valid only if the source tree under fedqpnt/ is
# clean at launch and did not change during the run.
# --------------------------------------------------------------------------
PROVENANCE_FILE = "_provenance.json"


def git_provenance(repo_root: Path | str = ".", subtree: str = "fedqpnt/") -> dict[str, Any]:
    """``git rev-parse HEAD`` + ``git status --porcelain <subtree>``.
    Never raises: on any git failure returns ``head=None`` (treated as INVALID)."""
    def _git(*args: str) -> str | None:
        try:
            r = subprocess.run(["git", *args], cwd=str(repo_root), capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return r.stdout if r.returncode == 0 else None
    head = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain", "--", subtree)
    return dict(head=head.strip() if head else None,
                dirty_files=None if status is None else sorted(l for l in status.splitlines() if l.strip()))


def provenance_verdict(start: dict[str, Any], end: dict[str, Any]) -> dict[str, Any]:
    """INVALID if git info is unavailable, the tree was dirty at launch or at
    the end, HEAD moved, or the set of dirty files changed during the run."""
    reasons = []
    if start.get("head") is None or end.get("head") is None or start.get("dirty_files") is None             or end.get("dirty_files") is None:
        reasons.append("git provenance unavailable")
    else:
        if start["dirty_files"]:
            reasons.append(f"tree dirty at launch: {start['dirty_files']}")
        if end["dirty_files"]:
            reasons.append(f"tree dirty at end: {end['dirty_files']}")
        if start["head"] != end["head"]:
            reasons.append(f"HEAD changed during run: {start['head']} -> {end['head']}")
        if start["dirty_files"] != end["dirty_files"]:
            reasons.append("dirty-file set changed during run")
    return dict(valid=not reasons, reasons=reasons, start=start, end=end)


def record_provenance(run_root: str | Path, verdict: dict[str, Any]) -> Path:
    """Appends one launch verdict to ``<run_root>/_provenance.json``."""
    path = Path(run_root) / PROVENANCE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    if path.exists():
        try:
            entries = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            entries = []
    entries.append(dict(verdict, time=time.time()))
    path.write_text(json.dumps(entries, indent=2))
    return path


def provenance_valid(run_root: str | Path) -> bool | None:
    """None if no provenance file (unknown); False if any launch was INVALID."""
    path = Path(run_root) / PROVENANCE_FILE
    if not path.exists():
        return None
    try:
        return all(e.get("valid") for e in json.loads(path.read_text()))
    except (json.JSONDecodeError, OSError):
        return False


def run_campaign(scenario_ids: list[str], seeds: list[int], *, methods: list[str] | None = None,
                  run_root: str = "runs", duration_s: float | None = None, kappa_R: float = DEFAULT_KAPPA_R,
                  kappa_Q: float = 1.0, n_workers: int | None = None, final: bool = False,
                  gate_cleared_flag: bool = False, python_exe: str | None = None,
                  n_rounds: int = 10, n_nodes: int | None = None,
                  imu_grades: list[str] | None = None) -> list[dict[str, Any]]:
    """Runs (or resumes) a campaign. Refuses the TEST seed range (>= 10000,
    section 7.1) unless ``final and gate_cleared_flag``; ``gate_cleared_flag``
    is itself refused unless ``results/GATE_D047.json`` says
    ``{"cleared": true}`` (D-046/D-047 gate)."""
    bad = [s for s in seeds if SG.classify_seed(s) in (SG.UNREGISTERED, SG.INVALID)]
    if bad:
        raise CampaignGateError(f"seeds {bad} are in no registered namespace (tuning [0,10000), test "
                                f"[{SG.TEST_MIN},{SG.TEST_MAX}), fleet-derived >= {SG.FLEET_DERIVED_MIN}); refused")
    test_seeds = [s for s in seeds if SG.classify_seed(s) == SG.TEST]
    if test_seeds:
        if not (final and gate_cleared_flag):
            raise CampaignGateError(
                f"seeds {test_seeds} are in the TEST range [{SG.TEST_MIN}, {SG.TEST_MAX}); refusing without "
                "--final --gate-cleared (section 7.1: test seeds are looked at only once, at the end)")
        if not gate_cleared(GATE_D047_PATH):
            raise CampaignGateError(
                f"--final --gate-cleared was passed but {GATE_D047_PATH} says cleared=false; "
                "D-046/D-047: no M4/publication campaign before the kappa_R gate clears")

    prov_start = git_provenance()
    tasks = generate_tasks(scenario_ids, methods, seeds, duration_s=duration_s, kappa_R=kappa_R,
                            kappa_Q=kappa_Q, n_rounds=n_rounds, n_nodes=n_nodes, imu_grades=imu_grades)
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
        results.append(_execute_one_fleet(t, run_root, final))

    if workers == 1:
        for td in task_dicts:
            results.append(_execute_one(td, run_root, py, final))
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(_execute_one, td, run_root, py, final) for td in task_dicts]
            for f in futs:
                results.append(f.result())
    verdict = provenance_verdict(prov_start, git_provenance())
    record_provenance(run_root, verdict)
    if not verdict["valid"]:
        import warnings
        warnings.warn(f"D-062: campaign run INVALID: {verdict['reasons']}")
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
                m["_imu_grade"] = scenario_id.split("@", 1)[1] if "@" in scenario_id else "industrial_mems"
                recs.append(m)
        if recs:
            out[method] = recs
    return out
