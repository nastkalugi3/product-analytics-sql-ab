-- Q5. Top-3 product categories by revenue (items price) in every quarter.
-- English names via the translation table; missing names become 'unknown'.

WITH cat_revenue AS (
    SELECT
        date_trunc('quarter', s.purchase_ts) AS quarter,
        COALESCE(t.product_category_name_english,
                 p.product_category_name, 'unknown') AS category,
        SUM(i.price) AS revenue,
        COUNT(DISTINCT s.order_id) AS orders
    FROM sales_orders AS s
    INNER JOIN order_items AS i ON i.order_id = s.order_id
    LEFT JOIN products AS p ON p.product_id = i.product_id
    LEFT JOIN category_translation AS t
           ON t.product_category_name = p.product_category_name
    GROUP BY
        date_trunc('quarter', s.purchase_ts),
        COALESCE(t.product_category_name_english, p.product_category_name, 'unknown')
),
ranked AS (
    SELECT
        quarter, category, revenue, orders,
        ROW_NUMBER() OVER (
            PARTITION BY quarter ORDER BY revenue DESC, category
        ) AS rank_in_quarter,
        revenue / SUM(revenue) OVER (PARTITION BY quarter) AS share_of_quarter
    FROM cat_revenue
)
SELECT quarter, rank_in_quarter, category, revenue, orders, share_of_quarter
FROM ranked
WHERE rank_in_quarter <= 3
ORDER BY quarter, rank_in_quarter;
