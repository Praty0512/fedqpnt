"""Seed-namespace gate (D-047, D-067, D-068). Dependency-free so any layer
(campaign, fleet adapter, runners) can import it.

Namespaces:
  * TUNING        [0, 10000)         free to use.
  * TEST          [10000, 20000)     refused unless final AND the D-047 gate is cleared.
  * UNREGISTERED  [20000, 100000)    refused always (not a registered namespace).
  * FLEET_DERIVED [100000, inf)      fleet local-training seeds (100_000 + seed*100 + ...);
                                     a disjoint derived namespace, allowed here because the
                                     parent scenario seed is itself gated.
  * negative                         refused.
"""
from __future__ import annotations

import json
from pathlib import Path

TUNING_MAX = 10000
TEST_MIN = 10000
TEST_MAX = 20000            # exclusive
FLEET_DERIVED_MIN = 100_000
GATE_D047_PATH = Path("results/GATE_D047.json")

TUNING, TEST, UNREGISTERED, FLEET_DERIVED, INVALID = "tuning", "test", "unregistered", "fleet_derived", "invalid"


class SeedGateError(RuntimeError):
    pass


def classify_seed(seed: int) -> str:
    s = int(seed)
    if s < 0:
        return INVALID
    if s < TUNING_MAX:
        return TUNING
    if s < TEST_MAX:
        return TEST
    if s < FLEET_DERIVED_MIN:
        return UNREGISTERED
    return FLEET_DERIVED


def _gate_open(path: Path | str) -> bool:
    p = Path(path)
    if not p.exists():
        return False
    try:
        return bool(json.loads(p.read_text()).get("cleared", False))
    except (json.JSONDecodeError, OSError):
        return False


def enforce_seed(seed: int, *, final: bool = False, gate_path: Path | str | None = None) -> str:
    """Returns the namespace, or raises SeedGateError. TEST seeds need
    ``final=True`` AND ``cleared: true`` in the gate file (missing file =
    closed). Never creates or modifies the gate file."""
    ns = classify_seed(seed)
    if ns in (TUNING, FLEET_DERIVED):
        return ns
    if ns == TEST:
        gp = GATE_D047_PATH if gate_path is None else gate_path
        if not final:
            raise SeedGateError(f"seed {seed} is in the TEST range [{TEST_MIN}, {TEST_MAX}); requires final=True")
        if not _gate_open(gp):
            raise SeedGateError(f"seed {seed} is a TEST seed but {gp} is not cleared (D-046/D-047)")
        return ns
    raise SeedGateError(f"seed {seed} is {ns} (not a registered namespace); refused")
