"""Signer service: processes pending attestation requests and submits onchain."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from services.common.logging import get_logger

logger = get_logger("attestation.signer_service")


def process_pending_requests(
    conn,
    chain: str = "celo",
    limit: int = 10,
    private_key: str | None = None,
) -> dict:
    """Process pending attestation requests for a chain.

    Queries attestation_request WHERE execution_status='pending',
    submits each onchain via EASClient, and updates DB on success/failure.

    Returns:
        {"processed": int, "confirmed": int, "failed": int, "results": list[dict]}
    """
    from services.attestation.eas_client import EASClient
    from services.attestation.schemas import KOKONUT_SCHEMAS, SCHEMA_DB_NAMES

    pending = conn.execute(
        conn.text(
            "SELECT id, subject_type, subject_id, schema_name, chain, metadata "
            "FROM attestation_request "
            "WHERE execution_status = 'pending' AND chain = :chain "
            "ORDER BY created_at ASC "
            "LIMIT :limit"
        ),
        {"chain": chain, "limit": limit},
    ).mappings().all()

    if not pending:
        logger.info("No pending attestation requests for chain %s", chain)
        return {"processed": 0, "confirmed": 0, "failed": 0, "results": []}

    client = EASClient(chain, private_key)
    if not client.is_connected():
        logger.warning("Cannot connect to chain %s, skipping processing", chain)
        return {"processed": 0, "confirmed": 0, "failed": 0, "results": []}

    confirmed = 0
    failed = 0
    results = []

    for request in pending:
        request_id = str(request["id"])
        try:
            result = _submit_attestation(conn, client, request, chain)
            confirmed += 1
            results.append({"request_id": request_id, "status": "confirmed", **result})
        except Exception as e:
            failed += 1
            _handle_failure(conn, request_id, str(e))
            results.append({"request_id": request_id, "status": "failed", "error": str(e)})
            logger.error("Failed to submit attestation request %s: %s", request_id, e)

    logger.info(
        "Processed %d requests for chain %s: %d confirmed, %d failed",
        len(pending), chain, confirmed, failed,
    )
    return {
        "processed": len(pending),
        "confirmed": confirmed,
        "failed": failed,
        "results": results,
    }


def _submit_attestation(conn, client, request, chain: str) -> dict:
    """Submit a single attestation request onchain and update DB."""
    from services.attestation.publisher import _resolve_schema_uid
    from services.attestation.schemas import prepare_data_post_attestation_data

    request_id = str(request["id"])
    subject_id = str(request["subject_id"])
    schema_name = request["schema_name"]
    metadata = json.loads(request["metadata"]) if request["metadata"] else {}

    schema_uid = _resolve_schema_uid(schema_name, chain)

    post = conn.execute(
        conn.text("SELECT * FROM data_stream_post WHERE id = :sid"),
        {"sid": subject_id},
    ).mappings().first()

    if not post:
        raise ValueError(f"data_stream_post not found: {subject_id}")

    data = prepare_data_post_attestation_data(
        location_id=str(post["location_id"]),
        post_type=post["post_type"],
        title=post["title"],
        content_hash=post.get("content_hash", ""),
        media_type=post.get("media_type") or "",
        timestamp=int(post["anchored_at"].timestamp()) if post.get("anchored_at") else 0,
        visibility=post.get("visibility", "internal"),
        evidence_hash=metadata.get("content_payload_hash", ""),
        payload_cid="",
    )

    result = client.attest(
        schema_uid=schema_uid,
        recipient=KOKONUT_RECIPIENT,
        data=data,
        revocable=True,
    )

    conn.execute(
        conn.text(
            "UPDATE attestation_request "
            "SET execution_status = 'confirmed', "
            "    attestation_uid = :uid, "
            "    tx_hash = :txh, "
            "    block_number = :bn, "
            "    updated_at = NOW() "
            "WHERE id = :rid"
        ),
        {
            "uid": result["attestation_uid"],
            "txh": result["tx_hash"],
            "bn": result["block_number"],
            "rid": request_id,
        },
    )

    conn.execute(
        conn.text(
            "UPDATE data_stream_post "
            "SET attestation_uid = :uid, chain = :chain, updated_at = NOW() "
            "WHERE id = :sid AND attestation_uid IS NULL"
        ),
        {"uid": result["attestation_uid"], "chain": chain, "sid": subject_id},
    )

    logger.info(
        "Confirmed attestation for request %s: uid=%s tx=%s block=%d",
        request_id, result["attestation_uid"], result["tx_hash"], result["block_number"],
    )
    return result


def _handle_failure(conn, request_id: str, error_message: str) -> None:
    """Update attestation_request on failure."""
    conn.execute(
        conn.text(
            "UPDATE attestation_request "
            "SET execution_status = 'failed', "
            "    signing_attempts = signing_attempts + 1, "
            "    last_signing_at = NOW(), "
            "    error_message = :err, "
            "    updated_at = NOW() "
            "WHERE id = :rid"
        ),
        {"err": error_message, "rid": request_id},
    )


KOKONUT_RECIPIENT = "0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5"
