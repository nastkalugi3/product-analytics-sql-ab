"""Statistics for the A/B test: pure functions, no statsmodels.

Conventions:
- two-sided tests, alpha = 0.05 by default;
- "control" and "treatment" follow Criteo: treatment = 1 means ads were allowed;
- all differences are treatment minus control.
"""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy import optimize, stats


@dataclass(frozen=True)
class SRMResult:
    chi2: float
    p_value: float
    observed_share: float
    expected_share: float


@dataclass(frozen=True)
class TestResult:
    __test__ = False  # not a pytest class

    mean_control: float
    mean_treatment: float
    abs_diff: float
    rel_diff: float
    ci_low: float
    ci_high: float
    z: float
    p_value: float


@dataclass(frozen=True)
class BootResult:
    diff: float
    ci_low: float
    ci_high: float
    se: float
    n_boot: int


@dataclass(frozen=True)
class CupedResult:
    y_adj: np.ndarray
    theta: float
    variance_reduction: float


def srm_check(
    n_control: int, n_treatment: int, expected_treatment_share: float
) -> SRMResult:
    """Sample ratio mismatch: chi-square goodness of fit against the design split."""
    n = n_control + n_treatment
    exp_t = n * expected_treatment_share
    exp_c = n * (1.0 - expected_treatment_share)
    chi2 = (n_treatment - exp_t) ** 2 / exp_t + (n_control - exp_c) ** 2 / exp_c
    return SRMResult(
        chi2=float(chi2),
        p_value=float(stats.chi2.sf(chi2, df=1)),
        observed_share=n_treatment / n,
        expected_share=expected_treatment_share,
    )


def proportion_test(
    x_c: int, n_c: int, x_t: int, n_t: int, alpha: float = 0.05
) -> TestResult:
    """Two-proportion z-test.

    The p-value uses the pooled standard error (null hypothesis: equal rates),
    so z squared equals Pearson chi-square without continuity correction.
    The confidence interval uses the unpooled standard error.
    """
    p_c, p_t = x_c / n_c, x_t / n_t
    diff = p_t - p_c
    pooled = (x_c + x_t) / (n_c + n_t)
    se_pooled = np.sqrt(pooled * (1 - pooled) * (1 / n_c + 1 / n_t))
    se_unpooled = np.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    z = diff / se_pooled if se_pooled > 0 else 0.0
    zcrit = stats.norm.ppf(1 - alpha / 2)
    return TestResult(
        mean_control=p_c,
        mean_treatment=p_t,
        abs_diff=diff,
        rel_diff=diff / p_c if p_c > 0 else float("nan"),
        ci_low=diff - zcrit * se_unpooled,
        ci_high=diff + zcrit * se_unpooled,
        z=float(z),
        p_value=float(2 * stats.norm.sf(abs(z))),
    )


def mean_diff_test(y_c, y_t, alpha: float = 0.05) -> TestResult:
    """Welch z-test for a difference in means (large samples, e.g. CUPED outcome)."""
    y_c = np.asarray(y_c, dtype=np.float64)
    y_t = np.asarray(y_t, dtype=np.float64)
    m_c, m_t = y_c.mean(), y_t.mean()
    se = np.sqrt(y_c.var(ddof=1) / len(y_c) + y_t.var(ddof=1) / len(y_t))
    diff = m_t - m_c
    z = diff / se
    zcrit = stats.norm.ppf(1 - alpha / 2)
    return TestResult(
        mean_control=float(m_c),
        mean_treatment=float(m_t),
        abs_diff=float(diff),
        rel_diff=float(diff / m_c) if m_c != 0 else float("nan"),
        ci_low=float(diff - zcrit * se),
        ci_high=float(diff + zcrit * se),
        z=float(z),
        p_value=float(2 * stats.norm.sf(abs(z))),
    )


def _n_control(p1: float, p2: float, alpha: float, power: float, ratio: float) -> float:
    """Control-group size (unrounded) to detect p1 -> p2; ratio = n_t / n_c."""
    za = stats.norm.ppf(1 - alpha / 2)
    zb = stats.norm.ppf(power)
    pbar = (p1 + ratio * p2) / (1 + ratio)
    term_null = za * np.sqrt(pbar * (1 - pbar) * (1 + 1 / ratio))
    term_alt = zb * np.sqrt(p1 * (1 - p1) + p2 * (1 - p2) / ratio)
    return float((term_null + term_alt) ** 2 / (p2 - p1) ** 2)


def sample_size_proportion(
    p_base: float,
    mde_rel: float,
    alpha: float = 0.05,
    power: float = 0.8,
    ratio: float = 1.0,
) -> tuple[int, int]:
    """Users needed (control, treatment) to detect a relative lift `mde_rel`.

    ratio = n_treatment / n_control. Sizes are rounded up.
    """
    p2 = p_base * (1 + mde_rel)
    n_c = _n_control(p_base, p2, alpha, power, ratio)
    return int(np.ceil(n_c)), int(np.ceil(n_c * ratio))


