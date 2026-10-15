-- Q9. Seller concentration (Pareto): sellers ranked by revenue (items price),
-- with the cumulative share of total revenue.

WITH seller_revenue AS (
    SELECT i.seller_id, SUM(i.price) AS revenue
    FROM sales_orders AS s
    INNER JOIN order_items AS i ON i.order_id = s.order_id
    GROUP BY i.seller_id
)
SELECT
    ROW_NUMBER() OVER (ORDER BY revenue DESC, seller_id) AS seller_rank,
    seller_id,
    revenue,
    SUM(revenue) OVER (
        ORDER BY revenue DESC, seller_id
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) / SUM(revenue) OVER () AS cum_revenue_share,
    1.0 * ROW_NUMBER() OVER (ORDER BY revenue DESC, seller_id)
        / COUNT(*) OVER () AS cum_seller_share
FROM seller_revenue
ORDER BY seller_rank;
