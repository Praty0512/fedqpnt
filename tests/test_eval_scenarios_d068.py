"""D-068 tasks 6-8: registry vs intent, S3/S14 criteria, 8-test confirmatory family, grade dimension."""
import json

import numpy as np
import pytest

from fedqpnt.eval import campaign as CP
from fedqpnt.eval import metrics as M
from fedqpnt.eval import report as RP
from fedqpnt.eval import scenarios as SC


# ---------------- registry vs intent ----------------
def test_s7_five_toggle_periods_and_attack_schedule():
    vs = SC.variants_of("S7")
    assert [v.id for v in vs] == ["S7-p2", "S7-p5", "S7-p10", "S7-p20", "S7-p60"]
    v10 = SC.get("S7-p10")
    assert len(v10.attacks) == int((3600 - 120) // 10)
    a0, a1 = v10.attacks[0], v10.attacks[1]
    assert a1["onset_s"] - a0["onset_s"] == 10.0 and a0["duration_s"] == 5.0   # 50% duty
    assert "undefended" in v10.methods


def test_s10_rate_grid():
    assert sorted(v.gnss_rate_hz for v in SC.variants_of("S10")) == [1.0, 2.0, 5.0, 10.0]
    spec = CP.build_spec_dict(SC.get("S10-r5"), "fedqpnt_local", 500)
    assert spec["gnss_rate_hz"] == 5.0


def test_s10_monotone_check():
    def res(v):
        return {"fedqpnt_local": [dict(rmse_h_pre=x) for x in v]}
    ok = SC.s10_rmse_monotone({1.0: res([3, 3.1, 2.9]), 2.0: res([2, 2.1, 1.9])})
    assert ok["passed"] is True
    bad = SC.s10_rmse_monotone({1.0: res([1, 1.1, 0.9, 1.0]), 2.0: res([5, 5.1, 4.9, 5.0])})
    assert bad["passed"] is False


def test_s11_noise_scaling_and_no_attack():
    s = SC.get("S11")
    assert s.attack is None
    assert s.noise_scale == dict(imu=10.0, gnss=5.0, cai_contrast_div=3.0)
    assert CP.build_spec_dict(s, "fedqpnt_local", 1)["noise_scale"]["gnss"] == 5.0
    assert "noise_scale" not in CP.build_spec_dict(SC.get("S1"), "fedqpnt_local", 1)   # legacy hashes intact


def test_s12_fractions_sign_flip():
    fs = {v.id: v.poison_frac for v in SC.variants_of("S12")}
    assert fs == {"S12-f20": 0.2, "S12-f40": 0.4}
    from fedqpnt.eval import fleet_adapter as FA
    cfg = FA.build_fleet_scenario_config(SC.get("S12-f40"), "fedqpnt", 500)
    assert len(cfg.poison_kind) == 4 and set(cfg.poison_kind.values()) == {"sign_flip"}
    cfg = FA.build_fleet_scenario_config(SC.get("S12-f20"), "fedqpnt", 500)
    assert len(cfg.poison_kind) == 2


def test_s12_f40_reported_only():
    res = {"fedqpnt": [dict(auc=0.7)], "fedqpnt_clean": [dict(auc=0.9)]}
    r = SC.get("S12-f40").criteria[0].check(res)
    assert r["passed"] is None and r["value"] == pytest.approx(0.2)
    assert SC.get("S12-f20").criteria[0].check(res)["passed"] is False


def test_s8_methods_allow_h4():
    assert "baseline_b_cont" in SC.get("S8").methods and "fedqpnt" in SC.get("S8").methods


def test_s4_has_both_legs():
    s = SC.get("S4")
    assert [a["kind"] for a in s.attacks] == ["jam_wideband", "drift_spoof"]
    assert s.attacks[1]["onset_s"] == s.attacks[0]["onset_s"] + s.attacks[0]["duration_s"]
    assert CP.build_spec_dict(s, "fedqpnt_local", 1)["attacks"][1]["kind"] == "drift_spoof"


def test_displaced_meaconer_registered():
    s = SC.get("S2-DM")
    assert s.attack["kind"] == "meaconing_displaced" and s.attack["params"]["d_max_m"] == 500
    assert s.attack["params"]["direction_enu"] == [0.6, 0.8, 0.0]


def test_abl_minus_quantum_alias_turns_cai_off():
    spec = CP.build_spec_dict(SC.get("S2-med"), "abl_minus_quantum", 1)
    assert spec["method"] == "fedqpnt_local" and spec["quantum_grade"] is None
    spec = CP.build_spec_dict(SC.get("S2-med"), "fedqpnt_local", 1)
    assert spec["quantum_grade"] == "field"


def test_grade_dimension_in_task_generation():
    tasks = CP.generate_tasks(["S2-med"], ["fedqpnt_local"], [500], imu_grades=["industrial_mems", "tactical"])
    assert {t.scenario_id for t in tasks} == {"S2-med@industrial_mems", "S2-med@tactical"}
    assert {t.spec["imu_grade"] for t in tasks} == {"industrial_mems", "tactical"}
    legacy = CP.generate_tasks(["S2-med"], ["fedqpnt_local"], [500])
    assert legacy[0].scenario_id == "S2-med" and legacy[0].spec["imu_grade"] == "industrial_mems"
    fleet = CP.generate_tasks(["S5"], ["fedqpnt"], [500], imu_grades=["tactical"])
    assert fleet[0].scenario_id == "S5"      # fleet scenarios have no grade axis


def test_load_results_tags_grade(tmp_path):
    d = tmp_path / "S2-med@tactical" / "fedqpnt_local"
    d.mkdir(parents=True)
    (d / "seed_500.json").write_text(json.dumps(dict(status="ok", seed=500, metrics=dict(x=1))))
    r = CP.load_results(str(tmp_path), "S2-med@tactical", ["fedqpnt_local"])
    assert r["fedqpnt_local"][0]["_imu_grade"] == "tactical"


# ---------------- S3 / S14 / S15 criteria ----------------
def test_s3_criteria_implemented_not_stubs():
    good = dict(t_dist=2.0, frac_e_le_3sigma_att=0.97, n_gnss_accepted_jammed=0)
    c = SC.get("S3").criteria[0]
    assert c.check({"fedqpnt_local": [dict(good), dict(good)]})["passed"] is True
    assert c.check({"fedqpnt_local": [dict(good, t_dist=5.0)]})["passed"] is False
    assert c.check({"fedqpnt_local": [dict(good, frac_e_le_3sigma_att=0.9)]})["passed"] is False
    assert c.check({"fedqpnt_local": [dict(t_dist=2.0)]})["passed"] is None


def test_s14_criteria():
    good = dict(rmse_h_hour_first=10.0, rmse_h_hour_last=11.0, p_spd_finite=1.0, far_per_hour=0.5,
                rss_growth_frac=0.05)
    c = SC.get("S14").criteria[0]
    assert c.check({"fedqpnt_local": [good]})["passed"] is True
    assert c.check({"fedqpnt_local": [dict(good, rmse_h_hour_last=13.0)]})["passed"] is False
    assert c.check({"fedqpnt_local": [dict(good, rss_growth_frac=0.2)]})["passed"] is False
    assert c.check({"fedqpnt_local": [dict(far_per_hour=0.5)]})["passed"] is None


def test_s15_attacked_leg():
    def run(lat):
        nodes = {f"node{i}": dict(latency_on=lat if i < 3 else 400.0, far_per_hour=0.1) for i in range(10)}
        return dict(nodes=nodes, fleet=dict(quarantine_events=0))
    c = [c for c in SC.get("S15").criteria if c.name == "attacked_meet_s2_pd"][0]
    assert c.check({"fedqpnt": [run(20.0)]})["passed"] is True
    assert c.check({"fedqpnt": [run(300.0)]})["passed"] is False      # censored at window -> miss


def test_s3_metrics_consistency_fraction():
    n = 100
    cov = np.tile(np.diag([4.0, 4.0, 4.0]), (n, 1, 1))      # sigma_h = 2 -> 3 sigma = 6
    e = np.full(n, 5.0)
    e[:10] = 7.0
    assert M.consistency_fraction(e, cov) == pytest.approx(0.9)
    assert M.sigma_h_from_cov(cov)[0] == pytest.approx(2.0)


# ---------------- sigma_nom & never-worse ----------------
def test_never_worse_needs_frozen_sigma(tmp_path, monkeypatch):
    monkeypatch.setattr(SC, "SIGMA_NOM_PATH", str(tmp_path / "none.json"))
    res = {"fedqpnt_local": [dict(max_h_att=10.0, _imu_grade="tactical")],
           "undefended": [dict(max_h_att=9.0, _imu_grade="tactical")]}
    c = [c for c in SC.get("S2-low").criteria if c.name == "damage_never_worse"][0]
    assert c.check(res)["passed"] is None
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"industrial_mems": 1.0, "tactical": 0.2}))
    monkeypatch.setattr(SC, "SIGMA_NOM_PATH", str(p))
    assert c.check(res)["passed"] is False          # margin 1.0 > 3*0.2
    res["fedqpnt_local"][0]["max_h_att"] = 9.5
    assert c.check(res)["passed"] is True


