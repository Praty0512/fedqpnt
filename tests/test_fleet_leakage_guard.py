"""D-048 M2: extends the SS4.4 leakage-guard AST scan to fedqpnt/fleet. Only
ModelUpdate/GlobalModel/NoUpdate/Lost/Failed/RoundSkipped may cross the
fedqpnt.fl wire; fedqpnt/fleet must never import fedqpnt.sim/fedqpnt.attacks
or AttackLabel/TruthState directly (it reaches truth/labels only through
fedqpnt.node.environment's EnvTick, which is the existing, already-approved
node boundary -- this guard mirrors fedqpnt.trust's and fedqpnt.fl's own).

D-052/D-050 (M2 completion): the fleet's local training data now comes from
``fedqpnt.fleet.local_data.build_node_local_dataset``, which reuses
``fedqpnt.training.build_supervised_dataset`` (the ONLY module allowed to
join oracle AttackLabel with trust features, tests/test_training_leakage_
guard.py) -- but that builder must run in the PARENT/orchestrator process,
never inside a spawned node Agent process. ``test_node_runner_never_reaches_
the_builder`` extends the import-graph walk from ``fedqpnt/node/agent.py``
(test_training_leakage_guard.py) to ``fedqpnt/fleet/node_runner.py``'s own
process entry point.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FLEET_DIR = ROOT / "fedqpnt" / "fleet"
FORBIDDEN_MODULES = {"fedqpnt.sim", "fedqpnt.attacks"}
FORBIDDEN_NAMES = {"AttackLabel", "TruthState", "TruthTrajectory"}


def _iter_fleet_py_files():
    return sorted(FLEET_DIR.glob("*.py"))


def _imported_modules_and_names(tree: ast.AST):
    modules, names = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
            for alias in node.names:
                names.add(alias.name)
    return modules, names


@pytest.mark.parametrize("path", _iter_fleet_py_files(), ids=lambda p: p.name)
def test_fleet_module_has_no_leakage_imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf8"), filename=str(path))
    modules, names = _imported_modules_and_names(tree)
    for forbidden in FORBIDDEN_MODULES:
        bad = {m for m in modules if m == forbidden or m.startswith(forbidden + ".")}
        assert not bad, f"{path}: imports forbidden module(s) {bad}"
    bad_names = names & FORBIDDEN_NAMES
    assert not bad_names, f"{path}: imports forbidden name(s) {bad_names}"


def test_fleet_package_has_files_to_scan():
    assert len(_iter_fleet_py_files()) >= 3


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf8"), filename=str(path))
    modules, _names = _imported_modules_and_names(tree)
    return modules


def _module_to_path(mod: str) -> Path | None:
    parts = mod.split(".")
    pkg_dir = ROOT.joinpath(*parts)
    if pkg_dir.is_dir() and (pkg_dir / "__init__.py").exists():
        return pkg_dir / "__init__.py"
    py = ROOT.joinpath(*parts).with_suffix(".py")
    return py if py.exists() else None


def test_node_runner_never_reaches_the_builder():
    """D-052/D-050: fedqpnt/fleet/node_runner.py (the actual per-process
    entry point spawned for each fleet node) must never import, directly or
    transitively, fedqpnt/training/build_supervised_dataset.py -- the label
    join happens ONLY in the parent process, before the node process is
    spawned (fedqpnt.fleet.orchestrator / fedqpnt.fleet.local_data), and the
    node receives just the resulting plain numpy arrays. This is the fleet
    analogue of test_training_leakage_guard.py's
    test_builder_is_outside_agent_py_import_graph."""
    entry = FLEET_DIR / "node_runner.py"
    builder_path = (ROOT / "fedqpnt" / "training" / "build_supervised_dataset.py").resolve()

    seen: set[Path] = set()
    stack = [entry]
    while stack:
        p = stack.pop()
        if p in seen or not p.exists():
            continue
        seen.add(p)
        assert p.resolve() != builder_path, f"{p} reaches the training builder -- leakage risk"
        for m in _imports(p):
            if m == "fedqpnt" or m.startswith("fedqpnt."):
                mp_ = _module_to_path(m)
                if mp_ is not None and mp_ not in seen:
                    stack.append(mp_)
    assert len(seen) >= 3


def test_node_runner_does_not_import_training_package_directly():
    modules = _imports(FLEET_DIR / "node_runner.py")
    bad = {m for m in modules if m == "fedqpnt.training" or m.startswith("fedqpnt.training.")}
    assert not bad, f"node_runner.py must not import the training/label-join package: {bad}"
