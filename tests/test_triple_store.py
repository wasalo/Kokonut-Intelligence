"""Tests for services.rdf.triple_store — CRUD and query operations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_triple_store_add_triple_rejects_both_value_and_iri():
    from services.rdf.triple_store import add_triple

    conn = MagicMock()

    with pytest.raises(ValueError, match="Exactly one"):
        add_triple(conn, "s", "p", object_value="val", object_iri="http://iri")


def test_triple_store_add_triple_rejects_neither_value_nor_iri():
    from services.rdf.triple_store import add_triple

    conn = MagicMock()

    with pytest.raises(ValueError, match="Exactly one"):
        add_triple(conn, "s", "p")


def test_triple_store_add_triple_inserts_with_value():
    from services.rdf.triple_store import add_triple

    conn = MagicMock()
    conn.execute.return_value.rowcount = 1

    result = add_triple(conn, "s", "p", object_value="hello")
    assert result is True
    conn.execute.assert_called_once()


def test_triple_store_add_triple_inserts_with_iri():
    from services.rdf.triple_store import add_triple

    conn = MagicMock()
    conn.execute.return_value.rowcount = 1

    result = add_triple(conn, "s", "p", object_iri="http://example.org/resource")
    assert result is True


def test_triple_store_add_triple_returns_false_on_duplicate():
    from services.rdf.triple_store import add_triple

    conn = MagicMock()
    conn.execute.return_value.rowcount = 0

    result = add_triple(conn, "s", "p", object_value="dup")
    assert result is False


def test_triple_store_add_triples_batch():
    from services.rdf.triple_store import add_triples

    conn = MagicMock()
    conn.execute.return_value.rowcount = 1

    triples = [
        {"subject": "s1", "predicate": "p1", "object_value": "v1"},
        {"subject": "s2", "predicate": "p2", "object_iri": "http://iri"},
    ]
    count = add_triples(conn, triples)
    assert count == 2


def test_triple_store_query_triples_returns_list():
    from services.rdf.triple_store import query_triples

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.all.return_value = []

    result = query_triples(conn, subject="s")
    assert isinstance(result, list)


def test_triple_store_count_triples():
    from services.rdf.triple_store import count_triples

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {"cnt": 42}

    count = count_triples(conn)
    assert count == 42


def test_triple_store_delete_triples_returns_zero_without_conditions():
    from services.rdf.triple_store import delete_triples

    conn = MagicMock()
    result = delete_triples(conn)
    assert result == 0


def test_triple_store_triple_hash_deterministic():
    from services.rdf.triple_store import _triple_hash

    h1 = _triple_hash("s", "p", "val", "string", None, "default")
    h2 = _triple_hash("s", "p", "val", "string", None, "default")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