# ---------------- confirmatory family ----------------
def _write_runs(root, sid, method, vals):
    d = root / sid / method
    d.mkdir(parents=True, exist_ok=True)
    for i, v in enumerate(vals):
        (d / f"seed_{500 + i}.json").write_text(json.dumps(dict(status="ok", seed=500 + i, metrics=dict(v))))


def test_family_is_exactly_eight_and_m_never_shrinks(tmp_path):
    assert len(RP.CONFIRMATORY_FAMILY) == 8
    conf = RP.confirmatory_tests(str(tmp_path), h2_path=str(tmp_path / "no_h2.json"),
                                 sigma_path=str(tmp_path / "no_sigma.json"))
    assert len(conf) == 8
    assert all(not r["evaluable"] for r in conf.values())
    assert all(r["holm_adjusted_p"] == 1.0 and r["holm_reject_at_0.05"] is False for r in conf.values())
    assert {r["hypothesis"] for r in conf.values()} == {"H1", "H2", "H3", "H4"}


def test_holm_uses_fixed_m8_with_partial_data(tmp_path):
    rng = np.random.default_rng(0)
    n = 12
    a = [dict(rmse_h_att=float(x), latency_on=float(l), detected_on=True, window_s=300.0)
         for x, l in zip(10 + rng.normal(0, 0.1, n), 20 + rng.normal(0, 0.1, n))]
    b = [dict(rmse_h_att=float(x) + 5.0, latency_on=float(l) + 30.0, detected_on=True, window_s=300.0)
         for x, l in zip(10 + rng.normal(0, 0.1, n), 20 + rng.normal(0, 0.1, n))]
    _write_runs(tmp_path, "S2-med", "fedqpnt_local", a)
    _write_runs(tmp_path, "S2-med", "baseline_a", b)
    conf = RP.confirmatory_tests(str(tmp_path), h2_path=str(tmp_path / "x.json"), sigma_path=str(tmp_path / "y.json"))
    r1, r2 = conf["H1_rmse_h_att_vs_A"], conf["H1_latency_on_vs_A"]
    assert r1["evaluable"] and r1["n"] == n
    p_min = min(r1["wilcoxon_p"], r2["wilcoxon_p"])
    # 6 unevaluable tests are still in the family (p=1): the smallest p is multiplied by m=8, not by 2
    assert min(r1["holm_adjusted_p"], r2["holm_adjusted_p"]) == pytest.approx(8 * p_min)
    assert r1["holm_reject_at_0.05"] is True
    assert conf["H2_pd10_vs_Bcont"]["holm_reject_at_0.05"] is False


