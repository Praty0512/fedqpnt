"""M4 orchestration (CAMPAIGN agent): same functions as run_campaign, but passes the v3 detector weights
explicitly (run_campaign does not expose detector_weights_path), logs progress, and is resumable."""
import json, sys, time, argparse
from pathlib import Path
from collections import Counter
from dataclasses import asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fedqpnt.eval import campaign as C, scenarios as SC
from fedqpnt.eval import seed_gate as SG

W = "results/m1/detector_weights_sup_v3.npz"
SEEDS = list(range(10000, 10030))
GRADES = ["industrial_mems", "tactical"]
ROOT = "results/m4"

def all_ids():
    ids = [s.id if hasattr(s, "id") else s for s in (SC.REGISTRY.values() if hasattr(SC, "REGISTRY") else SC.all_scenarios())]
    return ids

def build(phase):
    ids = all_ids()
    single = [i for i in ids if not SC.get(i).requires_fl]
    fleet = [i for i in ids if SC.get(i).requires_fl]
    sel = single if phase == "1" else fleet
    return ids, C.generate_tasks(sel, None, SEEDS, detector_weights_path=W, imu_grades=GRADES, final=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="1"); ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    ids, tasks = build(a.phase)
    if a.dry:
        cnt = Counter(t.scenario_id for t in tasks)
        assert all(t.spec.get("detector_weights_path", W) == W for t in tasks if not t.is_fleet)
        assert all(10000 <= t.seed <= 10029 for t in tasks)
        man = dict(n_scenarios_registry=len(ids), n_tasks=len(tasks), per_result_id=dict(cnt),
                   weights=W, seeds=[10000, 10029], grades=GRADES,
                   tasks=[dict(rid=t.scenario_id, method=t.method, seed=t.seed, fleet=t.is_fleet, hash=t.hash) for t in tasks])
        Path(f"{ROOT}/manifest_phase{a.phase}.json").write_text(json.dumps(man, indent=1))
        print(len(ids), "registry;", len(tasks), "tasks"); print(json.dumps(dict(cnt), indent=0)); return
    C.ensure_gate_file(); assert C.gate_cleared()
    prov0 = C.git_provenance()
    if a.phase == "1":
        todo = [t for t in tasks if not C._is_done(t.result_path(Path(ROOT)))]
        print(f"{time.ctime()} total {len(tasks)} todo {len(todo)} workers {a.workers}", flush=True)
        py = sys.executable; cnt = Counter(); t0 = time.time(); n = 0
        with ProcessPoolExecutor(max_workers=min(a.workers, 4)) as ex:
            futs = [ex.submit(C._execute_one, asdict(t), ROOT, py, True) for t in todo]
            for f in as_completed(futs):
                try: st = f.result()["status"]
                except Exception as e: st = "EXC:" + type(e).__name__
                cnt[st] += 1; n += 1
                if n % 25 == 0 or st != "ok":
                    print(f"{time.ctime()} {n}/{len(todo)} {dict(cnt)} elapsed {time.time()-t0:.0f}s", flush=True)
        print("DONE", dict(cnt), f"wall {time.time()-t0:.0f}s", flush=True)
    else:
        cnt = Counter()
        for t in tasks:
            if C._is_done(t.result_path(Path(ROOT))): cnt["skipped_done"] += 1; continue
            r = C._execute_one_fleet(t, ROOT, True); cnt[r["status"]] += 1
            print(time.ctime(), t.scenario_id, t.method, t.seed, r["status"], flush=True)
        print("DONE", dict(cnt), flush=True)
    v = C.provenance_verdict(prov0, C.git_provenance()); C.record_provenance(ROOT, v)
    print("PROVENANCE valid:", v["valid"], v["reasons"], flush=True)
if __name__ == "__main__":
    main()
