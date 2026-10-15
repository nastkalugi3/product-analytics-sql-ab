-- Q4. Delivery SLA: share of delivered orders that arrived after the promised
-- date, by customer state, and average review score on-time vs late.
-- Late = delivery DATE is later than the estimated DATE (estimates have no
-- time of day). The review score is averaged per order first, because some
-- orders have several reviews. Row 'ALL' is the total.

WITH order_review AS (
    SELECT order_id, AVG(review_score) AS review_score
    FROM order_reviews
    GROUP BY order_id
),
delivered AS (
    SELECT
        w.customer_state,
        CASE WHEN CAST(w.delivered_ts AS DATE) > CAST(w.estimated_ts AS DATE)
             THEN 1 ELSE 0 END AS is_late,
        r.review_score
    FROM orders_window AS w
    LEFT JOIN order_review AS r ON r.order_id = w.order_id
    WHERE w.order_status = 'delivered' AND w.delivered_ts IS NOT NULL
),
by_state AS (
    SELECT
        customer_state AS state,
        COUNT(*) AS delivered_orders,
        CAST(SUM(is_late) AS BIGINT) AS late_orders,
        1.0 * SUM(is_late) / COUNT(*) AS late_share,
        AVG(review_score) FILTER (WHERE is_late = 0) AS avg_score_on_time,
        AVG(review_score) FILTER (WHERE is_late = 1) AS avg_score_late
    FROM delivered
    GROUP BY customer_state
),
total AS (
    SELECT
        'ALL' AS state,
        COUNT(*) AS delivered_orders,
        CAST(SUM(is_late) AS BIGINT) AS late_orders,
        1.0 * SUM(is_late) / COUNT(*) AS late_share,
        AVG(review_score) FILTER (WHERE is_late = 0) AS avg_score_on_time,
        AVG(review_score) FILTER (WHERE is_late = 1) AS avg_score_late
    FROM delivered
)
SELECT * FROM by_state
UNION ALL
SELECT * FROM total
ORDER BY late_share DESC, state;
