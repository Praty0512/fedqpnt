"""§3.2/§4.2/§4.3 detector validation on real fedqpnt.gnss + fedqpnt.attacks
runs, tuning seeds 500-599 only (per DECISION_LOG/§4.2 seed partition).

Trains locally (no FL round-trip -- that's the FEDERATED agent's code) on
HINDSIGHT PSEUDO-LABELS ONLY (never AttackLabel). AttackLabel is read ONLY
by this test file (tests/ is evaluator territory), to report the required
honesty numbers: pseudo-label precision/recall and per-attack-family AUC.

**PROVISIONAL**: all AUC/precision/recall numbers in this file use SYNTHETIC
truth-derived Innovations (fix-vs-truth residual, tests/_trust_harness.py) --
there is no fusion filter at M0. Re-run once fedqpnt.fusion lands (M1) before
treating these numbers as final (D-022).
"""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from fedqpnt.trust.detector import TrustDetector
from fedqpnt.trust.features import EwmaStack
from fedqpnt.trust.pseudolabel import (
    label_epochs, pseudolabel_precision_recall, surrogate_s_cusum,
    _xsat_replay_condition, PseudoLabelConfig,
)
from tests._trust_harness import generate_run, FAMILIES

TRAIN_ATTACK_SEEDS = range(500, 505)   # 5 seeds x 4 families = 20 attacked runs
TRAIN_CLEAN_SEEDS = range(590, 595)    # 5 clean runs -> 25 train runs total (>= 20 attacked + clean, per brief)
TEST_ATTACK_SEEDS = range(550, 555)    # held-out seeds, still in [500,599]
TEST_CLEAN_SEEDS = range(595, 600)
CALIB_CLEAN_SEEDS = range(500, 550)    # D-026: enlarged per D-024's original spec, seeds 500-549


def _build_runs(attack_seeds, clean_seeds):
    runs = []
    for fam in FAMILIES:
        for seed in attack_seeds:
            runs.append(generate_run(seed, fam))
    for seed in clean_seeds:
        runs.append(generate_run(seed, "clean"))
    return runs


@pytest.fixture(scope="module")
def clean_reference():
    """D-024: robust nominal quantile reference (mu, sd over all 15 raw
    features), calibrated ONLY on clean runs from seeds 500-529 (never
    self-referential to the run being labelled, and never touching the
    500-554 attacked seeds used for train/test)."""
    feats = np.concatenate([generate_run(s, "clean").raw_features for s in CALIB_CLEAN_SEEDS])
    mu = feats.mean(axis=0)
    sd = feats.std(axis=0)
    sd = np.where(sd < 1e-9, 1.0, sd)
    return mu, sd


@pytest.fixture(scope="module")
def train_runs():
    return _build_runs(TRAIN_ATTACK_SEEDS, TRAIN_CLEAN_SEEDS)


@pytest.fixture(scope="module")
def test_runs():
    return _build_runs(TEST_ATTACK_SEEDS, TEST_CLEAN_SEEDS)


def _pseudolabel_run(run, clean_reference, rule_on=True):
    mu, sd = clean_reference
    cfg = PseudoLabelConfig(enable_xsat_rule=rule_on)
    return label_epochs(run.t, run.raw_features, run.raim_stat, run.num_sats,
                         surrogate_s_cusum(run.raw_features), cfg=cfg, quantile_mu=mu, quantile_sd=sd)


def _bootstrap_auc_ci(oracle, scores, n_boot=1000, seed=0):
    oracle = np.asarray(oracle, dtype=bool)
    scores = np.asarray(scores, dtype=float)
    if len(np.unique(oracle)) < 2:
        return float("nan"), (float("nan"), float("nan"))
    point = float(roc_auc_score(oracle, scores))
    rng = np.random.default_rng(seed)
    n = len(oracle)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        o_b, s_b = oracle[idx], scores[idx]
        if len(np.unique(o_b)) < 2:
            continue
        boots.append(roc_auc_score(o_b, s_b))
    if not boots:
        return point, (float("nan"), float("nan"))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return point, (float(lo), float(hi))


