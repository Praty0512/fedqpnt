"""D-054.3: FL sanity check. N=5 IID nodes, each with full labelled training
missions covering ALL families (seeds 500-549 split across nodes), starting
from theta0 (D-054.1, results/fleet/theta0_d054.npz). Compares FedAvg and
TRIM-NB-R fleet runs to the CENTRALISED upper bound (same design trained on
the UNION of all node data). Evaluated on held-out seeds (575-584, distinct
from 500-549 and from theta0's 400-449) via causal TrustDetector.score
replay per mission (fresh EwmaStack, same loaded weights/normalizer).

SCALED DOWN for this session's compute budget: short missions (120 s, not
the full 600 s), 6 seeds/node (30 total, not 50), a small 2x2 hyperparameter
grid. Labelled explicitly below; a full-scale run should widen both.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from fedqpnt.eval import metrics as M
from fedqpnt.fl.client import ClientConfig
from fedqpnt.fleet.orchestrator import FleetScenarioConfig, run_fleet
from fedqpnt.node.methods import load_detector_weights
from fedqpnt.training.build_supervised_dataset import collect_run, stack_dataset
from fedqpnt.trust.detector import TrustDetector

THETA0_PATH = Path("results/fleet/theta0_d054.npz")
TRAIN_DURATION_S = 60.0     # scaled down from a full 300-600s mission
EVAL_DURATION_S = 120.0
N_NODES = 5
TRAIN_SEEDS = list(range(500, 530))    # 30 seeds (scaled down from 500-549's 50), ALL families, IID split
EVAL_SEEDS = list(range(575, 585))     # 10 held-out eval seeds, all families
GRID = dict(local_epochs=[2, 4], lr=[0.02, 0.05], prox_mu=[0.0], rounds=[10])


def _theta0():
    p = load_detector_weights(THETA0_PATH)
    if p is None:
        raise SystemExit(f"{THETA0_PATH} missing -- run scripts/pretrain_theta0_d054.py first")
    return p, list(p.keys())


def _iid_split(seeds: list[int], n: int) -> list[list[int]]:
    return [seeds[i::n] for i in range(n)]


def _eval_detector(params: dict, seeds: list[int], by_seed_eval: dict) -> dict:
    """Causal replay: fresh TrustDetector per candidate, LOADED params, one
    fresh EwmaStack per mission (reset_stream) but the SAME loaded
    normalizer/weights across missions -- matches runtime score() usage."""
    det = TrustDetector(arch="mlp", seed=0)
    det.set_params(params)
    scores, labels, families = [], [], []
    for s in seeds:
        c = by_seed_eval[s]
        det.reset_stream()
        for j in range(len(c["t"])):
            raw = np.asarray(c["raw"][j], dtype=np.float64)
            p_spoof, p_jam, _u = det.score(c["t"][j], raw)
            scores.append(max(p_spoof, p_jam))
            labels.append(bool(c["y_spoof"][j]) or bool(c["y_jam"][j]))
            families.append(c["family"])
    scores, labels, families = np.array(scores), np.array(labels, dtype=bool), np.array(families)
    out = dict(auc_overall=M.roc_auc(scores, labels))
    for fam in sorted(set(families)):
        m = families == fam
        out[f"auc_{fam}"] = M.roc_auc(scores[m], labels[m]) if m.sum() > 0 else float("nan")
    clean_mask = families == "clean"
    if clean_mask.sum() > 0:
        far_events = int(np.sum(scores[clean_mask] > 0.5))
        hours = clean_mask.sum() / 3600.0  # 1 Hz GNSS -> 1 epoch/s
        out["far_per_hour_nominal_proxy"] = far_events / hours if hours > 0 else float("nan")
    return out


def main():
    theta0, param_names = _theta0()
    print("Building eval set (held-out seeds, all families) ...")
    by_seed_eval = {s: collect_run((s, "mixed", EVAL_DURATION_S)) for s in EVAL_SEEDS}
    print(f"  eval families: {sorted({c['family'] for c in by_seed_eval.values()})}")

    print("Building UNION training set (centralised upper bound) ...")
    by_seed_train = {s: collect_run((s, "mixed", TRAIN_DURATION_S)) for s in TRAIN_SEEDS}
    det_c = TrustDetector(arch="mlp", seed=0)
    det_c.set_params(theta0)
    U, y_spoof, y_jam = stack_dataset(by_seed_train, TRAIN_SEEDS, det_c, update_normalizer=True)
    det_c.train_local(U, y_spoof, y_jam, epochs=30, lr=0.05, batch_size=64, prox_mu=0.0,
                       theta_g=None, rng=np.random.default_rng(0), max_pos_fraction=0.5, balance=True)
    centralised_eval = _eval_detector(det_c.get_params(), EVAL_SEEDS, by_seed_eval)
    print(f"CENTRALISED: {centralised_eval}")

    node_ids = [f"n{i}" for i in range(N_NODES)]
    node_seed_splits = _iid_split(TRAIN_SEEDS, N_NODES)
    print(f"IID split: {dict(zip(node_ids, node_seed_splits))}")

    report = dict(centralised=centralised_eval, grid_results=[], chosen=None,
                   train_seeds=TRAIN_SEEDS, eval_seeds=EVAL_SEEDS,
                   note="SCALED DOWN: 60s train missions (30 seeds), 120s eval missions (10 seeds); "
                        "full-scale should use 500-549 (50 seeds) at 300-600s.")
    target_auc = 0.95 * centralised_eval["auc_overall"]
    best = None
    for local_epochs, lr, prox_mu, rounds in itertools.product(
            GRID["local_epochs"], GRID["lr"], GRID["prox_mu"], GRID["rounds"]):
        row = dict(local_epochs=local_epochs, lr=lr, prox_mu=prox_mu, rounds=rounds, arms={})
        for aggregator in ("fedavg", "trim_nb_r"):
            scenario = FleetScenarioConfig(
                scenario_id=f"fl_sanity_{aggregator}_le{local_epochs}_lr{lr}_r{rounds}",
                method="fedqpnt_local", seed=500, node_ids=node_ids, n_rounds=rounds,
                round_period_s=30.0, duration_s=rounds * 30.0,
                aggregator=aggregator,
                client_cfg=ClientConfig(local_epochs=local_epochs, lr=lr, prox_mu=prox_mu, min_samples=8),
                local_train_seeds={nid: node_seed_splits[i] for i, nid in enumerate(node_ids)},
                local_train_pool={nid: "mixed" for nid in node_ids},
                local_train_duration_s=TRAIN_DURATION_S,
            )
            result = run_fleet(scenario, theta0, param_names)
            if result.aborted:
                row["arms"][aggregator] = dict(aborted=True, reason=result.abort_reason)
                continue
            eval_res = _eval_detector(result.final_theta, EVAL_SEEDS, by_seed_eval) if result.final_theta else None
            any_node = next(iter(result.node_results.values()), {})
            row["arms"][aggregator] = dict(
                aborted=False, final_theta_hash=any_node.get("final_theta_hash"),
                eval=eval_res, round_installs={nid: n.get("round_installs") for nid, n in result.node_results.items()})
        report["grid_results"].append(row)
        print(json.dumps(row, indent=2, default=str))

    Path("results/fleet").mkdir(parents=True, exist_ok=True)
    Path("results/fleet/fl_sanity_check_d054.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"target_auc (0.95x centralised) = {target_auc}")
    print("Wrote results/fleet/fl_sanity_check_d054.json")


if __name__ == "__main__":
    main()
