# Data Dictionary — E-commerce Analytics Pipeline

**Source:** eCommerce Events History in Cosmetics Shop  
**Dataset:** Kaggle — mkechinov/ecommerce-events-history-in-cosmetics-shop  
**Coverage:** Oct 2019 – Feb 2020  
**Schema engineered from:** flat event logs → normalized relational model

---

## Source Event Schema (Raw CSV)

| Column | Data Type | Description | Notes |
|--------|-----------|-------------|-------|
| `event_time` | TIMESTAMPTZ | When the event occurred (UTC) | Parse as datetime |
| `event_type` | VARCHAR(50) | Type of event | `view`, `cart`, `remove_from_cart`, `purchase` |
| `product_id` | BIGINT | Product identifier | Natural key |
| `category_id` | BIGINT | Category identifier | Internal ID |
| `category_code` | VARCHAR(255) | Hierarchical category name | Dot-separated, e.g. `electronics.audio` |
| `brand` | VARCHAR(255) | Product brand name | Lowercase; may be null |
| `price` | NUMERIC(12,2) | Product price in USD | May vary across events for same product |
| `user_id` | BIGINT | Permanent user identifier | Natural key |
| `user_session` | VARCHAR(255) | Session identifier | Changes when user returns after long break |

---

## Derived Entity Tables

### `customers` (derived from unique `user_id`)

| Column | Data Type | PK | FK | Nullable | Description |
|--------|-----------|----|----|----------|-------------|
| `user_id` | BIGINT | ✓ | — | NO | Permanent user identifier |
| `first_seen_at` | TIMESTAMPTZ | — | — | NO | Earliest event for this user |
| `last_seen_at` | TIMESTAMPTZ | — | — | NO | Latest event for this user |
| `total_events` | INT | — | — | NO | Count of all events |
| `total_sessions` | INT | — | — | NO | Count of distinct sessions |

---

### `products` (derived from unique `product_id`)

| Column | Data Type | PK | FK | Nullable | Description |
|--------|-----------|----|----|----------|-------------|
| `product_id` | BIGINT | ✓ | — | NO | Product identifier |
| `category_id` | BIGINT | — | — | YES | Internal category ID |
| `category_code` | VARCHAR(255) | — | — | NO | Full category path (e.g. `cosmetics.fragrance`) |
| `brand` | VARCHAR(255) | — | — | NO | Brand name (default: `unknown`) |
| `price` | NUMERIC(12,2) | — | — | YES | Most recent price observed |

---

### `orders` (derived from purchase sessions)

> One order = one `user_session` with at least one `purchase` event

| Column | Data Type | PK | FK | Nullable | Description |
|--------|-----------|----|----|----------|-------------|
| `order_id` | VARCHAR(255) | ✓ | — | NO | `user_session` UUID |
| `user_id` | BIGINT | — | customers | NO | Buyer |
| `order_date` | TIMESTAMPTZ | — | — | NO | First purchase event in session |
| `total_items` | INT | — | — | NO | Count of purchase events in session |
| `total_amount` | NUMERIC(12,2) | — | — | NO | Sum of prices in session |
| `status` | VARCHAR(50) | — | — | NO | Always `completed` |

---

### `order_items` (one row per purchase event)

| Column | Data Type | PK | FK | Nullable | Description |
|--------|-----------|----|----|----------|-------------|
| `order_item_id` | BIGINT | ✓ | — | NO | Surrogate integer index |
| `order_id` | VARCHAR(255) | — | orders | NO | FK → orders |
| `product_id` | BIGINT | — | products | NO | FK → products |
| `quantity` | INT | — | — | NO | Always 1 (one event = one item) |
| `price` | NUMERIC(12,2) | — | — | YES | Unit price at time of purchase |
| `event_time` | TIMESTAMPTZ | — | — | YES | Exact timestamp of purchase |

---

### `payments` (derived: one per order)

> Derived because no payment table exists in source. Amount = `total_amount` per order.

| Column | Data Type | PK | FK | Nullable | Description |
|--------|-----------|----|----|----------|-------------|
| `payment_id` | BIGINT | ✓ | — | NO | Surrogate integer index |
| `order_id` | VARCHAR(255) | — | orders | NO | FK → orders |
| `payment_date` | TIMESTAMPTZ | — | — | NO | Same as `order_date` |
| `payment_value` | NUMERIC(12,2) | — | — | NO | Total order amount |
| `payment_method` | VARCHAR(100) | — | — | NO | Always `unknown` (not in source) |
| `payment_status` | VARCHAR(50) | — | — | NO | Always `paid` |

