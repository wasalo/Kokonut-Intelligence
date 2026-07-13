"""Credit Marketplace: sell orders, buy orders, escrow, fees."""

from __future__ import annotations

import json
from datetime import datetime, timezone
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
    disable_auto_retire: bool = False,
    allow_partial_fills: bool = True,
    expiration: str = None,
) -> dict:
    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    denom_check = conn.execute(
        conn.text("SELECT id FROM credit_allowed_denom WHERE denom = :d AND is_active = TRUE"),
        {"d": ask_denom},
    ).mappings().first()
    if not denom_check:
        raise ValueError(f"Denomination not allowed: {ask_denom}")

    escrowed = conn.execute(
        conn.text(
            "UPDATE credit_balance SET tradable_amount = tradable_amount - :qty, "
            "escrowed_amount = escrowed_amount + :qty, updated_at = NOW() "
            "WHERE credit_batch_id = :bid AND account_address = :seller "
            "AND tradable_amount >= :qty"
        ),
        {"qty": quantity, "bid": credit_batch_id, "seller": seller_address},
    )
    if escrowed.rowcount != 1:
        raise ValueError("Seller does not own enough tradable credits")

    result = conn.execute(
        conn.text(
            "INSERT INTO credit_sell_order "
            "(credit_batch_id, seller_address, quantity, ask_price, ask_denom, "
            "auto_retire, disable_auto_retire, allow_partial_fills, escrow_quantity, expiration) "
            "VALUES (:cbid, :seller, :qty, :price, :denom, "
            ":ar, :dar, :apf, :eq, :exp) "
            "RETURNING id"
        ),
        {
            "cbid": credit_batch_id, "seller": seller_address, "qty": quantity,
            "price": ask_price, "denom": ask_denom,
            "ar": auto_retire, "dar": disable_auto_retire,
            "apf": allow_partial_fills, "eq": quantity, "exp": expiration,
        },
    ).mappings().first()

    logger.info("Created sell order %s for %s credits at %s %s", result["id"], quantity, ask_price, ask_denom)
    return {"id": str(result["id"]), "quantity": quantity, "ask_price": ask_price}


def update_sell_order(
    conn,
    order_id: str,
    seller_address: str,
    new_quantity: float = None,
    new_ask_price: float = None,
    disable_auto_retire: bool = None,
    new_expiration: str = None,
) -> dict:
    row = conn.execute(conn.text("SELECT * FROM credit_sell_order WHERE id = :oid FOR UPDATE"),
                       {"oid": order_id}).mappings().first()
    order = dict(row) if row else None
    if not order:
        raise ValueError(f"Order not found: {order_id}")
    if order["seller_address"] != seller_address:
        raise ValueError("Only the seller can update an order")
    if order["status"] != "active":
        raise ValueError(f"Order is not active: {order['status']}")

    updates = {}
    if new_quantity is not None:
        current_escrow = float(order["escrow_quantity"])
        if new_quantity > current_escrow:
            additional = new_quantity - current_escrow
            moved = conn.execute(
                conn.text("UPDATE credit_balance SET tradable_amount = tradable_amount - :qty, "
                          "escrowed_amount = escrowed_amount + :qty, updated_at = NOW() "
                          "WHERE credit_batch_id = :bid AND account_address = :seller "
                          "AND tradable_amount >= :qty"),
                {"qty": additional, "bid": order["credit_batch_id"], "seller": seller_address},
            )
            if moved.rowcount != 1:
                raise ValueError("Seller does not own enough tradable credits")
        elif new_quantity < current_escrow:
            returned = current_escrow - new_quantity
            moved = conn.execute(
                conn.text("UPDATE credit_balance SET tradable_amount = tradable_amount + :qty, "
                          "escrowed_amount = escrowed_amount - :qty, updated_at = NOW() "
                          "WHERE credit_batch_id = :bid AND account_address = :seller "
                          "AND escrowed_amount >= :qty"),
                {"qty": returned, "bid": order["credit_batch_id"], "seller": seller_address},
            )
            if moved.rowcount != 1:
                raise ValueError("Seller escrow is inconsistent")
        updates["quantity"] = new_quantity
        updates["escrow_quantity"] = new_quantity

    if new_ask_price is not None:
        updates["ask_price"] = new_ask_price

    if disable_auto_retire is not None:
        updates["disable_auto_retire"] = disable_auto_retire

    if new_expiration is not None:
        updates["expiration"] = new_expiration

    if not updates:
        raise ValueError("No fields to update")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["oid"] = order_id
    conn.execute(
        conn.text(f"UPDATE credit_sell_order SET {set_clause}, updated_at = NOW() WHERE id = :oid"),
        updates,
    )
    return {"id": order_id, "updated_fields": list(updates.keys())}


def get_sell_order(conn, order_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM credit_sell_order WHERE id = :oid"),
        {"oid": order_id},
    ).mappings().first()
    return dict(result) if result else None


