"""Thesaurus: controlled vocabularies with hierarchical relationships."""

from __future__ import annotations

import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger("thesaurus")


def create_thesaurus(conn, identifier: str, title: str, description: str = None,
                     language: str = "en") -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO thesaurus (identifier, title, description, language) "
            "VALUES (:id, :title, :desc, :lang) "
            "ON CONFLICT (identifier) DO UPDATE SET title = EXCLUDED.title, description = EXCLUDED.description "
            "RETURNING id"
        ),
        {"id": identifier, "title": title, "desc": description, "lang": language},
    ).mappings().first()
    return {"id": str(result["id"]), "identifier": identifier}


def get_thesaurus(conn, identifier: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM thesaurus WHERE identifier = :id"),
        {"id": identifier},
    ).mappings().first()
    return dict(result) if result else None


def list_thesauri(conn) -> list[dict]:
    result = conn.execute(
        conn.text("SELECT * FROM thesaurus ORDER BY identifier")
    )
    return [dict(r) for r in result.mappings()]


def add_keyword(conn, thesaurus_id: str, keyword_about: str,
                alt_label: str = None, parent_keyword_id: str = None) -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO thesaurus_keyword (thesaurus_id, keyword_about, alt_label, parent_keyword_id) "
            "VALUES (:tid, :about, :alt, :parent) RETURNING id"
        ),
        {"tid": thesaurus_id, "about": keyword_about, "alt": alt_label, "parent": parent_keyword_id},
    ).mappings().first()
    return {"id": str(result["id"]), "keyword_about": keyword_about}


def add_keyword_label(conn, keyword_id: str, label: str, language: str = "en") -> dict:
    result = conn.execute(
        conn.text(
            "INSERT INTO thesaurus_keyword_label (keyword_id, label, language) "
            "VALUES (:kid, :label, :lang) "
            "ON CONFLICT (keyword_id, language) DO UPDATE SET label = EXCLUDED.label "
            "RETURNING id"
        ),
        {"kid": keyword_id, "label": label, "lang": language},
    ).mappings().first()
    return {"id": str(result["id"]), "label": label, "language": language}


def list_keywords(conn, thesaurus_id: str, parent_keyword_id: str = None) -> list[dict]:
    conditions = ["thesaurus_id = :tid"]
    params: dict[str, Any] = {"tid": thesaurus_id}
    if parent_keyword_id:
        conditions.append("parent_keyword_id = :pid")
        params["pid"] = parent_keyword_id
    else:
        conditions.append("parent_keyword_id IS NULL")
    where = " AND ".join(conditions)
    result = conn.execute(
        conn.text(f"SELECT * FROM thesaurus_keyword WHERE {where} ORDER BY keyword_about"),
        params,
    )
    return [dict(r) for r in result.mappings()]


def get_keyword_children(conn, keyword_id: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT * FROM thesaurus_keyword WHERE parent_keyword_id = :pid ORDER BY keyword_about"
        ),
        {"pid": keyword_id},
    )
    return [dict(r) for r in result.mappings()]


def get_keyword_labels(conn, keyword_id: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT * FROM thesaurus_keyword_label WHERE keyword_id = :kid"
        ),
        {"kid": keyword_id},
    )
    return [dict(r) for r in result.mappings()]


def delete_keyword(conn, keyword_id: str) -> bool:
    result = conn.execute(
        conn.text("DELETE FROM thesaurus_keyword WHERE id = :id"),
        {"id": keyword_id},
    )
    return result.rowcount > 0
