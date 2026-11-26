"""Tests for VSM flow-metric calculators and definitions."""

import re
from pathlib import Path
from unittest.mock import MagicMock

import psycopg2
import pytest

from services.ingestion.base import get_db
from services.metrics.calculators.first_time_through_yield import compute_first_time_through_yield
from services.metrics.calculators.governed_lead_time import compute_governed_lead_time
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


def test_flow_metric_seed_is_selected_for_default_bootstrap():
    seed_script = (Path(__file__).resolve().parents[1] / "scripts/seed.sh").read_text(
        encoding="utf-8"
    )
    default_seed_block = re.search(
        r"\nelse\n    CURATED_SEEDS=\((.*?)\n    \)\nfi",
        seed_script,
        flags=re.DOTALL,
    )

    assert default_seed_block is not None
    assert '"schemas/seeds/103_flow_metrics.sql"' in default_seed_block.group(1)


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


def test_first_time_through_query_is_read_only_and_location_bound():
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = {"total": 2, "fty": 1}

    result = compute_first_time_through_yield(
        connection, "location-1", "2026-10-01", "2026-10-31"
    )

    query, params = cursor.execute.call_args.args
    assert "WITH entity_loc AS" in query
    assert "WHERE location_id = %(loc)s" in query
    assert "farm_activity_source_eligible_for_use" in query
    assert "LEFT JOIN rej r USING (entity_type, entity_id)" in query
    assert not any(token in query.upper() for token in ("INSERT INTO", "UPDATE ", "DELETE FROM", "MERGE INTO"))
    assert params == {"loc": "location-1", "ps": "2026-10-01", "pe": "2026-10-31"}
    assert result["value"] == 50.0


def test_governed_lead_time_query_is_read_only_and_location_bound():
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = {"avg_lead_days": 1.25, "n": 3}

    result = compute_governed_lead_time(
        connection, "location-1", "2026-10-01", "2026-10-31"
    )

    query, params = cursor.execute.call_args.args
    assert "WITH entity_loc AS" in query
    assert "WHERE location_id = %(loc)s" in query
    assert "farm_activity_source_eligible_for_use" in query
    assert not any(token in query.upper() for token in ("INSERT INTO", "UPDATE ", "DELETE FROM", "MERGE INTO"))
    assert params == {"loc": "location-1", "ps": "2026-10-01", "pe": "2026-10-31"}
    assert result["value"] == 1.25


def test_rework_rate_query_is_read_only_and_location_bound():
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = {
        "total": 2,
        "reworked": 1,
        "source_ids": ["source-1"],
        "reworked_source_ids": ["source-1"],
    }

    result = compute_rework_rate(
        connection, "location-1", "2026-10-01", "2026-10-31"
    )

    query, params = cursor.execute.call_args.args
    assert "WITH entity_loc AS" in query
    assert "WHERE location_id = %(loc)s" in query
    assert "farm_activity_source_eligible_for_use" in query
    assert not any(token in query.upper() for token in ("INSERT INTO", "UPDATE ", "DELETE FROM", "MERGE INTO"))
    assert params == {"loc": "location-1", "ps": "2026-10-01", "pe": "2026-10-31"}
    assert result["value"] == 50.0
    assert result["source_record_ids"] == ["source-1"]
