"""Tests for VSM flow-metric calculators and definitions."""

from unittest.mock import MagicMock, patch

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.metrics.calculators.governed_lead_time import compute_governed_lead_time
from services.metrics.calculators.first_time_through_yield import compute_first_time_through_yield
from services.metrics.calculators.rework_rate import compute_rework_rate


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


def _location_id(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    return str(row[0]) if row else None


def test_calculators_return_governed_shape():
    conn = _db()
    try:
        loc = _location_id(conn)
        if not loc:
            pytest.skip("no location rows available")
        for fn in (compute_governed_lead_time, compute_first_time_through_yield, compute_rework_rate):
            res = fn(conn, loc)
            assert isinstance(res, dict)
            assert {"value", "unit", "computation_method", "source_record_ids", "metadata"} <= set(res)
    except psycopg2.ProgrammingError:
        pytest.skip("lifecycle_transition ledger not present (migrations not applied)")
    finally:
        conn.close()


def test_flow_metric_definitions_seeded():
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT metric_key, category FROM metric_definition "
                "WHERE metric_key IN ('governed_lead_time_days','first_time_through_yield_pct','rework_rate_pct')"
            )
            rows = {r[0]: r[1] for r in cur.fetchall()}
        assert set(rows) == {
            "governed_lead_time_days",
            "first_time_through_yield_pct",
            "rework_rate_pct",
        }
        assert rows["governed_lead_time_days"] == "lead_time"
        assert rows["first_time_through_yield_pct"] == "quality"
        assert rows["rework_rate_pct"] == "quality"
    except psycopg2.ProgrammingError:
        pytest.skip("metric_definition.category not present (migrations not applied)")
    finally:
        conn.close()
