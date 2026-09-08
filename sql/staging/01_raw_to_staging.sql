-- raw_to_staging.sql
--
-- Transforms data from the raw layer into the staging layer.
-- This is where SQL-native transformations happen:
-- CAST, TRIM, COALESCE, CASE, and referential integrity filtering.
--
-- Each entity is loaded with UPSERT (ON CONFLICT DO UPDATE) so
-- the script is safe to run repeatedly without creating duplicates.

-- Customers
TRUNCATE staging.customers RESTART IDENTITY CASCADE;

INSERT INTO staging.customers (
    user_id, first_seen_at, last_seen_at,
    total_events, total_sessions
)
SELECT
    user_id::BIGINT,
    first_seen_at::TIMESTAMPTZ,
    last_seen_at::TIMESTAMPTZ,
    COALESCE(total_events, 0)::INT,
    COALESCE(total_sessions, 0)::INT
FROM raw.customers
WHERE user_id IS NOT NULL
ON CONFLICT (user_id) DO UPDATE
    SET first_seen_at  = EXCLUDED.first_seen_at,
        last_seen_at   = EXCLUDED.last_seen_at,
        total_events   = EXCLUDED.total_events,
        total_sessions = EXCLUDED.total_sessions,
        loaded_at      = NOW();

-- Products
TRUNCATE staging.products RESTART IDENTITY CASCADE;

INSERT INTO staging.products (
    product_id, category_id, category_code, brand, price
)
SELECT
    product_id::BIGINT,
    category_id::BIGINT,
    LOWER(TRIM(COALESCE(NULLIF(category_code, ''), 'unknown'))),
    LOWER(TRIM(COALESCE(NULLIF(brand, ''), 'unknown'))),
    CASE
        WHEN price < 0 THEN NULL
        ELSE price::NUMERIC(12,2)
    END
FROM raw.products
WHERE product_id IS NOT NULL
ON CONFLICT (product_id) DO UPDATE
    SET category_id   = EXCLUDED.category_id,
        category_code = EXCLUDED.category_code,
        brand         = EXCLUDED.brand,
        price         = EXCLUDED.price,
        loaded_at     = NOW();

-- Orders
-- Only include orders whose user_id exists in staging.customers.
-- This enforces referential integrity at the SQL level.
TRUNCATE staging.orders RESTART IDENTITY CASCADE;

INSERT INTO staging.orders (
    order_id, user_id, order_date, total_items, total_amount, status
)
SELECT
    TRIM(order_id),
    user_id::BIGINT,
    order_date::TIMESTAMPTZ,
    COALESCE(total_items, 0)::INT,
    COALESCE(total_amount, 0)::NUMERIC(12,2),
    LOWER(TRIM(COALESCE(status, 'completed')))
FROM raw.orders
WHERE order_id   IS NOT NULL
  AND user_id    IS NOT NULL
  AND order_date IS NOT NULL
  AND user_id IN (SELECT user_id FROM staging.customers)
ON CONFLICT (order_id) DO UPDATE
    SET order_date   = EXCLUDED.order_date,
        total_items  = EXCLUDED.total_items,
        total_amount = EXCLUDED.total_amount,
        status       = EXCLUDED.status,
        loaded_at    = NOW();

-- Order items
-- Only include items whose order_id and product_id exist in staging.
TRUNCATE staging.order_items RESTART IDENTITY CASCADE;

INSERT INTO staging.order_items (
    order_item_id, order_id, product_id, quantity, price, event_time
)
SELECT
    order_item_id::BIGINT,
    TRIM(order_id),
    product_id::BIGINT,
    GREATEST(COALESCE(quantity, 1)::INT, 1),
    CASE
        WHEN price < 0 THEN NULL
        ELSE price::NUMERIC(12,2)
    END,
    event_time::TIMESTAMPTZ
FROM raw.order_items
WHERE order_item_id IS NOT NULL
  AND order_id      IS NOT NULL
  AND product_id    IS NOT NULL
  AND order_id   IN (SELECT order_id   FROM staging.orders)
  AND product_id IN (SELECT product_id FROM staging.products)
ON CONFLICT (order_item_id) DO NOTHING;

-- Payments
TRUNCATE staging.payments RESTART IDENTITY CASCADE;

INSERT INTO staging.payments (
    payment_id, order_id, payment_date, payment_value,
    payment_method, payment_status
)
SELECT
    payment_id::BIGINT,
    TRIM(order_id),
    payment_date::TIMESTAMPTZ,
    COALESCE(payment_value, 0)::NUMERIC(12,2),
    LOWER(TRIM(COALESCE(NULLIF(payment_method, ''), 'unknown'))),
    LOWER(TRIM(COALESCE(NULLIF(payment_status, ''), 'paid')))
FROM raw.payments
WHERE payment_id IS NOT NULL
  AND order_id   IS NOT NULL
  AND order_id IN (SELECT order_id FROM staging.orders)
ON CONFLICT (payment_id) DO NOTHING;
