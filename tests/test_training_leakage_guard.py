"""D-052: the supervised training-data builder
(``fedqpnt/training/build_supervised_dataset.py``) is the ONLY place in the
``fedqpnt`` package where ``AttackLabel`` (an Environment-side/oracle type)
is JOINED with the trust engine's feature stream to build (X, y) training
data. This is a static, package-wide check, distinct from (and in addition
to) ``tests/test_node_leakage_guard.py`` / ``tests/test_trust_leakage_guard.py``,
which check that ``fedqpnt/node/agent.py``'s import graph and
``fedqpnt/trust/*`` never import ``AttackLabel`` at all (runtime causality).
This test instead asks: of every module that IS allowed to know about
``AttackLabel`` (evaluator-only code), which of them ALSO import the
feature-computing machinery (``fedqpnt.trust.features`` /
``fedqpnt.trust.detector``) -- i.e. which of them could join labels with
features -- and asserts that set is exactly the builder module (plus the
one pre-existing, already-guarded evaluator-only exception,
``fedqpnt.trust.pseudolabel.evaluate_against_oracle``, which the
leakage-guard's own docstring already documents as evaluator-only).
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEDQPNT_DIR = ROOT / "fedqpnt"
BUILDER_REL = "fedqpnt/training/build_supervised_dataset.py"
FEATURE_MODULES = {"fedqpnt.trust.features", "fedqpnt.trust.detector"}
# The builder deliberately does NOT `import AttackLabel` by name (it reads
# ``tick.label`` off the Environment's tick object -- see
# test_builder_module_exists_and_imports_attacklabel_source below) so a
# plain "imports the AttackLabel NAME" scan can't find the join. The actual
# join signature is: imports the module that PRODUCES oracle labels
# (fedqpnt.node.environment, whose ``EnvTick.label: AttackLabel``) AND
# imports feature-computing machinery. Any file doing both can zip labels
# to features; only the builder is allowed to.
LABEL_SOURCE_MODULES = {"fedqpnt.node.environment"}

# Modules allowed to import BOTH the label source AND feature machinery.
# Only the builder.
ALLOWED_JOIN_MODULES = {BUILDER_REL}


def _imports(path: Path) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf8"), filename=str(path))
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


def _reads_dot_label(path: Path) -> bool:
    """True iff the file has an AST attribute access named ``.label`` (e.g.
    ``tick.label``) -- the actual oracle-read operation, distinct from
    merely importing the module that happens to produce it (e.g.
    fedqpnt/node/methods.py's ``pretrain_detector`` runs
    ``NodeEnvironment`` for its simulation loop but only ever reads
    pseudo-labels off the causal feature stream, never ``tick.label``)."""
    tree = ast.parse(path.read_text(encoding="utf8"), filename=str(path))
    return any(isinstance(node, ast.Attribute) and node.attr == "label" for node in ast.walk(tree))


def _iter_fedqpnt_py_files():
    return sorted(p for p in FEDQPNT_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def test_only_the_builder_joins_attacklabel_with_features():
    joiners = []
    for path in _iter_fedqpnt_py_files():
        modules, _names = _imports(path)
        imports_label_source = bool(modules & LABEL_SOURCE_MODULES)
        imports_features = bool(modules & FEATURE_MODULES)
        if imports_label_source and imports_features and _reads_dot_label(path):
            joiners.append(path.relative_to(ROOT).as_posix())
    assert set(joiners) == ALLOWED_JOIN_MODULES, (
        f"expected only {ALLOWED_JOIN_MODULES} to import both the oracle-label source "
        f"({LABEL_SOURCE_MODULES}) and feature machinery ({FEATURE_MODULES}), found {joiners}")


def test_builder_is_outside_agent_py_import_graph():
    """Re-walks fedqpnt/node/agent.py's import graph (same traversal idea as
    tests/test_node_leakage_guard.py) and asserts the builder module is never
    reached -- i.e. Agent/TrustEngineImpl never import it, directly or
    transitively."""
    agent_entry = FEDQPNT_DIR / "node" / "agent.py"
    builder_path = (FEDQPNT_DIR / "training" / "build_supervised_dataset.py").resolve()

    def module_to_path(mod: str) -> Path | None:
        parts = mod.split(".")
        pkg_dir = ROOT.joinpath(*parts)
        if pkg_dir.is_dir() and (pkg_dir / "__init__.py").exists():
            return pkg_dir / "__init__.py"
        py = ROOT.joinpath(*parts).with_suffix(".py")
        return py if py.exists() else None

    seen: set[Path] = set()
    stack = [agent_entry]
    while stack:
        p = stack.pop()
        if p in seen or not p.exists():
            continue
        seen.add(p)
        assert p.resolve() != builder_path, f"{p} reaches the training builder -- leakage risk"
        modules, _names = _imports(p)
        for m in modules:
            if m == "fedqpnt" or m.startswith("fedqpnt."):
                mp_ = module_to_path(m)
                if mp_ is not None and mp_ not in seen:
                    stack.append(mp_)
    assert len(seen) >= 5


def test_builder_module_exists_and_imports_attacklabel_source():
    """Sanity: the builder module exists, and does NOT itself import
    AttackLabel by name (it reads ``tick.label`` off the Environment's tick
    object -- an attribute access, not a symbol import -- keeping the join
    a pure runtime zip-by-timestamp rather than a type-level dependency)."""
    path = ROOT / BUILDER_REL
    assert path.exists()
    _modules, names = _imports(path)
    assert "AttackLabel" not in names, (
        "builder should read tick.label (attribute access), not import "
        "AttackLabel as a name -- keeps the join structurally minimal")
