"""Data Stream File management: structured file metadata for posts."""

from __future__ import annotations

import re

from services.common.logging import get_logger

logger = get_logger("data_stream.files")

VALID_MEDIA_TYPES = {"image", "video", "document", "sensor_data", "satellite", "audio", "other"}
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024
MIME_TYPE_RE = re.compile(r"^[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+$")


def add_file_to_post(
    conn,
    post_id: str,
    file_name: str = None,
    file_description: str = None,
    file_credit: str = None,
    file_url: str = None,
    file_iri: str = None,
    directus_file_id: str = None,
    media_type: str = None,
    file_size_bytes: int = None,
    mime_type: str = None,
    latitude: float = None,
    longitude: float = None,
    sort_order: int = 0,
) -> dict:
    if media_type not in VALID_MEDIA_TYPES:
        raise ValueError(f"Invalid media_type: {media_type}")
    if file_size_bytes is not None and not 0 <= file_size_bytes <= MAX_FILE_SIZE_BYTES:
        raise ValueError(f"file_size_bytes must be between 0 and {MAX_FILE_SIZE_BYTES}")
    if mime_type is not None and not MIME_TYPE_RE.fullmatch(mime_type):
        raise ValueError("mime_type must be a valid MIME type")
    if latitude is not None and not -90 <= latitude <= 90:
        raise ValueError("latitude must be between -90 and 90")
    if longitude is not None and not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180")

    geometry_wkt = None
    if latitude is not None and longitude is not None:
        geometry_wkt = f"SRID=4326;POINT({longitude} {latitude})"

    result = conn.execute(
        conn.text(
            "INSERT INTO data_stream_file "
            "(post_id, file_iri, file_name, file_description, file_credit, "
            "file_url, directus_file_id, media_type, file_size_bytes, mime_type, "
            "latitude, longitude, geometry, sort_order) "
            "VALUES "
            "(:pid, :iri, :name, :desc, :credit, "
            " :url, :dfid, :mt, :fsb, :mime, "
            " :lat, :lon, ST_GeomFromEWKT(:geom), :so) "
            "RETURNING id"
        ),
        {
            "pid": post_id, "iri": file_iri, "name": file_name,
            "desc": file_description, "credit": file_credit,
            "url": file_url, "dfid": directus_file_id,
            "mt": media_type, "fsb": file_size_bytes, "mime": mime_type,
            "lat": latitude, "lon": longitude,
            "geom": geometry_wkt,
            "so": sort_order,
        },
    )
    record = result.mappings().first()

    conn.execute(
        conn.text("UPDATE data_stream_post SET file_count = file_count + 1 WHERE id = :pid"),
        {"pid": post_id},
    )

    logger.info("Added file %s to post %s", record["id"], post_id)
    return {"id": str(record["id"]), "file_name": file_name}


def list_post_files(conn, post_id: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT id, file_iri, file_name, file_description, file_credit, "
            "file_url, directus_file_id, media_type, file_size_bytes, mime_type, "
            "latitude, longitude, sort_order, created_at "
            "FROM data_stream_file WHERE post_id = :pid AND deleted_at IS NULL "
            "ORDER BY sort_order, created_at"
        ),
        {"pid": post_id},
    )
    return [dict(r) for r in result.mappings()]


def list_public_post_files(conn, post_id: str) -> list[dict]:
    """List only files eligible for a public data-stream post."""
    result = conn.execute(
        conn.text(
            "SELECT id, file_iri, file_name, file_description, file_credit, "
            "file_url, directus_file_id, media_type, file_size_bytes, mime_type, "
            "latitude, longitude, sort_order, created_at "
            "FROM v_data_stream_public_file WHERE post_id = :pid "
            "ORDER BY sort_order, created_at"
        ),
        {"pid": post_id},
    )
    return [dict(r) for r in result.mappings()]


def get_file(conn, file_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM data_stream_file WHERE id = :fid AND deleted_at IS NULL"),
        {"fid": file_id},
    ).mappings().first()
    return dict(result) if result else None


def update_file_metadata(
    conn,
    file_id: str,
    file_name: str = None,
    file_description: str = None,
    file_credit: str = None,
    file_iri: str = None,
    sort_order: int = None,
    updated_by: str = None,
) -> dict:
    updates = {}
    if file_name is not None:
        updates["file_name"] = file_name
    if file_description is not None:
        updates["file_description"] = file_description
    if file_credit is not None:
        updates["file_credit"] = file_credit
    if file_iri is not None:
        updates["file_iri"] = file_iri
    if sort_order is not None:
        updates["sort_order"] = sort_order
    if updated_by is not None:
        updates["updated_by"] = updated_by
    if not updates:
        raise ValueError("No fields to update")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["fid"] = file_id
    conn.execute(
        conn.text(
            f"UPDATE data_stream_file SET {set_clause}, updated_at = NOW() "
            "WHERE id = :fid AND deleted_at IS NULL"
        ),
        updates,
    )
    return {"id": file_id, "updated_fields": list(updates.keys())}


def remove_file_from_post(
    conn,
    file_id: str,
    deleted_by: str | None = None,
    deletion_reason: str | None = None,
) -> bool:
    file = get_file(conn, file_id)
    if not file:
        return False

    result = conn.execute(
        conn.text(
            "UPDATE data_stream_file SET deleted_at = NOW(), deleted_by = :actor, "
            "deletion_reason = :reason, updated_at = NOW() "
            "WHERE id = :fid AND deleted_at IS NULL"
        ),
        {"fid": file_id, "actor": deleted_by, "reason": deletion_reason},
    )
    if result.rowcount > 0:
        conn.execute(
            conn.text("UPDATE data_stream_post SET file_count = GREATEST(file_count - 1, 0) WHERE id = :pid"),
            {"pid": str(file["post_id"])},
        )
        return True
    return False
