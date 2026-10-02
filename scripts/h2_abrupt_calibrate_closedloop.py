"""H2_PREREG AMENDMENT 2 (D-077): closed-loop tau calibration for the confirmatory run.
For each (part, arm): the arm's FINAL installed models of live seeds 500-509 (runs-dir/{part}_{arm}_seed{s}.npz) are each run CLOSED LOOP through the
same runner as the live runs (fedqpnt.fleet.node_runner._run_fleet_node, n_rounds=0, no attack, kappa_R=DEFAULT_KAPPA_R, 1000 s) on clean seeds
580+2(s-500), 581+2(s-500). 1 Hz epoch_raw_p, first T_ALIGN_S excluded, pooled -> 20 x 910 s = 5.06 h per (part, arm); tau = smallest threshold
with FAR <= 1/h. Resumable (per-mission cache). Scripts only; no fedqpnt/ edits.
Usage: python -u scripts/h2_abrupt_calibrate_closedloop.py --runs-dir results/fleet/h2_abrupt_runs_freeze3 --workers 4 [--parts h2_abrupt,h4_abrupt,control_drift]
"""
from __future__ import annotations
import argparse, json, multiprocessing as mp, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np

CLEAN_DURATION_S = 1000.0
LIVE_SEEDS = list(range(500, 510))
ARMS = ("fedqpnt_local", "baseline_b_cont")


class _Q:
    def __init__(self): self.items = []
    def put(self, x): self.items.append(x)


def _job(args):
    npz, clean_seed, cache = args
    cache = Path(cache)
    if cache.exists():
        return str(cache)
    from fedqpnt.core.defaults import DEFAULT_KAPPA_R
    from fedqpnt.fleet.node_runner import FleetNodeSpec, _run_fleet_node
    theta = {k: np.asarray(v) for k, v in dict(np.load(npz)).items()}
    spec = FleetNodeSpec(node_id="n0", master_seed=clean_seed, duration_s=CLEAN_DURATION_S, kappa_R=DEFAULT_KAPPA_R,
                         method="fedqpnt_local", n_rounds=0, attack=None)
    q = _Q()
    _run_fleet_node(spec, theta, None, None, q)
    n0 = q.items[0]
    np.savez(cache, t=np.array(n0["epoch_t"]), p=np.array(n0["epoch_raw_p"]), failed=bool(n0.get("failed")))
    return str(cache)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", default="results/fleet/h2_abrupt_runs_freeze3")
    ap.add_argument("--out-dir", default="results/fleet/h2_abrupt_clean_closedloop_freeze3")
    ap.add_argument("--parts", default="h2_abrupt,h4_abrupt,control_drift")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    runs, out = Path(a.runs_dir), Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jobs, index = [], {}
    for part in a.parts.split(","):
        for arm in ARMS:
            for s in LIVE_SEEDS:
                npz = runs / f"{part}_{arm}_seed{s}.npz"
                if not npz.exists():
                    print("MISSING model", npz); continue
                for c in (580 + 2 * (s - 500), 581 + 2 * (s - 500)):
                    cache = out / f"{part}_{arm}_seed{s}_clean{c}.npz"
                    jobs.append((str(npz), c, str(cache))); index.setdefault((part, arm), []).append(str(cache))
    print(f"{len(jobs)} closed-loop clean missions, {a.workers} workers", flush=True)
    with mp.get_context("spawn").Pool(a.workers) as pool:
        for i, r in enumerate(pool.imap_unordered(_job, jobs)):
            print(i + 1, "/", len(jobs), Path(r).name, flush=True)
    from h2_abrupt_metrics import calibrate_tau
    from fedqpnt.eval.metrics import T_ALIGN_S
    taus = {}
    for (part, arm), caches in index.items():
        ts, ps = [], []
        for i, c in enumerate(caches):
            z = np.load(c)
            m = z["t"] >= T_ALIGN_S
            ts.append(z["t"][m] + i * 5000.0); ps.append(z["p"][m])
        cal = calibrate_tau(np.concatenate(ps), np.concatenate(ts), 1.0)
        cal = {k: (float(v) if not isinstance(v, (int, str)) else v) for k, v in cal.items()}
        (out / f"tau_{part}_{arm}.json").write_text(json.dumps(cal))
        taus[f"{part}/{arm}"] = cal
        print(part, arm, cal, flush=True)
    (out / "taus.json").write_text(json.dumps(taus, indent=1))


if __name__ == "__main__":
    main()
