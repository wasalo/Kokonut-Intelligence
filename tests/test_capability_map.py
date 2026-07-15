"""Tests for Business Architecture Capability Map."""

import uuid
import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics.capability_map import (
    create_capability, get_capability, list_capabilities, update_capability,
    map_process, unmap_process, get_capability_processes,
    map_service, unmap_service, get_capability_services,
    record_maturity, get_maturity_history,
    get_capability_dashboard, get_coverage_analysis, get_hierarchy,
)


def _db():
    try:
        return get_db()
    except Exception as exc:
        pytest.skip(f"no database available: {exc}")


def _purge(conn, cap_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM capability_maturity_assessment WHERE capability_id = %s::uuid", (cap_id,))
        cur.execute("DELETE FROM capability_service_map WHERE capability_id = %s::uuid", (cap_id,))
        cur.execute("DELETE FROM capability_process_map WHERE capability_id = %s::uuid", (cap_id,))
        cur.execute("DELETE FROM business_capability WHERE id = %s::uuid", (cap_id,))
    conn.commit()


def test_create_capability():
    conn = _db()
    cap = create_capability("Test Capability", description="Test", capability_type="core", guild_key="test_guild")
    cap_id = cap["id"]
    try:
        assert cap["name"] == "Test Capability"
        assert cap["capability_type"] == "core"
        assert cap["guild_key"] == "test_guild"
        assert cap["status"] == "active"
        # retrieve
        got = get_capability(cap_id)
        assert got is not None
        assert got["name"] == "Test Capability"
    finally:
        _purge(conn, cap_id)


def test_list_capabilities():
    conn = _db()
    cap = create_capability("List Test Cap", guild_key="test_list_guild")
    try:
        caps = list_capabilities(guild_key="test_list_guild")
        assert any(c["id"] == cap["id"] for c in caps)
    finally:
        _purge(conn, cap["id"])


def test_update_capability():
    conn = _db()
    cap = create_capability("Update Test Cap", guild_key="test_update_guild")
    try:
        updated = update_capability(cap["id"], name="Updated Cap", maturity_level=4)
        assert updated["name"] == "Updated Cap"
        assert updated["maturity_level"] == 4
    finally:
        _purge(conn, cap["id"])


def test_map_process():
    conn = _db()
    cap = create_capability("Process Map Test", guild_key="test_pm_guild")
    try:
        result = map_process(cap["id"], "farm_operations")
        assert result["process_key"] == "farm_operations"
        procs = get_capability_processes(cap["id"])
        assert len(procs) >= 1
        assert any(p["process_key"] == "farm_operations" for p in procs)
    finally:
        _purge(conn, cap["id"])


def test_unmap_process():
    conn = _db()
    cap = create_capability("Unmap Process Test", guild_key="test_upm_guild")
    map_process(cap["id"], "farm_operations")
    try:
        ok = unmap_process(cap["id"], "farm_operations")
        assert ok
        procs = get_capability_processes(cap["id"])
        assert not any(p["process_key"] == "farm_operations" for p in procs)
    finally:
        _purge(conn, cap["id"])


def test_map_service():
    conn = _db()
    cap = create_capability("Service Map Test", guild_key="test_sm_guild")
    try:
        result = map_service(cap["id"], "gateway")
        assert result["service_name"] == "gateway"
        svcs = get_capability_services(cap["id"])
        assert len(svcs) >= 1
        assert any(s["service_name"] == "gateway" for s in svcs)
    finally:
        _purge(conn, cap["id"])


def test_unmap_service():
    conn = _db()
    cap = create_capability("Unmap Service Test", guild_key="test_usm_guild")
    map_service(cap["id"], "gateway")
    try:
        ok = unmap_service(cap["id"], "gateway")
        assert ok
        svcs = get_capability_services(cap["id"])
        assert not any(s["service_name"] == "gateway" for s in svcs)
    finally:
        _purge(conn, cap["id"])


def test_maturity_assessment():
    conn = _db()
    cap = create_capability("Maturity Test", guild_key="test_mat_guild")
    try:
        ass = record_maturity(cap["id"], 3, assessed_by="tester", notes="Initial")
        assert ass["maturity_level"] == 3
        assert ass["assessed_by"] == "tester"
        history = get_maturity_history(cap["id"])
        assert len(history) >= 1
        assert history[0]["maturity_level"] == 3
    finally:
        _purge(conn, cap["id"])


def test_dashboard():
    conn = _db()
    try:
        dash = get_capability_dashboard()
        assert isinstance(dash, list)
    except psycopg2.ProgrammingError:
        pytest.skip("view not present")


def test_coverage_analysis():
    conn = _db()
    try:
        cov = get_coverage_analysis()
        assert "capabilities" in cov
        assert "unmapped_processes" in cov
        assert "unmapped_services" in cov
        assert "total_capabilities" in cov
    except psycopg2.ProgrammingError:
        pytest.skip("view not present")


def test_hierarchy():
    conn = _db()
    cap = create_capability("Parent Cap", capability_type="strategic", guild_key="test_hier_guild")
    child = create_capability("Child Cap", parent_id=cap["id"], guild_key="test_hier_guild")
    try:
        tree = get_hierarchy()
        assert isinstance(tree, list)
        # find parent in tree
        parent_nodes = [n for n in tree if n["id"] == cap["id"]]
        assert len(parent_nodes) == 1
        assert any(c["id"] == child["id"] for c in parent_nodes[0]["_children"])
    finally:
        _purge(conn, child["id"])
        _purge(conn, cap["id"])
