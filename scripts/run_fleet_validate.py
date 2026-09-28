"""D-048/D-050/D-052 M2 fleet validation: tuning seeds only (500-599 for the
live fleet mission; 100000+ range for offline local-training missions, kept
well clear of the 500-599 train / 550-574 Platt / 575-599 eval / 10000+ test
partitions -- these are FL-plumbing datasets, not the M1 supervised
detector's own training set). N=5 nodes, 10-min missions, 2-3 seeds;
nominal, S15-style 2/5-drift-spoof, an H2 preview (meaconing generalisation
across peers) and an H4 preview (cold-start). Reports: global model
installs, fleet-wide detection, and wall time per fleet-hour.

ALL NUMBERS ARE "kappa_R PROVISIONAL; tuning seeds; plumbing, not results" --
this validates the fleet + D-052 local-training-data plumbing works
end-to-end, it is NOT the M4 campaign.

Each node's local FL training dataset is now built OFFLINE from real
labelled TRAINING missions (fedqpnt.fleet.local_data, reusing
fedqpnt.training.build_supervised_dataset -- D-052/D-050), not the rejected
surrogate-feature/pseudo-label path. See FleetScenarioConfig.local_train_*.

Process rule: <=8 worker processes total (5 nodes + 1 server = 6, run
strictly one fleet at a time).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from fedqpnt.trust.detector import TrustDetector
from fedqpnt.fl.client import ClientConfig
from fedqpnt.fleet.orchestrator import FleetScenarioConfig, run_fleet, write_campaign_result
from fedqpnt.training.build_supervised_dataset import plan_for

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "fleet"
N_NODES = 5
DURATION_S = 600.0       # 10-min missions
ROUND_PERIOD_S = 60.0    # SS9 default
N_ROUNDS = 10
SEEDS = (500, 501, 502)
DRIFT_SPOOF = dict(kind="drift_spoof", onset_s=120.0, duration_s=300.0, severity=0.6)
MEACONING_LIVE = dict(kind="meaconing", onset_s=120.0, duration_s=300.0, severity=0.6)
LOCAL_TRAIN_DURATION_S = 60.0   # short offline training missions -- plumbing, not M1's own retrain

def _theta0():
    d = TrustDetector(arch="mlp", seed=0)
    theta0 = d.get_params()
    return theta0, list(theta0.keys())


def _seeds_excluding_family(base: int, family_name: str, count: int = 6) -> list[int]:
    """count deterministic seeds >= base whose plan_for(seed, "mixed") family
    != family_name (used for the H2-preview node that must never see that
    family in its OWN local training data). Queries plan_for directly
    (never hardcodes its seed->family scheme, which fedqpnt/training/
    build_supervised_dataset.py's own owner may change, D-053a)."""
    out, s = [], base
    while len(out) < count:
        fam, _atk = plan_for(s, "mixed")
        if fam != family_name:
            out.append(s)
        s += 1
    return out


def _seeds_including_family(base: int, exclude_idx_target: int | None, count: int = 6) -> list[int]:
    out, s = [], base
    while len(out) < count:
        out.append(s)
        s += 1
    return out


def _run_one(scenario_id: str, seed: int, attacks: dict, method: str, node_ids: list[str],
             local_train_seeds: dict, local_train_pool: dict) -> dict:
    scenario = FleetScenarioConfig(
        scenario_id=scenario_id, method=method, seed=seed, node_ids=node_ids, n_rounds=N_ROUNDS,
        round_period_s=ROUND_PERIOD_S, duration_s=DURATION_S,
        client_cfg=ClientConfig(min_samples=8), attacks=attacks,
        local_train_seeds=local_train_seeds, local_train_pool=local_train_pool,
        local_train_duration_s=LOCAL_TRAIN_DURATION_S,
    )
    t0 = time.time()
    result = run_fleet(scenario, *_theta0())
    write_campaign_result(scenario, result, run_root="runs_fleet")
    return dict(scenario=scenario, result=result, wall_s=time.time() - t0)


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    node_ids = [f"n{i}" for i in range(N_NODES)]
    n_attacked = round(0.3 * N_NODES)   # 30% of 5 = 1.5 -> 2 (round-half-to-even is fine here)
    report = {"note": "kappa_R PROVISIONAL; tuning seeds; plumbing, not results",
              "n_nodes": N_NODES, "duration_s": DURATION_S, "seeds": list(SEEDS), "runs": {}}

    total_wall_fleet_hours = 0.0
    total_wall_s = 0.0

    # (a) nominal + (b) S15-style 2-of-5 drift spoof -- both nodes get a
    # normal mixed-family local training set.
    for seed in SEEDS[:2]:
        for scenario_id, attacks in (("nominal", {}),
                                      ("s15_2of5_drift_spoof",
                                       {node_ids[i]: DRIFT_SPOOF for i in range(n_attacked)})):
            local_seeds = {nid: _seeds_including_family(200_000 + seed * 100 + i * 10, None)
                           for i, nid in enumerate(node_ids)}
            out = _run_one(scenario_id, seed, attacks, "fedqpnt_local", node_ids,
                            local_seeds, {nid: "mixed" for nid in node_ids})
            r, key = out["result"], f"{scenario_id}_seed{seed}"
            fleet_hours = DURATION_S * N_NODES / 3600.0
            total_wall_fleet_hours += fleet_hours
            total_wall_s += out["wall_s"]
            report["runs"][key] = dict(
                aborted=r.aborted, abort_reason=r.abort_reason, wall_s=out["wall_s"],
                wall_s_per_fleet_hour=out["wall_s"] / fleet_hours,
                round_installs={nid: n.get("round_installs", 0) for nid, n in r.node_results.items()},
                node_failed={nid: n.get("failed", True) for nid, n in r.node_results.items()},
                far_per_hour={nid: n.get("far_per_hour") for nid, n in r.node_results.items()},
                rounds_skipped=sum(1 for e in r.server_log if e.get("event") == "ROUND_SKIPPED"),
                quarantine_events=sum(1 for e in r.server_log if e.get("event") == "QUARANTINE"),
            )
            print(f"[{key}] aborted={r.aborted} wall_s={out['wall_s']:.1f} "
                  f"installs={report['runs'][key]['round_installs']}")

    # (c) H2 PREVIEW: target node n0 never sees meaconing in ITS OWN local
    # training data; its 4 peers do. Evaluate n0 on a live meaconing attack,
    # FedQPNT (full 5-node fleet, FL) vs B-cont (n0 run alone, no peers ->
    # local-only detector).
    h2_seed = SEEDS[0]
    h2_local_seeds = {
        "n0": _seeds_excluding_family(300_000 + h2_seed * 100, "meaconing"),
        **{f"n{i}": _seeds_including_family(300_000 + h2_seed * 100 + i * 10, None)
           for i in range(1, N_NODES)},
    }
    h2_pool = {nid: "mixed" for nid in node_ids}
    for method, ids in (("fedqpnt_local", node_ids), ("baseline_b_cont", ["n0"])):
        local_seeds = {nid: h2_local_seeds[nid] for nid in ids}
        out = _run_one(f"h2_preview_meaconing_{method}", h2_seed, {"n0": MEACONING_LIVE}, method, ids,
                        local_seeds, {nid: h2_pool[nid] for nid in ids})
        r = out["result"]
        n0 = r.node_results.get("n0", {})
        key = f"h2_preview_{method}"
        fleet_hours = DURATION_S * len(ids) / 3600.0
        total_wall_fleet_hours += fleet_hours
        total_wall_s += out["wall_s"]
        report["runs"][key] = dict(aborted=r.aborted, abort_reason=r.abort_reason, wall_s=out["wall_s"],
                                    n0_auc=n0.get("auc"), n0_latency_on=n0.get("latency_on"),
                                    n0_failed=n0.get("failed"))
        print(f"[{key}] n0 auc={n0.get('auc')} latency_on={n0.get('latency_on')}")

    # (d) H4 PREVIEW: cold-start -- n0 joins at round 5 of 10 (mid-mission),
    # evaluated on its first attack (drift spoof onset after join). FedQPNT
    # (fleet, n0 installs the already-trained global model on joining) vs
    # B-cont (n0 alone the whole time, no join concept).
    h4_seed = SEEDS[0] + 1
    cold_attack = dict(kind="drift_spoof", onset_s=330.0, duration_s=200.0, severity=0.6)  # after round 5 (t=300s)
    h4_local_seeds = {nid: _seeds_including_family(400_000 + h4_seed * 100 + i * 10, None)
                      for i, nid in enumerate(node_ids)}
    for method, ids, join in (("fedqpnt_local", node_ids, {"n0": 5}), ("baseline_b_cont", ["n0"], {})):
        local_seeds = {nid: h4_local_seeds[nid] for nid in ids}
        scenario = FleetScenarioConfig(
            scenario_id=f"h4_preview_coldstart_{method}", method=method, seed=h4_seed, node_ids=ids,
            n_rounds=N_ROUNDS, round_period_s=ROUND_PERIOD_S, duration_s=DURATION_S,
            client_cfg=ClientConfig(min_samples=8), attacks={"n0": cold_attack}, join_round=join,
            local_train_seeds=local_seeds, local_train_pool={nid: "mixed" for nid in ids},
            local_train_duration_s=LOCAL_TRAIN_DURATION_S,
        )
        t0 = time.time()
        r = run_fleet(scenario, *_theta0())
        write_campaign_result(scenario, r, run_root="runs_fleet")
        wall_s = time.time() - t0
        n0 = r.node_results.get("n0", {})
        key = f"h4_preview_{method}"
        fleet_hours = DURATION_S * len(ids) / 3600.0
        total_wall_fleet_hours += fleet_hours
        total_wall_s += wall_s
        report["runs"][key] = dict(aborted=r.aborted, abort_reason=r.abort_reason, wall_s=wall_s,
                                    n0_auc=n0.get("auc"), n0_latency_on=n0.get("latency_on"),
                                    n0_round_installs=n0.get("round_installs"), n0_failed=n0.get("failed"))
        print(f"[{key}] n0 auc={n0.get('auc')} latency_on={n0.get('latency_on')} "
              f"installs={n0.get('round_installs')}")

    report["wall_s_per_fleet_hour_overall"] = total_wall_s / total_wall_fleet_hours if total_wall_fleet_hours else None
    report["total_wall_s"] = total_wall_s
    with open(RESULTS_DIR / "fleet_validation_report.json", "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(f"\nWrote {RESULTS_DIR / 'fleet_validation_report.json'}")
    print(f"Overall wall_s_per_fleet_hour = {report['wall_s_per_fleet_hour_overall']}")


if __name__ == "__main__":
    main()
