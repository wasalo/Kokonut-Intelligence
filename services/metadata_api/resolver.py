"""Metadata resolution and JSON-LD serialization."""

from __future__ import annotations

import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger("metadata_api.resolver")

SCHEMA_NS = "http://schema.org/"
KOKONUT_NS = "https://kokonut.network/ontology#"
CIDS_NS = "https://ontology.commonapproach.org/cids#"


def _prefixed(term: str, ns: str = SCHEMA_NS) -> str:
    return f"{ns}{term}"


def resolve_metadata_graph(conn, iri: str) -> dict | None:
    from services.iri.resolver import resolve_iri
    row = resolve_iri(conn, iri)
    if not row:
        return None

    doc = {
        "@context": {
            "schema": SCHEMA_NS,
            "kokonut": KOKONUT_NS,
            "cids": CIDS_NS,
        },
        "@id": iri,
        "@type": f"kokonut:{row['entity_type']}",
        "kokonut:version": row["version"],
        "kokonut:contentHash": row["content_hash"],
    }
    if row.get("metadata_json"):
        doc.update(row["metadata_json"])
    if row.get("previous_iri"):
        doc["kokonut:previousVersion"] = {"@id": row["previous_iri"]}

    return doc


def resolve_entity_metadata(conn, entity_type: str, entity_id: str) -> dict | None:
    from services.iri.resolver import get_current_iri
    iri = get_current_iri(conn, entity_type, entity_id)
    if not iri:
        return None
    return resolve_metadata_graph(conn, iri)


def generate_iri_from_metadata(conn, metadata_doc: dict) -> str:
    from services.iri.resolver import generate_iri
    entity_type = metadata_doc.get("@type", "unknown").replace("kokonut:", "")
    entity_id = metadata_doc.get("@id", "unknown")
    return generate_iri(conn, entity_type, entity_id, content=metadata_doc)


def to_jsonld(entity_type: str, entity_data: dict, context: dict = None) -> dict:
    doc = {
        "@context": context or {
            "schema": SCHEMA_NS,
            "kokonut": KOKONUT_NS,
        },
        "@type": f"kokonut:{entity_type}",
    }
    for key, value in entity_data.items():
        if key in ("id", "created_at", "updated_at", "created_by", "updated_by"):
            continue
        prop = key
        doc[prop] = value
    return doc


def expand_jsonld(doc: dict) -> dict:
    expanded = {}
    for key, value in doc.items():
        if key.startswith("@"):
            expanded[key] = value
        elif ":" not in key:
            expanded[f"{SCHEMA_NS}{key}"] = value
        else:
            expanded[key] = value
    return expanded


def compact_jsonld(doc: dict, context: dict = None) -> dict:
    ctx = context or {}
    compacted = {}
    for key, value in doc.items():
        if key.startswith("@"):
            compacted[key] = value
        else:
            short = key
            for prefix, uri in ctx.items():
                if key.startswith(uri):
                    short = f"{prefix}:{key[len(uri):]}"
                    break
            compacted[short] = value
    return compacted
