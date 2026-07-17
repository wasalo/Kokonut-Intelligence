"""Canonical KGP identity, voucher, and projection helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from eth_abi import encode
from web3 import Web3

ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
BYTES32_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")


def _keccak_hex(value: bytes) -> str:
    return "0x" + Web3.keccak(value).hex().removeprefix("0x")


def _address(value: str) -> str:
    if not ADDRESS_RE.fullmatch(value):
        raise ValueError(f"Invalid wallet address: {value}")
    return Web3.to_checksum_address(value)


def _bytes32(value: str, name: str) -> bytes:
    if not BYTES32_RE.fullmatch(value):
        raise ValueError(f"Invalid {name}: {value}")
    return bytes.fromhex(value[2:])


def hash_bytes32(value: str) -> str:
    """Represent a text or bytes32 value in the contract's bytes32 format."""
    if BYTES32_RE.fullmatch(value):
        return value.lower()
    return _keccak_hex(value.encode())


def compute_award_id(
    guild_id: str,
    domain_id: int,
    contributor_wallet: str,
    ledger_event_id: str,
    calculation_version: str,
) -> str:
    """Match KokonutGuildPoints.computeAwardId's ``abi.encode`` hash."""
    if domain_id < 0:
        raise ValueError("domain_id must be non-negative")
    encoded = encode(
        ["bytes32", "uint256", "address", "bytes32", "bytes32"],
        [
            _bytes32(guild_id, "guild_id"),
            domain_id,
            _address(contributor_wallet),
            _bytes32(ledger_event_id, "ledger_event_id"),
            _bytes32(calculation_version, "calculation_version"),
        ],
    )
    return _keccak_hex(encoded)


def build_claim_voucher(
    *,
    award_id: str,
    guild_id: str,
    contributor_wallet: str,
    domain_id: int,
    amount: int,
    epoch: int,
    evidence_hash: str,
    ledger_record_hash: str,
    calculation_version: str,
    nonce: int,
    deadline: int,
) -> dict[str, Any]:
    """Build the JSON-safe payload signed by the KGP claim signer."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    if epoch < 0 or nonce < 0 or deadline < 0:
        raise ValueError("epoch, nonce, and deadline must be non-negative")
    return {
        "awardId": "0x" + _bytes32(award_id, "award_id").hex(),
        "guildId": "0x" + _bytes32(guild_id, "guild_id").hex(),
        "contributor": _address(contributor_wallet),
        "domainId": domain_id,
        "amount": amount,
        "epoch": epoch,
        "evidenceHash": "0x" + _bytes32(evidence_hash, "evidence_hash").hex(),
        "ledgerRecordHash": "0x" + _bytes32(ledger_record_hash, "ledger_record_hash").hex(),
        "calculationVersion": "0x" + _bytes32(calculation_version, "calculation_version").hex(),
        "nonce": nonce,
        "deadline": deadline,
    }


def claim_typed_data(chain_id: int, verifying_contract: str, voucher: dict[str, Any]) -> dict[str, Any]:
    """Return EIP-712 typed data suitable for an approved signer implementation."""
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "ClaimVoucher": [
                {"name": "awardId", "type": "bytes32"},
                {"name": "guildId", "type": "bytes32"},
                {"name": "contributor", "type": "address"},
                {"name": "domainId", "type": "uint256"},
                {"name": "amount", "type": "uint256"},
                {"name": "epoch", "type": "uint256"},
                {"name": "evidenceHash", "type": "bytes32"},
                {"name": "ledgerRecordHash", "type": "bytes32"},
                {"name": "calculationVersion", "type": "bytes32"},
                {"name": "nonce", "type": "uint256"},
                {"name": "deadline", "type": "uint48"},
            ],
        },
        "primaryType": "ClaimVoucher",
        "domain": {
            "name": "Kokonut Guild Points",
            "version": "1",
            "chainId": chain_id,
            "verifyingContract": _address(verifying_contract),
        },
        "message": voucher,
    }


def insert_chain_event(cursor, event: dict[str, Any]) -> bool:
    """Insert one chain event; return false when an idempotency key exists."""
    cursor.execute(
        """
        INSERT INTO kgp_chain_event
            (deployment_id, chain_id, block_number, block_hash, transaction_hash,
             log_index, contract_address, event_signature, event_name, payload)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (deployment_id, transaction_hash, log_index) DO UPDATE SET
            block_number = EXCLUDED.block_number,
            block_hash = EXCLUDED.block_hash,
            contract_address = EXCLUDED.contract_address,
            event_signature = EXCLUDED.event_signature,
            event_name = EXCLUDED.event_name,
            payload = EXCLUDED.payload,
            is_canonical = TRUE,
            orphaned_at = NULL,
            processing_status = 'pending',
            processing_error = NULL,
            processed_at = NULL
        WHERE kgp_chain_event.is_canonical = FALSE
        RETURNING id
        """,
        (
            event["deployment_id"], event["chain_id"], event["block_number"],
            event.get("block_hash"), event["transaction_hash"], event["log_index"],
            event["contract_address"], event["event_signature"], event["event_name"],
            json.dumps(event.get("payload", {})),
        ),
    )
    return cursor.fetchone() is not None
