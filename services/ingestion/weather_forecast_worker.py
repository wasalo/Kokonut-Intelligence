"""Run one signed, location-scoped OpenWeatherMap forecast ingestion."""

from __future__ import annotations

import argparse
import json
import time
from uuid import UUID

from services.common.cli import print_json, run
from services.common.tenant_context import set_worker_tenant_context
from services.common.worker_database import get_worker_credential, get_worker_db
from services.core.features import is_enabled
from services.ingestion.base import hash_payload
from services.ingestion.config import OPENWEATHERMAP_API_KEY
from services.ingestion.weather_forecast import (
    build_forecast_clickhouse_projection,
    fetch_forecast_raw,
    parse_forecast_list,
)


def _open_scoped_connection(location_id: str, credential: str):
    connection = get_worker_db("weather_forecast")
    try:
        set_worker_tenant_context(
            connection,
            credential=credential,
            location_id=location_id,
            resource="weather_forecast",
            action="ingest",
        )
    except Exception:
        connection.close()
        raise
    return connection


def _load_location(location_id: str, credential: str) -> tuple[str, float, float]:
    """Resolve coordinates from the database under a signed location grant."""
    connection = _open_scoped_connection(location_id, credential)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT location_name, latitude, longitude "
                "FROM kokonut_security.weather_forecast_location(%s::uuid)",
                (location_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("signed weather forecast location is not active or has no coordinates")
        connection.commit()
        return str(row[0]), float(row[1]), float(row[2])
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _store_batch(
    location_id: str,
    credential: str,
    *,
    records: list[dict],
    projection: dict,
    provider_source_id: str,
    provider_payload_hash: str | None,
    processing_time_ms: int,
    error_text: str | None = None,
) -> int:
    """Persist only through the bounded signed-scope database function."""
    forecast_rows = [
        {
            **record,
            "metadata": json.loads(record["metadata"])
            if isinstance(record.get("metadata"), str)
            else record.get("metadata", {}),
        }
        for record in records
    ]
    connection = _open_scoped_connection(location_id, credential)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT kokonut_security.store_weather_forecast_batch(
                    %s::uuid, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s
                )
                """,
                (
                    location_id,
                    json.dumps(forecast_rows, default=str),
                    json.dumps(projection["rows"], default=str),
                    projection["payload_hash"] if records else None,
                    provider_source_id[:255],
                    provider_payload_hash,
                    processing_time_ms,
                    error_text,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("weather forecast worker returned no result")
            written = int(row[0])
        connection.commit()
        return written
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def ingest(location_id: str) -> int:
    """Fetch, validate, and atomically persist one signed location's forecast."""
    canonical_location_id = str(UUID(str(location_id)))
    if not OPENWEATHERMAP_API_KEY:
        raise RuntimeError("OpenWeatherMap API key is not configured")
    credential = get_worker_credential("weather_forecast")

    _, latitude, longitude = _load_location(
        canonical_location_id, credential
    )
    started = time.monotonic()
    try:
        raw = fetch_forecast_raw(latitude, longitude)
        records = parse_forecast_list(raw, canonical_location_id)
        projection = build_forecast_clickhouse_projection(records)
    except Exception as exc:
        elapsed_ms = min(600000, max(0, int((time.monotonic() - started) * 1000)))
        # Do not persist exception text: HTTP errors may contain query strings
        # with the provider credential.
        safe_error = f"forecast fetch or parsing failed ({type(exc).__name__})"
        _store_batch(
            canonical_location_id,
            credential,
            records=[],
            projection={"rows": [], "payload_hash": ""},
            provider_source_id="",
            provider_payload_hash=None,
            processing_time_ms=elapsed_ms,
            error_text=safe_error,
        )
        raise

    elapsed_ms = min(600000, max(0, int((time.monotonic() - started) * 1000)))
    written = _store_batch(
        canonical_location_id,
        credential,
        records=records,
        projection=projection,
        provider_source_id=str(raw.get("city", {}).get("id", "")),
        provider_payload_hash=hash_payload(raw),
        processing_time_ms=elapsed_ms,
    )
    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest forecasts for one signed worker location"
    )
    parser.add_argument("--location-id", required=True, help="Location UUID")
    args = parser.parse_args()
    try:
        location_id = str(UUID(str(args.location_id)))
    except (TypeError, ValueError, AttributeError):
        parser.error("--location-id must be a UUID")
    if not is_enabled("signed_weather_forecast_worker"):
        parser.error("signed weather forecast worker is disabled")

    written = ingest(location_id)
    print_json({
        "status": "success",
        "location_id": location_id,
        "rows_written": written,
        "source": "openweathermap",
    })


if __name__ == "__main__":
    run(main)
