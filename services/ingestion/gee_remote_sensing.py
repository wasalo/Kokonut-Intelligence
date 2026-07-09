"""Google Earth Engine remote sensing adapter.

Fetches Sentinel-2 L2A surface reflectance data via GEE,
computes spectral indices, and dual-writes to PostgreSQL + ClickHouse.

Requires:
    - earthengine-api package
    - GEE_SERVICE_ACCOUNT_KEY env var pointing to service account JSON
    - GCP project with Earth Engine API enabled

Usage (from remote_sensing_fetcher):
    from .gee_remote_sensing import fetch_gee
    result = fetch_gee(conn, job)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..common.logging import get_logger
from .base import log_ingestion, hash_payload

logger = get_logger("ingestion.gee_remote_sensing")

# Sentinel-2 band mapping
S2_BANDS = {
    "B2": "band_blue",
    "B3": "band_green",
    "B4": "band_red",
    "B5": "band_red_edge_1",
    "B6": "band_red_edge_2",
    "B7": "band_red_edge_3",
    "B8": "band_nir",
    "B8A": "band_nir_narrow",
    "B11": "band_swir1",
    "B12": "band_swir2",
}


def _get_gee_client():
    """Initialize GEE client with service account credentials."""
    try:
        import ee
    except ImportError:
        logger.error("earthengine-api not installed. Run: pip install earthengine-api")
        return None

    key_path = os.environ.get("GEE_SERVICE_ACCOUNT_KEY")
    if key_path:
        try:
            credentials = ee.ServiceAccountCredentials(None, key_path)
            ee.Initialize(credentials)
            logger.info("GEE initialized with service account")
            return ee
        except Exception as e:
            logger.error("GEE service account init failed: %s", e)
            return None

    # Try default credentials (for development)
    try:
        ee.Initialize()
        logger.info("GEE initialized with default credentials")
        return ee
    except Exception as e:
        logger.error("GEE default init failed: %s", e)
        return None


def _compute_indices(bands: Dict[str, float]) -> Dict[str, float]:
    """Compute spectral indices from Sentinel-2 bands.

    Uses the same formulas as spectral_indices.py for consistency.
    """
    indices = {}

    # NDVI
    nir = bands.get("band_nir")
    red = bands.get("band_red")
    if nir is not None and red is not None and (nir + red) != 0:
        indices["ndvi"] = round((nir - red) / (nir + red), 4)

    # NDRE
    red_edge = bands.get("band_red_edge_1")
    if nir is not None and red_edge is not None and (nir + red_edge) != 0:
        indices["ndre"] = round((nir - red_edge) / (nir + red_edge), 4)

    # EVI
    blue = bands.get("band_blue")
    if all(v is not None for v in [nir, red, blue]):
        denom = nir + 6 * red - 7.5 * blue + 1
        if denom != 0:
            indices["evi"] = round(2.5 * (nir - red) / denom, 4)

    # SAVI
    L = 0.5
    if nir is not None and red is not None and (nir + red + L) != 0:
        indices["savi"] = round(((nir - red) / (nir + red + L)) * (1 + L), 4)

    # MSAVI
    if nir is not None and red is not None:
        denom = 2 * nir + 1 - ((2 * nir + 1) ** 2 - 8 * (nir - red)) ** 0.5
        if denom != 0:
            indices["msavi"] = round((2 * nir + 1 - denom) / 2, 4)

    # NDWI
    green = bands.get("band_green")
    if nir is not None and green is not None and (nir + green) != 0:
        indices["ndwi"] = round((green - nir) / (green + nir), 4)

    # BSI
    swir1 = bands.get("band_swir1")
    if all(v is not None for v in [swir1, red, nir, blue]):
        numer = (swir1 + red) - (nir + blue)
        denom = (swir1 + red) + (nir + blue)
        if denom != 0:
            indices["bsi"] = round(numer / denom, 4)

    # SATVI
    swir2 = bands.get("band_swir2")
    if all(v is not None for v in [swir1, red, green]):
        denom = (swir1 + red + 0.5)
        if denom != 0:
            indices["satvi"] = round(((swir1 - red) / denom) * 1.5, 4)

    # NBR2
    if swir1 is not None and swir2 is not None and (swir1 + swir2) != 0:
        indices["nbr2"] = round((swir1 - swir2) / (swir1 + swir2), 4)

    # NDTI
    if swir1 is not None and green is not None and (swir1 + green) != 0:
        indices["ndti"] = round((swir1 - green) / (swir1 + green), 4)

    # LSWI
    if nir is not None and swir1 is not None and (nir + swir1) != 0:
        indices["lswi"] = round((nir - swir1) / (nir + swir1), 4)

    # Brightness Index
    if red is not None and green is not None:
        indices["brightness_index"] = round((red * green) ** 0.5, 4)

    # Tasseled Cap (Sentinel-2 coefficients approximation)
    if all(v is not None for v in [blue, green, red, nir, swir1, swir2]):
        indices["tc_brightness"] = round(
            0.3510 * blue + 0.3813 * green + 0.3437 * red + 0.7196 * nir + 0.2396 * swir1 + 0.1949 * swir2, 4
        )
        indices["tc_greenness"] = round(
            -0.3599 * blue - 0.3533 * green - 0.4734 * red + 0.6633 * nir + 0.0087 * swir1 - 0.2856 * swir2, 4
        )
        indices["tc_wetness"] = round(
            0.2578 * blue + 0.2305 * green + 0.0883 * red + 0.1071 * nir - 0.7611 * swir1 - 0.5308 * swir2, 4
        )

    return indices


def fetch_gee(conn, job: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch Sentinel-2 data via Google Earth Engine.

    Args:
        conn: PostgreSQL connection.
        job: Remote sensing job record.

    Returns:
        Dict with status, observations count, and details.
    """
    ee = _get_gee_client()
    if ee is None:
        return {"status": "error", "message": "GEE client not available", "observations": 0}

    bbox = _resolve_bbox(job)
    if not bbox:
        return {"status": "error", "message": "No bbox available", "observations": 0}

    location_id = str(job["location_id"])
    cloud_max = float(job.get("cloud_max_pct", 20))

    # Create bbox geometry for GEE
    bbox_geom = ee.Geometry.Rectangle([bbox["west"], bbox["south"], bbox["east"], bbox["north"]])

    # Date range
    end_date = datetime.now(timezone.utc)
    from datetime import timedelta
    start_date = end_date - timedelta(days=job.get("cadence_days", 7) * 2)

    # Load Sentinel-2 Surface Reflectance collection
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(bbox_geom)
        .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_max))
    )

    # Get image count
    image_count = collection.size().getInfo()
    if image_count == 0:
        logger.info("No cloud-free Sentinel-2 images for location %s", location_id[:8])
        return {"status": "success", "observations": 0, "message": "No cloud-free images"}

    # Compute median composite
    composite = collection.median()

    # Sample band values at the centroid of the bbox
    centroid = bbox_geom.centroid()
    sample = composite.sampleRegion(
        collection=ee.FeatureCollection([ee.Feature(centroid)]),
        scale=10,
        numPixels=1,
    ).getInfo()

    if not sample.get("features"):
        return {"status": "success", "observations": 0, "message": "No sample data"}

    properties = sample["features"][0]["properties"]

    # Extract bands
    bands = {}
    for gee_band, col_name in S2_BANDS.items():
        val = properties.get(gee_band)
        bands[col_name] = round(float(val), 4) if val is not None else None

    # Compute indices
    indices = _compute_indices(bands)

    # Build observation record
    now = datetime.now(timezone.utc)
    record = {
        "plot_id": job.get("plot_id"),
        "location_id": location_id,
        "observation_date": now.strftime("%Y-%m-%d"),
        "source": "sentinel-2",
        "source_system": "gee_api",
        "cloud_cover_pct": cloud_max,
        **bands,
        **indices,
        "metadata": json.dumps({
            "gee_image_count": image_count,
            "bbox": bbox,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
        }),
    }

    # Insert into PostgreSQL
    pg_id = _insert_pg(conn, record)

    # Insert into ClickHouse
    record["id"] = pg_id
    _insert_ch(record)

    log_ingestion(
        source_system="gee_api",
        source_table="sentinel2",
        source_id=f"median_composite_{image_count}_images",
        target_table="remote_sensing_observation",
        target_id=pg_id,
        operation="insert",
        payload_hash=hash_payload(record),
        status="success",
        rows_affected=1,
    )

    return {"status": "success", "observations": 1, "pg_id": pg_id, "bands": len(bands), "indices": len(indices)}


