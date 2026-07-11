"""Chronological stream queries for data stream posts."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger("data_stream.stream")


def get_project_stream(
    conn,
    location_id: str,
    visibility: str = "public",
    limit: int = 100,
) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT * FROM v_project_data_stream "
            "WHERE location_id = :location_id "
            "ORDER BY created_at DESC LIMIT :limit"
        ),
        {"location_id": location_id, "limit": limit},
    )
    return [dict(r) for r in result.mappings()]


def get_chronological_feed(
    conn,
    location_ids: list[str] | None = None,
    post_types: list[str] | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 200,
) -> list[dict]:
    conditions = [
        "dsp.status IN ('published', 'verified')",
        "dsp.visibility = 'public'",
        "l.status = 'active'",
        "EXISTS (SELECT 1 FROM farm_registry_record fr WHERE fr.location_id = dsp.location_id AND fr.status IN ('verified', 'published'))",
    ]
    params: dict[str, Any] = {"limit": limit}

    if location_ids:
        placeholders = ", ".join(f":loc_{i}" for i in range(len(location_ids)))
        conditions.append(f"dsp.location_id IN ({placeholders})")
        for i, lid in enumerate(location_ids):
            params[f"loc_{i}"] = lid

    if post_types:
        placeholders = ", ".join(f":pt_{i}" for i in range(len(post_types)))
        conditions.append(f"dsp.post_type IN ({placeholders})")
        for i, pt in enumerate(post_types):
            params[f"pt_{i}"] = pt

    if since:
        conditions.append("dsp.created_at >= :since")
        params["since"] = since
    if until:
        conditions.append("dsp.created_at <= :until")
        params["until"] = until

    where = " AND ".join(conditions)
    result = conn.execute(
        conn.text(
            f"SELECT dsp.*, l.name AS location_name, fr.farm_name "
            f"FROM data_stream_post dsp "
            f"JOIN location l ON l.id = dsp.location_id "
            f"LEFT JOIN farm_registry_record fr ON fr.location_id = dsp.location_id AND fr.status IN ('verified', 'published') "
            f"WHERE {where} "
            f"ORDER BY dsp.created_at DESC LIMIT :limit"
        ),
        params,
    )
    return [dict(r) for r in result.mappings()]


def get_filtered_stream(
    conn,
    location_id: str,
    post_type: str | None = None,
    since: str | None = None,
    until: str | None = None,
    visibility: str | None = None,
    limit: int = 50,
) -> list[dict]:
    conditions = ["location_id = :location_id"]
    params: dict[str, Any] = {"location_id": location_id, "limit": limit}

    if post_type:
        conditions.append("post_type = :post_type")
        params["post_type"] = post_type
    if visibility:
        conditions.append("visibility = :visibility")
        params["visibility"] = visibility
    if since:
        conditions.append("created_at >= :since")
        params["since"] = since
    if until:
        conditions.append("created_at <= :until")
        params["until"] = until

    where = " AND ".join(conditions)
    result = conn.execute(
        conn.text(
            f"SELECT * FROM data_stream_post WHERE {where} "
            "ORDER BY created_at DESC LIMIT :limit"
        ),
        params,
    )
    return [dict(r) for r in result.mappings()]