def test_h3_latency_eff_with_frozen_sigma(tmp_path):
    n = 10
    t = [float(x) for x in np.arange(0, 400.0, 1.0)]
    off = [0.0 if x < 100 else (x - 100) * 0.1 for x in t]        # exceeds 3*0.5=1.5 m first at t=116

    def rec(t_det):
        return dict(offset_t_s=t, offset_m=off, t_on_s=100.0, t_off_s=400.0, t_det=t_det)
    _write_runs(tmp_path, "S6@tactical", "fedqpnt_local", [rec(130.0 + i) for i in range(n)])
    _write_runs(tmp_path, "S6@tactical", "abl_minus_quantum", [rec(200.0 + i) for i in range(n)])
    (tmp_path / "sig.json").write_text(json.dumps({"industrial_mems": 0.5, "tactical": 0.5}))
    kw = dict(h2_path=str(tmp_path / "x.json"), sigma_path=str(tmp_path / "sig.json"))
    # S6 is still BLOCKED by D-047: unevaluable, counted as not rejected
    conf = RP.confirmatory_tests(str(tmp_path), **kw)
    assert conf["H3_latency_eff_tactical"]["evaluable"] is False
    assert "BLOCKED" in conf["H3_latency_eff_tactical"]["detail"]
    orig = SC.S6.blocked_by_D047
    SC.S6.blocked_by_D047 = False
    try:
        conf = RP.confirmatory_tests(str(tmp_path), **kw)
        r = conf["H3_latency_eff_tactical"]
        assert r["evaluable"] and r["n"] == n
        assert r["hodges_lehmann"] == pytest.approx(-70.0)          # (t_det-116): 14 s vs 84 s
        assert conf["H3_latency_eff_mems"]["evaluable"] is False    # no MEMS runs
        conf = RP.confirmatory_tests(str(tmp_path), h2_path=kw["h2_path"], sigma_path=str(tmp_path / "absent.json"))
        assert conf["H3_latency_eff_tactical"]["evaluable"] is False       # sigma_nom not frozen: fails loudly
        assert "sigma_nom" in conf["H3_latency_eff_tactical"]["detail"]
    finally:
        SC.S6.blocked_by_D047 = orig