def list_sell_orders(conn, credit_batch_id: str = None, seller_address: str = None,
                     status: str = None, active_only: bool = True) -> list[dict]:
    conditions = []
    params: dict[str, Any] = {}
    if active_only:
        conditions.append("status = 'active'")
    elif status:
        conditions.append("status = :s")
        params["s"] = status
    if credit_batch_id:
        conditions.append("credit_batch_id = :cbid")
        params["cbid"] = credit_batch_id
    if seller_address:
        conditions.append("seller_address = :seller")
        params["seller"] = seller_address
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    result = conn.execute(
        conn.text(f"SELECT * FROM credit_sell_order {where} ORDER BY created_at DESC"),
        params,
    )
    return [dict(r) for r in result.mappings()]


def cancel_sell_order(conn, order_id: str, seller_address: str) -> dict:
    row = conn.execute(conn.text("SELECT * FROM credit_sell_order WHERE id = :oid FOR UPDATE"),
                       {"oid": order_id}).mappings().first()
    order = dict(row) if row else None
    if not order:
        raise ValueError(f"Order not found: {order_id}")
    if order["seller_address"] != seller_address:
        raise ValueError("Only the seller can cancel an order")
    if order["status"] != "active":
        raise ValueError(f"Order is not active: {order['status']}")

    returned = conn.execute(
        conn.text(
            "UPDATE credit_balance SET tradable_amount = tradable_amount + :qty, "
            "escrowed_amount = escrowed_amount - :qty, updated_at = NOW() "
            "WHERE credit_batch_id = :bid AND account_address = :seller "
            "AND escrowed_amount >= :qty"
        ),
        {"qty": order["escrow_quantity"], "bid": order["credit_batch_id"], "seller": seller_address},
    )
    if returned.rowcount != 1:
        raise ValueError("Seller escrow is inconsistent")

    conn.execute(
        conn.text("UPDATE credit_sell_order SET status = 'cancelled', escrow_quantity = 0, updated_at = NOW() WHERE id = :oid"),
        {"oid": order_id},
    )

    logger.info("Cancelled sell order %s", order_id)
    return {"id": order_id, "status": "cancelled"}


def expire_sell_orders(conn) -> int:
    expired = conn.execute(
        conn.text(
            "SELECT id, credit_batch_id, seller_address, escrow_quantity FROM credit_sell_order "
            "WHERE status = 'active' AND expiration IS NOT NULL AND expiration < NOW() FOR UPDATE"
        ),
    ).mappings().all()
    for order in expired:
        moved = conn.execute(conn.text(
            "UPDATE credit_balance SET tradable_amount = tradable_amount + :qty, "
            "escrowed_amount = escrowed_amount - :qty, updated_at = NOW() "
            "WHERE credit_batch_id = :bid AND account_address = :seller AND escrowed_amount >= :qty"),
            {"qty": order["escrow_quantity"], "bid": order["credit_batch_id"],
             "seller": order["seller_address"]})
        if moved.rowcount != 1:
            raise ValueError(f"Seller escrow is inconsistent for order {order['id']}")
        conn.execute(conn.text("UPDATE credit_sell_order SET status = 'expired', escrow_quantity = 0, "
                               "updated_at = NOW() WHERE id = :oid"), {"oid": order["id"]})
    if expired:
        logger.info("Expired %d sell orders", len(expired))
    return len(expired)


