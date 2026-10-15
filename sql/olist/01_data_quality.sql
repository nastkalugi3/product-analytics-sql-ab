-- Q1. Is the data usable? Row counts, duplicate keys, orphan foreign keys,
-- and orders per month (to pick the analysis window).
-- Output: section, check_name, value.

SELECT 'rows' AS section, 'customers' AS check_name, COUNT(*) AS value FROM customers
UNION ALL SELECT 'rows', 'geolocation', COUNT(*) FROM geolocation
UNION ALL SELECT 'rows', 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'rows', 'order_payments', COUNT(*) FROM order_payments
UNION ALL SELECT 'rows', 'order_reviews', COUNT(*) FROM order_reviews
UNION ALL SELECT 'rows', 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'rows', 'products', COUNT(*) FROM products
UNION ALL SELECT 'rows', 'sellers', COUNT(*) FROM sellers
UNION ALL SELECT 'rows', 'category_translation', COUNT(*) FROM category_translation

-- keys that occur more than once
UNION ALL SELECT 'duplicate_keys', 'orders.order_id', COUNT(*)
FROM (SELECT order_id FROM orders GROUP BY order_id HAVING COUNT(*) > 1) AS d
UNION ALL SELECT 'duplicate_keys', 'customers.customer_id', COUNT(*)
FROM (SELECT customer_id FROM customers GROUP BY customer_id HAVING COUNT(*) > 1) AS d
UNION ALL SELECT 'duplicate_keys', 'products.product_id', COUNT(*)
FROM (SELECT product_id FROM products GROUP BY product_id HAVING COUNT(*) > 1) AS d
UNION ALL SELECT 'duplicate_keys', 'sellers.seller_id', COUNT(*)
FROM (SELECT seller_id FROM sellers GROUP BY seller_id HAVING COUNT(*) > 1) AS d
UNION ALL SELECT 'duplicate_keys', 'order_items(order_id, order_item_id)', COUNT(*)
FROM (
    SELECT order_id, order_item_id FROM order_items
    GROUP BY order_id, order_item_id HAVING COUNT(*) > 1
) AS d
UNION ALL SELECT 'duplicate_keys', 'order_payments(order_id, payment_sequential)', COUNT(*)
FROM (
    SELECT order_id, payment_sequential FROM order_payments
    GROUP BY order_id, payment_sequential HAVING COUNT(*) > 1
) AS d
UNION ALL SELECT 'duplicate_keys', 'order_reviews.review_id', COUNT(*)
FROM (SELECT review_id FROM order_reviews GROUP BY review_id HAVING COUNT(*) > 1) AS d

-- child rows whose parent is missing
UNION ALL SELECT 'orphans', 'orders -> customers', COUNT(*)
FROM orders AS o LEFT JOIN customers AS c ON c.customer_id = o.customer_id
WHERE c.customer_id IS NULL
UNION ALL SELECT 'orphans', 'order_items -> orders', COUNT(*)
FROM order_items AS i LEFT JOIN orders AS o ON o.order_id = i.order_id
WHERE o.order_id IS NULL
UNION ALL SELECT 'orphans', 'order_items -> products', COUNT(*)
FROM order_items AS i LEFT JOIN products AS p ON p.product_id = i.product_id
WHERE p.product_id IS NULL
UNION ALL SELECT 'orphans', 'order_items -> sellers', COUNT(*)
FROM order_items AS i LEFT JOIN sellers AS s ON s.seller_id = i.seller_id
WHERE s.seller_id IS NULL
UNION ALL SELECT 'orphans', 'order_payments -> orders', COUNT(*)
FROM order_payments AS p LEFT JOIN orders AS o ON o.order_id = p.order_id
WHERE o.order_id IS NULL
UNION ALL SELECT 'orphans', 'order_reviews -> orders', COUNT(*)
FROM order_reviews AS r LEFT JOIN orders AS o ON o.order_id = r.order_id
WHERE o.order_id IS NULL

-- orders per purchase month (all statuses, whole data range)
UNION ALL SELECT 'orders_per_month', CAST(CAST(date_trunc('month', order_purchase_timestamp) AS DATE) AS VARCHAR), COUNT(*)
FROM orders
GROUP BY date_trunc('month', order_purchase_timestamp)
ORDER BY 1, 2;
