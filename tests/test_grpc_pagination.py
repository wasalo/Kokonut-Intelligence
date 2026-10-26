"""Unit checks for bounded gRPC offset-cursor pagination."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.grpc.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    page_response,
    paginate_items,
    parse_page_request,
)


def page_request(*, limit=0, offset=b""):
    return SimpleNamespace(limit=limit, offset=offset)


def test_pagination_returns_stable_slice_total_and_next_cursor():
    rows = ["a", "b", "c", "d", "e"]

    first, first_page = paginate_items(rows, page_request(limit=2))
    second, second_page = paginate_items(
        rows,
        page_request(limit=2, offset=first_page["next_key"]),
    )
    final, final_page = paginate_items(
        rows,
        page_request(limit=2, offset=second_page["next_key"]),
    )

    assert first == ["a", "b"]
    assert first_page == {"next_key": b"2", "total": 5}
    assert second == ["c", "d"]
    assert second_page == {"next_key": b"4", "total": 5}
    assert final == ["e"]
    assert final_page == {"next_key": b"", "total": 5}


def test_zero_limit_uses_bounded_default_page_size():
    rows = list(range(DEFAULT_PAGE_SIZE + 3))

    page, metadata = paginate_items(rows, page_request())

    assert len(page) == DEFAULT_PAGE_SIZE
    assert metadata == {"next_key": str(DEFAULT_PAGE_SIZE).encode("ascii"), "total": len(rows)}


@pytest.mark.parametrize("offset", [b"-1", b"01", b"1.5", b"abc", b"\xff"])
def test_malformed_cursor_is_rejected(offset):
    with pytest.raises(ValueError, match="ASCII decimal cursor"):
        parse_page_request(page_request(limit=10, offset=offset))


def test_cursor_outside_supported_range_is_rejected():
    with pytest.raises(ValueError, match="exceeds the supported range"):
        parse_page_request(page_request(offset=str(2**63).encode("ascii")))


def test_oversized_page_is_rejected():
    with pytest.raises(ValueError, match=f"must not exceed {MAX_PAGE_SIZE}"):
        parse_page_request(page_request(limit=MAX_PAGE_SIZE + 1))


def test_page_response_uses_database_page_length_for_next_cursor():
    assert page_response(total=8, offset=4, returned_count=3) == {
        "next_key": b"7",
        "total": 8,
    }
    assert page_response(total=7, offset=4, returned_count=3) == {
        "next_key": b"",
        "total": 7,
    }


def test_missing_page_request_has_no_page_metadata():
    from services.grpc.credit_class_service import EcocreditServiceServicer

    assert EcocreditServiceServicer._page_metadata(None, 2, 2) == {}


def test_invalid_page_request_aborts_as_invalid_argument():
    import grpc

    from services.grpc.credit_class_service import EcocreditServiceServicer

    request = SimpleNamespace(
        HasField=lambda _name: True,
        pagination=page_request(limit=MAX_PAGE_SIZE + 1),
    )
    context = MagicMock()
    context.abort.side_effect = grpc.RpcError()
    servicer = EcocreditServiceServicer(MagicMock())

    with pytest.raises(grpc.RpcError):
        servicer._validate_pagination(request, context)

    context.abort.assert_called_once_with(
        grpc.StatusCode.INVALID_ARGUMENT,
        f"pagination limit must not exceed {MAX_PAGE_SIZE}",
    )


def test_each_paginated_ecocredit_handler_uses_database_page_metadata():
    source = Path("services/grpc/credit_class_service.py").read_text()
    tree = ast.parse(source)
    method_names = {
        "Classes",
        "ClassesByAdmin",
        "Projects",
        "ProjectsByClass",
        "Batches",
        "BatchesByClass",
        "BatchesByProject",
        "Baskets",
        "SellOrders",
    }
    methods = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in method_names
    }

    assert methods.keys() == method_names
    for name, method in methods.items():
        calls = [
            node
            for node in ast.walk(method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        ]
        assert any(
            node.func.attr == "_page_metadata"
            for node in calls
        ), f"{name} must return metadata for its bounded page"
        validation_lines = [
            node.lineno for node in calls if node.func.attr == "_validate_pagination"
        ]
        connection_lines = [
            node.lineno for node in calls if node.func.attr == "_get_conn"
        ]
        assert validation_lines and connection_lines
        assert min(validation_lines) < min(connection_lines), (
            f"{name} must validate pagination before acquiring the service database"
        )


def test_all_page_queries_apply_limit_and_offset_in_sql():
    query_sources = [
        Path("services/credit_class/class_manager.py").read_text(),
        Path("services/credit_class/batch_manager.py").read_text(),
        Path("services/credit_class/basket.py").read_text(),
        Path("services/credit_class/marketplace.py").read_text(),
        Path("services/grpc/credit_class_service.py").read_text(),
    ]
    assert all(
        "LIMIT :_page_limit OFFSET :_page_offset" in source
        for source in query_sources
    ), "each manager and both direct project queries must bound database reads"
