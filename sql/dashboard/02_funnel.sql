-- D2. Order funnel over the whole analysis window.
-- Steps are counted by the timestamp being filled in (order_status is only the
-- latest snapshot, not a history). Step conversion = step / previous step.
-- Losses are counted by status: canceled and unavailable. 'in_progress' groups
-- the non-final statuses (created, approved, invoiced, processing, shipped).
-- kind: step | loss | open. share_of_purchased is relative to all purchased orders.

WITH base AS (
    SELECT order_status, approved_ts, carrier_ts, delivered_ts
    FROM orders_window
),
counts AS (
    SELECT 1 AS step_order, 'Purchased' AS stage, 'step' AS kind,
           COUNT(*) AS orders
    FROM base
    UNION ALL
    SELECT 2, 'Approved', 'step', COUNT(approved_ts) FROM base
    UNION ALL
    SELECT 3, 'Handed to carrier', 'step', COUNT(carrier_ts) FROM base
    UNION ALL
    SELECT 4, 'Delivered', 'step', COUNT(delivered_ts) FROM base
    UNION ALL
    SELECT 5, 'Canceled', 'loss', COUNT(*) FROM base
    WHERE order_status = 'canceled'
    UNION ALL
    SELECT 6, 'Unavailable', 'loss', COUNT(*) FROM base
    WHERE order_status = 'unavailable'
    UNION ALL
    SELECT 7, 'In progress', 'open', COUNT(*) FROM base
    WHERE order_status IN ('created', 'approved', 'invoiced', 'processing', 'shipped')
),
with_prev AS (
    SELECT
        step_order, stage, kind, orders,
        LAG(orders) OVER (ORDER BY step_order) AS prev_orders,
        MAX(CASE WHEN step_order = 1 THEN orders END) OVER () AS purchased
    FROM counts
)
SELECT
    step_order,
    stage,
    kind,
    orders,
    1.0 * orders / purchased AS share_of_purchased,
    CASE WHEN kind = 'step' AND step_order > 1
         THEN 1.0 * orders / prev_orders END AS step_conversion
FROM with_prev
ORDER BY step_order;
