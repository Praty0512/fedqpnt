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
FLEET_METHOD_ALL = ("fedqpnt", "fedavg_ablation", "baseline_a", "baseline_b_cont", "baseline_b_bin",
                    "fedqpnt_clean", "fedqpnt_nofault", "fedqpnt_noloss")


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
    # --- D-068 registry-vs-intent fields (all optional; defaults keep legacy behaviour) ---
    base_id: str = ""                # family id for variants (e.g. "S10-r5" -> "S10"); "" = same as id
    gnss_rate_hz: float = 1.0        # S10 rate grid
    quantum_cycle_time_s: float | None = None   # S10: the AGENT's assumed CAI cycle time (mismatch axis); None = default
    attacks: tuple = ()              # multi-attack schedule (S4 jam->spoof, S7 toggling); needs RunSpec.attacks
    noise_scale: dict | None = None  # S11: {"imu": 10, "gnss": 5, "cai_contrast_div": 3}; needs RunSpec.noise_scale
    poison_frac: float | None = None # S12 fleet variants (f in {0.2, 0.4}, sign_flip)
    group: str = ""                  # variants of one ARCH row share a group (e.g. "S7", "S10")

    @property
    def family(self) -> str:
        return self.base_id or self.id


# D-068: method aliases resolved when a RunSpec is built (eval side only).
# abl_minus_quantum = the full FedQPNT node with the CAI switched off (H3 reference arm).
METHOD_ALIASES: dict[str, dict] = {"abl_minus_quantum": dict(method="fedqpnt_local", quantum_grade=None)}
SIGMA_NOM_PATH = "results/sigma_nom.json"    # D-068: frozen file, never computed on the fly


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



def _grade_of(results: dict[str, list[dict]]) -> str:
    for recs in results.values():
        for r in recs:
            if r.get("_imu_grade"):
                return r["_imu_grade"]
    return "industrial_mems"


def _sigma_nom(results: dict[str, list[dict]]) -> tuple[float | None, str]:
    """Frozen sigma_nom (D-068) for the results' IMU grade, or (None, reason)."""
    try:
        d = _M.load_sigma_nom(SIGMA_NOM_PATH)
    except (FileNotFoundError, ValueError) as exc:
        return None, f"sigma_nom not frozen: {exc}"
    g = _grade_of(results)
    if g not in d:
        return None, f"sigma_nom.json has no entry for grade '{g}'"
    return d[g], ""


def _leg(name: str, passed, value, detail: str) -> dict[str, Any]:
    return dict(name=name, passed=passed, value=value, detail=detail)


def _combine(legs: list[dict[str, Any]]) -> dict[str, Any]:
    """AND of legs; any FAILED leg -> False, else any unevaluable -> None, else True."""
    if any(l["passed"] is False for l in legs):
        passed = False
    elif any(l["passed"] is None for l in legs):
        passed = None
    else:
        passed = True
    val = next((l["value"] for l in legs if l["value"] is not None), None)
    return dict(passed=passed, value=val,
                detail=" | ".join(f"{l['name']}: {l['detail']}" for l in legs))


def _runs(results, method):
    return results.get(method, [])


def _all_runs_field(results, method, field_name):
    """Per-run values of ``field_name`` or None if any run lacks it (runner does not emit it yet)."""
    runs = _runs(results, method)
    if not runs:
        return None
    vals = [r.get(field_name) for r in runs]
    if any(v is None for v in vals):
        return None
    return np.array(vals, dtype=float)


def _never_worse_leg(results, method="fedqpnt_local", ref="undefended", field_name="max_h_att") -> dict[str, Any]:
    """D-068 primary safety criterion: mean_defended <= mean_undefended + 3 sigma_nom (sigma_nom frozen,
    per grade). Unevaluable (passed=None) until sigma_nom.json exists."""
    a = _method_series(results, method, field_name)
    u = _method_series(results, ref, field_name)
    if a.size == 0 or u.size == 0 or a.size != u.size:
        return _leg("never_worse", None, None, f"missing/mismatched {method}/{ref}")
    sig, why = _sigma_nom(results)
    if sig is None:
        return _leg("never_worse", None, None, why)
    margin = float(np.nanmean(a) - np.nanmean(u))
    return _leg("never_worse", bool(margin <= 3 * sig), margin,
                f"mean({field_name}) defended-undefended={margin:.3f} (bound 3*sigma_nom={3*sig:.3f}, "
                f"grade={_grade_of(results)})")


