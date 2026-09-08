-- staging_schema.sql
--
-- Cleaned, typed, constrained versions of the raw tables.
-- This is where data quality is enforced at the database level:
-- primary keys, foreign keys, NOT NULL constraints, and CHECK constraints.
-- The staging layer is what downstream warehouse transforms read from.

CREATE SCHEMA IF NOT EXISTS staging;

DROP TABLE IF EXISTS staging.customers CASCADE;
CREATE TABLE staging.customers (
    user_id         BIGINT          PRIMARY KEY,
    first_seen_at   TIMESTAMPTZ     NOT NULL,
    last_seen_at    TIMESTAMPTZ     NOT NULL,
    total_events    INT             NOT NULL DEFAULT 0,
    total_sessions  INT             NOT NULL DEFAULT 0,
    loaded_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS staging.products CASCADE;
CREATE TABLE staging.products (
    product_id      BIGINT          PRIMARY KEY,
    category_id     BIGINT,
    category_code   VARCHAR(255)    NOT NULL DEFAULT 'unknown',
    brand           VARCHAR(255)    NOT NULL DEFAULT 'unknown',
    price           NUMERIC(12, 2),
    loaded_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Orders must reference a known customer
DROP TABLE IF EXISTS staging.orders CASCADE;
CREATE TABLE staging.orders (
    order_id        VARCHAR(255)    PRIMARY KEY,
    user_id         BIGINT          NOT NULL,
    order_date      TIMESTAMPTZ     NOT NULL,
    total_items     INT             NOT NULL,
    total_amount    NUMERIC(12, 2)  NOT NULL,
    status          VARCHAR(50)     NOT NULL DEFAULT 'completed',
    loaded_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_order_customer FOREIGN KEY (user_id) REFERENCES staging.customers (user_id)
);

-- Each item must reference a valid order and product
DROP TABLE IF EXISTS staging.order_items CASCADE;
CREATE TABLE staging.order_items (
    order_item_id   BIGINT          PRIMARY KEY,
    order_id        VARCHAR(255)    NOT NULL,
    product_id      BIGINT          NOT NULL,
    quantity        INT             NOT NULL DEFAULT 1 CHECK (quantity > 0),
    price           NUMERIC(12, 2),
    event_time      TIMESTAMPTZ,
    loaded_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_item_order   FOREIGN KEY (order_id)   REFERENCES staging.orders (order_id),
    CONSTRAINT fk_item_product FOREIGN KEY (product_id) REFERENCES staging.products (product_id)
);

-- Each payment must reference a valid order
DROP TABLE IF EXISTS staging.payments CASCADE;
CREATE TABLE staging.payments (
    payment_id      BIGINT          PRIMARY KEY,
    order_id        VARCHAR(255)    NOT NULL,
    payment_date    TIMESTAMPTZ     NOT NULL,
    payment_value   NUMERIC(12, 2)  NOT NULL,
    payment_method  VARCHAR(100)    NOT NULL DEFAULT 'unknown',
    payment_status  VARCHAR(50)     NOT NULL DEFAULT 'paid',
    loaded_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_payment_order FOREIGN KEY (order_id) REFERENCES staging.orders (order_id)
);