def _resolve_bbox(job: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Resolve bbox from job dict or derive from location plots."""
    # Check if fetcher already resolved bbox
    if job.get("_resolved_bbox"):
        return job["_resolved_bbox"]
    return None


def _insert_pg(conn, record: dict) -> str:
    """Insert observation into PostgreSQL."""
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO remote_sensing_observation
            (plot_id, location_id, observation_date, source,
             ndvi, ndre, evi, savi, msavi, ndwi,
             satvi, bsi, nbr2, ndti, lswi,
             brightness_index, tc_brightness, tc_greenness, tc_wetness,
             band_blue, band_green, band_red, band_nir, band_swir1, band_swir2,
             cloud_cover_pct, source_system, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        RETURNING id
        """,
        (
            record.get("plot_id"), record.get("location_id"),
            record["observation_date"], record.get("source", "sentinel-2"),
            record.get("ndvi"), record.get("ndre"),
            record.get("evi"), record.get("savi"),
            record.get("msavi"), record.get("ndwi"),
            record.get("satvi"), record.get("bsi"),
            record.get("nbr2"), record.get("ndti"),
            record.get("lswi"),
            record.get("brightness_index"),
            record.get("tc_brightness"), record.get("tc_greenness"),
            record.get("tc_wetness"),
            record.get("band_blue"), record.get("band_green"),
            record.get("band_red"), record.get("band_nir"),
            record.get("band_swir1"), record.get("band_swir2"),
            record.get("cloud_cover_pct"),
            record.get("source_system", "gee_api"),
            record.get("metadata", "{}"),
        ),
    )
    record_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return record_id


