"""S7 "no chattering" bound: adversarial property tests (D-068 / S7-BOUND).

Derivation: docs/specs/raw/S7_BOUND.md.  Statement under test (frozen config, trust_law_version="v2"):

  (L1) EVENT-TIMING-FREE LEMMA.  w can only rise through the recovery ramp (rate 1/tau_r toward <= 1) or through
       the PROBE set-point w_probe = 0.3 < 0.5.  Hence, from a down-crossing of 0.5 (w < 0.5) to the next
       up-crossing of 0.9, at least  L = tau_r * ln((1-0.5)/(1-0.9)) = 10 ln 5 = 16.094 s  must elapse, whatever
       the evidence sequence and whatever the event (fix) timing.  Cycle intervals are disjoint, so
       N <= floor(3600 / L) = 223 per law, and for the alias min(w_pos, w_clk) too.
  (L2) REGULAR-CADENCE REFINEMENT.  If fixes arrive on a fixed grid of period D (S7: 1 Hz) the clean-dwell
       gate adds T_clean, giving a cycle of >= T_clean + ramp steps, plus >= 1 event to fall again:
       N <= 133 at D = 1 s.

If ANY sequence exceeds these, the derivation is wrong (fix the derivation, never the law).
"""
from __future__ import annotations

import copy
import math

import numpy as np
import pytest

from fedqpnt.core.types import GnssFix, Innovation
from fedqpnt.eval import metrics as M
from fedqpnt.trust.trust_law import SensorTrustLaw, TrustEngineImpl, TrustLawConfig, make_method_config

CFG = TrustLawConfig()
W_HOUR = 3600.0
W_DOWN, W_UP = 0.5, 0.9

# ---- derived bounds (functions of the frozen config) ----------------------------------------------------------
L_RISE_S = CFG.tau_r * math.log((1.0 - W_DOWN) / (1.0 - W_UP))          # 16.094 s
N_BOUND_ANY_TIMING = math.floor(W_HOUR / L_RISE_S)                       # 223


def n_bound_grid(delta_s: float) -> int:
    """Regular event grid of period delta_s: t_u - t_d >= (ceil(T_clean/D) + ceil(L/D) - 1) * D, next down-crossing
    needs >= 1 more event; N cycles complete by 26 + 27 (N-1) at D = 1."""
    k_clean = math.ceil(CFG.T_clean / delta_s - 1e-9)
    k_ramp = math.ceil(L_RISE_S / delta_s - 1e-9)
    t_cycle = (k_clean + k_ramp - 1) * delta_s
    period = t_cycle + delta_s
    return int(math.floor((W_HOUR - t_cycle) / period)) + 1


def v2_law(cfg: TrustLawConfig = CFG) -> SensorTrustLaw:
    return SensorTrustLaw(cfg=cfg, law_mode="continuous", trust_law_version="v2")


def cycle_intervals(ts, ws):
    """(t_down, t_up) per completed cycle, using EXACTLY the metric's state machine (metrics.trust_cycles)."""
    out, state, t_d = [], "above", None
    for k in range(1, len(ws)):
        if state == "above" and ws[k - 1] >= W_DOWN > ws[k]:
            state, t_d = "waiting_low", ts[k]
        elif state == "waiting_low" and ws[k - 1] < W_UP <= ws[k]:
            out.append((t_d, ts[k]))
            state = "above"
    return out


def check_series(ts, ws, n_bound=N_BOUND_ANY_TIMING, min_len=L_RISE_S):
    ws = np.asarray(ws)
    n = M.trust_cycles(np.asarray(ts), ws)
    iv = cycle_intervals(ts, ws)
    assert len(iv) == n
    for a, b in iv:
        assert b - a >= min_len - 1e-9, f"cycle [{a},{b}] shorter than L={min_len}"
    assert n <= n_bound, f"{n} cycles > bound {n_bound}"
    return n


