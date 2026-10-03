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

def claim(out_path):
    """Atomic claim file; True if we got it. Caller deletes via release()."""
    import os
    cp = str(out_path) + ".claim"
    Path(cp).parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(cp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.write(fd, f"{os.getpid()} {time.ctime()}".encode()); os.close(fd)
    return True

def release(out_path):
    import os
    try: os.remove(str(out_path) + ".claim")
    except OSError: pass

def exec_spec_file(task_dict, run_root, python_exe, final=True):
    t = C.RunTask(**task_dict); op = t.result_path(Path(run_root))
    if not claim(op):
        return dict(status="skipped_claimed")
    try:
        return _exec_spec_file(task_dict, run_root, python_exe, final)
    finally:
        release(op)

def _exec_spec_file(task_dict, run_root, python_exe, final=True):
    """Phase 1b: same record format/path as campaign._execute_one, spec passed via temp file."""
    import subprocess, tempfile, os
    task = C.RunTask(**task_dict)
    C._enforce_task_seed(task.seed, final)
    out_path = task.result_path(Path(run_root))
    if C._is_done(out_path):
        return dict(status="skipped_done")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="m4spec_"); os.close(fd)
    Path(tmp).write_text(json.dumps(task.spec))
    t0 = time.time()
    base = dict(scenario_id=task.scenario_id, method=task.method, seed=task.seed, config_hash=task.hash,
                kappa_R_status=SC.KAPPA_R_STATUS, launcher="spec_file")
    try:
        proc = subprocess.run([python_exe, str(Path(__file__).with_name("m4_run_spec_file.py")), tmp],
                              capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired as exc:
        out_path.write_text(json.dumps(dict(status="timeout", **base, wall_s=time.time()-t0, stderr=str(exc)), default=str, indent=2))
        return dict(status="timeout")
    finally:
        try: os.remove(tmp)
        except OSError: pass
    if proc.returncode != 0:
        out_path.write_text(json.dumps(dict(status="error", **base, wall_s=time.time()-t0, returncode=proc.returncode,
                                            stderr=proc.stderr[-4000:]), default=str, indent=2))
        return dict(status="error")
    try:
        metrics = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        metrics = dict(_parse_error=True, raw_stdout=proc.stdout[-2000:])
    out_path.write_text(json.dumps(dict(status="ok", **base, wall_s=time.time()-t0, metrics=metrics), default=str, indent=2))
    return dict(status="ok")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="1"); ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry", action="store_true"); ap.add_argument("--reverse", action="store_true"); ap.add_argument("--only1", action="store_true"); ap.add_argument("--clear-claims", action="store_true")
    a = ap.parse_args()
    ids, tasks = build("1" if a.phase == "1b" else a.phase)
    if a.reverse: tasks = tasks[::-1]
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
    if a.phase == "1b":
        if a.clear_claims:
            for cf in Path(ROOT).rglob("*.claim"): cf.unlink()
        todo = [t for t in tasks if not C._is_done(t.result_path(Path(ROOT))) and len(json.dumps(t.spec)) > 30000]
        if a.only1: todo = todo[:1]
        print(f"{time.ctime()} 1b todo {len(todo)} workers {a.workers}", flush=True)
        py = sys.executable; cnt = Counter(); t0 = time.time(); n = 0
        with ProcessPoolExecutor(max_workers=min(a.workers, 4)) as ex:
            futs = [ex.submit(exec_spec_file, asdict(t), ROOT, py, True) for t in todo]
            for f in as_completed(futs):
                try: st = f.result()["status"]
                except Exception as e: st = "EXC:" + type(e).__name__
                cnt[st] += 1; n += 1
                if n % 10 == 0 or st != "ok":
                    print(f"{time.ctime()} {n}/{len(todo)} {dict(cnt)} elapsed {time.time()-t0:.0f}s", flush=True)
        print("DONE", dict(cnt), f"wall {time.time()-t0:.0f}s", flush=True)
    elif a.phase == "1":
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
        if a.clear_claims:
            for cf in Path(ROOT).rglob("*.claim"): cf.unlink()
        for t in tasks:
            if C._is_done(t.result_path(Path(ROOT))): cnt["skipped_done"] += 1; continue
            op = t.result_path(Path(ROOT))
            if not claim(op): cnt["skipped_claimed"] += 1; continue
            try: r = C._execute_one_fleet(t, ROOT, True)
            finally: release(op)
            cnt[r["status"]] += 1
            print(time.ctime(), t.scenario_id, t.method, t.seed, r["status"], flush=True)
        print("DONE", dict(cnt), flush=True)
    v = C.provenance_verdict(prov0, C.git_provenance()); C.record_provenance(ROOT, v)
    print("PROVENANCE valid:", v["valid"], v["reasons"], flush=True)
if __name__ == "__main__":
    main()
