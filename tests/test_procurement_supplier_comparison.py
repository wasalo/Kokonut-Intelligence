"""Contract checks for migration-082 supplier comparison filters."""

from __future__ import annotations

from typing import Any

import pytest

from services.analytics.procurement import compute_supplier_comparison


class _Cursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.query = ""
        self.params: tuple[Any, ...] = ()
        self.closed = False

    def execute(self, query: str, params: tuple[Any, ...]) -> None:
        self.query = query
        self.params = tuple(params)

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows

    def close(self) -> None:
        self.closed = True


class _Connection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.cursor_instance = _Cursor(rows)
        self.cursor_factory = None

    def cursor(self, *, cursor_factory: Any = None) -> _Cursor:
        self.cursor_factory = cursor_factory
        return self.cursor_instance


@pytest.mark.parametrize(
    ("location_id", "product_category", "expected_params"),
    [
        (None, None, ()),
        ("loc-a", None, ("loc-a",)),
        (None, "soil", ("soil",)),
        ("loc-a", "soil", ("loc-a", "soil")),
    ],
)
def test_supplier_comparison_binds_optional_filters_in_query_order(
    location_id: str | None,
    product_category: str | None,
    expected_params: tuple[str, ...],
) -> None:
    rows = [{"supplier_id": "supplier-1", "order_count": 2, "total_spend": 30}]
    conn = _Connection(rows)

    result = compute_supplier_comparison(
        conn, location_id=location_id, product_category=product_category
    )

    assert result == rows
    assert conn.cursor_instance.params == expected_params
    assert conn.cursor_instance.closed

    query = " ".join(conn.cursor_instance.query.split())
    if location_id is None:
        assert "po.location_id = %s" not in query
    else:
        assert "po.location_id = %s" in query

    if product_category is None:
        assert "poi.product_category = %s" not in query
        assert "poi.order_id = po.id" not in query
    else:
        assert "poi.product_category = %s" in query
        assert "poi.order_id = po.id" in query
        assert "po2.supplier_id = sp.id" not in query

