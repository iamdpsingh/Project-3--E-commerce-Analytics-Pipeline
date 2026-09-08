"""
analytics.py

Creates and verifies the analytics schema views, and provides a
quick summary query to confirm the analytical layer is working.

The views themselves are defined in sql/analytics/01_create_views.sql.
This module handles execution and optional spot-checks.
"""

import logging
from pathlib import Path

from sqlalchemy import text

logger = logging.getLogger(__name__)


def create_analytics_views(engine) -> None:
    """
    Create all analytics.* views from the SQL definition file.

    Views are created with CREATE OR REPLACE, so this is safe to run
    multiple times. We split by semicolons and execute each statement
    individually because SQLAlchemy's text() doesn't support multi-statement
    execution reliably across all drivers.
    """
    sql_path = Path("sql/analytics/01_create_views.sql")
    logger.info(f"Creating analytics views from {sql_path.name} ...")
    sql = sql_path.read_text()

    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with engine.begin() as conn:
        for stmt in statements:
            if not stmt.strip():
                continue
            conn.execute(text(stmt))

    logger.info("  ✓ Analytics views created.")


def print_quick_analytics(engine) -> None:
    """
    Query the analytics views and print a quick executive summary.

    This is a sanity check to confirm the entire pipeline worked
    end-to-end — from raw CSV all the way through to the analytical layer.
    """
    print("\n" + "=" * 55)
    print("  ANALYTICS LAYER — QUICK SUMMARY")
    print("=" * 55)

    with engine.connect() as conn:
        kpis = conn.execute(text("SELECT * FROM analytics.executive_kpis")).fetchone()
        if kpis:
            print("\n  EXECUTIVE KPIs")
            print(f"  Total Revenue     : ${kpis[2]:>15,.2f}")
            print(f"  Total Orders      : {kpis[0]:>15,}")
            print(f"  Total Customers   : {kpis[1]:>15,}")
            print(f"  Avg Order Value   : ${kpis[3]:>15,.2f}")
            print(f"  Repeat Customers  : {kpis[4]:>15,}  ({kpis[5]}%)")

        print("\n  TOP 5 CATEGORIES (by revenue)")
        rows = conn.execute(text(
            "SELECT category_main, total_revenue, revenue_share_pct "
            "FROM analytics.category_performance LIMIT 5"
        )).fetchall()
        for r in rows:
            print(f"  {r[0]:<30} ${r[1]:>12,.2f}  ({r[2]}%)")

        print("\n  TOP 5 BRANDS (by revenue)")
        rows = conn.execute(text(
            "SELECT brand, total_revenue FROM analytics.brand_performance LIMIT 5"
        )).fetchall()
        for r in rows:
            print(f"  {r[0]:<30} ${r[1]:>12,.2f}")

        print("\n  MONTHLY REVENUE (most recent 5 months)")
        rows = conn.execute(text(
            "SELECT year_month, total_orders, total_revenue "
            "FROM analytics.monthly_revenue ORDER BY year_month DESC LIMIT 5"
        )).fetchall()
        for r in rows:
            print(f"  {r[0]}  orders={r[1]:>6,}  revenue=${r[2]:>12,.2f}")

    print("=" * 55 + "\n")
