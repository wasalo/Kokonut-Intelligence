"""Integration tests for services.analytics.process_mining against the real ledger.

Exercises variant discovery, conformance classification, case timelines,
and cycle-time distribution over lifecycle_transition. Skips when no DB
or the process_model / lifecycle_transition tables are unavailable, matching
the repo offline-test convention.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics import process_mining as pm


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


ETYPE = "pm_test"


def _seed(conn):
    base = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    rows = [
        # A: conforming happy path
        ("A", None, "draft", base),
        ("A", "draft", "submitted", base + timedelta(days=1)),
        ("A", "submitted", "verified", base + timedelta(days=2)),
        ("A", "verified", "published", base + timedelta(days=3)),
        # B: illegal skip (draft -> published)
        ("B", None, "draft", base),
        ("B", "draft", "published", base + timedelta(days=1)),
        # C: transition out of terminal (published -> rejected)
        ("C", None, "draft", base),
        ("C", "draft", "submitted", base + timedelta(days=1)),
        ("C", "submitted", "verified", base + timedelta(days=2)),
        ("C", "verified", "published", base + timedelta(days=3)),
        ("C", "published", "rejected", base + timedelta(days=4)),
    ]
    ids = []
    with conn.cursor() as cur:
        for tag, frm, to, ts in rows:
            eid = uuid.uuid5(uuid.NAMESPACE_DNS, f"pm-{tag}")
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


def test_discover_variants():
    conn = _db()
    ids = _seed(conn)
    try:
        variants = pm.discover_variants(conn, entity_type=ETYPE)
        by_sig = {v["variant_signature"]: v for v in variants}
        happy = by_sig.get("draft>submitted>verified>published")
        assert happy is not None, "happy-path variant missing"
        assert happy["is_conforming"] is True
        assert happy["instance_count"] >= 1
        skip = by_sig.get("draft>published")
        assert skip is not None
        assert skip["is_conforming"] is False
    except psycopg2.ProgrammingError:
        pytest.skip("lifecycle_transition / process_model not present")
    finally:
        _cleanup(conn, ids)
        conn.close()


def test_classify_conformance():
    conn = _db()
    try:
        model = pm.load_model(conn)
        if not model:
            pytest.skip("process_model not seeded")
        ok, reasons = pm.classify_conformance(
            ["draft", "submitted", "verified", "published"], model
        )
        assert ok is True and reasons == []
        bad, reasons = pm.classify_conformance(
            ["draft", "published"], model
        )
        assert bad is False
        assert any("illegal transition" in r for r in reasons)
    except psycopg2.ProgrammingError:
        pytest.skip("process_model not present")
    finally:
        conn.close()


def test_check_conformance():
    conn = _db()
    ids = _seed(conn)
    try:
        findings = pm.check_conformance(conn, entity_type=ETYPE)
        bad_ids = {f["entity_id"] for f in findings}
        a_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "pm-A"))
        b_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "pm-B"))
        c_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "pm-C"))
        assert a_id not in bad_ids, "conforming trace flagged"
        assert b_id in bad_ids
        assert c_id in bad_ids
    except psycopg2.ProgrammingError:
        pytest.skip("lifecycle_transition / process_model not present")
    finally:
        _cleanup(conn, ids)
        conn.close()


def test_case_timeline():
    conn = _db()
    ids = _seed(conn)
    try:
        a_id = uuid.uuid5(uuid.NAMESPACE_DNS, "pm-A")
        tl = pm.case_timeline(conn, str(a_id))
        assert len(tl) == 4
        assert tl[0]["duration_seconds"] is None
        assert tl[1]["duration_seconds"] == 86400.0
        assert tl[-1]["to_status"] == "published"
    except psycopg2.ProgrammingError:
        pytest.skip("lifecycle_transition not present")
    finally:
        _cleanup(conn, ids)
        conn.close()


def test_cycle_time_distribution():
    conn = _db()
    ids = _seed(conn)
    try:
        dist = pm.cycle_time_distribution(conn, entity_type=ETYPE)
        a_id = uuid.uuid5(uuid.NAMESPACE_DNS, "pm-A")
        match = [d for d in dist if d["entity_id"] == str(a_id)]
        assert match, "published instance missing from cycle times"
        assert abs(match[0]["cycle_time_days"] - 3.0) < 1e-6
    except psycopg2.ProgrammingError:
        pytest.skip("lifecycle_transition not present")
    finally:
        _cleanup(conn, ids)
        conn.close()
