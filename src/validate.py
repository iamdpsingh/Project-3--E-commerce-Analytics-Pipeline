"""
validate.py

Data quality checks that run after transformation and before any data
reaches the database.

Three categories of checks:
    - Primary keys: no nulls, no duplicates
    - Foreign keys: all child values exist in parent tables
    - Business rules: quantities > 0, prices >= 0, dates are valid

Checks are marked as either critical (pipeline stops on failure)
or warning (pipeline continues but the issue is logged). All results
are collected into a ValidationReport that prints a readable summary.
"""

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    entity:   str
    check:    str
    passed:   bool
    critical: bool
    detail:   str = ""

    def __str__(self):
        icon = "✓" if self.passed else ("✗" if self.critical else "⚠")
        crit = " [CRITICAL]" if (not self.passed and self.critical) else ""
        return f"  {icon}  {self.entity} — {self.check}{crit}: {self.detail}"


@dataclass
class ValidationReport:
    results: list[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult):
        self.results.append(result)
        if result.passed:
            logger.info(str(result))
        elif result.critical:
            logger.error(str(result))
        else:
            logger.warning(str(result))

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results if r.critical)

    @property
    def failed_critical(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed and r.critical]

    def print_report(self):
        print("\n" + "=" * 55)
        print("  DATA QUALITY REPORT")
        print("=" * 55)

        current_entity = None
        for r in self.results:
            if r.entity != current_entity:
                print(f"\n  {r.entity}:")
                current_entity = r.entity
            icon = "✓" if r.passed else ("✗" if r.critical else "⚠")
            suffix = f" ({r.detail})" if r.detail else ""
            crit = " [CRITICAL]" if (not r.passed and r.critical) else ""
            print(f"    {icon}  {r.check}{crit}{suffix}")

        print("\n" + "-" * 55)
        total    = len(self.results)
        passed   = sum(1 for r in self.results if r.passed)
        warnings = sum(1 for r in self.results if not r.passed and not r.critical)
        errors   = len(self.failed_critical)
        print(f"  Total checks  : {total}")
        print(f"  ✓ Passed      : {passed}")
        print(f"  ⚠ Warnings    : {warnings}")
        print(f"  ✗ Errors      : {errors}")
        if self.passed:
            print("\n  ✅  Validation PASSED — pipeline can continue")
        else:
            print("\n  ❌  Validation FAILED — fix critical errors before loading")
        print("=" * 55 + "\n")


def _check_pk(df: pd.DataFrame, entity: str, key: str, report: ValidationReport) -> None:
    null_count = df[key].isna().sum()
    report.add(CheckResult(
        entity=entity, check=f"No null {key}s",
        passed=(null_count == 0), critical=True,
        detail=f"{null_count:,} nulls" if null_count else "OK"
    ))
    dup_count = df.duplicated(subset=[key]).sum()
    report.add(CheckResult(
        entity=entity, check=f"No duplicate {key}s",
        passed=(dup_count == 0), critical=True,
        detail=f"{dup_count:,} duplicates" if dup_count else "OK"
    ))


def _check_fk(
    child_df: pd.DataFrame, child_key: str,
    parent_df: pd.DataFrame, parent_key: str,
    child_entity: str, parent_entity: str,
    report: ValidationReport,
    critical: bool = True
) -> None:
    parent_values = set(parent_df[parent_key].dropna().unique())
    child_values  = set(child_df[child_key].dropna().unique())
    orphans = child_values - parent_values
    count = len(orphans)
    report.add(CheckResult(
        entity=child_entity,
        check=f"{child_key} → {parent_entity}.{parent_key}",
        passed=(count == 0), critical=critical,
        detail=f"{count:,} orphan value(s)" if count else "OK"
    ))


def validate_customers(df: pd.DataFrame, report: ValidationReport) -> None:
    _check_pk(df, "Customers", "user_id", report)
    bad = (df["total_events"] <= 0).sum() if "total_events" in df.columns else 0
    report.add(CheckResult(
        entity="Customers", check="total_events > 0",
        passed=(bad == 0), critical=False,
        detail=f"{bad:,} rows with events <= 0" if bad else "OK"
    ))


