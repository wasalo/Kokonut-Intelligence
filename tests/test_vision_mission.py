"""Tests for Vision, Mission & Values."""

import uuid
import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics.vision_mission import (
    create_statement, get_statement, list_statements,
    approve_statement, archive_statement, get_current_statements,
)


def _db():
    try:
        return get_db()
    except Exception as exc:
        pytest.skip(f"no database available: {exc}")


def _purge(conn, stmt_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM vision_mission WHERE id = %s::uuid", (stmt_id,))
    conn.commit()


def test_create_statement():
    conn = _db()
    entity_id = str(uuid.uuid4())
    stmt = create_statement(
        "A world without hunger",
        statement_type="vision",
        entity_type="organization",
        entity_id=entity_id,
    )
    try:
        assert stmt["statement_type"] == "vision"
        assert stmt["statement_text"] == "A world without hunger"
        assert stmt["status"] == "draft"
        got = get_statement(stmt["id"])
        assert got is not None
    finally:
        _purge(conn, stmt["id"])


def test_list_statements():
    conn = _db()
    entity_id = str(uuid.uuid4())
    stmt = create_statement("List Test Vision", statement_type="vision", entity_type="organization", entity_id=entity_id)
    try:
        stmts = list_statements(entity_type="organization", entity_id=entity_id)
        assert any(s["id"] == stmt["id"] for s in stmts)
    finally:
        _purge(conn, stmt["id"])


def test_approve_statement():
    conn = _db()
    stmt = create_statement("Approve Test", statement_type="mission", entity_type="organization", entity_id=str(uuid.uuid4()))
    try:
        approved = approve_statement(stmt["id"], approved_by="test_admin")
        assert approved is not None
        assert approved["status"] == "approved"
        assert approved["approved_by"] == "test_admin"
    finally:
        _purge(conn, stmt["id"])


def test_archive_statement():
    conn = _db()
    stmt = create_statement("Archive Test", statement_type="values", entity_type="organization", entity_id=str(uuid.uuid4()))
    approve_statement(stmt["id"], approved_by="admin")
    try:
        archived = archive_statement(stmt["id"])
        assert archived["status"] == "archived"
    finally:
        _purge(conn, stmt["id"])


def test_get_current_statements():
    conn = _db()
    entity_id = str(uuid.uuid4())
    stmt = create_statement("Current Test", statement_type="vision", entity_type="organization", entity_id=entity_id)
    approve_statement(stmt["id"], approved_by="admin")
    try:
        current = get_current_statements(entity_type="organization", entity_id=entity_id)
        assert any(s["id"] == stmt["id"] for s in current)
    finally:
        _purge(conn, stmt["id"])


def test_reject_approve_non_draft():
    conn = _db()
    stmt = create_statement("Reject Test", statement_type="vision", entity_type="organization", entity_id=str(uuid.uuid4()))
    approve_statement(stmt["id"], approved_by="admin")
    try:
        # trying to approve again should fail (already approved, not draft)
        result = approve_statement(stmt["id"], approved_by="admin2")
        assert result is None
    finally:
        _purge(conn, stmt["id"])


def test_list_by_type():
    conn = _db()
    entity_id = str(uuid.uuid4())
    v = create_statement("Type Vision", statement_type="vision", entity_type="organization", entity_id=entity_id)
    m = create_statement("Type Mission", statement_type="mission", entity_type="organization", entity_id=entity_id)
    try:
        visions = list_statements(entity_type="organization", entity_id=entity_id, statement_type="vision")
        assert len(visions) >= 1
        assert all(s["statement_type"] == "vision" for s in visions)
    finally:
        _purge(conn, v["id"])
        _purge(conn, m["id"])
