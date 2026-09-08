"""
transform.py

Cleans and standardises each entity DataFrame produced by extract.py.
All transformations run in Python/Pandas — no database required.

What happens here:
    - Column names are normalised to snake_case
    - Null values in key columns are dropped
    - Data types are enforced (dates as datetime, IDs as int64, etc.)
    - Categorical columns are lowercased and stripped
    - Invalid values (negative prices, zero quantities) are flagged or corrected
    - Duplicates on primary keys are removed
"""

import logging
import re

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _to_snake_case(col: str) -> str:
    col = re.sub(r"[\s\-]+", "_", col.strip().lower())
    col = re.sub(r"[^a-z0-9_]", "", col)
    return col


def _standardise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [_to_snake_case(c) for c in df.columns]
    return df


def _log_nulls(df: pd.DataFrame, label: str) -> None:
    nulls = df.isnull().sum()
    nulls = nulls[nulls > 0]
    if not nulls.empty:
        logger.warning(f"[{label}] Null counts:\n{nulls.to_string()}")
    else:
        logger.info(f"[{label}] No nulls found.")


def _log_duplicates(df: pd.DataFrame, key: str, label: str) -> None:
    dupes = df.duplicated(subset=[key]).sum()
    if dupes:
        logger.warning(f"[{label}] {dupes:,} duplicate {key}s found.")
    else:
        logger.info(f"[{label}] No duplicate {key}s.")


def transform_customers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the customers DataFrame.

    Drops rows with null user_ids, enforces integer type on the key,
    parses date columns, and removes any duplicate users.
    """
    logger.info("Transforming customers ...")
    df = _standardise_columns(df.copy())

    before = len(df)
    df = df.dropna(subset=["user_id"])
    if dropped := before - len(df):
        logger.warning(f"  Dropped {dropped:,} rows with null user_id")

    df["user_id"] = df["user_id"].astype("int64")

    for col in ["first_seen_at", "last_seen_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    for col in ["total_events", "total_sessions"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")

    _log_duplicates(df, "user_id", "customers")
    df = df.drop_duplicates(subset=["user_id"], keep="first").reset_index(drop=True)
    _log_nulls(df, "customers")
    logger.info(f"  customers clean shape: {df.shape}")
    return df


def transform_products(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the products DataFrame.

    Standardises category_code and brand to lowercase, replaces
    empty strings with 'unknown', and nullifies any negative prices
    (which are data errors in the source).
    """
    logger.info("Transforming products ...")
    df = _standardise_columns(df.copy())

    before = len(df)
    df = df.dropna(subset=["product_id"])
    if dropped := before - len(df):
        logger.warning(f"  Dropped {dropped:,} rows with null product_id")

    df["product_id"] = df["product_id"].astype("int64")
    df["category_id"] = pd.to_numeric(df.get("category_id"), errors="coerce").astype("Int64")

    for col in ["category_code", "brand"]:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .str.lower()
                .replace({"nan": "unknown", "": "unknown"})
            )

    df["price"] = pd.to_numeric(df.get("price"), errors="coerce")
    invalid_price = (df["price"] < 0).sum()
    if invalid_price:
        logger.warning(f"  {invalid_price:,} products have negative price — setting to NaN")
        df.loc[df["price"] < 0, "price"] = np.nan

    _log_duplicates(df, "product_id", "products")
    df = df.drop_duplicates(subset=["product_id"], keep="first").reset_index(drop=True)
    _log_nulls(df, "products")
    logger.info(f"  products clean shape: {df.shape}")
    return df


