"""Run signed, location-scoped climate ingestion through bounded SQL functions."""

from __future__ import annotations

import argparse
import json
import time
from uuid import UUID

from services.common.cli import print_json, run
from services.common.tenant_context import set_worker_tenant_context
from services.common.worker_database import get_worker_credential, get_worker_db
from services.core.features import is_enabled
from services.ingestion.climate_data import _estimate_bioclim
from services.ingestion.gee_climate import (
    fetch_era5_land,
    fetch_modis_lst,
    fetch_sentinel1_sar,
    fetch_smap_moisture,
)

_PROVIDERS = (
    ("era5_land", fetch_era5_land),
    ("modis_lst", fetch_modis_lst),
    ("smap_moisture", fetch_smap_moisture),
    ("sentinel1_sar", fetch_sentinel1_sar),
)


def _open_scoped_connection(location_id: str, credential: str):
    connection = get_worker_db("climate")
    try:
        set_worker_tenant_context(
            connection,
            credential=credential,
            location_id=location_id,
            resource="climate",
            action="ingest",
        )
    except Exception:
        connection.close()
        raise
    return connection


def _load_location(location_id: str, credential: str) -> dict | None:
    """Read the signed location point and a bounded provider bbox."""
    connection = _open_scoped_connection(location_id, credential)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT latitude, longitude, west, south, east, north "
                "FROM kokonut_security.climate_location(%s::uuid)",
                (location_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
        connection.commit()
        return {
            "latitude": float(row[0]),
            "longitude": float(row[1]),
            "bbox": {
                "west": float(row[2]),
                "south": float(row[3]),
                "east": float(row[4]),
                "north": float(row[5]),
            },
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _store_result(
    location_id: str,
    credential: str,
    *,
    source_key: str,
    summary: dict | None,
    processing_time_ms: int,
    error_text: str | None = None,
) -> str | None:
    """Store one source result and its audit through the signed SQL boundary."""
    connection = _open_scoped_connection(location_id, credential)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.store_climate_summary("
                "%s::uuid, %s, %s::jsonb, %s, %s)",
                (
                    location_id,
                    source_key,
                    json.dumps(summary, default=str) if summary is not None else None,
                    min(600000, max(0, processing_time_ms)),
                    error_text,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("climate worker returned no persistence result")
            record_id = row[0]
        connection.commit()
        return str(record_id) if record_id is not None else None
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _worldclim_summary(latitude: float, longitude: float) -> dict:
    variables = {
        f"bio_{number}": _estimate_bioclim(latitude, longitude, number)
        for number in range(1, 20)
    }
    return {
        "source_key": "worldclim",
        "source_table": "worldclim_climate",
        "source_id": "latitude_proxy_v1",
        "target_table": "worldclim_climate",
        "target_date": None,
        "resolution_m": None,
        "values": {
            "bio1_mean_annual_temp": variables["bio_1"],
            "bio4_temp_seasonality": variables["bio_4"],
            "bio5_max_temp_warmest_month": variables["bio_5"],
            "bio6_min_temp_coldest_month": variables["bio_6"],
            "bio12_annual_precipitation": variables["bio_12"],
            "bio15_precip_seasonality": variables["bio_15"],
            "bio16_precip_wettest_quarter": variables["bio_16"],
            "bio17_precip_driest_quarter": variables["bio_17"],
            "temp_range": variables["bio_7"],
        },
        "metadata": {
            "estimation_method": "latitude_proxy_v1",
            "reference_period": "1970-2000",
            "estimated_bioclimatic_variables": variables,
        },
    }


def ingest(location_id: str) -> dict:
    """Fetch all current climate summaries for one signed location."""
    canonical_location_id = str(UUID(str(location_id)))
    credential = get_worker_credential("climate")
    location = _load_location(canonical_location_id, credential)
    if location is None:
        raise ValueError("signed climate location is not active or has no coordinates")

    results: dict[str, dict] = {}
    started = time.monotonic()
    worldclim = _worldclim_summary(location["latitude"], location["longitude"])
    try:
        record_id = _store_result(
            canonical_location_id,
            credential,
            source_key="worldclim",
            summary=worldclim,
            processing_time_ms=int((time.monotonic() - started) * 1000),
        )
        results["worldclim"] = {"status": "success", "record_id": record_id, "estimated": True}
    except Exception as exc:
        results["worldclim"] = {"status": "error", "error_type": type(exc).__name__}

    for source_key, fetcher in _PROVIDERS:
        source_started = time.monotonic()

        def persist(summary: dict) -> str:
            return _store_result(
                canonical_location_id,
                credential,
                source_key=source_key,
                summary=summary,
                processing_time_ms=int((time.monotonic() - source_started) * 1000),
            ) or ""

        try:
            result = fetcher(
                None,
                canonical_location_id,
                location["bbox"],
                worker_credentials=True,
                persist_summary=persist,
            )
            if result.get("status") == "error":
                safe_error = "climate provider fetch failed"
                _store_result(
                    canonical_location_id,
                    credential,
                    source_key=source_key,
                    summary=None,
                    processing_time_ms=int((time.monotonic() - source_started) * 1000),
                    error_text=safe_error,
                )
                results[source_key] = {"status": "error", "error": safe_error}
            else:
                results[source_key] = result
        except Exception as exc:
            safe_error = f"climate provider processing failed ({type(exc).__name__})"
            _store_result(
                canonical_location_id,
                credential,
                source_key=source_key,
                summary=None,
                processing_time_ms=int((time.monotonic() - source_started) * 1000),
                error_text=safe_error,
            )
            results[source_key] = {"status": "error", "error": safe_error}

    failed = sum(result.get("status") == "error" for result in results.values())
    skipped = sum(result.get("status") == "skipped" for result in results.values())
    report = {
        "status": "error" if failed else "success",
        "location_id": canonical_location_id,
        "results": results,
        "success": len(results) - failed - skipped,
        "skipped": skipped,
        "failed": failed,
        "total": len(results),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest all climate summaries for one signed worker location"
    )
    parser.add_argument("--location-id", required=True, help="Location UUID")
    args = parser.parse_args()
    try:
        location_id = str(UUID(str(args.location_id)))
    except (TypeError, ValueError, AttributeError):
        parser.error("--location-id must be a UUID")
    if not is_enabled("signed_climate_worker"):
        parser.error("signed climate worker is disabled")

    report = ingest(location_id)
    print_json(report)
    if report["status"] == "error":
        raise RuntimeError("one or more climate sources failed")


if __name__ == "__main__":
    run(main)
