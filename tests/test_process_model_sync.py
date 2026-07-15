"""Integration test for syncing process_model rows from workflow specs."""

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics import process_model_sync as sync


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


def test_sync_work_item_model():
    conn = _db()
    try:
        n = sync.sync_process_models(conn)
        assert n > 0
        cur = conn.cursor()
        cur.execute(
            "SELECT status, is_terminal, is_goal, is_initial FROM process_model "
            "WHERE entity_type = 'work_item' ORDER BY status"
        )
        rows = {r[0]: {"terminal": r[1], "goal": r[2], "initial": r[3]} for r in cur.fetchall()}
        assert set(rows) == {
            "draft", "assigned", "in_progress", "blocked", "done", "cancelled"
        }
        assert rows["done"]["terminal"] and rows["done"]["goal"]
        assert rows["draft"]["initial"]
        # Custom market_order and metric_value models retain their canonical states.
        cur.execute(
            "SELECT status, is_terminal, is_goal, is_initial FROM process_model "
            "WHERE entity_type = 'market_order' ORDER BY status"
        )
        market_rows = {
            r[0]: {"terminal": r[1], "goal": r[2], "initial": r[3]}
            for r in cur.fetchall()
        }
        assert set(market_rows) == {
            "pending", "confirmed", "shipped", "delivered", "cancelled"
        }
        assert market_rows["delivered"]["terminal"] and market_rows["delivered"]["goal"]
        assert market_rows["pending"]["initial"]
        cur.execute(
            "SELECT COUNT(*) FROM process_model WHERE entity_type = 'metric_value'"
        )
        assert cur.fetchone()[0] == 2
    except psycopg2.ProgrammingError:
        pytest.skip("process_model not present")
    finally:
        conn.close()
