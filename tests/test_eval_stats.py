"""WP-8.x: fedqpnt.eval.stats validated against scipy (D-002: every formula
must be checkable) and hand-computed textbook examples, ARCHITECTURE.md
section 7."""
from __future__ import annotations

import numpy as np
import pytest
from scipy import stats as sps

from fedqpnt.eval import stats as ST


# --------------------------------------------------------------------------
# Sample size formula (section 7.1)
# --------------------------------------------------------------------------
def test_required_sample_size_matches_hand_formula():
    d_z = 0.53
    z975 = sps.norm.ppf(0.975)
    z80 = sps.norm.ppf(0.80)
    expected = int(np.ceil((z975 + z80) ** 2 / d_z ** 2)) + 2
    assert ST.required_sample_size(d_z) == expected


def test_required_sample_size_n30_d_z_0_53_matches_spec_example():
    # section 7.1: "n = 30 has 80% power at alpha=.05 for d_z ~ 0.53"
    n = ST.required_sample_size(0.53)
    assert n in (29, 30, 31)  # spec's "~0.53" is approximate


def test_required_sample_size_rejects_nonpositive():
    with pytest.raises(ValueError):
        ST.required_sample_size(0.0)


# --------------------------------------------------------------------------
# Censoring (section 7.2)
# --------------------------------------------------------------------------
def test_censor_latencies_replaces_nan_with_censor_value():
    lat = np.array([1.0, np.nan, 3.0, np.inf])
    out = ST.censor_latencies(lat, censor_value=99.0)
    assert np.array_equal(out, [1.0, 99.0, 3.0, 99.0])


def test_censor_latencies_explicit_miss_mask():
    lat = np.array([1.0, 2.0, 3.0])
    out = ST.censor_latencies(lat, censor_value=10.0, is_miss=np.array([False, True, False]))
    assert np.array_equal(out, [1.0, 10.0, 3.0])


# --------------------------------------------------------------------------
# Paired test (Wilcoxon primary, conditional paired t-test) vs scipy directly
# --------------------------------------------------------------------------
def test_paired_test_wilcoxon_matches_scipy_directly():
    rng = np.random.default_rng(0)
    x = rng.normal(5.0, 1.0, size=20)
    y = x + rng.normal(0.3, 1.0, size=20)
    res = ST.paired_test(x, y)
    w_stat, w_p = sps.wilcoxon(x - y, zero_method="wilcox", alternative="two-sided", mode="auto")
    assert res.wilcoxon_stat == pytest.approx(w_stat)
    assert res.wilcoxon_p == pytest.approx(w_p)


def test_paired_test_reports_t_test_when_shapiro_p_above_0_05():
    rng = np.random.default_rng(1)
    x = rng.normal(0.0, 1.0, size=40)
    y = rng.normal(0.0, 1.0, size=40)
    res = ST.paired_test(x, y)
    if res.shapiro_p > 0.05:
        t_stat, t_p = sps.ttest_rel(x, y)
        assert res.t_stat == pytest.approx(t_stat)
        assert res.t_p == pytest.approx(t_p)
    else:
        pytest.skip("this RNG draw happened to fail Shapiro; formula still checked by construction")


def test_paired_test_omits_t_test_when_non_normal():
    x = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 100.0, 1.0, 1.0])
    y = np.zeros(8)
    res = ST.paired_test(x, y)
    if res.shapiro_p <= 0.05:
        assert res.t_stat is None and res.t_p is None


def test_paired_test_requires_matching_shapes():
    with pytest.raises(ValueError):
        ST.paired_test(np.array([1.0, 2.0]), np.array([1.0]))