def mde_proportion(
    p_base: float,
    n_c: int,
    n_t: int,
    alpha: float = 0.05,
    power: float = 0.8,
) -> float:
    """Smallest absolute lift detectable with the given group sizes.

    Solves the same formula as sample_size_proportion for the lift, so the two
    functions are exact inverses (up to rounding of n).
    """
    ratio = n_t / n_c

    def gap(delta: float) -> float:
        return _n_control(p_base, p_base + delta, alpha, power, ratio) - n_c

    upper = (1 - p_base) * 0.999999
    return float(optimize.brentq(gap, 1e-12, upper, xtol=1e-14, rtol=1e-12))


def _cell_metric(name: str) -> Callable[[np.ndarray], np.ndarray]:
    # cell order: (visit 0, conv 0), (visit 1, conv 0), (visit 1, conv 1),
    # (visit 0, conv 1)
    if name == "visit":
        return lambda c: (c[..., 1] + c[..., 2]) / c.sum(axis=-1)
    if name == "conversion":
        return lambda c: (c[..., 2] + c[..., 3]) / c.sum(axis=-1)
    if name == "conversion_given_visit":
        return lambda c: c[..., 2] / (c[..., 1] + c[..., 2])
    raise ValueError(f"unknown metric {name!r}")


def bootstrap_cells(
    cells_c,
    cells_t,
    metric: str | Callable[[np.ndarray], np.ndarray],
    n_boot: int = 2000,
    seed: int = 42,
    alpha: float = 0.05,
) -> BootResult:
    """Percentile bootstrap CI for (treatment - control) from cell counts.

    Cells are the counts of (visit0 conv0, visit1 conv0, visit1 conv1,
    visit0 conv1). One bootstrap draw is a multinomial sample of n users with
    the observed cell probabilities, which is equivalent to resampling users
    but takes milliseconds on 14M rows. `metric` is a name ("visit",
    "conversion", "conversion_given_visit") or a function from an array of
    cell counts (..., 4) to metric values.
    """
    f = _cell_metric(metric) if isinstance(metric, str) else metric
    cells_c = np.asarray(cells_c, dtype=np.int64)
    cells_t = np.asarray(cells_t, dtype=np.int64)
    rng = np.random.default_rng(seed)
    draws_c = rng.multinomial(cells_c.sum(), cells_c / cells_c.sum(), size=n_boot)
    draws_t = rng.multinomial(cells_t.sum(), cells_t / cells_t.sum(), size=n_boot)
    diffs = f(draws_t.astype(np.float64)) - f(draws_c.astype(np.float64))
    lo, hi = np.quantile(diffs, [alpha / 2, 1 - alpha / 2])
    point = float(f(cells_t.astype(np.float64)) - f(cells_c.astype(np.float64)))
    return BootResult(
        diff=point,
        ci_low=float(lo),
        ci_high=float(hi),
        se=float(diffs.std(ddof=1)),
        n_boot=n_boot,
    )


