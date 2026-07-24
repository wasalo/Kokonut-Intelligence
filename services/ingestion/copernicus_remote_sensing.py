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
from .base import log_ingestion, hash_payload, post_clickhouse_rows
from .clickhouse_outbox import enqueue

logger = get_logger("ingestion.copernicus_remote_sensing")

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CATALOG_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"


def _get_token() -> Optional[str]:
    """Get OAuth2 token from Copernicus Data Space.

    Supports two auth methods:
    1. Resource Owner Password Credentials (email + password) — default
    2. Client Credentials (client_id + client_secret) — for registered apps
    """
    email = os.environ.get("COPERNICUS_EMAIL")
    password = os.environ.get("COPERNICUS_PASSWORD")
    client_id = os.environ.get("COPERNICUS_CLIENT_ID")
    client_secret = os.environ.get("COPERNICUS_CLIENT_SECRET")

    # Method 1: Email/password (Resource Owner Password Credentials)
    if email and password:
        try:
            resp = requests.post(
                TOKEN_URL,
                data={
                    "grant_type": "password",
                    "username": email,
                    "password": password,
                    "client_id": "cdse-public",
                },
                timeout=30,
            )
            resp.raise_for_status()
            token = resp.json().get("access_token")
            if token:
                return token
        except Exception:
            logger.warning("Copernicus password authentication failed")

    # Method 2: Client Credentials
    if client_id and client_secret:
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
        except Exception:
            logger.error("Copernicus client-credential authentication failed")

    logger.error("No Copernicus credentials configured. Set COPERNICUS_EMAIL/PASSWORD or COPERNICUS_CLIENT_ID/SECRET")
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
        return {"status": "error", "message": "Copernicus token unavailable", "observations": 0, "retryable": False}

    bbox = _resolve_bbox(job)
    if not bbox:
        return {"status": "error", "message": "No bbox available", "observations": 0, "retryable": False}

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
        status_code = getattr(getattr(e, "response", None), "status_code", None)
        retryable = isinstance(e, (requests.Timeout, requests.ConnectionError)) or status_code in (429, 500, 502, 503, 504)
        return {"status": "error", "message": str(e), "observations": 0, "retryable": retryable}

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
            "source_id": product_id,
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
        if not record.get("_duplicate"):
            _insert_ch(record, conn)

        log_ingestion(
            source_system="copernicus_api",
            source_table="sentinel2_product",
            source_id=product_id,
            target_table="remote_sensing_observation",
            target_id=pg_id,
            operation="insert",
            payload_hash=hash_payload(record),
            status="success",
            rows_affected=0 if record.get("_duplicate") else 1,
        )
        observations += 1

    return {"status": "success", "observations": observations, "products_found": len(products)}


def _resolve_bbox(job: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Resolve bbox from job dict."""
    if job.get("_resolved_bbox"):
        return job["_resolved_bbox"]
    return None


def _insert_pg(conn, record: dict) -> str:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO remote_sensing_observation
            (plot_id, location_id, observation_date, source,
             cloud_cover_pct, source_system, source_id, metadata)
         VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
         ON CONFLICT (source_system, source_id) WHERE source_id IS NOT NULL DO NOTHING
         RETURNING id
        """,
        (
            record.get("plot_id"), record.get("location_id"),
            record["observation_date"], record.get("source", "sentinel-2"),
            record.get("cloud_cover_pct"),
            record.get("source_system", "copernicus_api"),
            record.get("source_id"),
            record.get("metadata", "{}"),
        ),
    )
    row = cur.fetchone()
    if row:
        record_id = str(row[0])
    else:
        record["_duplicate"] = True
        cur.execute(
            "SELECT id FROM remote_sensing_observation WHERE source_system = %s AND source_id = %s",
            (record.get("source_system", "copernicus_api"), record["source_id"]),
        )
        record_id = str(cur.fetchone()[0])
    cur.close()
    return record_id


def _insert_ch(record: dict, conn=None) -> None:
    """Queue canonical observation; direct writes are demo-only when conn is absent."""
    source_system = record.get("source_system", "copernicus_api")
    columns = ["timestamp", "observation_id", "location_id", "plot_id", "source",
               "cloud_cover_pct", "source_system", "metadata"]
    rows = [[f"{record['observation_date']} 00:00:00.000", record.get("id", ""),
             record.get("location_id", ""), record.get("plot_id") or "",
             record.get("source", "sentinel-2"), record.get("cloud_cover_pct"),
             source_system, {}]]
    try:
        if conn is not None:
            payload_hash = hash_payload(record)
            enqueue(conn, event_key=f"remote_sensing:remote_sensing_events:{record.get('id')}",
                    source_table="remote_sensing_observation", source_id=str(record.get("id")),
                    target_table="remote_sensing_events", columns=columns, rows=rows,
                    payload_hash=payload_hash)
            return
        # No PostgreSQL transaction means this is an explicit demo/maintenance path.
        post_clickhouse_rows(
            "remote_sensing_events",
            columns, rows,
        )
    except Exception as e:
        logger.warning("ClickHouse insert failed: %s", e)


def _ch_num(value) -> str:
    if value is None:
        return "NULL"
    return str(float(value))