def create_buy_order(
    conn,
    sell_order_id: str,
    buyer_address: str,
    quantity: float,
    auto_retire: bool = False,
    disable_auto_retire: bool = False,
    retirement_jurisdiction: str = None,
    retirement_reason: str = None,
    max_fee_amount: float = None,
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

    if sell_order.get("disable_auto_retire") and disable_auto_retire:
        pass
    elif not sell_order.get("disable_auto_retire") and not disable_auto_retire:
        auto_retire = True
    elif sell_order.get("disable_auto_retire") and not disable_auto_retire:
        pass
    elif not sell_order.get("disable_auto_retire") and disable_auto_retire:
        raise ValueError("Cannot disable auto-retire when sell order has auto-retire enabled")

    total_price = (quantity / sell_order["quantity"]) * float(sell_order["ask_price"])

    fee_params = _get_fee_params(conn)
    buyer_fee = total_price * float(fee_params.get("buyer_fee", 0))
    if max_fee_amount is not None and buyer_fee > max_fee_amount:
        raise ValueError(f"Buyer fee {buyer_fee} exceeds max_fee_amount {max_fee_amount}")

    result = conn.execute(
        conn.text(
            "INSERT INTO credit_buy_order "
            "(sell_order_id, buyer_address, quantity, total_price, price_denom, "
            "auto_retire, disable_auto_retire, retirement_jurisdiction, retirement_reason, max_fee_amount) "
            "VALUES (:soid, :buyer, :qty, :tp, :denom, "
            ":ar, :dar, :rj, :rr, :mfa) "
            "RETURNING id"
        ),
        {
            "soid": sell_order_id, "buyer": buyer_address, "qty": quantity,
            "tp": total_price, "denom": sell_order["ask_denom"],
            "ar": auto_retire, "dar": disable_auto_retire,
            "rj": retirement_jurisdiction, "rr": retirement_reason,
            "mfa": max_fee_amount,
        },
    ).mappings().first()

    logger.info("Created buy order %s for %s credits", result["id"], quantity)
    return {"id": str(result["id"]), "quantity": quantity, "total_price": total_price,
            "buyer_fee": buyer_fee}


def get_buy_order(conn, order_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM credit_buy_order WHERE id = :oid"),
        {"oid": order_id},
    ).mappings().first()
    return dict(result) if result else None


def execute_buy_order(conn, buy_order_id: str) -> dict:
    row = conn.execute(conn.text("SELECT * FROM credit_buy_order WHERE id = :oid FOR UPDATE"),
                       {"oid": buy_order_id}).mappings().first()
    buy_order = dict(row) if row else None
    if not buy_order:
        raise ValueError(f"Buy order not found: {buy_order_id}")
    if buy_order["status"] != "pending":
        raise ValueError(f"Buy order is not pending: {buy_order['status']}")

    row = conn.execute(conn.text("SELECT * FROM credit_sell_order WHERE id = :oid FOR UPDATE"),
                       {"oid": buy_order["sell_order_id"]}).mappings().first()
    sell_order = dict(row) if row else None
    if not sell_order:
        raise ValueError("Sell order not found")
    if sell_order["status"] != "active" or float(sell_order["escrow_quantity"]) < float(buy_order["quantity"]):
        raise ValueError("Sell order no longer has sufficient active escrow")

    quantity = float(buy_order["quantity"])
    seller_balance = conn.execute(conn.text(
        "UPDATE credit_balance SET escrowed_amount = escrowed_amount - :qty, updated_at = NOW() "
        "WHERE credit_batch_id = :bid AND account_address = :seller AND escrowed_amount >= :qty"),
        {"qty": quantity, "bid": sell_order["credit_batch_id"],
         "seller": sell_order["seller_address"]})
    if seller_balance.rowcount != 1:
        raise ValueError("Seller escrow is inconsistent")

    from services.credit_class.balance import upsert_balance
    if buy_order["auto_retire"]:
        upsert_balance(conn, sell_order["credit_batch_id"], buy_order["buyer_address"],
                       retired_delta=quantity)
        retired = conn.execute(conn.text(
            "UPDATE credit_batch SET retired_quantity = retired_quantity + :qty, updated_at = NOW() "
            "WHERE id = :bid AND issued_quantity - retired_quantity - cancelled_quantity >= :qty"),
            {"qty": quantity, "bid": sell_order["credit_batch_id"]})
        if retired.rowcount != 1:
            raise ValueError("Batch does not have enough issued credits to retire")
    else:
        upsert_balance(conn, sell_order["credit_batch_id"], buy_order["buyer_address"],
                       tradable_delta=quantity)

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


def _get_fee_params(conn) -> dict:
    buyer_result = conn.execute(
        conn.text("SELECT param_value FROM ecocredit_params WHERE param_key = 'marketplace_buyer_fee'")
    ).mappings().first()
    seller_result = conn.execute(
        conn.text("SELECT param_value FROM ecocredit_params WHERE param_key = 'marketplace_seller_fee'")
    ).mappings().first()
    return {
        "buyer_fee": float(buyer_result["param_value"]) if buyer_result else 0.03,
        "seller_fee": float(seller_result["param_value"]) if seller_result else 0.03,
    }


def get_fee_params(conn) -> dict:
    return _get_fee_params(conn)


def set_fee_params(conn, buyer_fee: float = None, seller_fee: float = None) -> dict:
    if buyer_fee is not None:
        conn.execute(
            conn.text(
                "INSERT INTO ecocredit_params (param_key, param_value, description) "
                "VALUES ('marketplace_buyer_fee', :val, 'Buyer percentage fee') "
                "ON CONFLICT (param_key) DO UPDATE SET param_value = :val, updated_at = NOW()"
            ),
            {"val": str(buyer_fee)},
        )
    if seller_fee is not None:
        conn.execute(
            conn.text(
                "INSERT INTO ecocredit_params (param_key, param_value, description) "
                "VALUES ('marketplace_seller_fee', :val, 'Seller percentage fee') "
                "ON CONFLICT (param_key) DO UPDATE SET param_value = :val, updated_at = NOW()"
            ),
            {"val": str(seller_fee)},
        )
    return _get_fee_params(conn)


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


def remove_allowed_denom(conn, denom: str) -> bool:
    result = conn.execute(
        conn.text("UPDATE credit_allowed_denom SET is_active = FALSE WHERE denom = :denom"),
        {"denom": denom},
    )
    return result.rowcount > 0
