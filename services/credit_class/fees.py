"""Marketplace fee collection and distribution."""

from __future__ import annotations

import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger("credit_class.fees")


def collect_fee(
    conn,
    transaction_type: str,
    transaction_id: str,
    buyer_fee: float = 0,
    seller_fee: float = 0,
    fee_denom: str = "cusd",
) -> dict:
    total_fee = buyer_fee + seller_fee

    fee_params = _get_fee_pool_address(conn)

    result = conn.execute(
        conn.text(
            "INSERT INTO marketplace_fee "
            "(transaction_type, transaction_id, buyer_fee, seller_fee, total_fee, "
            "fee_denom, fee_pool_address) "
            "VALUES (:tt, :ti, :bf, :sf, :tf, :fd, :fpa) "
            "RETURNING id"
        ),
        {
            "tt": transaction_type, "ti": transaction_id,
            "bf": buyer_fee, "sf": seller_fee, "tf": total_fee,
            "fd": fee_denom, "fpa": fee_params.get("fee_pool_address"),
        },
    ).mappings().first()

    logger.info("Collected fee for %s %s: %s %s", transaction_type, transaction_id, total_fee, fee_denom)
    return {"id": str(result["id"]), "total_fee": total_fee, "fee_denom": fee_denom}


def distribute_fee(
    conn,
    fee_id: str,
    recipient_address: str,
    amount: float,
    denom: str,
    tx_hash: str = None,
) -> dict:
    fee = conn.execute(
        conn.text("SELECT * FROM marketplace_fee WHERE id = :fid"),
        {"fid": fee_id},
    ).mappings().first()
    if not fee:
        raise ValueError(f"Fee not found: {fee_id}")

    result = conn.execute(
        conn.text(
            "INSERT INTO marketplace_fee_distribution "
            "(fee_id, recipient_address, amount, denom, tx_hash) "
            "VALUES (:fid, :ra, :amt, :denom, :txh) "
            "RETURNING id"
        ),
        {"fid": fee_id, "ra": recipient_address, "amt": amount, "denom": denom, "txh": tx_hash},
    ).mappings().first()

    conn.execute(
        conn.text(
            "UPDATE marketplace_fee SET status = 'distributed', distributed_at = NOW() WHERE id = :fid"
        ),
        {"fid": fee_id},
    )

    logger.info("Distributed fee %s: %s %s to %s", fee_id, amount, denom, recipient_address)
    return {"id": str(result["id"]), "amount": amount, "denom": denom}


def get_fee_params(conn) -> dict:
    buyer_result = conn.execute(
        conn.text("SELECT param_value FROM ecocredit_params WHERE param_key = 'marketplace_buyer_fee'")
    ).mappings().first()
    seller_result = conn.execute(
        conn.text("SELECT param_value FROM ecocredit_params WHERE param_key = 'marketplace_seller_fee'")
    ).mappings().first()
    pool_result = conn.execute(
        conn.text("SELECT param_value FROM ecocredit_params WHERE param_key = 'marketplace_fee_pool_address'")
    ).mappings().first()

    return {
        "buyer_fee": float(buyer_result["param_value"]) if buyer_result else 0.03,
        "seller_fee": float(seller_result["param_value"]) if seller_result else 0.03,
        "fee_pool_address": pool_result["param_value"] if pool_result else None,
    }


def _get_fee_pool_address(conn) -> dict:
    return get_fee_params(conn)


def list_fees(conn, transaction_type: str = None, status: str = None) -> list[dict]:
    conditions = []
    params: dict[str, Any] = {}
    if transaction_type:
        conditions.append("transaction_type = :tt")
        params["tt"] = transaction_type
    if status:
        conditions.append("status = :s")
        params["s"] = status
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    result = conn.execute(
        conn.text(f"SELECT * FROM marketplace_fee {where} ORDER BY created_at DESC"),
        params,
    )
    return [dict(r) for r in result.mappings()]


def get_pending_fees(conn) -> list[dict]:
    return list_fees(conn, status="pending")
