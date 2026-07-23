"""Governed comment operations for data-stream posts."""

from __future__ import annotations

import json

from services.common.logging import get_logger

logger = get_logger("data_stream.comments")

VALID_STATUSES = {"draft", "submitted", "verified", "published", "rejected"}
VALID_VISIBILITY = {"public", "internal", "private"}


def create_comment(
    conn,
    post_id: str,
    content: str,
    author_id: str | None = None,
    visibility: str = "private",
    metadata: dict | None = None,
) -> dict:
    if not content or not content.strip():
        raise ValueError("content is required")
    if visibility not in VALID_VISIBILITY:
        raise ValueError(f"Invalid visibility: {visibility}")

    result = conn.execute(
        conn.text(
            "INSERT INTO data_stream_post_comment "
            "(post_id, author_id, content, status, visibility, metadata) "
            "VALUES (:post_id, :author_id, :content, 'draft', :visibility, CAST(:metadata AS jsonb)) "
            "RETURNING id, created_at"
        ),
        {
            "post_id": post_id,
            "author_id": author_id,
            "content": content,
            "visibility": visibility,
            "metadata": json.dumps(metadata or {}),
        },
    )
    row = result.mappings().first()
    return {"id": str(row["id"]), "status": "draft", "created_at": row["created_at"]}


def moderate_comment(
    conn,
    comment_id: str,
    status: str,
    actor_id: str | None = None,
    rejection_reason: str | None = None,
) -> dict:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    if status == "rejected" and not rejection_reason:
        raise ValueError("rejection_reason is required")

    result = conn.execute(
        conn.text(
            "UPDATE data_stream_post_comment SET status = :status, "
            "rejection_reason = :reason, updated_by = :actor, updated_at = NOW() "
            "WHERE id = :id RETURNING id, status, rejection_reason"
        ),
        {
            "id": comment_id,
            "status": status,
            "reason": rejection_reason,
            "actor": actor_id,
        },
    )
    row = result.mappings().first()
    if not row:
        return None
    return dict(row)


def list_public_comments(conn, post_id: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT dsc.* FROM data_stream_post_comment dsc "
            "JOIN data_stream_post dsp ON dsp.id = dsc.post_id "
            "WHERE dsc.post_id = :post_id "
            "AND dsc.status = 'published' AND dsc.visibility = 'public' "
            "AND COALESCE(dsc.metadata ->> 'privacy', '') = 'public_summary' "
            "AND data_stream_post_is_public(dsp.id) "
            "ORDER BY dsc.created_at"
        ),
        {"post_id": post_id},
    )
    return [dict(row) for row in result.mappings()]
