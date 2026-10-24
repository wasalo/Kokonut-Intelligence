"""Unit tests for the KI ↔ Kokonut Protocol bridge contract."""

import copy
import hashlib
import json
import unittest
import uuid
from pathlib import Path

from services.protocol_bridge.execution import (
    BridgeConflictError,
    BridgeValidationError,
    activate_project_mapping,
    build_dispatch_envelope,
    canonical_request_hash,
    create_execution_intent,
    create_project_mapping,
    export_approved_intent,
    mark_outbox_dispatched,
    record_execution_approval,
    record_reconciliation,
    revoke_project_mapping,
    validate_execution_request,
    validate_reconciliation,
)

PROJECT_ID = "11111111-1111-4111-8111-111111111111"
INTENT_ID = "22222222-2222-4222-8222-222222222222"
REQUEST = {
    "protocol_version": "1",
    "request_id": "33333333-3333-4333-8333-333333333333",
    "project_id": PROJECT_ID,
    "chain_namespace": "eip155",
    "chain_id": "84532",
    "operation": "set_value",
    "target": "0x1234567890abcdef1234567890abcdef12345678",
    "value_base_units": "0",
    "gas_limit": "120000",
    "calldata_hash": "0x" + "11" * 32,
    "signing_payload_hash": "0x" + "22" * 32,
    "signer_key_version": 0,
    "expected_effect_hash": "0x" + "33" * 32,
    "nonce": "0",
    "gas_policy": {"max_fee": "1000000000", "max_priority_fee": "1000000"},
    "expires_at": "2099-01-01T00:00:00Z",
    "policy_version": "1",
    "idempotency_key": "intent-1",
}


class _FakeResult:
    def __init__(self, value):
        self.rows = value if isinstance(value, list) else ([value] if value is not None else [])

    def mappings(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)


class _FakeConnection:
    def __init__(self, rows):
        self.rows = list(rows)
        self.statements = []

    @staticmethod
    def text(sql):
        return sql

    def execute(self, sql, params=None):
        self.statements.append((sql, params or {}))
        return _FakeResult(self.rows.pop(0) if self.rows else None)


