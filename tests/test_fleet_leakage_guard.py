"""D-048 M2: extends the SS4.4 leakage-guard AST scan to fedqpnt/fleet. Only
ModelUpdate/GlobalModel/NoUpdate/Lost/Failed/RoundSkipped may cross the
fedqpnt.fl wire; fedqpnt/fleet must never import fedqpnt.sim/fedqpnt.attacks
or AttackLabel/TruthState directly (it reaches truth/labels only through
fedqpnt.node.environment's EnvTick, which is the existing, already-approved
node boundary -- this guard mirrors fedqpnt.trust's and fedqpnt.fl's own).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

FLEET_DIR = Path(__file__).resolve().parent.parent / "fedqpnt" / "fleet"
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
