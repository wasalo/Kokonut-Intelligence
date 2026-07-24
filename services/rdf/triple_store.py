"""RDF triple store: CRUD and query operations."""

from __future__ import annotations

import hashlib
from typing import Any

from services.common.logging import get_logger

logger = get_logger("rdf.triple_store")


def _triple_hash(
    subject: str, predicate: str, object_value: str, object_type: str, object_iri: str, graph_name: str
) -> str:
    content = f"{subject}|{predicate}|{object_value or ''}|{object_type}|{object_iri or ''}|{graph_name}"
    return hashlib.sha256(content.encode()).hexdigest()


def add_triple(
    conn,
    subject: str,
    predicate: str,
    object_value: str = None,
    object_type: str = "string",
    object_iri: str = None,
    graph_name: str = "default",
    source_table: str = None,
    source_id: str = None,
    source_column: str = None,
    generation_id: str = None,
) -> bool:
    if not subject or not predicate or not graph_name:
        raise ValueError("subject, predicate, and graph_name are required")
    if (object_value is None) == (object_iri is None):
        raise ValueError("Exactly one of object_value or object_iri must be provided")
    content_hash = _triple_hash(subject, predicate, object_value, object_type, object_iri, graph_name)

    result = conn.execute(
        conn.text(
            "INSERT INTO rdf_triple "
            "(subject, predicate, object_value, object_type, object_iri, graph_name, "
            "source_table, source_id, source_column, content_hash, generation_id) "
            "VALUES "
            "(:s, :p, :ov, :ot, :oi, :gn, :st, :sid, :sc, :ch, :gid) "
            "ON CONFLICT DO NOTHING"
        ),
        {
            "s": subject,
            "p": predicate,
            "ov": object_value,
            "ot": object_type,
            "oi": object_iri,
            "gn": graph_name,
            "st": source_table,
            "sid": source_id,
            "sc": source_column,
            "ch": content_hash,
            "gid": generation_id,
        },
    )
    return result.rowcount == 1


def add_triples(conn, triples: list[dict], graph_name: str = "default", generation_id: str = None) -> int:
    count = 0
    for t in triples:
        inserted = add_triple(
            conn,
            subject=t["subject"],
            predicate=t["predicate"],
            object_value=t.get("object_value"),
            object_type=t.get("object_type", "string"),
            object_iri=t.get("object_iri"),
            graph_name=t.get("graph_name", graph_name),
            source_table=t.get("source_table"),
            source_id=t.get("source_id"),
            source_column=t.get("source_column"),
            generation_id=t.get("generation_id", generation_id),
        )
        count += int(inserted)
    return count


def query_triples(
    conn,
    subject: str = None,
    predicate: str = None,
    object_iri: str = None,
    graph_name: str = None,
    limit: int = 1000,
) -> list[dict]:
    conditions = []
    params: dict[str, Any] = {"limit": limit}
    if subject:
        conditions.append("subject = :s")
        params["s"] = subject
    if predicate:
        conditions.append("predicate = :p")
        params["p"] = predicate
    if object_iri:
        conditions.append("object_iri = :oi")
        params["oi"] = object_iri
    if graph_name:
        conditions.append("graph_name = :gn")
        params["gn"] = graph_name
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    active = ""
    if graph_name:
        active = " AND (t.generation_id IS NULL OR t.generation_id = (SELECT active_generation_id FROM rdf_named_graph WHERE name = :gn))"
    else:
        active = " AND (t.generation_id IS NULL OR EXISTS (SELECT 1 FROM rdf_named_graph g WHERE g.name = t.graph_name AND g.active_generation_id = t.generation_id))"
    result = conn.execute(
        conn.text(
            f"SELECT t.* FROM rdf_triple t {where.replace('graph_name', 't.graph_name').replace('subject', 't.subject').replace('predicate', 't.predicate').replace('object_iri', 't.object_iri')} {active} LIMIT :limit"
        ),
        params,
    )
    return [dict(r) for r in result.mappings()]


def count_triples(conn, graph_name: str = None) -> int:
    if graph_name:
        result = (
            conn.execute(
                conn.text(
                    "SELECT COUNT(*) as cnt FROM rdf_triple t WHERE t.graph_name = :gn AND (t.generation_id IS NULL OR t.generation_id = (SELECT active_generation_id FROM rdf_named_graph WHERE name = :gn))"
                ),
                {"gn": graph_name},
            )
            .mappings()
            .first()
        )
    else:
        result = (
            conn.execute(
                conn.text(
                    "SELECT COUNT(*) as cnt FROM rdf_triple t WHERE t.generation_id IS NULL OR EXISTS (SELECT 1 FROM rdf_named_graph g WHERE g.name = t.graph_name AND g.active_generation_id = t.generation_id)"
                ),
            )
            .mappings()
            .first()
        )
    return result["cnt"]


def delete_triples(conn, graph_name: str = None, source_table: str = None, source_id: str = None) -> int:
    conditions = []
    params: dict[str, Any] = {}
    if graph_name:
        conditions.append("graph_name = :gn")
        params["gn"] = graph_name
    if source_table:
        conditions.append("source_table = :st")
        params["st"] = source_table
    if source_id:
        conditions.append("source_id = :sid")
        params["sid"] = source_id
    if not conditions:
        return 0
    where = " AND ".join(conditions)
    result = conn.execute(
        conn.text(f"DELETE FROM rdf_triple WHERE {where}"),
        params,
    )
    return result.rowcount
