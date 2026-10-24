"""Regression checks for bounded credit-class database list queries."""

from __future__ import annotations

import pytest


class _Mappings:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return _Mappings(self._rows)


class _Connection:
    def __init__(self, total=9, rows=None):
        self.total = total
        self.rows = [{"id": "row-1"}, {"id": "row-2"}] if rows is None else rows
        self.statements = []

    @staticmethod
    def text(statement):
        return statement

    def execute(self, statement, params=None):
        self.statements.append((statement, params or {}))
        if len(self.statements) == 1:
            return _Result([{"total": self.total}])
        return _Result(self.rows)


@pytest.mark.parametrize(
    ("module_name", "function_name", "filters"),
    [
        ("services.credit_class.class_manager", "list_classes_page", {"admin_address": "admin-1"}),
        ("services.credit_class.batch_manager", "list_batches_page", {"location_id": "loc-1"}),
        ("services.credit_class.basket", "list_baskets_page", {"status": "active"}),
        ("services.credit_class.marketplace", "list_sell_orders_page", {"seller_address": "seller-1"}),
    ],
)
def test_manager_pages_bound_sql_and_bind_filters(module_name, function_name, filters):
    import importlib

    function = getattr(importlib.import_module(module_name), function_name)
    connection = _Connection()

    rows, total = function(connection, limit=2, offset=4, **filters)

    assert rows == connection.rows
    assert total == 9
    assert len(connection.statements) == 2
    count_sql, count_params = connection.statements[0]
    page_sql, page_params = connection.statements[1]
    assert "COUNT(*) AS total" in count_sql
    assert "ORDER BY created_at DESC, id DESC" in page_sql
    assert "LIMIT :_page_limit OFFSET :_page_offset" in page_sql
    assert page_params["_page_limit"] == 2
    assert page_params["_page_offset"] == 4
    assert page_params.keys() == count_params.keys() | {"_page_limit", "_page_offset"}
    for key, value in filters.items():
        bind = {
            "admin_address": "admin",
            "location_id": "lid",
            "status": "s",
            "seller_address": "seller",
        }[key]
        assert count_params[bind] == value
        assert page_params[bind] == value


def test_fetch_page_returns_empty_page_with_count_and_bounded_parameters():
    from services.credit_class.page_queries import fetch_page

    connection = _Connection(total=6, rows=[])
    rows, total = fetch_page(
        connection,
        count_sql="SELECT COUNT(*) AS total FROM records",
        select_sql="SELECT * FROM records LIMIT :_page_limit OFFSET :_page_offset",
        params={"location_id": "loc-1"},
        limit=5,
        offset=99,
    )

    assert rows == []
    assert total == 6
    assert connection.statements[1][1] == {
        "location_id": "loc-1",
        "_page_limit": 5,
        "_page_offset": 99,
    }
