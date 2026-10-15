-- A/B 1. Group sizes and treatment share (input for the SRM check).
-- Reads the view `criteo` (one row per user).

SELECT
    treatment,
    COUNT(*) AS n,
    1.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS share
FROM criteo
GROUP BY treatment
ORDER BY treatment;
