"""Credit Basket: deposit credits → receive fungible basket tokens."""

from __future__ import annotations

import json
import math
from typing import Any

from services.common.logging import get_logger

logger = get_logger("credit_class.basket")

VALID_BASKET_STATUSES = {"active", "paused", "deprecated"}
VALID_DEPOSIT_STATUSES = {"deposited", "withdrawn", "cancelled"}

SI_PREFIX_MAP = {0: "", 1: "d", 2: "c", 3: "m", 6: "u", 9: "n", 12: "p", 15: "f", 18: "a", 21: "z", 24: "y"}


def _compute_basket_denom(name: str, credit_type_abbrev: str, exponent: int) -> str:
    prefix = SI_PREFIX_MAP.get(exponent, "u")
    return f"eco.{prefix}{credit_type_abbrev}.{name}"


def _compute_token_amount(quantity: float, exponent: int) -> float:
    return quantity * (10 ** exponent)


def _compute_credit_amount(token_amount: float, exponent: int) -> float:
    return token_amount / (10 ** exponent)


def create_basket(
    conn,
    name: str,
    token_denom: str = None,
    description: str = None,
    credit_type_id: str = None,
    credit_type_abbrev: str = None,
    credit_class_ids: list[str] = None,
    min_start_date: str = None,
    max_start_date: str = None,
    min_start_year: int = None,
    disable_auto_retire: bool = False,
    curator_address: str = None,
    exponent: int = 6,
    chain: str = "celo",
    metadata: dict = None,
) -> dict:
    if not token_denom and credit_type_abbrev:
        token_denom = _compute_basket_denom(name, credit_type_abbrev, exponent)

    result = conn.execute(
        conn.text(
            "INSERT INTO credit_basket "
            "(name, description, credit_type_id, credit_class_ids, "
            "min_start_date, max_start_date, min_start_year, "
            "token_denom, chain, disable_auto_retire, curator_address, "
            "basket_denom, exponent, metadata) "
            "VALUES (:name, :desc, :ctid, :ccids, "
            ":msd, :xsd, :msy, "
            ":td, :chain, :dar, :ca, :bd, :exp, :metadata) "
            "RETURNING id"
        ),
        {
            "name": name, "desc": description, "ctid": credit_type_id,
            "ccids": credit_class_ids, "msd": min_start_date, "xsd": max_start_date,
            "msy": min_start_year, "td": token_denom, "chain": chain,
            "dar": disable_auto_retire, "ca": curator_address,
            "bd": token_denom, "exp": exponent,
            "metadata": json.dumps(metadata) if metadata else "{}",
        },
    )
    record = result.mappings().first()
    logger.info("Created credit_basket %s: %s (denom=%s)", record["id"], name, token_denom)
    return {"id": str(record["id"]), "name": name, "basket_denom": token_denom}


def get_basket(conn, basket_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM credit_basket WHERE id = :bid"),
        {"bid": basket_id},
    ).mappings().first()
    return dict(result) if result else None


