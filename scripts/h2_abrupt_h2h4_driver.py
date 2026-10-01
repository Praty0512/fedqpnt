"""H2-ABRUPT steps 3-5: H2, H4, and the drift-control fleet runs, with
'abrupt' as the NOVEL family (theta0_noabrupt_v2.npz never saw it; n0's own
local FL data excludes it; peers' local data includes it).

Adapts scripts/h2_h4_subrule_d056.py's run_h2/run_h4 (already generic over
attack dict / family_name / tag -- no changes needed there, this is a NEW
script per the task's "write new scripts only" rule, not an edit) pointed
at:
  - theta0 = results/fleet/theta0_noabrupt_v2.npz (h2_abrupt_pretrain_theta0.py)
  - attack = abrupt_spoof, severity=0.15 (chosen by h2_abrupt_es_firing_check.py:
    0.6/0.4/0.2 all fire E_s above the 5% target under the CURRENT (CORE-ROBUST
    nav_prior-fixed) D-058 short-baseline jump test; 0.15 and 0.1 both pass at
    0% pooled firing over seeds 500-504; 0.15 chosen to keep more signal
    (12 m jump vs 0.1's 8 m) while still passing.
  - family_name = "abrupt" (for the exclude/include seed-partition helpers)

CONTROL: family n0 DID see (drift, full severity s=1, the family theta0
already saw AND is naturally present in every node's local mixed pool --
no forced exclusion/inclusion, unlike H2). Expect FedQPNT ~= B-cont (no
generalisation gap to close), same design-check role as D-056 item 5's
abrupt control, just swapped to drift here since abrupt is now the novel
family under test.

Same N=5, >=5 seeds [500-504], 600 s live missions, CHOSEN hyperparams
(local_epochs=2, lr=0.05, mu=0, R=10, D-054.3/D-056) as h2_h4_subrule_d056.py.
Fleets run STRICTLY SEQUENTIALLY (one run_fleet call at a time; each spawns
1 server + N node processes per fedqpnt/fleet/orchestrator.py).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from fedqpnt.eval.stats import paired_test
from fedqpnt.fl.client import ClientConfig
from fedqpnt.fleet.orchestrator import FleetScenarioConfig, run_fleet
from fedqpnt.node.methods import load_detector_weights
from fedqpnt.training.build_supervised_dataset import plan_for

THETA0_PATH = Path("results/fleet/theta0_noabrupt_v2.npz")
N_NODES = 5
LIVE_DURATION_S = 600.0
LOCAL_TRAIN_DURATION_S = 120.0
ROUND_PERIOD_S = 60.0
N_ROUNDS = 10
CHOSEN = dict(local_epochs=2, lr=0.05, prox_mu=0.0)   # D-054.3 FL sanity check
LIVE_SEEDS = list(range(500, 510))   # n=10 per H2_PREREG (D-064)

# Step 2 result: severity 0.15 (12 m jump) is the largest tested value that
# still keeps es_fire_frac_attack at 0% pooled over seeds 500-504 (0.2/16m
# fires at 9.8%, 0.6 default-control-value/48m fires at 15.6%).
NOVEL_ABRUPT = dict(kind="abrupt_spoof", onset_s=120.0, duration_s=300.0, severity=0.15)
FAMILY_NAME = "abrupt"

# CONTROL: drift, full severity (s=1), a family theta0_noabrupt DID see in
# pretraining and that is naturally present in every node's own local pool.
CONTROL_ATTACK = dict(kind="drift_spoof", onset_s=120.0, duration_s=300.0, severity=1.0)


def _theta0():
    p = load_detector_weights(THETA0_PATH)
    if p is None:
        raise SystemExit(f"{THETA0_PATH} missing -- run scripts/h2_abrupt_pretrain_theta0.py first")
    return p, list(p.keys())


def _seeds_excluding_family(base: int, family_name: str, count: int) -> list[int]:
    out, s = [], base
    while len(out) < count:
        fam, _atk = plan_for(s, "mixed")
        if fam != family_name:
            out.append(s)
        s += 1
    return out


def _seeds_including_family(base: int, family_name: str, count: int) -> list[int]:
    s, first = base, None
    while first is None:
        fam, _atk = plan_for(s, "mixed")
        if fam == family_name:
            first = s
        s += 1
    out = [first]
    s = base
    while len(out) < count:
        if s != first:
            out.append(s)
        s += 1
    return sorted(out)


def _ci95(vals: list[float]) -> dict:
    a = np.array([v for v in vals if v is not None and np.isfinite(v)], dtype=float)
    if len(a) == 0:
        return dict(mean=float("nan"), ci95=float("nan"), n=0)
    mean = float(np.mean(a))
    sd = float(np.std(a, ddof=1)) if len(a) > 1 else 0.0
    ci = 1.96 * sd / np.sqrt(len(a)) if len(a) > 1 else 0.0
    return dict(mean=mean, sd=sd, ci95=ci, n=len(a), values=a.tolist())


METRIC_KEYS = ("auc_detector_only", "auc", "latency_on", "t_dist", "es_fire_frac_attack")

# D-062 item 3 (Master ruling): the FIRST driver run (08:38-10:24) did not
# persist fedqpnt/fleet/node_runner.py's own per-round provenance
# (hash_pre/hash_post_train/hash_post_install, round_installs,
# final_theta_hash -- all already computed and returned in
# result.node_results["n0"], D-054's own provenance diagnostic) before the
# process exited; that data is now unrecoverable for that run. THIS driver
# now persists it in full, per (part, seed, method), to
# results/fleet/h2_abrupt_provenance.json, so a re-run can answer D-062 item
# 1 directly from real telemetry instead of an offline replay.
PROVENANCE_KEYS = ("round_installs", "provenance", "final_theta_hash")


def _git_state() -> dict:
    def _run(args):
        try:
            return subprocess.run(args, cwd=str(Path(__file__).resolve().parent.parent),
                                   capture_output=True, text=True, timeout=15).stdout.strip()
        except Exception as exc:  # noqa: BLE001
            return f"<git call failed: {exc!r}>"
    return dict(head=_run(["git", "rev-parse", "HEAD"]), fedqpnt_tree=_run(["git", "rev-parse", "HEAD:fedqpnt"]),
                status_porcelain_fedqpnt=_run(["git", "status", "--porcelain", "fedqpnt/"]))


RUNS_DIR = Path("results/fleet/h2_abrupt_runs")


def _run_or_load(part, method, seed, scenario, theta0, param_names):
    """Runs ONE fleet (sequential) and persists n0's full result (incl. epoch_* 1 Hz arrays,
    provenance) + the arm's FINAL installed model + git state; resumable (skips finished runs)."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stem = RUNS_DIR / f"{part}_{method}_seed{seed}"
    jpath = stem.with_suffix(".json")
    if jpath.exists():
        rec = json.loads(jpath.read_text())
        print(f"[resume] {jpath.name} already done")
        return rec["n0"], rec["aborted"]
    git0 = _git_state()
    result = run_fleet(scenario, theta0, param_names)
    n0 = result.node_results.get("n0", {})
    git1 = _git_state()
    if result.final_theta is not None:
        np.savez(stem.with_suffix(".npz"), **{k: np.asarray(v) for k, v in result.final_theta.items()})
    rec = dict(part=part, method=method, seed=seed, aborted=bool(result.aborted), wall_s=result.wall_s,
               git_start=git0, git_end=git1, fedqpnt_changed_during_run=((git0['fedqpnt_tree'], git0['status_porcelain_fedqpnt']) != (git1['fedqpnt_tree'], git1['status_porcelain_fedqpnt'])), n0=n0)
    jpath.write_text(json.dumps(rec, default=str))
    return n0, bool(result.aborted)


