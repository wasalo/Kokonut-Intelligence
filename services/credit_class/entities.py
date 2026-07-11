"""Credit class entity management: cobenefits, registries, programs, protocols, methodologies, buffer pools."""

from __future__ import annotations

import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger("credit_class.entities")


# ---------------------------------------------------------------------------
# Cobenefits (hasCoBenefits)
# ---------------------------------------------------------------------------

def add_cobenefit(conn, credit_class_id: str, impact_name: str, impact_type: str = None,
                  sdg_numbers: list[int] = None, description: str = None) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO credit_class_cobenefit "
            "(credit_class_id, impact_name, impact_type, sdg_numbers, description) "
            "VALUES (:ccid, :name, :type, :sdgs, :desc) RETURNING id"
        ),
        {"ccid": credit_class_id, "name": impact_name, "type": impact_type, "sdgs": sdg_numbers, "desc": description},
    )
    record = result.mappings().first()
    return {"id": str(record["id"]), "impact_name": impact_name}


def list_cobenefits(conn, credit_class_id: str) -> list[dict]:
    result = conn.execute(
        conn.text("SELECT * FROM credit_class_cobenefit WHERE credit_class_id = :cid ORDER BY created_at"),
        {"cid": credit_class_id},
    )
    return [dict(r) for r in result.mappings()]


def delete_cobenefit(conn, cobenefit_id: str) -> bool:
    result = conn.execute(
        conn.text("DELETE FROM credit_class_cobenefit WHERE id = :id"),
        {"id": cobenefit_id},
    )
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Registries (hasSourceRegistry)
# ---------------------------------------------------------------------------

def add_registry(conn, credit_class_id: str, registry_name: str, registry_url: str = None,
                 is_source: bool = True) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO credit_class_registry "
            "(credit_class_id, registry_name, registry_url, is_source) "
            "VALUES (:ccid, :name, :url, :src) RETURNING id"
        ),
        {"ccid": credit_class_id, "name": registry_name, "url": registry_url, "src": is_source},
    )
    record = result.mappings().first()
    return {"id": str(record["id"]), "registry_name": registry_name}


def list_registries(conn, credit_class_id: str) -> list[dict]:
    result = conn.execute(
        conn.text("SELECT * FROM credit_class_registry WHERE credit_class_id = :cid ORDER BY created_at"),
        {"cid": credit_class_id},
    )
    return [dict(r) for r in result.mappings()]


def delete_registry(conn, registry_id: str) -> bool:
    result = conn.execute(
        conn.text("DELETE FROM credit_class_registry WHERE id = :id"),
        {"id": registry_id},
    )
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Crediting Programs (managedUnderProgram)
# ---------------------------------------------------------------------------

def add_program(conn, credit_class_id: str, name: str, url: str = None,
                version: str = None, identifier: str = None, description: str = None) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO crediting_program "
            "(credit_class_id, name, url, version, identifier, description) "
            "VALUES (:ccid, :name, :url, :ver, :ident, :desc) RETURNING id"
        ),
        {"ccid": credit_class_id, "name": name, "url": url, "ver": version, "ident": identifier, "desc": description},
    )
    record = result.mappings().first()
    return {"id": str(record["id"]), "name": name}


def list_programs(conn, credit_class_id: str) -> list[dict]:
    result = conn.execute(
        conn.text("SELECT * FROM crediting_program WHERE credit_class_id = :cid ORDER BY created_at"),
        {"cid": credit_class_id},
    )
    return [dict(r) for r in result.mappings()]


def delete_program(conn, program_id: str) -> bool:
    result = conn.execute(
        conn.text("DELETE FROM crediting_program WHERE id = :id"),
        {"id": program_id},
    )
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Credit Protocols (hasCreditProtocol)
# ---------------------------------------------------------------------------

def add_protocol(conn, credit_class_id: str, name: str, url: str = None,
                 version: str = None, identifier: str = None, description: str = None,
                 is_primary: bool = False) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO credit_protocol "
            "(credit_class_id, name, url, version, identifier, description, is_primary) "
            "VALUES (:ccid, :name, :url, :ver, :ident, :desc, :prim) RETURNING id"
        ),
        {"ccid": credit_class_id, "name": name, "url": url, "ver": version,
         "ident": identifier, "desc": description, "prim": is_primary},
    )
    record = result.mappings().first()
    return {"id": str(record["id"]), "name": name}


def list_protocols(conn, credit_class_id: str) -> list[dict]:
    result = conn.execute(
        conn.text("SELECT * FROM credit_protocol WHERE credit_class_id = :cid ORDER BY is_primary DESC, created_at"),
        {"cid": credit_class_id},
    )
    return [dict(r) for r in result.mappings()]


def delete_protocol(conn, protocol_id: str) -> bool:
    result = conn.execute(
        conn.text("DELETE FROM credit_protocol WHERE id = :id"),
        {"id": protocol_id},
    )
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Methodologies (hasApprovedMethodologies)
# ---------------------------------------------------------------------------

def add_methodology(conn, credit_class_id: str, name: str, url: str = None,
                    version: str = None, identifier: str = None, description: str = None,
                    is_approved: bool = True) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO credit_class_methodology "
            "(credit_class_id, name, url, version, identifier, description, is_approved) "
            "VALUES (:ccid, :name, :url, :ver, :ident, :desc, :approved) RETURNING id"
        ),
        {"ccid": credit_class_id, "name": name, "url": url, "ver": version,
         "ident": identifier, "desc": description, "approved": is_approved},
    )
    record = result.mappings().first()
    return {"id": str(record["id"]), "name": name}


def list_methodologies(conn, credit_class_id: str) -> list[dict]:
    result = conn.execute(
        conn.text("SELECT * FROM credit_class_methodology WHERE credit_class_id = :cid ORDER BY is_approved DESC, created_at"),
        {"cid": credit_class_id},
    )
    return [dict(r) for r in result.mappings()]


def delete_methodology(conn, methodology_id: str) -> bool:
    result = conn.execute(
        conn.text("DELETE FROM credit_class_methodology WHERE id = :id"),
        {"id": methodology_id},
    )
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Buffer Pool Accounts (hasBufferPoolAccounts)
# ---------------------------------------------------------------------------

def add_buffer_pool(conn, credit_class_id: str, name: str, wallet_address: str = None,
                    pool_allocation: str = None, description: str = None) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO buffer_pool_account "
            "(credit_class_id, name, wallet_address, pool_allocation, description) "
            "VALUES (:ccid, :name, :wallet, :alloc, :desc) RETURNING id"
        ),
        {"ccid": credit_class_id, "name": name, "wallet": wallet_address,
         "alloc": pool_allocation, "desc": description},
    )
    record = result.mappings().first()
    return {"id": str(record["id"]), "name": name}


def list_buffer_pools(conn, credit_class_id: str) -> list[dict]:
    result = conn.execute(
        conn.text("SELECT * FROM buffer_pool_account WHERE credit_class_id = :cid ORDER BY created_at"),
        {"cid": credit_class_id},
    )
    return [dict(r) for r in result.mappings()]


def delete_buffer_pool(conn, pool_id: str) -> bool:
    result = conn.execute(
        conn.text("DELETE FROM buffer_pool_account WHERE id = :id"),
        {"id": pool_id},
    )
    return result.rowcount > 0
