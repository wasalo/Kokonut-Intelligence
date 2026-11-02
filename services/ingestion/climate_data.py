"""Climate-data compatibility CLI routed through the signed climate worker.

The legacy selectors and manual entry point remain available, but no longer
open the shared application database or write climate summary relations.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from typing import Any, Dict, List, Optional

from services.common.cli import print_json
from services.common.logging import get_logger
from services.common.worker_environment import worker_subprocess_environment
from services.core.features import is_enabled
from services.security.scheduled_command_contracts import validate_scheduled_command

logger = get_logger("ingestion.climate_data")

_CLIMATE_WORKER_MODULE = "services.ingestion.climate_worker"
_CLIMATE_SOURCE_KEYS = frozenset({
    "worldclim", "era5_land", "modis_lst", "smap_moisture", "sentinel1_sar",
})
_LEGACY_CLIMATE_RESULT_KEYS = {
    "worldclim": "worldclim",
    "era5_land": "ncep",
    "modis_lst": "modis",
    "smap_moisture": "smap",
    "sentinel1_sar": "sentinel1",
}


def _valid_worker_report(
    report: Any,
    *,
    location_id: str,
    expected_sources: set[str],
    exit_code: int,
) -> bool:
    if not isinstance(report, dict) or report.get("location_id") != location_id:
        return False
    results = report.get("results")
    if not isinstance(results, dict) or set(results) != expected_sources:
        return False
    statuses: list[str] = []
    for item in results.values():
        if not isinstance(item, dict) or item.get("status") not in {"success", "skipped", "error"}:
            return False
        statuses.append(item["status"])
    success = statuses.count("success")
    skipped = statuses.count("skipped")
    failed = statuses.count("error")
    expected_status = "error" if failed else "success"
    return (
        report.get("status") == expected_status
        and report.get("success") == success
        and report.get("skipped") == skipped
        and report.get("failed") == failed
        and report.get("total") == len(expected_sources)
        and isinstance(report.get("success"), int)
        and not isinstance(report.get("success"), bool)
        and isinstance(report.get("skipped"), int)
        and not isinstance(report.get("skipped"), bool)
        and isinstance(report.get("failed"), int)
        and not isinstance(report.get("failed"), bool)
        and isinstance(report.get("total"), int)
        and not isinstance(report.get("total"), bool)
        and exit_code == (1 if failed else 0)
    )


def _dispatch_signed_climate_worker(
    location_id: str,
    source: str | None = None,
) -> dict[str, Any]:
    """Run the isolated, signed writer with only its exact worker secrets."""
    try:
        canonical_location_id = str(uuid.UUID(str(location_id)))
    except (TypeError, ValueError, AttributeError):
        return {"status": "error", "message": "climate location ID must be a UUID"}
    if source is not None and source not in _CLIMATE_SOURCE_KEYS:
        return {"status": "error", "message": "unsupported climate source"}
    if not is_enabled("signed_climate_worker"):
        return {"status": "error", "location_id": canonical_location_id,
                "message": "signed climate worker is disabled"}

    arguments = ["--location-id", canonical_location_id]
    if source is not None:
        arguments.extend(("--source", source))
    try:
        validate_scheduled_command(_CLIMATE_WORKER_MODULE, arguments)
        result = subprocess.run(
            [sys.executable, "-m", _CLIMATE_WORKER_MODULE, *arguments],
            capture_output=True,
            text=True,
            timeout=3600,
            env=worker_subprocess_environment(
                allowed_worker_keys=("climate",),
                isolated_database_credentials=True,
            ),
        )
    except subprocess.TimeoutExpired:
        logger.error("Signed climate worker timed out")
        return {"status": "error", "location_id": canonical_location_id,
                "message": "signed climate worker timed out"}
    except Exception as exc:
        logger.error("Signed climate worker could not start (%s)", type(exc).__name__)
        return {"status": "error", "location_id": canonical_location_id,
                "message": "signed climate worker could not start"}

    try:
        report = json.loads(result.stdout) if result.stdout.strip() else None
    except (TypeError, ValueError):
        report = None
    expected_sources = {source} if source is not None else set(_CLIMATE_SOURCE_KEYS)
    if _valid_worker_report(
        report,
        location_id=canonical_location_id,
        expected_sources=expected_sources,
        exit_code=result.returncode,
    ):
        return report
    logger.error("Signed climate worker failed (exit code %s)", result.returncode)
    return {"status": "error", "location_id": canonical_location_id,
            "message": "signed climate worker failed"}


def _dispatch_signed_climate_source(location_id: str, source: str) -> dict[str, Any]:
    """Keep the single-source compatibility result while using the worker."""
    report = _dispatch_signed_climate_worker(location_id, source)
    if report.get("status") == "error" and "results" not in report:
        return report
    results = report.get("results")
    selected = results.get(source) if isinstance(results, dict) else None
    if isinstance(selected, dict) and selected.get("status") in {"success", "skipped", "error"}:
        return selected
    logger.error("Signed climate worker omitted the %s result", source)
    return {"status": "error", "message": "signed climate worker returned an invalid result"}


def _estimate_bioclim(lat: float, lon: float, bio: int) -> Optional[float]:
    """Estimate bioclimatic variables from latitude.

    This is a simplified approximation for regions without direct API access.
    Uses latitude-based temperature and precipitation models.
    """
    abs_lat = abs(lat)

    # Temperature estimates (°C)
    if bio == 1:  # Mean annual temperature
        return round(25.0 - abs_lat * 0.7, 2)
    elif bio == 2:  # Mean diurnal range
        return round(10.0 + abs_lat * 0.1, 2)
    elif bio == 3:  # Isothermality
        return round(50.0 - abs_lat * 0.3, 2)
    elif bio == 4:  # Temperature seasonality
        return round(abs_lat * 5.0, 2)
    elif bio == 5:  # Max temp warmest month
        return round(30.0 - abs_lat * 0.5, 2)
    elif bio == 6:  # Min temp coldest month
        return round(15.0 - abs_lat * 1.5, 2)
    elif bio == 7:  # Temp range annual
        return round(abs_lat * 1.0, 2)
    elif bio in (8, 9, 10, 11):  # Quarterly mean temps
        return round(25.0 - abs_lat * 0.7 + (bio - 8) * 2, 2)
    # Precipitation estimates (mm)
    elif bio == 12:  # Annual precipitation
        return round(max(200, 1500 - abs_lat * 20), 2)
    elif bio == 13:  # Wettest month
        return round(max(20, 200 - abs_lat * 3), 2)
    elif bio == 14:  # Driest month
        return round(max(5, 30 - abs_lat * 0.5), 2)
    elif bio == 15:  # Precip seasonality
        return round(min(200, abs_lat * 3 + 50), 2)
    elif bio in (16, 17, 18, 19):  # Quarterly precip
        return round(max(50, 400 - abs_lat * 5 + (bio - 16) * 20), 2)
    return None


def fetch_worldclim(conn, location_id: str) -> Dict[str, Any]:
    """Compatibility entry point routed to the signed WorldClim writer."""
    return _dispatch_signed_climate_source(location_id, "worldclim")


def fetch_ncep(conn, location_id: str) -> Dict[str, Any]:
    """Compatibility selector for the ERA5-Land climate summary."""
    return _dispatch_signed_climate_source(location_id, "era5_land")


def fetch_modis(conn, location_id: str) -> Dict[str, Any]:
    """Compatibility selector for the MODIS land-surface-temperature summary."""
    return _dispatch_signed_climate_source(location_id, "modis_lst")


def fetch_smap(conn, location_id: str) -> Dict[str, Any]:
    """Compatibility selector for the SMAP soil-moisture summary."""
    return _dispatch_signed_climate_source(location_id, "smap_moisture")


def fetch_sentinel1(conn, location_id: str) -> Dict[str, Any]:
    """Compatibility selector for the Sentinel-1 SAR summary."""
    return _dispatch_signed_climate_source(location_id, "sentinel1_sar")


def run_all(conn, location_id: str) -> Dict[str, Any]:
    """Compatibility entry point for all five signed climate sources."""
    return _legacy_climate_report(_dispatch_signed_climate_worker(location_id))


def _legacy_climate_report(report: dict[str, Any]) -> dict[str, Any]:
    """Keep the historical source labels at the public compatibility boundary."""
    results = report.get("results")
    if not isinstance(results, dict):
        return report
    return {
        **report,
        "results": {
            legacy_key: results[source_key]
            for source_key, legacy_key in _LEGACY_CLIMATE_RESULT_KEYS.items()
            if source_key in results
        },
    }


def main(argv: Optional[List[str]] = None) -> int:
    """Run the legacy selector interface without opening the shared database."""
    parser = argparse.ArgumentParser(description="Climate data ingestion")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--worldclim", action="store_true", help="Fetch WorldClim data")
    operation.add_argument("--ncep", action="store_true", help="Fetch ERA5-Land data")
    operation.add_argument("--modis", action="store_true", help="Fetch MODIS data")
    operation.add_argument("--smap", action="store_true", help="Fetch SMAP data")
    operation.add_argument("--sentinel1", action="store_true", help="Fetch Sentinel-1 data")
    operation.add_argument("--all", action="store_true", help="Fetch all climate data")
    parser.add_argument("--location-id", required=True, help="Location UUID")
    args = parser.parse_args(argv)

    if not any((args.all, args.worldclim, args.ncep, args.modis, args.smap, args.sentinel1)):
        parser.print_help()
        return 1

    try:
        location_id = str(uuid.UUID(args.location_id))
    except (TypeError, ValueError, AttributeError):
        parser.error("--location-id must be a UUID")

    source = None
    if args.worldclim:
        source = "worldclim"
    elif args.ncep:
        source = "era5_land"
    elif args.modis:
        source = "modis_lst"
    elif args.smap:
        source = "smap_moisture"
    elif args.sentinel1:
        source = "sentinel1_sar"

    report = (
        _legacy_climate_report(_dispatch_signed_climate_worker(location_id))
        if args.all
        else _dispatch_signed_climate_source(
            location_id,
            source or "sentinel1_sar",
        )
    )
    print_json(report)
    return 1 if report.get("status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
