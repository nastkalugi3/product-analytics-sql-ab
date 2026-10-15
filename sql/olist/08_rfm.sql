-- Q8. RFM segmentation. Recency and monetary use NTILE(5). Frequency does NOT:
-- almost every customer has one order, so quintiles would split identical
-- customers at random. It is a hand-made score: 1 order = 1, 2 = 2, 3+ = 3.
-- Ties in NTILE are broken by customer id so the result is reproducible.
-- Recency is measured from the day after the last purchase in the data.

WITH snapshot AS (
    SELECT MAX(purchase_ts) + INTERVAL '1 day' AS snap FROM sales_orders
),
customer AS (
    SELECT
        s.customer_unique_id,
        EXTRACT(epoch FROM (MAX(sn.snap) - MAX(s.purchase_ts))) / 86400.0 AS recency_days,
        COUNT(*) AS frequency,
        SUM(s.gmv) AS monetary
    FROM sales_orders AS s
    CROSS JOIN snapshot AS sn
    GROUP BY s.customer_unique_id
),
scored AS (
    SELECT
        customer_unique_id, recency_days, frequency, monetary,
        NTILE(5) OVER (ORDER BY recency_days DESC, customer_unique_id) AS r_score,
        CASE WHEN frequency >= 3 THEN 3 WHEN frequency = 2 THEN 2 ELSE 1 END AS f_score,
        NTILE(5) OVER (ORDER BY monetary, customer_unique_id) AS m_score
    FROM customer
),
segmented AS (
    SELECT
        *,
        CASE
            WHEN f_score >= 2 AND r_score >= 4 THEN 'active repeat'
            WHEN f_score >= 2 THEN 'lapsed repeat'
            WHEN r_score >= 4 AND m_score >= 4 THEN 'new big spenders'
            WHEN r_score >= 4 THEN 'new'
            WHEN r_score <= 2 AND m_score >= 4 THEN 'lost big spenders'
            WHEN r_score <= 2 THEN 'lost'
            ELSE 'in between'
        END AS segment
    FROM scored
)
SELECT
    segment,
    COUNT(*) AS customers,
    1.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS customer_share,
    SUM(monetary) AS revenue,
    SUM(monetary) / SUM(SUM(monetary)) OVER () AS revenue_share,
    AVG(monetary) AS avg_gmv,
    AVG(recency_days) AS avg_recency_days
FROM segmented
GROUP BY segment
ORDER BY revenue DESC;
