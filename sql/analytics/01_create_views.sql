-- create_views.sql
--
-- Analytical views built on top of the warehouse star schema.
-- Each view addresses a specific business question and serves
-- as the data source for a dashboard page.

CREATE SCHEMA IF NOT EXISTS analytics;

-- Monthly revenue — how much revenue was generated each month?
CREATE OR REPLACE VIEW analytics.monthly_revenue AS
SELECT
    dd.year,
    dd.month,
    dd.year_month,
    dd.month_name,
    COUNT(DISTINCT fo.order_sk)    AS total_orders,
    COUNT(DISTINCT fo.customer_sk) AS unique_customers,
    SUM(fo.total_amount)           AS total_revenue,
    AVG(fo.total_amount)           AS avg_order_value,
    SUM(fo.total_amount)
        / NULLIF(COUNT(DISTINCT fo.order_sk), 0) AS revenue_per_order
FROM warehouse.fact_orders fo
JOIN warehouse.dim_date    dd ON dd.date_sk = fo.date_sk
GROUP BY dd.year, dd.month, dd.year_month, dd.month_name
ORDER BY dd.year, dd.month;


-- Product performance — which products sell best by revenue?
CREATE OR REPLACE VIEW analytics.product_performance AS
SELECT
    dp.product_id,
    dp.category_code,
    dp.category_main,
    dp.brand,
    dp.price                                        AS list_price,
    COUNT(DISTINCT foi.order_item_sk)               AS times_purchased,
    SUM(foi.quantity)                               AS total_quantity_sold,
    SUM(foi.line_total)                             AS total_revenue,
    AVG(foi.unit_price)                             AS avg_selling_price,
    RANK() OVER (ORDER BY SUM(foi.line_total) DESC) AS revenue_rank
FROM warehouse.fact_order_items foi
JOIN warehouse.dim_product      dp ON dp.product_sk = foi.product_sk
GROUP BY
    dp.product_id, dp.category_code, dp.category_main,
    dp.brand, dp.price
ORDER BY total_revenue DESC;


-- Customer performance — who are the top customers by lifetime value?
CREATE OR REPLACE VIEW analytics.customer_performance AS
SELECT
    dc.user_id,
    dc.first_seen_at,
    dc.last_seen_at,
    dc.is_repeat_buyer,
    COUNT(DISTINCT fo.order_sk)                          AS total_orders,
    SUM(fo.total_amount)                                 AS lifetime_revenue,
    AVG(fo.total_amount)                                 AS avg_order_value,
    MAX(fo.order_date)                                   AS last_order_date,
    RANK() OVER (ORDER BY SUM(fo.total_amount) DESC)     AS revenue_rank
FROM warehouse.dim_customer dc
JOIN warehouse.fact_orders  fo ON fo.customer_sk = dc.customer_sk
GROUP BY
    dc.customer_sk, dc.user_id, dc.first_seen_at,
    dc.last_seen_at, dc.is_repeat_buyer
ORDER BY lifetime_revenue DESC;


-- Category performance — which product categories drive the most revenue?
CREATE OR REPLACE VIEW analytics.category_performance AS
SELECT
    dp.category_main,
    COUNT(DISTINCT dp.product_id)           AS unique_products,
    COUNT(DISTINCT foi.order_item_sk)       AS total_purchases,
    SUM(foi.quantity)                       AS total_quantity,
    SUM(foi.line_total)                     AS total_revenue,
    AVG(foi.unit_price)                     AS avg_price,
    ROUND(
        100.0 * SUM(foi.line_total)
        / NULLIF(SUM(SUM(foi.line_total)) OVER (), 0),
    2) AS revenue_share_pct
FROM warehouse.fact_order_items foi
JOIN warehouse.dim_product      dp ON dp.product_sk = foi.product_sk
GROUP BY dp.category_main
ORDER BY total_revenue DESC;


-- Executive KPIs — top-line numbers for the executive dashboard.
CREATE OR REPLACE VIEW analytics.executive_kpis AS
SELECT
    COUNT(DISTINCT fo.order_sk)                          AS total_orders,
    COUNT(DISTINCT fo.customer_sk)                       AS total_customers,
    SUM(fo.total_amount)                                 AS total_revenue,
    ROUND(
        SUM(fo.total_amount)
        / NULLIF(COUNT(DISTINCT fo.order_sk), 0), 2
    )                                                    AS avg_order_value,
    COUNT(DISTINCT
        CASE WHEN dc.is_repeat_buyer THEN fo.customer_sk END
    )                                                    AS repeat_customers,
    ROUND(
        100.0 * COUNT(DISTINCT
            CASE WHEN dc.is_repeat_buyer THEN fo.customer_sk END
        )
        / NULLIF(COUNT(DISTINCT fo.customer_sk), 0), 2
    )                                                    AS repeat_customer_pct
FROM warehouse.fact_orders  fo
JOIN warehouse.dim_customer dc ON dc.customer_sk = fo.customer_sk;


-- Time analytics — daily order and revenue breakdown.
CREATE OR REPLACE VIEW analytics.time_analytics AS
SELECT
    dd.year,
    dd.quarter,
    dd.month,
    dd.year_month,
    dd.week,
    dd.full_date,
    COUNT(DISTINCT fo.order_sk) AS daily_orders,
    SUM(fo.total_amount)        AS daily_revenue
FROM warehouse.dim_date    dd
LEFT JOIN warehouse.fact_orders fo ON fo.date_sk = dd.date_sk
GROUP BY
    dd.year, dd.quarter, dd.month, dd.year_month,
    dd.week, dd.full_date
ORDER BY dd.full_date;


-- Payment analysis — payment method and status breakdown.
CREATE OR REPLACE VIEW analytics.payment_analysis AS
SELECT
    sp.payment_method,
    sp.payment_status,
    COUNT(*)                         AS payment_count,
    SUM(sp.payment_value)            AS total_value,
    AVG(sp.payment_value)            AS avg_value,
    ROUND(
        100.0 * COUNT(*)
        / NULLIF(SUM(COUNT(*)) OVER (), 0), 2
    )                                AS payment_share_pct
FROM staging.payments sp
GROUP BY sp.payment_method, sp.payment_status
ORDER BY total_value DESC;


-- Brand performance — which brands generate the most revenue?
CREATE OR REPLACE VIEW analytics.brand_performance AS
SELECT
    dp.brand,
    COUNT(DISTINCT dp.product_id)     AS unique_products,
    SUM(foi.quantity)                 AS total_quantity_sold,
    SUM(foi.line_total)               AS total_revenue,
    AVG(foi.unit_price)               AS avg_price,
    RANK() OVER (ORDER BY SUM(foi.line_total) DESC) AS revenue_rank
FROM warehouse.fact_order_items foi
JOIN warehouse.dim_product      dp ON dp.product_sk = foi.product_sk
WHERE dp.brand <> 'unknown'
GROUP BY dp.brand
ORDER BY total_revenue DESC;
