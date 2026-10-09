"""DIAG (round-2, tuning seeds only): reduced fleet (S8, 2 nodes) through the real adapter/orchestrator; reports
round_installs and server log. Run from the repo root of the tree under test (main or the candidate worktree).
Usage: python scripts/diag_fleet_fix.py <seed> [n_nodes=2] [n_rounds=10] [local_train_duration_s=60]"""
import os, sys, json
from pathlib import Path
ROOT = Path(os.getcwd())
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    from fedqpnt.eval import scenarios as SC
    from fedqpnt.eval.fleet_adapter import build_fleet_scenario_config, load_theta0
    from fedqpnt.fleet.orchestrator import run_fleet
    import fedqpnt
    seed = int(sys.argv[1]); assert seed < 10000
    n_nodes = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    n_rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    ltd = float(sys.argv[4]) if len(sys.argv) > 4 else 60.0
    print("fedqpnt from", fedqpnt.__file__)
    sc = SC.get("S8")
    cfg = build_fleet_scenario_config(sc, "fedqpnt", seed, n_nodes=n_nodes, n_rounds=n_rounds)
    cfg.local_train_duration_s = ltd
    theta0, names = load_theta0()
    res = run_fleet(cfg, theta0, names, join_timeout_s=1500.0)
    print("aborted", res.aborted, res.abort_reason)
    print("server_log", [(e.get("round"), e.get("event"), e.get("n_live"), e.get("n_fresh")) for e in res.server_log])
    for nid, r in sorted(res.node_results.items()):
        prov = r.get("provenance", [])
        print(nid, "round_installs", r.get("round_installs"), "rmse_h_pre", round(r.get("rmse_h_pre", float("nan")), 2),
              "mean_w_gnss", round(r.get("mean_w_gnss", float("nan")), 3), "far_per_hour", r.get("far_per_hour"),
              "n_local_samples", [p.get("n_local_samples") for p in prov], "installed", [int(bool(p.get("installed"))) for p in prov])
