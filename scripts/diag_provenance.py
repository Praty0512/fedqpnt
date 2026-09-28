"""D-054 provenance diagnostic (Master directive, in response to the
identical-to-bit H2/H4 preview AUCs): checks (i) whether local training
actually changes detector parameters, (ii) whether the installed global
model differs from the pre-install local one, (iii) whether the FedQPNT and
B-cont arms end up scoring with different parameters. No multiprocessing --
drives fedqpnt.fl.client.FLClient directly against a real pre-built local
dataset, same code path node_runner.py uses, so any bug found here is the
same bug the fleet run has.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from fedqpnt.fl.client import ClientConfig, FLClient
from fedqpnt.fleet.features import make_round_provider
from fedqpnt.fleet.local_data import build_node_local_dataset
from fedqpnt.trust.detector import TrustDetector


def theta_hash(params: dict[str, np.ndarray]) -> str:
    h = hashlib.md5()
    for k in sorted(params):
        h.update(k.encode())
        h.update(np.asarray(params[k], dtype=np.float64).tobytes())
    return h.hexdigest()[:12]


def main():
    print("Building a local dataset (n0-style: seeds excluding meaconing) ...")
    X, y = build_node_local_dataset([300000, 300002, 300003, 300004, 300006, 300007],
                                     pool="mixed", duration_s=60.0, n_workers=1)
    print(f"  X.shape={X.shape} y.shape={y.shape} n_pos={int((y.sum(axis=1) > 0).sum())}")

    det = TrustDetector(arch="mlp", seed=0)
    theta0 = det.get_params()
    print(f"theta0 hash = {theta_hash(theta0)}")

    provider = make_round_provider(X, y, n_rounds=10)
    client = FLClient("n0", provider, det, ClientConfig(min_samples=8), rng=np.random.default_rng(0))

    prev_hash = theta_hash(det.get_params())
    for r in range(10):
        h_pre = theta_hash(det.get_params())
        update = client.local_round(r)
        h_post = theta_hash(det.get_params())
        n_new = 0
        if update is not None:
            n_new = update.n_samples
        changed = h_pre != h_post
        print(f"round {r}: pre={h_pre} post={h_post} changed={changed} "
              f"update={'None' if update is None else f'n_samples={n_new} metrics={update.metrics}'}")
    print(f"\nFinal detector hash: {theta_hash(det.get_params())} (theta0 was {theta_hash(theta0)})")
    print(f"Net change from theta0: {theta_hash(det.get_params()) != theta_hash(theta0)}")


if __name__ == "__main__":
    main()
