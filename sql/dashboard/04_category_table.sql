-- D4. Top 15 product categories by GMV over the whole analysis window.
-- GMV is summed over items. An order with items from several categories counts
-- once in each of them (so category orders add up to more than total orders);
-- its lateness and review are then attributed to every such category.
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
order_category AS (
    SELECT
        i.order_id,
        COALESCE(t.product_category_name_english,
                 p.product_category_name, 'unknown') AS category,
        SUM(i.price + i.freight_value) AS gmv
    FROM order_items AS i
    INNER JOIN order_flags AS f ON f.order_id = i.order_id
    LEFT JOIN products AS p ON p.product_id = i.product_id
    LEFT JOIN category_translation AS t
           ON t.product_category_name = p.product_category_name
    GROUP BY
        i.order_id,
        COALESCE(t.product_category_name_english, p.product_category_name, 'unknown')
),
per_category AS (
    SELECT
        c.category,
        SUM(c.gmv) AS gmv,
        COUNT(*) AS orders,
        1.0 * SUM(f.is_late) / NULLIF(SUM(f.is_delivered), 0) AS late_share,
        AVG(f.review_score) AS avg_review
    FROM order_category AS c
    INNER JOIN order_flags AS f ON f.order_id = c.order_id
    GROUP BY c.category
),
bench AS (
    SELECT 1.0 * SUM(is_late) / SUM(is_delivered) AS benchmark_late_share,
           AVG(review_score) AS benchmark_review
    FROM order_flags
)
SELECT
    ROW_NUMBER() OVER (ORDER BY pc.gmv DESC, pc.category) AS rank,
    pc.category,
    pc.gmv,
    pc.gmv / SUM(pc.gmv) OVER () AS share_of_gmv,
    pc.orders,
    pc.late_share,
    pc.avg_review,
    b.benchmark_late_share,
    b.benchmark_review
FROM per_category AS pc
CROSS JOIN bench AS b
ORDER BY pc.gmv DESC, pc.category
LIMIT 15;
