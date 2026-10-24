"""Deferred regenerative credit ledger (Keynes deferred-pay analog).

A withheld, credited claim on future regenerative output. Agents may ONLY
propose draft credits; settlement/redemption are human-approved flows out of
scope. All write paths are gated by services/agents/safety.py.

The `credit_capacity` function is the read-only "network-underwritten deficit"
analog: the sum of drafted (withheld) credits a location can draw against
later, mirroring Keynes's external-deficit / allied-financing idea.
"""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from services.agents.safety import assert_agent_action_allowed
from services.common.database import get_connection
from services.common.logging import get_logger

logger = get_logger(__name__)

_ALLOWED_SOURCE_TYPES = {
    "carbon_credit_surplus",
    "cooperative_surplus",
    "federation_underwrite",
}
_ALLOWED_REDEEM = {
    "regenerative_investment",
    "shared_dividend",
    "stewardship_grant",
}


def _clean(row: Any) -> Dict[str, Any]:
    return dict(row) if isinstance(row, dict) else dict(row)


def _same_credit_request(existing: Any, requested: tuple) -> bool:
    """Compare the immutable request fields for an idempotency-key retry."""
    if isinstance(existing, dict):
        fields = (
            "location_id", "contributor_party_id", "source_type", "source_ref_id",
            "withheld_amount", "unit", "redeemable_against", "created_by",
        )
        values = tuple(existing.get(field) for field in fields)
    else:
        values = tuple(existing)

    if len(values) != len(requested):
        return False

    # Database UUID values arrive as UUID objects while callers usually pass
    # strings. Compare their canonical text without changing SQL parameters.
    id_indexes = {0, 1, 3, 7}
    for index, (actual, expected) in enumerate(zip(values, requested)):
        if index in id_indexes:
            if (str(actual) if actual is not None else None) != (
                str(expected) if expected is not None else None
            ):
                return False
        elif index == 4:
            try:
                if Decimal(str(actual)) != Decimal(str(expected)):
                    return False
            except (InvalidOperation, ValueError):
                return False
        elif actual != expected:
            return False
    return True


def propose_credit(
    conn,
    location_id: str,
    source_type: str,
    withheld_amount: float,
    unit: str = "usd",
    contributor_party_id: Optional[str] = None,
    source_ref_id: Optional[str] = None,
    redeemable_against: str = "regenerative_investment",
    created_by: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Propose a DRAFT regenerative credit. Agents may NOT settle here.

    Enforced status='draft' and validated through safety.assert_agent_action_allowed.
    """
    if source_type not in _ALLOWED_SOURCE_TYPES:
        raise ValueError(f"invalid source_type: {source_type}")
    if redeemable_against not in _ALLOWED_REDEEM:
        raise ValueError(f"invalid redeemable_against: {redeemable_against}")
    try:
        amount = Decimal(str(withheld_amount))
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal("NaN")
    if not amount.is_finite() or amount <= 0:
        raise ValueError("withheld_amount must be positive")

    idem = idempotency_key or f"regen-credit-{uuid.uuid4().hex}"
    # Gated: agents may only create a draft credit ledger entry.
    assert_agent_action_allowed(
        "create",
        "regenerative_credit_ledger",
        {"status": "draft", "idempotency_key": idem},
    )

    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO regenerative_credit_ledger (
                location_id, contributor_party_id, source_type, source_ref_id,
                withheld_amount, unit, redeemable_against, credit_status,
                idempotency_key, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'draft', %s, %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id, credit_status
            """,
            (
                location_id, contributor_party_id, source_type, source_ref_id,
                withheld_amount, unit, redeemable_against, idem, created_by,
            ),
        )
        row = cur.fetchone()
        if row is None:
            cur.execute(
                """
                SELECT id, credit_status, location_id, contributor_party_id, source_type,
                       source_ref_id, withheld_amount, unit, redeemable_against, created_by
                FROM regenerative_credit_ledger
                WHERE idempotency_key = %s
                """,
                (idem,),
            )
            existing = cur.fetchone()
    finally:
        cur.close()

    if row is None:
        if not existing:
            return {
                "status": "skipped",
                "idempotency_key": idem,
                "reason": "idempotency key conflict row no longer exists",
            }
        existing_values = (
            existing[2], existing[3], existing[4], existing[5],
            existing[6], existing[7], existing[8], existing[9],
        ) if not isinstance(existing, dict) else existing
        requested_values = (
            location_id, contributor_party_id, source_type, source_ref_id,
            withheld_amount, unit, redeemable_against, created_by,
        )
        if not _same_credit_request(existing_values, requested_values):
            raise ValueError("idempotency_key was reused with a different credit request")
        existing_id = existing.get("id") if isinstance(existing, dict) else existing[0]
        existing_status = existing.get("credit_status") if isinstance(existing, dict) else existing[1]
        return {
            "id": str(existing_id),
            "credit_status": existing_status,
            "idempotency_key": idem,
            "status": "duplicate",
        }
    rid = row[0] if isinstance(row, (list, tuple)) else list(row.values())[0]
    return {
        "id": str(rid),
        "credit_status": "draft",
        "idempotency_key": idem,
        "location_id": location_id,
        "source_type": source_type,
        "withheld_amount": withheld_amount,
        "redeemable_against": redeemable_against,
    }


def list_draft_credits(conn, location_id: str) -> List[Dict[str, Any]]:
    """List draft regenerative credits for a location (read-only)."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT * FROM regenerative_credit_ledger
            WHERE location_id = %s AND credit_status = 'draft'
            ORDER BY created_at DESC
            """,
            (location_id,),
        )
        rows = [_clean(r) for r in cur.fetchall()]
    finally:
        cur.close()
    return rows


def credit_capacity(conn, location_id: str) -> Dict[str, Any]:
    """Read-only 'network-underwritten deficit' analog.

    Sum of drafted (withheld) credits the location can later draw against.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COALESCE(SUM(withheld_amount),0), COUNT(*)
            FROM regenerative_credit_ledger
            WHERE location_id = %s AND credit_status = 'draft'
            """,
            (location_id,),
        )
        row = cur.fetchone()
    finally:
        cur.close()
    total = float(row[0] if row else 0) or 0.0
    count = int((row[1] if row else 0) or 0)
    return {
        "location_id": location_id,
        "draft_credit_total": round(total, 2),
        "draft_credit_count": count,
        "note": "read-only capacity; settlement requires human confirmation",
    }


def credit_cli_propose(
    location_id: str,
    source_type: str,
    amount: float,
    **kwargs,
) -> Dict[str, Any]:
    with get_connection() as conn:
        return propose_credit(conn, location_id, source_type, amount, **kwargs)


def credit_cli_list(location_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        return list_draft_credits(conn, location_id)


def credit_cli_capacity(location_id: str) -> Dict[str, Any]:
    with get_connection() as conn:
        return credit_capacity(conn, location_id)