---

## Warehouse Tables (Star Schema)

### `warehouse.dim_customer`

| Column | Data Type | Key Type | Description |
|--------|-----------|----------|-------------|
| `customer_sk` | BIGSERIAL | Surrogate PK | Auto-increment |
| `user_id` | BIGINT | Natural key | Original user_id |
| `first_seen_at` | TIMESTAMPTZ | — | From customers |
| `last_seen_at` | TIMESTAMPTZ | — | From customers |
| `total_events` | INT | — | Total activity count |
| `total_sessions` | INT | — | Session count |
| `is_repeat_buyer` | BOOLEAN | — | Has > 1 order |
| `dw_created_at` | TIMESTAMPTZ | — | DW load timestamp |
| `dw_updated_at` | TIMESTAMPTZ | — | Last update timestamp |

---

### `warehouse.dim_product`

| Column | Data Type | Key Type | Description |
|--------|-----------|----------|-------------|
| `product_sk` | BIGSERIAL | Surrogate PK | Auto-increment |
| `product_id` | BIGINT | Natural key | Original product_id |
| `category_id` | BIGINT | — | Source category ID |
| `category_code` | VARCHAR(255) | — | Full category path |
| `category_main` | VARCHAR(100) | — | Top-level category (derived) |
| `brand` | VARCHAR(255) | — | Brand name |
| `price` | NUMERIC(12,2) | — | List price |

---

### `warehouse.dim_date`

| Column | Data Type | Key Type | Description |
|--------|-----------|----------|-------------|
| `date_sk` | INT | Surrogate PK | YYYYMMDD integer |
| `full_date` | DATE | Natural key | Calendar date |
| `year` | SMALLINT | — | Calendar year |
| `quarter` | SMALLINT | — | Quarter (1-4) |
| `month` | SMALLINT | — | Month (1-12) |
| `month_name` | VARCHAR(20) | — | Month name |
| `week` | SMALLINT | — | ISO week number |
| `day_of_month` | SMALLINT | — | Day (1-31) |
| `day_of_week` | SMALLINT | — | ISO day (1=Mon, 7=Sun) |
| `day_name` | VARCHAR(20) | — | Day name |
| `is_weekend` | BOOLEAN | — | Saturday or Sunday |
| `is_month_start` | BOOLEAN | — | First day of month |
| `is_month_end` | BOOLEAN | — | Last day of month |
| `year_month` | CHAR(7) | — | 'YYYY-MM' string |

---

### `warehouse.fact_orders`

| Column | Data Type | Key Type | Description |
|--------|-----------|----------|-------------|
| `order_sk` | BIGSERIAL | Surrogate PK | Auto-increment |
| `order_id` | VARCHAR(255) | Natural key | User session ID |
| `customer_sk` | BIGINT | FK → dim_customer | Resolved surrogate |
| `date_sk` | INT | FK → dim_date | Order date key |
| `order_date` | TIMESTAMPTZ | — | Full timestamp |
| `total_items` | INT | — | Item count |
| `total_amount` | NUMERIC(12,2) | — | Order total |
| `status` | VARCHAR(50) | — | Order status |

---

### `warehouse.fact_order_items`

| Column | Data Type | Key Type | Description |
|--------|-----------|----------|-------------|
| `order_item_sk` | BIGSERIAL | Surrogate PK | Auto-increment |
| `order_item_id` | BIGINT | Natural key | Original ID |
| `order_sk` | BIGINT | FK → fact_orders | Parent order |
| `product_sk` | BIGINT | FK → dim_product | Product reference |
| `date_sk` | INT | FK → dim_date | Event date key |
| `quantity` | INT | — | Units purchased |
| `unit_price` | NUMERIC(12,2) | — | Price per unit |
| `line_total` | NUMERIC(12,2) | — | quantity × unit_price |

---

## Relationships

```
customers (user_id)
    │
    ├── orders.user_id
    │       │
    │       ├── order_items.order_id
    │       │       │
    │       │       └── products (product_id)
    │       │
    │       └── payments.order_id
    │
    └── warehouse.dim_customer (user_id)
            │
            └── warehouse.fact_orders (customer_sk)
                    │
                    └── warehouse.fact_order_items (order_sk)
                            │
                            └── warehouse.dim_product (product_sk)
```
