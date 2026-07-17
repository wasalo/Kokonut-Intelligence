"""Pure KGP service tests that do not require a database or live RPC."""

from eth_abi import encode
from web3 import Web3

from services.guilds.indexer import EVENT_TOPICS, KGP_EVENT_NAMES, decode_log
from services.guilds.kgp import build_claim_voucher, claim_typed_data, compute_award_id


def test_compute_award_id_matches_solidity_abi_encode():
    guild_id = "0x" + "11" * 32
    ledger_event_id = "0x" + "22" * 32
    calculation_version = "0x" + "33" * 32
    wallet = "0x00000000000000000000000000000000000000a1"
    expected = Web3.keccak(
        encode(
            ["bytes32", "uint256", "address", "bytes32", "bytes32"],
            [bytes.fromhex(guild_id[2:]), 4, wallet, bytes.fromhex(ledger_event_id[2:]), bytes.fromhex(calculation_version[2:])],
        )
    ).hex()
    expected = "0x" + expected.removeprefix("0x")
    assert compute_award_id(guild_id, 4, wallet, ledger_event_id, calculation_version) == expected


def test_claim_payload_and_typed_data_are_stable():
    voucher = build_claim_voucher(
        award_id="0x" + "aa" * 32,
        guild_id="0x" + "bb" * 32,
        contributor_wallet="0x00000000000000000000000000000000000000a1",
        domain_id=4,
        amount=25,
        epoch=2,
        evidence_hash="0x" + "cc" * 32,
        ledger_record_hash="0x" + "dd" * 32,
        calculation_version="0x" + "ee" * 32,
        nonce=7,
        deadline=2_000_000_000,
    )
    typed = claim_typed_data(10200, "0x00000000000000000000000000000000000000b1", voucher)
    assert typed["primaryType"] == "ClaimVoucher"
    assert typed["domain"]["chainId"] == 10200
    assert typed["message"]["amount"] == 25
    assert typed["message"]["contributor"].endswith("00A1")


def test_kgp_event_topics_are_unique_and_complete():
    assert KGP_EVENT_NAMES <= set(EVENT_TOPICS.values())
    assert len(EVENT_TOPICS) >= 20


def test_award_event_decoder_preserves_indexed_identity():
    award_id = "0x" + "11" * 32
    guild_id = "0x" + "22" * 32
    contributor = "0x" + "00" * 19 + "a1"
    topic = next(topic for topic, name in EVENT_TOPICS.items() if name == "KGP_Awarded")
    decoded = decode_log({
        "topics": [topic, award_id, guild_id, contributor],
        "data": "0x" + "00" * 32,
    })
    assert decoded["event_name"] == "KGP_Awarded"
    assert decoded["award_id"] == award_id
    assert decoded["guild_id"] == guild_id
    assert decoded["contributor_wallet"].lower() == contributor.lower()
