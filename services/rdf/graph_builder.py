"""RDF graph builder: auto-generate triples from governed records."""

from __future__ import annotations

import hashlib

from services.common.logging import get_logger
from services.rdf.triple_store import add_triples

logger = get_logger("rdf.graph_builder")

KOKONUT_NS = "https://kokonut.network/ontology#"
SCHEMA_NS = "http://schema.org/"
CIDS_NS = "https://ontology.commonapproach.org/cids#"


def delete_triples(conn, graph_name: str = None, source_table: str = None, source_id: str = None) -> int:
    """Compatibility wrapper for callers that previously cleaned a graph in place."""
    from services.rdf.triple_store import delete_triples as _delete_triples

    return _delete_triples(conn, graph_name, source_table, source_id)


def _k(prop: str) -> str:
    return f"{KOKONUT_NS}{prop}"


def _s(prop: str) -> str:
    return f"{SCHEMA_NS}{prop}"


def _c(prop: str) -> str:
    return f"{CIDS_NS}{prop}"


def build_location_graph(conn, location_id: str) -> list[dict]:
    loc = (
        conn.execute(
            conn.text("SELECT * FROM location WHERE id = :lid"),
            {"lid": location_id},
        )
        .mappings()
        .first()
    )
    if not loc:
        return []

    triples = []
    base_iri = f"kokonut:location:{location_id}"

    triples.append(
        {
            "subject": base_iri,
            "predicate": _s("name"),
            "object_value": loc["name"],
            "graph_name": f"location:{location_id}",
            "source_table": "location",
            "source_id": location_id,
            "source_column": "name",
        }
    )
    if loc.get("description"):
        triples.append(
            {
                "subject": base_iri,
                "predicate": _s("description"),
                "object_value": loc["description"],
                "graph_name": f"location:{location_id}",
                "source_table": "location",
                "source_id": location_id,
            }
        )
    if loc.get("latitude") and loc.get("longitude"):
        triples.append(
            {
                "subject": base_iri,
                "predicate": _s("latitude"),
                "object_value": str(loc["latitude"]),
                "object_type": "decimal",
                "graph_name": f"location:{location_id}",
                "source_table": "location",
                "source_id": location_id,
            }
        )
        triples.append(
            {
                "subject": base_iri,
                "predicate": _s("longitude"),
                "object_value": str(loc["longitude"]),
                "object_type": "decimal",
                "graph_name": f"location:{location_id}",
                "source_table": "location",
                "source_id": location_id,
            }
        )

    registry = (
        conn.execute(
            conn.text(
                "SELECT * FROM farm_registry_record WHERE location_id = :lid AND status IN ('verified', 'published') LIMIT 1"
            ),
            {"lid": location_id},
        )
        .mappings()
        .first()
    )
    if registry:
        if registry.get("farm_name"):
            triples.append(
                {
                    "subject": base_iri,
                    "predicate": _s("alternateName"),
                    "object_value": registry["farm_name"],
                    "graph_name": f"location:{location_id}",
                    "source_table": "farm_registry_record",
                    "source_id": str(registry["id"]),
                }
            )
        if registry.get("project_summary"):
            triples.append(
                {
                    "subject": base_iri,
                    "predicate": _s("description"),
                    "object_value": registry["project_summary"],
                    "graph_name": f"location:{location_id}",
                    "source_table": "farm_registry_record",
                    "source_id": str(registry["id"]),
                }
            )

    return triples


