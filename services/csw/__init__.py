"""CSW OGC Catalogue Service: standardized metadata endpoints."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger("csw")
_MAX_RECORDS = 100


def _validate_pagination(max_records: int, start_position: int) -> None:
    if isinstance(max_records, bool) or not isinstance(max_records, int):
        raise ValueError("max_records must be an integer")
    if not 1 <= max_records <= _MAX_RECORDS:
        raise ValueError(f"max_records must be between 1 and {_MAX_RECORDS}")
    if isinstance(start_position, bool) or not isinstance(start_position, int):
        raise ValueError("start_position must be an integer")
    if start_position < 1:
        raise ValueError("start_position must be at least 1")


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
    _validate_pagination(max_records, start_position)
    conditions = ["dsp.status IN ('published', 'verified')", "dsp.visibility = 'public'"]
    filter_params: dict[str, Any] = {}

    if query:
        conditions.append("(dsp.title ILIKE :q OR dsp.content ILIKE :q)")
        filter_params["q"] = f"%{query}%"

    where = " AND ".join(conditions)
    matched = conn.execute(
        conn.text(
            "SELECT COUNT(*) "
            "FROM data_stream_post dsp "
            "JOIN location l ON l.id = dsp.location_id "
            f"WHERE {where}"
        ),
        filter_params,
    ).scalar_one()

    params = {
        **filter_params,
        "limit": max_records,
        "offset": start_position - 1,
    }
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
            "numberOfRecordsMatched": matched,
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
            "WHERE dsp.id = :rid "
            "AND dsp.status IN ('published', 'verified') "
            "AND dsp.visibility = 'public'"
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
