"""FIX7 B5 diagnostic (TUNING seeds only): pure-coast NEES of the ESKF on CLEAN data.
GNSS removed in [t_on, t_on+LEN); CAI (field) on; method=undefended (w=1, no attack). Statistics at +dt checkpoints:
6-D NEES (pos+vel block of P), 3-D pos NEES. ANEES = mean NEES / dof (ideal 1), pooled over seeds.
Usage: python scripts/fix7_coast_nees.py --grade tactical --t_on 60 --seeds 530-549 --workers 4 --out results/fix7/x.json"""
from __future__ import annotations
import argparse, json, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
LEN = 300.0
CHECK = (0.0, 30.0, 60.0, 120.0, 180.0, 240.0, 299.0)


def run_one(a):
    seed, grade, t_on, world, cai, nogps_extra = a
    assert seed < 10000
    from fedqpnt.node.agent import Agent
    from fedqpnt.node.environment import EnvConfig, NodeEnvironment
    from fedqpnt.node.methods import make_agent_config
    env = NodeEnvironment(EnvConfig(platform="ground", world=world, imu_grade=grade,
                                    quantum_grade=("field" if cai else None), gnss_rate_hz=1.0, hold_s=30.0,
                                    heading_noise_deg=2.0, attacks=[]),
                          seed=seed, node_id="n", dt=0.01, duration_s=t_on + LEN)
    cfg = make_agent_config("undefended", world=world, imu_grade=grade, quantum_grade=("field" if cai else None))
    ag = Agent(cfg, env.imu.config(), node_id="n")
    if nogps_extra == "so0":
        ag.eskf.cfg.second_order_att = False      # BEFORE-fix model (FIX7 B5 comparison)
    hold, init = [], False
    marks = {round(t_on + c, 3): c for c in CHECK}
    out = {}
    for k in range(len(env)):
        tk = env.tick(k); t = tk.t
        if not init:
            if t < env.hold_s:
                if tk.imu is not None:
                    hold.append(tk.imu.f_b)
                continue
            fx, fy, fz = np.mean(hold, axis=0)
            ag.initialize_static(t, tk.truth.pos.copy(), np.array(
                [np.arctan2(fy, fz), np.arctan2(-fx, np.hypot(fy, fz)),
                 float(tk.truth.att[2]) + env.initial_heading_noise()]))
            init = True
            continue
        ge = tk.gnss_epoch
        if t_on <= t < t_on + LEN:
            ge = None
        a_ = ag.step(t, tk.imu, tk.quantum, ge)
        key = round(t, 3)
        if key in marks:
            e = np.concatenate([a_.nav.pos - tk.truth.pos, a_.nav.vel - tk.truth.vel])
            P = ag.eskf.P[0:6, 0:6]
            out[marks[key]] = dict(n6=float(e @ np.linalg.solve(P, e)),
                                   n3=float(e[:3] @ np.linalg.solve(P[:3, :3], e[:3])),
                                   nv=float(e[3:] @ np.linalg.solve(P[3:, 3:], e[3:])),
                                   eh=float(np.hypot(e[0], e[1])), ev=float(np.linalg.norm(e[3:5])),
                                   sp=float(np.sqrt(np.trace(P[:2, :2]) / 2)))
    return dict(seed=seed, grade=grade, t_on=t_on, res=out)


def parse(txt):
    o = []
    for p in txt.replace(",", " ").split():
        if "-" in p:
            a, b = p.split("-"); o += range(int(a), int(b) + 1)
        else:
            o.append(int(p))
    return o


def summarize(rows, grade, t_on):
    print(f"=== {grade} outage t_on={t_on} n={len(rows)}  ANEES6 = mean(NEES6)/6, ANEES3 = mean/3 (ideal 1); med = median NEES6/6")
    print(f"{'+s':>5} {'ANEES6':>9} {'med6':>8} {'ANEES3pos':>10} {'ANEESvel':>9} {'med err_h':>10} {'med sig_h':>10}")
    pooled = []
    for c in CHECK:
        v = [r["res"][c] for r in rows if c in r["res"]]
        n6 = np.array([x["n6"] for x in v])
        print(f"{c:5.0f} {n6.mean()/6:9.2f} {np.median(n6)/6:8.2f} {np.mean([x['n3'] for x in v])/3:10.2f} "
              f"{np.mean([x['nv'] for x in v])/3:9.2f} {np.median([x['eh'] for x in v]):10.1f} {np.median([x['sp'] for x in v]):10.1f}")
        if c > 0:
            pooled.append(n6.mean() / 6)
    print(f"pooled mean ANEES6 over +30..+299: {np.mean(pooled):.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grade", required=True); ap.add_argument("--t_on", type=float, default=60.0)
    ap.add_argument("--seeds", default="530-549"); ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--world", default="schuler_tangent"); ap.add_argument("--nocai", action="store_true")
    ap.add_argument("--so0", action="store_true", help="disable the FIX7 second-order attitude covariance (before-fix model)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    seeds = parse(a.seeds); assert all(s < 10000 for s in seeds)
    tasks = [(s, a.grade, a.t_on, a.world, not a.nocai, 'so0' if a.so0 else None) for s in seeds]
    with ProcessPoolExecutor(max_workers=min(a.workers, 4)) as ex:
        rows = list(ex.map(run_one, tasks))
    for r in rows:
        r["res"] = {str(k): v for k, v in r["res"].items()}
    Path(a.out).write_text(json.dumps(rows))
    rows2 = [dict(r, res={float(k): v for k, v in r["res"].items()}) for r in rows]
    summarize(rows2, a.grade, a.t_on)


if __name__ == "__main__":
    main()