# --------------------------------------------------------------------------
# S1: Nominal
# --------------------------------------------------------------------------
def _s1_far(results):
    v = _method_series(results, "fedqpnt_local", "far_per_hour")
    if v.size == 0:
        return dict(passed=None, value=None, detail="no fedqpnt_local runs")
    val = float(np.mean(v))
    return dict(passed=bool(val <= 1.0), value=val, detail=f"FAR={val:.3f}/h/node (bound 1.0)")


def _anees_series(results, method, base):
    """D-068: prefer the full-3x3-block ANEES ('<base>_full') when every run has it, else the legacy diagonal key."""
    full = _method_series(results, method, base + "_full")
    if full.size and np.all(np.isfinite(full)):
        return full
    return _method_series(results, method, base)


def _s1_anees(results):
    v = _anees_series(results, "fedqpnt_local", "anees_pos_pre")
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


def _s1_tv(results):
    v = _method_series(results, "fedqpnt_local", "tv_w_per_hour")
    if v.size == 0:
        return dict(passed=None, value=None, detail="no fedqpnt_local runs")
    val = float(np.nanmean(v))
    return dict(passed=bool(val <= 1.0), value=val, detail=f"TV_w={val:.3f}/h (bound 1.0; ARCH S7 row 'in S1')")


S1 = Scenario(
    id="S1", title="Nominal", fleet_size=1, duration_s=600.0, world="flat", cai_grade="field",
    attack=None, methods=METHOD_ALL,
    criteria=(
        _paired_ratio_check("rmse_h_vs_fixed_trust", "Trust must cost <=5% when nothing is wrong",
                             "rmse_h_pre", "fedqpnt_local", "fixed_trust", 1.05),
        Criterion("far_le_1_per_hour", "Lenient nuisance-rate bound (RAIM-FDE Pfa with 25x slack)", _s1_far),
        Criterion("anees_in_band", "Factor-2 ANEES band tolerates correlated GNSS errors [ASSUMPTION]", _s1_anees),
        Criterion("mean_w_gnss_ge_0_95", "Trust must not distrust clean GNSS", _s1_mean_w),
        Criterion("tv_w_le_1_per_hour", "Trust must not chatter on clean data (ARCH S7 row)", _s1_tv),
    ),
)


# --------------------------------------------------------------------------
# S2: Gradual spoof, severities {low, med, high}
# --------------------------------------------------------------------------
def _pd_value(results, method, window):
    runs = _runs(results, method)
    hit = np.array([_M.detected_from_record(r, window) for r in runs], dtype=bool)
    return float(np.mean(hit)), len(runs)


def _make_s2(severity_name: str, severity: float, final_offset_ge_50m: bool) -> Scenario:
    attack = dict(kind="drift_spoof", onset_s=60.0, duration_s=300.0, severity=severity)
    return _make_spoof_scenario(f"S2-{severity_name}", f"Gradual spoof ({severity_name})", attack,
                                 final_offset_ge_50m)


def _make_spoof_scenario(sid: str, title: str, attack: dict, final_offset_ge_50m: bool, *,
                          duration_s: float = 600.0, base_id: str = "", notes: str = "") -> Scenario:
    """ARCH S2 row: for final offset >= 50 m: P_D >= 0.9 and MAX_h <= 0.5 x MAX_h(undefended);
    for ALL severities: MAX_h(defended) <= MAX_h(undefended) + 3 sigma_nom (D-068: sigma_nom is the
    frozen per-grade value, never an assumed constant)."""
    window = attack.get("duration_s")

    def _pd(results):
        # D-068: latency_on is CENSORED (finite) on a miss, so isfinite() was always True (P_D == 1.0).
        if not _runs(results, "fedqpnt_local"):
            return dict(passed=None, value=None, detail="no fedqpnt_local runs")
        p_d, n = _pd_value(results, "fedqpnt_local", window)
        crit = bool(p_d >= 0.9) if final_offset_ge_50m else None
        return dict(passed=crit, value=p_d, detail=f"P_D={p_d:.3f} (n={n})")

    def _halve(results):
        a = _method_series(results, "fedqpnt_local", "max_h_att")
        u = _method_series(results, "undefended", "max_h_att")
        if a.size == 0 or u.size == 0 or a.size != u.size:
            return dict(passed=None, value=None, detail="missing fedqpnt_local/undefended")
        if not final_offset_ge_50m:
            return dict(passed=None, value=None, detail="n/a (final offset < 50 m: halving not required)")
        ratio = float(np.median(a / np.where(u == 0, np.nan, u)))
        return dict(passed=bool(np.isfinite(ratio) and ratio <= 0.5), value=ratio,
                    detail=f"median MAX_h ratio={ratio:.4f} (bound 0.5)")

    def _never_worse(results):
        leg = _never_worse_leg(results)
        return dict(passed=leg["passed"], value=leg["value"], detail=leg["detail"])

    crits = [Criterion("detection_prob", "Halving the damage requires detecting it first", _pd)]
    if final_offset_ge_50m:
        crits.append(Criterion("damage_halved", "Halve the damage", _halve))
    crits.append(Criterion("damage_never_worse", "Defence never makes it worse (undefended + 3 sigma_nom)",
                            _never_worse))
    return Scenario(id=sid, title=title, fleet_size=1, duration_s=duration_s, world="flat", cai_grade="field",
                    attack=attack, methods=METHOD_ALL, criteria=tuple(crits), base_id=base_id, notes=notes)


