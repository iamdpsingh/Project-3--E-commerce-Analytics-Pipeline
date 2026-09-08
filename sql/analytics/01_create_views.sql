-- ==============================================================================
-- BIGQUERY ANALYTICS: VIEWS
-- ==============================================================================
-- Analytical views built on top of the warehouse star schema.
-- These views power the unified dashboard and allow slicing by source_vendor.
-- ==============================================================================

-- 1. Monthly revenue — how much revenue was generated each month per vendor?
CREATE OR REPLACE VIEW `ecommerce-pipe-ds30.ecommerce_analytics.monthly_revenue` AS
SELECT
    fo.source_vendor,
    dd.year,
    dd.month,
    dd.year_month,
    dd.month_name,
    COUNT(DISTINCT fo.order_id)    AS total_orders,
    COUNT(DISTINCT fo.user_id)     AS unique_customers,
    SUM(fo.total_amount)           AS total_revenue,
    AVG(fo.total_amount)           AS avg_order_value,
    SUM(fo.total_amount)
        / NULLIF(COUNT(DISTINCT fo.order_id), 0) AS revenue_per_order
FROM `ecommerce-pipe-ds30.ecommerce_warehouse.fact_orders` fo
JOIN `ecommerce-pipe-ds30.ecommerce_warehouse.dim_date` dd 
  ON dd.date_sk = fo.date_sk
GROUP BY fo.source_vendor, dd.year, dd.month, dd.year_month, dd.month_name
ORDER BY dd.year, dd.month;

-- 2. Product performance — which products sell best by revenue?
CREATE OR REPLACE VIEW `ecommerce-pipe-ds30.ecommerce_analytics.product_performance` AS
SELECT
    dp.product_id,
    dp.category_code,
    dp.category_main,
    dp.brand,
    dp.price                                        AS list_price,
    COUNT(DISTINCT foi.order_id)                    AS times_purchased,
    SUM(foi.quantity)                               AS total_quantity_sold,
    SUM(foi.line_total)                             AS total_revenue,
    AVG(foi.unit_price)                             AS avg_selling_price
FROM `ecommerce-pipe-ds30.ecommerce_warehouse.fact_order_items` foi
JOIN `ecommerce-pipe-ds30.ecommerce_warehouse.dim_product` dp 
  ON dp.product_id = foi.product_id
GROUP BY
    dp.product_id, dp.category_code, dp.category_main,
    dp.brand, dp.price;

-- 3. Customer performance — who are the top customers by lifetime value?
CREATE OR REPLACE VIEW `ecommerce-pipe-ds30.ecommerce_analytics.customer_performance` AS
SELECT
    dc.user_id,
    dc.first_seen_at,
    dc.last_seen_at,
    dc.is_repeat_buyer,
    COUNT(DISTINCT fo.order_id)                          AS total_orders,
    SUM(fo.total_amount)                                 AS lifetime_revenue,
    AVG(fo.total_amount)                                 AS avg_order_value,
    MAX(fo.order_date)                                   AS last_order_date
FROM `ecommerce-pipe-ds30.ecommerce_warehouse.dim_customer` dc
JOIN `ecommerce-pipe-ds30.ecommerce_warehouse.fact_orders` fo 
  ON fo.user_id = dc.user_id
GROUP BY
    dc.user_id, dc.first_seen_at,
    dc.last_seen_at, dc.is_repeat_buyer;

-- 4. Category performance — which product categories drive the most revenue?
CREATE OR REPLACE VIEW `ecommerce-pipe-ds30.ecommerce_analytics.category_performance` AS
SELECT
    dp.category_main,
    COUNT(DISTINCT dp.product_id)           AS unique_products,
    COUNT(DISTINCT foi.order_id)            AS total_purchases,
    SUM(foi.quantity)                       AS total_quantity,
    SUM(foi.line_total)                     AS total_revenue,
    AVG(foi.unit_price)                     AS avg_price
FROM `ecommerce-pipe-ds30.ecommerce_warehouse.fact_order_items` foi
JOIN `ecommerce-pipe-ds30.ecommerce_warehouse.dim_product` dp 
  ON dp.product_id = foi.product_id
GROUP BY dp.category_main;

-- 5. Executive KPIs — top-line numbers for the executive dashboard, split by vendor.
CREATE OR REPLACE VIEW `ecommerce-pipe-ds30.ecommerce_analytics.executive_kpis` AS
SELECT
    fo.source_vendor,
    COUNT(DISTINCT fo.order_id)                          AS total_orders,
    COUNT(DISTINCT fo.user_id)                           AS total_customers,
    SUM(fo.total_amount)                                 AS total_revenue,
    ROUND(
        SUM(fo.total_amount)
        / NULLIF(COUNT(DISTINCT fo.order_id), 0), 2
    )                                                    AS avg_order_value,
    COUNT(DISTINCT
        CASE WHEN dc.is_repeat_buyer THEN fo.user_id END
    )                                                    AS repeat_customers
FROM `ecommerce-pipe-ds30.ecommerce_warehouse.fact_orders` fo
JOIN `ecommerce-pipe-ds30.ecommerce_warehouse.dim_customer` dc 
  ON dc.user_id = fo.user_id
GROUP BY fo.source_vendor;

-- 6. Brand performance — which brands generate the most revenue?
CREATE OR REPLACE VIEW `ecommerce-pipe-ds30.ecommerce_analytics.brand_performance` AS
SELECT
    dp.brand,
    COUNT(DISTINCT dp.product_id)     AS unique_products,
    SUM(foi.quantity)                 AS total_quantity_sold,
    SUM(foi.line_total)               AS total_revenue,
    AVG(foi.unit_price)               AS avg_price
FROM `ecommerce-pipe-ds30.ecommerce_warehouse.fact_order_items` foi
JOIN `ecommerce-pipe-ds30.ecommerce_warehouse.dim_product` dp 
  ON dp.product_id = foi.product_id
WHERE dp.brand <> 'unknown'
GROUP BY dp.brand;
