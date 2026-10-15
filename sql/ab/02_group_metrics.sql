-- A/B 2. Per group: users, sums of visit / conversion / exposure, and the four
-- visit x conversion cells (the bootstrap resamples these cells).

SELECT
    treatment,
    COUNT(*) AS n,
    SUM(visit) AS visits,
    SUM(conversion) AS conversions,
    SUM(exposure) AS exposed,
    COUNT(*) FILTER (WHERE visit = 0 AND conversion = 0) AS n_v0_c0,
    COUNT(*) FILTER (WHERE visit = 1 AND conversion = 0) AS n_v1_c0,
    COUNT(*) FILTER (WHERE visit = 1 AND conversion = 1) AS n_v1_c1,
    COUNT(*) FILTER (WHERE visit = 0 AND conversion = 1) AS n_v0_c1
FROM criteo
GROUP BY treatment
ORDER BY treatment;
