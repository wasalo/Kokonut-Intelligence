"""Core CRUD operations for data stream posts."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from services.common.logging import get_logger

logger = get_logger("data_stream.post")

VALID_POST_TYPES = {
    "field_update", "monitoring_report", "photo", "satellite_image",
    "sensor_reading", "soil_analysis", "water_analysis", "biodiversity_survey",
    "harvest_report", "weather_report", "financial_report", "community_update",
    "training_record", "intervention_record", "compliance_record",
}

VALID_VISIBILITY = {"public", "internal", "private"}
VALID_STATUSES = {"draft", "submitted", "verified", "published", "rejected"}


def _compute_content_hash(content: Optional[str]) -> Optional[str]:
    if content is None:
        return None
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def create_post(
    conn,
    location_id: str,
    post_type: str = "field_update",
    title: str = "",
    content: str | None = None,
    visibility: str = "internal",
    evidence_urls: list[str] | None = None,
    file_ids: list[str] | None = None,
    media_type: str | None = None,
    plot_id: str | None = None,
    crop_cycle_id: str | None = None,
    source_system: str | None = None,
    source_id: str | None = None,
    source_raw: dict | None = None,
    metadata: dict | None = None,
    created_by: str | None = None,
) -> dict:
    if post_type not in VALID_POST_TYPES:
        raise ValueError(f"Invalid post_type: {post_type}. Must be one of: {sorted(VALID_POST_TYPES)}")
    if visibility not in VALID_VISIBILITY:
        raise ValueError(f"Invalid visibility: {visibility}. Must be one of: {sorted(VALID_VISIBILITY)}")
    if not title:
        raise ValueError("title is required")

    row = {
        "location_id": location_id,
        "post_type": post_type,
        "title": title,
        "content": content,
        "content_hash": _compute_content_hash(content),
        "visibility": visibility,
        "status": "draft",
        "evidence_urls": evidence_urls or [],
        "file_ids": file_ids or [],
        "media_type": media_type,
        "plot_id": plot_id,
        "crop_cycle_id": crop_cycle_id,
        "source_system": source_system,
        "source_id": source_id,
        "source_raw": json.dumps(source_raw) if source_raw else None,
        "metadata": json.dumps(metadata) if metadata else "{}",
        "created_by": created_by,
        "updated_by": created_by,
    }

    result = conn.execute(
        conn.text(
            "INSERT INTO data_stream_post "
            "(location_id, post_type, title, content, content_hash, visibility, status, "
            " evidence_urls, file_ids, media_type, plot_id, crop_cycle_id, "
            " source_system, source_id, source_raw, metadata, created_by, updated_by) "
            "VALUES "
            "(:location_id, :post_type, :title, :content, :content_hash, :visibility, :status, "
            " :evidence_urls, :file_ids, :media_type, :plot_id, :crop_cycle_id, "
            " :source_system, :source_id, :source_raw, :metadata, :created_by, :updated_by) "
            "RETURNING id, created_at"
        ),
        row,
    )
    record = result.mappings().first()
    logger.info("Created data_stream_post %s for location %s", record["id"], location_id)
    return {"id": str(record["id"]), "created_at": record["created_at"]}


def update_post(conn, post_id: str, **kwargs) -> dict:
    allowed_fields = {
        "title", "content", "post_type", "visibility", "evidence_urls",
        "file_ids", "media_type", "status", "plot_id", "crop_cycle_id",
        "source_system", "source_id", "source_raw", "metadata", "updated_by",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not updates:
        raise ValueError("No valid fields to update")

    if "post_type" in updates and updates["post_type"] not in VALID_POST_TYPES:
        raise ValueError(f"Invalid post_type: {updates['post_type']}")
    if "visibility" in updates and updates["visibility"] not in VALID_VISIBILITY:
        raise ValueError(f"Invalid visibility: {updates['visibility']}")
    if "status" in updates and updates["status"] not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {updates['status']}")

    if "content" in updates:
        updates["content_hash"] = _compute_content_hash(updates["content"])

    if "source_raw" in updates and isinstance(updates["source_raw"], dict):
        updates["source_raw"] = json.dumps(updates["source_raw"])
    if "metadata" in updates and isinstance(updates["metadata"], dict):
        updates["metadata"] = json.dumps(updates["metadata"])

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["post_id"] = post_id

    conn.execute(
        conn.text(f"UPDATE data_stream_post SET {set_clause}, updated_at = NOW() WHERE id = :post_id"),
        updates,
    )
    logger.info("Updated data_stream_post %s", post_id)
    return {"id": post_id, "updated_fields": list(updates.keys())}


def get_post(conn, post_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM data_stream_post WHERE id = :post_id"),
        {"post_id": post_id},
    )
    row = result.mappings().first()
    if not row:
        return None
    return dict(row)


def list_posts_by_project(
    conn,
    location_id: str,
    status: str | None = None,
    post_type: str | None = None,
    visibility: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    conditions = ["location_id = :location_id"]
    params: dict[str, Any] = {"location_id": location_id, "limit": limit, "offset": offset}

    if status:
        conditions.append("status = :status")
        params["status"] = status
    if post_type:
        conditions.append("post_type = :post_type")
        params["post_type"] = post_type
    if visibility:
        conditions.append("visibility = :visibility")
        params["visibility"] = visibility

    where = " AND ".join(conditions)
    result = conn.execute(
        conn.text(
            f"SELECT * FROM data_stream_post WHERE {where} "
            "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    )
    return [dict(r) for r in result.mappings()]


def search_posts(
    conn,
    query_text: str,
    location_id: str | None = None,
    post_type: str | None = None,
    limit: int = 20,
) -> list[dict]:
    conditions = [
        "id IN (SELECT id FROM v_data_stream_search)",
        "content_search @@ plainto_tsquery('english', :query)",
    ]
    params: dict[str, Any] = {"query": query_text, "limit": limit}

    if location_id:
        conditions.append("location_id = :location_id")
        params["location_id"] = location_id
    if post_type:
        conditions.append("post_type = :post_type")
        params["post_type"] = post_type

    where = " AND ".join(conditions)
    result = conn.execute(
        conn.text(
            f"SELECT id, location_id, post_type, title, content, visibility, status, created_at, "
            f"ts_rank(content_search, plainto_tsquery('english', :query)) AS rank "
            f"FROM data_stream_post WHERE {where} ORDER BY rank DESC LIMIT :limit"
        ),
        params,
    )
    return [dict(r) for r in result.mappings()]


def delete_post(conn, post_id: str) -> bool:
    result = conn.execute(
        conn.text("UPDATE data_stream_post SET status = 'rejected', updated_at = NOW() WHERE id = :post_id"),
        {"post_id": post_id},
    )
    deleted = result.rowcount > 0
    if deleted:
        logger.info("Soft-deleted data_stream_post %s", post_id)
    return deleted
