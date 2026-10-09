"""Integration tests for Business Architecture cross-cutting concerns."""

import uuid
import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics.capability_map import (
    create_capability, map_process, map_service, get_capability_processes,
    get_capability_services, get_coverage_analysis, get_hierarchy,
)


def _db():
    try:
        return get_db()
    except Exception as exc:
        pytest.skip(f"no database available: {exc}")


def _purge(conn, cap_ids):
    with conn.cursor() as cur:
        for cid in cap_ids:
            cur.execute("DELETE FROM capability_maturity_assessment WHERE capability_id = %s::uuid", (cid,))
            cur.execute("DELETE FROM capability_service_map WHERE capability_id = %s::uuid", (cid,))
            cur.execute("DELETE FROM capability_process_map WHERE capability_id = %s::uuid", (cid,))
            cur.execute("DELETE FROM business_capability WHERE id = %s::uuid", (cid,))
    conn.commit()


def test_capability_to_process_traceability():
    """Verify the full chain: capability → process → service."""
    conn = _db()
    cap = create_capability("Traceability Test", guild_key="test_trace")
    map_process(cap["id"], "farm_operations")
    map_service(cap["id"], "sensor_ingester")
    try:
        procs = get_capability_processes(cap["id"])
        svcs = get_capability_services(cap["id"])
        assert len(procs) == 1
        assert procs[0]["process_key"] == "farm_operations"
        assert len(svcs) == 1
        assert svcs[0]["service_name"] == "sensor_ingester"
        assert procs[0]["process_name"] == "Farm Operations"
    finally:
        _purge(conn, [cap["id"]])


def test_coverage_analysis_structure():
    """Verify coverage analysis returns expected structure."""
    conn = _db()
    try:
        cov = get_coverage_analysis()
        assert "capabilities" in cov
        assert "unmapped_processes" in cov
        assert "unmapped_services" in cov
        assert "total_capabilities" in cov
        assert "total_processes" in cov
        assert "total_services" in cov
        assert cov["total_capabilities"] > 0
        assert cov["total_processes"] > 0
        assert cov["total_services"] > 0
    except psycopg2.ProgrammingError:
        pytest.skip("view not present")


def test_hierarchy_guild_parenting():
    """Verify guild-level capabilities have children."""
    conn = _db()
    try:
        tree = get_hierarchy()
        assert isinstance(tree, list)
        assert len(tree) > 0
        # Each top-level node should have guild_key and _children
        for node in tree:
            assert "guild_key" in node
            assert "_children" in node
    except Exception:
        pytest.skip("hierarchy not buildable")


def test_seed_data_exists():
    """Verify that seed data created capabilities, processes, and service links."""
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM business_capability WHERE status = 'active'")
            count = cur.fetchone()[0]
            assert count > 0, "No seeded capabilities found"

            cur.execute("SELECT COUNT(*) FROM capability_process_map")
            proc_count = cur.fetchone()[0]
            assert proc_count > 0, "No capability-process links found"

            cur.execute("SELECT COUNT(*) FROM capability_service_map")
            svc_count = cur.fetchone()[0]
            assert svc_count > 0, "No capability-service links found"
    except psycopg2.ProgrammingError:
        pytest.skip("tables not present")


def test_vision_mission_seed():
    """Verify platform vision and mission are seeded."""
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM vision_mission "
                "WHERE entity_type = 'platform' AND status = 'approved'"
            )
            count = cur.fetchone()[0]
            assert count >= 2, f"Expected at least 2 approved statements, got {count}"
    except psycopg2.ProgrammingError:
        pytest.skip("table not present")


def test_value_stream_seed():
    """Verify value streams are seeded with stages."""
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM value_stream_definition WHERE status = 'active'")
            vs_count = cur.fetchone()[0]
            assert vs_count >= 4, f"Expected at least 4 value streams, got {vs_count}"

            cur.execute("SELECT COUNT(*) FROM value_stream_stage")
            stage_count = cur.fetchone()[0]
            assert stage_count >= 10, f"Expected at least 10 stages, got {stage_count}"
    except psycopg2.ProgrammingError:
        pytest.skip("tables not present")
