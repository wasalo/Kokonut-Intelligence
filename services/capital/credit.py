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
    if withheld_amount <= 0:
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
    finally:
        cur.close()

    if row is None:
        return {"status": "skipped", "idempotency_key": idem,
                "reason": "idempotency_key already present"}
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
