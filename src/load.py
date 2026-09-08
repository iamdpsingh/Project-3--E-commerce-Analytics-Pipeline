"""
load.py

Handles all database loading operations:
    - DataFrame → raw.* (full load or incremental)
    - Row count verification after loading
    - raw.* → staging.* (via SQL)
    - staging.* → warehouse.* (via SQL)
    - Incremental detection using MAX(date column)

The engine is configured to disable parallel query workers.
This prevents issues with broken PostgreSQL timezone installations
where parallel workers fail to open the timezonesets directory.
"""

import os
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def get_engine():
    """
    Create a SQLAlchemy engine from environment variables.

    Parallel workers are disabled at the session level because
    PostgreSQL 14's parallel worker processes can fail to load
    timezone data when the installation is incomplete or relocated.
    Setting max_parallel_workers_per_gather=0 keeps all queries
    on a single process and avoids the issue entirely.
    """
    host     = os.getenv("POSTGRES_HOST",     "127.0.0.1")
    port     = os.getenv("POSTGRES_PORT",     "5432")
    db       = os.getenv("POSTGRES_DB",       "ecommerce_db")
    user     = os.getenv("POSTGRES_USER",     "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"options": "-c max_parallel_workers_per_gather=0"},
    )
    logger.debug(f"Engine created: {host}:{port}/{db}")
    return engine


def run_sql_file(engine, sql_path: str | Path) -> None:
    """Execute a SQL file against the connected database."""
    sql_path = Path(sql_path)
    logger.info(f"Running SQL: {sql_path.name}")
    sql = sql_path.read_text()
    with engine.begin() as conn:
        conn.execute(text(sql))
    logger.info(f"  → {sql_path.name} completed")


def setup_schemas(engine) -> None:
    """
    Create all schemas and tables by running the DDL files in order.

    This is idempotent — all statements use CREATE TABLE IF NOT EXISTS
    or DROP ... CASCADE before recreating, so it's safe to run repeatedly.
    """
    sql_base = Path("sql/schema")
    for f in sorted(sql_base.glob("*.sql")):
        run_sql_file(engine, f)
    logger.info("Schema setup complete.")


def load_to_raw(
    cleaned: dict,
    engine,
    chunksize: int = 50_000,
    if_exists: str = "replace",
) -> dict[str, int]:
    """
    Load all entity DataFrames into the raw.* schema.

    Uses pandas to_sql with chunked inserts for memory efficiency.
    Returns a dict of {table_name: rows_loaded} for verification.

    Args:
        cleaned   : dict of {entity_name: DataFrame}
        engine    : SQLAlchemy engine
        chunksize : rows per batch
        if_exists : 'replace' truncates and reloads; 'append' adds new rows
    """
    table_map = {
        "customers":   "raw.customers",
        "products":    "raw.products",
        "orders":      "raw.orders",
        "order_items": "raw.order_items",
        "payments":    "raw.payments",
    }
    loaded_counts = {}

    for entity, table in table_map.items():
        df = cleaned.get(entity)
        if df is None or len(df) == 0:
            logger.warning(f"  Skipping {table} — no data")
            continue

        schema, tname = table.split(".")
        logger.info(f"  Loading {len(df):,} rows → {table} ...")
        df.to_sql(
            name=tname, schema=schema, con=engine,
            if_exists=if_exists, index=False,
            chunksize=chunksize, method="multi",
        )
        loaded_counts[table] = len(df)
        logger.info(f"  ✓ {table}: {len(df):,} rows loaded")

    return loaded_counts


