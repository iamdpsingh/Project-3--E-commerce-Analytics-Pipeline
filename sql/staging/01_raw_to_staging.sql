-- ==============================================================================
-- BIGQUERY STAGING LAYER: UNIFYING MULTI-VENDOR DATA
-- ==============================================================================
-- This script takes the raw data from 3 different vendors and standardizes
-- them into a single, clean staging table.
-- ==============================================================================

CREATE OR REPLACE TABLE `ecommerce-pipe-ds30.ecommerce_staging.all_events`
PARTITION BY DATE(event_time)
CLUSTER BY source_vendor, event_type
AS
WITH vendor_a AS (
    SELECT 
        'vendor_a_multicategory' AS source_vendor,
        event_time,
        event_type,
        product_id,
        category_id,
        category_code,
        brand,
        price,
        user_id,
        user_session,
        CAST(NULL AS INT64) AS order_id  -- Vendor A does not have order_id in raw data
    FROM `ecommerce-pipe-ds30.ecommerce_raw.vendor_a_events`
),

vendor_b AS (
    SELECT 
        'vendor_b_cosmetics' AS source_vendor,
        event_time,
        event_type,
        product_id,
        category_id,
        category_code,
        brand,
        price,
        user_id,
        user_session,
        CAST(NULL AS INT64) AS order_id
    FROM `ecommerce-pipe-ds30.ecommerce_raw.vendor_b_events`
),

vendor_c AS (
    SELECT 
        'vendor_c_electronics' AS source_vendor,
        event_time,
        'purchase' AS event_type,  -- Electronics dataset is purchase history only
        product_id,
        category_id,
        category_code,
        brand,
        price,
        user_id,
        CAST(NULL AS STRING) AS user_session,     -- Vendor C does not have user_session
        order_id
    FROM `ecommerce-pipe-ds30.ecommerce_raw.vendor_c_events`
)

SELECT * FROM vendor_a
UNION ALL
SELECT * FROM vendor_b
UNION ALL
SELECT * FROM vendor_c;
