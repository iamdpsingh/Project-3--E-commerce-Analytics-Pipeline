-- populate_facts.sql
--
-- Populates fact_orders and fact_order_items from the staging layer.
-- Joins to dimension tables to resolve natural keys → surrogate keys.
-- line_total is computed here as quantity × unit_price.

TRUNCATE warehouse.fact_orders CASCADE;

INSERT INTO warehouse.fact_orders (
    order_id, customer_sk, date_sk, order_date,
    total_items, total_amount, status
)
SELECT
    o.order_id,
    dc.customer_sk,
    TO_CHAR(o.order_date AT TIME ZONE 'UTC', 'YYYYMMDD')::INT AS date_sk,
    o.order_date,
    o.total_items,
    o.total_amount,
    o.status
FROM staging.orders o
JOIN warehouse.dim_customer dc ON dc.user_id  = o.user_id
JOIN warehouse.dim_date     dd ON dd.date_sk  = TO_CHAR(o.order_date AT TIME ZONE 'UTC', 'YYYYMMDD')::INT;

TRUNCATE warehouse.fact_order_items CASCADE;

INSERT INTO warehouse.fact_order_items (
    order_item_id, order_sk, product_sk, date_sk,
    quantity, unit_price, line_total
)
SELECT
    oi.order_item_id,
    fo.order_sk,
    dp.product_sk,
    TO_CHAR(oi.event_time AT TIME ZONE 'UTC', 'YYYYMMDD')::INT AS date_sk,
    oi.quantity,
    oi.price                    AS unit_price,
    (oi.quantity * oi.price)    AS line_total
FROM staging.order_items oi
JOIN warehouse.fact_orders  fo ON fo.order_id   = oi.order_id
JOIN warehouse.dim_product  dp ON dp.product_id = oi.product_id
JOIN warehouse.dim_date     dd ON dd.date_sk     = TO_CHAR(oi.event_time AT TIME ZONE 'UTC', 'YYYYMMDD')::INT;
