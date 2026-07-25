"""Blockchain anchoring for data stream posts via EAS."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from services.common.logging import get_logger

logger = get_logger("data_stream.anchor")


def anchor_post(conn, post_id: str, chain: str = "celo") -> dict:
    """Anchor a data stream post by creating a pending attestation request.

    The post is NOT marked is_anchored=TRUE until the signer service confirms
    onchain submission. This creates the request in the pending queue.
    """
    post = conn.execute(
        conn.text("SELECT * FROM data_stream_post WHERE id = :post_id"),
        {"post_id": post_id},
    ).mappings().first()

    if not post:
        raise ValueError(f"data_stream_post not found: {post_id}")
    if post["status"] not in ("verified", "published"):
        raise ValueError(f"Post must be verified or published to anchor, current status: {post['status']}")
    if post["is_anchored"] and post["attestation_uid"]:
        return {"post_id": post_id, "attestation_uid": post["attestation_uid"], "already_anchored": True}

    content_hash = _compute_content_hash(post)
    _store_content_hash(conn, post_id, content_hash)

    schema_result = conn.execute(
        conn.text(
            "SELECT schema_uid FROM attestation_schema "
            "WHERE name = :name AND chain = :chain AND active = TRUE LIMIT 1"
        ),
        {"name": "kokonut-data-post", "chain": chain},
    ).mappings().first()

    if not schema_result:
        raise ValueError(f"attestation_schema 'kokonut-data-post' not found for chain '{chain}'. Run schema registration first.")

    existing = conn.execute(
        conn.text(
            "SELECT id FROM attestation_request "
            "WHERE subject_type = 'data_stream_post' AND subject_id = :sid "
            "AND execution_status IN ('pending', 'confirmed') AND chain = :chain"
        ),
        {"sid": post_id, "chain": chain},
    ).mappings().first()

    if existing:
        return {"post_id": post_id, "attestation_request_id": str(existing["id"]), "already_pending": True, "chain": chain}

    attestation_result = conn.execute(
        conn.text(
            "INSERT INTO attestation_request "
            "(subject_type, subject_id, schema_name, chain, execution_status, metadata) "
            "VALUES ('data_stream_post', :subject_id, :schema_name, :chain, 'pending', :metadata) "
            "RETURNING id"
        ),
        {
            "subject_id": post_id,
            "schema_name": "kokonut-data-post",
            "chain": chain,
            "metadata": json.dumps({"content_payload_hash": content_hash, "post_title": post["title"]}),
        },
    ).mappings().first()

    logger.info("Created attestation_request %s for data_stream_post %s", attestation_result["id"], post_id)

    return {
        "post_id": post_id,
        "attestation_request_id": str(attestation_result["id"]),
        "chain": chain,
        "content_payload_hash": content_hash,
    }


def anchor_batch(conn, post_ids: list[str], chain: str = "celo") -> dict:
    """Anchor multiple posts in batch. Returns summary of results."""
    results = []
    for post_id in post_ids:
        try:
            result = anchor_post(conn, post_id, chain=chain)
            results.append({"post_id": post_id, "status": "pending", **result})
        except Exception as e:
            results.append({"post_id": post_id, "status": "error", "error": str(e)})

    pending = sum(1 for r in results if r["status"] == "pending")
    errors = sum(1 for r in results if r["status"] == "error")
    skipped = sum(1 for r in results if r.get("already_anchored") or r.get("already_pending"))

    return {
        "total": len(post_ids),
        "pending": pending,
        "errors": errors,
        "skipped": skipped,
        "results": results,
    }


def _compute_content_hash(post) -> str:
    """Compute deterministic content hash for a post."""
    content_payload = json.dumps({
        "location_id": str(post["location_id"]),
        "post_type": post["post_type"],
        "title": post["title"],
        "content_hash": post.get("content_hash", ""),
        "media_type": post.get("media_type", ""),
        "visibility": post["visibility"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, sort_keys=True)
    return hashlib.sha256(content_payload.encode()).hexdigest()


def _store_content_hash(conn, post_id: str, content_hash: str) -> None:
    """Store content hash on data_stream_post if not already set."""
    conn.execute(
        conn.text(
            "UPDATE data_stream_post SET content_hash = :ch, updated_at = NOW() "
            "WHERE id = :pid AND (content_hash IS NULL OR content_hash != :ch)"
        ),
        {"ch": content_hash, "pid": post_id},
    )


def verify_post_anchoring(conn, post_id: str) -> dict:
    result = conn.execute(
        conn.text(
            "SELECT dsp.id, dsp.is_anchored, dsp.attestation_uid, dsp.chain, dsp.anchored_at, "
            "ar.tx_hash, ar.execution_status AS attestation_status "
            "FROM data_stream_post dsp "
            "LEFT JOIN attestation_request ar ON ar.subject_id = dsp.id "
            "AND ar.subject_type = 'data_stream_post' "
            "AND ar.execution_status = 'confirmed' "
            "WHERE dsp.id = :post_id"
        ),
        {"post_id": post_id},
    ).mappings().first()

    if not result:
        raise ValueError(f"data_stream_post not found: {post_id}")

    return dict(result)


def list_anchored_posts(conn, location_id: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT id, post_type, title, attestation_uid, chain, anchored_at "
            "FROM data_stream_post "
            "WHERE location_id = :location_id AND is_anchored = TRUE "
            "ORDER BY anchored_at DESC"
        ),
        {"location_id": location_id},
    )
    return [dict(r) for r in result.mappings()]