def _train_and_eval(train_runs, test_runs, clean_reference, rule_on, balance_on):
    """D-026 2x2 cell: {xsat rule on/off} x {50%-cap balancing on/off}.
    Returns AUC+CI per family, pos/neg counts, and the jamming-ACTIVE
    pseudo-label breakdown (item 5's labeller-vs-classifier diagnostic)."""
    detector = TrustDetector(arch="mlp", seed=0)

    labels_by_run = {id(r): _pseudolabel_run(r, clean_reference, rule_on) for r in train_runs}
    neg_feats = np.concatenate([r.raw_features[labels_by_run[id(r)] == 0.0] for r in train_runs
                                 if np.any(labels_by_run[id(r)] == 0.0)])
    for row in neg_feats:
        detector.normalizer.update(row)

    U_list, y_list = [], []
    for run in train_runs:
        y = labels_by_run[id(run)]
        stack = EwmaStack()
        for k in range(len(run.t)):
            xtilde = detector.normalizer.normalize(run.raw_features[k])
            u = stack.step(run.t[k], xtilde)
            if not np.isnan(y[k]):
                U_list.append(u)
                y_list.append(y[k])
    U = np.array(U_list)
    y = np.array(y_list)
    n_pos_pre, n_neg_pre = int((y > 0).sum()), int((y == 0).sum())

    train_metrics = detector.train_local(U, y, y, epochs=2, lr=0.05, batch_size=64, prox_mu=0.0,
                                          balance=balance_on, max_pos_fraction=0.5)

    per_family_scores = {f: [] for f in FAMILIES}
    per_family_oracle = {f: [] for f in FAMILIES}
    all_scores, all_oracle = [], []
    for run in test_runs:
        detector.reset_stream()
        for k in range(len(run.t)):
            p_spoof, p_jam, _u = detector.score(run.t[k], run.raw_features[k])
            p = max(p_spoof, p_jam)
            if run.family != "clean":
                per_family_scores[run.family].append(p)
                per_family_oracle[run.family].append(run.oracle_active[k])
            all_scores.append(p)
            all_oracle.append(run.oracle_active[k])

    auc_per_family = {fam: _bootstrap_auc_ci(per_family_oracle[fam], per_family_scores[fam]) for fam in FAMILIES}
    overall_auc = _bootstrap_auc_ci(all_oracle, all_scores)

    # item 5: jamming-ACTIVE epochs (train pool) -- what pseudo-label do they get?
    jam_active_labels = []
    for run in train_runs:
        if run.family == "jamming":
            y = labels_by_run[id(run)]
            jam_active_labels.append(y[run.oracle_active])
    jam_active_labels = np.concatenate(jam_active_labels) if jam_active_labels else np.array([])
    jam_breakdown = dict(
        y0=int(np.sum(jam_active_labels == 0.0)),
        y1=int(np.sum(jam_active_labels == 1.0)),
        abstain=int(np.sum(np.isnan(jam_active_labels))),
        n=len(jam_active_labels),
    )

    return dict(train_pos=n_pos_pre, train_neg=n_neg_pre, train_metrics=train_metrics,
                auc_per_family=auc_per_family, overall_auc=overall_auc, jam_active_breakdown=jam_breakdown)


def test_xsat_replay_rule_false_positive_rate(clean_reference):
    """D-024 item 2: the new single-antenna/replay rule (x14/x4, >=10s
    dwell) must almost never fire on clean data, and should fire noticeably
    on the families it targets (meaconing, and other spoofs that touch
    C/N0), reported honestly per family."""
    mu, sd = clean_reference
    cfg = PseudoLabelConfig()
    rates = {}
    for fam in list(FAMILIES) + ["clean"]:
        seeds = TEST_ATTACK_SEEDS if fam != "clean" else TEST_CLEAN_SEEDS
        fires, total = 0, 0
        for seed in seeds:
            run = generate_run(seed, fam)
            event = _xsat_replay_condition(run.t, run.raw_features, mu, sd,
                                            cfg.quantile_z, cfg.xsat_cn0_band_excess_db, cfg.xsat_dwell_s)
            fires += int(event.sum())
            total += len(event)
        rates[fam] = fires / total if total else float("nan")
    print("\n[D-024 xsat-replay rule] firing rate per family (held-out seeds):", rates)
    assert rates["clean"] <= 0.01, f"xsat-replay rule false-positive rate {rates['clean']:.3f} > 1% target"


