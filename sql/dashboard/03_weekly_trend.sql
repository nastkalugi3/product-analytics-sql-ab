-- D3. Weekly orders and GMV (weeks start on Monday, by purchase date).
-- is_complete_week = 1 only for weeks that start on or after the first order day
-- and end on or before the last day of the last complete month (the same rule as
-- in D1: the data thins out at its very end, so later weeks are not comparable).
-- The dashboard draws only complete weeks.

WITH daily AS (
    SELECT
        date_trunc('month', purchase_ts) AS month_start,
        CAST(purchase_ts AS DATE) AS d,
        COUNT(*) AS n
    FROM orders_window
    GROUP BY date_trunc('month', purchase_ts), CAST(purchase_ts AS DATE)
),
month_stats AS (
    SELECT
        month_start,
        SUM(n) AS month_orders,
        SUM(CASE WHEN d >= CAST(month_start + INTERVAL '1 month' AS DATE) - 7
                 THEN n ELSE 0 END) AS tail_orders,
        CAST(month_start + INTERVAL '1 month' AS DATE)
            - CAST(month_start AS DATE) AS days_in_month
    FROM daily
    GROUP BY month_start
),
edges AS (
    SELECT
        (SELECT MIN(d) FROM daily) AS first_day,
        CAST(MAX(month_start) + INTERVAL '1 month' AS DATE) - 1 AS last_day
    FROM month_stats
    WHERE tail_orders / 7.0 >= 0.5 * month_orders / days_in_month
),
weekly AS (
    SELECT
        date_trunc('week', purchase_ts) AS week_start,
        COUNT(*) AS orders,
        SUM(gmv) AS gmv
    FROM sales_orders
    GROUP BY date_trunc('week', purchase_ts)
)
SELECT
    w.week_start,
    w.orders,
    w.gmv,
    w.gmv / w.orders AS aov,
    CASE WHEN CAST(w.week_start AS DATE) >= e.first_day
          AND CAST(w.week_start AS DATE) + 6 <= e.last_day
         THEN 1 ELSE 0 END AS is_complete_week
FROM weekly AS w
CROSS JOIN edges AS e
ORDER BY w.week_start;