S2_LOW = _make_s2("low", 0.3, final_offset_ge_50m=False)
S2_MED = _make_s2("med", 0.6, final_offset_ge_50m=True)
S2_HIGH = _make_s2("high", 0.9, final_offset_ge_50m=True)


# --------------------------------------------------------------------------
# S3: Sudden jamming (outage) -- BLOCKED (D-047: outage/attitude claims)
# --------------------------------------------------------------------------
T_DIST_BOUND_S = 2 * 1.0 + 1.0    # ARCH S3: 2 GNSS epochs (1 Hz) + 1 s
W_REACQ = 0.5                      # trust cfg w_reacq (fedqpnt.trust.trust_law.TrustEngineConfig)


def _leg_t_dist(results, method="fedqpnt_local") -> dict[str, Any]:
    v = _method_series(results, method, "t_dist")
    if v.size == 0:
        return _leg("t_dist", None, None, f"no {method} runs")
    ok = np.isfinite(v) & (v <= T_DIST_BOUND_S)
    frac = float(np.mean(ok))
    return _leg("t_dist", bool(frac == 1.0), float(np.nanmax(v)) if np.any(np.isfinite(v)) else float("nan"),
                f"runs with t_dist<={T_DIST_BOUND_S:g}s: {frac:.3f} (==1 required; NaN counts as failure)")


def _leg_consistency(results, method="fedqpnt_local") -> dict[str, Any]:
    v = _all_runs_field(results, method, "frac_e_le_3sigma_att")
    if v is None:
        return _leg("consistency", None, None, "runner does not emit frac_e_le_3sigma_att yet "
                                                "(SCENARIO-FIX proposal P3); not evaluable")
    return _leg("consistency", bool(np.all(v >= 0.95)), float(np.min(v)),
                f"min over runs of frac(e_h<=3 sigma_h(P_pos)) in P_att={np.min(v):.3f} (>=0.95 each run)")


def _leg_no_update_while_jammed(results, method="fedqpnt_local") -> dict[str, Any]:
    v = _all_runs_field(results, method, "n_gnss_accepted_jammed")
    if v is None:
        return _leg("no_update_while_jammed", None, None,
                    "runner does not emit n_gnss_accepted_jammed yet (P3); not evaluable")
    return _leg("no_update_while_jammed", bool(np.all(v == 0)), float(np.max(v)),
                f"max GNSS updates accepted while fix.valid false={np.max(v):.0f} (==0)")


def _s3_check(results):
    return _combine([_leg_t_dist(results), _leg_consistency(results), _leg_no_update_while_jammed(results)])


S3 = Scenario(
    id="S3", title="Sudden jamming", fleet_size=1, duration_s=300.0, world="flat", cai_grade="field",
    attack=dict(kind="jam_wideband", onset_s=60.0, duration_s=60.0, severity=1.0),
    methods=METHOD_ALL,
    criteria=(Criterion("tdist_consistency_no_update",
                         "Design latency bound; coast error must be honestly predicted; no update while jammed",
                         _s3_check, blocked_by_D047=True),),
    blocked_by_D047=True,
    notes="GNSS-outage drift claim; BLOCKED per D-046/D-047 until psi/b consistency is fixed. Criteria "
          "implemented per ARCH 6.1 (D-068) and computed, but reported BLOCKED.",
)


# --------------------------------------------------------------------------
# S4: Combined (jam -> spoof capture at reacquisition) -- BLOCKED
# D-068: the spoof leg was missing (registry was jam only). Intent: jam, then a drift spoof that starts
# when the jam ends and tries to capture the reacquiring receiver.
# --------------------------------------------------------------------------
S4_JAM = dict(kind="jam_wideband", onset_s=60.0, duration_s=40.0, severity=1.0)
S4_SPOOF = dict(kind="drift_spoof", onset_s=100.0, duration_s=200.0, severity=0.6)


