"""Tenant-scoped aggregate reads for carbon-credit custody and retirement."""

from __future__ import annotations

from decimal import Decimal
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def get_credit_custody_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return aggregate credit and retirement state without sensitive details.

    Retirement ledger totals remain separate from the credit reservation
    fields. Beneficiaries, wallets, statements, evidence references, idempotency
    keys, and reviewer notes are never selected.
    """
    try:
        operator_id = str(UUID(operator_id))
        location_id = str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator or location identifier") from exc

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="carbon_credit",
            action="read",
            required_scopes=(("credit_retirement", "read"),),
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS total_credits,
                       COALESCE(SUM(issuable_tonnes), 0) AS total_issuable_tonnes,
                       COALESCE(SUM(retired_tonnes), 0) AS total_retired_tonnes,
                       COALESCE(SUM(reserved_tonnes), 0) AS total_reserved_tonnes,
                       COALESCE(SUM(available_tonnes), 0) AS total_available_tonnes,
                       COALESCE(SUM(total_value_usd), 0) AS recorded_total_value_usd
                  FROM carbon_credit
                 WHERE location_id = %s::uuid
                """,
                (location_id,),
            )
            credit_totals = cur.fetchone()
            cur.execute(
                """
                SELECT status, COUNT(*) AS retirement_count,
                       COALESCE(SUM(retired_tonnes), 0) AS requested_tonnes,
                       COALESCE(SUM(retirement_value_usd), 0) AS requested_value_usd
                  FROM credit_retirement
                 WHERE location_id = %s::uuid
                 GROUP BY status
                 ORDER BY status
                """,
                (location_id,),
            )
            retirement_rows = cur.fetchall()

        return {
            "location_id": location_id,
            "total_credits": int(credit_totals[0] or 0),
            "credit_totals": {
                "issuable_tonnes": _fixed_decimal(credit_totals[1], 4),
                "retired_tonnes": _fixed_decimal(credit_totals[2], 4),
                "reserved_tonnes": _fixed_decimal(credit_totals[3], 4),
                "available_tonnes": _fixed_decimal(credit_totals[4], 4),
                "recorded_total_value_usd": _fixed_decimal(credit_totals[5], 2),
            },
            "retirements_by_status": [
                {
                    "status": row[0],
                    "count": int(row[1] or 0),
                    "requested_tonnes": _fixed_decimal(row[2], 4),
                    "requested_value_usd": _fixed_decimal(row[3], 2),
                }
                for row in retirement_rows
            ],
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def _fixed_decimal(value, scale: int) -> str:
    return format(Decimal(value or 0), f".{scale}f")
