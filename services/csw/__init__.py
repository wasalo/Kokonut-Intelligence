"""CSW OGC Catalogue Service: standardized metadata endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.common.logging import get_logger

logger = get_logger("csw")


def get_capabilities() -> dict:
    return {
        "service": "CSW",
        "version": "2.0.2",
        "title": "Kokonut Intelligence CSW Endpoint",
        "abstract": "OGC Catalogue Service for the Kokonut Intelligence platform",
        "keywords": ["ecological", "agriculture", "carbon", "biodiversity", "MRV"],
        "operations": [
            "GetCapabilities",
            "GetRecord",
            "GetRecords",
            "DescribeRecord",
        ],
        "formats": ["application/xml", "application/json"],
    }


def get_records(
    conn,
    query: str = None,
    result_type: str = "results",
    output_schema: str = "http://www.isotc211.org/2005/gmd",
    max_records: int = 10,
    start_position: int = 1,
) -> dict:
    conditions = ["dsp.status IN ('published', 'verified')", "dsp.visibility = 'public'"]
    params: dict[str, Any] = {"limit": max_records, "offset": start_position - 1}

    if query:
        conditions.append("(dsp.title ILIKE :q OR dsp.content ILIKE :q)")
        params["q"] = f"%{query}%"

    where = " AND ".join(conditions)
    result = conn.execute(
        conn.text(
            f"SELECT dsp.*, l.name AS location_name "
            f"FROM data_stream_post dsp "
            f"JOIN location l ON l.id = dsp.location_id "
            f"WHERE {where} "
            f"ORDER BY dsp.created_at DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    ).mappings().all()

    records = []
    for r in result:
        records.append({
            "identifier": str(r["id"]),
            "title": r["title"],
            "abstract": r.get("content", ""),
            "type": "dataset",
            "date": str(r["created_at"]),
            "subject": r["post_type"],
            "location": {
                "name": r.get("location_name", ""),
            },
        })

    return {
        "searchResults": {
            "numberOfRecordsMatched": len(records),
            "numberOfRecordsReturned": len(records),
            "records": records,
        },
    }


def get_record(conn, record_id: str) -> dict | None:
    result = conn.execute(
        conn.text(
            "SELECT dsp.*, l.name AS location_name "
            "FROM data_stream_post dsp "
            "JOIN location l ON l.id = dsp.location_id "
            "WHERE dsp.id = :rid AND dsp.status IN ('published', 'verified')"
        ),
        {"rid": record_id},
    ).mappings().first()

    if not result:
        return None

    return {
        "identifier": str(result["id"]),
        "title": result["title"],
        "abstract": result.get("content", ""),
        "type": "dataset",
        "date": str(result["created_at"]),
        "subject": result["post_type"],
        "location": {"name": result.get("location_name", "")},
    }


def describe_record() -> dict:
    return {
        "schema": {
            "targetNamespace": "http://www.isotc211.org/2005/gmd",
            "elementFormDefault": "qualified",
            "schemaLocation": "http://www.isotc211.org/2005/gmd http://www.isotc211.org/2005/gmd/gmd.xsd",
        },
        "typeName": "MD_Metadata",
        "childElementNames": [
            "fileIdentifier",
            "language",
            "characterSet",
            "level",
            "title",
            "abstract",
            "date",
            "spatialRepresentationInfo",
            "referenceSystemInfo",
            "identificationInfo",
            "distributionInfo",
            "dataQualityInfo",
        ],
    }
