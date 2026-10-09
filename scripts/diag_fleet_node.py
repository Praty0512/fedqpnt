"""DIAG (round-2, tuning seeds only): one fleet-style node IN-PROCESS (no FL), configured exactly like
fedqpnt/fleet/node_runner.py (flat world, industrial_mems, field CAI, theta0 detector from results/fleet/theta0_d054.npz,
fedqpnt_local, NO attack = S8/S5-style clean node). Reports false-alarm onset cause and whether the node ever re-admits.
Usage: python scripts/diag_fleet_node.py <seed> <node_id> [duration_s=570]  (DIAG_ROOT optional)"""
import os, sys
from pathlib import Path
import numpy as np
ROOT = Path(os.environ.get('DIAG_ROOT') or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT))
REPO = Path(__file__).resolve().parent.parent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import make_agent_config, load_detector_weights
from fedqpnt.node.agent import Agent
seed = int(sys.argv[1]); node_id = sys.argv[2]; dur = float(sys.argv[3]) if len(sys.argv) > 3 else 600.0
assert seed < 10000
theta0 = load_detector_weights(REPO / "results/fleet/theta0_d054.npz")
if os.environ.get('DIAG_NORM_V4') == '1':     # candidate F4: theta0 weights but the sup_v4 running normaliser (more clean-data support)
    v4 = load_detector_weights(REPO / 'results/m1/detector_weights_sup_v4.npz')
    for k in ('norm_mu', 'norm_sd', 'norm_count'): theta0[k] = v4[k]
env = NodeEnvironment(EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems", quantum_grade="field",
        gnss_rate_hz=1.0, hold_s=30.0, heading_noise_deg=2.0, attacks=[]), seed=seed, node_id=node_id, dt=0.01, duration_s=dur)
cfg = make_agent_config("fedqpnt_local", world="flat", quantum_enabled=True, imu_grade="industrial_mems", quantum_grade="field")
agent = Agent(cfg, env.imu.config(), node_id=node_id)
agent.trust.detector.set_params({k: np.asarray(v) for k, v in theta0.items()})
_orig = agent.trust._physical_spoof_evidence
_cap = {}
def _wrap(*a, **k):
    out = _orig(*a, **k)
    if k.get('split'):
        _cap['split'] = out
        if out[2] and not _cap.get('z'):
            import fedqpnt.trust.trust_law as TL
            raw = a[0]; nz = agent.trust.detector.normalizer
            _cap['z'] = dict(xsat=(round(float(raw[TL._IDX_XSAT_CORR]),3), round(float(nz.mu[TL._IDX_XSAT_CORR]),3), round(float(nz.sd[TL._IDX_XSAT_CORR]),3)),
                             cn0=(round(float(raw[TL._IDX_CN0_MEAN]),2), round(float(nz.mu[TL._IDX_CN0_MEAN]),2), round(float(nz.sd[TL._IDX_CN0_MEAN]),2)), t_ep=agent.trust.extractor._last_t)    # (position_event, clk_event, xsat_or_cn0_event)
    return out
agent.trust._physical_spoof_evidence = _wrap
f_hold, init, prev = [], False, "TRUST"
errs, events, n_ep, n_dis = [], [], 0, 0
for k in range(len(env)):
    tick = env.tick(k); t = tick.t
    if not init:
        if t < env.hold_s:
            if tick.imu is not None: f_hold.append(tick.imu.f_b)
            continue
        fm = np.mean(f_hold, axis=0)
        phi = np.arctan2(fm[1], fm[2]); th = np.arctan2(-fm[0], np.hypot(fm[1], fm[2]))
        agent.initialize_static(t, tick.truth.pos.copy(), np.array([phi, th, float(tick.truth.att[2]) + env.initial_heading_noise()]))
        init = True; continue
    a = agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
    errs.append(float(np.hypot(*(a.nav.pos - tick.truth.pos)[:2])))
    if tick.gnss_epoch is not None:
        n_ep += 1
        st = agent.trust.gnss_law._core_v2.state
        n_dis += st != "TRUST"
        if st != prev and (st == "DISTRUST" and prev == "TRUST" or st == "TRUST"):
            events.append((round(t, 1), prev + "->" + st, round(agent.trust.last_raw_p or 0, 2), bool(agent.trust.last_es_evidence), round(errs[-1], 1), 'E_s(pos,clk,xsat/cn0)=' + str(_cap.get('split'))))
        prev = st
e = np.array(errs)
print('first xsat/cn0 fire (value, mu, sd):', _cap.get('z'))
print(f"seed={seed} {node_id} rmse_h={np.sqrt(np.mean(e**2)):.1f} max_h={e.max():.1f} frac_epochs_not_TRUST={n_dis/max(n_ep,1):.2f} events(t,trans,raw_p,E_s,err_h)={events[:8]}")
