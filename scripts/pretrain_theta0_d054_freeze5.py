"""D-084: re-pretrain the fleet theta0 on core-freeze-5 with the UNCHANGED D-054.1 protocol
(scripts/pretrain_theta0_d054.py: seeds 400-449 restricted to clean/abrupt/jam_*, 120 s, 30 epochs,
lr 0.05, bs 64, balance, max_pos_fraction 0.5) -- imported and run as-is.

Only difference: build_supervised_dataset.collect_run now hard-codes world="schuler_tangent", but the
fleet runner (NodeRunSpec default) runs in world="flat". The dataset module is therefore patched IN
THIS PROCESS (no fedqpnt/ edit) so EnvConfig / make_agent_config see world="flat".

Steps: (0) back up the existing theta0 + provenance (refuses to overwrite an existing backup),
(1) pretrain -> results/fleet/theta0_d054.npz (+ results/fleet/theta0_d054_freeze5_provenance.json),
(2) descriptive held-out comparison old-vs-new theta0 (seeds 575-599, 600 s, flat world, raw heads, all
families, oracle labels), 4 worker processes max.

Usage: python -u scripts/pretrain_theta0_d054_freeze5.py [--workers 4]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess as sp
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np

WORLD = "flat"
FLEET = ROOT / "results" / "fleet"
OLD = FLEET / "theta0_d054.npz"
OLD_PROV = FLEET / "theta0_d054_provenance.json"
BAK = FLEET / "theta0_d054_pre_freeze5.npz"
BAK_PROV = FLEET / "theta0_d054_pre_freeze5_provenance.json"
NEW_PROV = FLEET / "theta0_d054_freeze5_provenance.json"
HELDOUT_SEEDS = list(range(575, 600))
HELDOUT_DURATION_S = 600.0


def force_flat() -> None:
    """Patch the dataset-builder module namespace so collect_run builds a world='flat' mission."""
    import fedqpnt.training.build_supervised_dataset as b
    if getattr(b, "_flat_patched", False):
        return
    ec, mk = b.EnvConfig, b.make_agent_config

    def env_cfg(*a, **kw):
        kw["world"] = WORLD
        return ec(*a, **kw)

    def agent_cfg(*a, **kw):
        kw["world"] = WORLD
        return mk(*a, **kw)
    b.EnvConfig, b.make_agent_config, b._flat_patched = env_cfg, agent_cfg, True


def collect_flat(args):
    """Worker-side entry (picklable under spawn)."""
    force_flat()
    import fedqpnt.training.build_supervised_dataset as b
    return b.collect_run(args)


def git_state() -> dict:
    def _run(*a):
        try:
            return sp.check_output(["git", *a], cwd=ROOT).decode().strip()
        except Exception:
            return "unknown"
    return dict(head=_run("rev-parse", "HEAD"), status_porcelain_fedqpnt=_run("status", "--porcelain", "fedqpnt/"),
                tag_core_freeze_5=_run("rev-parse", "core-freeze-5"))


def auc_ci(scores, labels, n_boot=500, seed=0):
    from sklearn.metrics import roc_auc_score
    scores, labels = np.asarray(scores), np.asarray(labels)
    if len(np.unique(labels)) < 2:
        return float("nan"), [float("nan")] * 2
    a = float(roc_auc_score(labels, scores))
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n_boot):
        i = rng.integers(0, len(labels), len(labels))
        if len(np.unique(labels[i])) == 2:
            bs.append(roc_auc_score(labels[i], scores[i]))
    return a, [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))] if bs else [float("nan")] * 2


def score(params, runs):
    import torch
    from fedqpnt.trust.detector import TrustDetector
    from fedqpnt.trust.features import EwmaStack
    det = TrustDetector(arch="mlp", seed=0)
    det.set_params(params)
    rows = []
    for c in runs:
        stack = EwmaStack()
        for j, t in enumerate(c["t"]):
            xt = det.normalizer.normalize(np.asarray(c["raw"][j], dtype=np.float64))
            u = stack.step(t, xt)
            with torch.no_grad():
                o = det.model(torch.as_tensor(u, dtype=torch.float32)).numpy()
            rows.append((c["family"], float(o[0]), float(o[1]), bool(c["y_spoof"][j]), bool(c["y_jam"][j])))
    return rows


def auc_table(rows):
    out = {}
    fams = sorted({r[0] for r in rows}) + ["overall"]
    for f in fams:
        sel = [r for r in rows if f == "overall" or r[0] == f]
        orc = [r[3] or r[4] for r in sel]
        a, ci = auc_ci([max(r[1], r[2]) for r in sel], orc)
        s, sci = auc_ci([r[1] for r in sel], [r[3] for r in sel])
        j, jci = auc_ci([r[2] for r in sel], [r[4] for r in sel])
        out[f] = dict(n=len(sel), n_pos=int(sum(orc)), auc_raw=a, ci95_raw=ci, auc_head_spoof=s, ci95_spoof=sci,
                      auc_head_jam=j, ci95_jam=jci)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    n_workers = min(args.workers, 4)

    git_launch = git_state()
    print("[git @launch]", json.dumps(git_launch), flush=True)
    assert OLD.exists(), OLD
    if BAK.exists():
        print(f"backup {BAK} already exists -- keeping it (resumed run)")
    else:
        shutil.copy2(OLD, BAK)
        if OLD_PROV.exists():
            shutil.copy2(OLD_PROV, BAK_PROV)
        print(f"backed up {OLD} -> {BAK}", flush=True)

    # (1) unchanged D-054.1 pretrain, world forced to flat
    force_flat()
    import pretrain_theta0_d054 as pre
    pre.OUT_PROVENANCE = NEW_PROV
    pre.OUT_WEIGHTS = OLD
    pre.main()

    # (2) descriptive held-out comparison (old backup vs new), flat world
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing as mp
    with ProcessPoolExecutor(max_workers=n_workers, mp_context=mp.get_context("spawn")) as ex:
        runs = list(ex.map(collect_flat, [(s, "mixed", HELDOUT_DURATION_S) for s in HELDOUT_SEEDS]))
    old_p = {k: v for k, v in np.load(BAK, allow_pickle=False).items()}
    new_p = {k: v for k, v in np.load(OLD, allow_pickle=False).items()}
    auc_old = auc_table(score(old_p, runs))
    auc_new = auc_table(score(new_p, runs))
    print("[held-out AUC OLD theta0 (pre_freeze5)]", json.dumps(auc_old, indent=1))
    print("[held-out AUC NEW theta0]", json.dumps(auc_new, indent=1), flush=True)

    git_end = git_state()
    prov = json.loads(NEW_PROV.read_text())
    prov.update(decision="D-084 (re-pretrain of D-054.1 theta0)", script="scripts/pretrain_theta0_d054_freeze5.py "
                "(runs scripts/pretrain_theta0_d054.py unchanged)", world=WORLD,
                world_note="dataset builder hard-codes schuler_tangent since core-freeze-5; forced to flat in-process "
                           "to match the fleet NodeRunSpec default",
                git_at_launch=git_launch, git_at_end=git_end, backup=str(BAK),
                heldout=dict(seeds=HELDOUT_SEEDS, duration_s=HELDOUT_DURATION_S, world=WORLD,
                             auc_old_theta0=auc_old, auc_new_theta0=auc_new,
                             note="descriptive; raw (uncalibrated) heads, oracle labels"))
    NEW_PROV.write_text(json.dumps(prov, indent=2, default=str))
    if git_end != git_launch:
        print("WARNING: git state changed during run", git_launch, git_end)
    print(f"done -> {OLD}, {NEW_PROV}", flush=True)


if __name__ == "__main__":
    main()
