"""Tests for Strategy Map (Balanced Scorecard)."""

import uuid
import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics.strategy_map import (
    create_strategy_entry, get_strategy_entry, list_strategy_entries,
    update_strategy_entry, create_initiative, get_initiative,
    list_initiatives, update_initiative,
    map_capability, get_strategy_capabilities,
    get_execution_dashboard, get_perspective_summary,
)
from services.analytics.capability_map import create_capability


def _db():
    try:
        return get_db()
    except Exception as exc:
        pytest.skip(f"no database available: {exc}")


def _purge(conn, entry_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM strategy_capability_map WHERE strategy_map_id = %s::uuid", (entry_id,))
        cur.execute("DELETE FROM strategy_initiative WHERE strategy_map_id = %s::uuid", (entry_id,))
        cur.execute("DELETE FROM strategy_map WHERE id = %s::uuid", (entry_id,))
    conn.commit()


def _purge_init(conn, init_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM strategy_initiative WHERE id = %s::uuid", (init_id,))
    conn.commit()


def test_create_strategy_entry():
    conn = _db()
    entry = create_strategy_entry(
        "Increase farm revenue by 20%",
        perspective="financial",
        strategic_theme="Growth",
        target_value=120,
        current_value=100,
        unit="%",
    )
    try:
        assert entry["perspective"] == "financial"
        assert entry["strategic_theme"] == "Growth"
        assert entry["target_value"] == 120
        got = get_strategy_entry(entry["id"])
        assert got is not None
        assert got["statement"] == "Increase farm revenue by 20%"
    finally:
        _purge(conn, entry["id"])


def test_list_strategy_entries():
    conn = _db()
    entry = create_strategy_entry("List Test", perspective="customer")
    try:
        entries = list_strategy_entries(perspective="customer")
        assert any(e["id"] == entry["id"] for e in entries)
    finally:
        _purge(conn, entry["id"])


def test_update_strategy_entry():
    conn = _db()
    entry = create_strategy_entry("Update Test", perspective="internal_process")
    try:
        updated = update_strategy_entry(entry["id"], status="at_risk", current_value=50)
        assert updated["status"] == "at_risk"
        assert updated["current_value"] == 50
    finally:
        _purge(conn, entry["id"])


def test_create_initiative():
    conn = _db()
    entry = create_strategy_entry("Initiative Parent", perspective="learning_growth")
    init = create_initiative(
        entry["id"],
        "Training Program",
        description="Staff upskilling",
        owner="HR",
    )
    try:
        assert init["name"] == "Training Program"
        assert init["owner"] == "HR"
        assert init["status"] == "planned"
        got = get_initiative(init["id"])
        assert got is not None
    finally:
        _purge_init(conn, init["id"])
        _purge(conn, entry["id"])


def test_map_strategy_capability():
    conn = _db()
    entry = create_strategy_entry("Capability bridge", perspective="internal_process")
    cap = create_capability("Strategy Test Capability", guild_key="test_strategy")
    try:
        mapped = map_capability(entry["id"], cap["id"], expected_impact="Faster delivery")
        assert mapped["contribution_type"] == "primary"
        capabilities = get_strategy_capabilities(entry["id"])
        assert capabilities[0]["capability_name"] == "Strategy Test Capability"
    finally:
        _purge(conn, entry["id"])
        with conn.cursor() as cur:
            cur.execute("DELETE FROM business_capability WHERE id = %s::uuid", (cap["id"],))
        conn.commit()


def test_list_initiatives():
    conn = _db()
    entry = create_strategy_entry("Init List Parent", perspective="financial")
    init = create_initiative(entry["id"], "List Initiative")
    try:
        inits = list_initiatives(strategy_map_id=entry["id"])
        assert any(i["id"] == init["id"] for i in inits)
    finally:
        _purge_init(conn, init["id"])
        _purge(conn, entry["id"])


def test_update_initiative():
    conn = _db()
    entry = create_strategy_entry("Init Update Parent", perspective="customer")
    init = create_initiative(entry["id"], "Update Initiative")
    try:
        updated = update_initiative(init["id"], status="in_progress", completion_pct=50)
        assert updated["status"] == "in_progress"
        assert updated["completion_pct"] == 50
    finally:
        _purge_init(conn, init["id"])
        _purge(conn, entry["id"])


def test_execution_dashboard():
    conn = _db()
    try:
        dash = get_execution_dashboard()
        assert isinstance(dash, list)
    except psycopg2.ProgrammingError:
        pytest.skip("view not present")


def test_perspective_summary():
    conn = _db()
    try:
        summary = get_perspective_summary()
        assert isinstance(summary, list)
    except psycopg2.ProgrammingError:
        pytest.skip("view not present")


def test_progress_calculation():
    conn = _db()
    entry = create_strategy_entry(
        "Progress Test",
        perspective="financial",
        target_value=100,
        current_value=75,
    )
    try:
        dash = get_execution_dashboard()
        mine = [d for d in dash if d["strategy_id"] == entry["id"]]
        assert len(mine) == 1
        assert mine[0]["progress_pct"] == 75.0
    finally:
        _purge(conn, entry["id"])
