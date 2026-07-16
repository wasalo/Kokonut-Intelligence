"""Tests for capacity-aware planning projections."""

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
