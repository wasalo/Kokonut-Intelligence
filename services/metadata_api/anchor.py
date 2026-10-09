"""Anchored metadata: on-chain anchoring for metadata IRIs."""

from __future__ import annotations

import json

from services.common.logging import get_logger

logger = get_logger("metadata_api.anchor")


def anchor_metadata(conn, iri: str, chain: str = "celo") -> dict:
    from services.iri.resolver import resolve_iri
    row = resolve_iri(conn, iri)
    if not row:
        raise ValueError(f"IRI not found: {iri}")

    schema_result = conn.execute(
        conn.text(
            "SELECT schema_uid FROM attestation_schema "
            "WHERE name = :name AND chain = :chain AND active = TRUE LIMIT 1"
        ),
        {"name": "kokonut-data-post", "chain": chain},
    ).mappings().first()
    if not schema_result:
        raise ValueError(f"Attestation schema not found: kokonut-data-post on {chain}")

    attestation_result = conn.execute(
        conn.text(
            "INSERT INTO attestation_request "
            "(subject_type, subject_id, schema_name, event_type, chain, execution_status, metadata) "
            "VALUES ('iri_registry', :subject_id, :schema_name, 'metadata_anchor', :chain, 'pending', :metadata) "
            "RETURNING id"
        ),
        {
            "subject_id": str(row["id"]),
            "schema_name": "kokonut-data-post",
            "chain": chain,
            "metadata": json.dumps({"iri": iri, "content_hash": row["content_hash"]}),
        },
    ).mappings().first()

    conn.execute(
        conn.text("UPDATE iri_registry SET chain = :chain, attestation_uid = :uid WHERE iri = :iri"),
        {"chain": chain, "uid": str(attestation_result["id"]), "iri": iri},
    )

    return {"iri": iri, "chain": chain, "attestation_request_id": str(attestation_result["id"])}


def verify_metadata_integrity(conn, iri: str) -> dict:
    from services.iri.resolver import resolve_iri
    row = resolve_iri(conn, iri)
    if not row:
        return {"valid": False, "error": "IRI not found"}

    return {
        "iri": iri,
        "content_hash": row["content_hash"],
        "has_attestation": row.get("attestation_uid") is not None,
        "attestation_uid": row.get("attestation_uid"),
        "chain": row.get("chain"),
    }


def batch_anchor(conn, entity_type: str, location_id: str, chain: str = "celo") -> int:
    results = conn.execute(
        conn.text(
            "SELECT iri FROM iri_registry "
            "WHERE entity_type = :et AND is_current = TRUE AND attestation_uid IS NULL"
        ),
        {"et": entity_type},
    ).mappings().all()

    count = 0
    for r in results:
        try:
            anchor_metadata(conn, r["iri"], chain=chain)
            count += 1
        except Exception as e:
            logger.warning("Failed to anchor %s: %s", r["iri"], e)

    return count
