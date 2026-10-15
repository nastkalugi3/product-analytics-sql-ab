-- Q7. Repeat purchase: share of customers with 2+ orders and the time from
-- the first to the second order (LEAD over each customer's orders).

WITH ordered AS (
    SELECT
        customer_unique_id,
        purchase_ts,
        ROW_NUMBER() OVER (
            PARTITION BY customer_unique_id ORDER BY purchase_ts, order_id
        ) AS rn,
        LEAD(purchase_ts) OVER (
            PARTITION BY customer_unique_id ORDER BY purchase_ts, order_id
        ) AS next_ts
    FROM sales_orders
),
customers_n AS (
    SELECT customer_unique_id, COUNT(*) AS n_orders
    FROM ordered
    GROUP BY customer_unique_id
),
gap AS (
    SELECT EXTRACT(epoch FROM (next_ts - purchase_ts)) / 86400.0 AS days_to_second
    FROM ordered
    WHERE rn = 1 AND next_ts IS NOT NULL
)
SELECT
    (SELECT COUNT(*) FROM customers_n) AS customers,
    (SELECT COUNT(*) FROM customers_n WHERE n_orders >= 2) AS repeat_customers,
    1.0 * (SELECT COUNT(*) FROM customers_n WHERE n_orders >= 2)
        / (SELECT COUNT(*) FROM customers_n) AS repeat_share,
    (SELECT MAX(n_orders) FROM customers_n) AS max_orders,
    (SELECT percentile_cont(0.25) WITHIN GROUP (ORDER BY days_to_second) FROM gap) AS p25_days,
    (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY days_to_second) FROM gap) AS median_days,
    (SELECT percentile_cont(0.75) WITHIN GROUP (ORDER BY days_to_second) FROM gap) AS p75_days;