def _insert_ch(record: dict) -> None:
    """Insert observation into ClickHouse."""
    import requests as req
    from .config import CH_HOST, CH_PORT, CH_USER, CH_PASSWORD

    ch_url = f"http://{CH_HOST}:{CH_PORT}"
    ts = f"{record['observation_date']} 00:00:00.000"
    source_system = record.get("source_system", "gee_api")

    query = f"""INSERT INTO remote_sensing_events
        (timestamp, observation_id, location_id, plot_id, source,
         ndvi, ndre, evi, savi, canopy_cover_pct, ndwi, cloud_cover_pct,
         msavi, satvi, bsi, nbr2, ndti, lswi,
         brightness_index, tc_brightness, tc_greenness, tc_wetness,
         band_blue, band_green, band_red, band_nir, band_swir1, band_swir2,
         source_system, metadata)
        VALUES (
            '{ts}',
            '{record.get("id", "")}',
            '{record.get("location_id", "")}',
            '{record.get("plot_id") or ""}',
            '{record.get("source", "sentinel-2")}',
            {_ch_num(record.get("ndvi"))},
            {_ch_num(record.get("ndre"))},
            {_ch_num(record.get("evi"))},
            {_ch_num(record.get("savi"))},
            {_ch_num(record.get("canopy_cover_pct"))},
            {_ch_num(record.get("ndwi"))},
            {_ch_num(record.get("cloud_cover_pct"))},
            {_ch_num(record.get("msavi"))},
            {_ch_num(record.get("satvi"))},
            {_ch_num(record.get("bsi"))},
            {_ch_num(record.get("nbr2"))},
            {_ch_num(record.get("ndti"))},
            {_ch_num(record.get("lswi"))},
            {_ch_num(record.get("brightness_index"))},
            {_ch_num(record.get("tc_brightness"))},
            {_ch_num(record.get("tc_greenness"))},
            {_ch_num(record.get("tc_wetness"))},
            {_ch_num(record.get("band_blue"))},
            {_ch_num(record.get("band_green"))},
            {_ch_num(record.get("band_red"))},
            {_ch_num(record.get("band_nir"))},
            {_ch_num(record.get("band_swir1"))},
            {_ch_num(record.get("band_swir2"))},
            '{source_system}',
            map()
        )"""

    try:
        resp = req.post(
            ch_url, data=query.encode("utf-8"),
            auth=(CH_USER, CH_PASSWORD),
            headers={"Content-Type": "text/plain"},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning("ClickHouse insert failed: %s", e)


def _ch_num(value) -> str:
    if value is None:
        return "NULL"
    return str(float(value))
