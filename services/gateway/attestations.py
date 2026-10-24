"""Tenant-scoped, privacy-preserving reads of stored location attestations."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def list_location_attestations(
    operator_id: str,
    location_id: str,
    limit: int = 50,
    *,
    connection_factory: Callable | None = None,
) -> list[dict]:
    """List stored Celo attestation metadata for one location subject.

    Claim payloads, evidence hashes/CIDs/URLs, and reviewer notes are not
    selected. Results describe stored database state and do not prove current
    on-chain validity.
    """
    try:
        operator_id = str(UUID(operator_id))
        location_id = str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator or location identifier") from exc
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="attestation",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT record.id, record.attestation_uid,
                       schema.schema_uid, schema.name AS schema_name,
                       record.claim_type, record.status,
                       COALESCE(record.chain, schema.chain) AS chain,
                       record.tx_hash, record.attested_at,
                       record.expiration_date, record.revocation_date,
                       record.schema_version, record.created_at
                  FROM attestation_record AS record
                  JOIN attestation_schema AS schema ON schema.id = record.schema_id
                 WHERE record.subject_type = 'location'
                   AND record.subject_id = %s::uuid
                   AND COALESCE(record.chain, schema.chain) = 'celo'
                 ORDER BY record.created_at DESC, record.id DESC
                 LIMIT %s
                """,
                (location_id, limit),
            )
            columns = [description.name for description in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

        return [
            {
                **row,
                "id": str(row["id"]),
                "attested_at": row["attested_at"].isoformat()
                if row["attested_at"]
                else None,
                "expiration_date": row["expiration_date"].isoformat()
                if row["expiration_date"]
                else None,
                "revocation_date": row["revocation_date"].isoformat()
                if row["revocation_date"]
                else None,
                "created_at": row["created_at"].isoformat()
                if row["created_at"]
                else None,
            }
            for row in rows
        ]
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
