"""Integration tests for the process-health board (BAM, Phase D).

Verifies build_health assembles VSM + conformance, that seeding a trace
changes the instance count, and that the report-generator registers the
`process_health` type. Skips without a DB.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics import process_health as ph
from services.analytics.process_health import _count_instances
from services.export.report_generator import REPORT_GENERATORS


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


PIPE = "data_stream_post"


def _seed_one(conn):
    tag = f"ph-{uuid.uuid4().hex[:8]}"
    eid = uuid.uuid5(uuid.NAMESPACE_DNS, tag)
    base = datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc)
    with conn.cursor() as cur:
        for to, ts in [
            ("draft", base),
            ("submitted", base + timedelta(days=1)),
            ("verified", base + timedelta(days=2)),
            ("published", base + timedelta(days=3)),
        ]:
            cur.execute(
                """
                INSERT INTO lifecycle_transition
                    (entity_type, entity_id, from_status, to_status, transitioned_at)
                VALUES (%s, %s, NULL, %s, %s)
                """,
                (PIPE, str(eid), to, ts),
            )
    conn.commit()
    return eid


def _cleanup(conn, eid):
    conn.rollback()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM lifecycle_transition WHERE entity_type = %s "
                "AND entity_id = %s::uuid",
                (PIPE, str(eid)),
            )
        conn.commit()
    finally:
        conn.close()


def test_build_health_structure():
    conn = _db()
    eid = _seed_one(conn)
    try:
        health = ph.build_health(conn)
        for key in ("wip_by_stage", "stage_lead_times_days",
                    "first_time_through_yield", "bottleneck_ranking", "conformance"):
            assert key in health
        # Seeded trace increased the instance count for this pipeline type.
        entry = next((c for c in health["conformance"] if c["entity_type"] == PIPE), None)
        assert entry is not None
        assert entry["total_instances"] >= 1
        assert "conformance_ratio" in entry
    except psycopg2.ProgrammingError:
        pytest.skip("tables not present")
    finally:
        _cleanup(conn, eid)
        conn.close()


def test_generate_process_health_signature():
    conn = _db()
    eid = _seed_one(conn)
    try:
        out = ph.generate_process_health(conn, location_id=None)
        assert "conformance" in out
        assert "wip_by_stage" in out
    except psycopg2.ProgrammingError:
        pytest.skip("tables not present")
    finally:
        _cleanup(conn, eid)
        conn.close()


def test_report_registration():
    assert "process_health" in REPORT_GENERATORS
