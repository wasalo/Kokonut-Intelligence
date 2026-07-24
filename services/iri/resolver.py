"""IRI generation, resolution, and management."""

from __future__ import annotations

import hashlib
import json

from services.common.logging import get_logger

logger = get_logger("iri.resolver")

KOKONUT_IRI_BASE = "kokonut"


def _compute_content_hash(data: dict, hash_type: str = "raw", algorithm: str = "sha256") -> str:
    if not isinstance(data, dict):
        raise ValueError("IRI content must be an object")
    if hash_type not in {"raw", "graph"}:
        raise ValueError("unsupported content hash type")
    if algorithm not in {"sha256", "blake2b256"}:
        raise ValueError("unsupported hash algorithm")
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    encoded = canonical.encode("utf-8")
    if algorithm == "blake2b256":
        return hashlib.blake2b(encoded, digest_size=32).hexdigest()
    return hashlib.sha256(encoded).hexdigest()


def generate_iri(
    conn,
    entity_type: str,
    entity_id: str,
    content: dict = None,
    content_hash_type: str = "raw",
    algorithm: str = "sha256",
    rebuild_id=None,
    source_cutoff=None,
) -> str:
    if not entity_type or not entity_id:
        raise ValueError("entity_type and entity_id are required")
    if content_hash_type not in {"raw", "graph"}:
        raise ValueError("unsupported content hash type")
    if algorithm not in {"sha256", "blake2b256"}:
        raise ValueError("unsupported hash algorithm")
    if (rebuild_id is None) != (source_cutoff is None):
        raise ValueError("rebuild_id and source_cutoff must be provided together")
    conn.execute(
        conn.text("SELECT pg_advisory_xact_lock(hashtextextended(:key, :namespace))"),
        {"key": f"iri:{entity_type}:{entity_id}", "namespace": 173003},
    )
    existing = (
        conn.execute(
            conn.text(
                "SELECT MAX(version) as max_version FROM iri_registry WHERE entity_type = :et AND entity_id = :eid"
            ),
            {"et": entity_type, "eid": entity_id},
        )
        .mappings()
        .first()
    )

    version = (existing["max_version"] or 0) + 1 if existing else 1
    iri = f"{KOKONUT_IRI_BASE}:{entity_type}:{entity_id}:v{version}"
    content_hash = _compute_content_hash(content, content_hash_type, algorithm) if content else None

    previous_iri = None
    if version > 1:
        prev = (
            conn.execute(
                conn.text("SELECT iri FROM iri_registry WHERE entity_type = :et AND entity_id = :eid AND version = :v"),
                {"et": entity_type, "eid": entity_id, "v": version - 1},
            )
            .mappings()
            .first()
        )
        if prev:
            previous_iri = prev["iri"]
    conn.execute(
        conn.text(
            "UPDATE iri_registry SET is_current = FALSE WHERE entity_type = :et AND entity_id = :eid AND is_current = TRUE"
        ),
        {"et": entity_type, "eid": entity_id},
    )

    conn.execute(
        conn.text(
            "INSERT INTO iri_registry (iri, entity_type, entity_id, content_hash, content_hash_type, version, "
            "previous_iri, is_current, metadata_json, rebuild_id, source_cutoff) "
            "VALUES (:iri, :et, :eid, :ch, :cht, :v, :pi, TRUE, :mj, :rebuild_id, :source_cutoff) "
            "ON CONFLICT (iri) DO UPDATE SET "
            "content_hash = EXCLUDED.content_hash, content_hash_type = EXCLUDED.content_hash_type, "
            "metadata_json = EXCLUDED.metadata_json, rebuild_id = EXCLUDED.rebuild_id, "
            "source_cutoff = EXCLUDED.source_cutoff, updated_at = NOW()"
        ),
        {
            "iri": iri,
            "et": entity_type,
            "eid": entity_id,
            "ch": content_hash,
            "cht": content_hash_type,
            "v": version,
            "pi": previous_iri,
            "mj": json.dumps(content) if content else None,
            "rebuild_id": rebuild_id,
            "source_cutoff": source_cutoff,
        },
    )
    logger.info("Generated IRI %s for %s:%s (hash_type=%s)", iri, entity_type, entity_id, content_hash_type)
    return iri


def resolve_iri(conn, iri: str) -> dict | None:
    result = (
        conn.execute(
            conn.text("SELECT * FROM iri_registry WHERE iri = :iri"),
            {"iri": iri},
        )
        .mappings()
        .first()
    )
    return dict(result) if result else None


def resolve_metadata(conn, iri: str) -> dict | None:
    row = resolve_iri(conn, iri)
    if not row:
        return None
    return {
        "iri": row["iri"],
        "entity_type": row["entity_type"],
        "entity_id": str(row["entity_id"]),
        "version": row["version"],
        "content_hash": row["content_hash"],
        "metadata_json": row["metadata_json"],
        "previous_iri": row["previous_iri"],
    }


def get_current_iri(conn, entity_type: str, entity_id: str) -> str | None:
    result = (
        conn.execute(
            conn.text(
                "SELECT iri FROM iri_registry WHERE entity_type = :et AND entity_id = :eid AND is_current = TRUE"
            ),
            {"et": entity_type, "eid": entity_id},
        )
        .mappings()
        .first()
    )
    return result["iri"] if result else None


def get_version_history(conn, entity_type: str, entity_id: str) -> list[dict]:
    results = conn.execute(
        conn.text(
            "SELECT iri, version, content_hash, previous_iri, is_current, created_at "
            "FROM iri_registry "
            "WHERE entity_type = :et AND entity_id = :eid "
            "ORDER BY version ASC"
        ),
        {"et": entity_type, "eid": entity_id},
    ).mappings()
    return [dict(r) for r in results]


def anchor_iri(conn, iri: str, chain: str = "celo") -> dict:
    row = resolve_iri(conn, iri)
    if not row:
        raise ValueError(f"IRI not found: {iri}")

    schema_result = (
        conn.execute(
            conn.text(
                "SELECT schema_uid FROM attestation_schema "
                "WHERE name = :name AND chain = :chain AND active = TRUE LIMIT 1"
            ),
            {"name": "kokonut-data-post", "chain": chain},
        )
        .mappings()
        .first()
    )
    if not schema_result:
        raise ValueError(f"Attestation schema not found: kokonut-data-post on {chain}")

    attestation_result = (
        conn.execute(
            conn.text(
                "INSERT INTO attestation_request "
                "(subject_type, subject_id, schema_name, chain, execution_status, metadata) "
                "VALUES ('iri_registry', :subject_id, :schema_name, :chain, 'pending', :metadata) "
                "RETURNING id"
            ),
            {
                "subject_id": str(row["id"]),
                "schema_name": "kokonut-data-post",
                "chain": chain,
                "metadata": json.dumps({"iri": iri, "content_hash": row["content_hash"]}),
            },
        )
        .mappings()
        .first()
    )

    conn.execute(
        conn.text("UPDATE iri_registry SET chain = :chain, attestation_uid = :uid WHERE iri = :iri"),
        {"chain": chain, "uid": str(attestation_result["id"]), "iri": iri},
    )

    return {"iri": iri, "chain": chain, "attestation_request_id": str(attestation_result["id"])}
