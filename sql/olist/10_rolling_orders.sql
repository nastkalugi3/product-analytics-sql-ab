-- Q10. Daily orders and a 7-day moving average (the day and the 6 before it).
-- RANGE over dates plus division by 7 treats days without orders as zeros.
-- The first 6 days of the window are partial.

WITH daily AS (
    SELECT CAST(purchase_ts AS DATE) AS day, COUNT(*) AS orders
    FROM orders_window
    GROUP BY CAST(purchase_ts AS DATE)
)
SELECT
    day,
    orders,
    SUM(orders) OVER (
        ORDER BY day
        RANGE BETWEEN INTERVAL '6 days' PRECEDING AND CURRENT ROW
    ) / 7.0 AS orders_ma7
FROM daily
ORDER BY day;
