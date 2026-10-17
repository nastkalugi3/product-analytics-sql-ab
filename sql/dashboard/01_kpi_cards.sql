-- D1. KPI cards: the last complete month vs the previous month and vs the same
-- month a year earlier. One row per period.
-- "Complete month": the latest month whose last 7 days still have at least half
-- of that month's average daily order count. The data thins out at its end
-- (daily orders fall from about 250 to under 15 in the last days of 2018-08),
-- so the last calendar month of the window is not comparable and is skipped.
-- GMV = items price + freight of sales orders (canceled/unavailable excluded).
-- Late % = delivered orders whose delivery DATE is after the estimated DATE.
-- Review = mean of per-order mean scores (some orders have several reviews).
-- Orders belong to the month of purchase. Orders still on their way at the end
-- of the data are not counted as late yet, so the latest late % can be understated.

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
bounds AS (
    SELECT MAX(month_start) AS cur_month
    FROM month_stats
    WHERE tail_orders / 7.0 >= 0.5 * month_orders / days_in_month
),
periods AS (
    SELECT 1 AS sort_key, 'current' AS period, cur_month AS month_start
    FROM bounds
    UNION ALL
    SELECT 2, 'previous_month', cur_month - INTERVAL '1 month' FROM bounds
    UNION ALL
    SELECT 3, 'same_month_last_year', cur_month - INTERVAL '1 year' FROM bounds
),
order_review AS (
    SELECT order_id, AVG(review_score) AS review_score
    FROM order_reviews
    GROUP BY order_id
),
orders_m AS (
    SELECT
        date_trunc('month', s.purchase_ts) AS month_start,
        s.order_id,
        s.gmv,
        CASE WHEN s.order_status = 'delivered' AND s.delivered_ts IS NOT NULL
             THEN 1 ELSE 0 END AS is_delivered,
        CASE WHEN s.order_status = 'delivered' AND s.delivered_ts IS NOT NULL
              AND CAST(s.delivered_ts AS DATE) > CAST(s.estimated_ts AS DATE)
             THEN 1 ELSE 0 END AS is_late,
        r.review_score
    FROM sales_orders AS s
    LEFT JOIN order_review AS r ON r.order_id = s.order_id
)
SELECT
    p.period,
    p.month_start,
    COUNT(m.order_id) AS orders,
    SUM(m.gmv) AS gmv,
    SUM(m.gmv) / NULLIF(COUNT(m.order_id), 0) AS aov,
    CAST(SUM(m.is_delivered) AS BIGINT) AS delivered_orders,
    1.0 * SUM(m.is_late) / NULLIF(SUM(m.is_delivered), 0) AS late_share,
    AVG(m.review_score) AS avg_review
FROM periods AS p
LEFT JOIN orders_m AS m ON m.month_start = p.month_start
GROUP BY p.sort_key, p.period, p.month_start
ORDER BY p.sort_key;