def validate_products(df: pd.DataFrame, report: ValidationReport) -> None:
    _check_pk(df, "Products", "product_id", report)
    bad_price = (df["price"] < 0).sum() if "price" in df.columns else 0
    report.add(CheckResult(
        entity="Products", check="price >= 0",
        passed=(bad_price == 0), critical=False,
        detail=f"{bad_price:,} negative prices" if bad_price else "OK"
    ))
    null_price = df["price"].isna().sum() if "price" in df.columns else 0
    report.add(CheckResult(
        entity="Products", check="No null prices",
        passed=(null_price == 0), critical=False,
        detail=f"{null_price:,} null prices" if null_price else "OK"
    ))


def validate_orders(df: pd.DataFrame, customers: pd.DataFrame, report: ValidationReport) -> None:
    _check_pk(df, "Orders", "order_id", report)
    _check_fk(df, "user_id", customers, "user_id", "Orders", "customers", report)
    bad_items = (df["total_items"] <= 0).sum() if "total_items" in df.columns else 0
    report.add(CheckResult(
        entity="Orders", check="total_items > 0",
        passed=(bad_items == 0), critical=False,
        detail=f"{bad_items:,} orders with items <= 0" if bad_items else "OK"
    ))
    bad_amt = (df["total_amount"] < 0).sum() if "total_amount" in df.columns else 0
    report.add(CheckResult(
        entity="Orders", check="total_amount >= 0",
        passed=(bad_amt == 0), critical=False,
        detail=f"{bad_amt:,} negative amounts" if bad_amt else "OK"
    ))
    null_dates = df["order_date"].isna().sum() if "order_date" in df.columns else 0
    report.add(CheckResult(
        entity="Orders", check="Valid order_date",
        passed=(null_dates == 0), critical=True,
        detail=f"{null_dates:,} null dates" if null_dates else "OK"
    ))


def validate_order_items(
    df: pd.DataFrame, orders: pd.DataFrame,
    products: pd.DataFrame, report: ValidationReport
) -> None:
    _check_pk(df, "Order Items", "order_item_id", report)
    _check_fk(df, "order_id",   orders,   "order_id",   "Order Items", "orders",   report)
    _check_fk(df, "product_id", products, "product_id", "Order Items", "products", report)
    bad_qty = (df["quantity"] <= 0).sum() if "quantity" in df.columns else 0
    report.add(CheckResult(
        entity="Order Items", check="quantity > 0",
        passed=(bad_qty == 0), critical=False,
        detail=f"{bad_qty:,} invalid quantities" if bad_qty else "OK"
    ))


def validate_payments(df: pd.DataFrame, orders: pd.DataFrame, report: ValidationReport) -> None:
    _check_pk(df, "Payments", "payment_id", report)
    _check_fk(df, "order_id", orders, "order_id", "Payments", "orders", report)
    bad_val = (df["payment_value"] < 0).sum() if "payment_value" in df.columns else 0
    report.add(CheckResult(
        entity="Payments", check="payment_value >= 0",
        passed=(bad_val == 0), critical=False,
        detail=f"{bad_val:,} negative values" if bad_val else "OK"
    ))


def validate_all(cleaned: dict) -> ValidationReport:
    """
    Run all validation checks and return a complete ValidationReport.

    Call report.passed before attempting to load data — the pipeline
    should halt if any critical checks failed.
    """
    report = ValidationReport()
    logger.info("Starting data validation ...")

    validate_customers(cleaned["customers"], report)
    validate_products(cleaned["products"],   report)
    validate_orders(cleaned["orders"], cleaned["customers"], report)
    validate_order_items(cleaned["order_items"], cleaned["orders"], cleaned["products"], report)
    validate_payments(cleaned["payments"], cleaned["orders"], report)

    report.print_report()
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    from src.extract import load_raw_events, extraction_summary
    from src.transform import transform_all

    events    = load_raw_events()
    extracted = extraction_summary(events)
    cleaned   = transform_all(extracted)
    report    = validate_all(cleaned)

    if not report.passed:
        raise SystemExit("Validation failed — see report above.")
