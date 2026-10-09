"""General harvesting framework: pull data from external sources."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
from typing import Any
from urllib.parse import urlparse

from services.common.logging import get_logger

logger = get_logger("ingestion.harvest_manager")


def _validate_external_url(source_url: str) -> None:
    """Reject non-HTTPS and network-local URLs before fetching source data."""
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("source_url must be an HTTPS URL without embedded credentials")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost", "localhost.localdomain"}:
        raise ValueError("source_url cannot target localhost")

    try:
        addresses = {
            ipaddress.ip_address(info[4][0])
            for info in socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        }
    except (OSError, ValueError) as exc:
        raise ValueError("source_url hostname could not be resolved safely") from exc

    if any(address.is_private or address.is_loopback or address.is_link_local or address.is_reserved for address in addresses):
        raise ValueError("source_url cannot target a private or local network")


def harvest_from_url(conn, location_id: str, source_url: str,
                     source_format: str = "json",
                     source_system: str = "manual") -> dict:
    log_id = _create_log(conn, location_id, source_url, source_format, source_system)

    try:
        _validate_external_url(source_url)
        from services.common.http import http
        response = http.get(source_url, timeout=30, allow_redirects=False)
        if 300 <= response.status_code < 400:
            raise ValueError("source_url redirects are not allowed")
        response.raise_for_status()

        if source_format == "json":
            data = response.json()
            records_count = len(data) if isinstance(data, list) else 1
        elif source_format == "csv":
            import csv
            import io
            reader = csv.DictReader(io.StringIO(response.text))
            records_count = sum(1 for _ in reader)
        else:
            records_count = 1

        _complete_log(conn, log_id, records_count)
        return {"status": "success", "records_ingested": records_count, "log_id": log_id}
    except Exception as e:
        _fail_log(conn, log_id, str(e))
        return {"status": "error", "message": str(e), "log_id": log_id}


def harvest_from_file(conn, location_id: str, filepath: str,
                      source_format: str = None,
                      source_system: str = "manual") -> dict:
    if not os.path.exists(filepath):
        return {"status": "error", "message": f"File not found: {filepath}"}

    if source_format is None:
        ext = filepath.rsplit(".", 1)[-1].lower()
        format_map = {"json": "json", "csv": "csv", "geojson": "geojson", "kml": "kml"}
        source_format = format_map.get(ext, "json")

    log_id = _create_log(conn, location_id, filepath, source_format, source_system)

    try:
        with open(filepath, "r") as f:
            if source_format in ("json", "geojson"):
                data = json.load(f)
                records_count = len(data.get("features", [])) if isinstance(data, dict) else len(data) if isinstance(data, list) else 1
            elif source_format == "csv":
                import csv
                reader = csv.DictReader(f)
                records_count = sum(1 for _ in reader)
            else:
                records_count = 1

        _complete_log(conn, log_id, records_count)
        return {"status": "success", "records_ingested": records_count, "log_id": log_id}
    except Exception as e:
        _fail_log(conn, log_id, str(e))
        return {"status": "error", "message": str(e), "log_id": log_id}


def list_harvest_logs(conn, location_id: str = None, status: str = None) -> list[dict]:
    conditions = []
    params: dict[str, Any] = {}
    if location_id:
        conditions.append("location_id = :lid")
        params["lid"] = location_id
    if status:
        conditions.append("status = :s")
        params["s"] = status
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    result = conn.execute(
        conn.text(f"SELECT * FROM harvest_ingestion_log {where} ORDER BY started_at DESC"),
        params,
    )
    return [dict(r) for r in result.mappings()]


def _create_log(conn, location_id: str, source_url: str, source_format: str,
                source_system: str) -> str:
    result = conn.execute(
        conn.text(
            "INSERT INTO harvest_ingestion_log "
            "(location_id, source_url, source_format, source_system) "
            "VALUES (:lid, :url, :fmt, :sys) RETURNING id"
        ),
        {"lid": location_id, "url": source_url, "fmt": source_format, "sys": source_system},
    ).mappings().first()
    return str(result["id"])


def _complete_log(conn, log_id: str, records_count: int):
    conn.execute(
        conn.text(
            "UPDATE harvest_ingestion_log SET status = 'success', records_ingested = :count, completed_at = NOW() WHERE id = :lid"
        ),
        {"count": records_count, "lid": log_id},
    )


def _fail_log(conn, log_id: str, error_message: str):
    conn.execute(
        conn.text(
            "UPDATE harvest_ingestion_log SET status = 'failed', error_message = :msg, completed_at = NOW() WHERE id = :lid"
        ),
        {"msg": error_message, "lid": log_id},
    )
