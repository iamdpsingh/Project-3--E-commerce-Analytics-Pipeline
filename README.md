# E-commerce Analytics Pipeline

An end-to-end data engineering project — built locally first, then migrated to GCP.

The source data is a flat eCommerce event log (20M+ rows). The pipeline engineers it into a normalized relational model, loads it through a layered PostgreSQL architecture, builds a star schema data warehouse, and creates SQL analytical views ready for dashboard consumption.

---

## Architecture

```
LOCAL VERSION
─────────────────────────────────────────────
Raw CSV files (20M+ events)
          │
          ▼
    Python / Pandas
    (extract → transform → validate)
          │
          ▼
    PostgreSQL raw.*
    (faithful landing zone)
          │
          ▼
    PostgreSQL staging.*
    (SQL transforms, constraints)
          │
          ▼
    PostgreSQL warehouse.*
    (star schema: facts + dimensions)
          │
          ▼
    PostgreSQL analytics.*
    (SQL views → dashboard)

GCP VERSION (migration target)
─────────────────────────────────────────────
Google Cloud Storage → BigQuery raw
→ BigQuery staging → BigQuery warehouse
→ BigQuery analytics → Dashboard
```

---

## Dataset

**Source:** [eCommerce Events History in Cosmetics Shop](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop)  
**Size:** ~20.7M events across 5 monthly CSV files (Oct 2019 – Feb 2020)  
**GCP version:** [eCommerce Behavior Data from Multi-Category Store](https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store) (~280M events)

The source is a flat event log — each row is one user action (view, cart, purchase). The pipeline engineers this into five normalized entities: customers, products, orders, order_items, and payments.

---

## Project Structure

```
ecommerce-analytics-pipeline/
│
├── src/
│   ├── extract.py          Reads CSVs, derives 5 entity DataFrames from event log
│   ├── transform.py        Cleans data: nulls, types, categoricals, invalid values
│   ├── validate.py         Data quality checks: PKs, FKs, business rules, report
│   ├── load.py             Loads data to PostgreSQL; full and incremental modes
│   ├── analytics.py        Creates analytics views, runs quick KPI summary
│   └── main.py             Pipeline orchestrator — runs all steps end to end
│
├── sql/
│   ├── schema/
│   │   ├── 01_raw_schema.sql         Raw layer table definitions (no constraints)
│   │   ├── 02_staging_schema.sql     Staging layer with PKs, FKs, CHECK constraints
│   │   └── 03_warehouse_schema.sql   Star schema: dims + facts + analytical indexes
│   ├── staging/
│   │   └── 01_raw_to_staging.sql     SQL transforms: CAST, TRIM, COALESCE, CASE
│   ├── warehouse/
│   │   ├── 01_populate_dim_date.sql  Date dimension spine (GENERATE_SERIES)
│   │   ├── 02_populate_dimensions.sql  dim_customer + dim_product population
│   │   └── 03_populate_facts.sql     fact_orders + fact_order_items population
│   └── analytics/
│       └── 01_create_views.sql       8 analytical views (KPIs, revenue, products, etc.)
│
├── data/
│   ├── raw/                          Source CSV files (tracked by Git LFS)
│   └── processed/                    Cleaned CSV files (tracked by Git LFS)
│
├── tests/
│   └── test_environment.py           Verifies all dependencies and DB connection
│
├── docs/
│   └── data_dictionary.md            Column-level documentation for all tables
│
├── logs/                             Pipeline run logs (timestamped)
├── dashboard/                        Dashboard files and screenshots
│
├── .env                              Environment variables (not committed)
├── .gitattributes                    Git LFS tracking for CSV files
├── requirements.txt
└── README.md
```

---

## File Guide

### `src/extract.py`
Reads all CSV files from `data/raw/` and engineers them into five DataFrames. The source is a flat event log — extraction involves groupby aggregations to derive customers from unique user_ids, orders from purchase sessions, and so on. Returns a dict of all entities.

### `src/transform.py`
Cleans each entity DataFrame. Handles: null values in key columns (drop), data types (datetime, int64, float64), categorical standardisation (lowercase + strip), negative prices (→ NaN), zero quantities (→ 1), duplicate primary keys (drop_duplicates). Each entity has its own transform function.

