"""Tests for Value Stream Definitions."""

import uuid
import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics.value_stream_defs import (
    create_stream, get_stream, list_streams, update_stream,
    create_stage, get_stage, list_stages, update_stage,
    record_observation, get_observations,
    get_stream_performance, get_stream_summary, get_stream_with_stages,
)


def _db():
    try:
        return get_db()
    except Exception as exc:
        pytest.skip(f"no database available: {exc}")


def _purge(conn, stream_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM value_stream_stage_observation "
                     "WHERE stage_id IN (SELECT id FROM value_stream_stage WHERE stream_id = %s::uuid)",
                     (stream_id,))
        cur.execute("DELETE FROM value_stream_stage WHERE stream_id = %s::uuid", (stream_id,))
        cur.execute("DELETE FROM value_stream_definition WHERE id = %s::uuid", (stream_id,))
    conn.commit()


def test_create_stream():
    conn = _db()
    stream = create_stream(
        "Test Stream",
        description="A test stream",
        stakeholder_type="farmer",
        trigger_event="Activity recorded",
        end_state="Revenue received",
    )
    try:
        assert stream["name"] == "Test Stream"
        assert stream["stakeholder_type"] == "farmer"
        got = get_stream(stream["id"])
        assert got is not None
    finally:
        _purge(conn, stream["id"])


def test_list_streams():
    conn = _db()
    stream = create_stream("List Stream", stakeholder_type="buyer")
    try:
        streams = list_streams(stakeholder_type="buyer")
        assert any(s["id"] == stream["id"] for s in streams)
    finally:
        _purge(conn, stream["id"])


def test_update_stream():
    conn = _db()
    stream = create_stream("Update Stream")
    try:
        updated = update_stream(stream["id"], name="Updated Stream", status="deprecated")
        assert updated["name"] == "Updated Stream"
        assert updated["status"] == "deprecated"
    finally:
        _purge(conn, stream["id"])


def test_create_stage():
    conn = _db()
    stream = create_stream("Stage Stream")
    try:
        stage = create_stage(
            stream["id"],
            "Stage 1",
            description="First stage",
            sequence_order=1,
            process_key="farm_operations",
            target_lead_time_hours=24,
            target_fty_pct=90,
        )
        assert stage["name"] == "Stage 1"
        assert stage["sequence_order"] == 1
        assert stage["process_key"] == "farm_operations"
        got = get_stage(stage["id"])
        assert got is not None
    finally:
        _purge(conn, stream["id"])


def test_list_stages():
    conn = _db()
    stream = create_stream("Stage List Stream")
    s1 = create_stage(stream["id"], "S1", sequence_order=1)
    s2 = create_stage(stream["id"], "S2", sequence_order=2)
    try:
        stages = list_stages(stream["id"])
        assert len(stages) == 2
        assert stages[0]["sequence_order"] <= stages[1]["sequence_order"]
    finally:
        _purge(conn, stream["id"])


def test_update_stage():
    conn = _db()
    stream = create_stream("Update Stage Stream")
    stage = create_stage(stream["id"], "Old Name", sequence_order=1)
    try:
        updated = update_stage(stage["id"], name="New Name", target_lead_time_hours=48)
        assert updated["name"] == "New Name"
        assert updated["target_lead_time_hours"] == 48
    finally:
        _purge(conn, stream["id"])


def test_record_observation():
    conn = _db()
    stream = create_stream("Observe Stream")
    stage = create_stage(stream["id"], "Observe Stage", sequence_order=1)
    try:
        obs = record_observation(
            stage["id"],
            "farm_activity",
            str(uuid.uuid4()),
            actual_lead_time_hours=20,
            actual_fty_pct=95,
            notes="Good run",
        )
        assert obs["actual_lead_time_hours"] == 20
        assert obs["actual_fty_pct"] == 95
    finally:
        _purge(conn, stream["id"])


def test_get_observations():
    conn = _db()
    stream = create_stream("Obs List Stream")
    stage = create_stage(stream["id"], "Obs List Stage", sequence_order=1)
    eid = str(uuid.uuid4())
    record_observation(stage["id"], "test", eid, actual_lead_time_hours=10)
    record_observation(stage["id"], "test", eid, actual_lead_time_hours=15)
    try:
        obs = get_observations(stage["id"])
        assert len(obs) >= 2
    finally:
        _purge(conn, stream["id"])


def test_get_stream_with_stages():
    conn = _db()
    stream = create_stream("Full Stream")
    create_stage(stream["id"], "Full S1", sequence_order=1)
    create_stage(stream["id"], "Full S2", sequence_order=2)
    try:
        full = get_stream_with_stages(stream["id"])
        assert full is not None
        assert "stages" in full
        assert len(full["stages"]) == 2
    finally:
        _purge(conn, stream["id"])


def test_performance_view():
    conn = _db()
    stream = create_stream("Perf Stream")
    stage = create_stage(stream["id"], "Perf Stage", sequence_order=1)
    try:
        perf = get_stream_performance(stream["id"])
        assert isinstance(perf, list)
    except psycopg2.ProgrammingError:
        pytest.skip("view not present")
    finally:
        _purge(conn, stream["id"])


def test_summary_view():
    conn = _db()
    try:
        summary = get_stream_summary()
        assert isinstance(summary, list)
    except psycopg2.ProgrammingError:
        pytest.skip("view not present")
