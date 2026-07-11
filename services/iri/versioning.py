"""IRI versioning for project update tracking."""

from __future__ import annotations

import json

from services.common.logging import get_logger
from services.iri.resolver import generate_iri, resolve_iri, get_current_iri, _compute_content_hash

logger = get_logger("iri.versioning")


def create_version(conn, entity_type: str, entity_id: str, metadata: dict,
                   content_hash_type: str = "raw") -> str:
    iri = generate_iri(conn, entity_type, entity_id, content=metadata,
                       content_hash_type=content_hash_type)
    logger.info("Created new version %s for %s:%s", iri, entity_type, entity_id)
    return iri


def get_version(conn, iri: str) -> dict | None:
    from services.iri.resolver import resolve_metadata
    return resolve_metadata(conn, iri)


def diff_versions(conn, iri_a: str, iri_b: str) -> dict:
    a = resolve_iri(conn, iri_a)
    b = resolve_iri(conn, iri_b)
    if not a or not b:
        raise ValueError("One or both IRIs not found")

    meta_a = a.get("metadata_json") or {}
    meta_b = b.get("metadata_json") or {}

    all_keys = set(meta_a.keys()) | set(meta_b.keys())
    changes = {}
    for k in all_keys:
        if meta_a.get(k) != meta_b.get(k):
            changes[k] = {"old": meta_a.get(k), "new": meta_b.get(k)}

    return {
        "iri_a": iri_a,
        "iri_b": iri_b,
        "version_a": a["version"],
        "version_b": b["version"],
        "changes": changes,
        "has_changes": len(changes) > 0,
    }
