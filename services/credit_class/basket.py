"""Credit Basket: deposit credits → receive fungible basket tokens."""

from __future__ import annotations

import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger("credit_class.basket")

VALID_BASKET_STATUSES = {"active", "paused", "deprecated"}
VALID_DEPOSIT_STATUSES = {"deposited", "withdrawn", "cancelled"}


def create_basket(
    conn,
    name: str,
    token_denom: str,
    description: str = None,
    credit_type_id: str = None,
    credit_class_ids: list[str] = None,
    min_start_date: str = None,
    max_start_date: str = None,
    min_start_year: int = None,
    chain: str = "celo",
    metadata: dict = None,
) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO credit_basket "
            "(name, description, credit_type_id, credit_class_ids, "
            "min_start_date, max_start_date, min_start_year, "
            "token_denom, chain, metadata) "
            "VALUES (:name, :desc, :ctid, :ccids, "
            ":msd, :xsd, :msy, "
            ":td, :chain, :metadata) "
            "RETURNING id"
        ),
        {
            "name": name, "desc": description, "ctid": credit_type_id,
            "ccids": credit_class_ids, "msd": min_start_date, "xsd": max_start_date,
            "msy": min_start_year, "td": token_denom, "chain": chain,
            "metadata": json.dumps(metadata) if metadata else "{}",
        },
    )
    record = result.mappings().first()
    logger.info("Created credit_basket %s: %s", record["id"], name)
    return {"id": str(record["id"]), "name": name}


def get_basket(conn, basket_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM credit_basket WHERE id = :bid"),
        {"bid": basket_id},
    ).mappings().first()
    return dict(result) if result else None


def list_baskets(conn, credit_type_id: str = None, status: str = None) -> list[dict]:
    conditions = []
    params: dict[str, Any] = {}
    if credit_type_id:
        conditions.append("credit_type_id = :ctid")
        params["ctid"] = credit_type_id
    if status:
        conditions.append("status = :s")
        params["s"] = status
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    result = conn.execute(
        conn.text(f"SELECT * FROM credit_basket {where} ORDER BY created_at DESC"),
        params,
    )
    return [dict(r) for r in result.mappings()]


def deposit_credits(
    conn,
    basket_id: str,
    credit_batch_id: str,
    depositor_address: str,
    quantity: float,
    token_amount: float,
    deposit_tx_hash: str = None,
    chain: str = "celo",
) -> dict:
    basket = get_basket(conn, basket_id)
    if not basket:
        raise ValueError(f"Basket not found: {basket_id}")
    if basket["status"] != "active":
        raise ValueError(f"Basket is not active: {basket['status']}")

    batch = conn.execute(
        conn.text("SELECT available_quantity FROM credit_batch WHERE id = :bid"),
        {"bid": credit_batch_id},
    ).mappings().first()
    if not batch:
        raise ValueError(f"Batch not found: {credit_batch_id}")
    if float(batch["available_quantity"]) < quantity:
        raise ValueError(f"Insufficient available quantity: {batch['available_quantity']} < {quantity}")

    conn.execute(
        conn.text(
            "UPDATE credit_batch SET retired_quantity = retired_quantity + :qty, updated_at = NOW() "
            "WHERE id = :bid"
        ),
        {"qty": quantity, "bid": credit_batch_id},
    )

    result = conn.execute(
        conn.text(
            "INSERT INTO credit_basket_deposit "
            "(basket_id, credit_batch_id, depositor_address, quantity, token_amount, "
            "deposit_tx_hash, chain) "
            "VALUES (:bid, :cbid, :addr, :qty, :ta, :txh, :chain) "
            "RETURNING id"
        ),
        {
            "bid": basket_id, "cbid": credit_batch_id, "addr": depositor_address,
            "qty": quantity, "ta": token_amount, "txh": deposit_tx_hash, "chain": chain,
        },
    ).mappings().first()

    conn.execute(
        conn.text(
            "INSERT INTO credit_basket_token (basket_id, holder_address, token_amount) "
            "VALUES (:bid, :addr, :ta) "
            "ON CONFLICT (basket_id, holder_address) DO UPDATE SET "
            "token_amount = credit_basket_token.token_amount + :ta, last_updated_at = NOW()"
        ),
        {"bid": basket_id, "addr": depositor_address, "ta": token_amount},
    )

    logger.info("Deposited %s credits into basket %s", quantity, basket_id)
    return {"id": str(result["id"]), "quantity": quantity, "token_amount": token_amount}


def get_token_balance(conn, basket_id: str, holder_address: str) -> dict:
    result = conn.execute(
        conn.text(
            "SELECT * FROM credit_basket_token WHERE basket_id = :bid AND holder_address = :addr"
        ),
        {"bid": basket_id, "addr": holder_address},
    ).mappings().first()
    if not result:
        return {"basket_id": basket_id, "holder_address": holder_address, "token_amount": 0}
    return dict(result)


def list_deposits(conn, basket_id: str = None, depositor_address: str = None) -> list[dict]:
    conditions = []
    params: dict[str, Any] = {}
    if basket_id:
        conditions.append("basket_id = :bid")
        params["bid"] = basket_id
    if depositor_address:
        conditions.append("depositor_address = :addr")
        params["addr"] = depositor_address
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    result = conn.execute(
        conn.text(f"SELECT * FROM credit_basket_deposit {where} ORDER BY deposited_at DESC"),
        params,
    )
    return [dict(r) for r in result.mappings()]