def verify_raw_counts(cleaned: dict, loaded_counts: dict, engine) -> bool:
    """
    Compare source DataFrame row counts to what actually landed in raw.*.

    This is a standard data engineering sanity check: the number of rows
    in the source must exactly match the number stored in the database.
    Any discrepancy indicates a truncation, encoding issue, or insert failure.
    """
    logger.info("Verifying row counts (CSV vs PostgreSQL) ...")

    table_map = {
        "customers":   "raw.customers",
        "products":    "raw.products",
        "orders":      "raw.orders",
        "order_items": "raw.order_items",
        "payments":    "raw.payments",
    }

    all_match = True
    print("\n" + "-" * 50)
    print("  ROW COUNT VERIFICATION (CSV → PostgreSQL raw)")
    print("-" * 50)
    print(f"  {'Table':<25} {'CSV':>10} {'PG raw':>10} {'Match':>6}")
    print("-" * 50)

    with engine.connect() as conn:
        for entity, table in table_map.items():
            df = cleaned.get(entity)
            if df is None:
                continue
            csv_count = len(df)
            schema, tname = table.split(".")
            pg_count = conn.execute(
                text(f"SELECT COUNT(*) FROM {schema}.{tname}")
            ).scalar()
            match = (csv_count == pg_count)
            if not match:
                all_match = False
            icon = "✓" if match else "✗"
            print(f"  {table:<25} {csv_count:>10,} {pg_count:>10,} {icon:>6}")

    print("-" * 50)
    print(f"  Result: {'✅ All counts match' if all_match else '❌ Count mismatch detected!'}")
    print("-" * 50 + "\n")

    return all_match


def run_staging_transform(engine) -> None:
    """Run the raw → staging SQL transformation script."""
    run_sql_file(engine, "sql/staging/01_raw_to_staging.sql")


def run_warehouse_load(engine) -> None:
    """
    Populate the warehouse layer by running SQL scripts in order:
    date dimension first, then other dimensions, then fact tables.

    The order matters because the fact tables reference the dimensions
    via foreign key constraints.
    """
    for sql_file in sorted(Path("sql/warehouse").glob("*.sql")):
        run_sql_file(engine, sql_file)


def get_last_loaded_date(engine, table: str, date_col: str) -> Optional[str]:
    """Return the MAX value of a date column in a given table."""
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT MAX({date_col}) FROM {table}")
        ).scalar()
    return str(result) if result else None


def load_incremental(
    df: pd.DataFrame,
    entity: str,
    engine,
    date_col: str = "order_date",
    chunksize: int = 50_000,
) -> int:
    """
    Append only records newer than the last loaded date.

    Finds MAX(date_col) in the existing raw table, filters the input
    DataFrame to only rows after that date, then appends them.
    On first run (empty table) it loads everything.

    Returns the number of new rows appended.
    """
    table  = f"raw.{entity}"
    schema = "raw"
    tname  = entity

    last_date = get_last_loaded_date(engine, table, date_col)
    if last_date:
        logger.info(f"  Incremental load: {entity} — last loaded = {last_date}")
        df = df[df[date_col].astype(str) > last_date].copy()
    else:
        logger.info(f"  First load detected for {entity} — loading all records")

    if len(df) == 0:
        logger.info(f"  No new records for {entity}.")
        return 0

    logger.info(f"  Appending {len(df):,} new rows → {table}")
    df.to_sql(
        name=tname, schema=schema, con=engine,
        if_exists="append", index=False,
        chunksize=chunksize, method="multi",
    )
    logger.info(f"  ✓ {table}: {len(df):,} new rows appended")
    return len(df)


def verify_staging_counts(engine) -> None:
    """Print row counts for all staging tables."""
    tables = [
        "staging.customers", "staging.products", "staging.orders",
        "staging.order_items", "staging.payments",
    ]
    print("\n" + "-" * 40)
    print("  STAGING TABLE COUNTS")
    print("-" * 40)
    with engine.connect() as conn:
        for table in tables:
            schema, tname = table.split(".")
            count = conn.execute(
                text(f"SELECT COUNT(*) FROM {schema}.{tname}")
            ).scalar()
            print(f"  {table:<30}: {count:>10,}")
    print("-" * 40 + "\n")


def verify_warehouse_counts(engine) -> None:
    """Print row counts for all warehouse tables."""
    tables = [
        "warehouse.dim_customer", "warehouse.dim_product",
        "warehouse.dim_date",
        "warehouse.fact_orders", "warehouse.fact_order_items",
    ]
    print("\n" + "-" * 45)
    print("  WAREHOUSE TABLE COUNTS")
    print("-" * 45)
    with engine.connect() as conn:
        for table in tables:
            schema, tname = table.split(".")
            count = conn.execute(
                text(f"SELECT COUNT(*) FROM {schema}.{tname}")
            ).scalar()
            print(f"  {table:<35}: {count:>10,}")
    print("-" * 45 + "\n")
