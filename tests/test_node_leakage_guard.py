"""WP-8.1 node-level leakage guard (ARCHITECTURE.md section 4.4, extended to
the node boundary): ``fedqpnt/node/agent.py`` and everything it imports
(transitively, within the ``fedqpnt`` package) must never import
``fedqpnt.sim``, ``fedqpnt.attacks``, ``AttackLabel`` or ``TruthState``.
This mirrors ``tests/test_trust_leakage_guard.py`` but walks agent.py's
whole import graph rather than scanning one package's files in isolation,
since agent.py pulls in ``fedqpnt.fusion.eskf``/``fedqpnt.fusion.clock``/
``fedqpnt.gnss.receiver``/``fedqpnt.trust.trust_law`` (and whatever THEY
import), any of which could reintroduce a leak.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_ENTRY = ROOT / "fedqpnt" / "node" / "agent.py"
FORBIDDEN_MODULES = {"fedqpnt.sim", "fedqpnt.attacks"}
FORBIDDEN_NAMES = {"AttackLabel", "TruthState", "TruthTrajectory"}
# PROPOSED-DECISION: fedqpnt/fusion/eskf.py (out of this WP's scope; another
# agent owns it) imports fedqpnt.sim.rotations for pure SO(3)/DCM math
# (so3_exp, dcm_to_euler, euler_to_dcm) -- no TruthState/AttackLabel/truth
# data flows through it, and it carries none of the FORBIDDEN_NAMES. The
# module's own docstring says it "MUST NEVER import fedqpnt.sim TRUTH,
# fedqpnt.attacks or AttackLabel", i.e. the concern is truth/attack DATA, not
# this math utility that happens to live under fedqpnt.sim. Treated as an
# accepted, pre-existing exception (no leakage-guard test previously covered
# fedqpnt/fusion/*.py; tests/test_trust_leakage_guard.py only scans
# fedqpnt/trust/*.py, which does not import it) rather than a bug to silently
# paper over or a reason to fail every future node-level test.
ALLOWED_FORBIDDEN_MODULE_EXCEPTIONS = {"fedqpnt.sim.rotations"}
# PROPOSED-DECISION: the FORBIDDEN_NAMES ("does this file even mention
# TruthState/AttackLabel by name") check is only meaningful for packages that
# ARE agent-side logic (fedqpnt/node, fedqpnt/fusion, fedqpnt/trust). Shared
# infrastructure packages like fedqpnt/gnss legitimately mix an
# Environment-side class (GnssSignalModel.step(truth: TruthState, ...) in
# gnss/signal.py) with an Agent-side one in the SAME package
# (GnssReceiver.solve(epoch) in gnss/receiver.py, which never touches
# TruthState) -- ARCHITECTURE.md section 1.1 lists fedqpnt/gnss under one
# owner covering both. Applying the name check package-wide would flag
# gnss/signal.py's own (correct, Environment-side) type hints as a "leak"
# even though nothing agent.py actually does ever receives a TruthState
# through this path (fedqpnt.gnss.receiver never imports TruthState itself).
# The FORBIDDEN_MODULES check above (fedqpnt.sim / fedqpnt.attacks) still
# applies to every visited file, everywhere in the graph.
NAME_CHECK_PACKAGES = ("fedqpnt/node", "fedqpnt/fusion", "fedqpnt/trust")


def _module_to_path(mod: str) -> Path | None:
    parts = mod.split(".")
    pkg_dir = ROOT.joinpath(*parts)
    if pkg_dir.is_dir() and (pkg_dir / "__init__.py").exists():
        return pkg_dir / "__init__.py"
    py = ROOT.joinpath(*parts).with_suffix(".py")
    return py if py.exists() else None


def _resolve_relative(base_path: Path, level: int, module: str | None) -> str:
    """Best-effort resolution of ``from . import x`` / ``from ..a import b``
    relative to ``base_path``'s package, to a dotted absolute module name."""
    pkg_parts = base_path.relative_to(ROOT).with_suffix("").parts
    if base_path.name == "__init__.py":
        pkg_parts = pkg_parts[:-1]
    else:
        pkg_parts = pkg_parts[:-1]
    if level > 1:
        pkg_parts = pkg_parts[: -(level - 1)] if (level - 1) <= len(pkg_parts) else ()
    base = ".".join(pkg_parts)
    if module:
        return f"{base}.{module}" if base else module
    return base


def _imports(path: Path) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf8"), filename=str(path))
    modules: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                mod = _resolve_relative(path, node.level, node.module)
            else:
                mod = node.module or ""
            if mod:
                modules.add(mod)
            for alias in node.names:
                names.add(alias.name)
    return modules, names


def test_agent_and_its_import_graph_never_leak_truth_or_attacks():
    seen: set[Path] = set()
    stack = [AGENT_ENTRY]
    all_names: set[str] = set()
    visited_fedqpnt_files = 0

    while stack:
        p = stack.pop()
        if p in seen or not p.exists():
            continue
        seen.add(p)
        visited_fedqpnt_files += 1
        modules, names = _imports(p)
        rel = p.relative_to(ROOT).as_posix()
        if any(rel.startswith(pkg + "/") for pkg in NAME_CHECK_PACKAGES):
            all_names |= names

        for forbidden in FORBIDDEN_MODULES:
            bad = {m for m in modules if (m == forbidden or m.startswith(forbidden + "."))
                   and m not in ALLOWED_FORBIDDEN_MODULE_EXCEPTIONS}
            assert not bad, f"{p}: imports forbidden module(s) {bad} (leaks Environment-side data)"

        for m in modules:
            if m == "fedqpnt" or m.startswith("fedqpnt."):
                mp = _module_to_path(m)
                if mp is not None and mp not in seen:
                    stack.append(mp)

    bad_names = all_names & FORBIDDEN_NAMES
    assert not bad_names, f"agent.py import graph imports forbidden name(s) {bad_names}"
    # guards against a refactor accidentally emptying the traversal
    assert visited_fedqpnt_files >= 5


def test_fusion_clock_module_has_no_leakage_imports():
    """fedqpnt/fusion/clock.py (owned by this WP) must also independently
    respect the eskf.py rule it documents itself as following."""
    path = ROOT / "fedqpnt" / "fusion" / "clock.py"
    modules, names = _imports(path)
    for forbidden in FORBIDDEN_MODULES:
        bad = {m for m in modules if m == forbidden or m.startswith(forbidden + ".")}
        assert not bad, f"{path}: imports forbidden module(s) {bad}"
    assert not (names & FORBIDDEN_NAMES)