def _leg_reacq_cap(results, method="fedqpnt_local") -> dict[str, Any]:
    v = _all_runs_field(results, method, "w_gnss_reacq_max")
    if v is None:
        return _leg("reacq_cap", None, None, "runner does not emit w_gnss_reacq_max yet (P3); not evaluable")
    return _leg("reacq_cap", bool(np.all(v <= W_REACQ + 1e-9)), float(np.max(v)),
                f"max w_gnss at reacquisition={np.max(v):.3f} (<= w_reacq={W_REACQ} in 100% of runs)")


def _s4_check(results):
    # S3 legs (t_dist from the union onset = jam onset) + S2 legs on the union attack window
    # [documented approximation: phases merge jam and spoof labels] + reacquisition cap.
    a = _method_series(results, "fedqpnt_local", "max_h_att")
    u = _method_series(results, "undefended", "max_h_att")
    if a.size and a.size == u.size:
        ratio = float(np.median(a / np.where(u == 0, np.nan, u)))
        halve = _leg("s2_damage_halved", bool(np.isfinite(ratio) and ratio <= 0.5), ratio,
                     f"median MAX_h ratio={ratio:.3f} (<=0.5)")
    else:
        halve = _leg("s2_damage_halved", None, None, "missing fedqpnt_local/undefended")
    return _combine([_leg_t_dist(results), _leg_consistency(results), halve,
                     _never_worse_leg(results), _leg_reacq_cap(results)])


S4 = Scenario(
    id="S4", title="Combined jam-then-spoof capture", fleet_size=1, duration_s=400.0, world="flat",
    cai_grade="field", attack=S4_JAM, attacks=(S4_JAM, S4_SPOOF),
    methods=METHOD_ALL,
    criteria=(Criterion("s2_s3_joint_plus_reacq_cap", "Tests the reacquisition cap", _s4_check,
                         blocked_by_D047=True),),
    blocked_by_D047=True,
    notes="Jam leg + drift-spoof capture leg (D-068). Needs RunSpec.attacks (P3). BLOCKED per D-046/D-047.",
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
    world="flat", cai_grade="field", attack=None, methods=("fedqpnt", "baseline_a", "fedqpnt_nofault"),
    criteria=(Criterion("quorum_or_skip_no_deadlock", "FL must degrade gracefully", _s5_quorum_no_deadlock),
              Criterion("auc_drop_le_0_02", "0.02 AUC within seed-to-seed spread [ASSUMPTION]", _s5_auc_drop)),
    requires_fl=True,
)

def _s6_never_worse(results):
    leg = _never_worse_leg(results)
    return dict(passed=leg["passed"], value=leg["value"], detail=leg["detail"])


def _s6_latency_eff_descriptive(results):
    """H3 is tested in report.confirmatory_tests (paired latency_eff per grade, Holm family). Here: descriptive only."""
    return dict(passed=None, value=None,
                detail="H3 primary (paired latency_eff vs abl_minus_quantum, per grade) is evaluated in the "
                       "confirmatory family; no pass/fail here")


S6 = Scenario(
    id="S6", title="CAI benefit under gradual spoofing (Schuler world) -- the H3 scenario", fleet_size=1,
    duration_s=1500.0, world="schuler_tangent", cai_grade="field",
    attack=dict(kind="drift_spoof", onset_s=300.0, duration_s=900.0, severity=0.3),
    methods=("fedqpnt_local", "abl_minus_quantum", "undefended"),
    criteria=(Criterion("h3_latency_eff", "H3: CAI shortens latency_eff (confirmatory, see report)",
                         _s6_latency_eff_descriptive),
              Criterion("never_worse", "Defence never worse than undefended + 3 sigma_nom (per grade)",
                         _s6_never_worse)),
    blocked_by_D047=True,
    notes="""D-070 registration. Replaces the earlier S6 (a GNSS drift with no -quantum arm, which could not answer
    H3 or the ARCH S6 row). RATIONALE: H3 (ARCH 6.2) is FedQPNT(CAI) < -quantum on latency_eff for GRADUAL
    spoofing. Severity 0.3 is a slow carry-off: the offset stays small relative to the inertial coast error for a
    long time, so how early the GNSS/INS innovation becomes inconsistent depends on the quality of the inertial
    (+CAI) prediction -- the D-063 diagnosis (on MEMS, 180 s of inertial coasting is as bad as following the spoof)
    and the D-065 coasting envelope (CAI cuts max coasting error 2.1-3.4x). Run at grades industrial_mems and
    tactical (result ids S6@<grade>); primary = paired latency_eff per grade (2 of the 8 confirmatory tests);
    safety = never-worse leg. PARAMETERS (Schuler world, 1500 s, onset 300 s, duration 900 s, severity 0.3) WERE
    FIXED BEFORE ANY TEST-SEED DATA (D-070), after the tuning data existed. The ARCH-literal 'CAI bias drift,
    w_q < 0.5 within 10 cycles' leg is NOT tested: no CAI fault injector exists and none was approved (D-070);
    narrowed in the paper. Still BLOCKED by D-047 (CAI/H3 claim) until the gate clears.""",
)

