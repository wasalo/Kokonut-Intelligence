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
