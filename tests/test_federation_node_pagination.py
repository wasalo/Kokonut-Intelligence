from __future__ import annotations

from unittest.mock import Mock

import pytest

from services.federation.node import FederationNode


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None
        self.parameters = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, statement, parameters=()):
        self.statement = statement
        self.parameters = parameters

    def fetchall(self):
        return self.rows


def _node_row(name):
    return (
        f"{name}-id",
        name,
        f"https://{name}.example",
        "trusted",
        [],
        None,
        "active",
        __import__("datetime").datetime(2026, 10, 28),
    )


class FakeConnection:
    def __init__(self, rows=()):
        self.fake_cursor = FakeCursor(rows)

    def cursor(self):
        return self.fake_cursor


@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (101, 0), (True, 0), (50, -1), (50, 10001), (50, False)],
)
def test_invalid_page_fails_before_database_access(limit, offset):
    node = FederationNode()
    get_connection = Mock(side_effect=AssertionError("database must not open"))
    node._get_conn = get_connection

    with pytest.raises(ValueError):
        node.list_nodes(limit=limit, offset=offset)
    with pytest.raises(ValueError):
        node.list_nodes_page(limit=limit, offset=offset)

    get_connection.assert_not_called()


def test_list_nodes_binds_status_and_page_in_sql():
    connection = FakeConnection()
    node = FederationNode(conn=connection)

    assert node.list_nodes(status="active", limit=25, offset=50) == []

    assert "WHERE status = %s" in connection.fake_cursor.statement
    assert "ORDER BY node_name" in connection.fake_cursor.statement
    assert "LIMIT %s OFFSET %s" in connection.fake_cursor.statement
    assert connection.fake_cursor.parameters == ("active", 25, 50)


def test_list_nodes_page_returns_exact_has_more_and_next_offset():
    connection = FakeConnection(rows=[_node_row("one"), _node_row("two")])
    node = FederationNode(conn=connection)

    page = node.list_nodes_page(limit=1, offset=10)

    assert [item["node_name"] for item in page["nodes"]] == ["one"]
    assert page["limit"] == 1
    assert page["offset"] == 10
    assert page["has_more"] is True
    assert page["next_offset"] == 11
    assert page["continuation_capped"] is False
    assert "LIMIT %s OFFSET %s" in connection.fake_cursor.statement
    assert connection.fake_cursor.parameters == (2, 10)


def test_list_nodes_page_marks_final_full_page_complete():
    connection = FakeConnection(rows=[_node_row("one")])
    node = FederationNode(conn=connection)

    page = node.list_nodes_page(limit=1, offset=10)

    assert len(page["nodes"]) == 1
    assert page["has_more"] is False
    assert page["next_offset"] is None
    assert page["continuation_capped"] is False


def test_list_nodes_page_reports_when_offset_ceiling_blocks_continuation():
    connection = FakeConnection(rows=[_node_row(str(index)) for index in range(101)])
    node = FederationNode(conn=connection)

    page = node.list_nodes_page(limit=100, offset=10_000)

    assert len(page["nodes"]) == 100
    assert page["has_more"] is True
    assert page["next_offset"] is None
    assert page["continuation_capped"] is True


def test_list_nodes_page_requires_limit_before_database_access():
    node = FederationNode()
    get_connection = Mock(side_effect=AssertionError("database must not open"))
    node._get_conn = get_connection

    with pytest.raises(ValueError, match="limit is required"):
        node.list_nodes_page(limit=None)

    get_connection.assert_not_called()


def test_list_nodes_preserves_unbounded_cli_reader_when_no_limit_is_given():
    connection = FakeConnection()
    node = FederationNode(conn=connection)

    assert node.list_nodes() == []

    assert "ORDER BY trust_level, node_name" in connection.fake_cursor.statement
    assert "LIMIT" not in connection.fake_cursor.statement
    assert connection.fake_cursor.parameters == ()