# S6-coast: EXPLORATORY (D-070), NOT in the Holm family. 180 s forced outage; max coasting error with/without CAI.
S6_COAST_ARMS = ("fedqpnt_local", "abl_minus_quantum")


def _s6c_coast_ratio(results):
    a = _method_series(results, "fedqpnt_local", "max_h_att")
    b = _method_series(results, "abl_minus_quantum", "max_h_att")
    if a.size == 0 or b.size == 0 or a.size != b.size:
        return dict(passed=None, value=None, detail="missing fedqpnt_local/abl_minus_quantum")
    ratio = float(np.median(b / np.where(a == 0, np.nan, a)))
    return dict(passed=None, value=ratio,
                detail=f"EXPLORATORY: median max coasting error ratio (-quantum / CAI)={ratio:.3f} "
                       f"(D-065 tuning envelope 2.1-3.4x); no pass/fail")


S6_COAST = Scenario(
    id="S6-coast", title="CAI coasting envelope, 180 s forced outage (EXPLORATORY)", fleet_size=1,
    duration_s=1200.0, world="schuler_tangent", cai_grade="field",
    attack=dict(kind="jam_wideband", onset_s=600.0, duration_s=180.0, severity=1.0),
    methods=S6_COAST_ARMS, base_id="S6", group="S6",
    criteria=(Criterion("coast_ratio_exploratory", "D-065 coasting envelope with/without CAI (exploratory)",
                         _s6c_coast_ratio, blocked_by_D047=True),),
    blocked_by_D047=True,
    notes="EXPLORATORY (D-070): not part of the 8-test Holm family. Parameters fixed before test data.",
)


S7_PERIODS_S = (2.0, 5.0, 10.0, 20.0, 60.0)      # ARCH S7 row
S7_DURATION_S = 3600.0
S7_T0_S = 60.0


def toggle_attacks(period_s: float, t0_s: float, t_end_s: float, severity: float = 0.5) -> tuple[dict, ...]:
    """Spoof toggled with the given period (50% duty): abrupt-offset segments [t0+k*P, t0+k*P+P/2).
    (attacks/ has no native toggle parameter; the previous registration's ``params.toggle_period_s`` was
    silently not a constructor argument, so S7 could not have run as registered -- D-068.)"""
    n = int((t_end_s - t0_s) // period_s)
    return tuple(dict(kind="abrupt_spoof", onset_s=t0_s + k * period_s, duration_s=period_s / 2.0,
                      severity=severity) for k in range(n))


def _s7_ncyc(results):
    v = _method_series(results, "fedqpnt_local", "n_cyc_per_hour")
    if v.size == 0:
        return dict(passed=None, value=None, detail="no fedqpnt_local runs")
    bound = _M.N_CYC_BOUND_PER_HOUR   # D-068: to be re-derived at the freeze; integer pre-registered then
    val = float(np.max(v))
    return dict(passed=bool(val <= bound), value=val, detail=f"max N_cyc/h={val:.2f} (formal bound {bound:.2f})")


def _s7_maxh(results):
    leg = _never_worse_leg(results)     # "MAX_h <= S2 bound" = undefended + 3 sigma_nom
    return dict(passed=leg["passed"], value=leg["value"], detail=leg["detail"])


def _make_s7(period_s: float) -> Scenario:
    atk = toggle_attacks(period_s, S7_T0_S, S7_DURATION_S - S7_T0_S)
    return Scenario(
        id=f"S7-p{period_s:g}", title=f"Trust chattering (toggled spoof, period {period_s:g} s)", fleet_size=1,
        duration_s=S7_DURATION_S, world="flat", cai_grade="field", attack=atk[0], attacks=atk,
        methods=("fedqpnt_local", "undefended"), base_id="S7", group="S7",
        criteria=(Criterion("n_cyc_bound", "Checks the formal chattering bound (section 3.3) holds in code",
                             _s7_ncyc),
                  Criterion("max_h_never_worse", "MAX_h <= S2 bound", _s7_maxh)),
        notes="'detector noise near threshold' variation of the ARCH row is NOT registered (narrow in paper). "
              "Needs RunSpec.attacks (P3).")


S7_VARIANTS = tuple(_make_s7(p) for p in S7_PERIODS_S)

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
    methods=("fedqpnt", "baseline_b_cont"),     # D-068: H4 compares fedqpnt vs B-cont on the cold-start node
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
    attack=None, methods=("fedqpnt", "fedqpnt_noloss"),
    criteria=(Criterion("no_deadlock_auc_bound", "Robustness of the FL protocol", _s9_no_deadlock_auc_bound),),
    requires_fl=True,
)


