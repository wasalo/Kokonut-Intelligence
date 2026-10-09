"""Explicit source adapters for the evidence-lineage projection."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from . import policy

IRI_ENTITY_TYPES = frozenset({"location", "farm_registry_record", "metric_definition", "metric_value", "impact_claim", "attestation_record", "attestation_schema"})
NODE_NAMESPACE = uuid.UUID("89d63826-da24-4c5a-a96b-f231341d4431")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _rows(cur, sql: str, params=()) -> list[dict]:
    cur.execute(sql, params)
    columns = [column[0] for column in cur.description]
    return [dict(row) if isinstance(row, dict) else dict(zip(columns, row)) for row in cur.fetchall()]


def load_sources(cur, cutoff) -> dict[str, list[dict]]:
    """Read only projection-approved fields at the transaction snapshot."""
    sources = {}
    sources["locations"] = _rows(cur, """SELECT id, name, slug, country, region, status, updated_at FROM location WHERE updated_at <= %s ORDER BY id""", (cutoff,))
    sources["registries"] = _rows(cur, """SELECT id, location_id, registry_slug, status, schema_version, record_hash, updated_at FROM farm_registry_record WHERE updated_at <= %s AND status IN ('verified','published') ORDER BY id""", (cutoff,))
    sources["definitions"] = _rows(cur, """SELECT id, metric_key, display_name, description, unit, version, active, updated_at FROM metric_definition WHERE updated_at <= %s ORDER BY id""", (cutoff,))
    sources["values"] = _rows(cur, """SELECT mv.id, mv.metric_id, mv.location_id, mv.period_start, mv.period_end, mv.value, mv.unit, mv.computation_method, mv.verified, mv.computed_at, mv.metadata, (mv.verified AND NOT EXISTS (SELECT 1 FROM metric_value newer WHERE newer.metric_id = mv.metric_id AND newer.location_id = mv.location_id AND newer.verified = TRUE AND (newer.computed_at, newer.id) > (mv.computed_at, mv.id))) AS is_public_candidate FROM metric_value mv WHERE mv.computed_at <= %s ORDER BY mv.id""", (cutoff,))
    sources["claims"] = _rows(cur, """SELECT id, location_id, metric_id, claim_type, claim_category, claim_date, period_start, period_end, claim_text, claim_value, claim_unit, evidence_cid, evidence_hash, evidence_maturity, attestation_uid, public_claim, methodology_ref, external_verifier, status, expires_at, updated_at FROM impact_claim WHERE updated_at <= %s ORDER BY id""", (cutoff,))
    # Only unique published UIDs are admitted; ambiguous on-chain identity is excluded.
    sources["attestations"] = _rows(cur, """SELECT ar.id, ar.schema_id, ar.subject_id, ar.subject_type, ar.attestation_uid, ar.evidence_hash, ar.evidence_cids, ar.status, ar.chain, ar.attested_at, ar.expiration_date, ar.expires_at, ar.revocation_date, ar.created_at, CASE WHEN ar.subject_type = 'location' THEN ar.subject_id WHEN ar.subject_type = 'impact_claim' THEN ic.location_id WHEN ar.subject_type = 'metric_value' THEN mv.location_id END AS location_id FROM attestation_record ar LEFT JOIN impact_claim ic ON ar.subject_type = 'impact_claim' AND ic.id = ar.subject_id LEFT JOIN metric_value mv ON ar.subject_type = 'metric_value' AND mv.id = ar.subject_id WHERE ar.created_at <= %s AND ar.status = 'published' AND ar.attestation_uid IS NOT NULL AND ar.attestation_uid IN (SELECT attestation_uid FROM attestation_record WHERE status = 'published' AND attestation_uid IS NOT NULL GROUP BY attestation_uid HAVING COUNT(*) = 1) ORDER BY ar.id""", (cutoff,))
    schema_ids = [row["schema_id"] for row in sources["attestations"]]
    sources["schemas"] = _rows(cur, """SELECT id, schema_uid, name, description, chain, resolver_address, version, active, created_at FROM attestation_schema WHERE id = ANY(%s::uuid[]) ORDER BY id""", (schema_ids,)) if schema_ids else []
    entity_ids = [(kind, row["id"]) for kind, key in (("location", "locations"), ("farm_registry_record", "registries"), ("metric_definition", "definitions"), ("metric_value", "values"), ("impact_claim", "claims"), ("attestation_record", "attestations"), ("attestation_schema", "schemas")) for row in sources[key]]
    sources["iris"] = lookup_iris(cur, entity_ids)
    return sources


def lookup_iris(cur, entities: list[tuple[str, Any]]) -> dict[tuple[str, str], str]:
    if not entities:
        return {}
    if any(entity_type not in IRI_ENTITY_TYPES for entity_type, _ in entities):
        raise ValueError("IRI lookup entity type is not allowlisted")
    types = [item[0] for item in entities]
    ids = [item[1] for item in entities]
    rows = _rows(cur, """SELECT r.entity_type, r.entity_id, r.iri FROM iri_registry r JOIN unnest(%s::text[], %s::uuid[]) AS wanted(entity_type, entity_id) USING (entity_type, entity_id) WHERE r.is_current = TRUE ORDER BY r.entity_type, r.entity_id, r.version DESC""", (types, ids))
    result = {}
    for row in rows:
        result.setdefault((row["entity_type"], str(row["entity_id"])), row["iri"])
    return result


def build(generation_id, sources: dict[str, list[dict]]) -> tuple[list[dict], list[dict]]:
    nodes: list[dict] = []
    edges: list[dict] = []
    node_index = {}
    node_keys = {}
    active_locations = {str(row["id"]) for row in sources["locations"] if row.get("status") == "active"}
    eligible = {str(row["location_id"]) for row in sources["registries"] if policy.registry_is_public(row) and str(row["location_id"]) in active_locations}
    iris = sources["iris"]

    def add_node(node_type, entity_type, row, key, location_id=None, audience="internal", attributes=None, source_table=None, updated=None):
        entity_id = row.get("id") if row else None
        entity_key = f"{entity_type}:{key}"
        node_id = uuid.uuid5(NODE_NAMESPACE, f"{generation_id}:{entity_key}")
        lifecycle = row.get("status") if row else None
        if lifecycle not in {"draft", "submitted", "verified", "published", "rejected"}:
            lifecycle = None
        data = {"id": node_id, "generation_id": generation_id, "node_type": node_type, "entity_type": entity_type, "entity_id": entity_id, "entity_key": entity_key, "iri": iris.get((entity_type, str(entity_id))) if entity_id else None, "location_id": location_id, "lifecycle_status": lifecycle, "audience": audience, "valid_from": None, "valid_to": None, "source_table": source_table or entity_type, "source_updated_at": updated, "attributes": attributes or {}}
        data["source_hash"] = canonical_hash({k: v for k, v in data.items() if k not in {"id", "generation_id", "source_hash"}})
        nodes.append(data); node_index[(entity_type, str(entity_id) if entity_id else str(key))] = node_id
        node_keys[node_id] = entity_key
        return node_id

    def add_edge(edge_type, source, target, source_table, source_key, location_id=None, audience="internal", source_entity_id=None, attributes=None):
        data = {"id": uuid.uuid5(NODE_NAMESPACE, f"{generation_id}:edge:{edge_type}:{source}:{target}:{source_key}"), "generation_id": generation_id, "edge_type": edge_type, "source_node_id": source, "target_node_id": target, "source_table": source_table, "source_entity_id": source_entity_id, "source_key": source_key, "location_id": location_id, "audience": audience, "valid_from": None, "valid_to": None, "attributes": attributes or {}}
        hash_input = {k: v for k, v in data.items() if k not in {"id", "generation_id", "source_hash", "source_node_id", "target_node_id"}}
        hash_input["source_entity_key"] = node_keys[source]
        hash_input["target_entity_key"] = node_keys[target]
        data["source_hash"] = canonical_hash(hash_input); edges.append(data)

    for row in sources["locations"]:
        public = str(row["id"]) in eligible
        add_node("entity", "location", row, row["id"], row["id"], "public" if public else "internal", {k: row.get(k) for k in ("name", "slug", "country", "region")}, updated=row.get("updated_at"))
    for row in sources["registries"]:
        audience = "public" if policy.registry_is_public(row) else "internal"; node = add_node("registry_record", "farm_registry_record", row, row["id"], row["location_id"], audience, {"registry_slug": row["registry_slug"], "schema_version": row.get("schema_version")}, updated=row.get("updated_at")); add_edge("registers", node, node_index[("location", str(row["location_id"]))], "farm_registry_record", str(row["id"]), row["location_id"], audience, row["id"])
    for row in sources["definitions"]:
        add_node("metric_definition", "metric_definition", row, row["id"], audience="public" if row.get("active") else "internal", attributes={k: row.get(k) for k in ("metric_key", "display_name", "description", "unit", "version", "active")}, updated=row.get("updated_at"))
    for row in sources["values"]:
        audience = "public" if policy.metric_value_is_public(row, eligible) else "internal"; node = add_node("metric_value", "metric_value", row, row["id"], row.get("location_id"), audience, {k: row.get(k) for k in ("period_start", "period_end", "value", "unit", "computation_method", "verified")}, updated=row.get("computed_at")); add_edge("measures", node, node_index[("metric_definition", str(row["metric_id"]))], "metric_value", str(row["id"]), row.get("location_id"), audience, row["id"])
        if row.get("location_id") in {r["id"] for r in sources["locations"]}: add_edge("about_location", node, node_index[("location", str(row["location_id"]))], "metric_value", str(row["id"]), row["location_id"], audience, row["id"])
    for row in sources["claims"]:
        audience = "public" if policy.impact_claim_is_public(row, eligible) else "internal"; node = add_node("impact_claim", "impact_claim", row, row["id"], row["location_id"], audience, {k: row.get(k) for k in ("claim_type", "claim_category", "claim_date", "claim_text", "claim_value", "claim_unit", "evidence_maturity")}, updated=row.get("updated_at")); add_edge("about_location", node, node_index[("location", str(row["location_id"]))], "impact_claim", str(row["id"]), row["location_id"], audience, row["id"])
        if row.get("metric_id") and ("metric_definition", str(row["metric_id"])) in node_index: add_edge("claims_metric", node, node_index[("metric_definition", str(row["metric_id"]))], "impact_claim", str(row["id"]), row["location_id"], audience, row["id"])
        for kind, value in (("cid", row.get("evidence_cid")), ("hash", row.get("evidence_hash"))):
            if value:
                evidence = add_node("evidence_reference", f"evidence_{kind}", {}, canonical_hash([kind, value]), row["location_id"], audience, {kind: value}, source_table="impact_claim", updated=row.get("updated_at")); add_edge("supported_by", node, evidence, "impact_claim", f"{row['id']}:{kind}", row["location_id"], audience, row["id"])
    for row in sources["schemas"]: add_node("attestation_schema", "attestation_schema", row, row["id"], audience="public" if row.get("chain") == "celo" and row.get("active") else "internal", attributes={k: row.get(k) for k in ("schema_uid", "name", "description", "chain", "resolver_address", "version", "active")}, updated=row.get("created_at"))
    for row in sources["attestations"]:
        audience = "public" if policy.attestation_is_public(row, eligible) else "internal"; node = add_node("attestation", "attestation_record", row, row["id"], row.get("location_id"), audience, {k: row.get(k) for k in ("attestation_uid", "chain", "attested_at", "expiration_date", "revocation_date", "evidence_hash", "evidence_cids")}, updated=row.get("created_at")); add_edge("uses_schema", node, node_index[("attestation_schema", str(row["schema_id"]))], "attestation_record", str(row["id"]), row.get("location_id"), audience, row["id"])
        target = node_index.get((row.get("subject_type"), str(row.get("subject_id"))))
        if target: add_edge("attests", node, target, "attestation_record", str(row["id"]), row.get("location_id"), audience, row["id"])
    attestations_by_uid = {row["attestation_uid"]: row for row in sources["attestations"]}
    for row in sources["claims"]:
        attestation = attestations_by_uid.get(row.get("attestation_uid"))
        if attestation:
            claim_node = node_index[("impact_claim", str(row["id"]))]
            attestation_node = node_index[("attestation_record", str(attestation["id"]))]
            audience = "public" if policy.impact_claim_is_public(row, eligible) and policy.attestation_is_public(attestation, eligible) else "internal"
            add_edge("attests", attestation_node, claim_node, "impact_claim", f"{row['id']}:attestation_uid", row["location_id"], audience, row["id"], {"join_basis": "attestation_uid"})
    return nodes, edges
