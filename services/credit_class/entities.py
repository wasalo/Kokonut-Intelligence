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


# ---------------------------------------------------------------------------
# Credit Types (Credit Type entity)
# ---------------------------------------------------------------------------

def create_credit_type(conn, name: str, abbreviation: str, unit: str,
                       precision: int = 2, description: str = None) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO credit_type (name, abbreviation, unit, precision, description) "
            "VALUES (:name, :abbr, :unit, :prec, :desc) RETURNING id"
        ),
        {"name": name, "abbr": abbreviation, "unit": unit, "prec": precision, "desc": description},
    )
    record = result.mappings().first()
    return {"id": str(record["id"]), "name": name}


def list_credit_types(conn) -> list[dict]:
    result = conn.execute(
        conn.text("SELECT * FROM credit_type ORDER BY name")
    )
    return [dict(r) for r in result.mappings()]


def get_credit_type(conn, type_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM credit_type WHERE id = :tid"),
        {"tid": type_id},
    ).mappings().first()
    return dict(result) if result else None


# ---------------------------------------------------------------------------
# Issuers (Credit Class Issuers)
# ---------------------------------------------------------------------------

def add_issuer(conn, credit_class_id: str, issuer_address: str,
               issuer_name: str = None, added_by: str = None) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO credit_class_issuer (credit_class_id, issuer_address, issuer_name, added_by) "
            "VALUES (:ccid, :addr, :name, :ab) RETURNING id"
        ),
        {"ccid": credit_class_id, "addr": issuer_address, "name": issuer_name, "ab": added_by},
    )
    record = result.mappings().first()
    return {"id": str(record["id"]), "issuer_address": issuer_address}


def list_issuers(conn, credit_class_id: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT * FROM credit_class_issuer "
            "WHERE credit_class_id = :ccid AND revoked_at IS NULL ORDER BY added_at"
        ),
        {"ccid": credit_class_id},
    )
    return [dict(r) for r in result.mappings()]


def revoke_issuer(conn, issuer_id: str) -> bool:
    result = conn.execute(
        conn.text(
            "UPDATE credit_class_issuer SET revoked_at = NOW() WHERE id = :id AND revoked_at IS NULL"
        ),
        {"id": issuer_id},
    )
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Creator Allowlist
# ---------------------------------------------------------------------------

def add_to_allowlist(conn, address: str, entity_name: str = None, added_by: str = None) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO credit_class_creator_allowlist (address, entity_name, added_by) "
            "VALUES (:addr, :name, :ab) "
            "ON CONFLICT (address) DO UPDATE SET is_active = TRUE "
            "RETURNING id"
        ),
        {"addr": address, "name": entity_name, "ab": added_by},
    )
    record = result.mappings().first()
    return {"id": str(record["id"]), "address": address}


def list_allowlist(conn) -> list[dict]:
    result = conn.execute(
        conn.text("SELECT * FROM credit_class_creator_allowlist WHERE is_active = TRUE ORDER BY added_at")
    )
    return [dict(r) for r in result.mappings()]


def remove_from_allowlist(conn, address: str) -> bool:
    result = conn.execute(
        conn.text(
            "UPDATE credit_class_creator_allowlist SET is_active = FALSE WHERE address = :addr"
        ),
        {"addr": address},
    )
    return result.rowcount > 0


def is_allowed_creator(conn, address: str) -> bool:
    result = conn.execute(
        conn.text(
            "SELECT 1 FROM credit_class_creator_allowlist WHERE address = :addr AND is_active = TRUE"
        ),
        {"addr": address},
    ).mappings().first()
    return result is not None
