"""
extract.py

Reads raw eCommerce event CSV files and engineers them into five
logical DataFrames: customers, products, orders, order_items, payments.

The source data is a flat event log (one row = one user action).
We derive a normalized relational model from it here — this is the
core engineering step that makes the rest of the pipeline possible.

Source CSV columns:
    event_time, event_type, product_id, category_id,
    category_code, brand, price, user_id, user_session
"""

import os
import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

RAW_PATH = Path(os.getenv("RAW_DATA_PATH", "data/raw"))

# Only read the columns we actually use, with explicit types.
# This keeps memory under control on 20M+ row files.
DTYPES = {
    "event_type":    "category",
    "product_id":    "int64",
    "category_id":   "int64",
    "category_code": "str",
    "brand":         "str",
    "price":         "float64",
    "user_id":       "int64",
    "user_session":  "str",
}


def load_raw_events() -> pd.DataFrame:
    """
    Load all CSV files from data/raw/ into a single DataFrame.

    Each monthly file is read separately and concatenated, which
    keeps per-file memory usage predictable.
    """
    raw_files = sorted(RAW_PATH.glob("*.csv"))

    if not raw_files:
        raise FileNotFoundError(
            f"No CSV files found in {RAW_PATH}. "
            "Place the raw event CSV(s) there first."
        )

    logger.info(f"Found {len(raw_files)} raw file(s): {[f.name for f in raw_files]}")

    frames = []
    for fpath in raw_files:
        logger.info(f"  Loading: {fpath.name} ...")
        df = pd.read_csv(
            fpath,
            dtype=DTYPES,
            parse_dates=["event_time"],
            low_memory=False,
        )
        df["_source_file"] = fpath.name
        frames.append(df)
        logger.info(f"  → {len(df):,} rows loaded from {fpath.name}")

    events = pd.concat(frames, ignore_index=True)
    logger.info(f"Total raw events loaded: {len(events):,}")
    return events


def load_customers(events: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Derive unique customers from event data.

    Each unique user_id becomes one customer row, with aggregate
    stats about their activity computed from all their events.
    """
    if events is None:
        events = load_raw_events()

    logger.info("Extracting customers ...")
    customers = (
        events.groupby("user_id", sort=False)
        .agg(
            first_seen_at=("event_time", "min"),
            last_seen_at=("event_time", "max"),
            total_events=("event_type", "count"),
            total_sessions=("user_session", "nunique"),
        )
        .reset_index()
    )
    logger.info(f"Customers extracted: {len(customers):,}")
    return customers


def load_products(events: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Derive unique products from event data.

    The most recent record wins when a product appears multiple times,
    so we get the latest known price and category for each product.
    """
    if events is None:
        events = load_raw_events()

    logger.info("Extracting products ...")
    products = (
        events[["product_id", "category_id", "category_code", "brand", "price", "event_time"]]
        .sort_values("event_time", ascending=False)
        .drop_duplicates(subset=["product_id"], keep="first")
        .drop(columns=["event_time"])
        .reset_index(drop=True)
    )
    logger.info(f"Products extracted: {len(products):,}")
    return products


def load_orders(events: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Derive one order per purchase session.

    A session with at least one 'purchase' event becomes an order.
    The order_id is the user_session UUID, which is stable across
    a single shopping visit.
    """
    if events is None:
        events = load_raw_events()

    logger.info("Extracting orders ...")
    purchases = events[events["event_type"] == "purchase"].copy()

    orders = (
        purchases.groupby("user_session", sort=False)
        .agg(
            user_id=("user_id", "first"),
            order_date=("event_time", "min"),
            total_items=("product_id", "count"),
            total_amount=("price", "sum"),
        )
        .reset_index()
        .rename(columns={"user_session": "order_id"})
    )
    orders["status"] = "completed"
    logger.info(f"Orders extracted: {len(orders):,}")
    return orders


def load_order_items(events: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Derive one row per purchased item.

    Each purchase event corresponds to one item in an order.
    Quantity is always 1 because each event represents a single
    product being purchased.
    """
    if events is None:
        events = load_raw_events()

    logger.info("Extracting order_items ...")
    purchases = events[events["event_type"] == "purchase"].copy()

    order_items = purchases[
        ["user_session", "product_id", "price", "event_time"]
    ].copy()
    order_items = order_items.rename(columns={"user_session": "order_id"})
    order_items["quantity"] = 1
    order_items = order_items.reset_index(drop=True)
    order_items.index.name = "order_item_id"
    order_items = order_items.reset_index()

    logger.info(f"Order items extracted: {len(order_items):,}")
    return order_items


def load_payments(events: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Derive one payment per order.

    There is no payment table in the source data, so we create one:
    one payment per order, with the total order amount as the payment
    value. Payment method is 'unknown' since the source doesn't track it.
    """
    if events is None:
        events = load_raw_events()

    logger.info("Extracting payments ...")
    orders = load_orders(events)

    payments = orders[["order_id", "order_date", "total_amount"]].copy()
    payments = payments.rename(columns={
        "order_date":   "payment_date",
        "total_amount": "payment_value",
    })
    payments["payment_method"] = "unknown"
    payments["payment_status"] = "paid"
    payments = payments.reset_index(drop=True)
    payments.index.name = "payment_id"
    payments = payments.reset_index()

    logger.info(f"Payments extracted: {len(payments):,}")
    return payments


def extraction_summary(events: pd.DataFrame) -> dict:
    """
    Run all extractions and print a row count summary.

    Returns a dictionary of all entity DataFrames so callers
    don't have to re-extract from scratch.
    """
    customers   = load_customers(events)
    products    = load_products(events)
    orders      = load_orders(events)
    order_items = load_order_items(events)
    payments    = load_payments(events)

    print("\n" + "=" * 45)
    print("  EXTRACTION SUMMARY")
    print("=" * 45)
    print(f"  Raw events  : {len(events):>12,}")
    print(f"  Customers   : {len(customers):>12,}")
    print(f"  Products    : {len(products):>12,}")
    print(f"  Orders      : {len(orders):>12,}")
    print(f"  Order items : {len(order_items):>12,}")
    print(f"  Payments    : {len(payments):>12,}")
    print("=" * 45 + "\n")

    return {
        "events":      events,
        "customers":   customers,
        "products":    products,
        "orders":      orders,
        "order_items": order_items,
        "payments":    payments,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    events = load_raw_events()
    extraction_summary(events)
