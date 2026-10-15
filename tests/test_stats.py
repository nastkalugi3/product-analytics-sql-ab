import numpy as np
import pytest
from scipy import stats as sps

from pa import stats


def test_srm_balanced_and_skewed():
    ok = stats.srm_check(5000, 5000, 0.5)
    assert ok.chi2 == pytest.approx(0.0)
    assert ok.p_value == pytest.approx(1.0)
    bad = stats.srm_check(6000, 4000, 0.5)
    assert bad.p_value < 1e-6
    assert bad.observed_share == pytest.approx(0.4)


def test_srm_matches_scipy_chisquare():
    r = stats.srm_check(8_400, 91_600, 0.9)
    ref = sps.chisquare([8_400, 91_600], f_exp=[10_000, 90_000])
    assert r.chi2 == pytest.approx(ref.statistic)
    assert r.p_value == pytest.approx(ref.pvalue)


def test_proportion_test_matches_chi2_contingency():
    x_c, n_c, x_t, n_t = 480, 10_000, 560, 12_000
    r = stats.proportion_test(x_c, n_c, x_t, n_t)
    table = [[x_c, n_c - x_c], [x_t, n_t - x_t]]
    chi2, p, _, _ = sps.chi2_contingency(table, correction=False)
    assert r.z**2 == pytest.approx(chi2)
    assert r.p_value == pytest.approx(p)
    assert r.abs_diff == pytest.approx(x_t / n_t - x_c / n_c)
    assert r.ci_low < r.abs_diff < r.ci_high


def test_proportion_test_zero_diff():
    r = stats.proportion_test(100, 1000, 100, 1000)
    assert r.abs_diff == 0
    assert r.p_value == pytest.approx(1.0)


def test_mde_sample_size_round_trip():
    p = 0.047
    for mde_rel in (0.01, 0.02, 0.05):
        n_c, n_t = stats.sample_size_proportion(p, mde_rel, ratio=1.0)
        assert n_c == n_t
        mde = stats.mde_proportion(p, n_c, n_t)
        assert mde == pytest.approx(p * mde_rel, rel=1e-2)


def test_mde_unequal_groups_round_trip():
    n_c, n_t = stats.sample_size_proportion(0.03, 0.05, ratio=5.0)
    assert n_t == pytest.approx(5 * n_c, abs=5)
    assert stats.mde_proportion(0.03, n_c, n_t) == pytest.approx(0.03 * 0.05, rel=1e-2)


def test_sample_size_known_value():
    # classic textbook case: 10% -> 12%, alpha 0.05, power 0.8 -> about 3841 per arm
    n_c, _ = stats.sample_size_proportion(0.10, 0.20)
    assert 3800 < n_c < 3900


def test_holm_hand_example():
    p = [0.01, 0.04, 0.03, 0.005]
    # sorted: 0.005*4=0.02, 0.01*3=0.03, 0.03*2=0.06, 0.04*1=0.04 -> max(0.06)
    adj = stats.holm(p)
    np.testing.assert_allclose(adj, [0.03, 0.06, 0.06, 0.02])


def test_holm_clips_at_one():
    assert stats.holm([0.6, 0.7]).max() == 1.0


def _cells(n, p_visit, p_conv_given_visit, rng):
    visit = rng.random(n) < p_visit
    conv = visit & (rng.random(n) < p_conv_given_visit)
    return np.array(
        [
            np.sum(~visit),
            np.sum(visit & ~conv),
            np.sum(visit & conv),
            0,
        ]
    )


def test_bootstrap_reproducible_and_covers_truth():
    rng = np.random.default_rng(0)
    c = _cells(200_000, 0.047, 0.05, rng)
    t = _cells(200_000, 0.052, 0.05, rng)
    a = stats.bootstrap_cells(c, t, "visit", n_boot=1000, seed=42)
    b = stats.bootstrap_cells(c, t, "visit", n_boot=1000, seed=42)
    assert a == b
    assert a.ci_low <= 0.005 <= a.ci_high
    other = stats.bootstrap_cells(c, t, "visit", n_boot=1000, seed=7)
    assert other.ci_low != a.ci_low


def test_bootstrap_matches_analytic_ci():
    rng = np.random.default_rng(1)
    c = _cells(300_000, 0.05, 0.1, rng)
    t = _cells(300_000, 0.055, 0.1, rng)
    boot = stats.bootstrap_cells(c, t, "visit", n_boot=4000, seed=42)
    ana = stats.proportion_test(
        int(c[1] + c[2]), int(c.sum()), int(t[1] + t[2]), int(t.sum())
    )
    assert boot.ci_low == pytest.approx(ana.ci_low, abs=3e-4)
    assert boot.ci_high == pytest.approx(ana.ci_high, abs=3e-4)


def test_bootstrap_unknown_metric():
    with pytest.raises(ValueError):
        stats.bootstrap_cells([1, 1, 1, 1], [1, 1, 1, 1], "nope")


@pytest.mark.parametrize("rho", [0.3, 0.6])
def test_cuped_unbiased_and_variance_reduction(rho):
    rng = np.random.default_rng(3)
    n = 200_000
    x = rng.normal(5, 2, n)
    noise = rng.normal(0, 1, n)
    y = 10 + rho * (x - 5) / 2 + np.sqrt(1 - rho**2) * noise
    res = stats.cuped(y, x)
    assert res.y_adj.mean() == pytest.approx(y.mean(), abs=1e-9)
    assert res.variance_reduction == pytest.approx(rho**2, abs=0.02)


