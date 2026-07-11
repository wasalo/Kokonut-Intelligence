"""Data Resolver: resolver registry and data-resolver registration."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger("data.resolver")


def define_resolver(conn, resolver_url: str, manager_address: str,
                    description: str = None) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO data_resolver (resolver_url, manager_address, description) "
            "VALUES (:url, :mgr, :desc) "
            "ON CONFLICT (resolver_url) DO UPDATE SET "
            "manager_address = EXCLUDED.manager_address, description = EXCLUDED.description "
            "RETURNING id"
        ),
        {"url": resolver_url, "mgr": manager_address, "desc": description},
    ).mappings().first()
    logger.info("Defined resolver %s at %s", result["id"], resolver_url)
    return {"id": str(result["id"]), "resolver_url": resolver_url}


def get_resolver(conn, resolver_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM data_resolver WHERE id = :rid"),
        {"rid": resolver_id},
    ).mappings().first()
    return dict(result) if result else None


def get_resolver_by_url(conn, resolver_url: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM data_resolver WHERE resolver_url = :url"),
        {"url": resolver_url},
    ).mappings().first()
    return dict(result) if result else None


def list_resolvers(conn, manager_address: str = None) -> list[dict]:
    conditions = ["is_active = TRUE"]
    params: dict[str, Any] = {}
    if manager_address:
        conditions.append("manager_address = :mgr")
        params["mgr"] = manager_address
    where = "WHERE " + " AND ".join(conditions)
    result = conn.execute(
        conn.text(f"SELECT * FROM data_resolver {where} ORDER BY created_at"),
        params,
    )
    return [dict(r) for r in result.mappings()]


def register_data_to_resolver(conn, resolver_id: str, iri_id: str,
                              registered_by: str = None) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO data_resolver_registration (resolver_id, iri_id, registered_by) "
            "VALUES (:rid, :iri, :rb) "
            "ON CONFLICT (resolver_id, iri_id) DO NOTHING "
            "RETURNING id"
        ),
        {"rid": resolver_id, "iri": iri_id, "rb": registered_by},
    ).mappings().first()
    if result:
        logger.info("Registered IRI %s to resolver %s", iri_id, resolver_id)
    return {"resolver_id": resolver_id, "iri_id": iri_id}


def get_resolvers_for_iri(conn, iri_id: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT dr.* FROM data_resolver dr "
            "JOIN data_resolver_registration drr ON drr.resolver_id = dr.id "
            "WHERE drr.iri_id = :iri AND dr.is_active = TRUE"
        ),
        {"iri": iri_id},
    )
    return [dict(r) for r in result.mappings()]


def get_data_for_resolver(conn, resolver_id: str, limit: int = 100) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT iri.* FROM iri_registry iri "
            "JOIN data_resolver_registration drr ON drr.iri_id = iri.id "
            "WHERE drr.resolver_id = :rid AND iri.is_current = TRUE "
            "ORDER BY iri.created_at DESC LIMIT :limit"
        ),
        {"rid": resolver_id, "limit": limit},
    )
    return [dict(r) for r in result.mappings()]


def unregister_data_from_resolver(conn, resolver_id: str, iri_id: str) -> bool:
    result = conn.execute(
        conn.text(
            "DELETE FROM data_resolver_registration WHERE resolver_id = :rid AND iri_id = :iri"
        ),
        {"rid": resolver_id, "iri": iri_id},
    )
    return result.rowcount > 0
