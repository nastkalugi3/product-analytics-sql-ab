-- Q6. Monthly cohorts by first purchase and retention for months 0..6.
-- A person is customer_unique_id (customer_id changes with every order).
-- Cells with zero active customers are absent; the notebook fills them in
-- and masks months that lie beyond the end of the data.

WITH first_month AS (
    SELECT
        customer_unique_id,
        MIN(date_trunc('month', purchase_ts)) AS cohort_month
    FROM sales_orders
    GROUP BY customer_unique_id
),
activity AS (
    SELECT DISTINCT
        s.customer_unique_id,
        f.cohort_month,
        (EXTRACT(year FROM s.purchase_ts) * 12 + EXTRACT(month FROM s.purchase_ts))
        - (EXTRACT(year FROM f.cohort_month) * 12 + EXTRACT(month FROM f.cohort_month))
            AS month_number
    FROM sales_orders AS s
    INNER JOIN first_month AS f ON f.customer_unique_id = s.customer_unique_id
),
cells AS (
    SELECT cohort_month, month_number, COUNT(*) AS active_customers
    FROM activity
    WHERE month_number BETWEEN 0 AND 6
    GROUP BY cohort_month, month_number
)
SELECT
    c.cohort_month,
    c.month_number,
    c.active_customers,
    z.active_customers AS cohort_size,
    1.0 * c.active_customers / z.active_customers AS retention
FROM cells AS c
INNER JOIN cells AS z
        ON z.cohort_month = c.cohort_month AND z.month_number = 0
ORDER BY c.cohort_month, c.month_number;
