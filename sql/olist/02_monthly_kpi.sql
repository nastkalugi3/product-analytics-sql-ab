-- Q2. Monthly KPIs: GMV, orders, buyers, AOV and month-over-month growth.
-- GMV = items price + freight. Buyers = distinct customer_unique_id.

WITH monthly AS (
    SELECT
        date_trunc('month', purchase_ts) AS month,
        COUNT(*)                         AS orders,
        COUNT(DISTINCT customer_unique_id) AS buyers,
        SUM(gmv)                         AS gmv
    FROM sales_orders
    GROUP BY date_trunc('month', purchase_ts)
)
SELECT
    month,
    orders,
    buyers,
    gmv,
    gmv / orders AS aov,
    gmv / LAG(gmv) OVER (ORDER BY month) - 1.0 AS gmv_mom,
    1.0 * orders / LAG(orders) OVER (ORDER BY month) - 1.0 AS orders_mom
FROM monthly
ORDER BY month;