def _s10_anees_band(results):
    v = _anees_series(results, "fedqpnt_local", "anees_pos_all")
    if v.size == 0:
        return dict(passed=None, value=None, detail="no fedqpnt_local runs")
    val = float(np.nanmean(v))
    return dict(passed=bool(0.5 <= val <= 2.0), value=val, detail=f"ANEES={val:.3f} (band [0.5,2])")


S10_RATES_HZ = (1.0, 2.0, 5.0, 10.0)
S10_TC_S = (0.5, 0.73, 1.0, 2.0)
S10_TC_DEFAULT = 1.0        # the agent's default assumed cycle time (make_agent_config); T_c=1.0 is the un-mismatched cell


def _make_s10(rate_hz: float, tc_s: float = S10_TC_DEFAULT) -> Scenario:
    default_tc = tc_s == S10_TC_DEFAULT
    sid = f"S10-r{rate_hz:g}" + ("" if default_tc else f"-c{tc_s:g}")
    return Scenario(
        id=sid, title=f"Sample-rate mismatch (GNSS {rate_hz:g} Hz, assumed T_c {tc_s:g} s)", fleet_size=1,
        duration_s=300.0, world="flat", cai_grade="field", attack=None, methods=("fedqpnt_local",),
        gnss_rate_hz=rate_hz, quantum_cycle_time_s=(None if default_tc else tc_s), base_id="S10", group="S10",
        criteria=(Criterion("no_crash_anees_band", "Rate handling correctness", _s10_anees_band),),
        notes="GNSS-rate x T_c grid of the ARCH row; T_c is the AGENT's assumed CAI cycle time (the sensor's true "
              "cycle is unchanged: that is the mismatch). The '+-1 tick jitter' axis is NOT implemented "
              "(narrow in paper).")


S10_VARIANTS = tuple(_make_s10(r, tc) for r in S10_RATES_HZ for tc in S10_TC_S)


def s10_rmse_monotone(results_by_rate: dict[float, dict[str, list[dict]]]) -> dict[str, Any]:
    """ARCH S10: RMSE_h(P_pre) non-increasing in GNSS rate 'within CI'. Cross-variant check, so it is not a
    per-scenario Criterion. Operationalisation (D-068, stated before test data): for each consecutive rate
    pair, mean RMSE_h(rate_hi) <= mean RMSE_h(rate_lo) + 1.96 * SE of the paired difference."""
    rates = sorted(results_by_rate)
    vals = {r: _method_series(results_by_rate[r], "fedqpnt_local", "rmse_h_pre") for r in rates}
    if len(rates) < 2 or any(v.size == 0 for v in vals.values()):
        return dict(passed=None, value=None, detail="need fedqpnt_local rmse_h_pre at >=2 rates")
    ok, worst = True, 0.0
    for lo, hi in zip(rates[:-1], rates[1:]):
        if vals[lo].size != vals[hi].size:
            return dict(passed=None, value=None, detail=f"unpaired runs at {lo} vs {hi} Hz")
        d = vals[hi] - vals[lo]
        se = float(np.std(d, ddof=1) / np.sqrt(d.size)) if d.size > 1 else 0.0
        excess = float(np.mean(d) - 1.96 * se)     # >0 => significantly worse at the higher rate
        worst = max(worst, excess)
        ok = ok and excess <= 0.0
    return dict(passed=bool(ok), value=worst, detail=f"max lower-CI excess of RMSE_h increase with rate={worst:.4g} (<=0)")


