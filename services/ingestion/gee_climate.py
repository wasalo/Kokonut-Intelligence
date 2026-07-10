"""Google Earth Engine climate data fetching.

Fetches MODIS LST, SMAP soil moisture, Sentinel-1 SAR, and ERA5 Land
data via GEE for climate covariates. Replaces placeholder implementations
in climate_data.py with actual data fetching.

Usage:
    from services.ingestion.gee_climate import fetch_all_climate
    result = fetch_all_climate(conn, location_id, bbox)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ..common.logging import get_logger
from .base import log_ingestion, hash_payload

logger = get_logger("ingestion.gee_climate")


def _get_gee_client():
    """Initialize GEE client."""
    try:
        import ee
    except ImportError:
        logger.error("earthengine-api not installed")
        return None

    key_path = os.environ.get("GEE_SERVICE_ACCOUNT_KEY")
    if key_path:
        try:
            credentials = ee.ServiceAccountCredentials(None, key_path)
            ee.Initialize(credentials)
            return ee
        except Exception as e:
            logger.error("GEE init failed: %s", e)
            return None

    try:
        ee.Initialize()
        return ee
    except Exception as e:
        logger.error("GEE default init failed: %s", e)
        return None


def _build_bbox_geometry(ee, bbox: Dict[str, float]):
    """Build GEE geometry from bbox dict."""
    return ee.Geometry.Rectangle([bbox["west"], bbox["south"], bbox["east"], bbox["north"]])


def fetch_modis_lst(conn, location_id: str, bbox: Dict[str, float], lookback_days: int = 180) -> Dict[str, Any]:
    """Fetch MODIS MOD11A2 Land Surface Temperature via GEE.

    Dataset: MODIS/061/MOD11A2 (8-day LST, 1km resolution)
    Variables: LST_Day_1km, LST_Night_1km
    """
    ee = _get_gee_client()
    if not ee:
        return {"status": "error", "message": "GEE client not available"}

    bbox_geom = _build_bbox_geometry(ee, bbox)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=lookback_days)

    try:
        collection = (
            ee.ImageCollection("MODIS/061/MOD11A2")
            .filterBounds(bbox_geom)
            .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            .select(["LST_Day_1km", "LST_Night_1km"])
        )

        # Compute mean LST over the period
        mean_lst = collection.mean()
        stats = mean_lst.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=bbox_geom,
            scale=1000,
            maxPixels=1e9,
        ).getInfo()

        lst_day = stats.get("LST_Day_1km")
        lst_night = stats.get("LST_Night_1km")

        # Convert from Kelvin*0.02 to Celsius
        lst_day_c = round((lst_day * 0.02) - 273.15, 2) if lst_day else None
        lst_night_c = round((lst_night * 0.02) - 273.15, 2) if lst_night else None
        lst_mean_c = round((lst_day_c + lst_night_c) / 2, 2) if lst_day_c and lst_night_c else lst_day_c

        # Insert into PostgreSQL
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO modis_lst_summary
                (location_id, period_type, period_start, period_end,
                 mean_lst_day_c, mean_lst_night_c, mean_lst_c, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            location_id, "6month",
            start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"),
            lst_day_c, lst_night_c, lst_mean_c, "modis_mod11a2",
        ))
        record_id = str(cur.fetchone()[0])
        conn.commit()
        cur.close()

        log_ingestion(
            source_system="gee_api", source_table="modis_lst",
            source_id="MODIS/061/MOD11A2", target_table="modis_lst_summary",
            target_id=record_id, operation="insert",
            payload_hash=hash_payload({"lst_day": lst_day_c, "lst_night": lst_night_c}),
            status="success", rows_affected=1,
        )

        return {"status": "success", "record_id": record_id, "lst_day_c": lst_day_c, "lst_night_c": lst_night_c}
    except Exception as e:
        logger.error("MODIS LST fetch failed: %s", e)
        return {"status": "error", "message": str(e)}


def fetch_smap_moisture(conn, location_id: str, bbox: Dict[str, float], lookback_days: int = 180) -> Dict[str, Any]:
    """Fetch SMAP L3 soil moisture via GEE.

    Dataset: NASA/SMAP/SPL3SMP_E/005 (Enhanced L3, 9km, daily)
    Variables: sm_pm (soil moisture polar metric)
    """
    ee = _get_gee_client()
    if not ee:
        return {"status": "error", "message": "GEE client not available"}

    bbox_geom = _build_bbox_geometry(ee, bbox)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=lookback_days)

    try:
        collection = (
            ee.ImageCollection("NASA/SMAP/SPL3SMP_E/005")
            .filterBounds(bbox_geom)
            .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            .select(["sm_pm"])
        )

        mean_sm = collection.mean()
        stats = mean_sm.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=bbox_geom,
            scale=9000,
            maxPixels=1e9,
        ).getInfo()

        sm_value = stats.get("sm_pm")
        sm_m3 = round(float(sm_value), 4) if sm_value else None

        cur = conn.cursor()
        cur.execute("""
            INSERT INTO smap_soil_moisture
                (location_id, target_date, source, resolution_m,
                 soil_moisture_6m, metadata)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
        """, (
            location_id, end_date.strftime("%Y-%m-%d"),
            "smap_l3_daily_9km", 9000, sm_m3,
            json.dumps({"lookback_days": lookback_days}),
        ))
        record_id = str(cur.fetchone()[0])
        conn.commit()
        cur.close()

        log_ingestion(
            source_system="gee_api", source_table="smap_soil_moisture",
            source_id="NASA/SMAP/SPL3SMP_E/005", target_table="smap_soil_moisture",
            target_id=record_id, operation="insert",
            payload_hash=hash_payload({"soil_moisture": sm_m3}),
            status="success", rows_affected=1,
        )

        return {"status": "success", "record_id": record_id, "soil_moisture_m3": sm_m3}
    except Exception as e:
        logger.error("SMAP fetch failed: %s", e)
        return {"status": "error", "message": str(e)}


def fetch_sentinel1_sar(conn, location_id: str, bbox: Dict[str, float], lookback_days: int = 180) -> Dict[str, Any]:
    """Fetch Sentinel-1 GRD SAR backscatter via GEE.

    Dataset: COPERNICUS/S1_GRD (Ground Range Detected, 10m, 12-day)
    Variables: VH, VV backscatter
    """
    ee = _get_gee_client()
    if not ee:
        return {"status": "error", "message": "GEE client not available"}

    bbox_geom = _build_bbox_geometry(ee, bbox)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=lookback_days)

    try:
        collection = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(bbox_geom)
            .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .select(["VV", "VH"])
        )

        image_count = collection.size().getInfo()
        if image_count == 0:
            return {"status": "success", "record_id": None, "message": "No Sentinel-1 data"}

        mean_sar = collection.mean()
        stats = mean_sar.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=bbox_geom,
            scale=10,
            maxPixels=1e9,
        ).getInfo()

        vh_db = round(float(stats.get("VH", 0)), 4) if stats.get("VH") else None
        vv_db = round(float(stats.get("VV", 0)), 4) if stats.get("VV") else None
        vh_vv_ratio = round(vh_db / vv_db, 4) if vh_db and vv_db and vv_db != 0 else None

        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sentinel1_sar_summary
                (location_id, period_type, period_start, period_end,
                 mean_vh_db, mean_vv_db, vh_vv_ratio, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            location_id, "6month",
            start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"),
            vh_db, vv_db, vh_vv_ratio, "sentinel1_grd",
        ))
        record_id = str(cur.fetchone()[0])
        conn.commit()
        cur.close()

        log_ingestion(
            source_system="gee_api", source_table="sentinel1_sar",
            source_id="COPERNICUS/S1_GRD", target_table="sentinel1_sar_summary",
            target_id=record_id, operation="insert",
            payload_hash=hash_payload({"vh": vh_db, "vv": vv_db}),
            status="success", rows_affected=1,
        )

        return {"status": "success", "record_id": record_id, "vh_db": vh_db, "vv_db": vv_db, "images": image_count}
    except Exception as e:
        logger.error("Sentinel-1 SAR fetch failed: %s", e)
        return {"status": "error", "message": str(e)}


def fetch_era5_land(conn, location_id: str, bbox: Dict[str, float], lookback_days: int = 180) -> Dict[str, Any]:
    """Fetch ERA5 Land daily aggregates via GEE.

    Dataset: ECMWF/ERA5_LAND/DAILY_AGGR (9km, hourly → daily aggregated)
    Variables: temperature_2m, total_precipitation_sum, soil_moisture_0_to_7cm
    Replaces NCEP CFS with higher resolution data.
    """
    ee = _get_gee_client()
    if not ee:
        return {"status": "error", "message": "GEE client not available"}

    bbox_geom = _build_bbox_geometry(ee, bbox)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=lookback_days)

    try:
        collection = (
            ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
            .filterBounds(bbox_geom)
            .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            .select(["temperature_2m", "total_precipitation_sum", "soil_moisture_0_to_7cm"])
        )

        mean_data = collection.mean()
        stats = mean_data.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=bbox_geom,
            scale=9000,
            maxPixels=1e9,
        ).getInfo()

        temp_k = stats.get("temperature_2m")
        precip = stats.get("total_precipitation_sum")
        soil_moisture = stats.get("soil_moisture_0_to_7cm")

        temp_c = round(float(temp_k) - 273.15, 2) if temp_k else None
        precip_mm = round(float(precip), 2) if precip else None
        sm_m3 = round(float(soil_moisture), 4) if soil_moisture else None

        # Insert into ncep_weather_summary (using ERA5 data, same schema)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ncep_weather_summary
                (location_id, summary_type, avg_surface_temp_k,
                 avg_precipitation_kg_m2, avg_soil_moisture_kg_m2,
                 period_start, period_end, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            location_id, "6month", temp_k,
            precip_mm, sm_m3,
            start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"),
            "era5_land",
        ))
        record_id = str(cur.fetchone()[0])
        conn.commit()
        cur.close()

        log_ingestion(
            source_system="gee_api", source_table="era5_land",
            source_id="ECMWF/ERA5_LAND/DAILY_AGGR", target_table="ncep_weather_summary",
            target_id=record_id, operation="insert",
            payload_hash=hash_payload({"temp_c": temp_c, "precip_mm": precip_mm}),
            status="success", rows_affected=1,
        )

        return {
            "status": "success",
            "record_id": record_id,
            "temperature_c": temp_c,
            "precipitation_mm": precip_mm,
            "soil_moisture_m3": sm_m3,
        }
    except Exception as e:
        logger.error("ERA5 Land fetch failed: %s", e)
        return {"status": "error", "message": str(e)}


def fetch_all_climate(conn, location_id: str, bbox: Dict[str, float]) -> Dict[str, Any]:
    """Fetch all climate data sources for a location via GEE.

    Returns:
        Summary of all fetch results.
    """
    results = {
        "modis_lst": fetch_modis_lst(conn, location_id, bbox),
        "smap_moisture": fetch_smap_moisture(conn, location_id, bbox),
        "sentinel1_sar": fetch_sentinel1_sar(conn, location_id, bbox),
        "era5_land": fetch_era5_land(conn, location_id, bbox),
    }

    success = sum(1 for r in results.values() if r.get("status") == "success")
    failed = sum(1 for r in results.values() if r.get("status") == "error")

    return {
        "status": "success",
        "location_id": location_id,
        "sources_success": success,
        "sources_failed": failed,
        "results": results,
    }
