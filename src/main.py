"""
main.py

Orchestrates the full data pipeline from raw CSV to analytics views.

Run it with:
    python -m src.main

The pipeline runs these steps in order:
    1. Load raw CSVs and extract entity DataFrames
    2. Clean and standardise each entity
    3. Run data quality checks
    4. Save cleaned data to data/processed/
    5. Create database schemas and tables
    6. Load data into the raw PostgreSQL layer
    7. Verify row counts match between source and database
    8. Transform raw layer into staging (SQL)
    9. Build the warehouse star schema (SQL)
    10. Create and populate analytics views

Flags:
    --mode full          Full reload (default) — truncates and reloads everything
    --mode incremental   Append-only — loads only new records based on date
    --skip-extract       Skip extraction and transformation, use saved processed CSVs
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

LOG_PATH = Path(os.getenv("LOG_PATH", "logs"))
LOG_PATH.mkdir(parents=True, exist_ok=True)

log_file = LOG_PATH / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("pipeline")


def run_pipeline(mode: str = "full", skip_extract: bool = False):
    pipeline_start = time.time()
    logger.info("=" * 60)
    logger.info(f"  PIPELINE STARTED  [{mode.upper()} LOAD]")
    logger.info(f"  Log: {log_file}")
    logger.info("=" * 60)

    processed_path = Path(os.getenv("PROCESSED_DATA_PATH", "data/processed"))
    processed_path.mkdir(parents=True, exist_ok=True)

    # 1. Extract
    step_start = time.time()
    logger.info("STEP 1 — EXTRACT")

    if skip_extract:
        logger.info("  Loading from existing processed CSVs (--skip-extract)")
        import pandas as pd
        extracted = {
            "events":      pd.DataFrame(),
            "customers":   pd.read_csv(processed_path / "customers_clean.csv"),
            "products":    pd.read_csv(processed_path / "products_clean.csv"),
            "orders":      pd.read_csv(processed_path / "orders_clean.csv"),
            "order_items": pd.read_csv(processed_path / "order_items_clean.csv"),
            "payments":    pd.read_csv(processed_path / "payments_clean.csv"),
        }
        logger.info("  Processed CSVs loaded.")
    else:
        from src.extract import load_raw_events, extraction_summary
        try:
            events = load_raw_events()
        except FileNotFoundError as e:
            logger.error(f"  EXTRACT FAILED: {e}")
            raise
        extracted = extraction_summary(events)

    logger.info(f"  EXTRACT completed in {time.time() - step_start:.1f}s")

    # 2. Transform
    if not skip_extract:
        step_start = time.time()
        logger.info("STEP 2 — TRANSFORM")
        from src.transform import transform_all
        try:
            cleaned = transform_all(extracted)
        except Exception as e:
            logger.error(f"  TRANSFORM FAILED: {e}")
            raise
        logger.info(f"  TRANSFORM completed in {time.time() - step_start:.1f}s")
    else:
        cleaned = extracted

    # 3. Validate
    step_start = time.time()
    logger.info("STEP 3 — VALIDATE")
    from src.validate import validate_all
    try:
        report = validate_all(cleaned)
    except Exception as e:
        logger.error(f"  VALIDATE FAILED: {e}")
        raise

    if not report.passed:
        failed = [str(r) for r in report.failed_critical]
        logger.error(f"  VALIDATION FAILED — {len(failed)} critical error(s):")
        for f in failed:
            logger.error(f"    {f}")
        raise ValueError("Pipeline halted: critical validation failures. See report above.")

    logger.info(f"  VALIDATE completed in {time.time() - step_start:.1f}s — all critical checks passed")

    # 4. Save processed CSVs
    if not skip_extract:
        step_start = time.time()
        logger.info("STEP 4 — SAVE PROCESSED CSVs")
        entity_files = {
            "customers":   "customers_clean.csv",
            "products":    "products_clean.csv",
            "orders":      "orders_clean.csv",
            "order_items": "order_items_clean.csv",
            "payments":    "payments_clean.csv",
        }
        for entity, fname in entity_files.items():
            fpath = processed_path / fname
            cleaned[entity].to_csv(fpath, index=False)
            logger.info(f"  Saved: {fpath} ({len(cleaned[entity]):,} rows)")
        logger.info(f"  SAVE completed in {time.time() - step_start:.1f}s")

    # 5. Database schema setup
    step_start = time.time()
    logger.info("STEP 5 — DATABASE SCHEMA SETUP")
    from src.load import get_engine, setup_schemas
    try:
        engine = get_engine()
        setup_schemas(engine)
    except Exception as e:
        logger.error(f"  DATABASE SETUP FAILED: {e}")
        raise
    logger.info(f"  DATABASE SETUP completed in {time.time() - step_start:.1f}s")

    # 6. Load raw layer
    step_start = time.time()
    logger.info(f"STEP 6 — LOAD → raw.* [{mode.upper()}]")
    from src.load import load_to_raw, load_incremental
    try:
        if mode == "incremental":
            new_rows = load_incremental(cleaned["orders"], "orders", engine, "order_date")
            logger.info(f"  Incremental load: {new_rows:,} new order rows")
            loaded_counts = {}
        else:
            loaded_counts = load_to_raw(cleaned, engine, if_exists="replace")
    except Exception as e:
        logger.error(f"  LOAD FAILED: {e}")
        raise
    logger.info(f"  LOAD completed in {time.time() - step_start:.1f}s")

    # 7. Verify row counts
    if mode == "full":
        step_start = time.time()
        logger.info("STEP 7 — VERIFY ROW COUNTS")
        from src.load import verify_raw_counts
        match = verify_raw_counts(cleaned, loaded_counts, engine)
        if not match:
            logger.error("  ROW COUNT MISMATCH — pipeline halted")
            raise ValueError("Row count verification failed.")
        logger.info(f"  VERIFY completed in {time.time() - step_start:.1f}s")

    # 8. Staging transform
    step_start = time.time()
    logger.info("STEP 8 — STAGING TRANSFORM (raw → staging)")
    from src.load import run_staging_transform, verify_staging_counts
    try:
        run_staging_transform(engine)
        verify_staging_counts(engine)
    except Exception as e:
        logger.error(f"  STAGING TRANSFORM FAILED: {e}")
        raise
    logger.info(f"  STAGING completed in {time.time() - step_start:.1f}s")

    # 9. Warehouse load
    step_start = time.time()
    logger.info("STEP 9 — WAREHOUSE LOAD (staging → warehouse)")
    from src.load import run_warehouse_load, verify_warehouse_counts
    try:
        run_warehouse_load(engine)
        verify_warehouse_counts(engine)
    except Exception as e:
        logger.error(f"  WAREHOUSE LOAD FAILED: {e}")
        raise
    logger.info(f"  WAREHOUSE completed in {time.time() - step_start:.1f}s")

    # 10. Analytics views
    step_start = time.time()
    logger.info("STEP 10 — CREATE ANALYTICS VIEWS")
    from src.analytics import create_analytics_views, print_quick_analytics
    try:
        create_analytics_views(engine)
        print_quick_analytics(engine)
    except Exception as e:
        logger.error(f"  ANALYTICS VIEWS FAILED: {e}")
        raise
    logger.info(f"  ANALYTICS completed in {time.time() - step_start:.1f}s")

    elapsed = time.time() - pipeline_start
    logger.info("=" * 60)
    logger.info(f"  ✅  PIPELINE COMPLETED SUCCESSFULLY in {elapsed:.1f}s")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="E-commerce Analytics Pipeline")
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="full",
        help="Load mode: 'full' replaces all data, 'incremental' appends new records only.",
    )
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Skip extraction and transformation; reload from existing processed CSVs.",
    )
    args = parser.parse_args()

    try:
        run_pipeline(mode=args.mode, skip_extract=args.skip_extract)
    except Exception as e:
        logger.exception(f"PIPELINE FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
