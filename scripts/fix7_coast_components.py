"""FIX7 B5: per-state normalised squared error z^2 = err_i^2 / P_ii (ideal mean 1) pooled over seeds, during a pure
GNSS outage on clean data (tuning seeds). States: pos E,N,U; vel E,N,U; tilt E,N; yaw; bg E,N,U (nav frame); ba E,N,U.
Usage: python scripts/fix7_coast_components.py --grade tactical --t_on 60 --seeds 530-549 --workers 4 [--nocai]"""
import argparse, sys, json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
MARKS = [0, 30, 60, 120, 180, 240, 299]
NAMES = ["pE", "pN", "pU", "vE", "vN", "vU", "tE", "tN", "yaw", "bgE", "bgN", "bgU", "baE", "baN", "baU"]


def log_rot(R):
    ang = np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))
    if ang < 1e-9: return np.zeros(3)
    return ang / (2 * np.sin(ang)) * np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])


def run_one(a):
    seed, grade, t_on, cai, world, zero = a
    from fedqpnt.node.agent import Agent
    from fedqpnt.node.environment import EnvConfig, NodeEnvironment
    from fedqpnt.node.methods import make_agent_config
    from fedqpnt.sim.rotations import euler_to_dcm
    q = "field" if cai else None
    env = NodeEnvironment(EnvConfig(platform="ground", world=world, imu_grade=grade, quantum_grade=q, gnss_rate_hz=1.0,
                                    hold_s=30.0, heading_noise_deg=2.0, attacks=[]), seed=seed, node_id="n", dt=0.01,
                          duration_s=t_on + 300.0)
    ag = Agent(make_agent_config("undefended", world=world, imu_grade=grade, quantum_grade=q), env.imu.config(), node_id="n")
    ga, gg = env.imu._accel_ch, env.imu._gyro_ch
    for z in zero:   # ABLATION ONLY (diagnostic): remove one true error source from the simulated IMU
        if z == "sf_g": gg.scale_factor = np.ones(3)
        if z == "mis_g": gg.misalignment = np.eye(3)
        if z == "sf_a": ga.scale_factor = np.ones(3)
        if z == "mis_a": ga.misalignment = np.eye(3)
        if z == "gm_g": gg.bias_gm = np.zeros(3); gg.driving_std = 0.0
        if z == "gm_a": ga.bias_gm = np.zeros(3); ga.driving_std = 0.0
        if z == "arw": gg.p = __import__('dataclasses').replace(gg.p, random_walk=0.0)
        if z == "vrw": ga.p = __import__('dataclasses').replace(ga.p, random_walk=0.0)
        if z == "ba": ga.turn_on_bias = np.zeros(3)
        if z == "bg": gg.turn_on_bias = np.zeros(3)
    hold, init = [], False
    out = {}
    for k in range(len(env)):
        tk = env.tick(k); t = tk.t
        if not init:
            if t < env.hold_s:
                if tk.imu is not None: hold.append(tk.imu.f_b)
                continue
            fx, fy, fz = np.mean(hold, axis=0)
            ag.initialize_static(t, tk.truth.pos.copy(), np.array([np.arctan2(fy, fz), np.arctan2(-fx, np.hypot(fy, fz)), float(tk.truth.att[2]) + env.initial_heading_noise()]))
            init = True; continue
        ge = tk.gnss_epoch
        if t_on <= t < t_on + 300: ge = None
        a_ = ag.step(t, tk.imu, tk.quantum, ge)
        off = round(t - t_on, 3)
        if off in MARKS:
            e = ag.eskf; P = e.P; Ct = euler_to_dcm(tk.truth.att)
            Cn = Ct  # body->nav of truth
            d = np.zeros(15)
            d[0:3] = a_.nav.pos - tk.truth.pos; d[3:6] = a_.nav.vel - tk.truth.vel
            d[6:9] = log_rot(Ct @ e.C.T)   # psi: C_true = exp(psi) C_est (filter convention)
            d[12:15] = Ct @ (e.b_g - (gg.turn_on_bias + gg.bias_gm)); d[9:12] = Ct @ (e.b_a - (ga.turn_on_bias + ga.bias_gm))
            # P is in the filter error-state convention (nav-frame psi; biases in BODY frame): rotate bias blocks to nav for z^2
            Tm = np.eye(15); Tm[9:12, 9:12] = Ct; Tm[12:15, 12:15] = Ct
            Pn = Tm @ P @ Tm.T
            z2 = d ** 2 / np.diag(Pn)
            # also 6-D, 9-D(pos,vel,tilt) and 15-D NEES in the nav frame (bias blocks rotated)
            def nees(ix):
                ix = list(ix); return float(d[ix] @ np.linalg.solve(Pn[np.ix_(ix, ix)], d[ix]))
            out[str(off)] = dict(z2=z2.tolist(), n6=nees(range(6)), n9=nees(range(9)), n15=nees(range(15)),
                                 n3p=nees(range(3)), n3v=nees(range(3, 6)))
    return dict(seed=seed, res=out)


def parse(txt):
    o = []
    for p in txt.replace(",", " ").split():
        if "-" in p:
            x, y = p.split("-"); o += range(int(x), int(y) + 1)
        else: o.append(int(p))
    return o


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--grade", required=True); ap.add_argument("--t_on", type=float, default=60.0)
    ap.add_argument("--seeds", default="530-549"); ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--nocai", action="store_true"); ap.add_argument("--world", default="schuler_tangent")
    ap.add_argument("--out", default=None); ap.add_argument("--zero", default="")
    a = ap.parse_args()
    seeds = parse(a.seeds); assert all(s < 10000 for s in seeds)
    with ProcessPoolExecutor(max_workers=min(a.workers, 4)) as ex:
        rows = list(ex.map(run_one, [(s, a.grade, a.t_on, not a.nocai, a.world, tuple(filter(None, a.zero.split(',')))) for s in seeds]))
    if a.out: Path(a.out).write_text(json.dumps(rows))
    print(f"=== {a.grade} t_on={a.t_on} cai={not a.nocai} n={len(rows)} mean z^2 per state (ideal 1)")
    print("  +s  " + " ".join(f"{n:>6}" for n in NAMES) + " |  A3p   A3v   A6   A9   A15 (mean NEES/dof)  | median A6")
    pool = []
    for m in MARKS:
        z = np.array([r["res"][str(float(m))]["z2"] for r in rows])
        g = lambda k: np.array([r["res"][str(float(m))][k] for r in rows])
        print(f"{m:5d} " + " ".join(f"{x:6.2f}" for x in z.mean(0)) + f" | {g('n3p').mean()/3:5.2f} {g('n3v').mean()/3:5.2f} {g('n6').mean()/6:5.2f} {g('n9').mean()/9:5.2f} {g('n15').mean()/15:5.2f} | {np.median(g('n6'))/6:5.2f}")
        if m > 0: pool.append(g("n6").mean() / 6)
    print(f"pooled mean ANEES6 (+30..+299): {np.mean(pool):.2f}")