def _empty_per_arm():
    return {"fedqpnt_local": {k: [] for k in METRIC_KEYS},
            "baseline_b_cont": {k: [] for k in METRIC_KEYS}}


def _record(per_arm, method, n0, provenance_log=None, part=None, seed=None):
    for k in METRIC_KEYS:
        per_arm[method][k].append(n0.get(k))
    if provenance_log is not None:
        provenance_log.append(dict(part=part, seed=seed, method=method,
                                    **{k: n0.get(k) for k in PROVENANCE_KEYS}))


def _summarize(per_arm) -> dict:
    out = {method: {k: _ci95(v[k]) for k in METRIC_KEYS} for method, v in per_arm.items()}
    for key in ("auc_detector_only", "latency_on"):
        x = np.array(per_arm["fedqpnt_local"][key], dtype=float)
        y = np.array(per_arm["baseline_b_cont"][key], dtype=float)
        mask = np.isfinite(x) & np.isfinite(y)
        if mask.sum() >= 1:
            r = paired_test(x[mask], y[mask])
            out[f"wilcoxon_{key}"] = dict(n=r.n, diff_mean=r.diff_mean,
                                           wilcoxon_stat=r.wilcoxon_stat, wilcoxon_p=r.wilcoxon_p)
        else:
            out[f"wilcoxon_{key}"] = dict(n=0, note="insufficient finite pairs")
    return out


