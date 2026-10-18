"""Tenant-scoped read-only views of location ecocredit batches."""

from __future__ import annotations

from decimal import Decimal
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def list_location_ecocredit_batches(
    operator_id: str,
    location_id: str,
    limit: int = 50,
    *,
    connection_factory: Callable | None = None,
) -> list[dict]:
    """Return batch state and account-aggregated ledger quantities.

    Wallet addresses and account-level balances are not exposed. Batch
    quantities and ledger totals remain separate so consumers can detect
    reconciliation gaps without treating either source as authoritative for
    the other.
    """
    try:
        operator_id = str(UUID(operator_id))
        location_id = str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator or location identifier") from exc
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

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
            resource="ecocredit",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                WITH location_batches AS (
                    SELECT id, credit_class_id, location_id, batch_code,
                           vintage_year, total_quantity, issued_quantity,
                           retired_quantity, cancelled_quantity, available_quantity,
                           unit, status, created_at
                      FROM credit_batch
                     WHERE location_id = %s::uuid
                ), ledger AS (
                    SELECT balance.credit_batch_id,
                           SUM(balance.tradable_amount) AS tradable_supply,
                           SUM(balance.retired_amount) AS retired_supply,
                           SUM(balance.escrowed_amount) AS escrowed_supply
                      FROM credit_balance AS balance
                      JOIN location_batches AS batch
                        ON batch.id = balance.credit_batch_id
                     GROUP BY balance.credit_batch_id
                )
                SELECT batch.id, batch.credit_class_id, class.name AS class_name,
                       class.credit_type, class.status AS class_status,
                       batch.batch_code, batch.vintage_year, batch.unit,
                       batch.status AS batch_status, batch.total_quantity,
                       batch.issued_quantity, batch.retired_quantity,
                       batch.cancelled_quantity, batch.available_quantity,
                       COALESCE(ledger.tradable_supply, 0) AS ledger_tradable_supply,
                       COALESCE(ledger.retired_supply, 0) AS ledger_retired_supply,
                       COALESCE(ledger.escrowed_supply, 0) AS ledger_escrowed_supply,
                       batch.created_at
                  FROM location_batches AS batch
                  JOIN credit_class AS class ON class.id = batch.credit_class_id
                  LEFT JOIN ledger ON ledger.credit_batch_id = batch.id
                 ORDER BY batch.created_at DESC, batch.id
                 LIMIT %s
                """,
                (location_id, limit),
            )
            columns = [description.name for description in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

        quantity_fields = (
            "total_quantity",
            "issued_quantity",
            "retired_quantity",
            "cancelled_quantity",
            "available_quantity",
            "ledger_tradable_supply",
            "ledger_retired_supply",
            "ledger_escrowed_supply",
        )
        for row in rows:
            row["id"] = str(row["id"])
            row["credit_class_id"] = str(row["credit_class_id"])
            row["created_at"] = row["created_at"].isoformat() if row["created_at"] else None
            for field in quantity_fields:
                row[field] = str(Decimal(row[field] or 0).quantize(Decimal("0.0001")))
        return rows
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
