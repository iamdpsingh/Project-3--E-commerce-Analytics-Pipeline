-- warehouse_schema.sql
--
-- Star schema for the data warehouse.
-- Three dimension tables and two fact tables.
--
-- The design uses both surrogate keys (BIGSERIAL, for internal joins)
-- and natural keys (original IDs, for traceability back to source).
--
-- Indexes are added for the query patterns that analytical views use:
-- filtering by date, grouping by customer, grouping by product category.

CREATE SCHEMA IF NOT EXISTS warehouse;

-- dim_customer
-- One row per unique user, with a surrogate key for warehouse joins.
DROP TABLE IF EXISTS warehouse.dim_customer CASCADE;
CREATE TABLE warehouse.dim_customer (
    customer_sk     BIGSERIAL       PRIMARY KEY,
    user_id         BIGINT          NOT NULL UNIQUE,
    first_seen_at   TIMESTAMPTZ,
    last_seen_at    TIMESTAMPTZ,
    total_events    INT,
    total_sessions  INT,
    is_repeat_buyer BOOLEAN         DEFAULT FALSE,
    dw_created_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    dw_updated_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- dim_product
-- One row per unique product, with a derived top-level category column
-- extracted from the dot-separated category_code (e.g. 'electronics.audio' → 'electronics').
DROP TABLE IF EXISTS warehouse.dim_product CASCADE;
CREATE TABLE warehouse.dim_product (
    product_sk      BIGSERIAL       PRIMARY KEY,
    product_id      BIGINT          NOT NULL UNIQUE,
    category_id     BIGINT,
    category_code   VARCHAR(255),
    category_main   VARCHAR(100),
    brand           VARCHAR(255),
    price           NUMERIC(12, 2),
    dw_created_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    dw_updated_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- dim_date
-- Pre-generated calendar table covering the dataset date range.
-- Using a date dimension instead of extracting date parts inline
-- makes queries cleaner and allows adding business calendar logic later.
DROP TABLE IF EXISTS warehouse.dim_date CASCADE;
CREATE TABLE warehouse.dim_date (
    date_sk         INT             PRIMARY KEY,
    full_date       DATE            NOT NULL UNIQUE,
    year            SMALLINT        NOT NULL,
    quarter         SMALLINT        NOT NULL,
    month           SMALLINT        NOT NULL,
    month_name      VARCHAR(20)     NOT NULL,
    week            SMALLINT        NOT NULL,
    day_of_month    SMALLINT        NOT NULL,
    day_of_week     SMALLINT        NOT NULL,
    day_name        VARCHAR(20)     NOT NULL,
    is_weekend      BOOLEAN         NOT NULL,
    is_month_start  BOOLEAN         NOT NULL,
    is_month_end    BOOLEAN         NOT NULL,
    year_month      CHAR(7)         NOT NULL
);

-- fact_orders
-- Grain: one row per order (one user session with at least one purchase).
DROP TABLE IF EXISTS warehouse.fact_orders CASCADE;
CREATE TABLE warehouse.fact_orders (
    order_sk        BIGSERIAL       PRIMARY KEY,
    order_id        VARCHAR(255)    NOT NULL UNIQUE,
    customer_sk     BIGINT          NOT NULL REFERENCES warehouse.dim_customer (customer_sk),
    date_sk         INT             NOT NULL REFERENCES warehouse.dim_date (date_sk),
    order_date      TIMESTAMPTZ     NOT NULL,
    total_items     INT             NOT NULL,
    total_amount    NUMERIC(12, 2)  NOT NULL,
    status          VARCHAR(50)     NOT NULL,
    dw_created_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- fact_order_items
-- Grain: one row per purchased item (one purchase event = one row).
DROP TABLE IF EXISTS warehouse.fact_order_items CASCADE;
CREATE TABLE warehouse.fact_order_items (
    order_item_sk   BIGSERIAL       PRIMARY KEY,
    order_item_id   BIGINT          NOT NULL UNIQUE,
    order_sk        BIGINT          NOT NULL REFERENCES warehouse.fact_orders (order_sk),
    product_sk      BIGINT          NOT NULL REFERENCES warehouse.dim_product (product_sk),
    date_sk         INT             NOT NULL REFERENCES warehouse.dim_date (date_sk),
    quantity        INT             NOT NULL,
    unit_price      NUMERIC(12, 2),
    line_total      NUMERIC(12, 2),
    dw_created_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fact_orders_customer   ON warehouse.fact_orders (customer_sk);
CREATE INDEX IF NOT EXISTS idx_fact_orders_date        ON warehouse.fact_orders (date_sk);
CREATE INDEX IF NOT EXISTS idx_fact_orders_date_col    ON warehouse.fact_orders (order_date);
CREATE INDEX IF NOT EXISTS idx_fact_items_order        ON warehouse.fact_order_items (order_sk);
CREATE INDEX IF NOT EXISTS idx_fact_items_product      ON warehouse.fact_order_items (product_sk);
CREATE INDEX IF NOT EXISTS idx_fact_items_date         ON warehouse.fact_order_items (date_sk);
CREATE INDEX IF NOT EXISTS idx_dim_product_category    ON warehouse.dim_product (category_main);
CREATE INDEX IF NOT EXISTS idx_dim_product_brand       ON warehouse.dim_product (brand);
