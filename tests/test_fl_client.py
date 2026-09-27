"""FLClient unit test (single-process, no orchestrator): local_round builds
a valid ModelUpdate that passes the leakage guard, NoUpdate below
min_samples, and install_global actually changes scored output."""
from __future__ import annotations

import numpy as np

from fedqpnt.trust.detector import TrustDetector
from fedqpnt.fl.client import ClientConfig, FLClient
from fedqpnt.fl.transport import enforce_leakage_guard
from tests._fl_harness import make_provider


def test_client_no_update_below_min_samples():
    provider = make_provider(base_seed=500, duration_s=2.0)   # tiny -> few samples
    detector = TrustDetector(arch="mlp", seed=0)
    client = FLClient("n0", provider, detector, ClientConfig(min_samples=10_000))
    update = client.local_round(0)
    assert update is None


def test_client_produces_valid_model_update_after_enough_rounds():
    provider = make_provider(base_seed=500, duration_s=20.0)
    detector = TrustDetector(arch="mlp", seed=0)
    client = FLClient("n0", provider, detector, ClientConfig(min_samples=32))
    update = None
    for r in range(6):
        update = client.local_round(r)
        if update is not None:
            break
    assert update is not None
    ref_shapes = {k: v.shape for k, v in detector.get_params().items()
                  if k not in ("norm_mu", "norm_sd", "norm_count")}
    enforce_leakage_guard(update.params, ref_shapes, update.metrics)
    assert set(update.metrics.keys()) >= {"n_pos", "n_neg", "loss", "pl_rate", "base_round"}
    assert update.n_samples > 0


def test_install_global_changes_local_params():
    provider = make_provider(base_seed=500, duration_s=20.0)
    detector = TrustDetector(arch="mlp", seed=0)
    client = FLClient("n0", provider, detector, ClientConfig(min_samples=32))
    for r in range(6):
        update = client.local_round(r)
        if update is not None:
            break
    theta_before = client.detector.get_params()
    other = TrustDetector(arch="mlp", seed=1).get_params()
    client.install_global(other, round_idx=99)
    theta_after = client.detector.get_params()
    assert not np.allclose(theta_before["fc1.weight"], theta_after["fc1.weight"])
    assert client.last_installed_round == 99
