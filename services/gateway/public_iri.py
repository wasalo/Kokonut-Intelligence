"""Public, non-sensitive JSON-LD resolution for versioned location IRIs."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Callable
from uuid import UUID

_IRI_PATTERN = re.compile(
    r"^kokonut:location:"
    r"(?P<entity_id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}):v(?P<version>[1-9][0-9]{0,8})$"
)

_CONTEXT = {
    "schema": "http://schema.org/",
    "kokonut": "https://kokonut.network/ontology#",
}


def _canonical_location_iri(iri: str) -> tuple[str, str, int] | None:
    if not isinstance(iri, str) or len(iri) > 96:
        return None
    match = _IRI_PATTERN.fullmatch(iri)
    if match is None:
        return None
    entity_id = str(UUID(match.group("entity_id")))
    version = int(match.group("version"))
    return f"kokonut:location:{entity_id}:v{version}", entity_id, version


def _public_projection_hash(document: dict) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def resolve_public_location_iri(
    iri: str,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Resolve a public location IRI without reading stored private metadata.

    Resolution is deliberately limited to location IRIs backed by the same
    verified/published public farm projection as the Gateway's public location
    API. The stored IRI hash and ``metadata_json`` are not selected because the
    registry does not record whether their source content is safe to disclose.
    """
    parsed = _canonical_location_iri(iri)
    if parsed is None:
        return None
    canonical_iri, entity_id, version = parsed

    if connection_factory is None:
        from services.common.database import get_connection

        connection_factory = get_connection

    with connection_factory(connect_timeout=3, readonly=True) as connection:
        connection.execute("SET LOCAL statement_timeout = '5s'")
        connection.execute("SET LOCAL lock_timeout = '2s'")
        row = (
            connection.execute(
                """
                SELECT iri.iri, iri.version, iri.entity_id::text AS entity_id,
                       iri.public_projection,
                       previous.iri AS verified_previous_iri
                FROM iri_registry AS iri
                JOIN v_public_farm_summary AS public_location
                  ON public_location.location_id = iri.entity_id
                LEFT JOIN iri_registry AS previous
                  ON previous.iri = iri.previous_iri
                 AND previous.entity_type = iri.entity_type
                 AND previous.entity_id = iri.entity_id
                 AND previous.version = iri.version - 1
                 AND previous.public_projection IS NOT NULL
                WHERE iri.iri = :iri
                  AND iri.entity_type = 'location'
                  AND iri.entity_id = :entity_id
                  AND iri.version = :version
                  AND iri.public_projection IS NOT NULL
                  AND public_location.status = 'active'
                """,
                {"iri": canonical_iri, "entity_id": entity_id, "version": version},
            )
            .first()
        )

    if row is None:
        return None

    projection = row["public_projection"]
    if (
        not isinstance(projection, dict)
        or set(projection) != {"name", "country", "region", "status"}
        or not isinstance(projection.get("name"), str)
        or not projection["name"].strip()
        or len(projection["name"]) > 255
        or projection.get("country") is not None
        and (not isinstance(projection["country"], str) or len(projection["country"]) > 255)
        or projection.get("region") is not None
        and (not isinstance(projection["region"], str) or len(projection["region"]) > 255)
        or projection.get("status") != "active"
    ):
        return None

    document = {
        "@context": _CONTEXT,
        "@id": canonical_iri,
        "@type": "kokonut:location",
        "schema:name": projection["name"],
        "schema:addressCountry": projection["country"],
        "schema:addressRegion": projection["region"],
        "kokonut:status": projection["status"],
        "kokonut:version": int(row["version"]),
    }
    if row["verified_previous_iri"]:
        document["kokonut:previousVersion"] = {
            "@id": row["verified_previous_iri"]
        }
    document["kokonut:publicProjectionHash"] = _public_projection_hash(document)
    document["kokonut:hashAlgorithm"] = "sha256"
    return document
