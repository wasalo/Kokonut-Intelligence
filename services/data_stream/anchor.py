"""Blockchain anchoring for data stream posts via EAS."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from services.common.logging import get_logger

logger = get_logger("data_stream.anchor")


def anchor_post(conn, post_id: str, chain: str = "celo") -> dict:
    post = conn.execute(
        conn.text("SELECT * FROM data_stream_post WHERE id = :post_id"),
        {"post_id": post_id},
    ).mappings().first()

    if not post:
        raise ValueError(f"data_stream_post not found: {post_id}")
    if post["status"] not in ("verified", "published"):
        raise ValueError(f"Post must be verified or published to anchor, current status: {post['status']}")
    if post["is_anchored"]:
        return {"post_id": post_id, "attestation_uid": post["attestation_uid"], "already_anchored": True}

    content_payload = json.dumps({
        "location_id": str(post["location_id"]),
        "post_type": post["post_type"],
        "title": post["title"],
        "content_hash": post["content_hash"],
        "media_type": post["media_type"],
        "visibility": post["visibility"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, sort_keys=True)
    payload_hash = hashlib.sha256(content_payload.encode()).hexdigest()

    schema_result = conn.execute(
        conn.text(
            "SELECT schema_uid FROM attestation_schema "
            "WHERE name = :name AND chain = :chain AND active = TRUE LIMIT 1"
        ),
        {"name": "kokonut-data-post", "chain": chain},
    ).mappings().first()

    if not schema_result:
        raise ValueError(f"attestation_schema 'kokonut-data-post' not found for chain '{chain}'. Run schema registration first.")

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
            "metadata": json.dumps({"content_payload_hash": payload_hash, "post_title": post["title"]}),
        },
    ).mappings().first()

    logger.info("Created attestation_request %s for data_stream_post %s", attestation_result["id"], post_id)

    conn.execute(
        conn.text(
            "UPDATE data_stream_post SET is_anchored = TRUE, chain = :chain, anchored_at = NOW() WHERE id = :post_id"
        ),
        {"chain": chain, "post_id": post_id},
    )

    return {
        "post_id": post_id,
        "attestation_request_id": str(attestation_result["id"]),
        "chain": chain,
        "content_payload_hash": payload_hash,
    }


def verify_post_anchoring(conn, post_id: str) -> dict:
    result = conn.execute(
        conn.text(
            "SELECT dsp.id, dsp.is_anchored, dsp.attestation_uid, dsp.chain, dsp.anchored_at, "
            "ar.tx_hash, ar.status AS attestation_status "
            "FROM data_stream_post dsp "
            "LEFT JOIN attestation_record ar ON ar.attestation_uid = dsp.attestation_uid "
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