# ---- event driver ---------------------------------------------------------------------------------------------
class Ev:
    __slots__ = ("t", "p", "nis_ok", "fn", "nv", "es", "esp")

    def __init__(self, t, p, nis_ok=True, fn=True, nv=0.1, es=False, esp=False):
        self.t, self.p, self.nis_ok, self.fn, self.nv, self.es, self.esp = t, p, nis_ok, fn, nv, es, esp


def step_law(law, e: Ev) -> float:
    return law.step(e.t, e.p, nis_ok=e.nis_ok, features_nominal=e.fn, nis_value=e.nv,
                    es_evidence=e.es, es_position=e.esp)


def run_events(events, law=None):
    law = law or v2_law()
    ts, ws = [], []
    for e in events:
        ts.append(e.t)
        ws.append(step_law(law, e))
    return np.array(ts), np.array(ws)


def grid_events(delta, p_fn, dur=W_HOUR):
    n = int(dur / delta)
    for k in range(n):
        t = k * delta
        p, kw = p_fn(k, t)
        yield Ev(t, p, **kw)


# ---- 1. hand-crafted worst cases ------------------------------------------------------------------------------
@pytest.mark.parametrize("delta", [1.0, 0.5, 0.25])
@pytest.mark.parametrize("period", [1.0, 2.0, 5.0, 10.0, 20.0, 60.0])
def test_periodic_toggling(period, delta):
    """Detector p toggling 0/1 with 50% duty at every period in {1,2,5,10,20,60} s; E_s toggling alongside."""
    def fn(k, t):
        hi = (t % period) < period / 2.0
        return (1.0 if hi else 0.0), dict(nis_ok=not hi, fn=not hi, nv=(50.0 if hi else 0.1))
    ts, ws = run_events(list(grid_events(delta, fn)))
    n = check_series(ts, ws)
    assert n <= n_bound_grid(delta) if delta == 1.0 else True


@pytest.mark.parametrize("period", [1.0, 2.0, 5.0, 10.0, 20.0, 60.0])
def test_periodic_toggling_es_evidence(period):
    """E_s (physical evidence: always vetoes, forces p_bar -> 1) toggling; detector p held at 0."""
    def fn(k, t):
        hi = (t % period) < period / 2.0
        return 0.0, dict(es=hi, nis_ok=not hi, nv=(50.0 if hi else 0.1))
    ts, ws = run_events(list(grid_events(1.0, fn)))
    check_series(ts, ws, n_bound=n_bound_grid(1.0), min_len=L_RISE_S)


