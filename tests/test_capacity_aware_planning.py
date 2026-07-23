"""Tests for capacity-aware planning projections."""

from unittest.mock import MagicMock

from services.planning import capacity_aware


def test_capacity_aware_queries_are_composable():
    class Cursor:
        def __init__(self):
            self.sql = ""
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def execute(self, sql, params):
            self.sql = sql
            self.params = params
        def fetchall(self):
            return []
    class Conn:
        def cursor(self, **_):
            return Cursor()
    assert capacity_aware.work_queue(Conn(), scope_type="internal") == []
    assert capacity_aware.portfolio_health(Conn(), scope_type="adelphi") == []


def test_work_queue_builds_where_clause_with_filters():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    capacity_aware.work_queue(mock_conn, organization_id="org-1", scope_type="internal")
    sql = mock_cursor.execute.call_args[0][0]
    assert "organization_id" in sql
    assert "inferred_scope_type" in sql


def test_portfolio_health_builds_where_clause():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    capacity_aware.portfolio_health(mock_conn, scope_type="adelphi", scope_id="scope-1")
    sql = mock_cursor.execute.call_args[0][0]
    assert "scope_type" in sql
    assert "scope_id" in sql
