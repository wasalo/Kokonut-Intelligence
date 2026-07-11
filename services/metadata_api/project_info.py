"""ProjectInfo: Complete project view aligned with Regen Framework WG ProjectInfo schema."""

from __future__ import annotations

import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger("metadata_api.project_info")


def get_project_info(conn, location_id: str) -> dict | None:
    loc = conn.execute(
        conn.text("SELECT * FROM location WHERE id = :lid"),
        {"lid": location_id},
    ).mappings().first()
    if not loc:
        return None

    registry = conn.execute(
        conn.text("SELECT * FROM farm_registry_record WHERE location_id = :lid AND status IN ('verified', 'published') LIMIT 1"),
        {"lid": location_id},
    ).mappings().first()

    links = list_project_links(conn, location_id)
    reference_ids = list_project_reference_ids(conn, location_id)

    from services.metadata_api.app_metadata import get_app_metadata
    app_meta = get_app_metadata(conn, location_id)

    from services.iri.resolver import get_current_iri
    iri = get_current_iri(conn, "location", location_id)

    # Resolve project roles from partner table
    roles = {}
    for role_key, fk_col in [("developer", "developer_id"), ("monitor", "monitor_id"),
                               ("operator", "operator_id"), ("owner", "owner_id")]:
        if registry and registry.get(fk_col):
            partner = conn.execute(
                conn.text("SELECT * FROM partner WHERE id = :pid"),
                {"pid": str(registry[fk_col])},
            ).mappings().first()
            if partner:
                roles[role_key] = dict(partner)

    return {
        "iri": iri,
        "name": loc["name"],
        "description": loc.get("description"),
        "url": loc.get("project_url"),
        "projectStartDate": str(loc["project_start_date"]) if loc.get("project_start_date") else None,
        "projectEndDate": str(loc["project_end_date"]) if loc.get("project_end_date") else None,
        "region": loc.get("region"),
        "subRegion": loc.get("sub_region"),
        "bioregion": loc.get("bioregion"),
        "biomeType": loc.get("biome_type"),
        "watershed": loc.get("watershed"),
        "subWatershed": loc.get("sub_watershed"),
        "latitude": float(loc["latitude"]) if loc.get("latitude") else None,
        "longitude": float(loc["longitude"]) if loc.get("longitude") else None,
        "links": links,
        "referenceIds": reference_ids,
        "projectDeveloper": roles.get("developer"),
        "projectMonitor": roles.get("monitor"),
        "projectOperator": roles.get("operator"),
        "projectOwner": roles.get("owner"),
        "registry": dict(registry) if registry else None,
        "appMetadata": app_meta,
    }


# ---------------------------------------------------------------------------
# Project Links (hasLinks)
# ---------------------------------------------------------------------------

def add_project_link(conn, location_id: str, link_name: str, link_url: str,
                     link_description: str = None, link_type: str = "external") -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO project_link (location_id, link_name, link_url, link_description, link_type) "
            "VALUES (:lid, :name, :url, :desc, :type) RETURNING id"
        ),
        {"lid": location_id, "name": link_name, "url": link_url,
         "desc": link_description, "type": link_type},
    )
    record = result.mappings().first()
    logger.info("Added project link %s for location %s", record["id"], location_id)
    return {"id": str(record["id"]), "link_name": link_name, "link_url": link_url}


def list_project_links(conn, location_id: str) -> list[dict]:
    result = conn.execute(
        conn.text("SELECT * FROM project_link WHERE location_id = :lid ORDER BY created_at"),
        {"lid": location_id},
    )
    return [dict(r) for r in result.mappings()]


def delete_project_link(conn, link_id: str) -> bool:
    result = conn.execute(
        conn.text("DELETE FROM project_link WHERE id = :id"),
        {"id": link_id},
    )
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Project Reference IDs (hasReferenceId)
# ---------------------------------------------------------------------------

def add_project_reference_id(conn, location_id: str, identifier: str, reference_type: str,
                             registry_name: str = None, url: str = None) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO project_reference_id (location_id, identifier, reference_type, registry_name, url) "
            "VALUES (:lid, :ident, :rtype, :rname, :url) RETURNING id"
        ),
        {"lid": location_id, "ident": identifier, "rtype": reference_type,
         "rname": registry_name, "url": url},
    )
    record = result.mappings().first()
    logger.info("Added project reference ID %s for location %s", record["id"], location_id)
    return {"id": str(record["id"]), "identifier": identifier, "reference_type": reference_type}


def list_project_reference_ids(conn, location_id: str) -> list[dict]:
    result = conn.execute(
        conn.text("SELECT * FROM project_reference_id WHERE location_id = :lid ORDER BY created_at"),
        {"lid": location_id},
    )
    return [dict(r) for r in result.mappings()]


def delete_project_reference_id(conn, ref_id: str) -> bool:
    result = conn.execute(
        conn.text("DELETE FROM project_reference_id WHERE id = :id"),
        {"id": ref_id},
    )
    return result.rowcount > 0
