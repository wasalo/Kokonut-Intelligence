"""Integration tests for per-entity-type BPM state models (Phase F).

Covers: per-type conformance (work_item), per-type prediction/cycle time
(market_order), the metric_value verified->draft/verified trigger, and the
work_item status trigger feeding the ledger.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics import process_mining as pm
from services.analytics import predictive_bpm as pp


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


def _purge(conn, entity_type, entity_ids):
    """Idempotent pre-test cleanup so re-runs never accumulate residue."""
    ids = [str(i) for i in entity_ids]
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM lifecycle_transition WHERE entity_type = %s "
            "AND entity_id = ANY(%s::uuid[])",
            (entity_type, ids),
        )
        for eid in ids:
            cur.execute("DELETE FROM metric_value WHERE id = %s::uuid", (eid,))
            cur.execute("DELETE FROM work_item WHERE id = %s::uuid", (eid,))
            cur.execute("DELETE FROM organization WHERE id = %s::uuid", (eid,))
            cur.execute(
                "DELETE FROM metric_definition WHERE id = %s::uuid", (eid,)
            )
    conn.commit()


def _safe_cleanup(conn, fn):
    """Roll back any aborted transaction, then run cleanup deletes."""
    conn.rollback()
    try:
        fn(conn)
        conn.commit()
    finally:
        conn.close()


def _del_lt(cur, entity_type, eid):
    cur.execute(
        "DELETE FROM lifecycle_transition WHERE entity_type = %s "
        "AND entity_id = %s::uuid",
        (entity_type, str(eid)),
    )


# --- work_item conformance ------------------------------------------------

def test_work_item_conformance():
    conn = _db()
    ids = [uuid.uuid5(uuid.NAMESPACE_DNS, f"wi-{t}") for t in ("A", "B")]
    _purge(conn, "work_item", ids)

    base = datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)
    rows = [
        ("A", None, "draft", base),
        ("A", "draft", "assigned", base + timedelta(hours=1)),
        ("A", "assigned", "in_progress", base + timedelta(hours=2)),
        ("A", "in_progress", "done", base + timedelta(hours=5)),
        # illegal skip
        ("B", None, "draft", base),
        ("B", "draft", "done", base + timedelta(hours=1)),
    ]
    with conn.cursor() as cur:
        for tag, frm, to, ts in rows:
            eid = uuid.uuid5(uuid.NAMESPACE_DNS, f"wi-{tag}")
            cur.execute(
                "INSERT INTO lifecycle_transition "
                "(entity_type, entity_id, from_status, to_status, transitioned_at) "
                "VALUES ('work_item', %s, %s, %s, %s)",
                (str(eid), frm, to, ts),
            )
    conn.commit()

    def cleanup(c):
        with c.cursor() as cur:
            for i in ids:
                _del_lt(cur, "work_item", i)

    try:
        # per-type model: happy path is conforming, draft->done is illegal.
        findings = pm.check_conformance(conn, entity_type="work_item")
        bad = {f["entity_id"] for f in findings}
        a_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "wi-A"))
        b_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "wi-B"))
        assert a_id not in bad
        assert b_id in bad
        assert any("illegal transition" in r for r in next(
            f["reasons"] for f in findings if f["entity_id"] == b_id))
        # goal state is 'done', not 'published'
        assert pm.goal_state(pm.load_model(conn, "work_item")) == "done"
    except psycopg2.ProgrammingError:
        pytest.skip("process_model not present")
    finally:
        _safe_cleanup(conn, cleanup)


# --- market_order prediction ---------------------------------------------

def test_market_order_prediction():
    conn = _db()
    ids = [uuid.uuid5(uuid.NAMESPACE_DNS, f"mo-{t}") for t in ("M1", "M2", "MY")]
    _purge(conn, "market_order", ids)

    base = datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    rows = [
        # M1 delivered in 5h
        ("M1", None, "pending", base),
        ("M1", "pending", "confirmed", base + timedelta(hours=1)),
        ("M1", "confirmed", "shipped", base + timedelta(hours=3)),
        ("M1", "shipped", "delivered", base + timedelta(hours=5)),
        # M2 delivered in 10h
        ("M2", None, "pending", base),
        ("M2", "pending", "confirmed", base + timedelta(hours=2)),
        ("M2", "confirmed", "shipped", base + timedelta(hours=6)),
        ("M2", "shipped", "delivered", base + timedelta(hours=10)),
        # MY in-flight: confirmed, 1h old
        ("MY", None, "pending", now - timedelta(hours=2)),
        ("MY", "pending", "confirmed", now - timedelta(hours=1)),
    ]
    with conn.cursor() as cur:
        for tag, frm, to, ts in rows:
            eid = uuid.uuid5(uuid.NAMESPACE_DNS, f"mo-{tag}")
            cur.execute(
                "INSERT INTO lifecycle_transition "
                "(entity_type, entity_id, from_status, to_status, transitioned_at) "
                "VALUES ('market_order', %s, %s, %s, %s)",
                (str(eid), frm, to, ts),
            )
    conn.commit()

    def cleanup(c):
        with c.cursor() as cur:
            for i in ids:
                _del_lt(cur, "market_order", i)

    try:
        # median of confirmed->delivered remaining [4h, 8h] = 6h
        rem = pp.predict_remaining(conn, "market_order", "confirmed")
        assert abs(rem - 6.0) < 1e-6
        # cycle-time distribution uses the 'delivered' goal
        dist = pm.cycle_time_distribution(conn, entity_type="market_order")
        m_ids = {str(uuid.uuid5(uuid.NAMESPACE_DNS, f"mo-{t}")) for t in ("M1", "M2")}
        matched = [d for d in dist if d["entity_id"] in m_ids]
        assert len(matched) == 2
    except psycopg2.ProgrammingError:
        pytest.skip("process_model not present")
    finally:
        _safe_cleanup(conn, cleanup)


# --- metric_value verified -> draft/verified trigger ----------------------

def test_metric_value_trigger():
    conn = _db()
    mid = uuid.uuid5(uuid.NAMESPACE_DNS, "mv-test")
    _purge(conn, "metric_value", [mid])
    # metric_value.metric_id is a FK -> metric_definition.
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO metric_definition (id, metric_key, display_name) "
            "VALUES (%s, 'mv-test-key', 'MV Test') ON CONFLICT (id) DO NOTHING",
            (str(mid),),
        )

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO metric_value (id, metric_id, value, unit, computed_at, verified) "
            "VALUES (%s, %s, 1.0, 'kg', now(), false)",
            (str(mid), str(mid)),
        )
    conn.commit()

    def cleanup(c):
        with c.cursor() as cur:
            cur.execute("DELETE FROM metric_value WHERE id = %s::uuid", (str(mid),))
            _del_lt(cur, "metric_value", mid)
            cur.execute(
                "DELETE FROM metric_definition WHERE id = %s::uuid", (str(mid),)
            )

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT from_status, to_status FROM lifecycle_transition "
                "WHERE entity_type = 'metric_value' AND entity_id = %s::uuid "
                "ORDER BY transitioned_at",
                (str(mid),),
            )
            trans = cur.fetchall()
        assert any(t[1] == "draft" for t in trans), "insert should record draft"
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE metric_value SET verified = true, verified_by = %s::uuid, "
                "verified_at = now() WHERE id = %s::uuid",
                (str(mid), str(mid)),
            )
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT from_status, to_status FROM lifecycle_transition "
                "WHERE entity_type = 'metric_value' AND entity_id = %s::uuid "
                "ORDER BY transitioned_at",
                (str(mid),),
            )
            trans = cur.fetchall()
        assert ("draft", "verified") in [(t[0], t[1]) for t in trans]
    except psycopg2.ProgrammingError:
        pytest.skip("tables not present")
    finally:
        _safe_cleanup(conn, cleanup)


# --- work_item status trigger ---------------------------------------------

def test_work_item_status_trigger():
    conn = _db()
    org_id = uuid.uuid4()
    wid = uuid.uuid4()
    _purge(conn, "work_item", [wid, org_id])
    # Fixed org_key would collide across re-runs; purge by key too.
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM organization WHERE org_key = 'wi-trigger-org'"
        )
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO organization (id, org_key, name, org_type, status, "
            "created_at, updated_at) VALUES (%s, %s, %s, %s, %s, now(), now())",
            (str(org_id), "wi-trigger-org", "WI Trigger Org", "cooperative", "active"),
        )
        cur.execute(
            "INSERT INTO work_item (id, organization_id, title, created_by_type, "
            "status, priority, version) VALUES (%s, %s, %s, %s, 'draft', 'medium', 1)",
            (str(wid), str(org_id), "WI trigger", "system"),
        )
    conn.commit()

    def cleanup(c):
        with c.cursor() as cur:
            cur.execute("DELETE FROM work_item WHERE id = %s::uuid", (str(wid),))
            cur.execute("DELETE FROM organization WHERE id = %s::uuid", (str(org_id),))
            cur.execute("DELETE FROM organization WHERE org_key = 'wi-trigger-org'")
            _del_lt(cur, "work_item", wid)

    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE work_item SET status = 'assigned', assignee_id = %s::uuid, "
                "assignee_type = 'staff' WHERE id = %s::uuid",
                (str(org_id), str(wid)),
            )
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT from_status, to_status FROM lifecycle_transition "
                "WHERE entity_type = 'work_item' AND entity_id = %s::uuid",
                (str(wid),),
            )
            trans = cur.fetchall()
        assert ("draft", "assigned") in [(t[0], t[1]) for t in trans]
    except psycopg2.ProgrammingError:
        pytest.skip("tables not present")
    finally:
        _safe_cleanup(conn, cleanup)