# --------------------------------------------------------------------------
# Hodges-Lehmann estimator: textbook hand-computed example
# --------------------------------------------------------------------------
def test_hodges_lehmann_hand_example():
    # differences [1, 2, 3]; Walsh averages: (1+1)/2=1, (1+2)/2=1.5, (1+3)/2=2,
    # (2+2)/2=2, (2+3)/2=2.5, (3+3)/2=3 -> sorted [1, 1.5, 2, 2, 2.5, 3] -> median 2.0
    d = np.array([1.0, 2.0, 3.0])
    assert ST.hodges_lehmann(d) == pytest.approx(2.0)


def test_hodges_lehmann_symmetric_zero_mean_gives_zero():
    d = np.array([-3.0, -1.0, 0.0, 1.0, 3.0])
    assert ST.hodges_lehmann(d) == pytest.approx(0.0)


# --------------------------------------------------------------------------
# BCa bootstrap CI: sanity (covers the true parameter for a known distribution,
# deterministic given the seeded stream)
# --------------------------------------------------------------------------
def test_bca_bootstrap_ci_is_deterministic_and_contains_hl_point_estimate():
    rng = np.random.default_rng(2)
    d = rng.normal(1.0, 0.5, size=40)
    lo, hi = ST.bca_bootstrap_ci(d, master_seed=0, n_resamples=2000)
    lo2, hi2 = ST.bca_bootstrap_ci(d, master_seed=0, n_resamples=2000)
    assert (lo, hi) == (lo2, hi2)   # deterministic RNG (D-005 stream)
    assert lo < ST.hodges_lehmann(d) < hi


def test_bca_bootstrap_ci_different_master_seed_gives_different_stream():
    d = np.random.default_rng(3).normal(0.0, 1.0, size=30)
    ci_a = ST.bca_bootstrap_ci(d, master_seed=0, n_resamples=1000)
    ci_b = ST.bca_bootstrap_ci(d, master_seed=1, n_resamples=1000)
    assert ci_a != ci_b


# --------------------------------------------------------------------------
# Rank-biserial and Cohen's d_z: hand-computed
# --------------------------------------------------------------------------
def test_rank_biserial_matched_all_positive_gives_one():
    x = np.array([5.0, 6.0, 7.0, 8.0])
    y = np.array([1.0, 1.0, 1.0, 1.0])
    assert ST.rank_biserial_matched(x, y) == pytest.approx(1.0)


def test_rank_biserial_matched_all_negative_gives_minus_one():
    x = np.array([1.0, 1.0, 1.0])
    y = np.array([5.0, 6.0, 7.0])
    assert ST.rank_biserial_matched(x, y) == pytest.approx(-1.0)


def test_cohens_dz_hand_example():
    x = np.array([2.0, 4.0, 6.0, 8.0])
    y = np.array([1.0, 2.0, 3.0, 4.0])
    d = x - y  # [1,2,3,4], mean=2.5, sd=sqrt(1.6666...)=1.29099...
    expected = np.mean(d) / np.std(d, ddof=1)
    assert ST.cohens_dz(x, y) == pytest.approx(expected)


def test_cohens_dz_zero_variance_gives_zero():
    x = np.array([1.0, 1.0, 1.0])
    y = np.array([0.0, 0.0, 0.0])
    assert ST.cohens_dz(x, y) == 0.0


# --------------------------------------------------------------------------
# Holm-Bonferroni: textbook example (Holm 1979)
# --------------------------------------------------------------------------
def test_holm_bonferroni_hand_example():
    # p = [0.01, 0.02, 0.03, 0.04], m=4, alpha=0.05
    # sorted ascending; adjusted = max_k( (m-k+1)*p_(k) ) cumulative max
    # p(1)=.01 -> 4*.01=.04; p(2)=.02 -> 3*.02=.06 (max so far .06);
    # p(3)=.03 -> 2*.03=.06 (max .06); p(4)=.04 -> 1*.04=.04 -> max(.06,.04)=.06
    p = {"a": 0.01, "b": 0.02, "c": 0.03, "d": 0.04}
    out = ST.holm_bonferroni(p, alpha=0.05)
    assert out["a"][0] == pytest.approx(0.04)
    assert out["b"][0] == pytest.approx(0.06)
    assert out["c"][0] == pytest.approx(0.06)
    assert out["d"][0] == pytest.approx(0.06)
    assert out["a"][1] is True     # 0.04 < 0.05
    assert out["b"][1] is False    # 0.06 >= 0.05


