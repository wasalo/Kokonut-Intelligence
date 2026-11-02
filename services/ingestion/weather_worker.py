"""Run one signed, location-scoped current-weather ingestion."""

from __future__ import annotations

import argparse
import json
import os
import time
from uuid import UUID

from services.common.cli import print_json, run
from services.common.http import http
from services.common.tenant_context import set_worker_tenant_context
from services.common.worker_database import get_worker_credential, get_worker_db
from services.core.features import is_enabled
from services.ingestion.base import hash_payload
from services.ingestion.weather import (
    API_BASE,
    build_weather_clickhouse_projection,
    parse_weather,
)


def _provider_api_key() -> str:
    key = os.getenv("KOKONUT_WEATHER_OPENWEATHERMAP_API_KEY", "").strip()
    if not key:
        raise RuntimeError("weather worker provider key is not configured")
    return key


def _fetch_weather(latitude: float, longitude: float, api_key: str) -> dict:
    response = http.get(
        API_BASE,
        params={"lat": latitude, "lon": longitude, "appid": api_key, "units": "metric"},
        timeout=10,
    )
    try:
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("OpenWeatherMap returned an invalid object")
        return payload
    finally:
        response.close()


def _open_scoped_connection(location_id: str, credential: str):
    connection = get_worker_db("weather")
    try:
        set_worker_tenant_context(
            connection,
            credential=credential,
            location_id=location_id,
            resource="weather_observation",
            action="ingest",
        )
    except Exception:
        connection.close()
        raise
    return connection


def _load_location(location_id: str, credential: str) -> tuple[float, float]:
    """Read only the signed location coordinates, then release the transaction."""
    connection = _open_scoped_connection(location_id, credential)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT latitude, longitude "
                "FROM kokonut_security.weather_observation_location(%s::uuid)",
                (location_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("signed weather location is not active or has no coordinates")
        connection.commit()
        return float(row[0]), float(row[1])
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _store_observation(
    location_id: str,
    credential: str,
    *,
    record: dict | None,
    projection: dict | None,
    provider_source_id: str,
    provider_payload_hash: str | None,
    processing_time_ms: int,
    error_text: str | None = None,
) -> tuple[str | None, bool]:
    """Store one observation, audit, receipt, and projection intent atomically."""
    observation = None
    projection_rows: list[list] = []
    projection_hash = None
    if record is not None and projection is not None:
        observation = {
            **record,
            "metadata": json.loads(record["metadata"])
            if isinstance(record.get("metadata"), str)
            else record.get("metadata", {}),
        }
        projection_rows = projection["rows"]
        projection_hash = projection["payload_hash"]

    connection = _open_scoped_connection(location_id, credential)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT observation_id::text, inserted
                  FROM kokonut_security.store_weather_observation(
                      %s::uuid, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s
                  )
                """,
                (
                    location_id,
                    json.dumps(observation, default=str) if observation is not None else None,
                    json.dumps(projection_rows, default=str),
                    projection_hash,
                    provider_source_id[:255],
                    provider_payload_hash,
                    processing_time_ms,
                    error_text,
                ),
            )
            result = cursor.fetchone()
            if result is None:
                raise RuntimeError("weather worker returned no result")
            observation_id, inserted = result
        connection.commit()
        return (str(observation_id) if observation_id is not None else None, bool(inserted))
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def ingest(location_id: str) -> tuple[str | None, bool]:
    """Fetch and persist one observation under a current signed location grant."""
    canonical_location_id = str(UUID(str(location_id)))
    api_key = _provider_api_key()
    credential = get_worker_credential("weather")
    latitude, longitude = _load_location(canonical_location_id, credential)

    started = time.monotonic()
    sanitized_error: RuntimeError | None = None
    try:
        raw = _fetch_weather(latitude, longitude, api_key)
        record = parse_weather(raw, canonical_location_id)
        projection = build_weather_clickhouse_projection([record])
    except Exception as exc:
        elapsed_ms = min(600000, max(0, int((time.monotonic() - started) * 1000)))
        # Provider exception text may include the API key in a request URL.
        safe_error = f"weather fetch or parsing failed ({type(exc).__name__})"
        try:
            _store_observation(
                canonical_location_id,
                credential,
                record=None,
                projection=None,
                provider_source_id="",
                provider_payload_hash=None,
                processing_time_ms=elapsed_ms,
                error_text=safe_error,
            )
        except Exception as audit_exc:
            from services.common.logging import get_logger

            get_logger("ingestion.weather_worker").warning(
                "Weather failure audit could not be persisted (%s)",
                type(audit_exc).__name__,
            )
        sanitized_error = RuntimeError(safe_error)

    if sanitized_error is not None:
        raise sanitized_error from None

    elapsed_ms = min(600000, max(0, int((time.monotonic() - started) * 1000)))
    return _store_observation(
        canonical_location_id,
        credential,
        record=record,
        projection=projection,
        provider_source_id=str(raw.get("id", "")),
        provider_payload_hash=hash_payload(raw),
        processing_time_ms=elapsed_ms,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest current weather for one signed worker location")
    parser.add_argument("--location-id", required=True, help="Location UUID")
    args = parser.parse_args()
    try:
        location_id = str(UUID(str(args.location_id)))
    except (TypeError, ValueError, AttributeError):
        parser.error("--location-id must be a UUID")
    if not is_enabled("signed_weather_worker"):
        parser.error("signed current-weather worker is disabled")

    observation_id, inserted = ingest(location_id)
    print_json({
        "status": "success",
        "location_id": location_id,
        "observation_id": observation_id,
        "inserted": inserted,
        "source": "openweathermap",
    })


if __name__ == "__main__":
    run(main)
