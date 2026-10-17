-- D7. Monthly series for the KPI sparklines: the same metric definitions as D1,
-- one row per month of the analysis window. The dashboard takes the 12 months
-- that end with the card month. Late orders are included so that a pooled
-- late share over several months can be computed exactly.

WITH order_review AS (
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
    month_start,
    COUNT(order_id) AS orders,
    SUM(gmv) AS gmv,
    SUM(gmv) / COUNT(order_id) AS aov,
    CAST(SUM(is_delivered) AS BIGINT) AS delivered_orders,
    CAST(SUM(is_late) AS BIGINT) AS late_orders,
    1.0 * SUM(is_late) / NULLIF(SUM(is_delivered), 0) AS late_share,
    AVG(review_score) AS avg_review
FROM orders_m
GROUP BY month_start
ORDER BY month_start;
