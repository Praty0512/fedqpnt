"""D-048 M2 fleet validation: tuning seeds only (500-599), SHORT runs.
N=5 nodes, 10-min missions, 2 seeds (500-501); nominal, and 30% of nodes
(2 of 5) under drift spoof. Reports: global model installs, fleet-wide
detection, determinism (separately, see tests/test_fleet_basic.py), and
wall time per fleet-hour. All numbers PROVISIONAL (kappa_R PROVISIONAL per
D-046/D-047; tuning seeds).

Process rule: <=8 worker processes total (5 nodes + 1 server = 6, run
strictly one fleet at a time).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fedqpnt.trust.detector import TrustDetector
from fedqpnt.fl.client import ClientConfig
from fedqpnt.fleet.orchestrator import FleetScenarioConfig, run_fleet, write_campaign_result

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "fleet"
N_NODES = 5
DURATION_S = 600.0       # 10-min missions
ROUND_PERIOD_S = 60.0    # SS9 default
N_ROUNDS = 10
SEEDS = (500, 501)
DRIFT_SPOOF = dict(kind="drift_spoof", onset_s=120.0, duration_s=300.0, severity=0.6)


def _theta0():
    d = TrustDetector(arch="mlp", seed=0)
    theta0 = d.get_params()
    return theta0, list(theta0.keys())


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    theta0, param_names = _theta0()
    node_ids = [f"n{i}" for i in range(N_NODES)]
    n_attacked = round(0.3 * N_NODES)   # 30% of 5 = 1.5 -> 2 (round-half-to-even is fine here)

    report = {"kappa_R_note": "kappa_R PROVISIONAL (D-046/D-047); tuning seeds",
              "n_nodes": N_NODES, "duration_s": DURATION_S, "seeds": list(SEEDS), "runs": {}}

    for seed in SEEDS:
        for scenario_id, attacks in (
            ("nominal", {}),
            ("s15_30pct_drift_spoof", {node_ids[i]: DRIFT_SPOOF for i in range(n_attacked)}),
        ):
            scenario = FleetScenarioConfig(scenario_id=scenario_id, method="fedqpnt_local", seed=seed,
                                            node_ids=node_ids, n_rounds=N_ROUNDS,
                                            round_period_s=ROUND_PERIOD_S, duration_s=DURATION_S,
                                            client_cfg=ClientConfig(min_samples=32), attacks=attacks)
            print(f"[running] scenario={scenario_id} seed={seed} ...")
            result = run_fleet(scenario, theta0, param_names)
            path = write_campaign_result(scenario, result, run_root="runs_fleet")
            installs = {nid: r.get("round_installs", 0) for nid, r in result.node_results.items()}
            failed = {nid: r.get("failed", True) for nid, r in result.node_results.items()}
            detected_any = {nid: (r.get("far_per_hour", 0) is not None) for nid, r in result.node_results.items()}
            key = f"{scenario_id}_seed{seed}"
            report["runs"][key] = dict(
                aborted=result.aborted, abort_reason=result.abort_reason, wall_s=result.wall_s,
                wall_s_per_fleet_hour=result.wall_s / (DURATION_S * N_NODES / 3600.0),
                round_installs=installs, node_failed=failed,
                rounds_skipped=sum(1 for e in result.server_log if e.get("event") == "ROUND_SKIPPED"),
                quarantine_events=sum(1 for e in result.server_log if e.get("event") == "QUARANTINE"),
                mean_w_gnss={nid: r.get("mean_w_gnss") for nid, r in result.node_results.items()},
                latency_on={nid: r.get("latency_on") for nid, r in result.node_results.items()},
                result_file=str(path),
            )
            print(f"  -> aborted={result.aborted} wall_s={result.wall_s:.1f} "
                  f"installs={installs} rounds_skipped={report['runs'][key]['rounds_skipped']}")

    with open(RESULTS_DIR / "fleet_validation_report.json", "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(f"\nWrote {RESULTS_DIR / 'fleet_validation_report.json'}")


if __name__ == "__main__":
    main()