def transform_orders(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the orders DataFrame.

    Validates that all order dates parse correctly, enforces integer
    type on user_id, and logs business rule violations (negative amounts,
    zero item counts) as warnings without dropping those rows.
    """
    logger.info("Transforming orders ...")
    df = _standardise_columns(df.copy())

    before = len(df)
    df = df.dropna(subset=["order_id", "user_id"])
    if dropped := before - len(df):
        logger.warning(f"  Dropped {dropped:,} rows with null order/user id")

    df["user_id"] = df["user_id"].astype("int64")
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce", utc=True)

    invalid_dates = df["order_date"].isna().sum()
    if invalid_dates:
        logger.warning(f"  {invalid_dates:,} orders with invalid date — dropping")
        df = df.dropna(subset=["order_date"])

    df["total_items"] = pd.to_numeric(df.get("total_items"), errors="coerce").fillna(0).astype("int64")
    df["total_amount"] = pd.to_numeric(df.get("total_amount"), errors="coerce")

    bad_qty = (df["total_items"] <= 0).sum()
    if bad_qty:
        logger.warning(f"  {bad_qty:,} orders with total_items <= 0")

    bad_amt = (df["total_amount"] < 0).sum()
    if bad_amt:
        logger.warning(f"  {bad_amt:,} orders with negative total_amount")

    if "status" in df.columns:
        df["status"] = df["status"].astype(str).str.strip().str.lower()

    _log_duplicates(df, "order_id", "orders")
    df = df.drop_duplicates(subset=["order_id"], keep="first").reset_index(drop=True)
    _log_nulls(df, "orders")
    logger.info(f"  orders clean shape: {df.shape}")
    return df


def transform_order_items(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the order items DataFrame.

    Enforces quantity > 0 (setting invalid quantities to 1),
    nullifies negative prices, and drops rows missing any key column.
    """
    logger.info("Transforming order_items ...")
    df = _standardise_columns(df.copy())

    before = len(df)
    df = df.dropna(subset=["order_item_id", "order_id", "product_id"])
    if dropped := before - len(df):
        logger.warning(f"  Dropped {dropped:,} rows with null key columns")

    df["order_item_id"] = df["order_item_id"].astype("int64")
    df["product_id"] = df["product_id"].astype("int64")
    df["quantity"] = pd.to_numeric(df.get("quantity"), errors="coerce").fillna(1).astype("int64")
    df["price"] = pd.to_numeric(df.get("price"), errors="coerce")
    df["event_time"] = pd.to_datetime(df.get("event_time"), errors="coerce", utc=True)

    bad_qty = (df["quantity"] <= 0).sum()
    if bad_qty:
        logger.warning(f"  {bad_qty:,} order_items with quantity <= 0 — setting to 1")
        df.loc[df["quantity"] <= 0, "quantity"] = 1

    bad_price = (df["price"] < 0).sum()
    if bad_price:
        logger.warning(f"  {bad_price:,} order_items with negative price — setting to NaN")
        df.loc[df["price"] < 0, "price"] = np.nan

    _log_duplicates(df, "order_item_id", "order_items")
    df = df.drop_duplicates(subset=["order_item_id"], keep="first").reset_index(drop=True)
    _log_nulls(df, "order_items")
    logger.info(f"  order_items clean shape: {df.shape}")
    return df


def transform_payments(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the payments DataFrame.

    Standardises payment_method and payment_status to lowercase,
    nullifies negative payment values, and drops rows missing
    the primary or foreign key.
    """
    logger.info("Transforming payments ...")
    df = _standardise_columns(df.copy())

    before = len(df)
    df = df.dropna(subset=["payment_id", "order_id"])
    if dropped := before - len(df):
        logger.warning(f"  Dropped {dropped:,} rows with null key columns")

    df["payment_id"] = df["payment_id"].astype("int64")
    df["payment_value"] = pd.to_numeric(df.get("payment_value"), errors="coerce")
    df["payment_date"] = pd.to_datetime(df.get("payment_date"), errors="coerce", utc=True)

    bad_val = (df["payment_value"] < 0).sum()
    if bad_val:
        logger.warning(f"  {bad_val:,} payments with negative value — setting to NaN")
        df.loc[df["payment_value"] < 0, "payment_value"] = np.nan

    for col in ["payment_method", "payment_status"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower()

    _log_duplicates(df, "payment_id", "payments")
    df = df.drop_duplicates(subset=["payment_id"], keep="first").reset_index(drop=True)
    _log_nulls(df, "payments")
    logger.info(f"  payments clean shape: {df.shape}")
    return df


def transform_all(extracted: dict) -> dict:
    """
    Run all entity transformations and return a dict of clean DataFrames.

    The input is the dict returned by extract.extraction_summary.
    The raw events DataFrame is passed through unchanged since it's
    only needed during extraction.
    """
    return {
        "events":      extracted["events"],
        "customers":   transform_customers(extracted["customers"]),
        "products":    transform_products(extracted["products"]),
        "orders":      transform_orders(extracted["orders"]),
        "order_items": transform_order_items(extracted["order_items"]),
        "payments":    transform_payments(extracted["payments"]),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    from src.extract import load_raw_events, extraction_summary
    events = load_raw_events()
    extracted = extraction_summary(events)
    cleaned = transform_all(extracted)

    print("\n  TRANSFORMATION SUMMARY")
    print("  " + "-" * 43)
    for entity, df in cleaned.items():
        if entity != "events":
            print(f"  {entity:<15}: {len(df):>10,} rows | {df.shape[1]} cols")
