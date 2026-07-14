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
        # market_order / metric_value (seeded in 186, no spec) must survive.
        cur.execute(
            "SELECT COUNT(*) FROM process_model WHERE entity_type IN "
            "('market_order', 'metric_value')"
        )
        assert cur.fetchone()[0] >= 7
    except psycopg2.ProgrammingError:
        pytest.skip("process_model not present")
    finally:
        conn.close()
