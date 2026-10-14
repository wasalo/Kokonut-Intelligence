"""Climate data ingestion service.

Builds a latitude-based bioclimatic proxy for WorldClim-shaped fields and
fetches ERA5, MODIS, SMAP, and Sentinel-1 data through Google Earth Engine.

Usage:
    python3 -m services.ingestion.climate_data --worldclim --location-id UUID
    python3 -m services.ingestion.climate_data --ncep --location-id UUID
    python3 -m services.ingestion.climate_data --modis --location-id UUID
    python3 -m services.ingestion.climate_data --smap --location-id UUID
    python3 -m services.ingestion.climate_data --sentinel1 --location-id UUID
    python3 -m services.ingestion.climate_data --all --location-id UUID
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.cli import print_json

from ..common.logging import get_logger
from .base import get_db, hash_payload, log_ingestion

logger = get_logger("ingestion.climate_data")


def _query_location_bbox(conn, location_id: str) -> Optional[Dict[str, Any]]:
    """Get location bounding box from plot geometries."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT
            ST_XMin(ST_Extent(p.geometry)) AS west,
            ST_YMin(ST_Extent(p.geometry)) AS south,
            ST_XMax(ST_Extent(p.geometry)) AS east,
            ST_YMax(ST_Extent(p.geometry)) AS north
        FROM plot p
        JOIN farm f ON p.farm_id = f.id
        WHERE f.location_id = %s AND p.geometry IS NOT NULL
    """,
        (location_id,),
    )
    row = cur.fetchone()
    cur.close()
    if row and row["west"] is not None:
        return {
            "west": float(row["west"]),
            "south": float(row["south"]),
            "east": float(row["east"]),
            "north": float(row["north"]),
        }
    return None


def _query_location_centroid(conn, location_id: str) -> Optional[Dict[str, float]]:
    """Get location centroid."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT ST_Y(centroid) AS lat, ST_X(centroid) AS lon
        FROM location WHERE id = %s AND centroid IS NOT NULL
    """,
        (location_id,),
    )
    row = cur.fetchone()
    cur.close()
    if row and row["lat"] is not None:
        return {"lat": float(row["lat"]), "lon": float(row["lon"])}
    return None


def fetch_worldclim(conn, location_id: str) -> Dict[str, Any]:
    """Store latitude-derived bioclimatic estimates for a location.

    This compatibility path does not download WorldClim rasters. It records
    the existing latitude formula as a proxy, with explicit provenance and no
    claimed spatial resolution.
    """
    centroid = _query_location_centroid(conn, location_id)
    if not centroid:
        logger.warning("No centroid for location %s, skipping WorldClim", location_id)
        return {"status": "skipped", "reason": "no_centroid"}

    lat, lon = centroid["lat"], centroid["lon"]

    bio_variables = {f"bio_{bio}": _estimate_bioclim(lat, lon, bio) for bio in range(1, 20)}

    metadata = {
        "estimation_method": "latitude_proxy_v1",
        "reference_period": "1970-2000",
        "estimated_bioclimatic_variables": bio_variables,
    }
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO worldclim_climate
            (location_id, bio1_mean_annual_temp, bio4_temp_seasonality,
             bio5_max_temp_warmest_month, bio6_min_temp_coldest_month,
             bio12_annual_precipitation, bio15_precip_seasonality,
             bio16_precip_wettest_quarter, bio17_precip_driest_quarter,
             temp_range, source, resolution_m, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                'latitude_proxy_v1', NULL, %s::jsonb)
        ON CONFLICT (location_id) WHERE plot_id IS NULL DO UPDATE SET
            bio1_mean_annual_temp = EXCLUDED.bio1_mean_annual_temp,
            bio4_temp_seasonality = EXCLUDED.bio4_temp_seasonality,
            bio5_max_temp_warmest_month = EXCLUDED.bio5_max_temp_warmest_month,
            bio6_min_temp_coldest_month = EXCLUDED.bio6_min_temp_coldest_month,
            bio12_annual_precipitation = EXCLUDED.bio12_annual_precipitation,
            bio15_precip_seasonality = EXCLUDED.bio15_precip_seasonality,
            bio16_precip_wettest_quarter = EXCLUDED.bio16_precip_wettest_quarter,
            bio17_precip_driest_quarter = EXCLUDED.bio17_precip_driest_quarter,
            temp_range = EXCLUDED.temp_range,
            source = EXCLUDED.source,
            resolution_m = EXCLUDED.resolution_m,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING id
    """,
        (
            location_id,
            bio_variables["bio_1"],
            bio_variables["bio_4"],
            bio_variables["bio_5"],
            bio_variables["bio_6"],
            bio_variables["bio_12"],
            bio_variables["bio_15"],
            bio_variables["bio_16"],
            bio_variables["bio_17"],
            bio_variables["bio_7"],
            json.dumps(metadata),
        ),
    )
    record_id = str(cur.fetchone()[0])
    cur.close()
    conn.commit()

    log_ingestion(
        source_system="latitude_proxy",
        source_table="worldclim_climate",
        source_id="latitude_proxy_v1",
        target_table="worldclim_climate",
        target_id=record_id,
        operation="upsert",
        payload_hash=hash_payload(bio_variables),
        status="success",
        rows_affected=1,
    )

    return {
        "status": "success",
        "record_id": record_id,
        "variables": len(bio_variables),
        "source": "latitude_proxy_v1",
        "estimated": True,
    }


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


