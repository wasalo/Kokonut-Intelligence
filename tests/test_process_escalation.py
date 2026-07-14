"""Integration tests for services.management.escalation (BPM Phase E).

Seeds an organization + a lifecycle instance predicted to breach SLA, then
checks escalation raises a draft work_item + process_escalation row,
is idempotent, and can be resolved. Skips without a DB.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.management import escalation as esc


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


ETYPE = "esc_test"


def _seed(conn):
    org_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO organization (id, org_key, name) VALUES (%s, %s, %s)",
            (str(org_id), f"esc-org-{org_id}", "esc-org"),
        )
    base = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    rows = [
        ("X1", None, "draft", base),
        ("X1", "draft", "submitted", base + timedelta(hours=1)),
        ("X1", "submitted", "verified", base + timedelta(hours=2)),
        ("X1", "verified", "published", base + timedelta(hours=3)),
        ("X2", None, "draft", base),
        ("X2", "draft", "submitted", base + timedelta(hours=2)),
        ("X2", "submitted", "verified", base + timedelta(hours=4)),
        ("X2", "verified", "published", base + timedelta(hours=6)),
        ("Y", None, "draft", now - timedelta(hours=2)),
        ("Y", "draft", "submitted", now - timedelta(hours=1)),
    ]
    ids = []
    with conn.cursor() as cur:
        for tag, frm, to, ts in rows:
            eid = uuid.uuid5(uuid.NAMESPACE_DNS, f"esc-{tag}")
            ids.append((ETYPE, eid))
            cur.execute(
                """
                INSERT INTO lifecycle_transition
                    (entity_type, entity_id, from_status, to_status, transitioned_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (ETYPE, str(eid), frm, to, ts),
            )
    conn.commit()
    return org_id, ids


def _cleanup(conn, org_id, ids):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT work_item_id FROM process_escalation WHERE entity_type = %s",
            (ETYPE,),
        )
        for (wi,) in cur.fetchall():
            if wi:
                cur.execute("DELETE FROM work_item WHERE id = %s", (wi,))
        cur.execute("DELETE FROM process_escalation WHERE entity_type = %s", (ETYPE,))
        for etype, eid in ids:
            cur.execute(
                "DELETE FROM lifecycle_transition WHERE entity_type = %s AND entity_id = %s",
                (etype, str(eid)),
            )
        cur.execute("DELETE FROM organization WHERE id = %s", (str(org_id),))
    conn.commit()


def test_sweep_creates_escalation_and_work_item():
    conn = _db()
    org_id, ids = _seed(conn)
    try:
        n = esc.sweep_and_escalate(conn, sla_target_hours=4.0, threshold=0.5, org_id=str(org_id))
        assert n == 1
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT work_item_id, resolved_at FROM process_escalation WHERE entity_type = %s",
                (ETYPE,),
            )
            row = cur.fetchone()
            assert row["work_item_id"] is not None
            assert row["resolved_at"] is None
            wi = row["work_item_id"]
            cur.execute("SELECT status FROM work_item WHERE id = %s", (wi,))
            assert cur.fetchone()["status"] == "draft"
    except psycopg2.ProgrammingError:
        pytest.skip("tables not present")
    finally:
        _cleanup(conn, org_id, ids)
        conn.close()


def test_sweep_idempotent():
    conn = _db()
    org_id, ids = _seed(conn)
    try:
        first = esc.sweep_and_escalate(conn, sla_target_hours=4.0, threshold=0.5, org_id=str(org_id))
        second = esc.sweep_and_escalate(conn, sla_target_hours=4.0, threshold=0.5, org_id=str(org_id))
        assert first == 1
        assert second == 0
    except psycopg2.ProgrammingError:
        pytest.skip("tables not present")
    finally:
        _cleanup(conn, org_id, ids)
        conn.close()


def test_resolve_escalation():
    conn = _db()
    org_id, ids = _seed(conn)
    try:
        esc.sweep_and_escalate(conn, sla_target_hours=4.0, threshold=0.5, org_id=str(org_id))
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM process_escalation WHERE entity_type = %s", (ETYPE,))
            esc_id = cur.fetchone()[0]
        assert esc.resolve_escalation(conn, str(esc_id)) == 1
        with conn.cursor() as cur:
            cur.execute("SELECT resolved_at FROM process_escalation WHERE id = %s", (esc_id,))
            assert cur.fetchone()[0] is not None
    except psycopg2.ProgrammingError:
        pytest.skip("tables not present")
    finally:
        _cleanup(conn, org_id, ids)
        conn.close()


def test_work_item_due_at_escalation():
    """work_item instances use their own due_at as the SLA target."""
    conn = _db()
    org_id = uuid.uuid4()
    w1 = uuid.uuid5(uuid.NAMESPACE_DNS, "esc-wi-W1")
    w2 = uuid.uuid5(uuid.NAMESPACE_DNS, "esc-wi-W2")
    now = datetime.now(timezone.utc)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO organization (id, org_key, name, org_type, status, "
                "created_at, updated_at) VALUES (%s, %s, %s, %s, %s, now(), now())",
                (str(org_id), "esc-wi-org", "ESC WI Org", "cooperative", "active"),
            )
            cur.execute(
                "INSERT INTO work_item (id, organization_id, title, created_by_type, "
                "status, priority, version, assignee_id, assignee_type, due_at) "
                "VALUES (%s, %s, %s, %s, 'assigned', 'medium', 1, %s::uuid, 'staff', %s)",
                (str(w2), str(org_id), "ESC WI", "system", str(org_id),
                 now - timedelta(hours=1)),
            )
        base = now - timedelta(days=1)
        train = [
            (w1, None, "draft", base),
            (w1, "draft", "assigned", base + timedelta(hours=1)),
            (w1, "assigned", "in_progress", base + timedelta(hours=1.5)),
            (w1, "in_progress", "done", base + timedelta(hours=2)),
        ]
        inflight = [
            (w2, None, "draft", now - timedelta(hours=3)),
            (w2, "draft", "assigned", now - timedelta(hours=2)),
        ]
        with conn.cursor() as cur:
            for eid, frm, to, ts in train + inflight:
                cur.execute(
                    "INSERT INTO lifecycle_transition "
                    "(entity_type, entity_id, from_status, to_status, transitioned_at) "
                    "VALUES ('work_item', %s, %s, %s, %s)",
                    (str(eid), frm, to, ts),
                )
        conn.commit()
        at_risk = esc.find_at_risk(conn, 72.0, 0.5)
        ids = {r["entity_type"] + ":" + r["entity_id"] for r in at_risk}
        assert f"work_item:{w2}" in ids
        assert f"work_item:{w1}" not in ids
    except psycopg2.ProgrammingError:
        pytest.skip("tables not present")
    finally:
        conn.rollback()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM work_item WHERE id = %s::uuid", (str(w2),))
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (str(org_id),))
                cur.execute(
                    "DELETE FROM organization WHERE org_key = 'esc-wi-org'"
                )
                cur.execute(
                    "DELETE FROM lifecycle_transition WHERE entity_type = 'work_item' "
                    "AND entity_id = ANY(%s::uuid[])", ([str(w1), str(w2)],))
            conn.commit()
        finally:
            conn.close()