def run_h2(theta0, param_names, attack: dict, family_name: str, tag: str, provenance_log: list) -> dict:
    PART = "h2_abrupt"
    node_ids = [f"n{i}" for i in range(N_NODES)]
    per_arm = _empty_per_arm()
    for seed in LIVE_SEEDS:
        local_seeds = {
            "n0": _seeds_excluding_family(300_000 + seed * 100, family_name, 6),
            **{f"n{i}": _seeds_including_family(300_000 + seed * 100 + i * 1000, family_name, 6)
               for i in range(1, N_NODES)},
        }
        for method, ids in (("fedqpnt_local", node_ids), ("baseline_b_cont", ["n0"])):
            scenario = FleetScenarioConfig(
                scenario_id=f"h2abrupt_{tag}_{method}_seed{seed}", method=method, seed=seed, node_ids=ids,
                n_rounds=N_ROUNDS, round_period_s=ROUND_PERIOD_S, duration_s=LIVE_DURATION_S,
                client_cfg=ClientConfig(min_samples=8, **CHOSEN), attacks={"n0": attack},
                local_train_seeds={nid: local_seeds[nid] for nid in ids},
                local_train_pool={nid: "mixed" for nid in ids}, local_train_duration_s=LOCAL_TRAIN_DURATION_S,
            )
            n0, aborted = _run_or_load(PART, method, seed, scenario, theta0, param_names)
            print(f"[H2-{tag} {method} seed{seed}] aborted={aborted} "
                  f"auc_det={n0.get('auc_detector_only')} auc_pbar={n0.get('auc')} "
                  f"latency_on={n0.get('latency_on')} es_frac={n0.get('es_fire_frac_attack')} "
                  f"installs={n0.get('round_installs')}")
            _record(per_arm, method, n0, provenance_log, part="h2_abrupt", seed=seed)
    return _summarize(per_arm)


def run_h4(theta0, param_names, attack: dict, family_name: str, tag: str, provenance_log: list) -> dict:
    PART = "h4_abrupt"
    node_ids = [f"n{i}" for i in range(N_NODES)]
    per_arm = _empty_per_arm()
    for seed in LIVE_SEEDS:
        local_seeds = {
            "n0": _seeds_excluding_family(400_000 + seed * 100, family_name, 6),
            **{f"n{i}": _seeds_including_family(400_000 + seed * 100 + i * 1000, family_name, 6)
               for i in range(1, N_NODES)},
        }
        for method, ids, join in (("fedqpnt_local", node_ids, {"n0": 5}), ("baseline_b_cont", ["n0"], {})):
            scenario = FleetScenarioConfig(
                scenario_id=f"h4abrupt_{tag}_{method}_seed{seed}", method=method, seed=seed, node_ids=ids,
                n_rounds=N_ROUNDS, round_period_s=ROUND_PERIOD_S, duration_s=LIVE_DURATION_S,
                client_cfg=ClientConfig(min_samples=8, **CHOSEN), attacks={"n0": attack}, join_round=join,
                local_train_seeds={nid: local_seeds[nid] for nid in ids},
                local_train_pool={nid: "mixed" for nid in ids}, local_train_duration_s=LOCAL_TRAIN_DURATION_S,
            )
            n0, aborted = _run_or_load(PART, method, seed, scenario, theta0, param_names)
            print(f"[H4-{tag} {method} seed{seed}] aborted={aborted} "
                  f"auc_det={n0.get('auc_detector_only')} auc_pbar={n0.get('auc')} "
                  f"installs={n0.get('round_installs')} es_frac={n0.get('es_fire_frac_attack')}")
            _record(per_arm, method, n0, provenance_log, part="h4_abrupt", seed=seed)
    return _summarize(per_arm)


