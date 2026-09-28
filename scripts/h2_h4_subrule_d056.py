"""D-056 H2/H4 sub-rule protocol (implements DECISION_LOG D-056, amending
h2_h4_full_d054.py). kappa_R PROVISIONAL; TUNING SEEDS ONLY.

Reuses theta0_d054.npz (D-054.1: pretrained on seeds 400-449 restricted to
clean/abrupt/jam_* -- NO drift, NO meaconing -- so both drift and meaconing
are "novel" families for theta0) and the FL hyperparameters chosen by
fl_sanity_check_d054.py (local_epochs=2, lr=0.05, prox_mu=0, R=10, same for
all FL methods, D-054.3).

For each evaluated node/arm reports separately (D-056 item 1):
  (a) learned-detector-only AUC (raw calibrated p, E_s excluded) --
      `auc_detector_only` (node_runner.py, from the read-only
      TrustEngineImpl.last_raw_p side channel added for this task; does not
      change runtime behaviour).
  (b) operational p_bar AUC -- `auc` (existing field).
  (c) latency_on, t_dist (existing fields).
  (d) fraction of ATTACK epochs where E_s fired -- `es_fire_frac_attack`
      (from the read-only TrustEngineImpl.last_es_evidence side channel).

Sub-rule attack parameters (D-056 item 2, verified separately by
scripts/subrule_search_d056.py against a <=5% E_s-firing target):
  - drift:     severity in {0.5, 0.75}, cn0_sig_scale reduced from the D-018
    default of 1.0 (see NOVEL_DRIFT below for the chosen value + measured
    firing rate, filled in from the verification sweep).
  - meaconing: cn0_bump_db < 3.0 (the E_s rule threshold) and a small
    replay_delay_m so the clock-jump feature stays under es_clk_sigma=5.0.

H2: novel family absent from theta0 AND from n0's own local FL training
data, present in its 4 peers' local FL training data (N=5).
H4: cold-start -- n0 joins the federation at round 5/10, same sub-rule
attack on n0.
CONTROL: same protocol but with "abrupt", a family theta0 already saw AND
that is present in n0's OWN local training data too (a family n0 "did see
locally") -- expected FedQPNT ~= B-cont (no generalisation gap to close).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from fedqpnt.eval.stats import paired_test
from fedqpnt.fl.client import ClientConfig
from fedqpnt.fleet.orchestrator import FleetScenarioConfig, run_fleet
from fedqpnt.node.methods import load_detector_weights
from fedqpnt.training.build_supervised_dataset import plan_for

THETA0_PATH = Path("results/fleet/theta0_d054.npz")
N_NODES = 5
LIVE_DURATION_S = 600.0
LOCAL_TRAIN_DURATION_S = 120.0
ROUND_PERIOD_S = 60.0
N_ROUNDS = 10
CHOSEN = dict(local_epochs=2, lr=0.05, prox_mu=0.0)   # D-054.3 FL sanity check
LIVE_SEEDS = [500, 501, 502, 503, 504]                 # >=5 seeds per D-056 item 3/4

# D-056 item 2: sub-rule attack configs. cn0_sig_scale/cn0_bump_db/
# replay_delay_m chosen by scripts/subrule_search_d056.py to keep E_s firing
# <=5% of attack epochs (see docs/specs/raw/H2_SUBRULE_NOTES.md for the
# measured sweep this was picked from).
NOVEL_DRIFT = dict(kind="drift_spoof", onset_s=120.0, duration_s=300.0, severity=0.75,
                    params=dict(cn0_sig_scale=0.05))
NOVEL_MEACONING = dict(kind="meaconing", onset_s=120.0, duration_s=300.0, severity=1.0,
                        params=dict(cn0_bump_db=2.0, replay_delay_m=30.0))
CONTROL_ATTACK = dict(kind="abrupt_spoof", onset_s=120.0, duration_s=300.0, severity=0.6)

FAMILY_OF = {"drift": "drift", "meaconing": "meaconing", "abrupt": "abrupt"}


def _theta0():
    p = load_detector_weights(THETA0_PATH)
    if p is None:
        raise SystemExit(f"{THETA0_PATH} missing -- run scripts/pretrain_theta0_d054.py first")
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


def _empty_per_arm():
    return {"fedqpnt_local": {k: [] for k in METRIC_KEYS},
            "baseline_b_cont": {k: [] for k in METRIC_KEYS}}


def _record(per_arm, method, n0):
    for k in METRIC_KEYS:
        per_arm[method][k].append(n0.get(k))


def _summarize(per_arm) -> dict:
    out = {method: {k: _ci95(v[k]) for k in METRIC_KEYS} for method, v in per_arm.items()}
    # paired Wilcoxon (D-056 item 3): (a) detector-only AUC and latency_on,
    # FedQPNT vs B-cont, paired per seed (fedqpnt.eval.stats.paired_test).
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


def run_h2(theta0, param_names, attack: dict, family_name: str, tag: str) -> dict:
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
                scenario_id=f"h2_{tag}_{method}_seed{seed}", method=method, seed=seed, node_ids=ids,
                n_rounds=N_ROUNDS, round_period_s=ROUND_PERIOD_S, duration_s=LIVE_DURATION_S,
                client_cfg=ClientConfig(min_samples=8, **CHOSEN), attacks={"n0": attack},
                local_train_seeds={nid: local_seeds[nid] for nid in ids},
                local_train_pool={nid: "mixed" for nid in ids}, local_train_duration_s=LOCAL_TRAIN_DURATION_S,
            )
            result = run_fleet(scenario, theta0, param_names)
            n0 = result.node_results.get("n0", {})
            print(f"[H2-{tag} {method} seed{seed}] aborted={result.aborted} "
                  f"auc_det={n0.get('auc_detector_only')} auc_pbar={n0.get('auc')} "
                  f"latency_on={n0.get('latency_on')} es_frac={n0.get('es_fire_frac_attack')}")
            _record(per_arm, method, n0)
    return _summarize(per_arm)


def run_h2_control(theta0, param_names) -> dict:
    """CONTROL (D-056 item 5): family = 'abrupt' -- theta0 already saw it
    AND n0's own local FL data includes it (not excluded), unlike H2's
    novel-family design. Expect FedQPNT ~= B-cont (no generalisation gap)."""
    node_ids = [f"n{i}" for i in range(N_NODES)]
    per_arm = _empty_per_arm()
    for seed in LIVE_SEEDS:
        # every node (including n0) gets a mixed pool that naturally
        # contains 'abrupt' -- no exclusion/inclusion forcing, this is the
        # "n0 DID see it locally" arm.
        local_seeds = {f"n{i}": list(range(300_000 + seed * 100 + i * 1000,
                                            300_000 + seed * 100 + i * 1000 + 6))
                        for i in range(N_NODES)}
        for method, ids in (("fedqpnt_local", node_ids), ("baseline_b_cont", ["n0"])):
            scenario = FleetScenarioConfig(
                scenario_id=f"h2_control_abrupt_{method}_seed{seed}", method=method, seed=seed, node_ids=ids,
                n_rounds=N_ROUNDS, round_period_s=ROUND_PERIOD_S, duration_s=LIVE_DURATION_S,
                client_cfg=ClientConfig(min_samples=8, **CHOSEN), attacks={"n0": CONTROL_ATTACK},
                local_train_seeds={nid: local_seeds[nid] for nid in ids},
                local_train_pool={nid: "mixed" for nid in ids}, local_train_duration_s=LOCAL_TRAIN_DURATION_S,
            )
            result = run_fleet(scenario, theta0, param_names)
            n0 = result.node_results.get("n0", {})
            print(f"[H2-control seed{seed}] {method} aborted={result.aborted} "
                  f"auc_det={n0.get('auc_detector_only')} auc_pbar={n0.get('auc')} "
                  f"es_frac={n0.get('es_fire_frac_attack')}")
            _record(per_arm, method, n0)
    return _summarize(per_arm)


def run_h4(theta0, param_names, attack: dict, family_name: str, tag: str) -> dict:
    node_ids = [f"n{i}" for i in range(N_NODES)]
    per_arm = _empty_per_arm()
    for seed in LIVE_SEEDS:
        # cold-start: n0 has no prior FL benefit before round 5, but still
        # needs SOME local data to exist as a client; exclude the novel
        # family from n0/peers pre-join the same way as H2 (peers carry it).
        local_seeds = {
            "n0": _seeds_excluding_family(400_000 + seed * 100, family_name, 6),
            **{f"n{i}": _seeds_including_family(400_000 + seed * 100 + i * 1000, family_name, 6)
               for i in range(1, N_NODES)},
        }
        for method, ids, join in (("fedqpnt_local", node_ids, {"n0": 5}), ("baseline_b_cont", ["n0"], {})):
            scenario = FleetScenarioConfig(
                scenario_id=f"h4_{tag}_{method}_seed{seed}", method=method, seed=seed, node_ids=ids,
                n_rounds=N_ROUNDS, round_period_s=ROUND_PERIOD_S, duration_s=LIVE_DURATION_S,
                client_cfg=ClientConfig(min_samples=8, **CHOSEN), attacks={"n0": attack}, join_round=join,
                local_train_seeds={nid: local_seeds[nid] for nid in ids},
                local_train_pool={nid: "mixed" for nid in ids}, local_train_duration_s=LOCAL_TRAIN_DURATION_S,
            )
            result = run_fleet(scenario, theta0, param_names)
            n0 = result.node_results.get("n0", {})
            print(f"[H4-{tag} {method} seed{seed}] aborted={result.aborted} "
                  f"auc_det={n0.get('auc_detector_only')} auc_pbar={n0.get('auc')} "
                  f"installs={n0.get('round_installs')} es_frac={n0.get('es_fire_frac_attack')}")
            _record(per_arm, method, n0)
    return _summarize(per_arm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="h2_drift,h4_drift,h2_control",
                    help="comma list from {h2_drift,h2_meaconing,h4_drift,h4_meaconing,h2_control}")
    ap.add_argument("--out", default="results/fleet/h2_h4_subrule_d056.json")
    args = ap.parse_args()
    parts = set(args.parts.split(","))

    theta0, param_names = _theta0()
    report: dict = dict(note="kappa_R PROVISIONAL; tuning seeds",
                         chosen_hyperparams=CHOSEN, n_rounds=N_ROUNDS, live_seeds=LIVE_SEEDS,
                         live_duration_s=LIVE_DURATION_S, local_train_duration_s=LOCAL_TRAIN_DURATION_S,
                         novel_drift=NOVEL_DRIFT, novel_meaconing=NOVEL_MEACONING, control_attack=CONTROL_ATTACK)

    out_path = Path(args.out)
    if out_path.exists():
        report.update(json.loads(out_path.read_text()))

    if "h2_drift" in parts:
        print("=== H2 (novel family = drift, sub-rule) ===")
        report["h2_drift"] = run_h2(theta0, param_names, NOVEL_DRIFT, "drift", "drift")
        out_path.write_text(json.dumps(report, indent=2, default=str))
    if "h2_meaconing" in parts:
        print("=== H2 (novel family = meaconing, sub-rule) ===")
        report["h2_meaconing"] = run_h2(theta0, param_names, NOVEL_MEACONING, "meaconing", "meaconing")
        out_path.write_text(json.dumps(report, indent=2, default=str))
    if "h4_drift" in parts:
        print("=== H4 (cold-start, novel family = drift, sub-rule) ===")
        report["h4_drift"] = run_h4(theta0, param_names, NOVEL_DRIFT, "drift", "drift")
        out_path.write_text(json.dumps(report, indent=2, default=str))
    if "h4_meaconing" in parts:
        print("=== H4 (cold-start, novel family = meaconing, sub-rule) ===")
        report["h4_meaconing"] = run_h4(theta0, param_names, NOVEL_MEACONING, "meaconing", "meaconing")
        out_path.write_text(json.dumps(report, indent=2, default=str))
    if "h2_control" in parts:
        print("=== H2 CONTROL (family = abrupt, n0 DID see it locally) ===")
        report["h2_control_abrupt"] = run_h2_control(theta0, param_names)
        out_path.write_text(json.dumps(report, indent=2, default=str))

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
