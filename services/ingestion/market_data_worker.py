"""Run global World Bank market-data ingestion through a bounded DB function."""

from __future__ import annotations

import argparse
import json
import time

from services.common.cli import print_json, run
from services.common.worker_database import get_worker_db
from services.core.features import is_enabled
from services.ingestion.base import hash_payload
from services.ingestion.market_data import (
    WORLD_BANK_FALLBACK_URL,
    download_pink_sheet,
    parse_pink_sheet,
    prepare_world_bank_records,
    validate_world_bank_filters,
)


def ingest(commodity: str | None = None, month: int | None = None, year: int | None = None) -> int:
    """Fetch and persist one bounded World Bank market-data batch.

    Provider retrieval and parsing finish before the isolated database
    connection opens. PostgreSQL validates and writes the rows plus audit in
    one bounded function call.
    """
    commodity = validate_world_bank_filters(commodity, month, year)
    if (month is None) != (year is None):
        raise ValueError("month and year must be supplied together")
    started = time.monotonic()
    payload = download_pink_sheet()
    parsed = parse_pink_sheet(payload, target_month=month, target_year=year)
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

    connection = get_worker_db("market_data")
    try:
        with connection.cursor() as cursor:
            cursor.execute(
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
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("market-data worker returned no result")
            inserted = int(row[0])
        connection.commit()
        return inserted
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


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
        parser.error("isolated market-data worker is disabled")

    inserted = ingest(commodity, args.month, args.year)
    print_json({
        "status": "success",
        "source": "world_bank_pink_sheet",
        "rows_inserted": inserted,
    })


if __name__ == "__main__":
    run(main)