def build_credit_graph(conn, credit_id: str) -> list[dict]:
    credit = (
        conn.execute(
            conn.text("SELECT * FROM carbon_credit WHERE id = :cid"),
            {"cid": credit_id},
        )
        .mappings()
        .first()
    )
    if not credit:
        return []

    triples = []
    base_iri = f"kokonut:credit:{credit_id}"

    triples.append(
        {
            "subject": base_iri,
            "predicate": _c("creditCode"),
            "object_value": credit["credit_code"],
            "graph_name": f"credit:{credit_id}",
            "source_table": "carbon_credit",
            "source_id": credit_id,
        }
    )
    triples.append(
        {
            "subject": base_iri,
            "predicate": _c("vintageYear"),
            "object_value": str(credit["vintage_year"]),
            "object_type": "integer",
            "graph_name": f"credit:{credit_id}",
            "source_table": "carbon_credit",
            "source_id": credit_id,
        }
    )
    triples.append(
        {
            "subject": base_iri,
            "predicate": _c("methodology"),
            "object_value": credit["methodology"],
            "graph_name": f"credit:{credit_id}",
            "source_table": "carbon_credit",
            "source_id": credit_id,
        }
    )
    triples.append(
        {
            "subject": base_iri,
            "predicate": _c("issuableQuantity"),
            "object_value": str(credit["issuable_tonnes"]),
            "object_type": "decimal",
            "graph_name": f"credit:{credit_id}",
            "source_table": "carbon_credit",
            "source_id": credit_id,
        }
    )
    triples.append(
        {
            "subject": base_iri,
            "predicate": _c("retiredQuantity"),
            "object_value": str(credit["retired_tonnes"]),
            "object_type": "decimal",
            "graph_name": f"credit:{credit_id}",
            "source_table": "carbon_credit",
            "source_id": credit_id,
        }
    )

    location_iri = f"kokonut:location:{credit['location_id']}"
    triples.append(
        {
            "subject": base_iri,
            "predicate": _s("location"),
            "object_iri": location_iri,
            "graph_name": f"credit:{credit_id}",
            "source_table": "carbon_credit",
            "source_id": credit_id,
        }
    )

    return triples


def build_claim_graph(conn, claim_id: str) -> list[dict]:
    claim = (
        conn.execute(
            conn.text("SELECT * FROM impact_claim WHERE id = :cid"),
            {"cid": claim_id},
        )
        .mappings()
        .first()
    )
    if not claim:
        return []

    triples = []
    base_iri = f"kokonut:claim:{claim_id}"

    triples.append(
        {
            "subject": base_iri,
            "predicate": _c("claimType"),
            "object_value": claim["claim_type"],
            "graph_name": f"claim:{claim_id}",
            "source_table": "impact_claim",
            "source_id": claim_id,
        }
    )
    triples.append(
        {
            "subject": base_iri,
            "predicate": _c("claimText"),
            "object_value": claim["claim_text"],
            "graph_name": f"claim:{claim_id}",
            "source_table": "impact_claim",
            "source_id": claim_id,
        }
    )
    if claim.get("claim_value"):
        triples.append(
            {
                "subject": base_iri,
                "predicate": _c("claimValue"),
                "object_value": str(claim["claim_value"]),
                "object_type": "decimal",
                "graph_name": f"claim:{claim_id}",
                "source_table": "impact_claim",
                "source_id": claim_id,
            }
        )

    location_iri = f"kokonut:location:{claim['location_id']}"
    triples.append(
        {
            "subject": base_iri,
            "predicate": _s("location"),
            "object_iri": location_iri,
            "graph_name": f"claim:{claim_id}",
            "source_table": "impact_claim",
            "source_id": claim_id,
        }
    )

    if claim.get("evidence_cid"):
        evidence_iri = f"kokonut:evidence:{claim['evidence_cid']}"
        triples.append(
            {
                "subject": base_iri,
                "predicate": _c("hasEvidence"),
                "object_iri": evidence_iri,
                "graph_name": f"claim:{claim_id}",
                "source_table": "impact_claim",
                "source_id": claim_id,
            }
        )

    return triples


def build_full_graph(conn, location_id: str) -> list[dict]:
    all_triples = build_location_graph(conn, location_id)

    credits = (
        conn.execute(
            conn.text("SELECT id FROM carbon_credit WHERE location_id = :lid"),
            {"lid": location_id},
        )
        .mappings()
        .all()
    )
    for c in credits:
        all_triples.extend(build_credit_graph(conn, str(c["id"])))

    claims = (
        conn.execute(
            conn.text("SELECT id FROM impact_claim WHERE location_id = :lid"),
            {"lid": location_id},
        )
        .mappings()
        .all()
    )
    for cl in claims:
        all_triples.extend(build_claim_graph(conn, str(cl["id"])))

    return all_triples


