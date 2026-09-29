"""H2-ABRUPT diagnostic (D-062 item 1, Master ruling): are n0's weights
ACTUALLY different between fedqpnt_local (N=5, TRIM-NB-R) and
baseline_b_cont (N=1, FedAvg-identity, D-059) for the H2 abrupt scenario?

Cheap OFFLINE replay, single process, NO fleet/multiprocessing spawn (per
Master's "do NOT run new fleet missions yet; ... <=2 processes" instruction)
-- reuses the REAL, unedited fedqpnt.fl.client.FLClient (client-side local
training) and fedqpnt.fl.aggregator.{fedavg,trim_nb_r_aggregate} (server-side
aggregation) library functions directly, with the SAME local datasets /
seeds / hyperparameters h2_abrupt_h2h4_driver.py's run_h2 uses for seed=500,
instead of spawning fedqpnt.fleet.orchestrator.run_fleet's 6 processes.

n0's OWN client-side local training is IDENTICAL regardless of which arm is
being evaluated (it depends only on n0's own local dataset + theta0 + FL
hyperparams, none of which differ between arms) -- so n0's ModelUpdate delta
computed once here is exactly what BOTH arms' node process would have
produced for n0 at that round. The only place the two arms diverge is the
SERVER aggregation step: B-cont aggregates {n0} alone (fedavg, N=1, the
D-059 identity case); FedQPNT aggregates {n0, n1, n2, n3, n4} via
TRIM-NB-R. This script builds n0 + the 4 peers' real local datasets, runs
one real local_round() each, and applies both aggregation paths to theta0,
then compares n0's resulting installed params (hash + L2 diff from theta0)
between the two arms.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from fedqpnt.fl.aggregator import fedavg, trim_nb_r_aggregate, TrimNbRConfig, TrimNbRState
from fedqpnt.fl.client import ClientConfig, FLClient
from fedqpnt.fleet.features import make_round_provider
from fedqpnt.fleet.local_data import build_node_local_dataset
from fedqpnt.node.methods import load_detector_weights
from fedqpnt.training.build_supervised_dataset import plan_for
from fedqpnt.trust.detector import TrustDetector

THETA0_PATH = Path("results/fleet/theta0_noabrupt.npz")
N_NODES = 5
CHOSEN = dict(local_epochs=2, lr=0.05, prox_mu=0.0)
MIN_SAMPLES = 8
LOCAL_TRAIN_DURATION_S = 120.0
N_ROUNDS = 10
SEED = 500   # first H2 live seed


def _seeds_excluding_family(base: int, family_name: str, count: int) -> list[int]:
    out, s = [], base
    while len(out) < count:
        fam, _atk = plan_for(s, "mixed")
        if fam != family_name:
            out.append(s)
        s += 1
    return out


def _seeds_including_family(base: int, family_name: str, count: int) -> list[int]:
    s, first = base, None
    while first is None:
        fam, _atk = plan_for(s, "mixed")
        if fam == family_name:
            first = s
        s += 1
    out = [first]
    s = base
    while len(out) < count:
        if s != first:
            out.append(s)
        s += 1
    return sorted(out)


def _theta_hash(params: dict) -> str:
    import hashlib
    h = hashlib.md5()
    for k in sorted(params):
        h.update(k.encode())
        h.update(np.asarray(params[k], dtype=np.float64).tobytes())
    return h.hexdigest()[:12]


def _l2_diff(a: dict, b: dict, keys) -> float:
    return float(np.sqrt(sum(np.sum((np.asarray(a[k], dtype=np.float64) -
                                      np.asarray(b[k], dtype=np.float64)) ** 2) for k in keys)))


def main():
    theta0 = load_detector_weights(THETA0_PATH)
    if theta0 is None:
        raise SystemExit(f"{THETA0_PATH} missing")
    param_names = list(theta0.keys())
    model_names = [k for k in param_names if k not in ("norm_mu", "norm_sd", "norm_count")]

    # EXACT same local_train_seeds construction as h2_abrupt_h2h4_driver.py's
    # run_h2, for seed=500 (H2's family_name="abrupt", tag="abrupt"):
    local_seeds = {
        "n0": _seeds_excluding_family(300_000 + SEED * 100, "abrupt", 6),
        **{f"n{i}": _seeds_including_family(300_000 + SEED * 100 + i * 1000, "abrupt", 6)
           for i in range(1, N_NODES)},
    }
    print("local_seeds:", local_seeds)

    clients: dict[str, FLClient] = {}
    detectors: dict[str, TrustDetector] = {}
    for nid, seeds in local_seeds.items():
        X, y = build_node_local_dataset(seeds, pool="mixed", duration_s=LOCAL_TRAIN_DURATION_S, n_workers=1)
        print(f"{nid}: X.shape={X.shape} n_pos_spoof={int(y[:, 0].sum())} n_pos_jam={int(y[:, 1].sum())}")
        det = TrustDetector(arch="mlp", seed=0)
        det.set_params({k: np.asarray(v) for k, v in theta0.items()})
        provider = make_round_provider(X, y, N_ROUNDS)
        client = FLClient(nid, provider, det, ClientConfig(min_samples=MIN_SAMPLES, **CHOSEN),
                           rng=np.random.default_rng(SEED))
        client.last_installed_round = -1
        clients[nid] = client
        detectors[nid] = det

    trim_state = TrimNbRState()
    n0_hash_theta0 = _theta_hash(theta0)
    report = dict(theta0=str(THETA0_PATH), seed=SEED, local_seeds=local_seeds,
                  theta0_hash=n0_hash_theta0, rounds=[])

    for r in range(2):   # 2 rounds is enough to show the mechanism + accumulation
        updates = {}
        n_samples = {}
        for nid, client in clients.items():
            upd = client.local_round(r)
            updates[nid] = upd
            n_samples[nid] = None if upd is None else int(upd.n_samples)
        print(f"round {r} n_samples per node: {n_samples}")

        fresh = [u for u in updates.values() if u is not None]

        # --- B-cont path: n0 alone, FedAvg identity (D-059) ---
        n0_upd = updates["n0"]
        if n0_upd is not None:
            bcont_delta = fedavg([n0_upd], model_names, staleness=[0])
            bcont_theta = {k: theta0[k] + bcont_delta[k] for k in model_names}
            bcont_theta["norm_mu"] = n0_upd.params["norm_mu"]
            bcont_theta["norm_sd"] = n0_upd.params["norm_sd"]
            bcont_theta["norm_count"] = theta0.get("norm_count", np.array(0.0))
            bcont_installed = True
        else:
            bcont_theta = dict(theta0)
            bcont_installed = False

        # --- FedQPNT path: all 5 (whoever sent an update), TRIM-NB-R ---
        if len(fresh) >= 1:
            fq_delta, info = trim_nb_r_aggregate(fresh, model_names, r, trim_state, TrimNbRConfig(),
                                                  staleness=[0] * len(fresh))
        else:
            fq_delta, info = None, {}
        if fq_delta is not None:
            fq_theta = {k: theta0[k] + fq_delta[k] for k in model_names}
            norm_reports = [(u.params["norm_mu"], u.params["norm_sd"]) for u in fresh]
            fq_theta["norm_mu"] = np.median(np.stack([nr[0] for nr in norm_reports]), axis=0)
            fq_theta["norm_sd"] = np.median(np.stack([nr[1] for nr in norm_reports]), axis=0)
            fq_theta["norm_count"] = theta0.get("norm_count", np.array(0.0))
            fq_installed = True
        else:
            fq_theta = dict(theta0)
            fq_installed = False

        rec = dict(
            round=r, n_samples=n_samples, n_fresh=len(fresh),
            bcont_installed=bcont_installed, fq_installed=fq_installed,
            bcont_hash=_theta_hash(bcont_theta), fq_hash=_theta_hash(fq_theta),
            bcont_l2_from_theta0=_l2_diff(bcont_theta, theta0, model_names),
            fq_l2_from_theta0=_l2_diff(fq_theta, theta0, model_names),
            bcont_vs_fq_l2=_l2_diff(bcont_theta, fq_theta, model_names),
            trim_info=info,
        )
        print(json.dumps({k: v for k, v in rec.items() if k != "trim_info"}, indent=2, default=str))
        report["rounds"].append(rec)
        # feed forward: install these params into each node for the NEXT
        # round's local_round() call, mirroring the two arms' node processes
        # (n0's detector gets B-CONT's install for B-cont-path bookkeeping
        # is a separate concern; here we only need n0's OWN local training
        # to continue for round 1, which does not depend on which arm's
        # install happened -- n0 in the REAL fleet always installs ITS OWN
        # arm's global model. We install the FedQPNT aggregate on the shared
        # n0 client since that's the arm whose accumulation we care about
        # most for the "does the aggregate move n0" question; B-cont's own
        # n0-alone trajectory is fully determined by bcont_theta already
        # computed above at each round independently in this analysis).
        if fq_installed:
            detectors["n0"].set_params({k: fq_theta.get(k, theta0[k]) for k in param_names})
            clients["n0"].last_installed_round = r
        for i in range(1, N_NODES):
            nid = f"n{i}"
            if updates[nid] is not None:
                detectors[nid].set_params({k: fq_theta.get(k, theta0[k]) for k in param_names})
                clients[nid].last_installed_round = r

    out = Path("results/fleet/h2_abrupt_weight_provenance_diag.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