def test_h2_file_interface(tmp_path):
    f = tmp_path / "h2.json"
    f.write_text(json.dumps({"h2": {"seeds": list(range(500, 510)),
                                     "pd10": {"fedqpnt": [1] * 10, "baseline_b_cont": [0] * 10},
                                     "onset_latency": {"fedqpnt": [5.0] * 10,
                                                       "baseline_b_cont": [float("nan")] * 10}}}))
    conf = RP.confirmatory_tests(str(tmp_path), h2_path=str(f), sigma_path=str(tmp_path / "y.json"))
    assert conf["H2_pd10_vs_Bcont"]["evaluable"]
    assert conf["H2_pd10_vs_Bcont"]["hodges_lehmann"] == pytest.approx(1.0)
    r = conf["H2_onset_latency_vs_Bcont"]
    assert r["evaluable"] and r["hodges_lehmann"] == pytest.approx(5.0 - 60.0)    # NaN censored at 60 s
    assert conf["H4_pd10_coldstart"]["evaluable"] is False                         # no h4 block


def test_provenance_banner_in_report(tmp_path):
    CP.record_provenance(tmp_path, dict(valid=False, reasons=["dirty"], start={}, end={}))
    md = RP.render_markdown(["S1"], str(tmp_path))
    assert "INVALID RUN (D-062)" in md


# ---------------- D-070: S6 = H3 scenario, S6-coast, fleet reference arms ----------------
def test_s6_is_the_h3_scenario():
    s = SC.get("S6")
    assert s.world == "schuler_tangent" and s.duration_s == 1500.0
    assert (s.attack["kind"], s.attack["onset_s"], s.attack["duration_s"], s.attack["severity"]) == \
        ("drift_spoof", 300.0, 900.0, 0.3)
    assert s.methods == ("fedqpnt_local", "abl_minus_quantum", "undefended")
    assert "FIXED BEFORE ANY TEST-SEED DATA" in s.notes and "gradual" in s.notes.lower()
    tasks = CP.generate_tasks(["S6"], None, [500], imu_grades=["industrial_mems", "tactical"])
    assert {t.scenario_id for t in tasks} == {"S6@industrial_mems", "S6@tactical"}
    q = {t.method: t.spec["quantum_grade"] for t in tasks}
    assert q["abl_minus_quantum"] is None and q["fedqpnt_local"] == "field"
    assert all(t.spec["world"] == "schuler_tangent" for t in tasks)


