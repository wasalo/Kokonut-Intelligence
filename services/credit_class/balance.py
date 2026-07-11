"""Credit Balance: per-account balance tracking for tradable/retired/escrowed credits."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger("credit_class.balance")


def get_balance(conn, batch_id: str, account_address: str) -> dict:
    result = conn.execute(
        conn.text(
            "SELECT * FROM credit_balance WHERE credit_batch_id = :bid AND account_address = :addr"
        ),
        {"bid": batch_id, "addr": account_address},
    ).mappings().first()
    if not result:
        return {
            "credit_batch_id": batch_id,
            "account_address": account_address,
            "tradable_amount": 0,
            "retired_amount": 0,
            "escrowed_amount": 0,
        }
    return dict(result)


def get_balances_for_account(conn, account_address: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT cb.*, b.batch_code, b.unit, cc.name AS class_name "
            "FROM credit_balance cb "
            "JOIN credit_batch b ON b.id = cb.credit_batch_id "
            "JOIN credit_class cc ON cc.id = b.credit_batch_id "
            "WHERE cb.account_address = :addr "
            "ORDER BY cb.updated_at DESC"
        ),
        {"addr": account_address},
    )
    return [dict(r) for r in result.mappings()]


def get_balances_for_batch(conn, batch_id: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT * FROM credit_balance WHERE credit_batch_id = :bid ORDER BY account_address"
        ),
        {"bid": batch_id},
    )
    return [dict(r) for r in result.mappings()]


def get_all_balances(conn, limit: int = 1000) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT cb.*, b.batch_code, b.unit "
            "FROM credit_balance cb "
            "JOIN credit_batch b ON b.id = cb.credit_batch_id "
            "ORDER BY cb.updated_at DESC LIMIT :limit"
        ),
        {"limit": limit},
    )
    return [dict(r) for r in result.mappings()]


def upsert_balance(conn, batch_id: str, account_address: str,
                   tradable_delta: float = 0, retired_delta: float = 0,
                   escrowed_delta: float = 0) -> dict:
    existing = conn.execute(
        conn.text(
            "SELECT id, tradable_amount, retired_amount, escrowed_amount "
            "FROM credit_balance WHERE credit_batch_id = :bid AND account_address = :addr"
        ),
        {"bid": batch_id, "addr": account_address},
    ).mappings().first()

    if existing:
        new_tradable = float(existing["tradable_amount"]) + tradable_delta
        new_retired = float(existing["retired_amount"]) + retired_delta
        new_escrowed = float(existing["escrowed_amount"]) + escrowed_delta

        if new_tradable < 0 or new_retired < 0 or new_escrowed < 0:
            raise ValueError(f"Insufficient balance: tradable={new_tradable}, retired={new_retired}, escrowed={new_escrowed}")

        conn.execute(
            conn.text(
                "UPDATE credit_balance SET "
                "tradable_amount = :ta, retired_amount = :ra, escrowed_amount = :ea, "
                "updated_at = NOW() WHERE id = :id"
            ),
            {"ta": new_tradable, "ra": new_retired, "ea": new_escrowed, "id": str(existing["id"])},
        )
        return {"id": str(existing["id"]), "tradable": new_tradable, "retired": new_retired, "escrowed": new_escrowed}
    else:
        if tradable_delta < 0 or retired_delta < 0 or escrowed_delta < 0:
            raise ValueError("Cannot have negative initial balance")

        result = conn.execute(
            conn.text(
                "INSERT INTO credit_balance (credit_batch_id, account_address, tradable_amount, retired_amount, escrowed_amount) "
                "VALUES (:bid, :addr, :ta, :ra, :ea) RETURNING id"
            ),
            {"bid": batch_id, "addr": account_address,
             "ta": tradable_delta, "ra": retired_delta, "ea": escrowed_delta},
        ).mappings().first()
        return {"id": str(result["id"]), "tradable": tradable_delta, "retired": retired_delta, "escrowed": escrowed_delta}


def get_supply(conn, batch_id: str) -> dict:
    result = conn.execute(
        conn.text(
            "SELECT "
            "COALESCE(SUM(tradable_amount), 0) AS tradable_supply, "
            "COALESCE(SUM(retired_amount), 0) AS retired_supply, "
            "COALESCE(SUM(escrowed_amount), 0) AS escrowed_supply "
            "FROM credit_balance WHERE credit_batch_id = :bid"
        ),
        {"bid": batch_id},
    ).mappings().first()
    return {
        "credit_batch_id": batch_id,
        "tradable_supply": float(result["tradable_supply"]),
        "retired_supply": float(result["retired_supply"]),
        "escrowed_supply": float(result["escrowed_supply"]),
    }