def get_basket_info(conn, basket_id: str) -> dict | None:
    basket = get_basket(conn, basket_id)
    if not basket:
        return None

    classes = []
    if basket.get("credit_class_ids"):
        result = conn.execute(
            conn.text("SELECT id, name, credit_type FROM credit_class WHERE id = ANY(:ids)"),
            {"ids": basket["credit_class_ids"]},
        )
        classes = [dict(r) for r in result.mappings()]

    basket["classes"] = classes
    return basket


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
    token_amount: float = None,
    deposit_tx_hash: str = None,
    chain: str = "celo",
) -> dict:
    basket = get_basket(conn, basket_id)
    if not basket:
        raise ValueError(f"Basket not found: {basket_id}")
    if basket["status"] != "active":
        raise ValueError(f"Basket is not active: {basket['status']}")

    exponent = basket.get("exponent", 6)
    expected_token_amount = _compute_token_amount(quantity, exponent)
    if token_amount is None:
        token_amount = expected_token_amount
    elif not math.isclose(token_amount, expected_token_amount, rel_tol=0, abs_tol=1e-8):
        raise ValueError("Token amount must match the basket exponent")

    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    batch = conn.execute(
        conn.text("SELECT vintage_year FROM credit_batch WHERE id = :bid"),
        {"bid": credit_batch_id},
    ).mappings().first()
    if not batch:
        raise ValueError(f"Batch not found: {credit_batch_id}")
    batch_start_date = f"{batch['vintage_year']}-01-01"

    if basket.get("min_start_year") and int(batch["vintage_year"]) < int(basket["min_start_year"]):
        raise ValueError("Batch vintage is earlier than basket criteria")
    if basket.get("min_start_date") and str(batch_start_date) < str(basket["min_start_date"]):
        raise ValueError("Batch vintage is earlier than basket criteria")
    if basket.get("max_start_date") and str(batch_start_date) > str(basket["max_start_date"]):
        raise ValueError("Batch vintage is later than basket criteria")

    escrowed = conn.execute(
        conn.text(
            "UPDATE credit_balance SET tradable_amount = tradable_amount - :qty, "
            "escrowed_amount = escrowed_amount + :qty, updated_at = NOW() "
            "WHERE credit_batch_id = :bid AND account_address = :addr AND tradable_amount >= :qty"
        ),
        {"qty": quantity, "bid": credit_batch_id, "addr": depositor_address},
    )
    if escrowed.rowcount != 1:
        raise ValueError("Depositor does not own enough tradable credits")

    result = conn.execute(
        conn.text(
            "INSERT INTO credit_basket_deposit "
            "(basket_id, credit_batch_id, depositor_address, quantity, token_amount, "
            "batch_start_date, deposit_tx_hash, chain) "
            "VALUES (:bid, :cbid, :addr, :qty, :ta, :bsd, :txh, :chain) "
            "RETURNING id"
        ),
        {
            "bid": basket_id, "cbid": credit_batch_id, "addr": depositor_address,
            "qty": quantity, "ta": token_amount, "bsd": batch_start_date,
            "txh": deposit_tx_hash, "chain": chain,
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

    logger.info("Deposited %s credits into basket %s (tokens=%s)", quantity, basket_id, token_amount)
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


def withdraw_from_basket(
    conn,
    basket_id: str,
    holder_address: str,
    quantity: float,
    retire_on_take: bool = False,
    retirement_jurisdiction: str = None,
    retirement_reason: str = None,
) -> dict:
    basket = get_basket(conn, basket_id)
    if not basket:
        raise ValueError(f"Basket not found: {basket_id}")
    if basket["status"] != "active":
        raise ValueError(f"Basket is not active: {basket['status']}")

    token_balance = conn.execute(conn.text(
        "SELECT * FROM credit_basket_token WHERE basket_id = :bid AND holder_address = :addr FOR UPDATE"),
        {"bid": basket_id, "addr": holder_address}).mappings().first()
    if float(token_balance.get("token_amount", 0)) < quantity:
        raise ValueError(f"Insufficient basket tokens: {token_balance.get('token_amount', 0)} < {quantity}")

    disable_auto_retire = basket.get("disable_auto_retire", False)
    exponent = basket.get("exponent", 6)
    credit_amount = _compute_credit_amount(quantity, exponent)

    if not disable_auto_retire:
        retire_on_take = True

    deposits = conn.execute(
        conn.text(
            "SELECT * FROM credit_basket_deposit "
            "WHERE basket_id = :bid AND status = 'deposited' "
            "ORDER BY batch_start_date ASC, deposited_at ASC FOR UPDATE"
        ),
        {"bid": basket_id},
    ).mappings().all()
    if sum(float(deposit["token_amount"]) for deposit in deposits) < quantity:
        raise ValueError("Basket does not have enough escrowed credits")

    remaining = quantity
    taken_credits = []
    for deposit in deposits:
        if remaining <= 0:
            break
        dep_tokens = float(deposit["token_amount"])
        take_tokens = min(dep_tokens, remaining)

        new_dep_tokens = dep_tokens - take_tokens
        new_dep_quantity = float(deposit["quantity"]) - _compute_credit_amount(take_tokens, exponent)
        new_status = "withdrawn" if new_dep_tokens <= 0 else "deposited"

        conn.execute(
            conn.text(
                "UPDATE credit_basket_deposit SET "
                "token_amount = :ta, quantity = :qty, status = :s "
                "WHERE id = :did"
            ),
            {"ta": max(new_dep_tokens, 0), "qty": max(new_dep_quantity, 0),
             "s": new_status, "did": str(deposit["id"])},
        )

        credit_quantity = _compute_credit_amount(take_tokens, exponent)
        moved = conn.execute(conn.text(
            "UPDATE credit_balance SET escrowed_amount = escrowed_amount - :qty, updated_at = NOW() "
            "WHERE credit_batch_id = :bid AND account_address = :addr AND escrowed_amount >= :qty"),
            {"qty": credit_quantity, "bid": deposit["credit_batch_id"],
             "addr": deposit["depositor_address"]})
        if moved.rowcount != 1:
            raise ValueError("Basket deposit escrow is inconsistent")

        from services.credit_class.balance import upsert_balance
        if retire_on_take:
            upsert_balance(conn, str(deposit["credit_batch_id"]), holder_address,
                           retired_delta=credit_quantity)
            retired = conn.execute(conn.text(
                "UPDATE credit_batch SET retired_quantity = retired_quantity + :qty, updated_at = NOW() "
                "WHERE id = :bid AND issued_quantity - retired_quantity - cancelled_quantity >= :qty"),
                {"qty": credit_quantity, "bid": deposit["credit_batch_id"]})
            if retired.rowcount != 1:
                raise ValueError("Batch does not have enough issued credits to retire")
        else:
            upsert_balance(conn, str(deposit["credit_batch_id"]), holder_address,
                           tradable_delta=credit_quantity)

        taken_credits.append({
            "batch_id": str(deposit["credit_batch_id"]),
            "quantity": credit_quantity,
            "retired": retire_on_take,
        })
        remaining -= take_tokens

    debited = conn.execute(
        conn.text(
            "UPDATE credit_basket_token SET "
            "token_amount = token_amount - :qty, last_updated_at = NOW() "
            "WHERE basket_id = :bid AND holder_address = :addr AND token_amount >= :qty"
        ),
        {"qty": quantity, "bid": basket_id, "addr": holder_address},
    )
    if debited.rowcount != 1:
        raise ValueError("Insufficient basket tokens")

    logger.info("Withdrew %s basket tokens from %s (credits=%s, retire=%s)",
                quantity, holder_address, credit_amount, retire_on_take)
    return {
        "basket_id": basket_id,
        "holder_address": holder_address,
        "token_amount_withdrawn": quantity,
        "credit_amount": credit_amount,
        "retire_on_take": retire_on_take,
        "credits": taken_credits,
    }


def cancel_deposit(conn, deposit_id: str, depositor_address: str) -> dict:
    row = conn.execute(conn.text(
        "SELECT * FROM credit_basket_deposit WHERE id = :did FOR UPDATE"),
        {"did": deposit_id}).mappings().first()
    if not row:
        raise ValueError(f"Deposit not found: {deposit_id}")
    deposit = dict(row)
    if deposit["depositor_address"] != depositor_address:
        raise ValueError("Only the depositor can cancel a deposit")
    if deposit["status"] != "deposited":
        raise ValueError(f"Deposit is not active: {deposit['status']}")

    token = conn.execute(conn.text(
        "UPDATE credit_basket_token SET token_amount = token_amount - :tokens, last_updated_at = NOW() "
        "WHERE basket_id = :bid AND holder_address = :addr AND token_amount >= :tokens"),
        {"tokens": deposit["token_amount"], "bid": deposit["basket_id"],
         "addr": depositor_address})
    if token.rowcount != 1:
        raise ValueError("Depositor no longer owns the basket tokens")
    moved = conn.execute(conn.text(
        "UPDATE credit_balance SET tradable_amount = tradable_amount + :qty, "
        "escrowed_amount = escrowed_amount - :qty, updated_at = NOW() "
        "WHERE credit_batch_id = :bid AND account_address = :addr AND escrowed_amount >= :qty"),
        {"qty": deposit["quantity"], "bid": deposit["credit_batch_id"],
         "addr": depositor_address})
    if moved.rowcount != 1:
        raise ValueError("Basket deposit escrow is inconsistent")
    conn.execute(conn.text(
        "UPDATE credit_basket_deposit SET status = 'cancelled', quantity = 0, token_amount = 0 "
        "WHERE id = :did"), {"did": deposit_id})
    return {"id": deposit_id, "status": "cancelled"}


def update_curator(conn, basket_id: str, current_curator: str, new_curator: str) -> dict:
    basket = get_basket(conn, basket_id)
    if not basket:
        raise ValueError(f"Basket not found: {basket_id}")
    if basket.get("curator_address") != current_curator:
        raise ValueError("Only the current curator can update the curator")

    conn.execute(
        conn.text("UPDATE credit_basket SET curator_address = :nc, updated_at = NOW() WHERE id = :bid"),
        {"nc": new_curator, "bid": basket_id},
    )
    logger.info("Updated curator for basket %s: %s → %s", basket_id, current_curator, new_curator)
    return {"basket_id": basket_id, "old_curator": current_curator, "new_curator": new_curator}


def update_date_criteria(
    conn,
    basket_id: str,
    min_start_date: str = None,
    max_start_date: str = None,
    min_start_year: int = None,
) -> dict:
    basket = get_basket(conn, basket_id)
    if not basket:
        raise ValueError(f"Basket not found: {basket_id}")

    conn.execute(
        conn.text(
            "UPDATE credit_basket SET "
            "min_start_date = :msd, max_start_date = :xsd, min_start_year = :msy, "
            "updated_at = NOW() WHERE id = :bid"
        ),
        {"msd": min_start_date, "xsd": max_start_date, "msy": min_start_year, "bid": basket_id},
    )
    logger.info("Updated date criteria for basket %s", basket_id)
    return {"basket_id": basket_id}


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


def get_basket_balances(conn, basket_id: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT cbd.*, b.batch_code, b.unit "
            "FROM credit_basket_deposit cbd "
            "JOIN credit_batch b ON b.id = cbd.credit_batch_id "
            "WHERE cbd.basket_id = :bid AND cbd.status = 'deposited' "
            "ORDER BY cbd.batch_start_date ASC, cbd.deposited_at ASC"
        ),
        {"bid": basket_id},
    )
    return [dict(r) for r in result.mappings()]


def get_basket_balance_for_batch(conn, basket_id: str, batch_id: str) -> dict:
    result = conn.execute(
        conn.text(
            "SELECT COALESCE(SUM(quantity), 0) AS balance "
            "FROM credit_basket_deposit "
            "WHERE basket_id = :bid AND credit_batch_id = :bhid AND status = 'deposited'"
        ),
        {"bid": basket_id, "bhid": batch_id},
    ).mappings().first()
    return {
        "basket_id": basket_id,
        "batch_id": batch_id,
        "balance": float(result["balance"]),
    }
