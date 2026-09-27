"""SS4.4 leakage guard for fedqpnt.fl: (1) the package must never import
fedqpnt.sim/fedqpnt.attacks or AttackLabel/TruthState (same static guard as
fedqpnt.trust); (2) enforce_leakage_guard must reject a ModelUpdate that
tries to smuggle an extra array or a non-scalar metric.
"""
from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from fedqpnt.fl.transport import enforce_leakage_guard, LeakageGuardError

FL_DIR = Path(__file__).resolve().parent.parent / "fedqpnt" / "fl"
FORBIDDEN_MODULES = {"fedqpnt.sim", "fedqpnt.attacks"}
FORBIDDEN_NAMES = {"AttackLabel", "TruthState", "TruthTrajectory"}


def _iter_fl_py_files():
    return sorted(FL_DIR.glob("*.py"))


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


@pytest.mark.parametrize("path", _iter_fl_py_files(), ids=lambda p: p.name)
def test_fl_module_has_no_leakage_imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf8"), filename=str(path))
    modules, names = _imported_modules_and_names(tree)
    for forbidden in FORBIDDEN_MODULES:
        bad = {m for m in modules if m == forbidden or m.startswith(forbidden + ".")}
        assert not bad, f"{path}: imports forbidden module(s) {bad}"
    bad_names = names & FORBIDDEN_NAMES
    assert not bad_names, f"{path}: imports forbidden name(s) {bad_names}"


def test_fl_package_has_files_to_scan():
    assert len(_iter_fl_py_files()) >= 6


def _ref_shapes():
    from fedqpnt.trust.detector import TrustDetector
    d = TrustDetector(arch="mlp", seed=0)
    return {k: v.shape for k, v in d.get_params().items()
            if k not in ("norm_mu", "norm_sd", "norm_count")}


REF_SHAPES = _ref_shapes()


def test_leakage_guard_accepts_well_formed_update():
    params = {k: np.zeros(shape) for k, shape in REF_SHAPES.items()}
    params["norm_mu"] = np.zeros(13)
    params["norm_sd"] = np.ones(13)
    enforce_leakage_guard(params, REF_SHAPES, {"n_pos": 3.0, "n_neg": 10.0, "loss": 0.5})


def test_leakage_guard_rejects_smuggled_array_param():
    params = {k: np.zeros(shape) for k, shape in REF_SHAPES.items()}
    params["norm_mu"] = np.zeros(13)
    params["norm_sd"] = np.ones(13)
    params["truth_trajectory"] = np.zeros((100, 3))   # smuggled extra array
    with pytest.raises(LeakageGuardError):
        enforce_leakage_guard(params, REF_SHAPES, {})


def test_leakage_guard_rejects_wrong_shape():
    params = {k: np.zeros(shape) for k, shape in REF_SHAPES.items()}
    params["fc1.weight"] = np.zeros((16, 999))   # shape mismatch
    params["norm_mu"] = np.zeros(13)
    params["norm_sd"] = np.ones(13)
    with pytest.raises(LeakageGuardError):
        enforce_leakage_guard(params, REF_SHAPES, {})


def test_leakage_guard_rejects_missing_param():
    params = {k: np.zeros(shape) for k, shape in list(REF_SHAPES.items())[:-1]}
    with pytest.raises(LeakageGuardError):
        enforce_leakage_guard(params, REF_SHAPES, {})


def test_leakage_guard_rejects_non_scalar_metric():
    params = {k: np.zeros(shape) for k, shape in REF_SHAPES.items()}
    params["norm_mu"] = np.zeros(13)
    params["norm_sd"] = np.ones(13)
    with pytest.raises(LeakageGuardError):
        enforce_leakage_guard(params, REF_SHAPES, {"labels": np.array([1, 0, 1])})
    with pytest.raises(LeakageGuardError):
        enforce_leakage_guard(params, REF_SHAPES, {"trajectory": [1, 2, 3]})
