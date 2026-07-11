"""Content Hash: structured content hash with type, algorithm, media type."""

from __future__ import annotations

import hashlib
from typing import Any

from services.common.logging import get_logger

logger = get_logger("data.content_hash")

SUPPORTED_ALGORITHMS = {"sha256", "blake2b256", "sha512"}
SUPPORTED_RAW_MEDIA_TYPES = {
    "json", "csv", "xml", "pdf", "png", "jpg", "jpeg", "tiff", "geotiff",
    "geojson", "txt", "html", "parquet", "arrow", "hdf5", "other",
}
SUPPORTED_CANONICALIZATION = {"urdna2015", "urdna2012"}
SUPPORTED_MERKLE_TREES = {"none", "ipld_dag", "hashlinked"}


def compute_hash(data: bytes, algorithm: str = "sha256") -> str:
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(f"Unsupported algorithm: {algorithm}. Must be one of: {sorted(SUPPORTED_ALGORITHMS)}")
    if algorithm == "sha256":
        return hashlib.sha256(data).hexdigest()
    elif algorithm == "blake2b256":
        return hashlib.blake2b(data, digest_size=32).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(data).hexdigest()
    return ""


def compute_content_hash(data: Any, algorithm: str = "sha256", content_type: str = "raw",
                         media_type: str = None) -> dict:
    import json
    if isinstance(data, (dict, list)):
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    elif isinstance(data, str):
        canonical = data.encode("utf-8")
    elif isinstance(data, bytes):
        canonical = data
    else:
        canonical = str(data).encode("utf-8")

    hash_value = compute_hash(canonical, algorithm)
    return {
        "hash_value": hash_value,
        "hash_algorithm": algorithm,
        "content_type": content_type,
        "media_type": media_type,
    }


def create_content_hash(
    conn,
    iri_id: str,
    hash_value: str,
    hash_algorithm: str = "sha256",
    content_type: str = "raw",
    media_type: str = None,
    canonicalization_algorithm: str = None,
    merkle_tree: str = "none",
) -> dict:
    if hash_algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(f"Unsupported algorithm: {hash_algorithm}")
    if content_type not in ("raw", "graph"):
        raise ValueError(f"Invalid content_type: {content_type}")
    if content_type == "graph" and not canonicalization_algorithm:
        canonicalization_algorithm = "urdna2015"
    if canonicalization_algorithm and canonicalization_algorithm not in SUPPORTED_CANONICALIZATION:
        raise ValueError(f"Unsupported canonicalization: {canonicalization_algorithm}")

    result = conn.execute(
        conn.text(
            "INSERT INTO content_hash_entry "
            "(iri_id, hash_value, hash_algorithm, content_type, media_type, "
            "canonicalization_algorithm, merkle_tree) "
            "VALUES (:iri, :hv, :ha, :ct, :mt, :ca, :mt2) "
            "RETURNING id"
        ),
        {
            "iri": iri_id, "hv": hash_value, "ha": hash_algorithm,
            "ct": content_type, "mt": media_type,
            "ca": canonicalization_algorithm, "mt2": merkle_tree,
        },
    ).mappings().first()
    logger.info("Created content hash %s for IRI %s", result["id"], iri_id)
    return {"id": str(result["id"]), "hash_value": hash_value}


def get_content_hashes_for_iri(conn, iri_id: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT * FROM content_hash_entry WHERE iri_id = :iri ORDER BY created_at"
        ),
        {"iri": iri_id},
    )
    return [dict(r) for r in result.mappings()]


def find_iri_by_content_hash(conn, hash_value: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT che.*, iri.iri, iri.entity_type, iri.entity_id "
            "FROM content_hash_entry che "
            "JOIN iri_registry iri ON iri.id = che.iri_id "
            "WHERE che.hash_value = :hv ORDER BY che.created_at DESC"
        ),
        {"hv": hash_value},
    )
    return [dict(r) for r in result.mappings()]


def find_iri_by_content_hash_raw(conn, hash_value: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT iri FROM iri_registry WHERE content_hash = :hv ORDER BY created_at DESC"
        ),
        {"hv": hash_value},
    )
    return [dict(r) for r in result.mappings()]


def delete_content_hash(conn, hash_id: str) -> bool:
    result = conn.execute(
        conn.text("DELETE FROM content_hash_entry WHERE id = :id"),
        {"id": hash_id},
    )
    return result.rowcount > 0