def test_pseudolabel_precision_recall_on_training_pool(train_runs, clean_reference):
    all_y, all_oracle = [], []
    for run in train_runs:
        y = _pseudolabel_run(run, clean_reference)
        all_y.append(y)
        all_oracle.append(run.oracle_active)
    y = np.concatenate(all_y)
    oracle = np.concatenate(all_oracle)
    metrics = pseudolabel_precision_recall(y, oracle)
    print("\n[pseudo-label] precision/recall (train pool, D-026 seeds 500-549 reference):", metrics)
    assert metrics["n_pos_pred"] > 0, "pseudo-labeller never fired a positive on 20 attacked runs"
    assert metrics["precision"] >= 0.5 or np.isnan(metrics["precision"])


def test_d026_2x2_diagnostic_and_frozen_design(train_runs, test_runs, clean_reference):
    """D-026: ONE controlled 2x2 round -- {xsat rule off,on} x {balancing
    off,on} -- all on the seeds-500-549 clean reference. Reports AUC/CI,
    pos/neg counts, and (item 5) the jamming-ACTIVE pseudo-label breakdown
    per cell. The {on,on} cell is ADOPTED as the frozen design regardless of
    its numbers (item 4) -- no assertion bar on AUC below."""
    cells = {}
    for rule_on in (False, True):
        for balance_on in (False, True):
            cells[(rule_on, balance_on)] = _train_and_eval(train_runs, test_runs, clean_reference,
                                                             rule_on, balance_on)

    print("\n[D-026 2x2 diagnostic] PROVISIONAL (synthetic truth-derived innovations)")
    for (rule_on, balance_on), r in cells.items():
        print(f"\n-- rule={'on' if rule_on else 'off'}, balance={'on' if balance_on else 'off'} --")
        print(f"   train pos/neg (pre-balance): {r['train_pos']}/{r['train_neg']}  "
              f"post-balance metrics: {r['train_metrics']}")
        print(f"   jamming-ACTIVE pseudo-labels: {r['jam_active_breakdown']}")
        for fam, (point, ci) in r["auc_per_family"].items():
            print(f"   AUC[{fam}]={point:.3f} CI=[{ci[0]:.3f},{ci[1]:.3f}]")
        op, oc = r["overall_auc"]
        print(f"   AUC[overall]={op:.3f} CI=[{oc[0]:.3f},{oc[1]:.3f}]")

    # Frozen design (item 4): adopt {rule on, balance on} regardless of outcome.
    frozen = cells[(True, True)]
    print("\n[D-026 FROZEN DESIGN] rule=on, balance=on -- adopted regardless of numbers, no further "
          "rule/threshold/feature changes after this round:")
    print(f"   {frozen['auc_per_family']}  overall={frozen['overall_auc']}")
    assert np.isfinite(frozen["overall_auc"][0])  # sanity only -- no pass bar per item 4


def test_train_local_balance_dead_zone_n_neg_0_trains_on_all_samples():
    """D-039: with n_neg=0, the ORIGINAL rule computed max_pos_kept=0 and
    dropped every sample (n=0 survives balancing), so train_local returned
    the n=0 early-exit and NO SGD step ran -- a node could go arbitrarily
    many rounds without training at all. Below n_min=10 negatives, the fix
    trains on everything instead of subsampling. This asserts the SGD loop
    actually runs (a real, non-nan loss; weights change) when n_neg=0."""
    detector = TrustDetector(arch="mlp", seed=0)
    rng = np.random.default_rng(0)
    n = 40
    U = rng.normal(size=(n, 60))
    y_spoof = np.ones(n)   # ALL positive -> n_neg = 0
    y_jam = np.ones(n)
    theta_before = {k: v.copy() for k, v in detector.get_params().items()}
    metrics = detector.train_local(U, y_spoof, y_jam, epochs=1, balance=True, n_min=10)
    assert metrics["n_neg"] == 0.0
    assert metrics["n_pos"] == float(n), "dead-zone fix must train on ALL samples when n_neg=0, not drop them"
    assert np.isfinite(metrics["loss"]), "SGD must actually run (finite loss), not early-exit to nan"
    theta_after = detector.get_params()
    assert not np.allclose(theta_before["fc1.weight"], theta_after["fc1.weight"]), "weights never updated"


