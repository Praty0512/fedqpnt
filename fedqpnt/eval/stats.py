"""Statistical protocol, ARCHITECTURE.md section 7 (+ D-002 integrity, D-005
seed pairing). EVALUATOR-ONLY: consumes per-seed paired metric arrays
produced by ``fedqpnt.eval.campaign`` / ``fedqpnt.node.runner``; never
imported by the Agent side.

Every function takes/returns plain numpy arrays and Python floats/dicts so
it is testable against scipy/statsmodels or hand-computed textbook values
(see ``tests/test_eval_stats.py``) without touching the simulation stack.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
from scipy import stats as sps

from fedqpnt.core.seeding import stream

# --------------------------------------------------------------------------
# Section 7.1: sample size, n = ceil((z_.975 + z_.8)^2 / d_z^2) + 2
# --------------------------------------------------------------------------
Z_975 = float(sps.norm.ppf(0.975))
Z_80 = float(sps.norm.ppf(0.80))


def required_sample_size(d_z: float, z_alpha: float = Z_975, z_power: float = Z_80) -> int:
    """Section 7.1's pre-registered formula. ``d_z`` is the standardised
    paired effect size (Cohen's d_z) the pilot (seeds 600-609) suggests;
    the +2 is the spec's stated safety margin."""
    if d_z <= 0:
        raise ValueError("d_z must be positive")
    return int(np.ceil((z_alpha + z_power) ** 2 / d_z ** 2)) + 2


# --------------------------------------------------------------------------
# Section 7.2: censored latencies -> set to the censoring value
# --------------------------------------------------------------------------
def censor_latencies(latencies: np.ndarray, censor_value: float, is_miss: np.ndarray | None = None) -> np.ndarray:
    """``is_miss`` marks entries that are misses/censored (e.g. NaN latency
    because detection never happened); if omitted, NaN/inf entries in
    ``latencies`` are treated as censored. Rank-based tests below then see
    the censoring value like any other observation (section 6/7.3)."""
    lat = np.array(latencies, dtype=float, copy=True)
    miss = np.asarray(is_miss, dtype=bool) if is_miss is not None else ~np.isfinite(lat)
    lat[miss] = float(censor_value)
    return lat


# --------------------------------------------------------------------------
# Section 7.3: primary paired test (Wilcoxon signed-rank, two-sided) +
# conditional paired t-test (Shapiro-Wilk on the differences, p > 0.05)
# --------------------------------------------------------------------------
@dataclass
class PairedTestResult:
    n: int
    diff_mean: float
    wilcoxon_stat: float
    wilcoxon_p: float
    shapiro_p: float
    normal_by_shapiro: bool
    t_stat: float | None
    t_p: float | None


def paired_test(x: np.ndarray, y: np.ndarray) -> PairedTestResult:
    """x, y are paired per-seed values for two methods (D-005 pairing).
    Wilcoxon signed-rank (Wilcoxon 1945) is always computed; the paired
    t-test is reported ADDITIONALLY when Shapiro-Wilk on (x - y) gives
    p > 0.05 (section 7.3)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.shape != y.shape:
        raise ValueError("x and y must be paired (same shape)")
    d = x - y
    n = d.size
    if n < 1:
        raise ValueError("need at least one pair")

    nonzero = d[d != 0]
    if nonzero.size == 0:
        w_stat, w_p = 0.0, 1.0
    else:
        w_stat, w_p = sps.wilcoxon(d, zero_method="wilcox", alternative="two-sided", mode="auto")

    if n >= 3 and np.ptp(d) > 0:
        shapiro_stat, shapiro_p = sps.shapiro(d)
    else:
        shapiro_p = 1.0 if np.ptp(d) == 0 else 0.0

    t_stat = t_p = None
    normal = shapiro_p > 0.05
    if normal:
        t_stat, t_p = sps.ttest_rel(x, y)
        t_stat, t_p = float(t_stat), float(t_p)

    return PairedTestResult(n=n, diff_mean=float(np.mean(d)), wilcoxon_stat=float(w_stat),
                             wilcoxon_p=float(w_p), shapiro_p=float(shapiro_p),
                             normal_by_shapiro=bool(normal), t_stat=t_stat, t_p=t_p)


# --------------------------------------------------------------------------
# Section 7.4: effect sizes
# --------------------------------------------------------------------------
def hodges_lehmann(diffs: np.ndarray) -> float:
    """Median of all pairwise Walsh averages (d_i + d_j)/2, i<=j -- the
    Hodges-Lehmann estimator of the paired-difference location, matched to
    the Wilcoxon signed-rank test (textbook definition)."""
    d = np.asarray(diffs, dtype=float)
    n = d.size
    walsh = np.empty(n * (n + 1) // 2)
    idx = 0
    for i in range(n):
        for j in range(i, n):
            walsh[idx] = 0.5 * (d[i] + d[j])
            idx += 1
    return float(np.median(walsh))


def bca_bootstrap_ci(diffs: np.ndarray, master_seed: int = 0, n_resamples: int = 10_000,
                      conf: float = 0.95, statistic=hodges_lehmann) -> tuple[float, float]:
    """95% BCa bootstrap CI for ``statistic`` (default: Hodges-Lehmann
    median of paired differences), RNG from
    ``fedqpnt.core.seeding.stream(master_seed, "eval", "bootstrap")``
    (section 7.4)."""
    d = np.asarray(diffs, dtype=float)
    n = d.size
    theta_hat = statistic(d)
    rng = stream(master_seed, "eval", "bootstrap")
    idx = rng.integers(0, n, size=(n_resamples, n))
    boot = np.array([statistic(d[row]) for row in idx])

    # bias-correction z0
    prop_less = np.mean(boot < theta_hat)
    prop_less = np.clip(prop_less, 1.0 / (n_resamples + 1), 1 - 1.0 / (n_resamples + 1))
    z0 = sps.norm.ppf(prop_less)

    # acceleration a via jackknife
    jack = np.empty(n)
    for i in range(n):
        jack[i] = statistic(np.delete(d, i))
    jack_mean = np.mean(jack)
    num = np.sum((jack_mean - jack) ** 3)
    den = 6.0 * (np.sum((jack_mean - jack) ** 2) ** 1.5)
    a = num / den if den != 0 else 0.0

    alpha = 1 - conf
    z_lo = sps.norm.ppf(alpha / 2)
    z_hi = sps.norm.ppf(1 - alpha / 2)

    def _adj(z):
        return sps.norm.cdf(z0 + (z0 + z) / (1 - a * (z0 + z)))

    lo_pct = np.clip(_adj(z_lo), 0.0, 1.0)
    hi_pct = np.clip(_adj(z_hi), 0.0, 1.0)
    lo = float(np.percentile(boot, 100 * lo_pct))
    hi = float(np.percentile(boot, 100 * hi_pct))
    return (min(lo, hi), max(lo, hi))


def rank_biserial_matched(x: np.ndarray, y: np.ndarray) -> float:
    """Matched-pairs rank-biserial correlation r = (W+ - W-) / (n(n+1)/2)
    (Kerby 2014 simple-difference formula), computed from the same signed
    ranks the Wilcoxon test uses (zero differences dropped)."""
    d = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)
    d = d[d != 0]
    if d.size == 0:
        return 0.0
    ranks = sps.rankdata(np.abs(d))
    w_pos = np.sum(ranks[d > 0])
    w_neg = np.sum(ranks[d < 0])
    n = d.size
    total = n * (n + 1) / 2.0
    return float((w_pos - w_neg) / total)


def cohens_dz(x: np.ndarray, y: np.ndarray) -> float:
    """d_z = mean(diff) / sd(diff), the standardised paired effect size
    used by section 7.1's sample-size formula."""
    d = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)
    sd = np.std(d, ddof=1)
    if sd == 0:
        return 0.0
    return float(np.mean(d) / sd)


