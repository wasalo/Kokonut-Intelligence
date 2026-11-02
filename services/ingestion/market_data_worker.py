"""Run global reference-price writes through bounded market-data functions."""

from __future__ import annotations

import argparse
import json
import math
import time
from numbers import Real

from services.common.cli import print_json, run
from services.common.worker_database import get_worker_db
from services.core.features import is_enabled
from services.ingestion.base import hash_payload
from services.ingestion.market_data import (
    COMMODITY_SEED_DATA,
    WORLD_BANK_FALLBACK_URL,
    download_pink_sheet,
    parse_pink_sheet,
    prepare_world_bank_records,
    validate_world_bank_filters,
)

_MANUAL_PRICE_FUNCTION = (
    "kokonut_security.store_manual_market_price"
    "(text,text,numeric,text,text,text,jsonb)"
)
_REFERENCE_SEED_FUNCTION = (
    "kokonut_security.store_world_bank_seed_market_data(jsonb,text,integer)"
)


def _require_enabled() -> None:
    if not is_enabled("isolated_market_data_worker"):
        raise RuntimeError("isolated market-data worker is disabled")


def _bounded_text(value: str, field: str, maximum: int, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum or "\x00" in normalized:
        raise ValueError(f"{field} is outside the allowed range")
    return normalized


def _call_worker(function_sql: str, arguments: tuple, *, operation: str):
    """Call one exact market-data function under the isolated login."""
    connection = get_worker_db("market_data")
    try:
        with connection.cursor() as cursor:
            cursor.execute(function_sql, arguments)
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError(f"market-data worker returned no {operation} result")
            result = row[0]
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def ingest(commodity: str | None = None, month: int | None = None, year: int | None = None) -> int:
    """Fetch and persist one bounded World Bank market-data batch.

    Provider retrieval and parsing finish before the isolated database
    connection opens. PostgreSQL validates and writes the rows plus audit in
    one bounded function call.
    """
    _require_enabled()
    commodity = validate_world_bank_filters(commodity, month, year)
    if (month is None) != (year is None):
        raise ValueError("month and year must be supplied together")
    started = time.monotonic()
    try:
        payload = download_pink_sheet()
    except Exception:
        raise RuntimeError(
            "World Bank Pink Sheet download failed; use explicit --source seed "
            "for reference samples"
        ) from None
    parsed = parse_pink_sheet(payload, target_month=month, target_year=year)
    if not parsed:
        raise RuntimeError("World Bank Pink Sheet returned no usable price records")
    records = prepare_world_bank_records(
        parsed,
        commodity=commodity,
        source_url=WORLD_BANK_FALLBACK_URL,
    )
    payload_hash = hash_payload(records)
    bounded_rows = [
        {
            "commodity_code": record["commodity_code"],
            "commodity_name": record["commodity_name"],
            "price_date": record["price_date"],
            "price_per_unit": record["price_per_unit"],
        }
        for record in records
    ]
    processing_time_ms = min(600_000, max(0, int((time.monotonic() - started) * 1000)))

    inserted = _call_worker(
        """
        SELECT kokonut_security.store_world_bank_market_data(
            %s::jsonb, %s, %s, %s
        )
        """,
        (
            json.dumps(bounded_rows, default=str),
            WORLD_BANK_FALLBACK_URL,
            payload_hash,
            processing_time_ms,
        ),
        operation="World Bank market-data",
    )
    return int(inserted)


def seed_reference_data(commodity: str | None = None) -> int:
    """Persist the explicit local reference-price dataset through its bounded function."""
    _require_enabled()
    normalized_commodity = commodity.upper() if commodity else None
    if normalized_commodity and normalized_commodity not in COMMODITY_SEED_DATA:
        raise ValueError(f"Unknown commodity: {normalized_commodity}")

    started = time.monotonic()
    records = [
        {
            "commodity_code": code,
            "commodity_name": info["name"],
            "price_date": point["date"],
            "price_per_unit": point["price"],
            "unit": info["unit"],
        }
        for code, info in COMMODITY_SEED_DATA.items()
        if normalized_commodity is None or code == normalized_commodity
        for point in info["prices"]
    ]
    payload_hash = hash_payload(records)
    bounded_records = [
        {key: record[key] for key in (
            "commodity_code", "commodity_name", "price_date", "price_per_unit", "unit"
        )}
        for record in records
    ]
    processing_time_ms = min(600_000, max(0, int((time.monotonic() - started) * 1000)))
    inserted = _call_worker(
        """
        SELECT kokonut_security.store_world_bank_seed_market_data(
            %s::jsonb, %s, %s
        )
        """,
        (json.dumps(bounded_records, default=str), payload_hash, processing_time_ms),
        operation="reference-seed market-data",
    )
    return int(inserted)


def record_manual_price(
    crop_name: str,
    market_name: str,
    price: float,
    quality_grade: str | None = None,
    unit: str = "kg",
    currency: str = "USD",
    metadata: dict | None = None,
) -> dict:
    """Record one global manual reference price using the dedicated DB identity."""
    _require_enabled()
    crop_name = _bounded_text(crop_name, "crop name", 200)
    # Keep application preflight aligned with `price_observation.market_name`
    # and the bounded SQL writer's VARCHAR(100) contract.
    market_name = _bounded_text(market_name, "market name", 100)
    unit = _bounded_text(unit, "unit", 50)
    # `price_observation.currency` is VARCHAR(10); fail before acquiring the
    # isolated worker connection instead of relying on a database truncation
    # or constraint error.
    currency = _bounded_text(currency, "currency", 10)
    quality_grade = _bounded_text(
        quality_grade, "quality grade", 50, optional=True
    )
    if isinstance(price, bool) or not isinstance(price, Real) or not math.isfinite(float(price)) or price <= 0:
        raise ValueError("price must be a finite positive number")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    try:
        metadata_json = json.dumps(metadata, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("metadata must be a JSON-compatible object") from exc
    if len(metadata_json.encode("utf-8")) > 8192:
        raise ValueError("metadata exceeds the allowed size")

    price_id = _call_worker(
        f"SELECT {_MANUAL_PRICE_FUNCTION}(%s, %s, %s, %s, %s, %s, %s::jsonb)",
        (
            crop_name,
            market_name,
            float(price),
            quality_grade,
            unit,
            currency,
            metadata_json,
        ),
        operation="manual market-price",
    )
    return {
        "price_id": str(price_id),
        "crop_name": crop_name,
        "market_name": market_name,
        "price": float(price),
        "currency": currency,
        "unit": unit,
        "quality_grade": quality_grade,
    }


def run_source(
    commodity: str | None = None,
    source: str = "world_bank",
    month: int | None = None,
    year: int | None = None,
) -> int:
    """Compatibility adapter for the legacy market-data CLI and saved tasks."""
    if source == "seed":
        if month is not None or year is not None:
            raise ValueError("month and year filters are only valid for world_bank")
        return seed_reference_data(commodity)
    if source == "world_bank":
        return ingest(commodity, month, year)
    raise ValueError("source must be 'world_bank' or 'seed'")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run isolated World Bank commodity price ingestion"
    )
    parser.add_argument("--commodity", help="Optional supported commodity code")
    parser.add_argument("--month", type=int, help="Optional month (requires --year)")
    parser.add_argument("--year", type=int, help="Optional year (requires --month)")
    args = parser.parse_args()
    if (args.month is None) != (args.year is None):
        parser.error("--month and --year must be supplied together")
    try:
        commodity = validate_world_bank_filters(args.commodity, args.month, args.year)
    except ValueError as exc:
        parser.error(str(exc))
    if not is_enabled("isolated_market_data_worker"):
        print_json({
            "status": "skipped",
            "reason": "isolated_market_data_worker_disabled",
        })
        return

    inserted = ingest(commodity, args.month, args.year)
    print_json({
        "status": "success",
        "source": "world_bank_pink_sheet",
        "rows_inserted": inserted,
    })


if __name__ == "__main__":
    run(main)
