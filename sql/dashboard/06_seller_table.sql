-- D6. Top 15 sellers by GMV over the whole analysis window: the analogue of a
-- "per-manager" table. An order with items from several sellers counts once for
-- each of them, and its lateness and review are attributed to each of them.
-- benchmark_* columns hold the all-orders values used for red/green highlighting.

WITH order_review AS (
    SELECT order_id, AVG(review_score) AS review_score
    FROM order_reviews
    GROUP BY order_id
),
order_flags AS (
    SELECT
        s.order_id,
        CASE WHEN s.order_status = 'delivered' AND s.delivered_ts IS NOT NULL
             THEN 1 ELSE 0 END AS is_delivered,
        CASE WHEN s.order_status = 'delivered' AND s.delivered_ts IS NOT NULL
              AND CAST(s.delivered_ts AS DATE) > CAST(s.estimated_ts AS DATE)
             THEN 1 ELSE 0 END AS is_late,
        r.review_score
    FROM sales_orders AS s
    LEFT JOIN order_review AS r ON r.order_id = s.order_id
),
order_seller AS (
    SELECT
        i.order_id,
        i.seller_id,
        SUM(i.price + i.freight_value) AS gmv
    FROM order_items AS i
    INNER JOIN order_flags AS f ON f.order_id = i.order_id
    GROUP BY i.order_id, i.seller_id
),
per_seller AS (
    SELECT
        o.seller_id,
        SUM(o.gmv) AS gmv,
        COUNT(*) AS orders,
        1.0 * SUM(f.is_late) / NULLIF(SUM(f.is_delivered), 0) AS late_share,
        AVG(f.review_score) AS avg_review
    FROM order_seller AS o
    INNER JOIN order_flags AS f ON f.order_id = o.order_id
    GROUP BY o.seller_id
),
bench AS (
    SELECT 1.0 * SUM(is_late) / SUM(is_delivered) AS benchmark_late_share,
           AVG(review_score) AS benchmark_review
    FROM order_flags
)
SELECT
    ROW_NUMBER() OVER (ORDER BY ps.gmv DESC, ps.seller_id) AS rank,
    ps.seller_id,
    sl.seller_state,
    ps.gmv,
    ps.gmv / SUM(ps.gmv) OVER () AS share_of_gmv,
    ps.orders,
    ps.late_share,
    ps.avg_review,
    b.benchmark_late_share,
    b.benchmark_review
FROM per_seller AS ps
LEFT JOIN sellers AS sl ON sl.seller_id = ps.seller_id
CROSS JOIN bench AS b
ORDER BY ps.gmv DESC, ps.seller_id
LIMIT 15;
