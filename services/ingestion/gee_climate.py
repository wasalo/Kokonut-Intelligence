"""Google Earth Engine climate fetching for the signed climate worker.

Provider calculations stay here; all canonical persistence is delegated to
the bounded signed climate writer. Legacy audit payloads accompany summaries
so the worker preserves the existing ingestion digest contract.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict

from ..common.logging import get_logger

logger = get_logger("ingestion.gee_climate")


def _get_gee_client(*, worker_credentials: bool = False):
    """Initialize GEE, optionally requiring the isolated climate key path."""
    try:
        import ee
    except ImportError:
        logger.error("earthengine-api not installed")
        return None

    key_path = (
        os.environ.get("KOKONUT_CLIMATE_GEE_SERVICE_ACCOUNT_KEY")
        if worker_credentials
        else os.environ.get("GEE_SERVICE_ACCOUNT_KEY")
    )
    if worker_credentials and (not key_path or not os.path.isfile(key_path)):
        logger.error("climate worker GEE service-account file is unavailable")
        return None
    if key_path:
        try:
            credentials = ee.ServiceAccountCredentials(None, key_path)
            ee.Initialize(credentials)
            return ee
        except Exception as e:
            logger.error("GEE init failed (%s)", type(e).__name__)
            return None

    try:
        ee.Initialize()
        return ee
    except Exception as e:
        logger.error("GEE default init failed (%s)", type(e).__name__)
        return None


def _build_bbox_geometry(ee, bbox: Dict[str, float]):
    """Build GEE geometry from bbox dict."""
    return ee.Geometry.Rectangle([bbox["west"], bbox["south"], bbox["east"], bbox["north"]])


def _period(lookback_days: int) -> tuple[datetime, datetime]:
    if isinstance(lookback_days, bool) or not isinstance(lookback_days, int) or lookback_days <= 0:
        raise ValueError("lookback_days must be a positive integer")
    end_date = datetime.now(timezone.utc)
    return end_date - timedelta(days=lookback_days), end_date


def _rounded(value: Any, digits: int) -> float | None:
    return round(float(value), digits) if value is not None else None


def _persist_summary(
    *,
    provider_summary: dict,
    legacy_audit_payload: dict,
    persist_summary: Callable[[dict, dict], str],
) -> str:
    """Persist through the signed writer while retaining the legacy audit payload."""
    if not callable(persist_summary):
        raise ValueError("signed climate persistence callback is required")
    return persist_summary(provider_summary, legacy_audit_payload)


def _metadata(
    dataset: str,
    start_date: datetime,
    end_date: datetime,
    lookback_days: int,
    temporal_reducer: str,
    resolution_m: int,
    value_units: dict[str, str],
) -> str:
    return json.dumps({
        "dataset": dataset,
        "lookback_days": lookback_days,
        "period_start": start_date.date().isoformat(),
        "period_end_exclusive": end_date.date().isoformat(),
        "temporal_reducer": temporal_reducer,
        "spatial_reducer": "mean",
        "resolution_m": resolution_m,
        "value_units": value_units,
    })


def fetch_modis_lst(
    conn,
    location_id: str,
    bbox: Dict[str, float],
    lookback_days: int = 180,
    *,
    worker_credentials: bool = False,
    persist_summary: Callable[[dict, dict], str] | None = None,
) -> Dict[str, Any]:
    """Fetch 180-day MODIS MOD11A2 mean daytime and nighttime LST.

    The catalog scale factor (0.02 K) is applied before conversion to Celsius.
    The canonical table stores the spatial mean of the temporal mean as-of
    ``target_date``.
    """
    if not worker_credentials or not callable(persist_summary):
        return {"status": "error", "message": "signed climate writer is required"}

    ee = _get_gee_client(worker_credentials=True)
    if not ee:
        return {"status": "error", "message": "GEE client not available"}

    try:
        start_date, end_date = _period(lookback_days)
        bbox_geom = _build_bbox_geometry(ee, bbox)
        collection = (
            ee.ImageCollection("MODIS/061/MOD11A2")
            .filterBounds(bbox_geom)
            .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            .select(["LST_Day_1km", "LST_Night_1km"])
        )
        stats = collection.mean().reduceRegion(
            reducer=ee.Reducer.mean(), geometry=bbox_geom, scale=1000, maxPixels=1e9,
        ).getInfo()

        lst_day_c = _rounded(stats.get("LST_Day_1km"), 2)
        lst_night_c = _rounded(stats.get("LST_Night_1km"), 2)
        lst_day_c = round(lst_day_c * 0.02 - 273.15, 2) if lst_day_c is not None else None
        lst_night_c = round(lst_night_c * 0.02 - 273.15, 2) if lst_night_c is not None else None
        metadata = _metadata("MODIS/061/MOD11A2", start_date, end_date,
                             lookback_days, "mean", 1000,
                             {"lst_day_mean_6m": "degC", "lst_night_mean_6m": "degC"})
        provider_summary = {
            "source_key": "modis_lst",
            "source_table": "modis_lst",
            "source_id": "MODIS/061/MOD11A2",
            "target_table": "modis_lst_summary",
            "target_date": end_date.date().isoformat(),
            "resolution_m": 1000,
            "values": {"lst_day_mean_6m": lst_day_c, "lst_night_mean_6m": lst_night_c},
            "metadata": json.loads(metadata),
        }
        record_id = _persist_summary(
            provider_summary=provider_summary,
            legacy_audit_payload={
                "lst_day_mean_6m_c": lst_day_c,
                "lst_night_mean_6m_c": lst_night_c,
            },
            persist_summary=persist_summary,
        )
        return {"status": "success", "record_id": record_id,
                "lst_day_c": lst_day_c, "lst_night_c": lst_night_c}
    except Exception as e:
        logger.error("MODIS LST fetch failed (%s)", type(e).__name__)
        return {"status": "error", "message": f"MODIS LST fetch failed ({type(e).__name__})"}


def fetch_smap_moisture(
    conn,
    location_id: str,
    bbox: Dict[str, float],
    lookback_days: int = 180,
    *,
    worker_credentials: bool = False,
    persist_summary: Callable[[dict, dict], str] | None = None,
) -> Dict[str, Any]:
    """Fetch SMAP L3 Enhanced 9km PM soil-moisture volume fraction.

    Collection 006 contains the post-2023 data and exposes the
    ``soil_moisture_pm`` band in volume fraction.
    """
    if not worker_credentials or not callable(persist_summary):
        return {"status": "error", "message": "signed climate writer is required"}

    ee = _get_gee_client(worker_credentials=True)
    if not ee:
        return {"status": "error", "message": "GEE client not available"}

    try:
        start_date, end_date = _period(lookback_days)
        bbox_geom = _build_bbox_geometry(ee, bbox)
        collection = (
            ee.ImageCollection("NASA/SMAP/SPL3SMP_E/006")
            .filterBounds(bbox_geom)
            .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            .select(["soil_moisture_pm"])
        )
        stats = collection.mean().reduceRegion(
            reducer=ee.Reducer.mean(), geometry=bbox_geom, scale=9000, maxPixels=1e9,
        ).getInfo()
        soil_moisture = _rounded(stats.get("soil_moisture_pm"), 4)
        metadata = _metadata("NASA/SMAP/SPL3SMP_E/006", start_date, end_date,
                             lookback_days, "mean", 9000,
                             {"soil_moisture_6m": "volume_fraction"})
        provider_summary = {
            "source_key": "smap_moisture",
            "source_table": "smap_soil_moisture",
            "source_id": "NASA/SMAP/SPL3SMP_E/006",
            "target_table": "smap_soil_moisture",
            "target_date": end_date.date().isoformat(),
            "resolution_m": 9000,
            "values": {"soil_moisture_6m": soil_moisture},
            "metadata": json.loads(metadata),
        }
        record_id = _persist_summary(
            provider_summary=provider_summary,
            legacy_audit_payload={
                "soil_moisture_6m_volume_fraction": soil_moisture,
            },
            persist_summary=persist_summary,
        )
        return {"status": "success", "record_id": record_id,
                "soil_moisture_volume_fraction": soil_moisture}
    except Exception as e:
        logger.error("SMAP fetch failed (%s)", type(e).__name__)
        return {"status": "error", "message": f"SMAP fetch failed ({type(e).__name__})"}


def fetch_sentinel1_sar(
    conn,
    location_id: str,
    bbox: Dict[str, float],
    lookback_days: int = 180,
    *,
    worker_credentials: bool = False,
    persist_summary: Callable[[dict, dict], str] | None = None,
) -> Dict[str, Any]:
    """Fetch 180-day Sentinel-1 GRD temporal median VV/VH backscatter in dB."""
    if not worker_credentials or not callable(persist_summary):
        return {"status": "error", "message": "signed climate writer is required"}

    ee = _get_gee_client(worker_credentials=True)
    if not ee:
        return {"status": "error", "message": "GEE client not available"}

    try:
        start_date, end_date = _period(lookback_days)
        bbox_geom = _build_bbox_geometry(ee, bbox)
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

        stats = collection.median().reduceRegion(
            reducer=ee.Reducer.mean(), geometry=bbox_geom, scale=10, maxPixels=1e9,
        ).getInfo()
        vh_db = _rounded(stats.get("VH"), 4)
        vv_db = _rounded(stats.get("VV"), 4)
        metadata = _metadata("COPERNICUS/S1_GRD", start_date, end_date,
                             lookback_days, "median", 10,
                             {"vh_median_6m": "dB", "vv_median_6m": "dB"})
        provider_summary = {
            "source_key": "sentinel1_sar",
            "source_table": "sentinel1_sar",
            "source_id": "COPERNICUS/S1_GRD",
            "target_table": "sentinel1_sar_summary",
            "target_date": end_date.date().isoformat(),
            "resolution_m": 10,
            "values": {"vh_median_6m": vh_db, "vv_median_6m": vv_db},
            "metadata": json.loads(metadata),
        }
        record_id = _persist_summary(
            provider_summary=provider_summary,
            legacy_audit_payload={
                "vh_median_6m_db": vh_db,
                "vv_median_6m_db": vv_db,
            },
            persist_summary=persist_summary,
        )
        return {"status": "success", "record_id": record_id,
                "vh_db": vh_db, "vv_db": vv_db, "images": image_count}
    except Exception as e:
        logger.error("Sentinel-1 SAR fetch failed (%s)", type(e).__name__)
        return {"status": "error", "message": f"Sentinel-1 SAR fetch failed ({type(e).__name__})"}


def fetch_era5_land(
    conn,
    location_id: str,
    bbox: Dict[str, float],
    lookback_days: int = 180,
    *,
    worker_credentials: bool = False,
    persist_summary: Callable[[dict, dict], str] | None = None,
) -> Dict[str, Any]:
    """Fetch 180-day ERA5-Land daily climate summaries via GEE.

    Temperatures are stored in Celsius, total precipitation in millimeters,
    and soil moisture as volumetric fraction, matching the canonical summary
    table's semantic columns.
    """
    if not worker_credentials or not callable(persist_summary):
        return {"status": "error", "message": "signed climate writer is required"}

    ee = _get_gee_client(worker_credentials=True)
    if not ee:
        return {"status": "error", "message": "GEE client not available"}

    try:
        start_date, end_date = _period(lookback_days)
        bbox_geom = _build_bbox_geometry(ee, bbox)
        collection = (
            ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
            .filterBounds(bbox_geom)
            .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        )
        temperature_soil = collection.select([
            "temperature_2m", "temperature_2m_max", "temperature_2m_min",
            "volumetric_soil_water_layer_1",
        ]).mean().reduceRegion(
            reducer=ee.Reducer.mean(), geometry=bbox_geom, scale=11132, maxPixels=1e9,
        ).getInfo()
        precipitation = collection.select(["total_precipitation_sum"]).sum().reduceRegion(
            reducer=ee.Reducer.mean(), geometry=bbox_geom, scale=11132, maxPixels=1e9,
        ).getInfo().get("total_precipitation_sum")

        def kelvin_to_celsius(name: str) -> float | None:
            value = temperature_soil.get(name)
            return round(float(value) - 273.15, 2) if value is not None else None

        mean_temp_c = kelvin_to_celsius("temperature_2m")
        max_temp_c = kelvin_to_celsius("temperature_2m_max")
        min_temp_c = kelvin_to_celsius("temperature_2m_min")
        precipitation_mm = round(float(precipitation) * 1000, 2) if precipitation is not None else None
        soil_moisture = _rounded(temperature_soil.get("volumetric_soil_water_layer_1"), 4)
        metadata = _metadata(
            "ECMWF/ERA5_LAND/DAILY_AGGR", start_date, end_date, lookback_days,
            "mean (temperature/soil); sum (precipitation)", 11132,
            {
                "soil_moisture_6m": "volume_fraction",
                "mean_temp_6m": "degC",
                "max_temp_6m": "degC",
                "min_temp_6m": "degC",
                "precipitation_6m": "mm",
            },
        )
        payload = {
            "soil_moisture_6m_volume_fraction": soil_moisture,
            "mean_temp_6m_c": mean_temp_c,
            "max_temp_6m_c": max_temp_c,
            "min_temp_6m_c": min_temp_c,
            "precipitation_6m_mm": precipitation_mm,
        }
        provider_summary = {
            "source_key": "era5_land",
            "source_table": "era5_land",
            "source_id": "ECMWF/ERA5_LAND/DAILY_AGGR",
            "target_table": "ncep_weather_summary",
            "target_date": end_date.date().isoformat(),
            "resolution_m": 11132,
            "values": {
                "soil_moisture_6m": soil_moisture,
                "mean_temp_6m": mean_temp_c,
                "max_temp_6m": max_temp_c,
                "min_temp_6m": min_temp_c,
                "precipitation_6m": precipitation_mm,
            },
            "metadata": json.loads(metadata),
        }
        record_id = _persist_summary(
            provider_summary=provider_summary,
            legacy_audit_payload=payload,
            persist_summary=persist_summary,
        )
        return {"status": "success", "record_id": record_id,
                "temperature_c": mean_temp_c, "precipitation_mm": precipitation_mm,
                "soil_moisture_volume_fraction": soil_moisture}
    except Exception as e:
        logger.error("ERA5 Land fetch failed (%s)", type(e).__name__)
        return {"status": "error", "message": f"ERA5 Land fetch failed ({type(e).__name__})"}


def fetch_all_climate(conn, location_id: str, bbox: Dict[str, float]) -> Dict[str, Any]:
    """Dispatch a full climate refresh through the signed worker boundary."""
    from .climate_data import _dispatch_signed_climate_worker

    return _dispatch_signed_climate_worker(location_id)
