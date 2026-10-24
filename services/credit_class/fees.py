"""Marketplace fee collection and distribution."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from services.common.logging import get_logger

logger = get_logger("credit_class.fees")

_FEE_QUANTUM = Decimal("0.00000001")


def _fee_amount(value: Any, field: str, *, allow_zero: bool) -> Decimal:
    """Validate and normalize a marketplace amount to the database scale."""
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite amount")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{field} must be a finite amount") from None
    if not amount.is_finite() or amount < 0 or (not allow_zero and amount == 0):
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{field} must be finite and {qualifier}")
    if amount >= Decimal("10000000000"):
        raise ValueError(f"{field} exceeds the supported fee range")
    try:
        normalized = amount.quantize(_FEE_QUANTUM, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValueError(f"{field} is below the supported fee precision") from None
    if not allow_zero and normalized == 0:
        raise ValueError(f"{field} is below the supported fee precision")
    if normalized >= Decimal("10000000000"):
        raise ValueError(f"{field} exceeds the supported fee range")
    return normalized


def collect_fee(
    conn,
    transaction_type: str,
    transaction_id: str,
    buyer_fee: float = 0,
    seller_fee: float = 0,
    fee_denom: str = "cusd",
) -> dict:
    buyer_amount = _fee_amount(buyer_fee, "buyer_fee", allow_zero=True)
    seller_amount = _fee_amount(seller_fee, "seller_fee", allow_zero=True)
    if not isinstance(transaction_type, str) or not transaction_type.strip():
        raise ValueError("transaction_type is required")
    if not isinstance(transaction_id, str) or not transaction_id.strip():
        raise ValueError("transaction_id is required")
    if not isinstance(fee_denom, str) or not fee_denom.strip():
        raise ValueError("fee_denom is required")
    total_fee = buyer_amount + seller_amount

    fee_params = _get_fee_pool_address(conn)

    result = conn.execute(
        conn.text(
            "INSERT INTO marketplace_fee "
            "(transaction_type, transaction_id, buyer_fee, seller_fee, total_fee, "
            "fee_denom, fee_pool_address, status, distributed_at) "
            "VALUES (:tt, :ti, :bf, :sf, :tf, :fd, :fpa, "
            "CASE WHEN :tf = 0 THEN 'distributed' ELSE 'pending' END, "
            "CASE WHEN :tf = 0 THEN NOW() ELSE NULL END) "
            "RETURNING id"
        ),
        {
            "tt": transaction_type, "ti": transaction_id,
            "bf": buyer_amount, "sf": seller_amount, "tf": total_fee,
            "fd": fee_denom, "fpa": fee_params.get("fee_pool_address"),
        },
    ).mappings().first()

    logger.info("Collected fee for %s %s: %s %s", transaction_type, transaction_id, total_fee, fee_denom)
    return {"id": str(result["id"]), "total_fee": float(total_fee), "fee_denom": fee_denom}


def distribute_fee(
    conn,
    fee_id: str,
    recipient_address: str,
    amount: float,
    denom: str,
    tx_hash: str = None,
) -> dict:
    distribution_amount = _fee_amount(amount, "amount", allow_zero=False)
    if not isinstance(recipient_address, str) or not recipient_address.strip():
        raise ValueError("recipient_address is required")
    if not isinstance(denom, str) or not denom.strip():
        raise ValueError("denom is required")

    fee = conn.execute(
        conn.text("SELECT * FROM marketplace_fee WHERE id = :fid FOR UPDATE"),
        {"fid": fee_id},
    ).mappings().first()
    if not fee:
        raise ValueError(f"Fee not found: {fee_id}")
    if fee.get("status", "pending") != "pending":
        raise ValueError(f"Fee is not pending distribution: {fee.get('status')}")
    if denom != fee["fee_denom"]:
        raise ValueError(f"Distribution denomination must match fee denomination: {fee['fee_denom']}")

    total_fee = _fee_amount(fee["total_fee"], "total_fee", allow_zero=True)
    existing_distributed = conn.execute(
        conn.text(
            "SELECT COALESCE(SUM(amount), 0) AS total_distributed "
            "FROM marketplace_fee_distribution WHERE fee_id = :fid"
        ),
        {"fid": fee_id},
    ).mappings().first()
    previously_distributed = _fee_amount(
        existing_distributed["total_distributed"], "previously_distributed", allow_zero=True
    )

    if previously_distributed + distribution_amount > total_fee:
        raise ValueError(
            f"Over-distribution: {previously_distributed} + {distribution_amount} > {total_fee} total fee"
        )

    result = conn.execute(
        conn.text(
            "INSERT INTO marketplace_fee_distribution "
            "(fee_id, recipient_address, amount, denom, tx_hash) "
            "VALUES (:fid, :ra, :amt, :denom, :txh) "
            "RETURNING id"
        ),
        {
            "fid": fee_id, "ra": recipient_address, "amt": distribution_amount,
            "denom": denom, "txh": tx_hash,
        },
    ).mappings().first()

    fully_distributed = previously_distributed + distribution_amount == total_fee
    if fully_distributed:
        conn.execute(
            conn.text(
                "UPDATE marketplace_fee SET status = 'distributed', distributed_at = NOW() "
                "WHERE id = :fid AND status = 'pending'"
            ),
            {"fid": fee_id},
        )

    logger.info(
        "Distributed fee %s: %s %s to %s", fee_id, distribution_amount, denom, recipient_address
    )
    return {"id": str(result["id"]), "amount": float(distribution_amount), "denom": denom}


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
