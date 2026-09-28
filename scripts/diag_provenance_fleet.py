"""D-054 step 1: real multiprocess fleet provenance check. Reuses the exact
H2-preview scenario setup (n0 excludes meaconing, peers include it) at a
SMALL scale (2 peers instead of 4, short missions) to keep this cheap, and
dumps n0's per-round param-hash provenance for both arms."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fedqpnt.trust.detector import TrustDetector
from fedqpnt.fl.client import ClientConfig
from fedqpnt.fleet.orchestrator import FleetScenarioConfig, run_fleet

MEACONING_LIVE = dict(kind="meaconing", onset_s=30.0, duration_s=60.0, severity=0.6)


def _theta0():
    d = TrustDetector(arch="mlp", seed=0)
    return d.get_params(), list(d.get_params().keys())


def main():
    node_ids = ["n0", "n1", "n2"]
    local_seeds = {
        "n0": [700000, 700002, 700003, 700004, 700006, 700007],   # excludes meaconing (idx!=1)
        "n1": [700001, 700005, 700009, 700011, 700015, 700019],   # includes meaconing (idx==1 present)
        "n2": [700021, 700025, 700029, 700031, 700035, 700039],
    }
    for method in ("fedqpnt_local", "baseline_b_cont"):
        ids = node_ids if method == "fedqpnt_local" else ["n0"]
        scenario = FleetScenarioConfig(
            scenario_id=f"diag_{method}", method=method, seed=700, node_ids=ids, n_rounds=5,
            round_period_s=20.0, duration_s=100.0, client_cfg=ClientConfig(min_samples=4),
            attacks={"n0": MEACONING_LIVE},
            local_train_seeds={nid: local_seeds[nid] for nid in ids},
            local_train_pool={nid: "mixed" for nid in ids}, local_train_duration_s=40.0,
        )
        result = run_fleet(scenario, *_theta0())
        n0 = result.node_results.get("n0", {})
        print(f"\n=== {method} === aborted={result.aborted} n0.auc={n0.get('auc')} "
              f"n0.mean_w_gnss={n0.get('mean_w_gnss')}")
        for rec in n0.get("provenance", []):
            print(" ", rec)
        print("final_theta_hash:", n0.get("final_theta_hash"))


if __name__ == "__main__":
    main()
