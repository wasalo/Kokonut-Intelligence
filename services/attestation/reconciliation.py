"""Reconciliation: compares DB attestation state with onchain state."""

from __future__ import annotations

from services.common.logging import get_logger

logger = get_logger("attestation.reconciliation")


def reconcile_data_stream_anchors(conn, chain: str = "celo") -> dict:
    """Reconcile data_stream_post anchoring state with onchain attestations.

    1. Backfill missing attestation_uid from confirmed attestation_request rows.
    2. Detect orphaned posts (anchored but no confirmed request).
    3. Verify onchain attestation existence for confirmed UIDs.

    Returns:
        {"backfilled": int, "orphaned": int, "verified": int, "discrepancies": list[dict]}
    """
    backfilled = _backfill_missing_uids(conn, chain)
    orphaned = _detect_orphans(conn, chain)
    verified, discrepancies = _verify_onchain(conn, chain)

    logger.info(
        "Reconciliation for chain %s: backfilled=%d orphaned=%d verified=%d discrepancies=%d",
        chain, backfilled, orphaned, verified, len(discrepancies),
    )

    return {
        "chain": chain,
        "backfilled": backfilled,
        "orphaned": orphaned,
        "verified": verified,
        "discrepancies": discrepancies,
    }


def _backfill_missing_uids(conn, chain: str) -> int:
    """Backfill data_stream_post.attestation_uid from confirmed attestation_request rows."""
    result = conn.execute(
        conn.text(
            "UPDATE data_stream_post "
            "SET attestation_uid = ar.attestation_uid, chain = :chain, updated_at = NOW() "
            "FROM attestation_request ar "
            "WHERE ar.subject_id = data_stream_post.id "
            "  AND ar.subject_type = 'data_stream_post' "
            "  AND ar.execution_status = 'confirmed' "
            "  AND ar.attestation_uid IS NOT NULL "
            "  AND data_stream_post.attestation_uid IS NULL "
            "  AND ar.chain = :chain"
        ),
        {"chain": chain},
    )
    return result.rowcount


def _detect_orphans(conn, chain: str) -> int:
    """Detect posts marked is_anchored=TRUE but with no confirmed attestation."""
    orphans = conn.execute(
        conn.text(
            "SELECT dsp.id, dsp.title, dsp.anchored_at "
            "FROM data_stream_post dsp "
            "WHERE dsp.is_anchored = TRUE "
            "  AND dsp.attestation_uid IS NULL "
            "  AND NOT EXISTS ("
            "    SELECT 1 FROM attestation_request ar "
            "    WHERE ar.subject_id = dsp.id "
            "      AND ar.subject_type = 'data_stream_post' "
            "      AND ar.execution_status = 'confirmed' "
            "  )"
        ),
    ).mappings().all()

    for orphan in orphans:
        logger.warning(
            "Orphaned anchored post: id=%s title='%s' anchored_at=%s",
            orphan["id"], orphan["title"], orphan["anchored_at"],
        )

    return len(orphans)


def _verify_onchain(conn, chain: str) -> tuple[int, list[dict]]:
    """Verify that confirmed attestation UIDs exist onchain.

    Returns:
        (verified_count, discrepancies)
    """
    from services.attestation.config import get_chain_config

    try:
        get_chain_config(chain)
    except ValueError:
        logger.warning("Chain %s not configured, skipping onchain verification", chain)
        return 0, []

    confirmed = conn.execute(
        conn.text(
            "SELECT ar.id AS request_id, ar.attestation_uid, ar.tx_hash, "
            "       ar.subject_id, dsp.title "
            "FROM attestation_request ar "
            "LEFT JOIN data_stream_post dsp ON dsp.id = ar.subject_id "
            "WHERE ar.execution_status = 'confirmed' "
            "  AND ar.attestation_uid IS NOT NULL "
            "  AND ar.chain = :chain "
            "ORDER BY ar.created_at DESC "
            "LIMIT 100"
        ),
        {"chain": chain},
    ).mappings().all()

    verified = 0
    discrepancies = []

    try:
        from services.attestation.eas_client import EASClient
        client = EASClient(chain)
        if not client.is_connected():
            logger.warning("Cannot connect to chain %s for verification", chain)
            return 0, []

        for row in confirmed:
            uid = row["attestation_uid"]
            try:
                attestation = client.get_attestation(uid)
                is_valid = client.is_valid_attestation(uid)
                if not is_valid:
                    discrepancies.append({
                        "request_id": str(row["request_id"]),
                        "attestation_uid": uid,
                        "title": row["title"],
                        "issue": "attestation_invalid",
                        "detail": "Attestation exists but is not valid",
                    })
                else:
                    verified += 1
            except Exception as e:
                discrepancies.append({
                    "request_id": str(row["request_id"]),
                    "attestation_uid": uid,
                    "title": row["title"],
                    "issue": "attestation_not_found",
                    "detail": str(e),
                })
    except ImportError:
        logger.warning("web3 not available, skipping onchain verification")

    return verified, discrepancies


def get_anchoring_status(conn, chain: str = None) -> dict:
    """Get summary of anchoring pipeline status."""
    conditions = ["1=1"]
    params: dict = {}
    if chain:
        conditions.append("chain = :chain")
        params["chain"] = chain

    where = "WHERE " + " AND ".join(conditions)

    counts = conn.execute(
        conn.text(
            f"SELECT "
            f"  COUNT(*) FILTER (WHERE execution_status = 'pending') AS pending, "
            f"  COUNT(*) FILTER (WHERE execution_status = 'confirmed') AS confirmed, "
            f"  COUNT(*) FILTER (WHERE execution_status = 'failed') AS failed "
            f"FROM attestation_request "
            f"{where}"
        ),
        params,
    ).mappings().first()

    post_counts = conn.execute(
        conn.text(
            "SELECT "
            "  COUNT(*) FILTER (WHERE is_anchored = TRUE AND attestation_uid IS NOT NULL) AS fully_anchored, "
            "  COUNT(*) FILTER (WHERE is_anchored = TRUE AND attestation_uid IS NULL) AS pending_uid, "
            "  COUNT(*) FILTER (WHERE is_anchored = FALSE) AS not_anchored "
            "FROM data_stream_post"
        ),
    ).mappings().first()

    return {
        "attestation_requests": dict(counts) if counts else {"pending": 0, "confirmed": 0, "failed": 0},
        "data_stream_posts": dict(post_counts) if post_counts else {"fully_anchored": 0, "pending_uid": 0, "not_anchored": 0},
    }
