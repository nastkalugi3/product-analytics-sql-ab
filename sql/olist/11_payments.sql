-- Q11. Payments: payment types, installments and multi-method orders.
-- Output: dimension, bucket, orders, avg_order_value, share_of_orders.
-- avg_order_value = average total payment value of the orders in the bucket.
-- An order paid with two types appears in both type rows.

WITH order_pay AS (
    SELECT
        p.order_id,
        SUM(p.payment_value) AS total_paid,
        MAX(p.payment_installments) AS max_installments,
        COUNT(DISTINCT p.payment_type) AS n_types
    FROM order_payments AS p
    INNER JOIN sales_orders AS s ON s.order_id = p.order_id
    GROUP BY p.order_id
),
n_all AS (SELECT COUNT(*) AS n FROM order_pay),
pay_types AS (
    -- one row per (order, type): an order with two voucher payments must
    -- count once in its type row
    SELECT DISTINCT order_id, payment_type FROM order_payments
),
by_type AS (
    SELECT
        'payment_type' AS dimension,
        t.payment_type AS bucket,
        COUNT(*) AS orders,
        AVG(o.total_paid) AS avg_order_value
    FROM pay_types AS t
    INNER JOIN order_pay AS o ON o.order_id = t.order_id
    GROUP BY t.payment_type
),
by_installments AS (
    SELECT
        'installments' AS dimension,
        CASE WHEN max_installments <= 1 THEN '1'
             WHEN max_installments <= 3 THEN '2-3'
             WHEN max_installments <= 6 THEN '4-6'
             WHEN max_installments <= 10 THEN '7-10'
             ELSE '11+' END AS bucket,
        COUNT(*) AS orders,
        AVG(total_paid) AS avg_order_value
    FROM order_pay
    GROUP BY CASE WHEN max_installments <= 1 THEN '1'
             WHEN max_installments <= 3 THEN '2-3'
             WHEN max_installments <= 6 THEN '4-6'
             WHEN max_installments <= 10 THEN '7-10'
             ELSE '11+' END
),
by_methods AS (
    SELECT
        'methods_per_order' AS dimension,
        CASE WHEN n_types = 1 THEN '1' ELSE '2+' END AS bucket,
        COUNT(*) AS orders,
        AVG(total_paid) AS avg_order_value
    FROM order_pay
    GROUP BY CASE WHEN n_types = 1 THEN '1' ELSE '2+' END
),
unioned AS (
    SELECT * FROM by_type
    UNION ALL SELECT * FROM by_installments
    UNION ALL SELECT * FROM by_methods
)
SELECT
    u.dimension, u.bucket, u.orders, u.avg_order_value,
    1.0 * u.orders / n_all.n AS share_of_orders
FROM unioned AS u CROSS JOIN n_all
ORDER BY u.dimension, u.orders DESC, u.bucket;
