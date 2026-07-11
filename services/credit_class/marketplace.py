"""Credit Marketplace: sell orders, buy orders, escrow."""

from __future__ import annotations

import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger("credit_class.marketplace")

VALID_SELL_STATUSES = {"active", "filled", "cancelled", "expired"}
VALID_BUY_STATUSES = {"pending", "completed", "cancelled", "failed"}


def create_sell_order(
    conn,
    credit_batch_id: str,
    seller_address: str,
    quantity: float,
    ask_price: float,
    ask_denom: str,
    auto_retire: bool = False,
    allow_partial_fills: bool = True,
) -> dict:
    batch = conn.execute(
        conn.text("SELECT available_quantity FROM credit_batch WHERE id = :bid"),
        {"bid": credit_batch_id},
    ).mappings().first()
    if not batch:
        raise ValueError(f"Batch not found: {credit_batch_id}")
    if float(batch["available_quantity"]) < quantity:
        raise ValueError(f"Insufficient available quantity: {batch['available_quantity']} < {quantity}")

    denom_check = conn.execute(
        conn.text("SELECT id FROM credit_allowed_denom WHERE denom = :d AND is_active = TRUE"),
        {"d": ask_denom},
    ).mappings().first()
    if not denom_check:
        raise ValueError(f"Denomination not allowed: {ask_denom}")

    conn.execute(
        conn.text(
            "UPDATE credit_batch SET retired_quantity = retired_quantity + :qty, updated_at = NOW() "
            "WHERE id = :bid"
        ),
        {"qty": quantity, "bid": credit_batch_id},
    )

    result = conn.execute(
        conn.text(
            "INSERT INTO credit_sell_order "
            "(credit_batch_id, seller_address, quantity, ask_price, ask_denom, "
            "auto_retire, allow_partial_fills, escrow_quantity) "
            "VALUES (:cbid, :seller, :qty, :price, :denom, "
            ":ar, :apf, :eq) "
            "RETURNING id"
        ),
        {
            "cbid": credit_batch_id, "seller": seller_address, "qty": quantity,
            "price": ask_price, "denom": ask_denom,
            "ar": auto_retire, "apf": allow_partial_fills, "eq": quantity,
        },
    ).mappings().first()

    logger.info("Created sell order %s for %s credits at %s %s", result["id"], quantity, ask_price, ask_denom)
    return {"id": str(result["id"]), "quantity": quantity, "ask_price": ask_price}


def get_sell_order(conn, order_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM credit_sell_order WHERE id = :oid"),
        {"oid": order_id},
    ).mappings().first()
    return dict(result) if result else None


def list_sell_orders(conn, credit_batch_id: str = None, status: str = None) -> list[dict]:
    conditions = ["status = 'active'"]
    params: dict[str, Any] = {}
    if credit_batch_id:
        conditions.append("credit_batch_id = :cbid")
        params["cbid"] = credit_batch_id
    if status:
        conditions[0] = "status = :s"
        params["s"] = status
    where = "WHERE " + " AND ".join(conditions)
    result = conn.execute(
        conn.text(f"SELECT * FROM credit_sell_order {where} ORDER BY created_at DESC"),
        params,
    )
    return [dict(r) for r in result.mappings()]


def cancel_sell_order(conn, order_id: str, seller_address: str) -> dict:
    order = get_sell_order(conn, order_id)
    if not order:
        raise ValueError(f"Order not found: {order_id}")
    if order["seller_address"] != seller_address:
        raise ValueError("Only the seller can cancel an order")
    if order["status"] != "active":
        raise ValueError(f"Order is not active: {order['status']}")

    conn.execute(
        conn.text(
            "UPDATE credit_batch SET retired_quantity = retired_quantity - :qty, updated_at = NOW() "
            "WHERE id = :bid"
        ),
        {"qty": order["escrow_quantity"], "bid": order["credit_batch_id"]},
    )

    conn.execute(
        conn.text("UPDATE credit_sell_order SET status = 'cancelled', escrow_quantity = 0, updated_at = NOW() WHERE id = :oid"),
        {"oid": order_id},
    )

    logger.info("Cancelled sell order %s", order_id)
    return {"id": order_id, "status": "cancelled"}


