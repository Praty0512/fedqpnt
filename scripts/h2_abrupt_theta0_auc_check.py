"""H2-ABRUPT step 1 (report item): held-out abrupt AUC of theta0_noabrupt
(results/fleet/theta0_noabrupt.npz, trained on {clean,jam_*,drift} only --
see h2_abrupt_pretrain_theta0.py). Since theta0 never saw abrupt, this AUC
should be near chance (~0.5) if the restriction genuinely holds.

Eval protocol mirrors fl_sanity_check_d054.py's _eval_detector (causal
TrustDetector.score replay, fresh EwmaStack per mission, loaded
weights/normalizer). Held-out seeds are within the tuning range (500-599,
per the task's seed-range constraint). First pass (585-599) found only ONE
abrupt-family seed (596, n=118 epochs) -- too thin to trust a 0.91 AUC
result, so widened to the full 500-599 range for a larger held-out sample
(plan_for cycles families deterministically by seed, independent of which
base seeds the H2/H4 fleet runs later use for LIVE missions -- those draw
from a disjoint offset space, e.g. 300000+seed*100, not raw seeds 500-599 --
so reusing 500-599 here for a held-out AUC probe does not leak into the
fleet runs' local-training or live-mission data).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from fedqpnt.eval import metrics as M
from fedqpnt.node.methods import load_detector_weights
from fedqpnt.training.build_supervised_dataset import collect_run, plan_for
from fedqpnt.trust.detector import TrustDetector

THETA0_PATH = Path("results/fleet/theta0_noabrupt.npz")
OUT = Path("results/fleet/h2_abrupt_theta0_auc_check.json")
EVAL_DURATION_S = 120.0
CANDIDATE_RANGE = range(500, 600)


def main():
    params = load_detector_weights(THETA0_PATH)
    if params is None:
        raise SystemExit(f"{THETA0_PATH} missing -- run scripts/h2_abrupt_pretrain_theta0.py first")

    abrupt_seeds = []
    other_seeds = []
    for s in CANDIDATE_RANGE:
        fam, _atk = plan_for(s, "mixed")
        (abrupt_seeds if fam == "abrupt" else other_seeds).append(s)
    print(f"abrupt_seeds={abrupt_seeds} other_seeds(non-abrupt, same range)={other_seeds}")

    by_seed = {s: collect_run((s, "mixed", EVAL_DURATION_S)) for s in abrupt_seeds}

    det = TrustDetector(arch="mlp", seed=0)
    det.set_params(params)
    scores, labels = [], []
    for s in abrupt_seeds:
        c = by_seed[s]
        det.reset_stream()
        for j in range(len(c["t"])):
            raw = np.asarray(c["raw"][j], dtype=np.float64)
            p_spoof, p_jam, _u = det.score(c["t"][j], raw)
            scores.append(max(p_spoof, p_jam))
            labels.append(bool(c["y_spoof"][j]) or bool(c["y_jam"][j]))
    scores = np.array(scores)
    labels = np.array(labels, dtype=bool)
    auc = M.roc_auc(scores, labels) if labels.sum() > 0 and labels.sum() < len(labels) else float("nan")
    out = dict(theta0=str(THETA0_PATH), abrupt_seeds=abrupt_seeds, n_epochs=len(scores),
               n_pos=int(labels.sum()), auc_abrupt_heldout=auc)
    print(json.dumps(out, indent=2))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
