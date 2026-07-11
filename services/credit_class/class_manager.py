"""Credit class management: methodology and protocol definitions."""

from __future__ import annotations

import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger("credit_class.class_manager")

VALID_CREDIT_TYPES = {"carbon", "biodiversity", "water", "soil", "mixed"}
VALID_CLASS_STATUSES = {"draft", "submitted", "verified", "published", "deprecated"}


def create_class(
    conn,
    name: str,
    methodology: str,
    credit_type: str,
    description: str = None,
    url: str = None,
    methodology_version: str = None,
    methodology_ref: str = None,
    ecosystem_types: list[str] = None,
    eligible_activities: list[str] = None,
    crediting_period_years: int = 10,
    registry_slug: str = None,
    issuer_wallet: str = None,
    governance_mechanism: str = None,
    primary_impact_type: str = None,
    primary_impact_name: str = None,
    primary_impact_sdgs: list[int] = None,
    admin_address: str = None,
    credit_type_id: str = None,
    allowlist_required: bool = False,
    metadata: dict = None,
    created_by: str = None,
) -> dict:
    if credit_type not in VALID_CREDIT_TYPES:
        raise ValueError(f"Invalid credit_type: {credit_type}. Must be one of: {sorted(VALID_CREDIT_TYPES)}")
    if not name:
        raise ValueError("name is required")
    if not methodology:
        raise ValueError("methodology is required")

    result = conn.execute(
        conn.text(
            "INSERT INTO credit_class "
            "(name, description, url, methodology, methodology_version, methodology_ref, "
            "credit_type, ecosystem_types, eligible_activities, crediting_period_years, "
            "registry_slug, issuer_wallet, governance_mechanism, "
            "primary_impact_type, primary_impact_name, primary_impact_sdgs, "
            "admin_address, credit_type_id, allowlist_required, "
            "metadata, created_by, updated_by) "
            "VALUES "
            "(:name, :description, :url, :methodology, :mv, :mr, "
            ":ct, :et, :ea, :cpy, "
            ":rs, :iw, :gm, "
            ":pit, :pin, :pisdgs, "
            ":admin, :ctid, :ar, "
            ":metadata, :cb, :cb) "
            "RETURNING id"
        ),
        {
            "name": name, "description": description, "url": url,
            "methodology": methodology, "mv": methodology_version, "mr": methodology_ref,
            "ct": credit_type, "et": ecosystem_types, "ea": eligible_activities,
            "cpy": crediting_period_years,
            "rs": registry_slug, "iw": issuer_wallet, "gm": governance_mechanism,
            "pit": primary_impact_type, "pin": primary_impact_name, "pisdgs": primary_impact_sdgs,
            "admin": admin_address, "ctid": credit_type_id, "ar": allowlist_required,
            "metadata": json.dumps(metadata) if metadata else "{}",
            "cb": created_by,
        },
    )
    record = result.mappings().first()
    logger.info("Created credit_class %s: %s", record["id"], name)
    return {"id": str(record["id"]), "name": name}


def update_class(conn, class_id: str, **kwargs) -> dict:
    allowed = {
        "name", "description", "url", "methodology", "methodology_version", "methodology_ref",
        "credit_type", "ecosystem_types", "eligible_activities", "crediting_period_years",
        "registry_slug", "issuer_wallet", "governance_mechanism",
        "primary_impact_type", "primary_impact_name", "primary_impact_sdgs",
        "admin_address", "credit_type_id", "allowlist_required",
        "status", "metadata", "updated_by",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        raise ValueError("No valid fields to update")
    if "credit_type" in updates and updates["credit_type"] not in VALID_CREDIT_TYPES:
        raise ValueError(f"Invalid credit_type: {updates['credit_type']}")
    if "status" in updates and updates["status"] not in VALID_CLASS_STATUSES:
        raise ValueError(f"Invalid status: {updates['status']}")

    if "metadata" in updates and isinstance(updates["metadata"], dict):
        updates["metadata"] = json.dumps(updates["metadata"])

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["cid"] = class_id
    conn.execute(
        conn.text(f"UPDATE credit_class SET {set_clause}, updated_at = NOW() WHERE id = :cid"),
        updates,
    )
    return {"id": class_id, "updated_fields": list(updates.keys())}


def get_class(conn, class_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM credit_class WHERE id = :cid"),
        {"cid": class_id},
    ).mappings().first()
    return dict(result) if result else None


def list_classes(conn, credit_type: str = None, status: str = None) -> list[dict]:
    conditions = []
    params: dict[str, Any] = {}
    if credit_type:
        conditions.append("credit_type = :ct")
        params["ct"] = credit_type
    if status:
        conditions.append("status = :s")
        params["s"] = status
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    result = conn.execute(
        conn.text(f"SELECT * FROM credit_class {where} ORDER BY created_at DESC"),
        params,
    )
    return [dict(r) for r in result.mappings()]


def deprecate_class(conn, class_id: str) -> dict:
    return update_class(conn, class_id, status="deprecated")


def get_class_full(conn, class_id: str) -> dict | None:
    cc = get_class(conn, class_id)
    if not cc:
        return None

    cobenefits = conn.execute(
        conn.text("SELECT * FROM credit_class_cobenefit WHERE credit_class_id = :cid ORDER BY created_at"),
        {"cid": class_id},
    ).mappings().all()

    registries = conn.execute(
        conn.text("SELECT * FROM credit_class_registry WHERE credit_class_id = :cid ORDER BY created_at"),
        {"cid": class_id},
    ).mappings().all()

    programs = conn.execute(
        conn.text("SELECT * FROM crediting_program WHERE credit_class_id = :cid ORDER BY created_at"),
        {"cid": class_id},
    ).mappings().all()

    protocols = conn.execute(
        conn.text("SELECT * FROM credit_protocol WHERE credit_class_id = :cid ORDER BY is_primary DESC, created_at"),
        {"cid": class_id},
    ).mappings().all()

    methodologies = conn.execute(
        conn.text("SELECT * FROM credit_class_methodology WHERE credit_class_id = :cid ORDER BY is_approved DESC, created_at"),
        {"cid": class_id},
    ).mappings().all()

    buffer_pools = conn.execute(
        conn.text("SELECT * FROM buffer_pool_account WHERE credit_class_id = :cid ORDER BY created_at"),
        {"cid": class_id},
    ).mappings().all()

    cc["cobenefits"] = [dict(r) for r in cobenefits]
    cc["registries"] = [dict(r) for r in registries]
    cc["programs"] = [dict(r) for r in programs]
    cc["protocols"] = [dict(r) for r in protocols]
    cc["methodologies"] = [dict(r) for r in methodologies]
    cc["buffer_pools"] = [dict(r) for r in buffer_pools]

    return cc
