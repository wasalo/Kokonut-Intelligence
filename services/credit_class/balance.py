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
            "JOIN credit_class cc ON cc.id = b.credit_class_id "
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
    if tradable_delta < 0 or retired_delta < 0 or escrowed_delta < 0:
        existing = conn.execute(
            conn.text(
                "SELECT id FROM credit_balance WHERE credit_batch_id = :bid "
                "AND account_address = :addr FOR UPDATE"
            ),
            {"bid": batch_id, "addr": account_address},
        ).mappings().first()
        if not existing:
            raise ValueError("Insufficient balance")

    result = conn.execute(
        conn.text(
            "INSERT INTO credit_balance "
            "(credit_batch_id, account_address, tradable_amount, retired_amount, escrowed_amount) "
            "VALUES (:bid, :addr, :td, :rd, :ed) "
            "ON CONFLICT (credit_batch_id, account_address) DO UPDATE SET "
            "tradable_amount = credit_balance.tradable_amount + EXCLUDED.tradable_amount, "
            "retired_amount = credit_balance.retired_amount + EXCLUDED.retired_amount, "
            "escrowed_amount = credit_balance.escrowed_amount + EXCLUDED.escrowed_amount, "
            "updated_at = NOW() "
            "WHERE credit_balance.tradable_amount + EXCLUDED.tradable_amount >= 0 "
            "AND credit_balance.retired_amount + EXCLUDED.retired_amount >= 0 "
            "AND credit_balance.escrowed_amount + EXCLUDED.escrowed_amount >= 0 "
            "RETURNING id, tradable_amount, retired_amount, escrowed_amount"
        ),
        {"bid": batch_id, "addr": account_address, "td": tradable_delta,
         "rd": retired_delta, "ed": escrowed_delta},
    ).mappings().first()
    if not result:
        raise ValueError("Insufficient balance")
    return {"id": str(result["id"]), "tradable": float(result["tradable_amount"]),
            "retired": float(result["retired_amount"]), "escrowed": float(result["escrowed_amount"])}


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
