"""M4 orchestration (CAMPAIGN agent), round-2 form. Scripts only; no fedqpnt/ edits.

Differs from fedqpnt.eval.campaign.run_campaign in that it (a) passes detector weights EXPLICITLY (required),
(b) uses a spec-file launcher for tasks whose spec JSON exceeds the Windows command-line limit (2 s / 5 s
toggling in S7-p2/p5), (c) claim files for every task so several instances can share one result store,
(d) progress log + D-062 provenance.

Examples (round 2; nothing is launched until the Master says "round 2 go"):
    python scripts/m4_campaign.py --dry --weights <placeholder.npz>            # manifest + assertions only
    python scripts/m4_campaign.py --phase 1 --weights results/m1/detector_weights_sup_v4.npz --workers 4
    python scripts/m4_campaign.py --phase 2 --weights ...                       # fleet, 1 at a time
    python scripts/m4_campaign.py --phase 2 --reverse --weights ...             # 2nd fleet instance, reverse order
Resume = rerun the same command (done tasks skipped). After a crash use --clear-claims ONLY when no instance is live.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from fedqpnt.eval import campaign as C, scenarios as SC  # noqa: E402

GRADES = ["industrial_mems", "tactical"]
LONG_SPEC_CHARS = 30_000          # Windows cmdline limit is 32,767
TIMEOUT_NORMAL_S = 3600           # _execute_one's own timeout
TIMEOUT_LONG_S = 7200
CODE_TAG = "core-freeze-5"
SPEC_FILE_SCRIPT = Path(__file__).with_name("m4_run_spec_file.py")


def core_snapshot(tag: str) -> dict:
    """fedqpnt/-specific provenance point: HEAD, fedqpnt/ porcelain, and diff vs the freeze tag."""
    return dict(head=_git("rev-parse", "HEAD").strip(),
                dirty=sorted(l for l in _git("status", "--porcelain", "--", "fedqpnt/").splitlines() if l.strip()),
                diff_vs_tag_empty=not _git("diff", tag, "HEAD", "--", "fedqpnt").strip())


def fedqpnt_verdict(start: dict, end: dict, tag: str) -> dict:
    """Core-specific verdict (ignores docs/log commits): fedqpnt/ unchanged between the two HEADs, clean at both
    ends, and equal to <tag> at both ends."""
    between_empty = not _git("diff", start["head"], end["head"], "--", "fedqpnt").strip()
    reasons = []
    if not between_empty:
        reasons.append("fedqpnt/ changed between start and end HEAD")
    if start["dirty"] or end["dirty"]:
        reasons.append(f"fedqpnt/ dirty: start={start['dirty']} end={end['dirty']}")
    if not (start["diff_vs_tag_empty"] and end["diff_vs_tag_empty"]):
        reasons.append(f"fedqpnt/ differs from {tag}")
    return dict(valid=not reasons, reasons=reasons, tag=tag, start=start, end=end)


# ---------------------------------------------------------------- args / preflight
def parse_seeds(txt: str) -> list[int]:
    out: list[int] = []
    for part in txt.replace(",", " ").split():
        if "-" in part:
            a, b = part.split("-", 1)
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(REPO), capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def check_code(tag: str) -> dict:
    """Code must equal <tag> on fedqpnt/ and the fedqpnt/ working tree must be clean (D-062)."""
    diff = _git("diff", tag, "HEAD", "--", "fedqpnt").strip()
    dirty = _git("status", "--porcelain", "--", "fedqpnt/").strip()
    if diff or dirty:
        raise SystemExit(f"CODE CHECK FAILED vs {tag}: diff={'non-empty' if diff else 'empty'} dirty={dirty!r}")
    return dict(tag=tag, tag_commit=_git("rev-parse", tag).strip(), head=_git("rev-parse", "HEAD").strip())


def all_ids() -> list[str]:
    return [s.id for s in SC.all_scenarios()]


def build(phase: str, seeds: list[int], weights: str):
    ids = all_ids()
    sel = [i for i in ids if (SC.get(i).requires_fl if phase == "2" else not SC.get(i).requires_fl)]
    return ids, C.generate_tasks(sel, None, seeds, detector_weights_path=weights, imu_grades=GRADES, final=True)


def is_long(task) -> bool:
    return (not task.is_fleet) and len(json.dumps(task.spec)) > LONG_SPEC_CHARS


# ---------------------------------------------------------------- claims
def claim(out_path) -> bool:
    cp = str(out_path) + ".claim"
    Path(cp).parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(cp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.write(fd, f"{os.getpid()} {time.ctime()}".encode())
    os.close(fd)
    return True


def release(out_path) -> None:
    try:
        os.remove(str(out_path) + ".claim")
    except OSError:
        pass


# ---------------------------------------------------------------- executors (run in worker processes)
def exec_spec_file(task: "C.RunTask", run_root: str, python_exe: str, timeout_s: int) -> dict:
    """Same record format/path as campaign._execute_one (+ launcher='spec_file'); spec passed via temp file."""
    out_path = task.result_path(Path(run_root))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="m4spec_")
    os.close(fd)
    Path(tmp).write_text(json.dumps(task.spec))
    t0 = time.time()
    base = dict(scenario_id=task.scenario_id, method=task.method, seed=task.seed, config_hash=task.hash,
                kappa_R_status=SC.KAPPA_R_STATUS, launcher="spec_file")
    try:
        proc = subprocess.run([python_exe, str(SPEC_FILE_SCRIPT), tmp], capture_output=True, text=True,
                              timeout=timeout_s, cwd=str(REPO))
    except subprocess.TimeoutExpired as exc:
        out_path.write_text(json.dumps(dict(status="timeout", **base, wall_s=time.time() - t0, stderr=str(exc)),
                                       default=str, indent=2))
        return dict(status="timeout")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    if proc.returncode != 0:
        out_path.write_text(json.dumps(dict(status="error", **base, wall_s=time.time() - t0,
                                            returncode=proc.returncode, stderr=proc.stderr[-4000:]),
                                       default=str, indent=2))
        return dict(status="error")
    try:
        metrics = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        metrics = dict(_parse_error=True, raw_stdout=proc.stdout[-2000:])
    out_path.write_text(json.dumps(dict(status="ok", **base, wall_s=time.time() - t0, metrics=metrics),
                                   default=str, indent=2))
    return dict(status="ok")


def run_node_task(task_dict: dict, run_root: str, python_exe: str) -> dict:
    """Claim -> (spec-file launcher if long else campaign._execute_one) -> release."""
    task = C.RunTask(**task_dict)
    out_path = task.result_path(Path(run_root))
    if C._is_done(out_path):
        return dict(status="skipped_done")
    if not claim(out_path):
        return dict(status="skipped_claimed")
    try:
        if C._is_done(out_path):
            return dict(status="skipped_done")
        C._enforce_task_seed(task.seed, True)
        if is_long(task):
            return exec_spec_file(task, run_root, python_exe, TIMEOUT_LONG_S)
        return C._execute_one(task_dict, run_root, python_exe, True)
    finally:
        release(out_path)


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", choices=["1", "2"], help="1 = single-node (pool), 2 = fleet (sequential)")
    ap.add_argument("--dry", action="store_true", help="build + assert + write manifest, run nothing")
    ap.add_argument("--seeds", default="10030-10059")
    ap.add_argument("--weights", required=True, help="detector weights path (no default)")
    ap.add_argument("--root", default="results/m4r2")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--reverse", action="store_true")
    ap.add_argument("--clear-claims", action="store_true")
    ap.add_argument("--tag", default=CODE_TAG)
    ap.add_argument("--only", default=None, help="run only this scenario id (base before @), e.g. S14")
    ap.add_argument("--take-reserved", action="store_true",
                    help="first drop RESERVED claims (placed by hand) on the selected tasks")
    a = ap.parse_args()
    if not a.dry and not a.phase:
        ap.error("--phase required unless --dry")

    seeds = parse_seeds(a.seeds)
    root = Path(a.root)
    assert seeds and all(SG_TEST_MIN <= s < SG_TEST_MAX for s in seeds), "seeds outside test range"
    assert seeds == list(range(seeds[0], seeds[-1] + 1)), "seed list not contiguous"
    code = check_code(a.tag)

    # ---- manifest (both phases) with assertions
    man_tasks = []
    counts: dict[str, int] = {}
    n_long = 0
    for ph in ("1", "2"):
        ids, tasks = build(ph, seeds, a.weights)
        for t in tasks:
            assert 10000 <= t.seed and t.seed in seeds, f"seed {t.seed} out of range"
            if not t.is_fleet:
                assert t.spec["detector_weights_path"] == a.weights, "task without the requested weights"
                assert t.spec.get("final") is True and t.spec["kappa_R"] == C.DEFAULT_KAPPA_R and t.spec["kappa_Q"] == 1.0
            counts[t.scenario_id] = counts.get(t.scenario_id, 0) + 1
            n_long += is_long(t)
            man_tasks.append(dict(rid=t.scenario_id, method=t.method, seed=t.seed, fleet=t.is_fleet, hash=t.hash,
                                  long_spec=is_long(t)))
    keys = [(m["rid"], m["method"], m["seed"]) for m in man_tasks]
    assert len(keys) == len(set(keys)), "duplicate tasks"
    root.mkdir(parents=True, exist_ok=True)
    manifest = dict(code=code, weights=a.weights, seeds=[seeds[0], seeds[-1]], grades=GRADES,
                    n_tasks=len(man_tasks), n_single=sum(not m["fleet"] for m in man_tasks),
                    n_fleet=sum(m["fleet"] for m in man_tasks), n_long_spec=n_long, per_result_id=counts,
                    fleet_note="fleet tasks use fleet_adapter.THETA0_PATH (results/fleet/theta0_d054.npz), "
                               "NOT --weights", tasks=man_tasks)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"manifest: {manifest['n_tasks']} tasks = {manifest['n_single']} single-node ({n_long} long-spec) "
          f"+ {manifest['n_fleet']} fleet; weights={a.weights}; code {code['tag']} == HEAD on fedqpnt/", flush=True)
    if a.dry:
        return

    # ---- launch checks
    assert Path(a.weights).exists(), f"weights file missing: {a.weights}"
    if a.phase == "2":
        prov = Path("results/fleet/theta0_d054_freeze5_provenance.json")
        assert prov.exists(), f"fleet theta0 not retrained on {a.tag}: {prov} missing; phase 2 refused"
    C.ensure_gate_file()
    assert C.gate_cleared(), "seed gate not cleared"
    if a.clear_claims:
        for cf in root.rglob("*.claim"):
            cf.unlink()
    prov0 = C.git_provenance()
    core0 = core_snapshot(a.tag)
    ids, tasks = build(a.phase, seeds, a.weights)
    if a.only:
        tasks = [t for t in tasks if t.scenario_id.split("@")[0] == a.only]
    if a.take_reserved:
        for t in tasks:
            cp = Path(str(t.result_path(root)) + ".claim")
            if cp.exists() and cp.read_text(errors="ignore").startswith("RESERVED"):
                cp.unlink()
    if a.phase == "1":
        tasks.sort(key=lambda t: not is_long(t))          # long S7-p2/p5 first so they don't tail
    if a.reverse:
        tasks = tasks[::-1]
    todo = [t for t in tasks if not C._is_done(t.result_path(root))]
    cnt: Counter = Counter()
    t0 = time.time()
    print(f"{time.ctime()} phase {a.phase} total {len(tasks)} todo {len(todo)} workers "
          f"{a.workers if a.phase == '1' else 1} reverse={a.reverse}", flush=True)
    if a.phase == "1":
        with ProcessPoolExecutor(max_workers=max(1, min(a.workers, 4))) as ex:
            futs = [ex.submit(run_node_task, asdict(t), str(root), sys.executable) for t in todo]
            for n, f in enumerate(as_completed(futs), 1):
                try:
                    st = f.result()["status"]
                except Exception as e:  # noqa: BLE001
                    st = "EXC:" + type(e).__name__
                cnt[st] += 1
                if n % 25 == 0 or st not in ("ok", "skipped_claimed", "skipped_done"):
                    print(f"{time.ctime()} {n}/{len(todo)} {dict(cnt)} elapsed {time.time() - t0:.0f}s", flush=True)
    else:
        for n, t in enumerate(todo, 1):
            out = t.result_path(root)
            if C._is_done(out):
                cnt["skipped_done"] += 1
                continue
            if not claim(out):
                cnt["skipped_claimed"] += 1
                continue
            try:
                r = C._execute_one_fleet(t, str(root), True)
                st = r["status"]
            except Exception as e:  # noqa: BLE001
                st = "EXC:" + type(e).__name__
            finally:
                release(out)
            cnt[st] += 1
            print(f"{time.ctime()} {n}/{len(todo)} {t.scenario_id} {t.method} {t.seed} {st}", flush=True)
    print("DONE", dict(cnt), f"wall {time.time() - t0:.0f}s", flush=True)
    v = C.provenance_verdict(prov0, C.git_provenance())
    fv = fedqpnt_verdict(core0, core_snapshot(a.tag), a.tag)
    C.record_provenance(root, dict(v, fedqpnt_verdict=fv, phase=a.phase, reverse=a.reverse))
    print("PROVENANCE frozen(whole-repo HEAD) valid:", v["valid"], v["reasons"], flush=True)
    print("PROVENANCE fedqpnt_verdict valid:", fv["valid"], fv["reasons"], flush=True)


from fedqpnt.eval import seed_gate as _SG  # noqa: E402
SG_TEST_MIN, SG_TEST_MAX = _SG.TEST_MIN, _SG.TEST_MAX

if __name__ == "__main__":
    main()
