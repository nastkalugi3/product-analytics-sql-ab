-- Helper views on top of the 9 raw Olist tables.
-- Plain SQL that runs in both DuckDB and PostgreSQL.
--
-- Analysis window: orders purchased 2017-01-01 .. 2018-08-31.
-- Why: late 2016 has only a few hundred orders and Sep-Oct 2018 only a handful
-- (see 01_data_quality), so monthly numbers at the edges are noise.

CREATE VIEW order_value AS
SELECT
    order_id,
    COUNT(*)                 AS n_items,
    SUM(price)               AS items_revenue,
    SUM(freight_value)       AS freight,
    SUM(price + freight_value) AS gmv
FROM order_items
GROUP BY order_id;

-- One row per order with the real customer key. customer_id is generated per
-- order, so people are counted by customer_unique_id.
CREATE VIEW orders_enriched AS
SELECT
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    c.customer_state,
    o.order_status,
    o.order_purchase_timestamp      AS purchase_ts,
    o.order_approved_at             AS approved_ts,
    o.order_delivered_carrier_date  AS carrier_ts,
    o.order_delivered_customer_date AS delivered_ts,
    o.order_estimated_delivery_date AS estimated_ts
FROM orders AS o
LEFT JOIN customers AS c ON c.customer_id = o.customer_id;

CREATE VIEW orders_window AS
SELECT *
FROM orders_enriched
WHERE purchase_ts >= TIMESTAMP '2017-01-01 00:00:00'
  AND purchase_ts <  TIMESTAMP '2018-09-01 00:00:00';

-- Orders that count as sales: inside the window, not canceled/unavailable,
-- with at least one item (so GMV is defined).
CREATE VIEW sales_orders AS
SELECT w.*, v.n_items, v.items_revenue, v.freight, v.gmv
FROM orders_window AS w
INNER JOIN order_value AS v ON v.order_id = w.order_id
WHERE w.order_status NOT IN ('canceled', 'unavailable');
