"""Cross-chain bridge: send/receive credits across chains."""

from __future__ import annotations

import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger("credit_class.bridge")


def create_bridge_outbound(
    conn,
    credit_batch_id: str,
    sender_address: str,
    target_chain: str,
    recipient_address: str,
    quantity: float,
    metadata: dict = None,
) -> dict:
    batch = conn.execute(
        conn.text("SELECT available_quantity FROM credit_batch WHERE id = :bid"),
        {"bid": credit_batch_id},
    ).mappings().first()
    if not batch:
        raise ValueError(f"Batch not found: {credit_batch_id}")
    if float(batch["available_quantity"]) < quantity:
        raise ValueError(f"Insufficient available quantity: {batch['available_quantity']} < {quantity}")

    allowed_chains_raw = conn.execute(
        conn.text("SELECT param_value FROM ecocredit_params WHERE param_key = 'allowed_bridge_chains'")
    ).mappings().first()
    allowed_chains = ["celo", "gnosis"]
    if allowed_chains_raw and isinstance(allowed_chains_raw["param_value"], list):
        allowed_chains = allowed_chains_raw["param_value"]
    if target_chain not in allowed_chains:
        raise ValueError(f"Target chain not allowed: {target_chain}. Allowed: {allowed_chains}")

    result = conn.execute(
        conn.text(
            "INSERT INTO credit_bridge_transaction "
            "(direction, source_chain, target_chain, sender_address, recipient_address, "
            "credit_batch_id, quantity, metadata) "
            "VALUES ('outbound', 'kokonut', :target, :sender, :recipient, "
            ":bid, :qty, :meta) "
            "RETURNING id"
        ),
        {
            "target": target_chain, "sender": sender_address,
            "recipient": recipient_address, "bid": credit_batch_id,
            "qty": quantity, "meta": json.dumps(metadata) if metadata else "{}",
        },
    ).mappings().first()

    logger.info("Created outbound bridge tx %s: %s credits → %s", result["id"], quantity, target_chain)
    return {"id": str(result["id"]), "direction": "outbound", "target_chain": target_chain}


def create_bridge_inbound(
    conn,
    credit_class_id: str,
    source_chain: str,
    issuer_address: str,
    recipient_address: str,
    quantity: float,
    origin_tx_id: str = None,
    origin_tx_source: str = None,
    origin_tx_contract: str = None,
    jurisdiction: str = None,
    metadata: dict = None,
) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO credit_bridge_transaction "
            "(direction, source_chain, target_chain, sender_address, recipient_address, "
            "quantity, origin_tx_id, origin_tx_source, metadata) "
            "VALUES ('inbound', :source, 'kokonut', :sender, :recipient, "
            ":qty, :otxid, :otxsrc, :meta) "
            "RETURNING id"
        ),
        {
            "source": source_chain, "sender": issuer_address,
            "recipient": recipient_address, "qty": quantity,
            "otxid": origin_tx_id, "otxsrc": origin_tx_source,
            "meta": json.dumps(metadata) if metadata else "{}",
        },
    ).mappings().first()

    logger.info("Created inbound bridge tx %s: %s credits from %s", result["id"], quantity, source_chain)
    return {"id": str(result["id"]), "direction": "inbound", "source_chain": source_chain}


def complete_bridge(conn, bridge_tx_id: str, bridge_tx_hash: str = None) -> dict:
    tx = conn.execute(
        conn.text("SELECT * FROM credit_bridge_transaction WHERE id = :id"),
        {"id": bridge_tx_id},
    ).mappings().first()
    if not tx:
        raise ValueError(f"Bridge transaction not found: {bridge_tx_id}")
    if tx["status"] != "pending":
        raise ValueError(f"Bridge transaction is not pending: {tx['status']}")

    conn.execute(
        conn.text(
            "UPDATE credit_bridge_transaction SET "
            "status = 'completed', bridge_tx_hash = :txh, completed_at = NOW() "
            "WHERE id = :id"
        ),
        {"txh": bridge_tx_hash, "id": bridge_tx_id},
    )

    logger.info("Completed bridge transaction %s", bridge_tx_id)
    return {"id": bridge_tx_id, "status": "completed"}


def get_bridge_transaction(conn, bridge_tx_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM credit_bridge_transaction WHERE id = :id"),
        {"id": bridge_tx_id},
    ).mappings().first()
    return dict(result) if result else None


def list_bridge_transactions(
    conn,
    direction: str = None,
    source_chain: str = None,
    target_chain: str = None,
    status: str = None,
) -> list[dict]:
    conditions = []
    params: dict[str, Any] = {}
    if direction:
        conditions.append("direction = :d")
        params["d"] = direction
    if source_chain:
        conditions.append("source_chain = :sc")
        params["sc"] = source_chain
    if target_chain:
        conditions.append("target_chain = :tc")
        params["tc"] = target_chain
    if status:
        conditions.append("status = :s")
        params["s"] = status
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    result = conn.execute(
        conn.text(f"SELECT * FROM credit_bridge_transaction {where} ORDER BY created_at DESC"),
        params,
    )
    return [dict(r) for r in result.mappings()]