def run_control(theta0, param_names, attack: dict, provenance_log: list) -> dict:
    """CONTROL: family n0 DID see (drift, s=1) -- naturally present in every
    node's local mixed pool, no forced exclusion/inclusion. Expect
    FedQPNT ~= B-cont (no generalisation gap)."""
    PART = "control_drift"
    node_ids = [f"n{i}" for i in range(N_NODES)]
    per_arm = _empty_per_arm()
    for seed in LIVE_SEEDS:
        local_seeds = {f"n{i}": list(range(300_000 + seed * 100 + i * 1000,
                                            300_000 + seed * 100 + i * 1000 + 6))
                        for i in range(N_NODES)}
        for method, ids in (("fedqpnt_local", node_ids), ("baseline_b_cont", ["n0"])):
            scenario = FleetScenarioConfig(
                scenario_id=f"h2abrupt_control_drift_{method}_seed{seed}", method=method, seed=seed, node_ids=ids,
                n_rounds=N_ROUNDS, round_period_s=ROUND_PERIOD_S, duration_s=LIVE_DURATION_S,
                client_cfg=ClientConfig(min_samples=8, **CHOSEN), attacks={"n0": attack},
                local_train_seeds={nid: local_seeds[nid] for nid in ids},
                local_train_pool={nid: "mixed" for nid in ids}, local_train_duration_s=LOCAL_TRAIN_DURATION_S,
            )
            n0, aborted = _run_or_load(PART, method, seed, scenario, theta0, param_names)
            print(f"[control-drift {method} seed{seed}] aborted={aborted} "
                  f"auc_det={n0.get('auc_detector_only')} auc_pbar={n0.get('auc')} "
                  f"es_frac={n0.get('es_fire_frac_attack')} installs={n0.get('round_installs')}")
            _record(per_arm, method, n0, provenance_log, part="control_drift", seed=seed)
    return _summarize(per_arm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="h2,h4,control",
                    help="comma list from {h2,h4,control}")
    ap.add_argument("--out", default="results/fleet/h2_abrupt.json")
    ap.add_argument("--provenance-out", default="results/fleet/h2_abrupt_provenance.json")
    args = ap.parse_args()
    parts = set(args.parts.split(","))

    theta0, param_names = _theta0()
    git_start = _git_state()
    print(f"git state at launch: {git_start}")
    report: dict = dict(note="H2-ABRUPT: novel family=abrupt (theta0_noabrupt), "
                              "severity=0.15 (E_s-quiet, chosen by h2_abrupt_es_firing_check.py)",
                         chosen_hyperparams=CHOSEN, n_rounds=N_ROUNDS, live_seeds=LIVE_SEEDS,
                         live_duration_s=LIVE_DURATION_S, local_train_duration_s=LOCAL_TRAIN_DURATION_S,
                         novel_abrupt=NOVEL_ABRUPT, control_attack=CONTROL_ATTACK,
                         git_state_at_launch=git_start)

    out_path = Path(args.out)
    if out_path.exists():
        report.update(json.loads(out_path.read_text()))

    prov_path = Path(args.provenance_out)
    provenance_log: list = json.loads(prov_path.read_text()) if prov_path.exists() else []

    def _flush_provenance():
        prov_path.parent.mkdir(parents=True, exist_ok=True)
        prov_path.write_text(json.dumps(provenance_log, indent=2, default=str))

    if "h2" in parts:
        print("=== H2 (novel family = abrupt) ===")
        report["h2_abrupt"] = run_h2(theta0, param_names, NOVEL_ABRUPT, FAMILY_NAME, "abrupt", provenance_log)
        out_path.write_text(json.dumps(report, indent=2, default=str))
        _flush_provenance()
    if "h4" in parts:
        print("=== H4 (cold-start, novel family = abrupt) ===")
        report["h4_abrupt"] = run_h4(theta0, param_names, NOVEL_ABRUPT, FAMILY_NAME, "abrupt", provenance_log)
        out_path.write_text(json.dumps(report, indent=2, default=str))
        _flush_provenance()
    if "control" in parts:
        print("=== CONTROL (family = drift, s=1, n0 DID see it locally) ===")
        report["control_drift"] = run_control(theta0, param_names, CONTROL_ATTACK, provenance_log)
        out_path.write_text(json.dumps(report, indent=2, default=str))
        _flush_provenance()

    git_end = _git_state()
    print(f"git state at end: {git_end}")
    report["git_state_at_end"] = git_end
    if (git_start['fedqpnt_tree'], git_start['status_porcelain_fedqpnt']) != (git_end['fedqpnt_tree'], git_end['status_porcelain_fedqpnt']):
        report["WARNING_code_changed_during_run"] = True
        print("WARNING: git state changed during this run -- results used mixed code, per D-062 item 3 -- "
              "DO NOT treat this run as valid; re-run after the core is frozen.")
    out_path.write_text(json.dumps(report, indent=2, default=str))

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
