"""D-089 CANDIDATE (H2 round 3): theta0_noabrupt_v3 = theta0_noabrupt_v2 model weights + detector v5 normaliser (same recipe as theta0_d054_f6/f8,
D-086 F4: the pretrain scripts estimate the running normaliser from a small clean subset (count 1499), ~100x narrower on nis_pos than the production
normaliser (count 20552)). Scripts only; weights untouched."""
import hashlib, json
from pathlib import Path
import numpy as np
R = Path(__file__).resolve().parent.parent
SRC, NORM, OUT = R/"results/fleet/theta0_noabrupt_v2.npz", R/"results/m1/detector_weights_sup_v5.npz", R/"results/fleet/theta0_noabrupt_v3.npz"
a = dict(np.load(SRC)); n = np.load(NORM); old = int(a["norm_count"][0])
for k in ("norm_mu", "norm_sd", "norm_count"):
    a[k] = np.asarray(n[k])
np.savez(OUT, **a)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
OUT.with_name(OUT.stem + "_provenance.json").write_text(json.dumps(dict(
    decision="D-089 candidate", weights_from="results/fleet/theta0_noabrupt_v2.npz", normaliser_from="results/m1/detector_weights_sup_v5.npz",
    old_norm_count=old, new_norm_count=int(n["norm_count"][0]), sha256_src=sha(SRC), sha256_new=sha(OUT)), indent=1))
print("wrote", OUT)
