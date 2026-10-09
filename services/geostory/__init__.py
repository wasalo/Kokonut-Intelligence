"""Geostories: narrative spatial stories."""

from __future__ import annotations

import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger("geostory")


def create_geostory(conn, location_id: str, title: str, description: str = None,
                    author_id: str = None, cover_image_url: str = None,
                    metadata: dict = None) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO geostory (location_id, title, description, author_id, cover_image_url, metadata) "
            "VALUES (:lid, :title, :desc, :aid, :ciu, :meta) RETURNING id"
        ),
        {
            "lid": location_id, "title": title, "desc": description,
            "aid": author_id, "ciu": cover_image_url,
            "meta": json.dumps(metadata) if metadata else "{}",
        },
    ).mappings().first()
    return {"id": str(result["id"]), "title": title}


def get_geostory(conn, geostory_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM geostory WHERE id = :gid"),
        {"gid": geostory_id},
    ).mappings().first()
    if not result:
        return None

    story = dict(result)
    sections = conn.execute(
        conn.text("SELECT * FROM geostory_section WHERE geostory_id = :gid ORDER BY sort_order"),
        {"gid": geostory_id},
    ).mappings().all()
    story["sections"] = [dict(s) for s in sections]
    return story


def list_geostories(conn, location_id: str = None, status: str = "published") -> list[dict]:
    conditions = ["status = :s"]
    params: dict[str, Any] = {"s": status}
    if location_id:
        conditions.append("location_id = :lid")
        params["lid"] = location_id
    where = " AND ".join(conditions)
    result = conn.execute(
        conn.text(f"SELECT * FROM geostory WHERE {where} ORDER BY created_at DESC"),
        params,
    )
    return [dict(r) for r in result.mappings()]


def add_section(conn, geostory_id: str, section_type: str, title: str = None,
                content: str = None, image_url: str = None,
                map_center_lat: float = None, map_center_lon: float = None,
                map_zoom: int = 10, map_layers: list[str] = None,
                sort_order: int = 0) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO geostory_section "
            "(geostory_id, section_type, title, content, image_url, "
            "map_center_lat, map_center_lon, map_zoom, map_layers, sort_order) "
            "VALUES (:gid, :st, :title, :content, :iu, "
            ":lat, :lon, :zoom, :ml, :so) "
            "RETURNING id"
        ),
        {
            "gid": geostory_id, "st": section_type, "title": title,
            "content": content, "iu": image_url,
            "lat": map_center_lat, "lon": map_center_lon,
            "zoom": map_zoom, "ml": map_layers, "so": sort_order,
        },
    ).mappings().first()
    return {"id": str(result["id"]), "section_type": section_type}


def list_sections(conn, geostory_id: str) -> list[dict]:
    result = conn.execute(
        conn.text("SELECT * FROM geostory_section WHERE geostory_id = :gid ORDER BY sort_order"),
        {"gid": geostory_id},
    )
    return [dict(r) for r in result.mappings()]


def delete_geostory(conn, geostory_id: str) -> bool:
    result = conn.execute(
        conn.text("DELETE FROM geostory WHERE id = :gid"),
        {"gid": geostory_id},
    )
    return result.rowcount > 0