def _persist_graph(conn, location_id: str, rebuild_id=None, cutoff=None, commit: bool = True) -> dict:
    graph_name = f"location:{location_id}"
    cutoff = cutoff or conn.execute(conn.text("SELECT NOW() AS cutoff")).mappings().first()["cutoff"]
    conn.execute(
        conn.text("SELECT pg_advisory_xact_lock(hashtextextended(:key, :namespace))"),
        {"key": graph_name, "namespace": 173002},
    )
    generation = (
        conn.execute(
            conn.text(
                "INSERT INTO rdf_graph_generation (graph_name, source_cutoff, status, rebuild_id) "
                "VALUES (:name, :cutoff, 'building', :rebuild_id) RETURNING id"
            ),
            {"name": graph_name, "cutoff": cutoff, "rebuild_id": rebuild_id},
        )
        .mappings()
        .first()
    )
    generation_id = generation["id"]
    try:
        triples = build_full_graph(conn, location_id)
        for triple in triples:
            triple["graph_name"] = graph_name
        count = add_triples(conn, triples, graph_name=graph_name, generation_id=generation_id)
        # The store computes the canonical hash on insert; hash the source terms
        # here as a stable generation fingerprint without rereading staged rows.
        from services.rdf.triple_store import _triple_hash

        content_hash = hashlib.sha256(
            "".join(
                sorted(
                    _triple_hash(
                        t["subject"],
                        t["predicate"],
                        t.get("object_value"),
                        t.get("object_type", "string"),
                        t.get("object_iri"),
                        graph_name,
                    )
                    for t in triples
                )
            ).encode()
        ).hexdigest()
        persisted = (
            conn.execute(
                conn.text(
                    "SELECT COUNT(*) AS count, string_agg(content_hash, '' ORDER BY content_hash) AS hashes FROM rdf_triple WHERE generation_id = :id"
                ),
                {"id": generation_id},
            )
            .mappings()
            .first()
        )
        actual = persisted["count"]
        expected_hashes = "".join(
            sorted(
                _triple_hash(
                    t["subject"],
                    t["predicate"],
                    t.get("object_value"),
                    t.get("object_type", "string"),
                    t.get("object_iri"),
                    graph_name,
                )
                for t in triples
            )
        )
        if actual != count or (persisted.get("hashes") and persisted["hashes"] != expected_hashes):
            raise ValueError("persisted RDF counts do not match generated triples")
        conn.execute(
            conn.text(
                "UPDATE rdf_graph_generation SET status = 'superseded' WHERE graph_name = :name AND status = 'active'"
            ),
            {"name": graph_name},
        )
        conn.execute(
            conn.text(
                "UPDATE rdf_graph_generation SET status = 'active', triple_count = :count, content_hash = :hash, rebuild_id = :rebuild_id, completed_at = NOW() WHERE id = :id AND status = 'building'"
            ),
            {"id": generation_id, "count": count, "hash": content_hash, "rebuild_id": rebuild_id},
        )
        conn.execute(
            conn.text(
                "INSERT INTO rdf_named_graph (name, description, triple_count, last_built_at, active_generation_id, source_cutoff, content_hash) "
                "VALUES (:n, :d, :tc, NOW(), :gid, :cutoff, :hash) "
                "ON CONFLICT (name) DO UPDATE SET triple_count = EXCLUDED.triple_count, last_built_at = NOW(), active_generation_id = EXCLUDED.active_generation_id, source_cutoff = EXCLUDED.source_cutoff, content_hash = EXCLUDED.content_hash"
            ),
            {
                "n": graph_name,
                "d": f"RDF graph for location {location_id}",
                "tc": count,
                "gid": generation_id,
                "cutoff": cutoff,
                "hash": content_hash,
            },
        )
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("RDF graph rebuild failed for %s", location_id)
        raise
    logger.info("Persisted %d triples for location %s", count, location_id)
    return {"generation_id": generation_id, "count": count, "source_cutoff": cutoff, "content_hash": content_hash}


def persist_graph(conn, location_id: str) -> int:
    return _persist_graph(conn, location_id)["count"]