def create_buy_order(
    conn,
    sell_order_id: str,
    buyer_address: str,
    quantity: float,
    auto_retire: bool = False,
) -> dict:
    sell_order = get_sell_order(conn, sell_order_id)
    if not sell_order:
        raise ValueError(f"Sell order not found: {sell_order_id}")
    if sell_order["status"] != "active":
        raise ValueError(f"Sell order is not active: {sell_order['status']}")
    if not sell_order["allow_partial_fills"] and quantity != sell_order["quantity"]:
        raise ValueError("Partial fills not allowed; must buy full quantity")
    if quantity > sell_order["escrow_quantity"]:
        raise ValueError(f"Insufficient escrow: {sell_order['escrow_quantity']} < {quantity}")

    total_price = (quantity / sell_order["quantity"]) * float(sell_order["ask_price"])

    result = conn.execute(
        conn.text(
            "INSERT INTO credit_buy_order "
            "(sell_order_id, buyer_address, quantity, total_price, price_denom, auto_retire) "
            "VALUES (:soid, :buyer, :qty, :tp, :denom, :ar) "
            "RETURNING id"
        ),
        {
            "soid": sell_order_id, "buyer": buyer_address, "qty": quantity,
            "tp": total_price, "denom": sell_order["ask_denom"], "ar": auto_retire,
        },
    ).mappings().first()

    logger.info("Created buy order %s for %s credits", result["id"], quantity)
    return {"id": str(result["id"]), "quantity": quantity, "total_price": total_price}


def get_buy_order(conn, order_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM credit_buy_order WHERE id = :oid"),
        {"oid": order_id},
    ).mappings().first()
    return dict(result) if result else None


def execute_buy_order(conn, buy_order_id: str) -> dict:
    buy_order = get_buy_order(conn, buy_order_id)
    if not buy_order:
        raise ValueError(f"Buy order not found: {buy_order_id}")
    if buy_order["status"] != "pending":
        raise ValueError(f"Buy order is not pending: {buy_order['status']}")

    sell_order = get_sell_order(conn, buy_order["sell_order_id"])
    if not sell_order:
        raise ValueError("Sell order not found")

    new_escrow = float(sell_order["escrow_quantity"]) - float(buy_order["quantity"])
    new_status = "filled" if new_escrow <= 0 else "active"

    conn.execute(
        conn.text(
            "UPDATE credit_sell_order SET escrow_quantity = :eq, status = :s, updated_at = NOW() "
            "WHERE id = :sid"
        ),
        {"eq": max(new_escrow, 0), "s": new_status, "sid": sell_order["id"]},
    )

    conn.execute(
        conn.text(
            "UPDATE credit_buy_order SET status = 'completed', completed_at = NOW() WHERE id = :bid"
        ),
        {"bid": buy_order_id},
    )

    logger.info("Executed buy order %s", buy_order_id)
    return {"buy_order_id": buy_order_id, "status": "completed"}


def list_allowed_denoms(conn) -> list[dict]:
    result = conn.execute(
        conn.text("SELECT * FROM credit_allowed_denom WHERE is_active = TRUE ORDER BY denom")
    )
    return [dict(r) for r in result.mappings()]


def add_allowed_denom(conn, denom: str, chain: str = "celo",
                      contract_address: str = None, added_by: str = None) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO credit_allowed_denom (denom, chain, contract_address, added_by) "
            "VALUES (:denom, :chain, :ca, :ab) "
            "ON CONFLICT (denom) DO UPDATE SET is_active = TRUE "
            "RETURNING id"
        ),
        {"denom": denom, "chain": chain, "ca": contract_address, "ab": added_by},
    ).mappings().first()
    return {"id": str(result["id"]), "denom": denom}
