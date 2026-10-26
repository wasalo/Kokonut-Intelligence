"""Governed, idempotent KI ↔ Kokonut Protocol execution bridge.

This module stores approved request snapshots and destination reconciliation
as KI records. It never signs or broadcasts transactions and never mutates
farm, finance, metric, or evidence source records.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

SUPPORTED_EVM_TESTNETS = frozenset({"84532", "10200"})
_HEX32 = re.compile(r"^0x[0-9a-fA-F]{64}$")
_EVM_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
_DECIMAL = re.compile(r"^(0|[1-9][0-9]*)$")
_POSITIVE_DECIMAL = re.compile(r"^[1-9][0-9]*$")
_REQUEST_FIELDS = frozenset({
    "protocol_version", "request_id", "project_id", "chain_namespace", "chain_id",
    "operation", "target", "value_base_units", "gas_limit", "calldata_hash",
    "signing_payload_hash", "signer_key_version", "expected_effect_hash", "nonce",
    "gas_policy", "expires_at", "policy_version", "idempotency_key",
})


class BridgeValidationError(ValueError):
    """A bridge payload does not satisfy the approved Protocol contract."""


class BridgeConflictError(RuntimeError):
    """An idempotency key or immutable snapshot was reused inconsistently."""


def _uuid(value: Any, field: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise BridgeValidationError(f"{field} must be a UUID") from exc


def _sha256_json(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "0x" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def canonical_request_hash(request: Mapping[str, Any]) -> str:
    """Hash an immutable request snapshot using canonical UTF-8 JSON."""
    if not isinstance(request, Mapping):
        raise BridgeValidationError("request must be a JSON object")
    return _sha256_json(request)


def validate_execution_request(
    request: Mapping[str, Any], *, protocol_project_id: str,
) -> dict[str, Any]:
    """Validate the EVM testnet subset of Protocol v1 and its project crosswalk."""
    if not isinstance(request, Mapping):
        raise BridgeValidationError("request must be a JSON object")
    if set(request) != _REQUEST_FIELDS:
        missing = sorted(_REQUEST_FIELDS - set(request))
        extra = sorted(set(request) - _REQUEST_FIELDS)
        raise BridgeValidationError(f"request field mismatch (missing={missing}, extra={extra})")
    normalized = dict(request)
    if normalized["protocol_version"] != "1":
        raise BridgeValidationError("unsupported Protocol request version")
    if _uuid(normalized["project_id"], "project_id") != _uuid(protocol_project_id, "crosswalk project_id"):
        raise BridgeValidationError("request project_id does not match the approved KI crosswalk")
    _uuid(normalized["request_id"], "request_id")
    chain_id = normalized["chain_id"]
    if (
        normalized["chain_namespace"] != "eip155"
        or not isinstance(chain_id, str)
        or not _POSITIVE_DECIMAL.fullmatch(chain_id)
        or chain_id not in SUPPORTED_EVM_TESTNETS
    ):
        raise BridgeValidationError("only the configured EVM testnets are supported")
    if not isinstance(normalized["operation"], str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", normalized["operation"]):
        raise BridgeValidationError("operation must be a lowercase protocol identifier")
    if not isinstance(normalized["target"], str) or not _EVM_ADDRESS.fullmatch(normalized["target"]):
        raise BridgeValidationError("target must be a 20-byte EVM address")
    for field in ("value_base_units", "nonce"):
        if not isinstance(normalized[field], str) or not _DECIMAL.fullmatch(normalized[field]):
            raise BridgeValidationError(f"{field} must be a canonical decimal string")
    if not isinstance(normalized["gas_limit"], str) or not _POSITIVE_DECIMAL.fullmatch(normalized["gas_limit"]):
        raise BridgeValidationError("gas_limit must be a positive decimal string")
    for field in ("calldata_hash", "signing_payload_hash", "expected_effect_hash"):
        if not isinstance(normalized[field], str) or not _HEX32.fullmatch(normalized[field]):
            raise BridgeValidationError(f"{field} must be a 32-byte hex value")
    key_version = normalized["signer_key_version"]
    if isinstance(key_version, bool) or not isinstance(key_version, int) or not 0 <= key_version <= 0xFFFFFFFF:
        raise BridgeValidationError("signer_key_version must be a u32, including zero")
    gas_policy = normalized["gas_policy"]
    if not isinstance(gas_policy, Mapping) or set(gas_policy) != {"max_fee", "max_priority_fee"}:
        raise BridgeValidationError("gas_policy must contain exactly max_fee and max_priority_fee")
    for field in ("max_fee", "max_priority_fee"):
        if not isinstance(gas_policy[field], str) or not _DECIMAL.fullmatch(gas_policy[field]):
            raise BridgeValidationError(f"gas_policy.{field} must be a canonical decimal string")
    if int(gas_policy["max_priority_fee"]) > int(gas_policy["max_fee"]):
        raise BridgeValidationError("priority fee cannot exceed max fee")
    expires_at = normalized["expires_at"]
    if not isinstance(expires_at, str):
        raise BridgeValidationError("expires_at must be an RFC3339 timestamp")
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BridgeValidationError("expires_at must be an RFC3339 timestamp") from exc
    if expiry.tzinfo is None or expiry.utcoffset() is None:
        raise BridgeValidationError("expires_at must include a timezone")
    if expiry <= datetime.now(timezone.utc):
        raise BridgeValidationError("execution request expiry must be in the future")
    if not isinstance(normalized["policy_version"], str) or not normalized["policy_version"] or len(normalized["policy_version"]) > 128:
        raise BridgeValidationError("policy_version is required and limited to 128 characters")
    if not isinstance(normalized["idempotency_key"], str) or not normalized["idempotency_key"] or len(normalized["idempotency_key"]) > 256:
        raise BridgeValidationError("idempotency_key is required and limited to 256 characters")
    return normalized


def build_dispatch_envelope(
    intent_id: str,
    request: Mapping[str, Any],
    request_hash: str,
    *,
    approval_threshold: int,
    approved_by_party_ids: Sequence[str],
) -> dict[str, Any]:
    """Build the stable outbound envelope only after a distinct-human quorum."""
    stable_intent_id = _uuid(intent_id, "intent_id")
    expected_hash = canonical_request_hash(request)
    if not isinstance(request_hash, str) or request_hash.lower() != expected_hash:
        raise BridgeConflictError("stored request hash does not match its immutable request snapshot")
    if isinstance(approval_threshold, bool) or not isinstance(approval_threshold, int) or approval_threshold < 1:
        raise BridgeValidationError("approval threshold must be a positive integer")
    voters = [_uuid(value, "approver_party_id") for value in approved_by_party_ids]
    distinct_voters = sorted(set(voters))
    if len(distinct_voters) < approval_threshold:
        raise BridgeValidationError("human approval quorum has not been met")
    return {
        "bridge_version": "1",
        "intent_id": stable_intent_id,
        "request_id": str(request["request_id"]),
        "request_hash": expected_hash,
        "approval_threshold": approval_threshold,
        "approval_count": len(distinct_voters),
        "approved_by_party_ids": distinct_voters,
        "request": dict(request),
    }


def validate_reconciliation(
    approved_request: Mapping[str, Any], result: Mapping[str, Any],
) -> dict[str, Any]:
    """Accept only matching, consensus-finalized, effect-verified EVM evidence."""
    if not isinstance(result, Mapping):
        raise BridgeValidationError("reconciliation result must be a JSON object")
    expected = {
        "request_id", "chain_namespace", "chain_id", "transaction_hash",
        "receipt_block_number", "receipt_block_hash", "finality_status",
        "observed_effect_hash", "effect_verified", "evidence",
    }
    if set(result) != expected:
        raise BridgeValidationError("reconciliation fields do not match the bridge contract")
    if str(result["request_id"]) != str(approved_request.get("request_id")):
        raise BridgeConflictError("reconciliation request_id does not match the approved intent")
    if result["chain_namespace"] != approved_request.get("chain_namespace") or str(result["chain_id"]) != str(approved_request.get("chain_id")):
        raise BridgeConflictError("reconciliation destination does not match the approved intent")
    if result["finality_status"] != "finalized":
        raise BridgeValidationError("only consensus-finalized destination evidence can be reconciled")
    if result["effect_verified"] is not True:
        raise BridgeValidationError("destination effect must be verified before reconciliation")
    expected_effect = approved_request.get("expected_effect_hash")
    observed_effect = result["observed_effect_hash"]
    if not isinstance(expected_effect, str) or not isinstance(observed_effect, str) or observed_effect.lower() != expected_effect.lower():
        raise BridgeConflictError("observed destination effect does not match the approved effect commitment")
    for field in ("transaction_hash", "receipt_block_hash"):
        if not isinstance(result[field], str) or not _HEX32.fullmatch(result[field]):
            raise BridgeValidationError(f"{field} must be a 32-byte hex value")
    if not isinstance(result["receipt_block_number"], str) or not _DECIMAL.fullmatch(result["receipt_block_number"]):
        raise BridgeValidationError("receipt_block_number must be a canonical decimal string")
    if not isinstance(result["evidence"], Mapping):
        raise BridgeValidationError("evidence must be a JSON object")
    return {**dict(result), "review_status": "submitted"}


def _one(conn, sql: str, params: Mapping[str, Any] | None = None):
    return conn.execute(conn.text(sql), dict(params or {})).mappings().first()


def create_project_mapping(conn, protocol_project_id: str, location_id: str, mapped_by_party_id: str):
    project_id = _uuid(protocol_project_id, "protocol_project_id")
    location = _uuid(location_id, "location_id")
    mapper = _uuid(mapped_by_party_id, "mapped_by_party_id")
    actor = _one(conn, "SELECT id FROM party WHERE id = :actor AND party_type = 'person'", {"actor": mapper})
    if not actor:
        raise BridgeValidationError("project mapping must be created by an identified human party")
    return _one(conn, """
        INSERT INTO protocol_project_location
            (protocol_project_id, location_id, mapped_by_party_id, status)
        VALUES (:project_id, :location_id, :mapper, 'draft')
        RETURNING id, protocol_project_id, location_id, status
    """, {"project_id": project_id, "location_id": location, "mapper": mapper})


def activate_project_mapping(conn, mapping_id: str, approved_by_party_id: str):
    mapping = _one(conn, "SELECT id, mapped_by_party_id, status FROM protocol_project_location WHERE id = :id FOR UPDATE", {"id": _uuid(mapping_id, "mapping_id")})
    if not mapping or mapping["status"] != "draft":
        raise BridgeValidationError("only a draft project mapping can be activated")
    approver = _uuid(approved_by_party_id, "approved_by_party_id")
    if str(mapping["mapped_by_party_id"]) == approver:
        raise BridgeValidationError("project mapping requires a separate human approver")
    if not _one(conn, "SELECT id FROM party WHERE id = :actor AND party_type = 'person'", {"actor": approver}):
        raise BridgeValidationError("project mapping approver must be an identified human party")
    result = _one(conn, """
        UPDATE protocol_project_location
        SET status = 'active', approved_by_party_id = :approver, approved_at = NOW()
        WHERE id = :id AND status = 'draft'
        RETURNING id, protocol_project_id, location_id, status
    """, {"id": str(mapping["id"]), "approver": approver})
    if not result:
        raise BridgeConflictError("project mapping changed before activation")
    return result


def revoke_project_mapping(conn, mapping_id: str, revoked_by_party_id: str):
    mapping = _one(conn, "SELECT id, status FROM protocol_project_location WHERE id = :id FOR UPDATE", {"id": _uuid(mapping_id, "mapping_id")})
    if not mapping or mapping["status"] != "active":
        raise BridgeConflictError("only an active project mapping can be revoked")
    revoker = _uuid(revoked_by_party_id, "revoked_by_party_id")
    if not _one(conn, "SELECT id FROM party WHERE id = :actor AND party_type = 'person'", {"actor": revoker}):
        raise BridgeValidationError("project mapping revocation requires an identified human party")
    result = _one(conn, """
        UPDATE protocol_project_location
        SET status = 'revoked', revoked_by_party_id = :revoker, revoked_at = NOW()
        WHERE id = :id AND status = 'active'
        RETURNING id, protocol_project_id, location_id, status, revoked_by_party_id, revoked_at
    """, {"id": str(mapping["id"]), "revoker": revoker})
    if not result:
        raise BridgeConflictError("project mapping changed before revocation")
    return result


def create_execution_intent(
    conn, mapping_id: str, request: Mapping[str, Any], requested_by_party_id: str,
    approval_threshold: int,
):
    mapping = _one(conn, "SELECT id, protocol_project_id, status FROM protocol_project_location WHERE id = :id", {"id": _uuid(mapping_id, "mapping_id")})
    if not mapping or mapping["status"] != "active":
        raise BridgeValidationError("execution intent requires an active approved project crosswalk")
    normalized = validate_execution_request(request, protocol_project_id=str(mapping["protocol_project_id"]))
    requester = _uuid(requested_by_party_id, "requested_by_party_id")
    if not _one(conn, "SELECT id FROM party WHERE id = :actor AND party_type = 'person'", {"actor": requester}):
        raise BridgeValidationError("execution intent must be requested by an identified human party")
    if isinstance(approval_threshold, bool) or not isinstance(approval_threshold, int) or approval_threshold < 1:
        raise BridgeValidationError("approval threshold must be a positive integer")
    return _one(conn, """
        INSERT INTO protocol_execution_intent
            (id, request_id, mapping_id, request_payload, request_hash, approval_threshold,
             requested_by_party_id, status)
        VALUES (:id, :request_id, :mapping_id, CAST(:payload AS jsonb), :request_hash,
                :approval_threshold, :requester, 'draft')
        RETURNING id, request_hash, status
    """, {
        "id": str(uuid.uuid4()), "request_id": normalized["request_id"],
        "mapping_id": str(mapping["id"]),
        "payload": json.dumps(normalized, sort_keys=True, separators=(",", ":")),
        "request_hash": canonical_request_hash(normalized),
        "approval_threshold": approval_threshold, "requester": requester,
    })


def submit_execution_intent(conn, intent_id: str):
    result = _one(conn, """
        UPDATE protocol_execution_intent
        SET status = 'submitted', submitted_at = NOW()
        WHERE id = :id AND status = 'draft'
        RETURNING id, status, submitted_at
    """, {"id": _uuid(intent_id, "intent_id")})
    if not result:
        raise BridgeConflictError("only a draft execution intent can be submitted")
    return result


def record_execution_approval(conn, intent_id: str, approver_party_id: str, comments: str | None = None):
    intent = _one(conn, "SELECT id, status, requested_by_party_id FROM protocol_execution_intent WHERE id = :id FOR UPDATE", {"id": _uuid(intent_id, "intent_id")})
    if not intent or intent["status"] != "submitted":
        raise BridgeValidationError("human approvals may only be recorded for submitted intents")
    approver = _uuid(approver_party_id, "approver_party_id")
    if str(intent["requested_by_party_id"]) == approver:
        raise BridgeValidationError("the requester cannot approve their own execution intent")
    if not _one(conn, "SELECT id FROM party WHERE id = :actor AND party_type = 'person'", {"actor": approver}):
        raise BridgeValidationError("execution intent approval must come from an identified human party")
    return _one(conn, """
        INSERT INTO approval (collection, record_id, approver_id, action, comments)
        VALUES ('protocol_execution_intent', :record_id, :approver, 'approve', :comments)
        RETURNING id, record_id, approver_id, action
    """, {"record_id": str(intent["id"]), "approver": approver, "comments": comments})


def export_approved_intent(conn, intent_id: str):
    stable_id = _uuid(intent_id, "intent_id")
    intent = _one(conn, """
        SELECT i.id, i.request_payload, i.request_hash, i.approval_threshold,
               i.requested_by_party_id, i.status, m.protocol_project_id, m.status AS mapping_status
        FROM protocol_execution_intent i
        JOIN protocol_project_location m ON m.id = i.mapping_id
        WHERE i.id = :id FOR UPDATE OF i
    """, {"id": stable_id})
    if not intent or intent["mapping_status"] != "active" or intent["status"] not in {"submitted", "approved"}:
        raise BridgeValidationError("intent is not eligible for outbound dispatch")
    request = intent["request_payload"]
    if isinstance(request, str):
        request = json.loads(request)
    request = validate_execution_request(request, protocol_project_id=str(intent["protocol_project_id"]))
    vote_rows = conn.execute(conn.text("""
        SELECT DISTINCT a.approver_id
        FROM approval a JOIN party p ON p.id = a.approver_id
        WHERE a.collection = 'protocol_execution_intent' AND a.record_id = :id
          AND a.action = 'approve' AND p.party_type = 'person'
        ORDER BY a.approver_id
    """), {"id": stable_id}).mappings().all()
    voters = [str(row["approver_id"]) for row in vote_rows]
    envelope = build_dispatch_envelope(
        stable_id, request, str(intent["request_hash"]),
        approval_threshold=int(intent["approval_threshold"]), approved_by_party_ids=voters,
    )
    encoded = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
    outbox_hash = _sha256_json(envelope)
    inserted = _one(conn, """
        INSERT INTO protocol_execution_outbox
            (intent_id, payload, payload_hash, delivery_status)
        VALUES (:intent_id, CAST(:payload AS jsonb), :payload_hash, 'ready')
        ON CONFLICT (intent_id) DO NOTHING
        RETURNING id, intent_id, payload_hash, delivery_status
    """, {"intent_id": stable_id, "payload": encoded, "payload_hash": outbox_hash})
    if not inserted:
        inserted = _one(conn, "SELECT id, intent_id, payload_hash, delivery_status FROM protocol_execution_outbox WHERE intent_id = :id", {"id": stable_id})
        if not inserted or inserted["payload_hash"] != outbox_hash:
            raise BridgeConflictError("existing outbox item differs from the approved request snapshot")
    if intent["status"] == "submitted":
        conn.execute(conn.text("UPDATE protocol_execution_intent SET status = 'approved', approved_at = NOW() WHERE id = :id AND status = 'submitted'"), {"id": stable_id})
    return {"outbox": dict(inserted), "envelope": envelope}


def mark_outbox_dispatched(conn, intent_id: str, payload_hash: str):
    stable_id = _uuid(intent_id, "intent_id")
    if not isinstance(payload_hash, str) or not _HEX32.fullmatch(payload_hash):
        raise BridgeValidationError("payload_hash must be a 32-byte hex value")
    snapshot = _one(conn, """
        SELECT o.id, o.intent_id, o.payload, o.payload_hash, o.delivery_status,
               i.status AS intent_status, i.request_payload, m.protocol_project_id,
               m.status AS mapping_status
        FROM protocol_execution_outbox o
        JOIN protocol_execution_intent i ON i.id = o.intent_id
        JOIN protocol_project_location m ON m.id = i.mapping_id
        WHERE o.intent_id = :id
        FOR UPDATE OF o, i, m
    """, {"id": stable_id})
    if not snapshot or str(snapshot["payload_hash"]).lower() != payload_hash.lower():
        raise BridgeConflictError("outbox row is absent or its payload hash changed")
    stored_payload = snapshot["payload"]
    if isinstance(stored_payload, str):
        try:
            stored_payload = json.loads(stored_payload)
        except json.JSONDecodeError as exc:
            raise BridgeConflictError("stored outbox payload is not valid JSON") from exc
    if not isinstance(stored_payload, Mapping) or _sha256_json(stored_payload).lower() != payload_hash.lower():
        raise BridgeConflictError("outbox hash does not commit to the stored payload")
    if snapshot["delivery_status"] == "dispatched":
        return snapshot
    if snapshot["delivery_status"] != "ready" or snapshot["intent_status"] != "approved":
        raise BridgeConflictError("outbox row is no longer dispatchable")
    if snapshot["mapping_status"] != "active":
        raise BridgeValidationError("project crosswalk was revoked before dispatch")
    request = snapshot["request_payload"]
    if isinstance(request, str):
        request = json.loads(request)
    validate_execution_request(request, protocol_project_id=str(snapshot["protocol_project_id"]))
    result = _one(conn, """
        UPDATE protocol_execution_outbox
        SET delivery_status = 'dispatched', dispatched_at = NOW(), attempts = attempts + 1
        WHERE intent_id = :id AND payload_hash = :payload_hash AND delivery_status = 'ready'
        RETURNING id, intent_id, payload_hash, delivery_status, dispatched_at
    """, {"id": stable_id, "payload_hash": payload_hash})
    if not result:
        raise BridgeConflictError("outbox row changed while marking dispatch")
    return result


def record_reconciliation(conn, intent_id: str, result: Mapping[str, Any]):
    stable_id = _uuid(intent_id, "intent_id")
    intent = _one(conn, """
        SELECT i.request_payload, o.delivery_status
        FROM protocol_execution_intent i
        JOIN protocol_execution_outbox o ON o.intent_id = i.id
        WHERE i.id = :id AND i.status = 'approved'
    """, {"id": stable_id})
    if not intent or intent["delivery_status"] != "dispatched":
        raise BridgeValidationError("reconciliation requires a dispatched, approved KI intent")
    request = intent["request_payload"]
    if isinstance(request, str):
        request = json.loads(request)
    normalized = validate_reconciliation(request, result)
    inserted = _one(conn, """
        INSERT INTO protocol_execution_reconciliation
            (intent_id, chain_id, transaction_hash, receipt_block_number,
             receipt_block_hash, expected_effect_hash, observed_effect_hash,
             finality_status, evidence, review_status)
        VALUES (:intent_id, :chain_id, :tx_hash, :block_number, :block_hash,
                :expected_hash, :observed_hash, 'finalized', CAST(:evidence AS jsonb), 'submitted')
        ON CONFLICT (intent_id) DO NOTHING
        RETURNING id, intent_id, transaction_hash, review_status
    """, {
        "intent_id": stable_id, "chain_id": str(normalized["chain_id"]),
        "tx_hash": normalized["transaction_hash"],
        "block_number": int(normalized["receipt_block_number"]),
        "block_hash": normalized["receipt_block_hash"],
        "expected_hash": request["expected_effect_hash"],
        "observed_hash": normalized["observed_effect_hash"],
        "evidence": json.dumps(dict(result), sort_keys=True, separators=(",", ":")),
    })
    if inserted:
        return inserted
    existing = _one(conn, """
        SELECT id, intent_id, transaction_hash, review_status, evidence
        FROM protocol_execution_reconciliation WHERE intent_id = :id
    """, {"id": stable_id})
    if not existing or str(existing["transaction_hash"]).lower() != normalized["transaction_hash"].lower():
        raise BridgeConflictError("intent already has a different reconciliation record")
    old_evidence = existing["evidence"]
    if isinstance(old_evidence, str):
        old_evidence = json.loads(old_evidence)
    if old_evidence != dict(result)["evidence"]:
        raise BridgeConflictError("replayed reconciliation changed its evidence snapshot")
    return existing


def verify_reconciliation(conn, reconciliation_id: str, reviewed_by_party_id: str):
    stable_id = _uuid(reconciliation_id, "reconciliation_id")
    reviewer = _uuid(reviewed_by_party_id, "reviewed_by_party_id")
    if not _one(conn, "SELECT id FROM party WHERE id = :actor AND party_type = 'person'", {"actor": reviewer}):
        raise BridgeValidationError("reconciliation review requires an identified human party")
    result = _one(conn, """
        UPDATE protocol_execution_reconciliation
        SET review_status = 'verified', reviewed_by_party_id = :reviewer, reviewed_at = NOW()
        WHERE id = :id AND review_status = 'submitted'
        RETURNING id, intent_id, review_status, reviewed_by_party_id, reviewed_at
    """, {"id": stable_id, "reviewer": reviewer})
    if not result:
        raise BridgeConflictError("only a submitted reconciliation can be human-verified")
    return result
