-- D0. Footer facts: coverage of the analysis window and totals.
-- Not a dashboard block; it feeds the footer and the documentation.

SELECT
    (SELECT CAST(MIN(purchase_ts) AS DATE) FROM orders_window) AS first_order_date,
    (SELECT CAST(MAX(purchase_ts) AS DATE) FROM orders_window) AS last_order_date,
    (SELECT COUNT(*) FROM orders_window) AS window_orders,
    (SELECT COUNT(*) FROM sales_orders) AS sales_orders,
    (SELECT SUM(gmv) FROM sales_orders) AS total_gmv;