def _s11_check(results):
    """ARCH S11: 100% runs finite with P SPD; RMSE_h <= 1.5 x RMSE_h(GNSS-only fixes); FAR reported only."""
    v = _method_series(results, "fedqpnt_local", "rmse_h_pre")
    if v.size == 0:
        return dict(passed=None, value=None, detail="no fedqpnt_local runs")
    fin = float(np.mean(np.isfinite(v)))
    legs = [_leg("finite", bool(fin == 1.0), fin, f"finite fraction={fin:.3f} (==1)")]
    spd = _all_runs_field(results, "fedqpnt_local", "p_spd_finite")
    legs.append(_leg("P_SPD", None if spd is None else bool(np.all(spd >= 1.0)),
                     None if spd is None else float(np.mean(spd)),
                     "runner does not emit p_spd_finite yet (P3); not evaluable" if spd is None
                     else f"P finite+SPD in {np.mean(spd):.3f} of runs (==1)"))
    raw = _all_runs_field(results, "fedqpnt_local", "rmse_h_gnss_raw_pre")
    if raw is None:
        legs.append(_leg("vs_raw_gnss", None, None, "runner does not emit rmse_h_gnss_raw_pre yet (P3); not evaluable"))
    else:
        ratio = float(np.median(v / np.where(raw == 0, np.nan, raw)))
        legs.append(_leg("vs_raw_gnss", bool(np.isfinite(ratio) and ratio <= 1.5), ratio,
                         f"median RMSE_h/RMSE_h(raw GNSS)={ratio:.3f} (<=1.5)"))
    far = _method_series(results, "fedqpnt_local", "far_per_hour")
    if far.size:
        legs.append(_leg("far_reported", True, None, f"FAR={float(np.nanmean(far)):.3f}/h (reported, no threshold)"))
    return _combine(legs)


S11 = Scenario(
    id="S11", title="Extreme noise (filter not told)", fleet_size=1, duration_s=300.0, world="flat",
    cai_grade="field", attack=None,     # D-068: intent has no attack (registry had an abrupt spoof)
    noise_scale=dict(imu=10.0, gnss=5.0, cai_contrast_div=3.0),
    methods=("fedqpnt_local",),
    criteria=(Criterion("finite_spd_and_vs_raw_gnss", "Numerical robustness; no divergence below raw GNSS quality",
                         _s11_check),),
    notes="IMU noise x10, GNSS sigma x5, CAI contrast /3, filter NOT told. Needs RunSpec.noise_scale (P3).",
)

def _s12_auc_drop(f: float):
    def _check(results):
        a = _method_series(results, "fedqpnt", "auc")
        b = _method_series(results, "fedqpnt_clean", "auc")     # reference: same config, no poisoning
        if a.size == 0:
            return dict(passed=None, value=None, detail="no 'fedqpnt' (poisoned) fleet runs")
        if b.size == 0 or b.size != a.size:
            return dict(passed=None, value=None,
                         detail="no matched 'fedqpnt_clean' reference runs (run with poison_kind cleared)")
        drop = float(np.nanmean(b - a))
        if f <= 0.2 + 1e-9:
            return dict(passed=bool(drop <= 0.05), value=drop,
                        detail=f"AUC drop (clean - poisoned)={drop:.4f} (bound <=0.05 at f=20%, TRIM-NB-R)")
        return dict(passed=None, value=drop,
                    detail=f"AUC drop={drop:.4f} at f={f:.0%} REPORTED ONLY (beyond beta=20% breakdown)")
    return _check


def _make_s12(f: float) -> Scenario:
    return Scenario(
        id=f"S12-f{int(round(f * 100))}", title=f"Trust-score / model poisoning (sign-flip, f={f:.0%})",
        fleet_size=10, duration_s=600.0, world="flat", cai_grade="field", attack=None, methods=("fedqpnt", "fedqpnt_clean"),
        criteria=(Criterion(f"auc_drop_f{int(round(f * 100))}", "Theory: trimmed mean robust for f < beta",
                             _s12_auc_drop(f)),),
        requires_fl=True, poison_frac=f, base_id="S12", group="S12",
        notes="sign_flip only; the ARCH row's other 3 SS4.5 poisoning types are covered by scripts/run_fl_s12_full.py "
              "outside the campaign registry (D-068 scope: sign_flip at the ARCH fractions). 'fedqpnt_clean' = "
              "same federation with no poisoned nodes (D-070).")


S12_VARIANTS = tuple(_make_s12(f) for f in (0.2, 0.4))


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


