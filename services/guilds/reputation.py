"""Canonical PostgreSQL-to-KGP reputation event creation."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from web3 import Web3

from .kgp import compute_award_id, hash_bytes32


def _identity_hash(value: Any) -> str:
    return "0x" + Web3.keccak(text=str(value)).hex().removeprefix("0x")


def candidate_award_payload(candidate: dict[str, Any], event_id: uuid.UUID, calculation_version: str, epoch: int) -> dict[str, Any]:
    """Build the exact award commitment consumed by the Solidity contract."""
    guild_id = _identity_hash(candidate["guild_id"])
    ledger_event_id = _identity_hash(event_id)
    calculation_version_hash = hash_bytes32(calculation_version)
    award_id = compute_award_id(
        guild_id,
        int(candidate["domain_id"]),
        candidate["contributor_wallet"],
        ledger_event_id,
        calculation_version_hash,
    )
    evidence_hash = candidate["evidence_hash"]
    raw_amount = Decimal(str(candidate.get("reward_amount") or 0))
    if raw_amount != raw_amount.to_integral_value():
        raise ValueError("KGP reward_amount must be an integer point value")
    amount = int(raw_amount)
    if not evidence_hash or amount <= 0:
        raise ValueError("A KGP candidate requires evidence_hash and a positive reward_amount")
    return {
        "award_id": award_id,
        "guild_id": guild_id,
        "contributor_wallet": Web3.to_checksum_address(candidate["contributor_wallet"]),
        "domain_id": int(candidate["domain_id"]),
        "amount": amount,
        "epoch": epoch,
        "evidence_hash": hash_bytes32(evidence_hash),
        "ledger_record_hash": "0x" + Web3.keccak(text=f"guild_reputation_event:{event_id}").hex().removeprefix("0x"),
        "calculation_version": calculation_version_hash,
        "event_id": event_id,
    }


def create_award_event(
    cursor,
    task_id: str,
    epoch: int,
    calculation_version: str,
    amount: int | None = None,
    settlement_method: str = "automatic",
) -> dict[str, Any]:
    """Create an idempotent canonical award from an accepted task review."""
    cursor.execute(
        """
        SELECT task_id, guild_id, domain_id, contributor_id, contributor_wallet,
               evidence_review_id, evidence_hash, evidence_cid, reward_amount
        FROM v_guild_reputation_candidates
        WHERE task_id = %s
        """,
        (task_id,),
    )
    candidate = cursor.fetchone()
    if not candidate:
        raise ValueError("Task is not an accepted, governed KGP candidate")
    if not isinstance(candidate, dict):
        candidate = dict(candidate)
    if amount is not None:
        candidate["reward_amount"] = amount

    event_id = uuid.uuid5(uuid.NAMESPACE_URL, f"kokonut:kgp:{task_id}:{epoch}:{calculation_version}")
    payload = candidate_award_payload(candidate, event_id, calculation_version, epoch)
    cursor.execute(
        """
        INSERT INTO guild_reputation_event
            (id, guild_id, contributor_id, contributor_wallet, domain_id,
             event_type, settlement_method, settlement_status, review_status,
             amount, epoch, evidence_hash, evidence_cid, ledger_record_hash,
             calculation_version, award_id, task_id, evidence_review_id)
        VALUES (%s, %s, %s, %s, %s, 'award', %s, 'pending', 'submitted',
                %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (award_id) DO NOTHING
        RETURNING id
        """,
        (
            str(event_id), candidate["guild_id"], candidate.get("contributor_id"),
            candidate["contributor_wallet"], candidate["domain_id"], settlement_method,
            payload["amount"], epoch, payload["evidence_hash"], candidate.get("evidence_cid"),
            payload["ledger_record_hash"], payload["calculation_version"], payload["award_id"],
            candidate["task_id"], candidate["evidence_review_id"],
        ),
    )
    row = cursor.fetchone()
    persisted_event_id = row[0] if row and not isinstance(row, dict) else (row["id"] if row else None)
    if row is None:
        cursor.execute(
            """
            SELECT id, guild_id, contributor_wallet, domain_id, amount, epoch,
                   evidence_hash, ledger_record_hash, calculation_version
            FROM guild_reputation_event
            WHERE award_id = %s
            """,
            (payload["award_id"],),
        )
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("KGP award conflict row disappeared")
        existing = dict(row) if isinstance(row, dict) else {
            "id": row[0], "guild_id": row[1], "contributor_wallet": row[2],
            "domain_id": row[3], "amount": row[4], "epoch": row[5],
            "evidence_hash": row[6], "ledger_record_hash": row[7],
            "calculation_version": row[8],
        }
        expected = {
            "guild_id": candidate["guild_id"], "contributor_wallet": candidate["contributor_wallet"],
            "domain_id": candidate["domain_id"], "amount": payload["amount"], "epoch": epoch,
            "evidence_hash": payload["evidence_hash"], "ledger_record_hash": payload["ledger_record_hash"],
            "calculation_version": payload["calculation_version"],
        }
        for field, value in expected.items():
            if str(existing[field]).lower() != str(value).lower():
                raise ValueError(f"Immutable KGP award conflict for {field}")
        persisted_event_id = existing["id"]
    payload["event_id"] = persisted_event_id or event_id
    return payload


def verify_award_event(cursor, event_id: str, reviewer_id: str) -> None:
    """Apply the human review transition required before KGP settlement."""
    cursor.execute(
        """
        UPDATE guild_reputation_event
        SET review_status = 'verified', reviewed_by = %s, reviewed_at = NOW(), updated_at = NOW()
        WHERE id = %s AND review_status IN ('submitted', 'draft')
        RETURNING id
        """,
        (reviewer_id, event_id),
    )
    if cursor.fetchone() is None:
        raise ValueError("KGP event is not pending human verification")


def canonical_balance(cursor, guild_id: str, domain_id: int, wallet: str) -> int:
    cursor.execute(
        """
        SELECT COALESCE(kgp_balance, 0)
        FROM v_kgp_canonical_balance
        WHERE guild_id = %s AND domain_id = %s AND LOWER(contributor_wallet) = LOWER(%s)
        """,
        (guild_id, domain_id, wallet),
    )
    row = cursor.fetchone()
    return int(row[0]) if row else 0
