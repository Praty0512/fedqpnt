"""H2-ABRUPT diagnostic (D-062 item 2, Master ruling): why is the LIVE
auc_detector_only (~0.25, BELOW chance) so different from the isolated
held-out check (~0.805) at the SAME severity (0.15)?

Cheap offline replay, SINGLE NODE (fedqpnt_local, closed-loop trust active,
matching the live H2 pipeline exactly -- NOT the fleet's 6-process
orchestrator; no multiprocessing spawn at all), ONE seed (500), theta0_noabrupt,
the SAME abrupt attack config the H2/H4 fleet runs use (onset_s=120,
duration_s=300, severity=0.15) in a FULL 600s mission (matching H2's
LIVE_DURATION_S, NOT the isolated check's 120s truncated window). Logs the
FULL per-tick trace (t, oracle active-label, raw_p, w_gnss, es_evidence) so
the exact epoch-set / feature-shift questions in Master's item 2 can be
answered from real numbers instead of guesswork:
  (a) label alignment -- prints t_on/t_off (fedqpnt.eval.metrics.compute_phases)
      alongside the attack config's own onset_s/duration_s to check for any
      off-by-epoch shift.
  (b) score polarity -- raw_p is read directly via the SAME
      `agent.trust.last_raw_p` side channel node_runner.py uses for
      auc_detector_only (M.roc_auc(raw_p_arr, active)); this script does not
      touch that convention, only reports the resulting values.
  (c) epoch set -- splits the labelled 'active' window into an EARLY
      sub-window (first ATTACK_TRANSIENT_S seconds after onset) vs the
      REMAINDER, and reports mean raw_p in each, vs mean raw_p in the
      pre-onset and post-attack CLEAN windows -- directly tests the
      hypothesis that abrupt_spoof's oracle label covers the ENTIRE
      duration_s=300 window even though the attack itself is a ONE-TIME
      step-jump (then held static) whose actual feature signature is only
      transient (near onset + the reacq_epochs=2 lock-loss window), so most
      of the labelled-positive window may in fact look feature-wise
      unremarkable (or even LOWER-scoring than nominal noise), which alone
      can produce a sub-chance AUC without any code bug.
  (d) feature shift under the closed loop -- reports mean w_gnss (trust
      weight) during the same four windows: if trust distrust/exclusion
      itself perturbs the post-transient window's own innovations (e.g. by
      partially trusting a now-steady but offset GNSS fix, or by residual
      filter-state effects from the brief transient), that is visible here
      as a lasting change in w_gnss beyond the transient.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from fedqpnt.eval import metrics as M
from fedqpnt.node.agent import Agent
from fedqpnt.node.environment import EnvConfig, NodeEnvironment
from fedqpnt.node.methods import load_detector_weights, make_agent_config

THETA0_PATH = Path("results/fleet/theta0_noabrupt.npz")
KAPPA_R = 60.0
SEED = 500
DURATION_S = 600.0
ONSET_S, ATK_DUR_S = 120.0, 300.0
SEVERITY = 0.15
# Candidate onset-window widths to report to Master for pre-registration
# (NOT chosen by this script -- D-062 item 2 rule 2: propose options with
# numbers, Master picks). 2.0 = AbruptSpoof's OWN `reacq_epochs=2` field
# (fedqpnt/attacks/spoofing.py) -- a principled, pre-existing, attack-model-
# intrinsic definition of "the physically real transient duration", not
# something chosen after seeing results. 5.0 and 10.0 are wider illustrative
# alternatives.
CANDIDATE_WINDOWS_S = (2.0, 5.0, 10.0)


def main():
    weights_path = THETA0_PATH if THETA0_PATH.exists() else None
    env_cfg = EnvConfig(platform="ground", world="flat", imu_grade="industrial_mems",
                         quantum_grade="field", gnss_rate_hz=1.0, hold_s=30.0,
                         heading_noise_deg=2.0,
                         attacks=[dict(kind="abrupt_spoof", onset_s=ONSET_S, duration_s=ATK_DUR_S,
                                       severity=SEVERITY)])
    env = NodeEnvironment(env_cfg, seed=SEED, node_id="score_trace", dt=0.01, duration_s=DURATION_S)
    agent_cfg = make_agent_config("fedqpnt_local", kappa_R=KAPPA_R, kappa_Q=1.0, world="flat",
                                   quantum_enabled=True,
                                   detector_weights_path=str(weights_path) if weights_path else None)
    agent = Agent(agent_cfg, env.imu.config(), node_id="score_trace")

    f_b_hold, initialized = [], False
    rows_t, rows_active, rows_raw_p, rows_w_gnss, rows_es = [], [], [], [], []
    for k in range(len(env)):
        tick = env.tick(k)
        t = tick.t
        if not initialized:
            if t < env.hold_s:
                if tick.imu is not None:
                    f_b_hold.append(tick.imu.f_b)
                continue
            f_mean = np.mean(f_b_hold, axis=0) if f_b_hold else np.array([0.0, 0.0, 9.80665])
            fx, fy, fz = f_mean
            phi0 = float(np.arctan2(fy, fz))
            theta0_ = float(np.arctan2(-fx, np.sqrt(fy ** 2 + fz ** 2)))
            psi0 = float(tick.truth.att[2]) + env.initial_heading_noise()
            agent.initialize_static(t, tick.truth.pos.copy(), np.array([phi0, theta0_, psi0]))
            initialized = True
            continue
        atick = agent.step(t, tick.imu, tick.quantum, tick.gnss_epoch)
        rows_t.append(t)
        rows_active.append(bool(tick.label.spoofing or tick.label.jamming))
        raw_p = agent.trust.last_raw_p
        rows_raw_p.append(float(raw_p) if raw_p is not None else 0.0)
        rows_w_gnss.append(atick.trust.weights.get("gnss", 1.0))
        rows_es.append(bool(agent.trust.last_es_evidence))

    t_arr = np.array(rows_t)
    active = np.array(rows_active, dtype=bool)
    raw_p = np.array(rows_raw_p, dtype=float)
    w_gnss = np.array(rows_w_gnss, dtype=float)
    es_arr = np.array(rows_es, dtype=bool)

    phases = M.compute_phases(t_arr, active)
    print(f"attack config: onset_s={ONSET_S} duration_s={ATK_DUR_S} severity={SEVERITY}")
    print(f"compute_phases: t_on={phases.t_on} t_off={phases.t_off} "
          f"(expected t_on~={ONSET_S}, t_off~={ONSET_S + ATK_DUR_S})")
    print(f"n_pre={int(phases.pre.sum())} n_att={int(phases.att.sum())} n_post={int(phases.post.sum())}")

    auc = M.roc_auc(raw_p, active)
    print(f"auc_detector_only (full mission, matches node_runner.py's own metric): {auc}")

    def _stats(name, mask):
        if mask.sum() == 0:
            print(f"  {name}: n=0")
            return
        print(f"  {name}: n={int(mask.sum())} mean_raw_p={raw_p[mask].mean():.4f} "
              f"mean_w_gnss={w_gnss[mask].mean():.4f} es_frac={es_arr[mask].mean():.4f}")

    print("windows (pre/post, unconditional on candidate width):")
    _stats("pre-onset (clean, phases.pre)", phases.pre)
    _stats("post-attack (clean, phases.post)", phases.post)

    print("\nD-062 item 2 rule 2: candidate onset-window widths for Master to pre-register "
          "(NOT chosen here) -- 'full attack window' is the CURRENT node_runner.py definition "
          "already reported above; each row below is one 'onset window of N s' candidate:")
    for w in CANDIDATE_WINDOWS_S:
        early_mask = active & (t_arr < ONSET_S + w)
        late_mask = active & (t_arr >= ONSET_S + w)
        _stats(f"  attack EARLY (onset..onset+{w}s)", early_mask)
        _stats(f"  attack LATE (onset+{w}s..offset)", late_mask)
        mask_for_auc = phases.pre | early_mask | phases.post
        if early_mask.sum() > 0 and (phases.pre.sum() + phases.post.sum()) > 0:
            auc_early_only = M.roc_auc(raw_p[mask_for_auc], active[mask_for_auc])
            print(f"    N={w}s: auc_detector_only with ONLY the onset-window's active epochs as "
                  f"positives (vs ALL clean negatives, pre+post): {auc_early_only:.4f}")
        mask_for_auc2 = phases.pre | late_mask | phases.post
        if late_mask.sum() > 0 and (phases.pre.sum() + phases.post.sum()) > 0:
            auc_late_only = M.roc_auc(raw_p[mask_for_auc2], active[mask_for_auc2])
            print(f"    N={w}s: auc_detector_only with ONLY the POST-window's (beyond N s) active "
                  f"epochs as positives (vs ALL clean negatives): {auc_late_only:.4f}")
        print()

    # Also: what if post-attack recovery epochs were excluded from the
    # NEGATIVE set entirely (a "both" option -- full attack window as
    # positives, but negatives = pre-onset only, not post-attack)? Tests
    # whether post-attack's elevated scores (the likely main driver of the
    # sub-chance full-window AUC) are themselves the problem.
    mask_pre_only_neg = phases.pre | active
    auc_full_preneg_only = M.roc_auc(raw_p[mask_pre_only_neg], active[mask_pre_only_neg])
    print(f"auc_detector_only, FULL attack window as positives, PRE-ONSET-ONLY as negatives "
          f"(post-attack excluded entirely): {auc_full_preneg_only:.4f}")


if __name__ == "__main__":
    main()
