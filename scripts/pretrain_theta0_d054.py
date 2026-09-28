"""D-054.1: pretrain theta0 on seeds 400-449, RESTRICTED to jamming+abrupt
families only (+ naturally-occurring clean epochs), so the H2 preview's
"never seen meaconing" claim is meaningful for theta0 too, not just each
node's own FL data. Reuses fedqpnt.training.build_supervised_dataset's
collect_run/stack_dataset UNCHANGED (no edits to that module -- it may be
touched by a parallel agent); the family restriction is done by CURATING
the seed set passed in (seeds whose plan_for family index is drift(0) or
meaconing(1) are skipped), not by changing plan_for's cycling logic.

Trains a fresh TrustDetector (arch=mlp, seed=0) offline on the UNION of the
restricted seeds via TrustDetector.train_local for several epochs (this is
a proper pretrain, not one FL-style mini-step), then saves the weights +
a provenance JSON (seed list, families actually present, sample counts,
loss).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from fedqpnt.node.methods import save_detector_weights
from fedqpnt.training.build_supervised_dataset import collect_run, plan_for, stack_dataset
from fedqpnt.trust.detector import TrustDetector

OUT_WEIGHTS = Path("results/fleet/theta0_d054.npz")
OUT_PROVENANCE = Path("results/fleet/theta0_d054_provenance.json")
DURATION_S = 120.0
# D-053a (DETECT-MIX, concurrent): build_supervised_dataset.py's family
# scheme changed under us (6 families: drift, meaconing, abrupt, jam_cw,
# jam_wideband, jam_then_spoof; seed%10==0 -> clean). Query `plan_for`
# directly for each candidate seed's ACTUAL family name (never hardcode an
# index scheme against a module another agent is actively editing) and keep
# only "abrupt" and any "jam_*" family (Master's "jamming + abrupt only").
ALLOWED_FAMILIES = {"clean", "abrupt"}


def _is_allowed(seed: int) -> bool:
    family, _atk = plan_for(seed, "mixed")
    return family in ALLOWED_FAMILIES or family.startswith("jam")


def restricted_seeds(lo: int, hi: int) -> list[int]:
    return [s for s in range(lo, hi + 1) if _is_allowed(s)]


def main():
    seeds = restricted_seeds(400, 449)
    print(f"seeds (n={len(seeds)}): {seeds}")
    by_seed = {s: collect_run((s, "mixed", DURATION_S)) for s in seeds}
    families = sorted({by_seed[s]["family"] for s in seeds})
    print(f"families present: {families}")
    assert "meaconing" not in families and "drift" not in families, "restriction leaked"

    det = TrustDetector(arch="mlp", seed=0)
    U, y_spoof, y_jam = stack_dataset(by_seed, seeds, det, update_normalizer=True)
    print(f"U.shape={U.shape} n_pos_spoof={int(y_spoof.sum())} n_pos_jam={int(y_jam.sum())}")

    metrics = det.train_local(U, y_spoof, y_jam, epochs=30, lr=0.05, batch_size=64,
                               prox_mu=0.0, theta_g=None, rng=np.random.default_rng(0),
                               max_pos_fraction=0.5, balance=True)
    print(f"train metrics: {metrics}")

    OUT_WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    save_detector_weights(OUT_WEIGHTS, det.get_params())
    provenance = dict(
        decision="D-054.1", seed_range=[400, 449], seeds_used=seeds, allowed_families=sorted(ALLOWED_FAMILIES),
        families_present=families, duration_s=DURATION_S, n_samples=int(U.shape[0]),
        n_pos_spoof=int(y_spoof.sum()), n_pos_jam=int(y_jam.sum()), train_metrics=metrics,
        weights_file=str(OUT_WEIGHTS),
    )
    OUT_PROVENANCE.write_text(json.dumps(provenance, indent=2, default=str))
    print(f"Wrote {OUT_WEIGHTS} and {OUT_PROVENANCE}")


if __name__ == "__main__":
    main()
