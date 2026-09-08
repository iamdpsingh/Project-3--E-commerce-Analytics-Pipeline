-- raw_schema.sql
--
-- Creates the raw layer tables. These mirror the entity DataFrames
-- produced by extract.py exactly — no constraints, no transformations.
-- The raw layer is a faithful landing zone for what Python loaded.

CREATE SCHEMA IF NOT EXISTS raw;

-- Full event log — useful for debugging and reprocessing
DROP TABLE IF EXISTS raw.events CASCADE;
CREATE TABLE raw.events (
    event_time      TIMESTAMPTZ,
    event_type      VARCHAR(50),
    product_id      BIGINT,
    category_id     BIGINT,
    category_code   VARCHAR(255),
    brand           VARCHAR(255),
    price           NUMERIC(12, 2),
    user_id         BIGINT,
    user_session    VARCHAR(255),
    _source_file    VARCHAR(255)
);

DROP TABLE IF EXISTS raw.customers CASCADE;
CREATE TABLE raw.customers (
    user_id         BIGINT,
    first_seen_at   TIMESTAMPTZ,
    last_seen_at    TIMESTAMPTZ,
    total_events    BIGINT,
    total_sessions  BIGINT
);

DROP TABLE IF EXISTS raw.products CASCADE;
CREATE TABLE raw.products (
    product_id      BIGINT,
    category_id     BIGINT,
    category_code   VARCHAR(255),
    brand           VARCHAR(255),
    price           NUMERIC(12, 2)
);

DROP TABLE IF EXISTS raw.orders CASCADE;
CREATE TABLE raw.orders (
    order_id        VARCHAR(255),
    user_id         BIGINT,
    order_date      TIMESTAMPTZ,
    total_items     INT,
    total_amount    NUMERIC(12, 2),
    status          VARCHAR(50)
);

DROP TABLE IF EXISTS raw.order_items CASCADE;
CREATE TABLE raw.order_items (
    order_item_id   BIGINT,
    order_id        VARCHAR(255),
    product_id      BIGINT,
    quantity        INT,
    price           NUMERIC(12, 2),
    event_time      TIMESTAMPTZ
);

DROP TABLE IF EXISTS raw.payments CASCADE;
CREATE TABLE raw.payments (
    payment_id      BIGINT,
    order_id        VARCHAR(255),
    payment_date    TIMESTAMPTZ,
    payment_value   NUMERIC(12, 2),
    payment_method  VARCHAR(100),
    payment_status  VARCHAR(50)
);