# --------------------------------------------------------------------------
# Section 7.5: multiplicity -- Holm-Bonferroni over the confirmatory family
# --------------------------------------------------------------------------
def holm_bonferroni(pvalues: dict[str, float] | list[float], alpha: float = 0.05):
    """Holm (1979) step-down procedure. Returns, in the same container
    shape as the input, (adjusted_p, reject) pairs. ``adjusted_p`` is the
    usual Holm step-up-max-adjusted p-value, monotone non-decreasing."""
    is_dict = isinstance(pvalues, dict)
    keys = list(pvalues.keys()) if is_dict else list(range(len(pvalues)))
    p = np.array([pvalues[k] for k in keys] if is_dict else list(pvalues), dtype=float)
    m = p.size
    order = np.argsort(p)
    adj = np.empty(m)
    running_max = 0.0
    for rank, i in enumerate(order):
        val = (m - rank) * p[i]
        running_max = max(running_max, val)
        adj[i] = min(running_max, 1.0)
    reject = adj < alpha
    out = {keys[i]: (float(adj[i]), bool(reject[i])) for i in range(m)}
    return out if is_dict else [out[i] for i in range(m)]


# --------------------------------------------------------------------------
# Section 7.3: Friedman + Nemenyi (multi-method comparisons)
# --------------------------------------------------------------------------
@dataclass
class FriedmanResult:
    statistic: float
    p_value: float
    k: int
    n: int
    avg_ranks: np.ndarray


