-- A/B 5. Counts per (categorical feature, category, group): users, visits and
-- conversions. Used for chi-square tests of treatment x category and for
-- post-stratified estimates. f1, f3, f4, f5, f6, f8, f9, f11 are hashed
-- categorical features (Diemert et al., arXiv:2111.10106, Table 2).

SELECT 'f1' AS feature, f1 AS category, treatment,
       COUNT(*) AS n, SUM(visit) AS visits, SUM(conversion) AS conversions
FROM criteo
GROUP BY f1, treatment
UNION ALL
SELECT 'f3' AS feature, f3 AS category, treatment,
       COUNT(*) AS n, SUM(visit) AS visits, SUM(conversion) AS conversions
FROM criteo
GROUP BY f3, treatment
UNION ALL
SELECT 'f4' AS feature, f4 AS category, treatment,
       COUNT(*) AS n, SUM(visit) AS visits, SUM(conversion) AS conversions
FROM criteo
GROUP BY f4, treatment
UNION ALL
SELECT 'f5' AS feature, f5 AS category, treatment,
       COUNT(*) AS n, SUM(visit) AS visits, SUM(conversion) AS conversions
FROM criteo
GROUP BY f5, treatment
UNION ALL
SELECT 'f6' AS feature, f6 AS category, treatment,
       COUNT(*) AS n, SUM(visit) AS visits, SUM(conversion) AS conversions
FROM criteo
GROUP BY f6, treatment
UNION ALL
SELECT 'f8' AS feature, f8 AS category, treatment,
       COUNT(*) AS n, SUM(visit) AS visits, SUM(conversion) AS conversions
FROM criteo
GROUP BY f8, treatment
UNION ALL
SELECT 'f9' AS feature, f9 AS category, treatment,
       COUNT(*) AS n, SUM(visit) AS visits, SUM(conversion) AS conversions
FROM criteo
GROUP BY f9, treatment
UNION ALL
SELECT 'f11' AS feature, f11 AS category, treatment,
       COUNT(*) AS n, SUM(visit) AS visits, SUM(conversion) AS conversions
FROM criteo
GROUP BY f11, treatment
ORDER BY feature, category, treatment;
