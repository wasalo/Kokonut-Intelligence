"""Evidence chaining via RDF: provenance chains for impact claims."""

from __future__ import annotations

import json
from typing import Any

from services.common.logging import get_logger
from services.rdf.triple_store import add_triples, query_triples

logger = get_logger("rdf.evidence_chain")

KOKONUT_NS = "https://kokonut.network/ontology#"
SCHEMA_NS = "http://schema.org/"
CIDS_NS = "https://ontology.commonapproach.org/cids#"


def build_evidence_chain(conn, claim_id: str) -> list[dict]:
    claim = conn.execute(
        conn.text("SELECT * FROM impact_claim WHERE id = :cid"),
        {"cid": claim_id},
    ).mappings().first()
    if not claim:
        return []

    triples = []
    graph = f"evidence:{claim_id}"
    claim_iri = f"kokonut:claim:{claim_id}"

    if claim.get("evidence_cid"):
        evidence_iri = f"kokonut:evidence:{claim['evidence_cid']}"
        triples.append({"subject": claim_iri, "predicate": f"{CIDS_NS}hasEvidence", "object_iri": evidence_iri, "graph_name": graph, "source_table": "impact_claim", "source_id": claim_id})
        triples.append({"subject": evidence_iri, "predicate": f"{SCHEMA_NS}name", "object_value": f"Evidence for claim {claim_id}", "graph_name": graph})
        if claim.get("evidence_hash"):
            triples.append({"subject": evidence_iri, "predicate": f"{KOKONUT_NS}contentHash", "object_value": claim["evidence_hash"], "graph_name": graph})

    if claim.get("attestation_uid"):
        attestation_iri = f"kokonut:attestation:{claim['attestation_uid']}"
        triples.append({"subject": claim_iri, "predicate": f"{CIDS_NS}hasAttestation", "object_iri": attestation_iri, "graph_name": graph})
        triples.append({"subject": attestation_iri, "predicate": f"{KOKONUT_NS}attestationUid", "object_value": claim["attestation_uid"], "graph_name": graph})

    if claim.get("external_verifier"):
        verifier_iri = f"kokonut:verifier:{claim['external_verifier'].replace(' ', '-')}"
        triples.append({"subject": claim_iri, "predicate": f"{CIDS_NS}verifiedBy", "object_iri": verifier_iri, "graph_name": graph})
        triples.append({"subject": verifier_iri, "predicate": f"{SCHEMA_NS}name", "object_value": claim["external_verifier"], "graph_name": graph})

    location_iri = f"kokonut:location:{claim['location_id']}"
    triples.append({"subject": claim_iri, "predicate": f"{SCHEMA_NS}location", "object_iri": location_iri, "graph_name": graph, "source_table": "impact_claim", "source_id": claim_id})

    if claim.get("stakeholder_outcome_id"):
        outcome_iri = f"kokonut:outcome:{claim['stakeholder_outcome_id']}"
        triples.append({"subject": claim_iri, "predicate": f"{CIDS_NS}indicates", "object_iri": outcome_iri, "graph_name": graph})

    return triples


def verify_evidence_chain(conn, claim_id: str) -> dict:
    claim_iri = f"kokonut:claim:{claim_id}"
    graph = f"evidence:{claim_id}"
    triples = query_triples(conn, subject=claim_iri, graph_name=graph)

    has_evidence = any(t["predicate"] == f"{CIDS_NS}hasEvidence" for t in triples)
    has_attestation = any(t["predicate"] == f"{CIDS_NS}hasAttestation" for t in triples)
    has_location = any(t["predicate"] == f"{SCHEMA_NS}location" for t in triples)

    return {
        "claim_id": claim_id,
        "chain_valid": has_evidence and has_location,
        "has_evidence": has_evidence,
        "has_attestation": has_attestation,
        "has_location": has_location,
        "triple_count": len(triples),
    }


def get_evidence_provenance(conn, entity_type: str, entity_id: str) -> dict:
    base_iri = f"kokonut:{entity_type}:{entity_id}"
    all_triples = query_triples(conn, subject=base_iri)

    linked_iris = set()
    for t in all_triples:
        if t.get("object_iri"):
            linked_iris.add(t["object_iri"])

    for linked_iri in linked_iris:
        all_triples.extend(query_triples(conn, subject=linked_iri))

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "base_iri": base_iri,
        "total_triples": len(all_triples),
        "linked_entities": list(linked_iris),
    }
