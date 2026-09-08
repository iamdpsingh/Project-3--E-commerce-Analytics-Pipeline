-- populate_dimensions.sql
--
-- Populates dim_customer and dim_product from the staging layer.
-- Uses TRUNCATE CASCADE so dependent fact tables are cleared first
-- (they get rebuilt by the next script).

-- dim_customer
-- is_repeat_buyer is computed using a CTE to aggregate order counts,
-- which is much faster than a correlated subquery on 1.6M rows.
TRUNCATE warehouse.dim_customer CASCADE;

WITH order_counts AS (
    SELECT user_id, COUNT(*) AS order_count
    FROM staging.orders
    GROUP BY user_id
)
INSERT INTO warehouse.dim_customer (
    user_id, first_seen_at, last_seen_at,
    total_events, total_sessions, is_repeat_buyer
)
SELECT
    c.user_id,
    c.first_seen_at,
    c.last_seen_at,
    c.total_events,
    c.total_sessions,
    COALESCE(oc.order_count, 0) > 1 AS is_repeat_buyer
FROM staging.customers c
LEFT JOIN order_counts oc ON c.user_id = oc.user_id;

-- dim_product
-- category_main is derived by splitting the dot-separated category_code
-- and taking the first segment (e.g. 'electronics.audio' → 'electronics').
TRUNCATE warehouse.dim_product CASCADE;

INSERT INTO warehouse.dim_product (
    product_id, category_id, category_code, category_main, brand, price
)
SELECT
    product_id,
    category_id,
    category_code,
    CASE
        WHEN category_code = 'unknown' THEN 'unknown'
        WHEN POSITION('.' IN category_code) > 0
            THEN SPLIT_PART(category_code, '.', 1)
        ELSE category_code
    END AS category_main,
    brand,
    price
FROM staging.products;
