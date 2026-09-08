-- ==============================================================================
-- BIGQUERY WAREHOUSE: FACTS
-- ==============================================================================
-- Builds fact_orders and fact_order_items directly from staging.
-- Handles multi-vendor order definition (Vendor C has order_id, A/B use user_session)
-- ==============================================================================

-- 1. fact_orders
CREATE OR REPLACE TABLE `ecommerce-pipe-ds30.ecommerce_warehouse.fact_orders`
PARTITION BY DATE(order_date)
CLUSTER BY user_id
AS
WITH purchase_events AS (
    SELECT 
        event_time,
        source_vendor,
        user_id,
        user_session,
        order_id,
        product_id,
        price
    FROM `ecommerce-pipe-ds30.ecommerce_staging.all_events`
    WHERE event_type = 'purchase'
),
order_groups AS (
    SELECT 
        -- Vendor C provides order_id. Vendor A & B use user_session as the cart ID.
        COALESCE(CAST(order_id AS STRING), user_session) AS unified_order_id,
        user_id,
        MAX(source_vendor) AS source_vendor,
        MIN(event_time) AS order_date,
        COUNT(product_id) AS total_items,
        SUM(price) AS total_amount,
        'completed' AS status
    FROM purchase_events
    WHERE COALESCE(CAST(order_id AS STRING), user_session) IS NOT NULL
    GROUP BY unified_order_id, user_id
)
SELECT 
    unified_order_id AS order_id,
    user_id,
    source_vendor,
    CAST(FORMAT_DATE('%Y%m%d', order_date) AS INT64) AS date_sk,
    order_date,
    total_items,
    total_amount,
    status
FROM order_groups;

-- 2. fact_order_items
CREATE OR REPLACE TABLE `ecommerce-pipe-ds30.ecommerce_warehouse.fact_order_items`
PARTITION BY DATE(event_time)
CLUSTER BY order_id, product_id
AS
SELECT 
    GENERATE_UUID() AS order_item_id,
    COALESCE(CAST(order_id AS STRING), user_session) AS order_id,
    product_id,
    CAST(FORMAT_DATE('%Y%m%d', event_time) AS INT64) AS date_sk,
    event_time,
    1 AS quantity,  -- Raw events represent 1 item per row
    price AS unit_price,
    price AS line_total
FROM `ecommerce-pipe-ds30.ecommerce_staging.all_events`
WHERE event_type = 'purchase'
AND COALESCE(CAST(order_id AS STRING), user_session) IS NOT NULL;