@pytest.mark.parametrize("nis_case", ["edge_pass", "edge_fail", "alternate"])
def test_nis_at_probe_bound_edges(nis_case):
    """PROBE accepts on mean shadow NIS <= chi2_6(0.99): drive it exactly at / just past the edge, with p toggling."""
    from fedqpnt.trust.trust_law import CHI2_6_99
    period = 30.0
    def nv_of(k):
        if nis_case == "edge_pass":
            return CHI2_6_99 - 1e-9
        if nis_case == "edge_fail":
            return CHI2_6_99 + 1e-9
        return CHI2_6_99 - 1e-9 if (k // 10) % 2 else CHI2_6_99 + 1e-9
    def fn(k, t):
        hi = (t % period) < 4.0                       # short strong bursts (drives D=1 then long clean)
        return (1.0 if hi else 0.0), dict(nv=nv_of(k), nis_ok=not hi)
    ts, ws = run_events(list(grid_events(1.0, fn)))
    check_series(ts, ws, n_bound=n_bound_grid(1.0))


def _greedy(delta, dur=W_HOUR, sparse_gap=None, w_target=0.4999):
    """Adaptive adversary with look-ahead on a deep copy of the law: when armed (w >= 0.9) it picks the p that
    leaves w just below 0.5 (SHALLOWEST possible dip -> shortest possible rise); while dipped it feeds clean
    evidence.  sparse_gap: after a dip, skip events for that many seconds (event-timing attack)."""
    law = v2_law()
    ts, ws = [], []
    t, armed = 0.0, True
    grid = [i / 200.0 for i in range(201)]
    while t < dur:
        if armed:
            best, best_w = None, -1.0
            for p in grid:
                probe = copy.deepcopy(law)
                w = step_law(probe, Ev(t, p, nis_ok=False, fn=False, nv=50.0))
                if w < W_DOWN and w > best_w:
                    best, best_w = p, w
            if best is None:
                best = 1.0
            w = step_law(law, Ev(t, best, nis_ok=False, fn=False, nv=50.0))
            ts.append(t); ws.append(w)
            if w < W_DOWN:
                armed = False
                t += sparse_gap if sparse_gap else delta
                continue
        else:
            w = step_law(law, Ev(t, 0.0))
            ts.append(t); ws.append(w)
            if w >= W_UP:
                armed = True
        t += delta
    return np.array(ts), np.array(ws)


@pytest.mark.parametrize("delta", [1.0, 0.5])
def test_greedy_shallow_dip_adversary_regular_cadence(delta):
    ts, ws = _greedy(delta)
    n = check_series(ts, ws, n_bound=n_bound_grid(1.0) if delta == 1.0 else N_BOUND_ANY_TIMING)
    # D-075: with DISTRUST pinned the greedy adversary at delta=0.5 gets 19 cycles/h (was >= 20); non-vacuity floor 10
    assert n >= 10, "adversary failed to produce cycles (test would be vacuous)"


@pytest.mark.parametrize("gap", [16.2, 17.0, 25.0])
def test_greedy_adversary_sparse_events(gap):
    """Event-timing attack: one shallow-dip event, then silence, then a single clean event that receives the whole
    ramp (dt = gap).  Reaches ~200 cycles/h: this is why the timing-free bound (223), not 133, is the pre-registerable
    integer unless fix cadence is pinned."""
    ts, ws = _greedy(1.0, sparse_gap=gap)
    n = check_series(ts, ws, n_bound=N_BOUND_ANY_TIMING)
    assert n >= 100, f"sparse-timing adversary should get near the bound; got {n}"


# ---- 2. random adversaries (hypothesis-style; hypothesis is not installed -> seeded numpy) ---------------------
def _random_events(rng, mode):
    t = 0.0
    while t < W_HOUR:
        if mode == "grid1":
            dt = 1.0
        elif mode == "mixed":
            dt = float(rng.choice([0.02, 0.1, 0.5, 1.0, 1.0, 1.0, 2.0, 5.0, 12.0, 20.0]))
        else:  # sparse
            dt = float(rng.uniform(0.5, 30.0))
        t += dt
        p = float(rng.choice([0.0, 1.0, rng.uniform(0.0, 1.0), rng.uniform(0.55, 0.62)]))
        # bursts: correlated regime changes make dips + long clean stretches (rises) likely
        yield Ev(t, p, nis_ok=bool(rng.random() < 0.7), fn=bool(rng.random() < 0.7),
                 nv=float(rng.choice([0.1, 5.0, 16.8, 16.82, 40.0])), es=bool(rng.random() < 0.03),
                 esp=bool(rng.random() < 0.03))


def _regime_events(rng, mode):
    """Piecewise regimes (clean stretch / attack burst) with random lengths -> many full cycles."""
    t, clean, left = 0.0, True, 0.0
    while t < W_HOUR:
        if left <= 0:
            clean = not clean
            left = float(rng.uniform(0.3, 12.0) if not clean else rng.uniform(0.5, 40.0))
        dt = 1.0 if mode == "grid1" else float(rng.choice([0.05, 0.5, 1.0, 3.0, 16.0]))
        t += dt; left -= dt
        if clean:
            yield Ev(t, 0.0)
        else:
            yield Ev(t, float(rng.choice([1.0, 0.7, 0.62, 0.58])), nis_ok=False, fn=False, nv=40.0,
                     es=bool(rng.random() < 0.1))


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("mode", ["grid1", "mixed", "sparse"])
def test_random_adversary(seed, mode):
    rng = np.random.default_rng(1000 * seed + hash(mode) % 997)
    ts, ws = run_events(list(_random_events(rng, mode)))
    check_series(ts, ws, n_bound=n_bound_grid(1.0) if mode == "grid1" else N_BOUND_ANY_TIMING)


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("mode", ["grid1", "mixed"])
def test_random_regime_adversary(seed, mode):
    rng = np.random.default_rng(7000 + seed)
    ts, ws = run_events(list(_regime_events(rng, mode)))
    check_series(ts, ws, n_bound=n_bound_grid(1.0) if mode == "grid1" else N_BOUND_ANY_TIMING)


# ---- 3. premises of the proof ----------------------------------------------------------------------------------
def test_premise_rise_only_via_ramp_or_probe_setpoint():
    """Lemma L1's invariant: after every event, 1-w >= (1-w_before) * exp(-dt/tau_r), unless the PROBE branch set
    w = w_probe (0.3 < 0.5, so it can never help cross 0.5 upward)."""
    rng = np.random.default_rng(5)
    for mode in ("mixed", "sparse"):
        law = v2_law()
        prev_t, prev_u = None, 0.0
        for e in _regime_events(rng, "mixed") if mode == "mixed" else _random_events(rng, "sparse"):
            probe_before = law._core_v2.state
            w = step_law(law, e)
            u = 1.0 - w
            if prev_t is not None:
                dt = e.t - prev_t
                in_probe_setpoint = abs(w - CFG.w_probe) < 1e-12
                assert in_probe_setpoint or u >= prev_u * math.exp(-dt / CFG.tau_r) - 1e-12, (e.t, w, prev_u, probe_before)
            prev_t, prev_u = e.t, u


def test_premise_distrust_exits_only_through_probe():
    """State machine: TRUST->DISTRUST only; DISTRUST->PROBE only after >= T_ex; PROBE->{TRUST, DISTRUST}."""
    rng = np.random.default_rng(11)
    for gen in (_random_events(rng, "mixed"), _regime_events(rng, "grid1"), _regime_events(rng, "mixed")):
        law = v2_law()
        prev, t_in = "TRUST", None
        seen = set()
        for e in gen:
            step_law(law, e)
            s = law._core_v2.state
            if s != prev:
                seen.add((prev, s))
                if prev == "DISTRUST":
                    assert s == "PROBE", (prev, s)
                    assert e.t - t_in >= CFG.T_ex - 1e-9
                if prev == "TRUST":
                    assert s == "DISTRUST"
                if s == "DISTRUST":
                    t_in = e.t
                prev = s
        assert ("TRUST", "DISTRUST") in seen


def test_premise_w_pinned_inside_distrust_without_probe():
    """D-075 (inverts the earlier documented SURPRISE): DISTRUST PINS w at w_min and suspends the ramp, so w can
    no longer reach 0.9 inside DISTRUST; the only way up is DISTRUST -> PROBE -> success -> TRUST.  A strong burst
    then clean evidence leaves w == w_min for the whole DISTRUST dwell (< T_ex)."""
    law = v2_law()
    t = 0.0
    for _ in range(3):
        step_law(law, Ev(t, 1.0, nis_ok=False, fn=False, nv=40.0)); t += 1.0
    assert law._core_v2.state == "DISTRUST"
    for _ in range(50):
        step_law(law, Ev(t, 0.0)); t += 1.0
        assert law._core_v2.state == "DISTRUST"
        assert law.w == pytest.approx(CFG.w_min)


def test_premise_reacquisition_cap_never_raises_w():
    law = v2_law()
    for w0 in (0.02, 0.3, 0.5, 0.7, 1.0):
        law.force_w(w0)
        law.apply_reacquisition_cap()
        assert law.w <= w0 + 1e-15 and law.w <= max(w0, 0.0)
        assert law.w == min(w0, CFG.w_reacq)


def test_analytic_numbers():
    assert L_RISE_S == pytest.approx(16.0944, abs=1e-3)
    assert N_BOUND_ANY_TIMING == 223
    assert n_bound_grid(1.0) == 133


# ---- 4. two independent laws / the alias min(w_pos, w_clk) -----------------------------------------------------
@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("mode", ["grid1", "mixed"])
def test_alias_of_two_independent_laws(seed, mode):
    """Two independent v2 laws fed different adversarial evidence (interleaved dips), alias = min."""
    rng = np.random.default_rng(300 + seed)
    a, b = v2_law(), v2_law(dataclass_replace_probe())
    ts, wa, wb = [], [], []
    ga, gb = _regime_events(rng, mode), _regime_events(rng, mode)
    # common clock: take times from ga, feed b its own evidence at the same instants
    for ea in ga:
        eb = next(gb, None) or Ev(ea.t, 0.0)
        eb.t = ea.t
        ts.append(ea.t); wa.append(step_law(a, ea)); wb.append(step_law(b, eb))
    alias = np.minimum(wa, wb)
    nb = n_bound_grid(1.0) if mode == "grid1" else N_BOUND_ANY_TIMING
    n_alias = check_series(ts, alias, n_bound=nb)
    # every alias cycle contains a full rise of at least one channel (proof step) -> >= L (checked in check_series)
    assert n_alias <= N_BOUND_ANY_TIMING


def dataclass_replace_probe():
    import dataclasses
    from fedqpnt.trust.trust_law import CHI2_2_99
    return dataclasses.replace(CFG, probe_nis_bound=CHI2_2_99)


def test_alias_interleaving_greedy_alternating():
    """Constructive interleaving attempt: channel X dips while Y is high, and Y dips the moment X is back at 0.9
    (Y's dip can only start after the alias is 'above' again, i.e. after X >= 0.9)."""
    x, y = v2_law(), v2_law(dataclass_replace_probe())
    ts, al = [], []
    t, turn = 0.0, 0
    armed = True
    while t < W_HOUR:
        cur, oth = (x, y) if turn == 0 else (y, x)
        if armed:
            w_c = step_law(cur, Ev(t, 0.6, nis_ok=False, fn=False, nv=40.0))
            w_o = step_law(oth, Ev(t, 0.0))
            armed = w_c >= W_DOWN
        else:
            w_c = step_law(cur, Ev(t, 0.0))
            w_o = step_law(oth, Ev(t, 0.0))
        w_x, w_y = (w_c, w_o) if turn == 0 else (w_o, w_c)
        ts.append(t); al.append(min(w_x, w_y))
        if not armed and min(w_x, w_y) >= W_UP:
            armed, turn = True, 1 - turn
        t += 1.0
    n = check_series(ts, al, n_bound=n_bound_grid(1.0))
    assert n >= 20


# ---- 5. engine-level (TrustEngineImpl split laws, alias, reacquisition waiver, sparse fixes) -------------------
def _engine(method="fedqpnt"):
    eng = TrustEngineImpl(make_method_config(method))
    st = dict(p=0.0, nis=0.1, x8=0.0, es=(False, False, False), shadow=None)

    def extractor_step(fix, innovations):
        raw = np.zeros(len(eng.detector.normalizer.mu))   # feature-dim agnostic (13/15)
        raw[0] = st["nis"]
        raw[7] = st["x8"]
        return raw

    eng.extractor.step = extractor_step
    eng._gnss_p = lambda raw: st["p"]
    eng._physical_spoof_evidence = lambda *a, **k: st["es"]
    return eng, st


def _fix(t):
    return GnssFix(t=t, pos=np.zeros(3), vel=np.zeros(3), clk_bias=0.0, clk_drift=0.0, cov_pos=np.eye(3),
                   cov_vel=np.eye(3), residual_rms=0.5, num_sats=8, mean_cn0=45.0, std_cn0=1.0, agc_db=0.0,
                   valid=True, raim_stat=1.0, pdop=2.0)


def _engine_run(rng, mode, regime=True):
    eng, st = _engine()
    ts, alias, wp, wc = [], [], [], []
    t, clean, left = 0.0, True, 0.0
    while t < W_HOUR:
        if left <= 0:
            clean = not clean
            left = float(rng.uniform(0.3, 12.0) if not clean else rng.uniform(0.5, 40.0))
        if mode == "grid1":
            dt = 1.0
        else:   # includes gaps > T_gap=5 s -> reacquisition cap / consistency waiver path
            dt = float(rng.choice([0.2, 1.0, 1.0, 3.0, 7.0, 16.0]))
        t += dt; left -= dt
        if clean:
            st.update(p=0.0, nis=0.1, x8=0.0, es=(False, False, False))
        else:
            r = rng.random()
            st.update(p=float(rng.choice([1.0, 0.7, 0.6])), nis=float(rng.choice([0.1, 9.0])),
                      x8=float(rng.choice([0.0, 8.0])),
                      es=(bool(r < 0.2), bool(0.2 <= r < 0.4), bool(0.4 <= r < 0.5)))
        shadow_nis = float(rng.choice([0.5, 12.0, 16.8, 30.0]))
        innov = [Innovation(t=t, sensor="gnss_shadow", nu=np.zeros(6), S=np.eye(6), nis=shadow_nis, dof=6,
                            accepted=True)]
        s = eng.update(t, _fix(t), None, None, None, innov)
        ts.append(t); alias.append(s.weights["gnss"]); wp.append(s.weights["gnss_pos"]); wc.append(s.weights["gnss_clk"])
        assert s.weights["gnss"] == min(s.weights["gnss_pos"], s.weights["gnss_clk"])
    return np.array(ts), np.array(alias), np.array(wp), np.array(wc)


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("mode", ["grid1", "gaps"])
def test_engine_alias_and_per_law_bounds(seed, mode):
    rng = np.random.default_rng(900 + seed)
    ts, alias, wp, wc = _engine_run(rng, mode)
    nb = n_bound_grid(1.0) if mode == "grid1" else N_BOUND_ANY_TIMING
    for series in (alias, wp, wc):
        check_series(ts, series, n_bound=nb)


def test_engine_reacquisition_waiver_cannot_speed_cycles():
    """First fix after a >T_gap outage: capped (w <= 0.5) unless consistent; either way no cycle is faster than L."""
    eng, st = _engine()
    ts, alias = [], []
    t = 0.0
    for k in range(200):
        # short burst -> dip; then 30 s outage; consistent (shadow 0.5) return; repeat
        hi = (k % 20) < 2
        st.update(p=1.0 if hi else 0.0, nis=9.0 if hi else 0.1, es=(False, False, False))
        t += 30.0 if (k % 20) == 5 else 1.0
        innov = [Innovation(t=t, sensor="gnss_shadow", nu=np.zeros(6), S=np.eye(6), nis=0.5, dof=6, accepted=True)]
        s = eng.update(t, _fix(t), None, None, None, innov)
        ts.append(t); alias.append(s.weights["gnss"])
    check_series(ts, alias, n_bound=N_BOUND_ANY_TIMING)


def test_s7_toggle_schedule_through_engine():
    """The registered S7 periods, evidence tied to the toggled spoof windows (p=1 & E_s during ON half)."""
    for period in (2.0, 5.0, 10.0, 20.0, 60.0):
        eng, st = _engine()
        ts, alias = [], []
        for k in range(3600):
            t = float(k)
            on = 60.0 <= t and ((t - 60.0) % period) < period / 2.0
            st.update(p=1.0 if on else 0.0, nis=9.0 if on else 0.1, es=(on, False, False))
            s = eng.update(t, _fix(t), None, None, None, [])
            ts.append(t); alias.append(s.weights["gnss"])
        check_series(ts, alias, n_bound=n_bound_grid(1.0))
