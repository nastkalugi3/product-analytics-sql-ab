-- A/B 4. Segment metrics: quartiles of one pre-chosen feature.
-- Reads the view `criteo_segments` (see pa.data.register_segment), which has
-- the chosen feature as `segment_feature`. Quartile edges are computed once
-- with percentile_cont and applied with <=, so equal values always land in the
-- same quartile (NTILE would split ties arbitrarily).

WITH cuts AS (
    SELECT
        percentile_cont(0.25) WITHIN GROUP (ORDER BY segment_feature) AS q1,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY segment_feature) AS q2,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY segment_feature) AS q3
    FROM criteo_segments
),
seg AS (
    SELECT
        CASE WHEN s.segment_feature <= c.q1 THEN 1
             WHEN s.segment_feature <= c.q2 THEN 2
             WHEN s.segment_feature <= c.q3 THEN 3
             ELSE 4 END AS quartile,
        s.treatment, s.visit, s.conversion, s.exposure
    FROM criteo_segments AS s
    CROSS JOIN cuts AS c
)
SELECT
    quartile,
    treatment,
    COUNT(*) AS n,
    SUM(visit) AS visits,
    SUM(conversion) AS conversions,
    SUM(exposure) AS exposed
FROM seg
GROUP BY quartile, treatment
ORDER BY quartile, treatment;
