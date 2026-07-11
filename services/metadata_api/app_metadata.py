"""Application-level metadata: additional off-chain project info."""

from __future__ import annotations

import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger("metadata_api.app_metadata")


def get_app_metadata(conn, location_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM app_project_metadata WHERE location_id = :lid"),
        {"lid": location_id},
    ).mappings().first()
    return dict(result) if result else None


def upsert_app_metadata(conn, location_id: str, **kwargs) -> dict:
    allowed = {
        "tagline", "description_short", "description_long",
        "cover_image_url", "gallery_image_urls", "video_urls",
        "website_url", "twitter_url", "instagram_url", "facebook_url",
        "linkedin_url", "github_url",
        "partner_name", "partner_logo_url", "partner_website",
        "categories", "tags", "highlights", "language",
        "last_updated_by", "metadata",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if "metadata" in updates and isinstance(updates["metadata"], dict):
        updates["metadata"] = json.dumps(updates["metadata"])

    existing = get_app_metadata(conn, location_id)
    if existing:
        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        updates["lid"] = location_id
        conn.execute(
            conn.text(f"UPDATE app_project_metadata SET {set_clause}, updated_at = NOW() WHERE location_id = :lid"),
            updates,
        )
    else:
        updates["location_id"] = location_id
        cols = ", ".join(updates.keys())
        placeholders = ", ".join(f":{k}" for k in updates.keys())
        conn.execute(
            conn.text(f"INSERT INTO app_project_metadata ({cols}) VALUES ({placeholders})"),
            updates,
        )
    return {"location_id": location_id, "upserted_fields": list(updates.keys())}


def get_complete_project_view(conn, location_id: str) -> dict:
    from services.metadata_api.project_info import get_project_info
    return get_project_info(conn, location_id)
