-- populate_dim_date.sql
--
-- Generates the date dimension spine covering 2019-01-01 → 2021-12-31.
-- We use CASCADE so the TRUNCATE works even when fact tables reference dim_date.
-- All dependent fact tables are repopulated immediately after by the
-- subsequent warehouse SQL scripts.

TRUNCATE warehouse.dim_date CASCADE;

INSERT INTO warehouse.dim_date (
    date_sk, full_date, year, quarter, month, month_name,
    week, day_of_month, day_of_week, day_name,
    is_weekend, is_month_start, is_month_end, year_month
)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INT         AS date_sk,
    d::DATE                              AS full_date,
    EXTRACT(YEAR    FROM d)::SMALLINT   AS year,
    EXTRACT(QUARTER FROM d)::SMALLINT   AS quarter,
    EXTRACT(MONTH   FROM d)::SMALLINT   AS month,
    TO_CHAR(d, 'Month')                  AS month_name,
    EXTRACT(WEEK    FROM d)::SMALLINT   AS week,
    EXTRACT(DAY     FROM d)::SMALLINT   AS day_of_month,
    EXTRACT(ISODOW  FROM d)::SMALLINT   AS day_of_week,
    TO_CHAR(d, 'Day')                    AS day_name,
    EXTRACT(ISODOW  FROM d) IN (6, 7)   AS is_weekend,
    (d = DATE_TRUNC('month', d))         AS is_month_start,
    (d = DATE_TRUNC('month', d) + INTERVAL '1 month - 1 day') AS is_month_end,
    TO_CHAR(d, 'YYYY-MM')               AS year_month
FROM GENERATE_SERIES(
    '2019-01-01'::DATE,
    '2021-12-31'::DATE,
    '1 day'::INTERVAL
) AS d;