def cuped(y, x) -> CupedResult:
    """CUPED adjustment: y_adj = y - theta * (x - mean(x)).

    theta = cov(x, y) / var(x), estimated on all users pooled. x must be a
    pre-treatment covariate. The mean of y_adj equals the mean of y, so the
    estimate stays unbiased, while the variance shrinks by about corr(x, y)^2.
    """
    y = np.asarray(y, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    xc = x - x.mean()
    denom = float(np.dot(xc, xc))
    if denom == 0.0:  # constant covariate: nothing to adjust with
        return CupedResult(y_adj=y.copy(), theta=0.0, variance_reduction=0.0)
    theta = float(np.dot(xc, y - y.mean()) / denom)
    y_adj = y - theta * xc
    reduction = 1.0 - float(y_adj.var() / y.var())
    return CupedResult(y_adj=y_adj, theta=theta, variance_reduction=reduction)


def aa_false_positive_rate(
    y,
    n_iter: int = 1000,
    sample_size: int = 200_000,
    seed: int = 42,
    alpha: float = 0.05,
) -> float:
    """Share of A/A splits of a binary outcome that look 'significant'.

    Each iteration draws `sample_size` users without replacement from y, splits
    them into two random halves and runs the pooled two-proportion z-test.
    If y is smaller than `sample_size`, all of y is used.
    A healthy test gives a value close to alpha.
    """
    y = np.asarray(y)
    sample_size = min(sample_size, len(y))
    if sample_size < 2:
        raise ValueError("need at least 2 observations for an A/A split")
    rng = np.random.default_rng(seed)
    half = sample_size // 2
    zcrit = stats.norm.ppf(1 - alpha / 2)
    rejections = 0
    for _ in range(n_iter):
        idx = rng.choice(len(y), size=2 * half, replace=False)
        x1 = int(y[idx[:half]].sum())
        x2 = int(y[idx[half:]].sum())
        pooled = (x1 + x2) / (2 * half)
        se = np.sqrt(pooled * (1 - pooled) * 2 / half)
        if se > 0 and abs((x2 - x1) / half / se) > zcrit:
            rejections += 1
    return rejections / n_iter


def holm(p_values) -> np.ndarray:
    """Holm-Bonferroni adjusted p-values, in the original order."""
    p = np.asarray(p_values, dtype=np.float64)
    m = len(p)
    order = np.argsort(p)
    adjusted = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adjusted[idx] = min(1.0, running)
    return adjusted


def cace(itt_abs: float, exposure_rate_t: float, exposure_rate_c: float = 0.0) -> float:
    """Complier average causal effect = ITT / difference in exposure rates.

    Valid when the control group cannot be exposed (one-sided non-compliance)
    and treatment only works through exposure (exclusion restriction).
    """
    return itt_abs / (exposure_rate_t - exposure_rate_c)


def smd(mean_c: float, mean_t: float, sd_c: float, sd_t: float) -> float:
    """Standardised mean difference with the pooled (root mean square) sd."""
    return (mean_t - mean_c) / np.sqrt((sd_c**2 + sd_t**2) / 2)


@dataclass(frozen=True)
class StratifiedResult:
    abs_diff: float
    se: float
    ci_low: float
    ci_high: float
    coverage: float  # share of all users that sit in strata with both groups
    n_strata_used: int
    n_strata_total: int


def poststratified_diff(n_c, x_c, n_t, x_t, alpha: float = 0.05) -> StratifiedResult:
    """Post-stratified difference in proportions (treatment minus control).

    Inputs are per-stratum arrays: users and events in control and treatment.
    Strata without users in one of the groups are dropped; `coverage` reports
    which share of all users remains. Weights are the stratum sizes, so the
    target is the effect on the population that sits in the kept strata.
    """
    n_c, x_c, n_t, x_t = (np.asarray(a, dtype=np.float64) for a in (n_c, x_c, n_t, x_t))
    total = float((n_c + n_t).sum())
    keep = (n_c > 0) & (n_t > 0)
    n_c, x_c, n_t, x_t = n_c[keep], x_c[keep], n_t[keep], x_t[keep]
    w = (n_c + n_t) / (n_c + n_t).sum()
    p_c, p_t = x_c / n_c, x_t / n_t
    diff = float(np.sum(w * (p_t - p_c)))
    var = p_t * (1 - p_t) / n_t + p_c * (1 - p_c) / n_c
    se = float(np.sqrt(np.sum(w**2 * var)))
    zcrit = stats.norm.ppf(1 - alpha / 2)
    return StratifiedResult(
        abs_diff=diff,
        se=se,
        ci_low=diff - zcrit * se,
        ci_high=diff + zcrit * se,
        coverage=float((n_c + n_t).sum() / total),
        n_strata_used=int(keep.sum()),
        n_strata_total=int(len(keep)),
    )


def crude_odds_ratio(n_c: float, x_c: float, n_t: float, x_t: float) -> float:
    """Odds ratio of the event, treatment vs control, ignoring strata."""
    return (x_t / (n_t - x_t)) / (x_c / (n_c - x_c))


def mantel_haenszel_or(n_c, x_c, n_t, x_t) -> float:
    """Mantel-Haenszel common odds ratio over strata (treatment vs control)."""
    n_c, x_c, n_t, x_t = (np.asarray(a, dtype=np.float64) for a in (n_c, x_c, n_t, x_t))
    n = n_c + n_t
    keep = (n_c > 0) & (n_t > 0)
    a, b = x_t[keep], (n_t - x_t)[keep]
    c, d = x_c[keep], (n_c - x_c)[keep]
    return float(np.sum(a * d / n[keep]) / np.sum(b * c / n[keep]))


def ols_effect(y, t, X, chunk: int = 1_000_000) -> tuple[float, float]:
    """Treatment coefficient and HC0 robust standard error of y ~ 1 + t + X.

    Works in two passes over chunks, so 14M rows never need a float64 copy.
    """
    n = len(y)
    k = 2 + X.shape[1]
    xtx = np.zeros((k, k))
    xty = np.zeros(k)

    def design(sl):
        z = np.empty((sl.stop - sl.start, k))
        z[:, 0] = 1.0
        z[:, 1] = t[sl]
        z[:, 2:] = X[sl]
        return z

    spans = [slice(i, min(i + chunk, n)) for i in range(0, n, chunk)]
    for sl in spans:
        z = design(sl)
        xtx += z.T @ z
        xty += z.T @ np.asarray(y[sl], dtype=np.float64)
    beta = np.linalg.solve(xtx, xty)
    meat = np.zeros((k, k))
    for sl in spans:
        z = design(sl)
        e = np.asarray(y[sl], dtype=np.float64) - z @ beta
        meat += (z * (e**2)[:, None]).T @ z
    inv = np.linalg.inv(xtx)
    cov = inv @ meat @ inv
    return float(beta[1]), float(np.sqrt(cov[1, 1]))


def cramers_v(chi2: float, n: float, n_rows: int, n_cols: int) -> float:
    """Cramer's V effect size for a chi-square test of independence."""
    return float(np.sqrt(chi2 / (n * (min(n_rows, n_cols) - 1))))


def format_p(p: float, floor: float = 1e-300) -> str:
    """Format a p-value; values at or below the float floor print as '< 1e-300'."""
    return f"< {floor:.0e}" if p <= floor else f"{p:.3g}"