def test_cuped_perfectly_correlated_covariate():
    rng = np.random.default_rng(4)
    x = rng.normal(size=1000)
    res = stats.cuped(2 * x + 1, x)
    assert res.theta == pytest.approx(2.0)
    assert res.variance_reduction == pytest.approx(1.0)


def test_aa_false_positive_rate_close_to_alpha():
    rng = np.random.default_rng(5)
    y = (rng.random(1_000_000) < 0.05).astype(np.int8)
    fpr = stats.aa_false_positive_rate(y, n_iter=1000, sample_size=50_000, seed=42)
    assert 0.03 <= fpr <= 0.07


def test_cuped_constant_covariate_is_safe():
    y = np.array([1.0, 0.0, 1.0, 0.0])
    res = stats.cuped(y, np.ones(4))
    assert res.theta == 0.0
    assert res.variance_reduction == 0.0
    np.testing.assert_array_equal(res.y_adj, y)


def test_aa_small_sample_is_clamped_and_tiny_raises():
    y = (np.random.default_rng(8).random(1000) < 0.1).astype(np.int8)
    assert 0.0 <= stats.aa_false_positive_rate(y, n_iter=20, sample_size=10**6) <= 1.0
    with pytest.raises(ValueError):
        stats.aa_false_positive_rate(y[:1], n_iter=2)


def test_cace_is_itt_over_exposure():
    assert stats.cace(0.002, 0.03) == pytest.approx(0.002 / 0.03)
    assert stats.cace(0.002, 0.5, 0.1) == pytest.approx(0.005)


def test_smd():
    assert stats.smd(1.0, 1.0, 2.0, 2.0) == 0.0
    assert stats.smd(0.0, 1.0, 1.0, 1.0) == pytest.approx(1.0)


def test_mean_diff_test_detects_shift():
    rng = np.random.default_rng(6)
    a = rng.normal(0, 1, 50_000)
    b = rng.normal(0.1, 1, 50_000)
    r = stats.mean_diff_test(a, b)
    assert r.p_value < 1e-6
    assert r.ci_low < 0.1 < r.ci_high


def test_poststratified_hand_value():
    n_c, n_t = np.array([100, 300]), np.array([400, 1200])
    x_c, x_t = np.array([10, 60]), np.array([60, 300])
    r = stats.poststratified_diff(n_c, x_c, n_t, x_t)
    naive = x_t.sum() / n_t.sum() - x_c.sum() / n_c.sum()
    assert r.coverage == 1.0 and r.n_strata_used == 2
    # hand value: w = (500, 1500)/2000, diffs 0.15-0.10 and 0.25-0.20
    assert r.abs_diff == pytest.approx(0.25 * 0.05 + 0.75 * 0.05)
    # constant treatment share per stratum: the naive difference agrees
    assert naive == pytest.approx(r.abs_diff)


def test_poststratified_drops_strata_and_reports_coverage():
    r = stats.poststratified_diff([100, 0, 50], [5, 0, 5], [100, 80, 0], [10, 8, 0])
    assert r.n_strata_used == 1 and r.n_strata_total == 3
    assert r.coverage == pytest.approx(200 / 330)
    assert r.abs_diff == pytest.approx(0.05)


def test_poststratified_removes_confounding():
    rng = np.random.default_rng(11)
    n = 400_000
    stratum = rng.integers(0, 2, n)
    # treatment is more likely in the high-rate stratum: naive diff is biased up
    t = rng.random(n) < np.where(stratum == 1, 0.9, 0.5)
    y = rng.random(n) < (0.02 + 0.10 * stratum + 0.01 * t)
    cells = [
        (
            int(((stratum == s) & ~t).sum()),
            int(y[(stratum == s) & ~t].sum()),
            int(((stratum == s) & t).sum()),
            int(y[(stratum == s) & t].sum()),
        )
        for s in (0, 1)
    ]
    n_c, x_c, n_t, x_t = (np.array(v) for v in zip(*cells, strict=True))
    naive = x_t.sum() / n_t.sum() - x_c.sum() / n_c.sum()
    adj = stats.poststratified_diff(n_c, x_c, n_t, x_t)
    assert naive > 0.03
    assert adj.ci_low < 0.01 < adj.ci_high


def test_mantel_haenszel_hand_example_and_crude():
    # one stratum: MH equals the crude odds ratio
    r = stats.mantel_haenszel_or([100], [10], [100], [20])
    assert r == pytest.approx(stats.crude_odds_ratio(100, 10, 100, 20))
    assert r == pytest.approx((20 / 80) / (10 / 90))
    # two identical strata: same common odds ratio
    r2 = stats.mantel_haenszel_or([100, 100], [10, 10], [100, 100], [20, 20])
    assert r2 == pytest.approx(r)


def test_ols_effect_matches_lstsq():
    rng = np.random.default_rng(12)
    n = 50_000
    X = rng.normal(size=(n, 3))
    t = (rng.random(n) < 0.7).astype(np.float64)
    y = 1 + 0.5 * t + X @ np.array([0.3, -0.2, 0.1]) + rng.normal(size=n)
    beta, se = stats.ols_effect(y, t, X, chunk=7_000)
    Z = np.column_stack([np.ones(n), t, X])
    ref = np.linalg.lstsq(Z, y, rcond=None)[0]
    assert beta == pytest.approx(ref[1])
    assert beta - 4 * se < 0.5 < beta + 4 * se
    assert 0 < se < 0.02


def test_cramers_v_and_format_p():
    assert stats.cramers_v(0.0, 1000, 2, 5) == 0.0
    assert stats.cramers_v(10.0, 1000, 2, 5) == pytest.approx(0.1)
    assert stats.format_p(0.0) == "< 1e-300"
    assert stats.format_p(0.01234) == "0.0123"
