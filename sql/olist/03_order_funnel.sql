-- Q3. Order funnel: purchase -> approved -> handed to carrier -> delivered,
-- plus canceled / unavailable shares and median hours between steps.
-- Stage is reached when its timestamp is filled in.

WITH steps AS (
    SELECT
        order_status,
        EXTRACT(epoch FROM (approved_ts - purchase_ts)) / 3600.0 AS h_to_approved,
        EXTRACT(epoch FROM (carrier_ts - approved_ts)) / 3600.0 AS h_to_carrier,
        EXTRACT(epoch FROM (delivered_ts - carrier_ts)) / 3600.0 AS h_to_delivered,
        approved_ts, carrier_ts, delivered_ts
    FROM orders_window
),
tot AS (SELECT COUNT(*) AS n FROM steps)
SELECT 1 AS step, 'purchased' AS stage, tot.n AS orders,
       1.0 AS share_of_purchased,
       CAST(NULL AS DOUBLE PRECISION) AS median_hours_from_prev
FROM tot
UNION ALL
SELECT 2, 'approved', COUNT(approved_ts), 1.0 * COUNT(approved_ts) / (SELECT n FROM tot),
       percentile_cont(0.5) WITHIN GROUP (ORDER BY h_to_approved)
FROM steps
UNION ALL
SELECT 3, 'handed_to_carrier', COUNT(carrier_ts), 1.0 * COUNT(carrier_ts) / (SELECT n FROM tot),
       percentile_cont(0.5) WITHIN GROUP (ORDER BY h_to_carrier)
FROM steps
UNION ALL
SELECT 4, 'delivered', COUNT(delivered_ts), 1.0 * COUNT(delivered_ts) / (SELECT n FROM tot),
       percentile_cont(0.5) WITHIN GROUP (ORDER BY h_to_delivered)
FROM steps
UNION ALL
SELECT 5, 'canceled', COUNT(*), 1.0 * COUNT(*) / (SELECT n FROM tot),
       CAST(NULL AS DOUBLE PRECISION)
FROM steps WHERE order_status = 'canceled'
UNION ALL
SELECT 6, 'unavailable', COUNT(*), 1.0 * COUNT(*) / (SELECT n FROM tot),
       CAST(NULL AS DOUBLE PRECISION)
FROM steps WHERE order_status = 'unavailable'
ORDER BY step;
