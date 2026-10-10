"""D-089: theta0_d054_f8 = ORIGINAL theta0 model weights (results/fleet/theta0_d054.npz; freeze-5 re-pretrain, seeds 400-449, unchanged)
+ the detector v5 normaliser (norm_mu, norm_sd, norm_count from results/m1/detector_weights_sup_v5.npz). Same recipe as theta0_d054_f6
(D-086 F4, which used the sup_v4 normaliser). No retraining of the weights; scripts only."""
import hashlib, json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "results/fleet/theta0_d054.npz"
NORM = ROOT / "results/m1/detector_weights_sup_v5.npz"
OUT = ROOT / "results/fleet/theta0_d054_f8.npz"
a = dict(np.load(SRC)); n = np.load(NORM)
old_count = int(a["norm_count"][0])
for k in ("norm_mu", "norm_sd", "norm_count"):
    a[k] = np.asarray(n[k])
np.savez(OUT, **a)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
prov = dict(decision="D-089 f8 (f6 recipe)", file="results/fleet/theta0_d054_f8.npz",
            weights_from="results/fleet/theta0_d054.npz (freeze-5 re-pretrain, seeds 400-449; unchanged)",
            normaliser_from="results/m1/detector_weights_sup_v5.npz (norm_mu, norm_sd, norm_count=%d)" % int(n["norm_count"][0]),
            old_norm_count=old_count,
            reason="detector features x1/x2/x12 depend on the ESKF covariance changed by C1/B5 (results/m1/feature_dependency_f5_vs_f6.json); the fleet node's E_s reuses the detector normaliser, so it must be the v5 one (campaign precondition norm_count equality)",
            caveat="weights were fitted under the freeze-5 narrow normaliser; inputs scaled by the v5 normaliser, so detector outputs shift (same caveat as f6)",
            sha256_weights_source=sha(SRC), sha256_new=sha(OUT))
OUT.with_name(OUT.stem + "_provenance.json").write_text(json.dumps(prov, indent=1))
print(json.dumps(prov, indent=1))
