"""Credit batch management: issuance, retirement, and balance tracking."""

from __future__ import annotations

import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger("credit_class.batch_manager")

VALID_BATCH_STATUSES = {"draft", "submitted", "verified", "published", "retired", "cancelled"}


def _generate_batch_code(conn, credit_class_id: str, location_id: str, vintage_year: int) -> str:
    cc = conn.execute(
        conn.text("SELECT methodology FROM credit_class WHERE id = :cid"),
        {"cid": credit_class_id},
    ).mappings().first()
    prefix = cc["methodology"][:3].upper() if cc else "CRD"

    loc = conn.execute(
        conn.text("SELECT name FROM location WHERE id = :lid"),
        {"lid": location_id},
    ).mappings().first()
    loc_prefix = loc["name"][:4].upper() if loc else "UNKN"

    seq_result = conn.execute(
        conn.text(
            "SELECT COUNT(*) + 1 as seq FROM credit_batch "
            "WHERE credit_class_id = :cid AND vintage_year = :vy"
        ),
        {"cid": credit_class_id, "vy": vintage_year},
    ).mappings().first()
    seq = seq_result["seq"]

    return f"CC-{prefix}-{vintage_year}-{loc_prefix}-{seq:04d}"


def create_batch(
    conn,
    credit_class_id: str,
    location_id: str,
    vintage_year: int,
    total_quantity: float,
    unit: str = "tonneCO2e",
    monitoring_report_cid: str = None,
    verification_report_cid: str = None,
    evidence_maturity: int = 1,
    metadata: dict = None,
    created_by: str = None,
) -> dict:
    cc = get_class_with_validation(conn, credit_class_id)
    batch_code = _generate_batch_code(conn, credit_class_id, location_id, vintage_year)

    result = conn.execute(
        conn.text(
            "INSERT INTO credit_batch "
            "(credit_class_id, location_id, batch_code, vintage_year, total_quantity, unit, "
            "monitoring_report_cid, verification_report_cid, evidence_maturity, metadata, "
            "created_by, updated_by) "
            "VALUES "
            "(:ccid, :lid, :bc, :vy, :tq, :u, "
            ":mrc, :vrc, :em, :metadata, "
            ":cb, :cb) "
            "RETURNING id"
        ),
        {
            "ccid": credit_class_id, "lid": location_id, "bc": batch_code,
            "vy": vintage_year, "tq": total_quantity, "u": unit,
            "mrc": monitoring_report_cid, "vrc": verification_report_cid,
            "em": evidence_maturity,
            "metadata": json.dumps(metadata) if metadata else "{}",
            "cb": created_by,
        },
    )
    record = result.mappings().first()
    logger.info("Created credit_batch %s: %s", record["id"], batch_code)
    return {"id": str(record["id"]), "batch_code": batch_code}


def issue_batch(conn, batch_id: str) -> dict:
    batch = get_batch(conn, batch_id)
    if not batch:
        raise ValueError(f"Batch not found: {batch_id}")
    if batch["status"] not in ("verified", "submitted"):
        raise ValueError(f"Batch must be verified or submitted to issue, current: {batch['status']}")

    conn.execute(
        conn.text(
            "UPDATE credit_batch SET status = 'published', issued_quantity = total_quantity, "
            "minted_at = NOW(), updated_at = NOW() WHERE id = :bid"
        ),
        {"bid": batch_id},
    )
    logger.info("Issued credit_batch %s (%s)", batch_id, batch["batch_code"])
    return {"id": batch_id, "batch_code": batch["batch_code"], "status": "published"}


def get_batch(conn, batch_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM credit_batch WHERE id = :bid"),
        {"bid": batch_id},
    ).mappings().first()
    return dict(result) if result else None


def list_batches(conn, credit_class_id: str = None, location_id: str = None) -> list[dict]:
    conditions = []
    params: dict[str, Any] = {}
    if credit_class_id:
        conditions.append("credit_class_id = :ccid")
        params["ccid"] = credit_class_id
    if location_id:
        conditions.append("location_id = :lid")
        params["lid"] = location_id
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    result = conn.execute(
        conn.text(f"SELECT * FROM credit_batch {where} ORDER BY created_at DESC"),
        params,
    )
    return [dict(r) for r in result.mappings()]


def get_batch_balance(conn, batch_id: str) -> dict:
    batch = get_batch(conn, batch_id)
    if not batch:
        raise ValueError(f"Batch not found: {batch_id}")
    return {
        "batch_id": batch_id,
        "batch_code": batch["batch_code"],
        "total_quantity": float(batch["total_quantity"]),
        "issued_quantity": float(batch["issued_quantity"]),
        "retired_quantity": float(batch["retired_quantity"]),
        "cancelled_quantity": float(batch["cancelled_quantity"]),
        "available_quantity": float(batch["available_quantity"]),
        "unit": batch["unit"],
    }


def get_class_with_validation(conn, class_id: str) -> dict:
    cc = conn.execute(
        conn.text("SELECT * FROM credit_class WHERE id = :cid"),
        {"cid": class_id},
    ).mappings().first()
    if not cc:
        raise ValueError(f"Credit class not found: {class_id}")
    return dict(cc)


def update_batch_metadata(conn, batch_id: str, metadata: dict) -> dict:
    import json
    batch = get_batch(conn, batch_id)
    if not batch:
        raise ValueError(f"Batch not found: {batch_id}")

    conn.execute(
        conn.text(
            "UPDATE credit_batch SET metadata = :meta, updated_at = NOW() WHERE id = :bid"
        ),
        {"meta": json.dumps(metadata), "bid": batch_id},
    )
    return {"id": batch_id, "updated_fields": ["metadata"]}


def list_batches_by_issuer(conn, issuer_address: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT b.* FROM credit_batch b "
            "JOIN credit_class_issuer ci ON ci.credit_class_id = b.credit_class_id "
            "WHERE ci.issuer_address = :addr AND ci.revoked_at IS NULL "
            "ORDER BY b.created_at DESC"
        ),
        {"addr": issuer_address},
    )
    return [dict(r) for r in result.mappings()]


def get_batch_by_code(conn, batch_code: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM credit_batch WHERE batch_code = :code"),
        {"code": batch_code},
    ).mappings().first()
    return dict(result) if result else None
