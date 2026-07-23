"""Pure tests for Guild projection and reputation payload semantics."""

import uuid

from services.guilds.kgp import hash_bytes32, ADDRESS_RE, BYTES32_RE
from services.guilds.reputation import candidate_award_payload


def test_candidate_payload_is_deterministic_and_domain_scoped():
    event_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    candidate = {
        "guild_id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
        "domain_id": 7,
        "contributor_wallet": "0x00000000000000000000000000000000000000a1",
        "evidence_hash": hash_bytes32("evidence-a"),
        "reward_amount": 25,
        "task_id": "task-a",
        "evidence_review_id": "review-a",
    }
    first = candidate_award_payload(candidate, event_id, "v2026.07", 3)
    second = candidate_award_payload(candidate, event_id, "v2026.07", 3)
    assert first == second
    assert first["domain_id"] == 7
    assert first["amount"] == 25


def test_text_versions_are_encoded_as_bytes32_hashes():
    assert hash_bytes32("v2026.07").startswith("0x")
    assert len(hash_bytes32("v2026.07")) == 66


def test_hash_bytes32_preserves_valid_bytes32():
    valid = "0x" + "ab" * 32
    assert hash_bytes32(valid) == valid.lower()


def test_address_regex_validates_checksummed():
    assert ADDRESS_RE.fullmatch("0x0000000000000000000000000000000000000001")
    assert not ADDRESS_RE.fullmatch("not-an-address")