def friedman_test(*samples: np.ndarray) -> FriedmanResult:
    """samples: k arrays of length n (n seeds), one per method, paired by
    seed (D-005). Wraps ``scipy.stats.friedmanchisquare`` and also returns
    the average ranks Nemenyi needs."""
    arrs = [np.asarray(s, dtype=float) for s in samples]
    k = len(arrs)
    n = arrs[0].size
    stat, p = sps.friedmanchisquare(*arrs)
    ranks = np.array([sps.rankdata(row) for row in np.column_stack(arrs)])
    avg_ranks = ranks.mean(axis=0)
    return FriedmanResult(statistic=float(stat), p_value=float(p), k=k, n=n, avg_ranks=avg_ranks)


def nemenyi_posthoc(*samples: np.ndarray, alpha: float = 0.05) -> dict[tuple[int, int], dict]:
    """Nemenyi post-hoc test (Demsar 2006): critical difference
    CD = q_alpha * sqrt(k(k+1)/(6n)), q_alpha from the studentized range
    distribution for k groups (infinite df). Returns, for every method
    pair (i, j), the rank difference, CD, and whether it's significant."""
    fr = friedman_test(*samples)
    k, n = fr.k, fr.n
    q_alpha = float(sps.studentized_range.ppf(1 - alpha, k, np.inf)) / np.sqrt(2)
    cd = q_alpha * np.sqrt(k * (k + 1) / (6.0 * n))
    out = {}
    for i, j in combinations(range(k), 2):
        rdiff = abs(fr.avg_ranks[i] - fr.avg_ranks[j])
        out[(i, j)] = dict(rank_diff=float(rdiff), cd=float(cd), significant=bool(rdiff > cd))
    return out


# --------------------------------------------------------------------------
# Section 7.3: exact McNemar (binary paired outcomes, e.g. detected yes/no)
# --------------------------------------------------------------------------
def mcnemar_exact(a_pos: np.ndarray, b_pos: np.ndarray) -> dict:
    """Exact McNemar test on paired binary outcomes (e.g. attack detected
    yes/no per seed for method A vs B). Uses the exact binomial test on the
    discordant pairs, two-sided."""
    a = np.asarray(a_pos, dtype=bool)
    b = np.asarray(b_pos, dtype=bool)
    n01 = int(np.sum((~a) & b))    # A no, B yes
    n10 = int(np.sum(a & (~b)))    # A yes, B no
    n_disc = n01 + n10
    if n_disc == 0:
        p = 1.0
    else:
        k = min(n01, n10)
        p = float(sps.binomtest(k, n_disc, 0.5, alternative="two-sided").pvalue)
    return dict(n01=n01, n10=n10, n_discordant=n_disc, p_value=p)


# --------------------------------------------------------------------------
# Section 6.1: Wilson 95% CI for proportions (acceptance-criteria pass rates)
# --------------------------------------------------------------------------
def wilson_ci(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    z = float(sps.norm.ppf(1 - (1 - conf) / 2))
    phat = k / n
    denom = 1 + z ** 2 / n
    centre = phat + z ** 2 / (2 * n)
    half = z * np.sqrt(phat * (1 - phat) / n + z ** 2 / (4 * n ** 2))
    lo = (centre - half) / denom
    hi = (centre + half) / denom
    return (float(max(0.0, lo)), float(min(1.0, hi)))
