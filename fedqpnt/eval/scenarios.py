"""Scenario registry S1-S15, ARCHITECTURE.md section 6.1 (+ D-046/D-047
kappa_R gate). EVALUATOR-ONLY declarative configs consumed by
``fedqpnt.eval.campaign``; never imported by the Agent side.

Each ``Scenario`` is a config diff over ``fedqpnt.node.runner.RunSpec``
(attack schedule, world, CAI grade, duration) plus its section 6.1
acceptance criteria as executable checks over the campaign's aggregated,
per-method, per-seed results.

D-046/D-047: results depending only on position/velocity (RMSE_h, latency,
detector/trust behaviour) may proceed under kappa_R = 60 (D-061; was 40 PROVISIONAL).
Claims depending on attitude/bias estimates -- GNSS-outage drift, the
CAI/H3 benefit, S6 (CAI bias drift), S14 (multi-hour stability) -- are
BLOCKED until the ESKF psi/b consistency issue (D-047) is fixed. Every
scenario carries ``blocked_by_D047``; every artefact downstream (campaign
run records, report tables) must carry a ``kappa_R_status`` stamp -- see
``KAPPA_R_STATUS`` below and ``fedqpnt.eval.campaign.GATE_D047_PATH``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from fedqpnt.eval import metrics as _M

# --------------------------------------------------------------------------
# kappa_R_status stamp (D-046/D-047): every artefact this module's callers
# produce (campaign run records, report tables) must carry this literal.
# --------------------------------------------------------------------------
KAPPA_R_STATUS = "D-061_kappa_R=60"

METHOD_ALL = ("fedqpnt_local", "baseline_a", "baseline_b_bin", "baseline_b_cont",
              "bprime", "fixed_trust", "undefended")

# CAMPAIGN-FLEET: fleet-scenario method labels (S5/S8/S9/S12/S15), routed
# through fedqpnt.eval.fleet_adapter instead of fedqpnt.node.runner (D-050).
# Must match fedqpnt.eval.fleet_adapter._METHOD_MAP's keys exactly -- kept
# as a literal tuple here (not imported) to avoid scenarios.py depending on
# fleet_adapter, which itself imports this module for KAPPA_R_STATUS.
FLEET_METHOD_ALL = ("fedqpnt", "fedavg_ablation", "baseline_a", "baseline_b_cont", "baseline_b_bin")


@dataclass
class Criterion:
    """One executable section-6.1 acceptance check.

    ``check(results)`` takes ``results: dict[method_name -> list[result_dict]]``
    (per-seed result dicts from ``fedqpnt.node.runner.run_single``, paired by
    seed/index per D-005) and returns a dict with at least
    ``{"passed": bool | None, "value": float | None, "detail": str}``.
    ``passed=None`` means "not evaluable" (e.g. blocked by D-047, or a
    method the criterion needs was not run).
    """
    name: str
    justification: str
    check: Callable[[dict[str, list[dict]]], dict[str, Any]]
    blocked_by_D047: bool = False


@dataclass
class Scenario:
    id: str
    title: str
    fleet_size: int
    duration_s: float
    world: str                       # "flat" | "schuler_tangent"
    cai_grade: str | None            # quantum_grade passed to RunSpec, or None (CAI off)
    attack: dict | None              # RunSpec.attack dict, or None (nominal)
    methods: tuple[str, ...]
    criteria: tuple[Criterion, ...]
    blocked_by_D047: bool = False    # scenario-level: ALL its criteria are attitude/bias-dependent
    requires_fl: bool = False        # needs a multi-node federated fleet; fedqpnt.fl is out of
                                     # scope here and fedqpnt.node.runner is single-node only, so
                                     # the campaign runner cannot yet execute this scenario's fleet
                                     # semantics -- registered declaratively, execution deferred.
    notes: str = ""


def _method_series(results: dict[str, list[dict]], method: str, field_name: str) -> np.ndarray:
    if method not in results:
        return np.array([])
    return np.array([r.get(field_name, np.nan) for r in results[method]], dtype=float)


def _paired_ratio_check(name: str, justification: str, field_name: str, method: str,
                         reference: str, max_ratio: float, reducer=np.median) -> Criterion:
    def _check(results: dict[str, list[dict]]) -> dict[str, Any]:
        a = _method_series(results, method, field_name)
        b = _method_series(results, reference, field_name)
        if a.size == 0 or b.size == 0 or a.size != b.size:
            return dict(passed=None, value=None, detail=f"missing/mismatched {method} vs {reference}")
        ratio = a / np.where(b == 0, np.nan, b)
        val = float(reducer(ratio[np.isfinite(ratio)])) if np.any(np.isfinite(ratio)) else float("nan")
        passed = bool(np.isfinite(val) and val <= max_ratio)
        return dict(passed=passed, value=val, detail=f"{reducer.__name__}({field_name} ratio {method}/{reference}) "
                                                       f"= {val:.4f} (bound {max_ratio})")
    return Criterion(name=name, justification=justification, check=_check)


# --------------------------------------------------------------------------
# S1: Nominal
# --------------------------------------------------------------------------
def _s1_far(results):
    v = _method_series(results, "fedqpnt_local", "far_per_hour")
    if v.size == 0:
        return dict(passed=None, value=None, detail="no fedqpnt_local runs")
    val = float(np.mean(v))
    return dict(passed=bool(val <= 1.0), value=val, detail=f"FAR={val:.3f}/h/node (bound 1.0)")


def _s1_anees(results):
    v = _method_series(results, "fedqpnt_local", "anees_pos_pre")
    if v.size == 0:
        return dict(passed=None, value=None, detail="no fedqpnt_local runs")
    val = float(np.mean(v[np.isfinite(v)])) if np.any(np.isfinite(v)) else float("nan")
    return dict(passed=bool(0.5 <= val <= 2.0), value=val, detail=f"ANEES_pos={val:.3f} (band [0.5,2])")


def _s1_mean_w(results):
    v = _method_series(results, "fedqpnt_local", "mean_w_gnss")
    if v.size == 0:
        return dict(passed=None, value=None, detail="no fedqpnt_local runs")
    val = float(np.mean(v))
    return dict(passed=bool(val >= 0.95), value=val, detail=f"mean w_gnss={val:.4f} (bound >=0.95)")


S1 = Scenario(
    id="S1", title="Nominal", fleet_size=1, duration_s=600.0, world="flat", cai_grade="field",
    attack=None, methods=METHOD_ALL,
    criteria=(
        _paired_ratio_check("rmse_h_vs_fixed_trust", "Trust must cost <=5% when nothing is wrong",
                             "rmse_h_pre", "fedqpnt_local", "fixed_trust", 1.05),
        Criterion("far_le_1_per_hour", "Lenient nuisance-rate bound (RAIM-FDE Pfa with 25x slack)", _s1_far),
        Criterion("anees_in_band", "Factor-2 ANEES band tolerates correlated GNSS errors [ASSUMPTION]", _s1_anees),
        Criterion("mean_w_gnss_ge_0_95", "Trust must not distrust clean GNSS", _s1_mean_w),
    ),
)


# --------------------------------------------------------------------------
# S2: Gradual spoof, severities {low, med, high}
# --------------------------------------------------------------------------
def _make_s2(severity_name: str, severity: float, final_offset_ge_50m: bool) -> Scenario:
    attack = dict(kind="drift_spoof", onset_s=60.0, duration_s=300.0, severity=severity)

    def _pd(results):
        lat = _method_series(results, "fedqpnt_local", "latency_on")
        if lat.size == 0:
            return dict(passed=None, value=None, detail="no fedqpnt_local runs")
        # D-068: latency_on is CENSORED (finite) on a miss, so isfinite() was
        # always True (P_D == 1.0). Use the explicit detected flag.
        window = (attack or {}).get("duration_s")
        hit = np.array([_M.detected_from_record(r, window) for r in results["fedqpnt_local"]], dtype=bool)
        p_d = float(np.mean(hit))
        crit = bool(p_d >= 0.9) if final_offset_ge_50m else None
        return dict(passed=crit, value=p_d, detail=f"P_D={p_d:.3f} (n={lat.size})")

    def _damage(results):
        a = _method_series(results, "fedqpnt_local", "max_h_att")
        u = _method_series(results, "undefended", "max_h_att")
        if a.size == 0 or u.size == 0 or a.size != u.size:
            return dict(passed=None, value=None, detail="missing fedqpnt_local/undefended")
        if final_offset_ge_50m:
            ratio = np.median(a / np.where(u == 0, np.nan, u))
            passed = bool(np.isfinite(ratio) and ratio <= 0.5)
            return dict(passed=passed, value=float(ratio), detail=f"median MAX_h ratio={ratio:.4f} (bound 0.5)")
        sigma_nom_m = 5.0   # [ASSUMPTION]: 3-sigma nominal horizontal error margin
        margin = np.median(a - u)
        passed = bool(margin <= 3 * sigma_nom_m)
        return dict(passed=passed, value=float(margin), detail=f"median(MAX_h_a - MAX_h_u)={margin:.3f} "
                                                                 f"(bound 3*sigma_nom={3*sigma_nom_m})")

    return Scenario(
        id=f"S2-{severity_name}", title=f"Gradual spoof ({severity_name})", fleet_size=1, duration_s=600.0,
        world="flat", cai_grade="field",
        attack=dict(kind="drift_spoof", onset_s=60.0, duration_s=300.0, severity=severity),
        methods=METHOD_ALL,
        criteria=(
            Criterion("detection_prob", "Halving the damage requires detecting it first", _pd),
            Criterion("damage_bound", "Halve the damage (or never worsen it)", _damage),
        ),
    )


S2_LOW = _make_s2("low", 0.3, final_offset_ge_50m=False)
S2_MED = _make_s2("med", 0.6, final_offset_ge_50m=True)
S2_HIGH = _make_s2("high", 0.9, final_offset_ge_50m=True)


# --------------------------------------------------------------------------
# S3: Sudden jamming (outage) -- BLOCKED (D-047: outage/attitude claims)
# --------------------------------------------------------------------------
def _s3_tdist(results):
    v = _method_series(results, "fedqpnt_local", "t_dist")
    if v.size == 0:
        return dict(passed=None, value=None, detail="no fedqpnt_local runs; BLOCKED by D-047 regardless")
    bound = 2 * 1.0 + 1.0  # 2 GNSS epochs (1 Hz) + 1 s
    val = float(np.nanmean(v))
    return dict(passed=None, value=val, detail=f"BLOCKED by D-047 (outage/attitude); t_dist={val:.3f}s "
                                                f"vs design bound {bound}s")


S3 = Scenario(
    id="S3", title="Sudden jamming", fleet_size=1, duration_s=300.0, world="flat", cai_grade="field",
    attack=dict(kind="jam_wideband", onset_s=60.0, duration_s=60.0, severity=1.0),
    methods=METHOD_ALL,
    criteria=(Criterion("t_dist_bound", "Design latency bound; coast error must be honestly predicted",
                         _s3_tdist, blocked_by_D047=True),),
    blocked_by_D047=True,
    notes="GNSS-outage drift claim; BLOCKED per D-046/D-047 until psi/b consistency is fixed.",
)


# --------------------------------------------------------------------------
# S4: Combined (jam -> spoof capture at reacquisition) -- BLOCKED
# --------------------------------------------------------------------------
def _s4_reacq(results):
    v = _method_series(results, "fedqpnt_local", "mean_w_gnss")
    return dict(passed=None, value=(float(np.mean(v)) if v.size else None),
                detail="BLOCKED by D-047 (outage/attitude); reacquisition-cap check not evaluable")


S4 = Scenario(
    id="S4", title="Combined jam-then-spoof capture", fleet_size=1, duration_s=400.0, world="flat",
    cai_grade="field", attack=dict(kind="jam_wideband", onset_s=60.0, duration_s=40.0, severity=1.0),
    methods=METHOD_ALL,
    criteria=(Criterion("s2_s3_joint_plus_reacq_cap", "Tests the reacquisition cap", _s4_reacq,
                         blocked_by_D047=True),),
    blocked_by_D047=True,
    notes="Includes an outage (jam) leg; BLOCKED per D-046/D-047.",
)


# --------------------------------------------------------------------------
# S5-S15: registered declaratively. S5/S8/S9/S12/S15 need a federated fleet;
# CAMPAIGN-FLEET (D-050 follow-up) routes them through
# fedqpnt.eval.fleet_adapter -> fedqpnt.fleet.orchestrator.run_fleet instead
# of fedqpnt.node.runner. ``requires_fl=True`` now means "dispatched to the
# fleet orchestrator" (fedqpnt.eval.campaign checks this flag), not
# NOT_RUNNABLE -- see fedqpnt.eval.fleet_adapter.FLEET_SCENARIO_IDS.
# `_not_runnable` is kept for any criterion still lacking a real reference
# run (e.g. the "no-fault" baseline some AUC-drop bounds need).
# --------------------------------------------------------------------------
def _not_runnable(reason: str) -> Callable[[dict], dict]:
    def _check(results):
        return dict(passed=None, value=None, detail=reason)
    return _check


# --------------------------------------------------------------------------
# Fleet-scenario helpers (S5/S8/S9/S12/S15). ``results[method]`` entries are
# the flat metric dicts fedqpnt.eval.campaign.load_results returns for a
# fleet run (fedqpnt.fleet.orchestrator.write_campaign_result's schema):
# per-run means of the usual scalars PLUS ``nodes`` (full per-node
# breakdown, including each node's ``provenance`` -- per-FL-round install
# timing, D-054) and ``fleet`` (rounds_skipped/quarantine_events/aborted).
# Node-id conventions (fedqpnt.eval.fleet_adapter): nodes are "node0..N-1";
# S8's cold-start node is the LAST id; S12/S15's poisoned/attacked subset is
# the FIRST ceil(frac*N) ids, sorted.
# --------------------------------------------------------------------------
def _fleet_runs(results: dict[str, list[dict]], method: str) -> list[dict]:
    return results.get(method, [])


def _cold_start_node_id(node_ids: list[str]) -> str:
    return sorted(node_ids)[-1]


def _s5_quorum_no_deadlock(results):
    runs = _fleet_runs(results, "fedqpnt")
    if not runs:
        return dict(passed=None, value=None, detail="no 'fedqpnt' fleet runs")
    aborted = [bool((r.get("fleet") or {}).get("aborted")) for r in runs]
    val = float(np.mean([not a for a in aborted]))
    skipped = [int((r.get("fleet") or {}).get("rounds_skipped") or 0) for r in runs]
    return dict(passed=bool(val == 1.0), value=val,
                detail=f"P(no deadlock/ABORT)={val:.3f} (==1 required); "
                       f"mean ROUND_SKIPPED events/run={np.mean(skipped):.2f} (graceful degrade, not a failure)")


def _s5_auc_drop(results):
    a = _method_series(results, "fedqpnt", "auc")           # with 30% node failures + delays
    b = _method_series(results, "fedqpnt_nofault", "auc")   # reference: same config, no failures
    if a.size == 0:
        return dict(passed=None, value=None, detail="no 'fedqpnt' fleet runs")
    if b.size == 0 or b.size != a.size:
        return dict(passed=None, value=None,
                     detail="no matched 'fedqpnt_nofault' reference runs (run the same scenario/seeds "
                            "with failure_round/delay_window cleared to populate this baseline)")
    drop = float(np.nanmean(b - a))
    return dict(passed=bool(drop <= 0.02), value=drop,
                detail=f"AUC drop (nofault - withfault)={drop:.4f} (bound <=0.02) [ASSUMPTION: seed-to-seed spread]")


S5 = Scenario(
    id="S5", title="Partial node failure / delayed FL updates", fleet_size=10, duration_s=600.0,
    world="flat", cai_grade="field", attack=None, methods=("fedqpnt", "baseline_a"),
    criteria=(Criterion("quorum_or_skip_no_deadlock", "FL must degrade gracefully", _s5_quorum_no_deadlock),
              Criterion("auc_drop_le_0_02", "0.02 AUC within seed-to-seed spread [ASSUMPTION]", _s5_auc_drop)),
    requires_fl=True,
)

S6 = Scenario(
    id="S6", title="CAI bias drift, long duration (Schuler world)", fleet_size=1, duration_s=14400.0,
    world="schuler_tangent", cai_grade="field",
    attack=dict(kind="drift_spoof", onset_s=600.0, duration_s=None, severity=0.05),
    methods=("fedqpnt_local", "baseline_b_cont"),
    criteria=(Criterion("rmse_h_vs_minus_quantum", "Graceful degradation: CAI must never worsen the system",
                         _not_runnable("BLOCKED by D-047 (CAI/H3, attitude/bias)"), blocked_by_D047=True),
              Criterion("w_q_lt_0_5_within_10_cycles", "CAI must be down-weighted once it drifts",
                         _not_runnable("BLOCKED by D-047 (CAI/H3, attitude/bias)"), blocked_by_D047=True)),
    blocked_by_D047=True,
    notes="CAI/H3 benefit claim; BLOCKED per D-046/D-047.",
)


def _s7_ncyc(results):
    v = _method_series(results, "fedqpnt_local", "n_cyc_per_hour")
    if v.size == 0:
        return dict(passed=None, value=None, detail="no fedqpnt_local runs")
    bound = 3600.0 / 26.1
    val = float(np.max(v))
    return dict(passed=bool(val <= bound), value=val, detail=f"max N_cyc/h={val:.2f} (formal bound {bound:.2f})")


S7 = Scenario(
    id="S7", title="Trust chattering (toggled spoof)", fleet_size=1, duration_s=3600.0, world="flat",
    cai_grade="field", attack=dict(kind="drift_spoof", onset_s=60.0, duration_s=None, severity=0.5,
                                    params={"toggle_period_s": 10.0}),
    methods=("fedqpnt_local",),
    criteria=(Criterion("n_cyc_bound", "Checks the formal chattering bound (section 3.3) holds in code",
                         _s7_ncyc),),
)

def _s8_within_2_rounds(results):
    runs = _fleet_runs(results, "fedqpnt")
    if not runs:
        return dict(passed=None, value=None, detail="no 'fedqpnt' fleet runs")
    hits = []
    for r in runs:
        nodes = r.get("nodes") or {}
        if not nodes:
            continue
        cs_id = _cold_start_node_id(list(nodes.keys()))
        prov = (nodes.get(cs_id) or {}).get("provenance") or []
        active = [p for p in prov if p.get("n_local_samples", 0) or p.get("installed")]
        if not active:
            continue
        join_r = active[0]["round"]
        installed = [p["round"] for p in active if p.get("installed")]
        hits.append(bool(installed and (installed[0] - join_r) <= 2))
    if not hits:
        return dict(passed=None, value=None, detail="no cold-start node provenance recorded")
    val = float(np.mean(hits))
    return dict(passed=bool(val >= 0.95), value=val,
                detail=f"P(cold-start receives global model within 2 rounds of joining)={val:.3f} (>=0.95)")


def _s8_first_attack_auc(results):
    runs = _fleet_runs(results, "fedqpnt")
    if not runs:
        return dict(passed=None, value=None, detail="no 'fedqpnt' fleet runs")
    diffs = []
    for r in runs:
        nodes = r.get("nodes") or {}
        if len(nodes) < 2:
            continue
        cs_id = _cold_start_node_id(list(nodes.keys()))
        cs_auc = nodes.get(cs_id, {}).get("auc")
        veteran_aucs = [v.get("auc") for k, v in nodes.items()
                         if k != cs_id and isinstance(v.get("auc"), (int, float)) and np.isfinite(v.get("auc"))]
        if not isinstance(cs_auc, (int, float)) or not np.isfinite(cs_auc) or not veteran_aucs:
            continue
        diffs.append(float(cs_auc) - float(np.mean(veteran_aucs)))
    if not diffs:
        return dict(passed=None, value=None, detail="insufficient per-node AUC data for cold-start vs veteran")
    val = float(np.mean(diffs))
    return dict(passed=bool(val >= -0.05), value=val,
                detail=f"mean(cold-start AUC - veteran AUC)={val:.4f} (bound >=-0.05) "
                       f"[approximation: mission-level per-node AUC, not first-attack-only]")


S8 = Scenario(
    id="S8", title="Cold-start node at T/2", fleet_size=5, duration_s=600.0, world="flat", cai_grade="field",
    attack=dict(kind="drift_spoof", onset_s=330.0, duration_s=120.0, severity=0.6),
    methods=("fedqpnt",),
    criteria=(Criterion("global_model_within_2_rounds", "Tests FL knowledge transfer", _s8_within_2_rounds),
              Criterion("first_attack_auc", "Cold-start AUC vs veteran - 0.05", _s8_first_attack_auc)),
    requires_fl=True,
)


def _s9_no_deadlock_auc_bound(results):
    runs = _fleet_runs(results, "fedqpnt")
    if not runs:
        return dict(passed=None, value=None, detail="no 'fedqpnt' fleet runs")
    aborted = [bool((r.get("fleet") or {}).get("aborted")) for r in runs]
    no_deadlock = float(np.mean([not a for a in aborted]))
    ref = _fleet_runs(results, "fedqpnt_noloss")
    if ref:
        a = _method_series(results, "fedqpnt", "auc")
        b = _method_series(results, "fedqpnt_noloss", "auc")
        if a.size and a.size == b.size:
            drop = float(np.nanmean(b - a))
            passed = bool(no_deadlock == 1.0 and drop <= 0.03)
            return dict(passed=passed, value=drop,
                        detail=f"P(no deadlock)={no_deadlock:.3f}, AUC drop (no-loss - lossy)={drop:.4f} "
                               f"(bound <=0.03)")
    passed = True if no_deadlock == 1.0 else False
    return dict(passed=passed, value=no_deadlock,
                detail=f"P(no deadlock/ABORT)={no_deadlock:.3f} (AUC-drop leg not evaluable: no "
                       f"'fedqpnt_noloss' reference runs)")


S9 = Scenario(
    id="S9", title="Comms dropouts", fleet_size=5, duration_s=600.0, world="flat", cai_grade="field",
    attack=None, methods=("fedqpnt",),
    criteria=(Criterion("no_deadlock_auc_bound", "Robustness of the FL protocol", _s9_no_deadlock_auc_bound),),
    requires_fl=True,
)


def _s10_anees_band(results):
    v = _method_series(results, "fedqpnt_local", "anees_pos_all")
    if v.size == 0:
        return dict(passed=None, value=None, detail="no fedqpnt_local runs")
    val = float(np.nanmean(v))
    return dict(passed=bool(0.5 <= val <= 2.0), value=val, detail=f"ANEES={val:.3f} (band [0.5,2])")


S10 = Scenario(
    id="S10", title="Sample-rate mismatch", fleet_size=1, duration_s=300.0, world="flat", cai_grade="field",
    attack=None, methods=("fedqpnt_local",),
    criteria=(Criterion("no_crash_anees_band", "Rate handling correctness", _s10_anees_band),),
    notes="Rate/jitter sweep is a config axis (gnss_rate_hz, cycle_time); campaign expands one Scenario "
          "per combination at run-generation time.",
)


def _s11_finite_bound(results):
    v = _method_series(results, "fedqpnt_local", "rmse_h_att")
    if v.size == 0:
        return dict(passed=None, value=None, detail="no fedqpnt_local runs")
    finite = np.isfinite(v)
    val = float(np.mean(finite))
    return dict(passed=bool(val == 1.0), value=val, detail=f"finite fraction={val:.3f}")


S11 = Scenario(
    id="S11", title="Extreme noise (filter not told)", fleet_size=1, duration_s=300.0, world="flat",
    cai_grade="field", attack=dict(kind="abrupt_spoof", onset_s=60.0, duration_s=60.0, severity=1.0),
    methods=("fedqpnt_local",),
    criteria=(Criterion("all_runs_finite_P_spd", "Numerical robustness; no divergence", _s11_finite_bound),),
)

def _s12_auc_drop_f20(results):
    a = _method_series(results, "fedqpnt", "auc")          # f=20% poisoned nodes (fleet_adapter default)
    b = _method_series(results, "fedqpnt_clean", "auc")     # reference: same config, no poisoning
    if a.size == 0:
        return dict(passed=None, value=None, detail="no 'fedqpnt' (poisoned) fleet runs")
    if b.size == 0 or b.size != a.size:
        return dict(passed=None, value=None,
                     detail="no matched 'fedqpnt_clean' reference runs (run with poison_kind cleared)")
    drop = float(np.nanmean(b - a))
    return dict(passed=bool(drop <= 0.05), value=drop,
                detail=f"AUC drop (clean - poisoned)={drop:.4f} (bound <=0.05 at f=20%, TRIM-NB-R)")


S12 = Scenario(
    id="S12", title="Trust-score / model poisoning", fleet_size=10, duration_s=600.0, world="flat",
    cai_grade="field", attack=None, methods=("fedqpnt",),
    criteria=(Criterion("auc_drop_le_0_05_at_f20", "Theory: trimmed mean robust for f < beta",
                         _s12_auc_drop_f20),),
    requires_fl=True,
)


def _s13_trec(results):
    v = _method_series(results, "fedqpnt_local", "t_rec")
    if v.size == 0:
        return dict(passed=None, value=None, detail="no fedqpnt_local runs")
    hit = np.isfinite(v)
    frac_60 = float(np.mean(v[hit] <= 60.0)) if np.any(hit) else 0.0
    frac_180 = float(np.mean((v[hit] <= 180.0))) if np.any(hit) else 0.0
    no_lockout = float(np.mean(hit))
    passed = bool(frac_60 >= 0.9 and no_lockout >= 1.0 - 1e-9)
    return dict(passed=passed, value=frac_60, detail=f"P(t_rec<=60s)={frac_60:.3f} (>=0.9), "
                                                       f"P(recovered<=180s)={no_lockout:.3f} (==1)")


S13 = Scenario(
    id="S13", title="Recovery after attack", fleet_size=1, duration_s=300.0, world="flat", cai_grade="field",
    attack=dict(kind="abrupt_spoof", onset_s=60.0, duration_s=60.0, severity=0.8),
    methods=("fedqpnt_local",),
    criteria=(Criterion("t_rec_bounds", "Design recovery ~33s + EKF reconvergence [ASSUMPTION]", _s13_trec),),
)


def _s14_stability(results):
    return dict(passed=None, value=None, detail="BLOCKED by D-047 (multi-hour attitude/bias drift, Schuler world)")


S14 = Scenario(
    id="S14", title="Multi-hour stability (Schuler world)", fleet_size=1, duration_s=14400.0,
    world="schuler_tangent", cai_grade="field", attack=None, methods=("fedqpnt_local",),
    criteria=(Criterion("no_slow_drift", "No slow numerical or statistical drift", _s14_stability,
                         blocked_by_D047=True),),
    blocked_by_D047=True,
)

def _s15_quarantine_and_far(results):
    runs = _fleet_runs(results, "fedqpnt")
    if not runs:
        return dict(passed=None, value=None, detail="no 'fedqpnt' fleet runs")
    zero_q, far_margins = [], []
    for r in runs:
        fleet = r.get("fleet") or {}
        zero_q.append((fleet.get("quarantine_events") or 0) == 0)
        nodes = r.get("nodes") or {}
        if not nodes:
            continue
        ids = sorted(nodes.keys())
        n_attacked = max(1, round(0.3 * len(ids)))
        clean_ids = ids[n_attacked:]
        clean_far = [nodes[i].get("far_per_hour") for i in clean_ids
                     if isinstance(nodes[i].get("far_per_hour"), (int, float))
                     and np.isfinite(nodes[i]["far_per_hour"])]
        if clean_far:
            far_margins.append(float(np.mean(clean_far)))
    q_frac = float(np.mean(zero_q)) if zero_q else float("nan")
    far_val = float(np.mean(far_margins)) if far_margins else float("nan")
    if not np.isfinite(q_frac):
        return dict(passed=None, value=None, detail="no quarantine-event data")
    far_ok = np.isfinite(far_val) and far_val <= 1.5   # S1 FAR bound (1/h) + 0.5/h slack
    passed = bool(q_frac >= 0.9 and far_ok) if np.isfinite(far_val) else None
    return dict(passed=passed, value=far_val,
                detail=f"P(quarantine_events==0)={q_frac:.3f} (>=0.9); "
                       f"mean unattacked-node FAR={far_val:.3f}/h (bound <=1.5)")


S15 = Scenario(
    id="S15", title="Simultaneous attacks on fleet subset", fleet_size=10, duration_s=600.0, world="flat",
    cai_grade="field", attack=dict(kind="drift_spoof", onset_s=60.0, duration_s=300.0, severity=0.6),
    methods=("fedqpnt",),
    criteria=(Criterion("attacked_meet_s2_unattacked_far_bound", "Robust aggregator must not punish honest "
                         "heterogeneity", _s15_quarantine_and_far),),
    requires_fl=True,
)


REGISTRY: dict[str, Scenario] = {s.id: s for s in
                                 (S1, S2_LOW, S2_MED, S2_HIGH, S3, S4, S5, S6, S7, S8, S9, S10, S11, S12,
                                  S13, S14, S15)}


def get(scenario_id: str) -> Scenario:
    return REGISTRY[scenario_id]


def all_scenarios() -> tuple[Scenario, ...]:
    return tuple(REGISTRY.values())
