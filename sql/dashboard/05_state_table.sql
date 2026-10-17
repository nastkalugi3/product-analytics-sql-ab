-- D5. Customer states (all) ranked by GMV over the whole analysis window.
-- State = customer_state of the order. Same metric definitions as D1.
-- benchmark_* columns hold the all-orders values used for red/green highlighting.

WITH order_review AS (
    SELECT order_id, AVG(review_score) AS review_score
    FROM order_reviews
    GROUP BY order_id
),
order_flags AS (
    SELECT
        s.order_id,
        s.customer_state,
        s.gmv,
        CASE WHEN s.order_status = 'delivered' AND s.delivered_ts IS NOT NULL
             THEN 1 ELSE 0 END AS is_delivered,
        CASE WHEN s.order_status = 'delivered' AND s.delivered_ts IS NOT NULL
              AND CAST(s.delivered_ts AS DATE) > CAST(s.estimated_ts AS DATE)
             THEN 1 ELSE 0 END AS is_late,
        r.review_score
    FROM sales_orders AS s
    LEFT JOIN order_review AS r ON r.order_id = s.order_id
),
per_state AS (
    SELECT
        customer_state AS state,
        SUM(gmv) AS gmv,
        COUNT(*) AS orders,
        1.0 * SUM(is_late) / NULLIF(SUM(is_delivered), 0) AS late_share,
        AVG(review_score) AS avg_review
    FROM order_flags
    GROUP BY customer_state
),
bench AS (
    SELECT 1.0 * SUM(is_late) / SUM(is_delivered) AS benchmark_late_share,
           AVG(review_score) AS benchmark_review
    FROM order_flags
)
SELECT
    ROW_NUMBER() OVER (ORDER BY ps.gmv DESC, ps.state) AS rank,
    ps.state,
    ps.gmv,
    ps.gmv / SUM(ps.gmv) OVER () AS share_of_gmv,
    ps.orders,
    ps.late_share,
    ps.avg_review,
    b.benchmark_late_share,
    b.benchmark_review
FROM per_state AS ps
CROSS JOIN bench AS b
ORDER BY ps.gmv DESC, ps.state;
