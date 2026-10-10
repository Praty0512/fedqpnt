"""FIX7 B6: held-out AUC of fleet theta0 variants (TUNING seeds 500-599 only, not in pretrain seeds 400-449).
AUC over all epochs of each family present in the range, causal TrustDetector.score replay (fresh stream per mission).
Usage: python scripts/fix7_theta0_auc.py out.json  theta0_a.npz theta0_b.npz ..."""
import sys, json
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from concurrent.futures import ProcessPoolExecutor
from fedqpnt.eval import metrics as M
from fedqpnt.node.methods import load_detector_weights
from fedqpnt.training.build_supervised_dataset import collect_run, plan_for
from fedqpnt.trust.detector import TrustDetector
SEEDS = list(range(500, 560))


def run(s):
    assert s < 10000
    c = collect_run((s, "mixed", 120.0)); c["fam"] = plan_for(s, "mixed")[0]; return s, c


def main():
    out, paths = sys.argv[1], sys.argv[2:]
    with ProcessPoolExecutor(3) as ex:
        runs = dict(ex.map(run, SEEDS))
    res = {}
    for pth in paths:
        params = load_detector_weights(pth)
        det = TrustDetector(arch="mlp", seed=0); det.set_params(params)
        S, L, F = [], [], []
        for s in SEEDS:
            c = runs[s]; det.reset_stream()
            for j in range(len(c["t"])):
                ps, pj, _ = det.score(c["t"][j], np.asarray(c["raw"][j], dtype=float))
                S.append(max(ps, pj)); L.append(bool(c["y_spoof"][j]) or bool(c["y_jam"][j])); F.append(c["fam"])
        S, L, F = np.array(S), np.array(L), np.array(F)
        d = dict(n=len(S), n_pos=int(L.sum()), auc_all=M.roc_auc(S, L))
        for fam in sorted(set(F)):
            m = (F == fam)
            # family AUC: positives of this family vs ALL negatives in the range
            msk = m | (~L)
            if (L & m).sum() > 0:
                d[f"auc_{fam}"] = M.roc_auc(S[msk], L[msk]); d[f"n_pos_{fam}"] = int((L & m).sum())
        d["fpr_at_0.5_clean"] = float(np.mean(S[~L] >= 0.5))
        res[str(pth)] = d
        print(pth, json.dumps(d, indent=1), flush=True)
    Path(out).write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
