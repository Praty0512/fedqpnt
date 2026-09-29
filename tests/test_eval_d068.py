"""D-068: provenance (D-062), ANEES full block, uniform censoring, latency_eff."""
import json
import subprocess

import numpy as np
import pytest

from fedqpnt.eval import campaign as CP
from fedqpnt.eval import metrics as M
from fedqpnt.eval import report as RP
from fedqpnt.eval import scenarios as SC


# ---- provenance ----
def _git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "fedqpnt").mkdir()
    (tmp_path / "fedqpnt" / "a.py").write_text("x=1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def test_provenance_clean_valid(repo):
    a = CP.git_provenance(repo)
    b = CP.git_provenance(repo)
    assert a["head"] and a["dirty_files"] == []
    assert CP.provenance_verdict(a, b)["valid"] is True


def test_provenance_dirty_at_launch_invalid(repo):
    (repo / "fedqpnt" / "a.py").write_text("x=2\n")
    a = CP.git_provenance(repo)
    assert a["dirty_files"]
    v = CP.provenance_verdict(a, CP.git_provenance(repo))
    assert v["valid"] is False and any("dirty at launch" in r for r in v["reasons"])


def test_provenance_changed_during_run_invalid(repo):
    a = CP.git_provenance(repo)
    (repo / "fedqpnt" / "a.py").write_text("x=3\n")
    v = CP.provenance_verdict(a, CP.git_provenance(repo))
    assert v["valid"] is False


def test_provenance_untracked_outside_subtree_ignored(repo):
    (repo / "other.txt").write_text("z")
    assert CP.git_provenance(repo)["dirty_files"] == []


def test_provenance_unavailable_invalid(tmp_path):
    a = CP.git_provenance(tmp_path)   # not a git repo
    assert CP.provenance_verdict(a, a)["valid"] is False


def test_record_and_read_provenance(tmp_path):
    bad = dict(valid=False, reasons=["x"], start={}, end={})
    assert CP.provenance_valid(tmp_path) is None
    CP.record_provenance(tmp_path, dict(valid=True, reasons=[], start={}, end={}))
    assert CP.provenance_valid(tmp_path) is True
    CP.record_provenance(tmp_path, bad)
    assert CP.provenance_valid(tmp_path) is False


# ---- ANEES full block ----
def test_anees_full_block_hand_computed():
    # err = [1,1,0]; P = [[2,1,0],[1,2,0],[0,0,1]]; P^-1 block = 1/3*[[2,-1],[-1,2]]
    # e^T P^-1 e = (1/3)(2 -1 -1 +2) = 2/3 ; ANEES = (2/3)/3 = 2/9
    est = np.array([[1.0, 1.0, 0.0]])
    true = np.zeros((1, 3))
    P = np.array([[[2.0, 1.0, 0.0], [1.0, 2.0, 0.0], [0.0, 0.0, 1.0]]])
    assert M.anees_pos(est, true, P) == pytest.approx(2.0 / 9.0, rel=1e-6)
    # the diagonal approximation would give (0.5+0.5)/3 = 1/3: differs
    assert M.anees_pos(est, true, np.diagonal(P, axis1=1, axis2=2)) == pytest.approx(1.0 / 3.0, rel=1e-6)


def test_anees_mask():
    est = np.array([[1.0, 0, 0], [5.0, 0, 0]])
    P = np.stack([np.eye(3)] * 2)
    assert M.anees_pos(est, np.zeros((2, 3)), P, np.array([True, False])) == pytest.approx(1.0 / 3.0, rel=1e-6)


# ---- censoring ----
def test_censor_event_and_window():
    assert M.censor_event(np.nan, False) == 60.0
    assert M.censor_event(5.0, True) == 5.0
    assert M.censor_event(500.0, True) == 60.0
    assert M.censor_window(300.0, False, 300.0) == 300.0
    assert M.censor_window(7.0, True, 300.0) == 7.0


def test_detection_outcome_hit_and_miss():
    t = np.arange(0, 100, 1.0)
    active = (t >= 20) & (t < 60)
    ph = M.compute_phases(t, active, t_align=0)
    det = t >= 30
    o = M.detection_outcome(t, det, ph)
    assert o["detected"] and o["latency_on"] == pytest.approx(10.0)
    o = M.detection_outcome(t, np.zeros_like(t, bool), ph)
    assert not o["detected"] and o["latency_on"] == o["window_s"]


def test_report_latency_series_no_data_dependent_censor():
    sc = SC.get("S2-med")
    res = {"a": [dict(latency_on=300.0, detected_on=False), dict(latency_on=10.0, detected_on=True)]}
    v = RP._latency_series(res, "a", "latency_on", sc)
    assert list(v) == [300.0, 10.0]                      # t_off - t_on = 300, not nanmax
    res2 = {"a": [dict(latency_on=10.0, detected_on=True, window_s=300.0)]}
    res2["a"] = [dict(onset_latency=10.0, detected_on=True), dict(onset_latency=300.0, detected_on=False)]
    assert list(RP._latency_series(res2, "a", "onset_latency", sc)) == [10.0, 60.0]
    ev = {"a": [dict(onset_latency=np.nan, detected_on=False)]}
    assert list(RP._latency_series(ev, "a", "onset_latency", sc)) == [60.0]


# ---- latency_eff ----
def test_load_sigma_nom_fails_loudly(tmp_path):
    with pytest.raises(FileNotFoundError):
        M.load_sigma_nom(str(tmp_path / "nope.json"))
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"industrial_mems": 0.3, "tactical": 0.2}))
    assert M.load_sigma_nom(str(p))["tactical"] == 0.2


def test_latency_eff_hit_miss_excluded():
    t = np.arange(0, 100, 1.0)
    ph = M.compute_phases(t, (t >= 20) & (t < 80), t_align=0)
    off = np.where(t >= 20, (t - 20) * 0.5, 0.0)        # exceeds 3*0.5=1.5 m at t=24 (0.5*4=2>1.5; t=23 -> 1.5 not >)
    r = M.latency_eff(t, off, t_det=30.0, phases=ph, sigma_nom_m=0.5)
    assert r["t_eff"] == 24.0 and r["latency_eff"] == 6.0 and r["detected"]
    r = M.latency_eff(t, off, t_det=float("nan"), phases=ph, sigma_nom_m=0.5)
    assert r["latency_eff"] == ph.t_off - 24.0 and not r["detected"]
    r = M.latency_eff(t, off * 0.0, t_det=30.0, phases=ph, sigma_nom_m=0.5)
    assert r["excluded"] and np.isnan(r["latency_eff"])
    r = M.latency_eff(t, off, t_det=22.0, phases=ph, sigma_nom_m=0.5)   # detected before effective
    assert r["latency_eff"] == -2.0
