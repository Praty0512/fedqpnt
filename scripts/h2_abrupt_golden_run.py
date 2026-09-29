"""Golden run for the node_runner.py per-epoch telemetry diff (D-064 step a).
Tiny deterministic fleet mission (1 node + server = 2 processes, per the
<=2-process budget). main() writes tests/data/node_runner_golden.json from the
CURRENT code; the test re-runs run_golden_mission() and compares bit-exactly."""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fedqpnt.fl.client import ClientConfig
from fedqpnt.fleet.orchestrator import FleetScenarioConfig, run_fleet
from fedqpnt.node.methods import load_detector_weights

THETA0 = Path(__file__).resolve().parent.parent / "results/fleet/theta0_noabrupt.npz"
GOLDEN = Path(__file__).resolve().parent.parent / "tests/data/node_runner_golden.json"
NEW_KEYS = ("epoch_t", "epoch_active", "epoch_raw_p")
NONDET_KEYS = ("wall_s",)


def run_golden_mission() -> dict:
    theta0 = load_detector_weights(THETA0)
    names = list(theta0.keys())
    sc = FleetScenarioConfig(
        scenario_id="node_runner_golden", method="fedqpnt_local", seed=500, node_ids=["n0"],
        n_rounds=2, round_period_s=60.0, duration_s=120.0,
        client_cfg=ClientConfig(min_samples=8, local_epochs=2, lr=0.05, prox_mu=0.0),
        attacks={"n0": dict(kind="abrupt_spoof", onset_s=60.0, duration_s=60.0, severity=0.5)},
        local_train_seeds={"n0": [500001, 500002]}, local_train_pool={"n0": "mixed"},
        local_train_duration_s=60.0)
    res = run_fleet(sc, theta0, names)
    return res.node_results["n0"]


def golden_view(n0: dict) -> dict:
    return {k: v for k, v in n0.items() if k not in NEW_KEYS and k not in NONDET_KEYS}


if __name__ == "__main__":
    n0 = run_golden_mission()
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps(golden_view(n0), indent=1, default=str))
    print("wrote", GOLDEN, "keys:", sorted(golden_view(n0)))