def test_train_local_balance_dead_zone_n_neg_3_trains_on_all_samples():
    """D-039: n_neg=3 (< n_min=10) must also skip subsampling and train on
    everything, not cap positives down to ~1 (3*0.5/0.5=3) and discard the
    rest."""
    detector = TrustDetector(arch="mlp", seed=0)
    rng = np.random.default_rng(1)
    n_pos, n_neg = 37, 3
    U = rng.normal(size=(n_pos + n_neg, 60))
    y_spoof = np.concatenate([np.ones(n_pos), np.zeros(n_neg)])
    y_jam = np.zeros(n_pos + n_neg)
    metrics = detector.train_local(U, y_spoof, y_jam, epochs=1, balance=True, n_min=10)
    assert metrics["n_neg"] == float(n_neg)
    assert metrics["n_pos"] == float(n_pos), "n_neg=3 < n_min=10 must train on all positives too, not subsample"
    assert np.isfinite(metrics["loss"])


def test_train_local_balance_at_or_above_n_min_still_subsamples():
    """Sanity: at/above n_min negatives, the original subsampling behaviour
    (down to max_pos_fraction) is unchanged."""
    detector = TrustDetector(arch="mlp", seed=0)
    rng = np.random.default_rng(2)
    n_pos, n_neg = 100, 20   # >= n_min=10 -> subsampling still applies
    U = rng.normal(size=(n_pos + n_neg, 60))
    y_spoof = np.concatenate([np.ones(n_pos), np.zeros(n_neg)])
    y_jam = np.zeros(n_pos + n_neg)
    metrics = detector.train_local(U, y_spoof, y_jam, epochs=1, balance=True,
                                    max_pos_fraction=0.5, n_min=10, rng=np.random.default_rng(3))
    # cap: n_pos_kept <= n_neg * 0.5/0.5 = 20
    assert metrics["n_pos"] <= 20.0 + 1e-9
    assert metrics["n_neg"] == float(n_neg)


def test_class_weight_cap_bounds_update_norm_with_single_negative():
    """D-050: class-weight cap at 10x. A single negative in an otherwise
    all-positive batch (balance=False, so the D-039 subsampling above cannot
    mask this) is the worst case for the uncapped inverse-class-frequency
    weight (n / (2*n_neg) -> huge as n grows for a fixed n_neg=1). The cap
    must keep w_neg <= 10 regardless of how large the batch is, and hence
    keep the resulting parameter-update norm bounded rather than growing
    with n."""
    def update_norm(n: int, seed: int) -> tuple[float, float]:
        detector = TrustDetector(arch="mlp", seed=0)
        rng = np.random.default_rng(seed)
        U = rng.normal(size=(n, 60))
        y_spoof = np.ones(n)
        y_spoof[0] = 0.0  # exactly one negative
        y_jam = np.zeros(n)
        theta_before = {k: v.copy() for k, v in detector.get_params().items() if k.startswith("fc")}
        metrics = detector.train_local(U, y_spoof, y_jam, epochs=1, lr=0.05, batch_size=n,
                                        balance=False, rng=np.random.default_rng(seed))
        theta_after = detector.get_params()
        delta_norm = float(np.sqrt(sum(
            np.sum((theta_after[k] - theta_before[k]) ** 2) for k in theta_before)))
        return delta_norm, metrics["w_neg"]

    delta_100, w_neg_100 = update_norm(100, seed=10)
    delta_5000, w_neg_5000 = update_norm(5000, seed=11)

    assert w_neg_100 <= 10.0 + 1e-9
    assert w_neg_5000 <= 10.0 + 1e-9, f"w_neg must be capped at 10x regardless of batch size, got {w_neg_5000}"
    # Bounded: the update norm at n=5000 must not blow up relative to n=100
    # (uncapped, w_neg would be ~25x larger at n=5000 than at n=100, i.e.
    # n/(2*1) = 50 vs 2500 -- a 50x difference the cap must absorb).
    assert delta_5000 < 5.0 * max(delta_100, 1e-9), (
        f"update norm grew unbounded with batch size (n=100: {delta_100}, n=5000: {delta_5000}), "
        f"class-weight cap not effective")
