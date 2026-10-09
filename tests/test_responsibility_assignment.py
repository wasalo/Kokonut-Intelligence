"""Tests for RACI responsibility assignment and the single-accountable rule."""

import uuid
from unittest.mock import MagicMock

import pytest
from psycopg2 import IntegrityError

from services.ingestion.base import get_db
from services.management import responsibility


def test_assign_responsibility_rejects_invalid_party():
    with pytest.raises(ValueError):
        responsibility.assign_responsibility(
            MagicMock(), "location", str(uuid.uuid4()), "bogus", str(uuid.uuid4()), "accountable"
        )


def test_assign_responsibility_rejects_invalid_role():
    with pytest.raises(ValueError):
        responsibility.assign_responsibility(
            MagicMock(), "location", str(uuid.uuid4()), "staff", str(uuid.uuid4()), "bogus"
        )


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


@pytest.fixture
def entity():
    return ("location", str(uuid.uuid4()))


def test_single_accountable_enforced(entity):
    conn = _db()
    try:
        et, eid = entity
        responsibility.assign_responsibility(conn, et, eid, "staff", str(uuid.uuid4()), "accountable")
        with pytest.raises(ValueError):
            responsibility.assign_responsibility(conn, et, eid, "staff", str(uuid.uuid4()), "accountable")
        responsibility.assign_responsibility(conn, et, eid, "staff", str(uuid.uuid4()), "responsible")

        acc = responsibility.get_accountable(conn, et, eid)
        assert acc is not None and acc["raci_role"] == "accountable"

        rows = responsibility.list_responsibilities_for_entity(conn, et, eid)
        assert len(rows) == 2
    finally:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM responsibility_assignment WHERE entity_type = %s AND entity_id = %s",
                (et, uuid.UUID(eid)),
            )
            conn.commit()
        conn.close()


def test_list_entities_for_party(entity):
    conn = _db()
    try:
        et, eid = entity
        party_id = str(uuid.uuid4())
        responsibility.assign_responsibility(conn, et, eid, "staff", party_id, "responsible")
        rows = responsibility.list_entities_for_party(conn, "staff", party_id)
        assert any(str(r["entity_id"]) == eid for r in rows)
    finally:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM responsibility_assignment WHERE entity_type = %s AND entity_id = %s",
                (et, uuid.UUID(eid)),
            )
            conn.commit()
        conn.close()