def fetch_ncep(conn, location_id: str) -> Dict[str, Any]:
    """Fetch climate summaries via GEE ERA5 Land (replaces NCEP CFS).

    ERA5 Land provides higher resolution (9km vs 50km) than NCEP CFS
    and is accessible through the existing GEE infrastructure.
    """
    bbox = _query_location_bbox(conn, location_id)
    if not bbox:
        centroid = _query_location_centroid(conn, location_id)
        if not centroid:
            return {"status": "skipped", "reason": "no_geometry"}
        bbox = {
            "west": centroid["lon"] - 0.05,
            "south": centroid["lat"] - 0.05,
            "east": centroid["lon"] + 0.05,
            "north": centroid["lat"] + 0.05,
        }

    from .gee_climate import fetch_era5_land

    return fetch_era5_land(conn, location_id, bbox)


def fetch_modis(conn, location_id: str) -> Dict[str, Any]:
    """Fetch MODIS MOD11A2 land surface temperature via GEE."""
    bbox = _query_location_bbox(conn, location_id)
    if not bbox:
        centroid = _query_location_centroid(conn, location_id)
        if not centroid:
            return {"status": "skipped", "reason": "no_geometry"}
        bbox = {
            "west": centroid["lon"] - 0.05,
            "south": centroid["lat"] - 0.05,
            "east": centroid["lon"] + 0.05,
            "north": centroid["lat"] + 0.05,
        }

    from .gee_climate import fetch_modis_lst

    return fetch_modis_lst(conn, location_id, bbox)


def fetch_smap(conn, location_id: str) -> Dict[str, Any]:
    """Fetch SMAP L3 soil moisture via GEE."""
    bbox = _query_location_bbox(conn, location_id)
    if not bbox:
        centroid = _query_location_centroid(conn, location_id)
        if not centroid:
            return {"status": "skipped", "reason": "no_geometry"}
        bbox = {
            "west": centroid["lon"] - 0.05,
            "south": centroid["lat"] - 0.05,
            "east": centroid["lon"] + 0.05,
            "north": centroid["lat"] + 0.05,
        }

    from .gee_climate import fetch_smap_moisture

    return fetch_smap_moisture(conn, location_id, bbox)


def fetch_sentinel1(conn, location_id: str) -> Dict[str, Any]:
    """Fetch Sentinel-1 SAR backscatter via GEE."""
    bbox = _query_location_bbox(conn, location_id)
    if not bbox:
        centroid = _query_location_centroid(conn, location_id)
        if not centroid:
            return {"status": "skipped", "reason": "no_geometry"}
        bbox = {
            "west": centroid["lon"] - 0.05,
            "south": centroid["lat"] - 0.05,
            "east": centroid["lon"] + 0.05,
            "north": centroid["lat"] + 0.05,
        }

    from .gee_climate import fetch_sentinel1_sar

    return fetch_sentinel1_sar(conn, location_id, bbox)


def run_all(conn, location_id: str) -> Dict[str, Any]:
    """Run all climate data fetchers for a location."""
    results = {}
    results["worldclim"] = fetch_worldclim(conn, location_id)
    results["ncep"] = fetch_ncep(conn, location_id)
    results["modis"] = fetch_modis(conn, location_id)
    results["smap"] = fetch_smap(conn, location_id)
    results["sentinel1"] = fetch_sentinel1(conn, location_id)

    success = sum(1 for r in results.values() if r.get("status") == "success")
    skipped = sum(1 for r in results.values() if r.get("status") == "skipped")

    return {
        "location_id": location_id,
        "results": results,
        "success": success,
        "skipped": skipped,
        "total": len(results),
    }


def main(argv: Optional[List[str]] = None) -> int:
    """Run the climate-data CLI and return its process status."""
    parser = argparse.ArgumentParser(description="Climate data ingestion")
    parser.add_argument("--worldclim", action="store_true", help="Fetch WorldClim data")
    parser.add_argument("--ncep", action="store_true", help="Fetch NCEP data")
    parser.add_argument("--modis", action="store_true", help="Fetch MODIS data")
    parser.add_argument("--smap", action="store_true", help="Fetch SMAP data")
    parser.add_argument("--sentinel1", action="store_true", help="Fetch Sentinel-1 data")
    parser.add_argument("--all", action="store_true", help="Fetch all climate data")
    parser.add_argument("--location-id", required=True, help="Location UUID")
    args = parser.parse_args(argv)

    if not any((args.all, args.worldclim, args.ncep, args.modis, args.smap, args.sentinel1)):
        parser.print_help()
        return 1

    conn = get_db()
    try:
        if args.all:
            result = run_all(conn, args.location_id)
        elif args.worldclim:
            result = fetch_worldclim(conn, args.location_id)
        elif args.ncep:
            result = fetch_ncep(conn, args.location_id)
        elif args.modis:
            result = fetch_modis(conn, args.location_id)
        elif args.smap:
            result = fetch_smap(conn, args.location_id)
        else:
            result = fetch_sentinel1(conn, args.location_id)
        print_json(result)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