def test_s6_coast_exploratory_not_in_family():
    s = SC.get("S6-coast")
    assert s.attack["kind"] == "jam_wideband" and s.attack["duration_s"] == 180.0
    assert "EXPLORATORY" in s.notes
    r = s.criteria[0].check({"fedqpnt_local": [dict(max_h_att=100.0)], "abl_minus_quantum": [dict(max_h_att=300.0)]})
    assert r["passed"] is None and r["value"] == pytest.approx(3.0)
    assert not any(t.scenario.startswith("S6-coast") for t in RP.CONFIRMATORY_FAMILY)


def test_fleet_reference_arms_registered():
    from fedqpnt.eval import fleet_adapter as FA
    for m in ("fedqpnt_clean", "fedqpnt_nofault", "fedqpnt_noloss"):
        assert m in FA._METHOD_MAP and m in FA.FLEET_METHOD_ALL and m in SC.FLEET_METHOD_ALL
    assert set(SC.FLEET_METHOD_ALL) == set(FA.FLEET_METHOD_ALL)


def test_fleet_clean_arm_has_no_poison():
    from fedqpnt.eval import fleet_adapter as FA
    p = FA.build_fleet_scenario_config(SC.get("S12-f20"), "fedqpnt", 500)
    c = FA.build_fleet_scenario_config(SC.get("S12-f20"), "fedqpnt_clean", 500)
    assert p.poison_kind and not c.poison_kind
    assert (c.method, c.aggregator, c.node_ids) == (p.method, p.aggregator, p.node_ids)


def test_fleet_nofault_arm_has_no_failures_or_delays():
    from fedqpnt.eval import fleet_adapter as FA
    p = FA.build_fleet_scenario_config(SC.get("S5"), "fedqpnt", 500)
    c = FA.build_fleet_scenario_config(SC.get("S5"), "fedqpnt_nofault", 500)
    assert p.failure_round and p.delay_window
    assert not c.failure_round and not c.delay_window


def test_fleet_noloss_arm_uses_lossless_comms_both_legs():
    from fedqpnt.eval import fleet_adapter as FA
    p = FA.build_fleet_scenario_config(SC.get("S9"), "fedqpnt", 500)
    c = FA.build_fleet_scenario_config(SC.get("S9"), "fedqpnt_noloss", 500)
    assert p.comms_cfg.loss_b == 0.9
    assert c.comms_cfg == FA._LOSSLESS_COMMS
    assert c.server_cfg is not None and c.server_cfg.comms == FA._LOSSLESS_COMMS


def test_auc_drop_legs_now_evaluable():
    r = SC.get("S5").criteria[1].check({"fedqpnt": [dict(auc=0.80)], "fedqpnt_nofault": [dict(auc=0.81)]})
    assert r["passed"] is True
    r = SC.get("S9").criteria[0].check({"fedqpnt": [dict(auc=0.7, fleet=dict(aborted=False))],
                                        "fedqpnt_noloss": [dict(auc=0.8)]})
    assert r["passed"] is False           # drop 0.1 > 0.03
    r = SC.get("S12-f20").criteria[0].check({"fedqpnt": [dict(auc=0.85)], "fedqpnt_clean": [dict(auc=0.88)]})
    assert r["passed"] is True
    for sid, ref in (("S5", "fedqpnt_nofault"), ("S9", "fedqpnt_noloss"), ("S12-f20", "fedqpnt_clean")):
        assert ref in SC.get(sid).methods
