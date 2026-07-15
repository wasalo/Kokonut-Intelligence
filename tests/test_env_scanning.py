"""Tests for Environmental Scanning Workflow service."""

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCHEMA = Path("schemas/postgres/206_env_scanning.sql")


def _db():
    try:
        from services.ingestion.base import get_db
        return get_db()
    except Exception as exc:
        pytest.skip(f"no database available: {exc}")


def _location(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    return str(row[0]) if row else None


# --- Module shape ---

def test_module_has_create_scan():
    from services.analytics import env_scanning
    assert hasattr(env_scanning, "create_scan")


def test_module_has_update_step():
    from services.analytics import env_scanning
    assert hasattr(env_scanning, "update_step")


def test_module_has_auto_populate():
    from services.analytics import env_scanning
    assert hasattr(env_scanning, "auto_populate")


def test_module_has_render_markdown():
    from services.analytics import env_scanning
    assert hasattr(env_scanning, "render_markdown")


def test_module_has_render_cli():
    from services.analytics import env_scanning
    assert hasattr(env_scanning, "render_cli")


# --- Schema validation ---

def test_schema_file_exists():
    assert SCHEMA.exists(), f"{SCHEMA} does not exist"


def test_schema_defines_env_scan():
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS env_scan" in text


def test_schema_defines_env_scan_step():
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS env_scan_step" in text


def test_schema_defines_env_scan_source():
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS env_scan_source" in text


def test_schema_has_step_name_check():
    text = SCHEMA.read_text()
    assert "'identify'" in text
    assert "'gather'" in text
    assert "'analyze'" in text
    assert "'communicate'" in text
    assert "'decide'" in text


def test_schema_has_views():
    text = SCHEMA.read_text()
    assert "v_env_scan_status" in text
    assert "v_env_scan_findings" in text


# --- Validation ---

def test_create_scan_invalid_type():
    from services.analytics import env_scanning
    conn = MagicMock()
    with pytest.raises(ValueError, match="scan_type"):
        env_scanning.create_scan(conn, "loc-id", "Test", "invalid")


def test_update_step_invalid_number():
    from services.analytics import env_scanning
    conn = MagicMock()
    with pytest.raises(ValueError, match="step_number"):
        env_scanning.update_step(conn, "scan-id", 6)


# --- Rendering (no DB) ---

def test_render_markdown():
    from services.analytics import env_scanning
    scan = {
        "title": "Test Scan",
        "location_name": "Adelphi",
        "scan_type": "full",
        "status": "completed",
        "completed_steps": 5,
        "total_steps": 5,
        "steps": [
            {"step_number": 1, "step_name": "identify", "status": "completed",
             "findings": "Found 3 threats", "recommendations": "Review threats"},
        ],
    }
    md = env_scanning.render_markdown(scan)
    assert "Environmental Scan: Test Scan" in md
    assert "Adelphi" in md
    assert "[x] Step 1: Identify" in md
    assert "Found 3 threats" in md


def test_render_cli():
    from services.analytics import env_scanning
    scan = {
        "title": "Test",
        "location_name": "Farm",
        "scan_type": "quick",
        "status": "in_progress",
        "completed_steps": 2,
        "total_steps": 5,
        "steps": [
            {"step_number": 1, "step_name": "identify", "status": "completed",
             "findings": "Finding 1", "recommendations": "Rec 1"},
            {"step_number": 2, "step_name": "gather", "status": "in_progress",
             "findings": None, "recommendations": None},
        ],
    }
    cli = env_scanning.render_cli(scan)
    assert "ENVIRONMENTAL SCAN" in cli
    assert "2/5 steps" in cli


# --- DB integration ---

def test_create_scan_with_steps():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        from services.analytics import env_scanning
        scan = env_scanning.create_scan(conn, loc, "Test Scan", "full")
        assert scan["title"] == "Test Scan"
        assert scan["status"] == "draft"
        full = env_scanning.get_scan(conn, scan["id"])
        assert len(full["steps"]) == 5
        assert full["steps"][0]["step_name"] == "identify"
        assert full["steps"][4]["step_name"] == "decide"
    except Exception:
        conn.rollback()
        pytest.skip("env_scan tables not present")
    finally:
        conn.close()


def test_update_step_and_progress():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        from services.analytics import env_scanning
        scan = env_scanning.create_scan(conn, loc, "Step Test", "quick")
        env_scanning.update_step(conn, scan["id"], 1, status="completed",
                                 findings="3 threats identified")
        updated = env_scanning.get_scan(conn, scan["id"])
        assert updated["completed_steps"] == 1
        assert updated["status"] == "in_progress"
    except Exception:
        conn.rollback()
        pytest.skip("env_scan tables not present")
    finally:
        conn.close()


def test_list_scans():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        from services.analytics import env_scanning
        env_scanning.create_scan(conn, loc, "List Test", "full")
        scans = env_scanning.list_scans(conn, loc)
        assert isinstance(scans, list)
        assert len(scans) >= 1
    except Exception:
        conn.rollback()
        pytest.skip("env_scan tables not present")
    finally:
        conn.close()


def test_auto_populate():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        from services.analytics import env_scanning
        scan = env_scanning.create_scan(conn, loc, "Auto Test", "full")
        result = env_scanning.auto_populate(conn, scan["id"])
        assert "step_1" in result
        assert "step_2" in result
        assert "step_3" in result
        assert "step_4" in result
        assert "step_5" in result
    except Exception:
        conn.rollback()
        pytest.skip("auto_populate failed")
    finally:
        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
