"""Integration tests for services.analytics.predictive_bpm against the real ledger.

Builds a small training set of published instances plus one in-flight
instance, then checks remaining-time prediction, SLA-breach probability,
and the breaches/forecasts queries. Skips without a DB.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics import predictive_bpm as pp


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


ETYPE = "pp_test"


def _seed(conn):
    base = datetime(2026, 2, 1, 8, 0, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    rows = [
        # X1 published in 3h
        ("X1", None, "draft", base),
        ("X1", "draft", "submitted", base + timedelta(hours=1)),
        ("X1", "submitted", "verified", base + timedelta(hours=2)),
        ("X1", "verified", "published", base + timedelta(hours=3)),
        # X2 published in 6h
        ("X2", None, "draft", base),
        ("X2", "draft", "submitted", base + timedelta(hours=2)),
        ("X2", "submitted", "verified", base + timedelta(hours=4)),
        ("X2", "verified", "published", base + timedelta(hours=6)),
        # Y in-flight: currently 'submitted', 1h old
        ("Y", None, "draft", now - timedelta(hours=2)),
        ("Y", "draft", "submitted", now - timedelta(hours=1)),
    ]
    ids = []
    with conn.cursor() as cur:
        for tag, frm, to, ts in rows:
            eid = uuid.uuid5(uuid.NAMESPACE_DNS, f"pp-{tag}")
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
    return ids


def _cleanup(conn, ids):
    with conn.cursor() as cur:
        for etype, eid in ids:
            cur.execute(
                "DELETE FROM lifecycle_transition WHERE entity_type = %s AND entity_id = %s",
                (etype, str(eid)),
            )
    conn.commit()


def test_predict_remaining():
    conn = _db()
    ids = _seed(conn)
    try:
        # median of submitted remaining times [2h, 4h] = 3h
        rem = pp.predict_remaining(conn, ETYPE, "submitted")
        assert abs(rem - 3.0) < 1e-6
    except psycopg2.ProgrammingError:
        pytest.skip("lifecycle_transition not present")
    finally:
        _cleanup(conn, ids)
        conn.close()


def test_predict_with_sla():
    conn = _db()
    ids = _seed(conn)
    try:
        out = pp.predict(conn, ETYPE, "submitted", age_hours=1.0, sla_target_hours=4.0)
        assert abs(out["predicted_remaining_hours"] - 3.0) < 1e-6
        # totals [3,6]; P(total > 4) = 1/2 = 0.5
        assert abs(out["breach_probability"] - 0.5) < 1e-6
    except psycopg2.ProgrammingError:
        pytest.skip("lifecycle_transition not present")
    finally:
        _cleanup(conn, ids)
        conn.close()


def test_breaches():
    conn = _db()
    ids = _seed(conn)
    try:
        found = pp.breaches(conn, ETYPE, sla_target_hours=4.0, threshold=0.5)
        y_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "pp-Y"))
        assert any(f["entity_id"] == y_id for f in found)
        x1 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "pp-X1"))
        assert all(f["entity_id"] != x1 for f in found), "terminal instance leaked"
    except psycopg2.ProgrammingError:
        pytest.skip("lifecycle_transition not present")
    finally:
        _cleanup(conn, ids)
        conn.close()


def test_persist_forecasts():
    conn = _db()
    ids = _seed(conn)
    try:
        n = pp.persist_forecasts(conn, ETYPE, sla_target_hours=4.0)
        assert n == 1  # only Y is in-flight
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM predictive_process_forecast WHERE entity_type = %s",
                (ETYPE,),
            )
            assert cur.fetchone()[0] == 1
    except psycopg2.ProgrammingError:
        pytest.skip("tables not present")
    finally:
        _cleanup(conn, ids)
        conn.close()
