"""FIX6 mini-matrix runner (D-086): same task machinery as scripts/m4_campaign.py, but for TUNING seeds only (< 10000)
and an arbitrary result root. Does not weaken m4_campaign's test-range assert; refuses any seed >= 10000.

  python scripts/minimatrix.py --phase 1 --seeds 530-532 --root results/minimatrix_f6 --workers 2 \
      --weights results/m1/detector_weights_sup_v4.npz [--only S1,S2-med] [--skip S7,S14] [--methods a,b]
  python scripts/minimatrix.py --phase 2 --seeds 530 --root results/minimatrix_f6 --weights ...   (fleet, sequential)
Resume = rerun (done tasks skipped)."""
import argparse
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from fedqpnt.eval import campaign as C, scenarios as SC  # noqa: E402

GRADES = ["industrial_mems", "tactical"]


def parse_seeds(txt):
    out = []
    for part in txt.replace(",", " ").split():
        if "-" in part:
            a, b = part.split("-", 1)
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def one(task_dict, root):
    return C._execute_one(task_dict, root, sys.executable, False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["1", "2"], required=True)
    ap.add_argument("--seeds", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--only", default=None, help="comma list of base scenario ids")
    ap.add_argument("--skip", default="", help="comma list of base scenario ids to skip")
    ap.add_argument("--methods", default=None, help="comma list of methods (default: each scenario's own)")
    ap.add_argument("--grades", default=None, help="comma list (default both)")
    a = ap.parse_args()
    seeds = parse_seeds(a.seeds)
    assert seeds and all(s < 10000 for s in seeds), "mini-matrix runs TUNING seeds only"
    only = set(a.only.split(",")) if a.only else None
    skip = set(filter(None, a.skip.split(",")))
    methods = a.methods.split(",") if a.methods else None
    grades = a.grades.split(",") if a.grades else GRADES
    ids = [s.id for s in SC.all_scenarios()]
    sel = [i for i in ids if (SC.get(i).requires_fl if a.phase == "2" else not SC.get(i).requires_fl)
           and (only is None or i in only) and i not in skip]
    tasks = C.generate_tasks(sel, methods, seeds, detector_weights_path=a.weights, imu_grades=grades, final=False)
    tasks = [t for t in tasks if all(s < 10000 for s in [t.seed])]
    root = Path(a.root)
    root.mkdir(parents=True, exist_ok=True)
    todo = [t for t in tasks if not C._is_done(t.result_path(root))]
    cnt = Counter()
    t0 = time.time()
    print(f"{time.ctime()} phase {a.phase} total {len(tasks)} todo {len(todo)} workers {a.workers}", flush=True)
    if a.phase == "1":
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            futs = {ex.submit(one, asdict(t), str(root)): t for t in todo}
            for n, f in enumerate(as_completed(futs), 1):
                try:
                    st = f.result()["status"]
                except Exception as e:  # noqa: BLE001
                    st = "EXC:" + type(e).__name__
                cnt[st] += 1
                if n % 10 == 0 or st != "ok":
                    print(f"{time.ctime()} {n}/{len(todo)} {dict(cnt)} elapsed {time.time() - t0:.0f}s", flush=True)
    else:
        for n, t in enumerate(todo, 1):
            try:
                st = C._execute_one_fleet(t, str(root), False)["status"]
            except Exception as e:  # noqa: BLE001
                st = "EXC:" + type(e).__name__ + str(e)[:200]
            cnt[st] += 1
            print(f"{time.ctime()} {n}/{len(todo)} {t.scenario_id} {t.method} {t.seed} {st}", flush=True)
    print("DONE", dict(cnt), f"wall {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
