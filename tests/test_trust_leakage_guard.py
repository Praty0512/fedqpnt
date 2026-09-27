"""§4.4 leakage guard: fedqpnt.trust must never import fedqpnt.sim,
fedqpnt.attacks, AttackLabel or TruthState (contract C-1 node boundary)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

TRUST_DIR = Path(__file__).resolve().parent.parent / "fedqpnt" / "trust"
FORBIDDEN_MODULES = {"fedqpnt.sim", "fedqpnt.attacks"}
FORBIDDEN_NAMES = {"AttackLabel", "TruthState", "TruthTrajectory"}


def _iter_trust_py_files():
    return sorted(TRUST_DIR.glob("*.py"))


def _imported_modules_and_names(tree: ast.AST) -> tuple[set[str], set[str]]:
    modules: set[str] = set()
    names: set[str] = set()
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


@pytest.mark.parametrize("path", _iter_trust_py_files(), ids=lambda p: p.name)
def test_trust_module_has_no_leakage_imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf8"), filename=str(path))
    modules, names = _imported_modules_and_names(tree)

    for forbidden in FORBIDDEN_MODULES:
        bad = {m for m in modules if m == forbidden or m.startswith(forbidden + ".")}
        assert not bad, f"{path}: imports forbidden module(s) {bad} (leaks Environment-side data)"

    bad_names = names & FORBIDDEN_NAMES
    assert not bad_names, f"{path}: imports forbidden name(s) {bad_names} (oracle/truth leakage)"


def test_trust_package_has_files_to_scan():
    # guards against the parametrize silently collecting zero cases if the
    # package layout ever changes.
    assert len(_iter_trust_py_files()) >= 4
