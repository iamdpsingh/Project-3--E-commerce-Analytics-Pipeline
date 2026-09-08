-- ==============================================================================
-- BIGQUERY WAREHOUSE: DIMENSIONS
-- ==============================================================================
-- Builds dim_customer and dim_product directly from the unified staging layer.
-- Uses ELT (Transform in BigQuery) rather than Pandas.
-- ==============================================================================

-- 1. dim_customer
-- Groups all events by user_id to build the customer profile
CREATE OR REPLACE TABLE `ecommerce-pipe-ds30.ecommerce_warehouse.dim_customer`
CLUSTER BY user_id
AS
SELECT 
    user_id,
    MIN(event_time) AS first_seen_at,
    MAX(event_time) AS last_seen_at,
    COUNT(*) AS total_events,
    COUNT(DISTINCT user_session) AS total_sessions,
    COUNTIF(event_type = 'purchase') > 1 AS is_repeat_buyer
FROM `ecommerce-pipe-ds30.ecommerce_staging.all_events`
WHERE user_id IS NOT NULL
GROUP BY user_id;


-- 2. dim_product
-- Deduplicates products across the 133 million rows by taking the most recent seen price/category
CREATE OR REPLACE TABLE `ecommerce-pipe-ds30.ecommerce_warehouse.dim_product`
CLUSTER BY product_id
AS
WITH ranked_products AS (
    SELECT 
        product_id,
        category_id,
        IFNULL(category_code, 'unknown') AS category_code,
        CASE
            WHEN category_code IS NULL THEN 'unknown'
            WHEN STRPOS(category_code, '.') > 0 THEN SPLIT(category_code, '.')[OFFSET(0)]
            ELSE category_code
        END AS category_main,
        IFNULL(brand, 'unknown') AS brand,
        price,
        ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY event_time DESC) AS rn
    FROM `ecommerce-pipe-ds30.ecommerce_staging.all_events`
    WHERE product_id IS NOT NULL
)
SELECT 
    product_id, category_id, category_code, category_main, brand, price
FROM ranked_products 
WHERE rn = 1;
