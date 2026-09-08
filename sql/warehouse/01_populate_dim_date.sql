-- ==============================================================================
-- BIGQUERY WAREHOUSE: DATE DIMENSION
-- ==============================================================================
-- Generates a static Date dimension table for 2019 - 2021
-- ==============================================================================

CREATE OR REPLACE TABLE `ecommerce-pipe-ds30.ecommerce_warehouse.dim_date`
AS
SELECT
    CAST(FORMAT_DATE('%Y%m%d', d) AS INT64) AS date_sk,
    d AS full_date,
    EXTRACT(YEAR FROM d) AS year,
    EXTRACT(QUARTER FROM d) AS quarter,
    EXTRACT(MONTH FROM d) AS month,
    FORMAT_DATE('%B', d) AS month_name,
    EXTRACT(ISOWEEK FROM d) AS week,
    EXTRACT(DAY FROM d) AS day_of_month,
    EXTRACT(DAYOFWEEK FROM d) AS day_of_week, -- 1=Sun, 2=Mon...
    FORMAT_DATE('%A', d) AS day_name,
    EXTRACT(DAYOFWEEK FROM d) IN (1, 7) AS is_weekend,
    d = DATE_TRUNC(d, MONTH) AS is_month_start,
    d = LAST_DAY(d, MONTH) AS is_month_end,
    FORMAT_DATE('%Y-%m', d) AS year_month
FROM UNNEST(GENERATE_DATE_ARRAY('2019-01-01', '2021-12-31', INTERVAL 1 DAY)) AS d;
