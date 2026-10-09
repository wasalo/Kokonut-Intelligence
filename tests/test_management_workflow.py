"""Tests for the work-item lifecycle workbench and workflow spec."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from services.ingestion.base import get_db
from services.management import workbench
from services.workflow_specs.validator import validate
from services.workflow_specs.work_item import WORK_ITEM


def test_work_item_spec_validates():
    validate(WORK_ITEM)
    assert WORK_ITEM.states == frozenset(
        {"draft", "assigned", "in_progress", "blocked", "done", "cancelled"}
    )


def test_allowed_transitions_from_draft():
    assert workbench.allowed_transitions("draft") == {"assigned", "cancelled"}


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
                (str(uuid.uuid4()), "mgmt-test"),
            )
            oid = cur.fetchone()[0]
            conn.commit()
        yield str(oid)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM work_item WHERE organization_id = %s", (oid,))
            cur.execute("DELETE FROM organization WHERE id = %s", (oid,))
            conn.commit()
    finally:
        conn.close()


def test_create_draft_and_assign_lifecycle(org_id):
    conn = _db()
    try:
        row = workbench.create_work_item(conn, org_id, "Task A", "system")
        assert row["status"] == "draft"
        wid = str(row["id"])

        row = workbench.assign(conn, wid, "staff", str(uuid.uuid4()), "staff")
        assert row["status"] == "assigned"

        row = workbench.transition(conn, wid, "in_progress", "staff")
        assert row["status"] == "in_progress"
        assert row["started_at"] is not None

        row = workbench.transition(conn, wid, "done", "staff")
        assert row["status"] == "done"
        assert row["completed_at"] is not None
    finally:
        conn.close()


def test_invalid_transition_rejected(org_id):
    conn = _db()
    try:
        row = workbench.create_work_item(conn, org_id, "Task", "system")
        wid = str(row["id"])
        with pytest.raises(ValueError):
            workbench.transition(conn, wid, "done", "staff")
    finally:
        conn.close()


def test_blocked_requires_note(org_id):
    conn = _db()
    try:
        row = workbench.create_work_item(
            conn, org_id, "Task", "system",
            assignee_type="staff", assignee_id=str(uuid.uuid4()),
        )
        wid = str(row["id"])
        workbench.transition(conn, wid, "in_progress", "staff")
        with pytest.raises(ValueError):
            workbench.transition(conn, wid, "blocked", "staff", note=None)
        workbench.transition(conn, wid, "blocked", "staff", note="waiting on parts")
        assert workbench.get_work_item(conn, wid)["status"] == "blocked"
    finally:
        conn.close()


def test_sla_sweep_flags_overdue(org_id):
    conn = _db()
    try:
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        row = workbench.create_work_item(
            conn, org_id, "Overdue", "system",
            assignee_type="staff", assignee_id=str(uuid.uuid4()), due_at=past,
        )
        result = workbench.check_sla(conn, org_id)
        assert str(row["id"]) in {str(r["id"]) for r in result["overdue"]}
    finally:
        conn.close()
