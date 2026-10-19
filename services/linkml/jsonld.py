"""JSON-LD context generation from LinkML schemas."""

from __future__ import annotations

from services.common.logging import get_logger

logger = get_logger("linkml.jsonld")

# Schema.org context
SCHEMA_ORG_CONTEXT = "http://schema.org/"

# Kokonut namespace
KOKONUT_NS = "https://kokonut.network/ontology#"

# Regen Framework namespace
REGEN_NS = "https://framework.regen.network/schema/"

# QUDT namespace
QUDT_NS = "http://qudt.org/schema/qudt/"

# GeoSPARQL namespace
GEO_NS = "http://www.opengis.net/ont/geosparql#"

# Default context mapping
DEFAULT_CONTEXT = {
    "schema": SCHEMA_ORG_CONTEXT,
    "kokonut": KOKONUT_NS,
    "rfs": REGEN_NS,
    "qudt": QUDT_NS,
    "geo": GEO_NS,
}


def generate_context(schema_name: str, slot_uris: dict[str, str] = None) -> dict:
    """Generate a JSON-LD @context from a LinkML schema name."""
    context = dict(DEFAULT_CONTEXT)
    if slot_uris:
        for slot_name, uri in slot_uris.items():
            context[slot_name] = uri
    return context


def to_jsonld_document(
    entity_type: str,
    entity_data: dict,
    iri: str = None,
    context: dict = None,
) -> dict:
    """Convert entity data to a JSON-LD document."""
    type_term = entity_type if ":" in entity_type else f"kokonut:{entity_type}"
    doc = {
        "@context": DEFAULT_CONTEXT if context is None else context,
        "@type": type_term,
    }
    if iri:
        doc["@id"] = iri

    for key, value in entity_data.items():
        if key in ("id", "created_at", "updated_at", "created_by", "updated_by", "metadata"):
            continue
        doc[key] = value

    return doc


def to_jsonld_with_graph(entities: list[dict], context: dict = None) -> dict:
    """Convert multiple entities to a JSON-LD @graph document."""
    graph = []
    for entity in entities:
        entity_type = entity.get("@type", "unknown")
        doc = {
            "@type": entity_type,
        }
        for key, value in entity.items():
            if key in ("@type",):
                continue
            doc[key] = value
        graph.append(doc)

    return {
        "@context": DEFAULT_CONTEXT if context is None else context,
        "@graph": graph,
    }


def expand_prefixed_term(term: str, context: dict = None) -> str:
    """Expand a prefixed term (e.g., 'schema:name') to a full URI."""
    ctx = DEFAULT_CONTEXT if context is None else context
    if ":" in term:
        prefix, local = term.split(":", 1)
        if prefix in ctx:
            return f"{ctx[prefix]}{local}"
    return term


def compact_uri(uri: str, context: dict = None) -> str:
    """Compact a full URI to a prefixed term."""
    ctx = DEFAULT_CONTEXT if context is None else context
    for prefix, ns in ctx.items():
        if uri.startswith(ns):
            return f"{prefix}:{uri[len(ns):]}"
    return uri
