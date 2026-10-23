"""Offline tests for the KI-to-Protocol submission connector."""

import copy
import unittest

from services.protocol_bridge.connector import submit_execution_envelope
from services.protocol_bridge.execution import (
    BridgeConflictError,
    BridgeValidationError,
    build_dispatch_envelope,
    canonical_request_hash,
)

INTENT_ID = "22222222-2222-4222-8222-222222222222"
REQUEST = {
    "protocol_version": "1",
    "request_id": "33333333-3333-4333-8333-333333333333",
    "project_id": "11111111-1111-4111-8111-111111111111",
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


APPROVERS = [
    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
]


def make_envelope():
    return build_dispatch_envelope(
        INTENT_ID,
        REQUEST,
        canonical_request_hash(REQUEST),
        approval_threshold=2,
        approved_by_party_ids=APPROVERS,
    )


class FakeProtocolClient:
    def __init__(self):
        self.requests = {}
        self.proposal_calls = 0
        self.fail_mode: str | None = None

    def get_execution_request(self, request_id):
        return self.requests.get(request_id)

    def propose_execution(self, request):
        self.proposal_calls += 1
        if self.fail_mode == "before_acceptance":
            raise OSError("temporary transport failure")
        self.requests[request["request_id"]] = {"request": copy.deepcopy(dict(request))}
        if self.fail_mode == "after_acceptance":
            raise OSError("response lost after chain accepted request")
        return {"accepted": True}


class ProtocolConnectorTests(unittest.TestCase):
    def test_submits_once_and_retries_idempotently_by_protocol_request_id(self):
        client = FakeProtocolClient()
        envelope = make_envelope()

        first = submit_execution_envelope(envelope, client)
        second = submit_execution_envelope(envelope, client)

        self.assertEqual(first["status"], "submitted")
        self.assertEqual(second["status"], "already_present")
        self.assertEqual(client.proposal_calls, 1)

    def test_transport_failure_before_acceptance_is_retryable(self):
        client = FakeProtocolClient()
        client.fail_mode = "before_acceptance"
        envelope = make_envelope()

        with self.assertRaisesRegex(OSError, "temporary transport failure"):
            submit_execution_envelope(envelope, client)
        self.assertEqual(client.get_execution_request(envelope["request_id"]), None)

        client.fail_mode = None
        result = submit_execution_envelope(envelope, client)
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(client.proposal_calls, 2)

    def test_lost_transport_response_recovers_by_reading_protocol_state(self):
        client = FakeProtocolClient()
        client.fail_mode = "after_acceptance"

        result = submit_execution_envelope(make_envelope(), client)

        self.assertEqual(result["status"], "already_present")
        self.assertEqual(client.proposal_calls, 1)

    def test_existing_request_id_with_different_payload_conflicts(self):
        client = FakeProtocolClient()
        envelope = make_envelope()
        changed = copy.deepcopy(REQUEST)
        changed["project_id"] = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        client.requests[envelope["request_id"]] = {"request": changed}

        with self.assertRaisesRegex(BridgeConflictError, "different request"):
            submit_execution_envelope(envelope, client)
        self.assertEqual(client.proposal_calls, 0)

    def test_rejects_modified_envelope_before_protocol_call(self):
        client = FakeProtocolClient()
        envelope = make_envelope()
        envelope["approved_by_party_ids"] = list(reversed(envelope["approved_by_party_ids"]))

        with self.assertRaises(BridgeValidationError):
            submit_execution_envelope(envelope, client)
        self.assertEqual(client.proposal_calls, 0)


if __name__ == "__main__":
    unittest.main()