def _s14_check(results):
    m = "fedqpnt_local"
    legs = []
    f1, fl = _all_runs_field(results, m, "rmse_h_hour_first"), _all_runs_field(results, m, "rmse_h_hour_last")
    if f1 is None or fl is None:
        legs.append(_leg("last_vs_first_hour", None, None, "runner does not emit rmse_h_hour_first/last yet (P3)"))
    else:
        ratio = float(np.median(fl / np.where(f1 == 0, np.nan, f1)))
        legs.append(_leg("last_vs_first_hour", bool(np.isfinite(ratio) and ratio <= 1.2), ratio,
                         f"median RMSE_h(last h)/RMSE_h(first h)={ratio:.3f} (<=1.2)"))
    spd = _all_runs_field(results, m, "p_spd_finite")
    legs.append(_leg("P_SPD", None if spd is None else bool(np.all(spd >= 1.0)),
                     None if spd is None else float(np.mean(spd)),
                     "runner does not emit p_spd_finite yet (P3)" if spd is None
                     else f"P SPD+finite in {np.mean(spd):.3f} of runs (==1)"))
    far = _method_series(results, m, "far_per_hour")
    legs.append(_leg("far", None if far.size == 0 else bool(np.nanmean(far) <= 1.0),
                     None if far.size == 0 else float(np.nanmean(far)),
                     "no runs" if far.size == 0 else f"FAR={np.nanmean(far):.3f}/h (<=1)"))
    rss = _all_runs_field(results, m, "rss_growth_frac")
    legs.append(_leg("rss_growth", None if rss is None else bool(np.all(rss < 0.10)),
                     None if rss is None else float(np.max(rss)),
                     "runner does not emit rss_growth_frac yet (P3)" if rss is None
                     else f"max RSS growth hour1->hour4={np.max(rss):.3f} (<0.10)"))
    return _combine(legs)


S14 = Scenario(
    id="S14", title="Multi-hour stability (Schuler world)", fleet_size=1, duration_s=14400.0,
    world="schuler_tangent", cai_grade="field", attack=None, methods=("fedqpnt_local",),
    criteria=(Criterion("no_slow_drift", "No slow numerical or statistical drift", _s14_check,
                         blocked_by_D047=True),),
    blocked_by_D047=True,
)

S15_ATTACK = dict(kind="drift_spoof", onset_s=60.0, duration_s=300.0, severity=0.6)


def _s15_attacked_leg(results):
    """ARCH S15: 'attacked nodes meet S2' -- P_D >= 0.9 over attacked nodes (first round(0.3 N) node ids).
    The S2 damage legs need an undefended fleet arm (none registered): not evaluable, narrow in paper."""
    runs = _fleet_runs(results, "fedqpnt")
    if not runs:
        return dict(passed=None, value=None, detail="no 'fedqpnt' fleet runs")
    window = S15_ATTACK.get("duration_s")
    hits = []
    for r in runs:
        nodes = r.get("nodes") or {}
        ids = sorted(nodes)
        n_att = max(1, round(0.3 * len(ids)))
        for i in ids[:n_att]:
            nd = dict(nodes[i])
            if nd.get("latency_on") is None:
                continue
            hits.append(_M.detected_from_record(nd, window))
    if not hits:
        return dict(passed=None, value=None, detail="no per-node latency_on for attacked nodes")
    p_d = float(np.mean(hits))
    return dict(passed=bool(p_d >= 0.9), value=p_d,
                detail=f"P_D over attacked nodes={p_d:.3f} (>=0.9); S2 damage legs need an undefended "
                       f"fleet arm: not evaluable (narrow in paper)")


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
    cai_grade="field", attack=S15_ATTACK,
    methods=("fedqpnt",),
    criteria=(Criterion("attacked_meet_s2_pd", "Attacked nodes meet S2 (P_D leg)", _s15_attacked_leg),
              Criterion("unattacked_far_no_quarantine", "Robust aggregator must not punish honest "
                         "heterogeneity", _s15_quarantine_and_far)),
    requires_fl=True,
)


# D-066/D-068: displaced-meaconer variant (attack kind "meaconing_displaced", MEACON 0183f6e). No pass/fail
# halving claim is pre-registered for it (P_D reported; never-worse leg only).
S2_DM = _make_spoof_scenario(
    "S2-DM", "Displaced meaconer (variant)",
    dict(kind="meaconing_displaced", onset_s=60.0, duration_s=300.0, severity=0.6,
         params={"d_max_m": 500, "direction_enu": [0.6, 0.8, 0.0]}),
    final_offset_ge_50m=False, base_id="S2",
    notes="Displaced-meaconer variant (D-066). P_D and never-worse-than-undefended only.")


REGISTRY: dict[str, Scenario] = {s.id: s for s in
                                 (S1, S2_LOW, S2_MED, S2_HIGH, S2_DM, S3, S4, S5, S6, S6_COAST, *S7_VARIANTS, S8, S9,
                                  *S10_VARIANTS, S11, *S12_VARIANTS, S13, S14, S15)}


def variants_of(family: str) -> tuple[Scenario, ...]:
    """All registered variants of an ARCH row (e.g. 'S7' -> 5 toggle periods)."""
    return tuple(s for s in REGISTRY.values() if s.family == family)


def get(scenario_id: str) -> Scenario:
    return REGISTRY[scenario_id]


def all_scenarios() -> tuple[Scenario, ...]:
    return tuple(REGISTRY.values())