### `src/validate.py`
Runs data quality checks before any data touches the database. Three check types:
- **Primary key checks** — no nulls, no duplicates on PK columns
- **Foreign key checks** — all child values exist in parent DataFrames
- **Business rule checks** — quantity > 0, price >= 0, dates are valid

Produces a `ValidationReport` with per-check pass/fail status. Pipeline halts on critical failures.

### `src/load.py`
Handles all database loading. Key functions:
- `get_engine()` — SQLAlchemy engine with parallel workers disabled (avoids a PostgreSQL 14 timezone bug)
- `load_to_raw()` — full load of all entities to raw.* using chunked inserts
- `verify_raw_counts()` — compares CSV row counts to PostgreSQL counts
- `run_staging_transform()` — executes the raw → staging SQL
- `run_warehouse_load()` — executes all warehouse SQL scripts in order
- `load_incremental()` — append-only mode: finds MAX(date_col) and loads only newer rows

### `src/analytics.py`
Creates the analytics.* schema views by executing `sql/analytics/01_create_views.sql` statement by statement. Also runs a quick KPI summary query to confirm the pipeline worked end to end.

### `src/main.py`
The single entry point for the full pipeline. Runs 10 steps in order with timing, logging, and error handling. Flags: `--mode full|incremental`, `--skip-extract` (reuse processed CSVs). Logs to both console and a timestamped file in `logs/`.

---

## SQL Views

| View | Description |
|------|-------------|
| `analytics.executive_kpis` | Total revenue, orders, customers, AOV, repeat customer % |
| `analytics.monthly_revenue` | Revenue, orders, and AOV by calendar month |
| `analytics.product_performance` | Per-product revenue, quantity sold, revenue rank |
| `analytics.category_performance` | Revenue and share by top-level category |
| `analytics.customer_performance` | Lifetime revenue, order count, repeat buyer flag |
| `analytics.brand_performance` | Revenue and quantity sold by brand |
| `analytics.time_analytics` | Daily orders and revenue for time-series charts |
| `analytics.payment_analysis` | Payment method and status breakdown |

---

## How to Run

### 1. Set up environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure credentials

Edit `.env` with your PostgreSQL connection details:

```
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=ecommerce_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=
```

### 3. Create the database

```bash
createdb ecommerce_db
```

### 4. Download the dataset

Download from Kaggle and place CSV files in `data/raw/`:  
https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop

### 5. Run the pipeline

```bash
# Full load (first run or complete refresh)
python -m src.main

# Re-run without re-extracting (uses saved processed CSVs)
python -m src.main --skip-extract

# Incremental load (append new records only)
python -m src.main --mode incremental

# Verify environment only
python tests/test_environment.py
```

---

## Data Warehouse Model

```
               dim_customer
                    │
                    │ customer_sk
                    ▼
dim_date ────── fact_orders ────── dim_product
  date_sk              │  product_sk
                       │ order_sk
                       ▼
                 fact_order_items
```

**Dimension tables** use surrogate keys (BIGSERIAL) for internal joins and natural keys (original IDs) for traceability back to source data.

**Fact tables** store measures (total_amount, quantity, line_total) and resolve all dimensions to surrogate keys at load time.

---

## Data Quality

The validation layer runs 22 checks before any data is loaded:

- **20 checks passed** on the cosmetics dataset
- **2 warnings** (non-critical): 5 null product prices, 21 orders with negative amounts
- **0 critical failures**

The pipeline continues only when all critical checks pass.

---

## Skills Demonstrated

| Area | What it covers |
|------|---------------|
| Python | Extraction, transformation, validation, orchestration |
| SQL | Joins, aggregations, CTEs, window functions, UPSERT |
| PostgreSQL | Layered architecture (raw → staging → warehouse → analytics) |
| Data Warehousing | Star schema design, surrogate keys, natural keys |
| Data Quality | Validation framework, business rules, quality reports |
| Cloud (upcoming) | GCS + BigQuery, partitioning, clustering |
| BI | Production-style analytical views for dashboard |

---

## Author

Dhruv Pratap Singh
