"""Integration tests for services.systems.process_control (SPC).

Covers the pure control-limits math, KPI snapshot capture from the
lifecycle ledger, and out-of-control detection. Skips without a DB.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.systems import process_control as pc


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


ETYPE = "pc_test"


def _seed(conn):
    base = datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)
    rows = [
        ("A", None, "draft", base),
        ("A", "draft", "submitted", base + timedelta(days=1)),
        ("A", "submitted", "verified", base + timedelta(days=2)),
        ("A", "verified", "published", base + timedelta(days=3)),
        ("B", None, "draft", base),
        ("B", "draft", "submitted", base + timedelta(days=1)),
        ("B", "submitted", "verified", base + timedelta(days=1)),
        ("B", "verified", "published", base + timedelta(days=1)),
    ]
    ids = []
    with conn.cursor() as cur:
        for tag, frm, to, ts in rows:
            eid = uuid.uuid5(uuid.NAMESPACE_DNS, f"pc-{tag}")
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
        cur.execute("DELETE FROM process_kpi_snapshot WHERE entity_type = %s", (ETYPE,))
        cur.execute("DELETE FROM process_kpi_snapshot WHERE entity_type = 'pc_ctrl'")
    conn.commit()


def test_control_limits():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    lim = pc.control_limits(vals)
    assert lim["n"] == 5
    assert abs(lim["mean"] - 3.0) < 1e-6
    # sample stdev of [1..5] = sqrt(2.5) ~= 1.5811
    sd_expected = (2.5 ** 0.5)
    assert abs(lim["sd"] - sd_expected) < 1e-4
    assert abs(lim["ucl"] - (3.0 + 3 * sd_expected)) < 1e-3
    empty = pc.control_limits([])
    assert empty["n"] == 0


def test_capture_snapshots():
    conn = _db()
    ids = _seed(conn)
    try:
        n = pc.capture_snapshots(conn, ETYPE)
        assert n == 3  # cycle_time_days, fty_pct, rework_rate_pct
        with conn.cursor() as cur:
            cur.execute(
                "SELECT metric, value FROM process_kpi_snapshot WHERE entity_type = %s",
                (ETYPE,),
            )
            rows = {m: v for m, v in cur.fetchall()}
        assert "cycle_time_days" in rows
        assert abs(rows["fty_pct"] - 100.0) < 1e-6
        assert abs(rows["rework_rate_pct"] - 0.0) < 1e-6
    except psycopg2.ProgrammingError:
        pytest.skip("tables not present")
    finally:
        _cleanup(conn, ids)
        conn.close()


def test_evaluate_control():
    conn = _db()
    ids = _seed(conn)
    try:
        # Insert a series: many in-control points at 2.0 plus one outlier at 10.0
        # so a single extreme point breaches the 3-sigma limit.
        vals = [2.0] * 20 + [10.0]
        with conn.cursor() as cur:
            for i, v in enumerate(vals):
                cur.execute(
                    """INSERT INTO process_kpi_snapshot
                         (entity_type, metric, value, period, captured_at)
                       VALUES (%s, 'cycle_time_days', %s, 'p', %s)""",
                    ("pc_ctrl", v, datetime(2026, 4, 1, tzinfo=timezone.utc)
                     + timedelta(days=i)),
                )
        conn.commit()
        rep = pc.evaluate_control(conn, "pc_ctrl", "cycle_time_days")
        assert rep["out_of_control_count"] >= 1
        flagged = [p for p in rep["points"] if p["out_of_control"]]
        assert any(abs(p["value"] - 10.0) < 1e-6 for p in flagged)
    except psycopg2.ProgrammingError:
        pytest.skip("tables not present")
    finally:
        _cleanup(conn, ids)
        conn.close()
