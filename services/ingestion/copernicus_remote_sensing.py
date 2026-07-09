"""Copernicus Data Space remote sensing adapter.

Fetches Sentinel-2 L2A data via Copernicus Data Space Ecosystem API.
Falls back when GEE is unavailable.

Requires:
    - COPERNICUS_CLIENT_ID and COPERNICUS_CLIENT_SECRET env vars
    - Account at dataspace.copernicus.eu

Usage (from remote_sensing_fetcher):
    from .copernicus_remote_sensing import fetch_copernicus
    result = fetch_copernicus(conn, job)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

from ..common.logging import get_logger
from .base import log_ingestion, hash_payload

logger = get_logger("ingestion.copernicus_remote_sensing")

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CATALOG_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"


def _get_token() -> Optional[str]:
    """Get OAuth2 token from Copernicus Data Space."""
    client_id = os.environ.get("COPERNICUS_CLIENT_ID")
    client_secret = os.environ.get("COPERNICUS_CLIENT_SECRET")
    if not client_id or not client_secret:
        logger.warning("COPERNICUS_CLIENT_ID/SECRET not set")
        return None

    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        logger.error("Copernicus token request failed: %s", e)
        return None


def fetch_copernicus(conn, job: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch Sentinel-2 data via Copernicus Data Space.

    Uses the OData catalog API to search for available products.
    Downloads are not implemented (would require large data transfer);
    instead, we catalog available scenes and store metadata.

    Args:
        conn: PostgreSQL connection.
        job: Remote sensing job record.

    Returns:
        Dict with status, observations count, and details.
    """
    token = _get_token()
    if not token:
        return {"status": "error", "message": "Copernicus token unavailable", "observations": 0}

    bbox = _resolve_bbox(job)
    if not bbox:
        return {"status": "error", "message": "No bbox available", "observations": 0}

    location_id = str(job["location_id"])
    cloud_max = float(job.get("cloud_max_pct", 20))

    # Date range
    from datetime import timedelta
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=job.get("cadence_days", 7) * 2)

    # Search for Sentinel-2 L2A products
    bbox_str = f"{bbox['west']} {bbox['south']} {bbox['east']} {bbox['north']}"
    params = {
        "$filter": (
            f"Collection/Name eq 'SENTINEL-2' "
            f"and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and att/OData.CSC.StringAttribute/Value eq 'S2MSI2A') "
            f"and OData.CSC.Intersects(area=geography'SRID=4326;POINT({(bbox['west']+bbox['east'])/2} {(bbox['south']+bbox['north'])/2})') "
            f"and ContentDate/Start gt {start_date.strftime('%Y-%m-%dT00:00:00.000Z')} "
            f"and Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value lt {cloud_max})"
        ),
        "$top": 5,
        "$orderby": "ContentDate/Start desc",
    }

    try:
        resp = requests.get(CATALOG_URL, params=params, timeout=30)
        resp.raise_for_status()
        products = resp.json().get("value", [])
    except Exception as e:
        logger.error("Copernicus catalog query failed: %s", e)
        return {"status": "error", "message": str(e), "observations": 0}

    if not products:
        logger.info("No Copernicus products for location %s", location_id[:8])
        return {"status": "success", "observations": 0, "message": "No products found"}

    # Store product metadata as observations
    now = datetime.now(timezone.utc)
    observations = 0

    for product in products:
        product_id = product.get("Id", "")
        product_name = product.get("Name", "")
        cloud_cover = None
        for attr in product.get("Attributes", []):
            if attr.get("Name") == "cloudCover":
                cloud_cover = attr.get("Value")

        record = {
            "plot_id": job.get("plot_id"),
            "location_id": location_id,
            "observation_date": now.strftime("%Y-%m-%d"),
            "source": "sentinel-2",
            "source_system": "copernicus_api",
            "cloud_cover_pct": float(cloud_cover) if cloud_cover else None,
            "metadata": json.dumps({
                "product_id": product_id,
                "product_name": product_name,
                "cloud_cover": cloud_cover,
                "bbox": bbox,
                "source": "copernicus_dataspace",
            }),
        }

        pg_id = _insert_pg(conn, record)
        record["id"] = pg_id
        _insert_ch(record)

        log_ingestion(
            source_system="copernicus_api",
            source_table="sentinel2_product",
            source_id=product_id,
            target_table="remote_sensing_observation",
            target_id=pg_id,
            operation="insert",
            payload_hash=hash_payload(record),
            status="success",
            rows_affected=1,
        )
        observations += 1

    return {"status": "success", "observations": observations, "products_found": len(products)}


def _resolve_bbox(job: Dict[str, Any]) -> Optional[Dict[str, float]]:
    return job.get("_resolved_bbox")


def _insert_pg(conn, record: dict) -> str:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO remote_sensing_observation
            (plot_id, location_id, observation_date, source,
             cloud_cover_pct, source_system, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        RETURNING id
        """,
        (
            record.get("plot_id"), record.get("location_id"),
            record["observation_date"], record.get("source", "sentinel-2"),
            record.get("cloud_cover_pct"),
            record.get("source_system", "copernicus_api"),
            record.get("metadata", "{}"),
        ),
    )
    record_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return record_id


def _insert_ch(record: dict) -> None:
    import requests as req
    from .config import CH_HOST, CH_PORT, CH_USER, CH_PASSWORD

    ch_url = f"http://{CH_HOST}:{CH_PORT}"
    ts = f"{record['observation_date']} 00:00:00.000"
    source_system = record.get("source_system", "copernicus_api")

    query = f"""INSERT INTO remote_sensing_events
        (timestamp, observation_id, location_id, plot_id, source,
         cloud_cover_pct, source_system, metadata)
        VALUES (
            '{ts}',
            '{record.get("id", "")}',
            '{record.get("location_id", "")}',
            '{record.get("plot_id") or ""}',
            '{record.get("source", "sentinel-2")}',
            {_ch_num(record.get("cloud_cover_pct"))},
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
