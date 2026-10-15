-- A/B 3. Covariate balance for the CONTINUOUS features f0, f2, f7, f10:
-- count, mean and standard deviation per group. The notebook turns them into
-- standardised mean differences with a z statistic.
-- (f1, f3, f4, f5, f6, f8, f9, f11 are hashed categorical features, so means
-- mean nothing for them; see 05_strata_counts.sql.)

SELECT
    treatment,
    COUNT(*) AS n,
    AVG(f0) AS f0_mean,
    STDDEV_SAMP(f0) AS f0_sd,
    AVG(f2) AS f2_mean,
    STDDEV_SAMP(f2) AS f2_sd,
    AVG(f7) AS f7_mean,
    STDDEV_SAMP(f7) AS f7_sd,
    AVG(f10) AS f10_mean,
    STDDEV_SAMP(f10) AS f10_sd
FROM criteo
GROUP BY treatment
ORDER BY treatment;