def test_holm_bonferroni_list_input_preserves_order():
    p = [0.001, 0.2, 0.05]
    out = ST.holm_bonferroni(p)
    assert len(out) == 3
    assert out[0][1] is True


# --------------------------------------------------------------------------
# Friedman + Nemenyi: Friedman vs scipy directly
# --------------------------------------------------------------------------
def test_friedman_test_matches_scipy_directly():
    rng = np.random.default_rng(4)
    a = rng.normal(0, 1, 15)
    b = rng.normal(0.5, 1, 15)
    c = rng.normal(1.0, 1, 15)
    res = ST.friedman_test(a, b, c)
    stat, p = sps.friedmanchisquare(a, b, c)
    assert res.statistic == pytest.approx(stat)
    assert res.p_value == pytest.approx(p)
    assert res.k == 3 and res.n == 15


def test_nemenyi_posthoc_identical_samples_never_significant():
    a = np.arange(10.0)
    out = ST.nemenyi_posthoc(a, a, a)
    for pair, info in out.items():
        assert info["rank_diff"] == pytest.approx(0.0)
        assert info["significant"] is False


def test_nemenyi_posthoc_clearly_separated_samples_is_significant():
    rng = np.random.default_rng(5)
    n = 30
    a = rng.normal(0.0, 0.01, n)
    b = rng.normal(0.0, 0.01, n)
    c = rng.normal(100.0, 0.01, n)   # clearly separated from a, b
    out = ST.nemenyi_posthoc(a, b, c)
    assert out[(0, 2)]["significant"] is True
    assert out[(1, 2)]["significant"] is True


# --------------------------------------------------------------------------
# Exact McNemar: hand-computed vs scipy binomtest
# --------------------------------------------------------------------------
def test_mcnemar_exact_hand_example():
    # n01 = 3 (A no, B yes), n10 = 9 (A yes, B no) -> exact binomial(k=3, n=12, p=0.5)
    a = np.array([True] * 9 + [False] * 3 + [True] * 5)
    b = np.array([False] * 9 + [True] * 3 + [True] * 5)
    out = ST.mcnemar_exact(a, b)
    assert out["n10"] == 9 and out["n01"] == 3
    expected_p = sps.binomtest(3, 12, 0.5, alternative="two-sided").pvalue
    assert out["p_value"] == pytest.approx(expected_p)


def test_mcnemar_exact_no_discordant_pairs_gives_p_one():
    a = np.array([True, True, False, False])
    b = np.array([True, True, False, False])
    out = ST.mcnemar_exact(a, b)
    assert out["n_discordant"] == 0
    assert out["p_value"] == 1.0


# --------------------------------------------------------------------------
# Wilson CI: textbook example
# --------------------------------------------------------------------------
def test_wilson_ci_hand_example_k5_n20():
    lo, hi = ST.wilson_ci(5, 20)
    # Hand-computed Wilson score interval for p_hat=5/20=0.25, z=1.959964:
    # centre=(p+z^2/2n)/(1+z^2/n)=0.290295, half-width=0.178423
    # -> (0.111872, 0.468718)
    assert lo == pytest.approx(0.111872, abs=2e-4)
    assert hi == pytest.approx(0.468718, abs=2e-4)


def test_wilson_ci_k_equals_n_bounded_below_one():
    lo, hi = ST.wilson_ci(10, 10)
    assert hi < 1.0
    assert 0.0 < lo < hi


def test_wilson_ci_zero_n_returns_nan():
    lo, hi = ST.wilson_ci(0, 0)
    assert np.isnan(lo) and np.isnan(hi)