class ProtocolBridgeValidationTests(unittest.TestCase):
    def test_request_validation_binds_explicit_project_crosswalk(self):
        normalized = validate_execution_request(REQUEST, protocol_project_id=PROJECT_ID)
        self.assertEqual(normalized, REQUEST)

        wrong_project = copy.deepcopy(REQUEST)
        wrong_project["project_id"] = str(uuid.uuid4())
        with self.assertRaisesRegex(BridgeValidationError, "crosswalk"):
            validate_execution_request(wrong_project, protocol_project_id=PROJECT_ID)

    def test_request_rejects_expired_or_timezone_naive_expiry(self):
        expired = copy.deepcopy(REQUEST)
        expired["expires_at"] = "2000-01-01T00:00:00Z"
        with self.assertRaisesRegex(BridgeValidationError, "future"):
            validate_execution_request(expired, protocol_project_id=PROJECT_ID)
        naive = copy.deepcopy(REQUEST)
        naive["expires_at"] = "2099-01-01T00:00:00"
        with self.assertRaisesRegex(BridgeValidationError, "timezone"):
            validate_execution_request(naive, protocol_project_id=PROJECT_ID)

    def test_request_validation_rejects_non_allowlisted_evm_network(self):
        mainnet = copy.deepcopy(REQUEST)
        mainnet["chain_id"] = "1"
        with self.assertRaisesRegex(BridgeValidationError, "testnet"):
            validate_execution_request(mainnet, protocol_project_id=PROJECT_ID)

    def test_dispatch_envelope_requires_distinct_human_quorum(self):
        voters = [str(uuid.uuid4()), str(uuid.uuid4())]
        request_hash = canonical_request_hash(REQUEST)
        envelope = build_dispatch_envelope(
            INTENT_ID, REQUEST, request_hash, approval_threshold=2, approved_by_party_ids=voters
        )
        self.assertEqual(envelope["intent_id"], INTENT_ID)
        self.assertEqual(envelope["request"], REQUEST)
        self.assertEqual(envelope["request_hash"], request_hash)
        self.assertEqual(envelope["approval_count"], 2)

        with self.assertRaisesRegex(BridgeValidationError, "quorum"):
            build_dispatch_envelope(
                INTENT_ID, REQUEST, request_hash, approval_threshold=2,
                approved_by_party_ids=[voters[0], voters[0]],
            )

    def test_reconciliation_accepts_only_finalized_matching_effect_evidence(self):
        result = {
            "request_id": REQUEST["request_id"],
            "chain_namespace": "eip155",
            "chain_id": "84532",
            "transaction_hash": "0x" + "44" * 32,
            "receipt_block_number": "42",
            "receipt_block_hash": "0x" + "55" * 32,
            "finality_status": "finalized",
            "observed_effect_hash": REQUEST["expected_effect_hash"],
            "effect_verified": True,
            "evidence": {"adapter_version": "1", "effect_kind": "event"},
        }
        normalized = validate_reconciliation(REQUEST, result)
        self.assertEqual(normalized["review_status"], "submitted")
        self.assertEqual(normalized["transaction_hash"], result["transaction_hash"])

        unfinalized = copy.deepcopy(result)
        unfinalized["finality_status"] = "confirmation_threshold_met"
        with self.assertRaisesRegex(BridgeValidationError, "finalized"):
            validate_reconciliation(REQUEST, unfinalized)

        wrong_effect = copy.deepcopy(result)
        wrong_effect["observed_effect_hash"] = "0x" + "66" * 32
        with self.assertRaisesRegex(BridgeConflictError, "effect"):
            validate_reconciliation(REQUEST, wrong_effect)

    def test_mapping_creation_requires_an_identified_human(self):
        project_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        location_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        mapper_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        mapping = {"id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd", "status": "draft"}
        conn = _FakeConnection([{"id": mapper_id}, mapping])
        created = create_project_mapping(conn, project_id, location_id, mapper_id)
        self.assertEqual(created["status"], "draft")
        self.assertIn("INSERT INTO protocol_project_location", conn.statements[1][0])

    def test_mapping_activation_requires_a_distinct_human_approver(self):
        mapping_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        mapper_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        approver_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        conn = _FakeConnection([
            {"id": mapping_id, "mapped_by_party_id": mapper_id, "status": "draft"},
            {"id": approver_id},
            {"id": mapping_id, "status": "active"},
        ])
        activated = activate_project_mapping(conn, mapping_id, approver_id)
        self.assertEqual(activated["status"], "active")
        self.assertIn("SET status = 'active'", conn.statements[2][0])

    def test_revoke_crosswalk_requires_an_identified_human(self):
        mapping_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        actor_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        conn = _FakeConnection([
            {"id": mapping_id, "status": "active"},
            {"id": actor_id},
            {"id": mapping_id, "status": "revoked"},
        ])
        revoked = revoke_project_mapping(conn, mapping_id, actor_id)
        self.assertEqual(revoked["status"], "revoked")
        self.assertIn("revoked_by_party_id", conn.statements[2][0])

    def test_create_intent_uses_active_explicit_crosswalk_and_human_requester(self):
        mapping_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        requester = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        conn = _FakeConnection([
            {"id": mapping_id, "protocol_project_id": PROJECT_ID, "status": "active"},
            {"id": requester},
            {"id": INTENT_ID, "request_hash": canonical_request_hash(REQUEST), "status": "draft"},
        ])
        created = create_execution_intent(conn, mapping_id, REQUEST, requester, approval_threshold=2)
        self.assertEqual(created["status"], "draft")
        insert_sql, params = conn.statements[2]
        self.assertIn("INSERT INTO protocol_execution_intent", insert_sql)
        self.assertEqual(params["request_id"], REQUEST["request_id"])
        self.assertEqual(params["request_hash"], canonical_request_hash(REQUEST))
        self.assertEqual(params["approval_threshold"], 2)

    def test_export_creates_one_quorum_bound_durable_envelope(self):
        voters = [
            {"approver_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc"},
            {"approver_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd"},
        ]
        outbox = {
            "id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
            "intent_id": INTENT_ID,
            "payload_hash": "0x" + "77" * 32,
            "delivery_status": "ready",
        }
        conn = _FakeConnection([
            {
                "id": INTENT_ID, "request_payload": REQUEST,
                "request_hash": canonical_request_hash(REQUEST), "approval_threshold": 2,
                "requested_by_party_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "status": "submitted", "protocol_project_id": PROJECT_ID,
                "mapping_status": "active",
            },
            voters,
            outbox,
            None,
        ])
        result = export_approved_intent(conn, INTENT_ID)
        self.assertEqual(result["envelope"]["approval_count"], 2)
        self.assertEqual(result["envelope"]["request"], REQUEST)
        self.assertIn("INSERT INTO protocol_execution_outbox", conn.statements[2][0])
        self.assertIn("SET status = 'approved'", conn.statements[3][0])

    def test_record_approval_rejects_requester_self_approval(self):
        requester = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        conn = _FakeConnection([{
            "id": INTENT_ID, "status": "submitted", "requested_by_party_id": requester,
        }])
        with self.assertRaisesRegex(BridgeValidationError, "cannot approve their own"):
            record_execution_approval(conn, INTENT_ID, requester)
        self.assertEqual(len(conn.statements), 1)

    def test_reconciliation_records_finalized_evidence_as_submitted(self):
        tx_hash = "0x" + "44" * 32
        result = {
            "request_id": REQUEST["request_id"], "chain_namespace": "eip155", "chain_id": "84532",
            "transaction_hash": tx_hash, "receipt_block_number": "42",
            "receipt_block_hash": "0x" + "55" * 32, "finality_status": "finalized",
            "observed_effect_hash": REQUEST["expected_effect_hash"], "effect_verified": True,
            "evidence": {"adapter_version": "1", "effect_kind": "event"},
        }
        inserted = {"id": "ffffffff-ffff-4fff-8fff-ffffffffffff", "intent_id": INTENT_ID,
                    "transaction_hash": tx_hash, "review_status": "submitted"}
        conn = _FakeConnection([{"request_payload": REQUEST, "delivery_status": "dispatched"}, inserted])
        row = record_reconciliation(conn, INTENT_ID, result)
        self.assertEqual(row["review_status"], "submitted")
        self.assertIn("ON CONFLICT (intent_id) DO NOTHING", conn.statements[1][0])

    def test_dispatch_marks_only_hash_verified_stored_envelope(self):
        voters = ["cccccccc-cccc-4ccc-8ccc-cccccccccccc"]
        envelope = build_dispatch_envelope(
            INTENT_ID, REQUEST, canonical_request_hash(REQUEST),
            approval_threshold=1, approved_by_party_ids=voters,
        )
        payload_hash = "0x" + hashlib.sha256(
            json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        snapshot = {
            "id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", "intent_id": INTENT_ID,
            "payload": envelope, "payload_hash": payload_hash, "delivery_status": "ready",
            "intent_status": "approved", "request_payload": REQUEST,
            "protocol_project_id": PROJECT_ID, "mapping_status": "active",
        }
        dispatched = {**snapshot, "delivery_status": "dispatched"}
        conn = _FakeConnection([snapshot, dispatched])
        result = mark_outbox_dispatched(conn, INTENT_ID, payload_hash)
        self.assertEqual(result["delivery_status"], "dispatched")
        self.assertIn("FOR UPDATE OF o, i, m", conn.statements[0][0])

    def test_dispatch_rejects_stored_hash_that_does_not_commit_to_payload(self):
        corrupted_hash = "0x" + "77" * 32
        conn = _FakeConnection([{
            "intent_status": "approved", "delivery_status": "ready",
            "request_payload": REQUEST, "protocol_project_id": PROJECT_ID,
            "mapping_status": "active", "payload_hash": corrupted_hash,
            "payload": {"tampered": True},
        }])
        with self.assertRaisesRegex(BridgeConflictError, "hash does not commit to"):
            mark_outbox_dispatched(conn, INTENT_ID, corrupted_hash)
        self.assertEqual(len(conn.statements), 1)

    def test_dispatch_rejects_expired_or_revoked_crosswalk_before_marking_sent(self):
        expired = copy.deepcopy(REQUEST)
        expired["expires_at"] = "2000-01-01T00:00:00Z"
        expired_payload = {}
        expired_hash = "0x" + hashlib.sha256(b"{}").hexdigest()
        conn = _FakeConnection([{
            "intent_status": "approved",
            "delivery_status": "ready",
            "request_payload": expired,
            "protocol_project_id": PROJECT_ID,
            "mapping_status": "active",
            "payload_hash": expired_hash,
            "payload": expired_payload,
        }])
        with self.assertRaisesRegex(BridgeValidationError, "future"):
            mark_outbox_dispatched(conn, INTENT_ID, expired_hash)
        self.assertEqual(len(conn.statements), 1)
        self.assertIn("FOR UPDATE", conn.statements[0][0])

    def test_migration_installs_crosswalk_approval_outbox_and_review_guards(self):
        migration = Path(__file__).resolve().parents[1] / "schemas/postgres/600_protocol_execution_bridge.sql"
        self.assertTrue(migration.exists())
        sql = migration.read_text().casefold()
        for required in (
            "create table if not exists public.protocol_project_location",
            "create table if not exists public.protocol_execution_intent",
            "create table if not exists public.protocol_execution_outbox",
            "create table if not exists public.protocol_execution_reconciliation",
            "uq_protocol_project_location_active",
            "trg_protocol_execution_approval_guard",
            "trg_protocol_execution_outbox_guard",
            "trg_protocol_execution_reconciliation_guard",
            "human approval quorum has not been met",
            "new.payload->'request' is distinct from intent.request_payload",
            "new.payload->>'request_hash' is distinct from intent.request_hash",
            "new.payload->'approved_by_party_ids' is distinct from voter_ids",
            "new.payload is distinct from jsonb_build_object(",
            "approved intent, active crosswalk, and unexpired request are required before dispatch",
            "reconciliation requires dispatched, finalized, effect-matched execution evidence",
        ):
            self.assertIn(required, sql)
