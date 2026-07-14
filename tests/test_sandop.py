"""Tests for the S&OP cockpit (read-only)."""

import uuid

import pytest

from services.ingestion.base import get_db
from services.planning import sandop


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


@pytest.fixture
def org_id():
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO organization (org_key, name) VALUES (%s, %s) RETURNING id",
                (str(uuid.uuid4()), "sandop-test"),
            )
            oid = cur.fetchone()[0]
            conn.commit()
        yield str(oid)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM organization WHERE id = %s", (oid,))
            conn.commit()
    finally:
        conn.close()


def test_cockpit_returns_structure(org_id):
    conn = _db()
    try:
        result = sandop.cockpit(conn, org_id)
        assert result["organization_id"] == org_id
        assert "summary" in result
        assert isinstance(result["demand"], list)
        assert isinstance(result["capacity"], list)
        assert isinstance(result["financial_plans"], list)
        assert isinstance(result["budget_lines"], list)
    finally:
        conn.close()
