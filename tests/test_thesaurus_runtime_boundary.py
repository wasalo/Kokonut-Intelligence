"""Focused source regressions for the bounded thesaurus writer contract."""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

from services import thesaurus


def _connection(row):
    connection = MagicMock()
    result = MagicMock()
    mappings = MagicMock()
    mappings.first.return_value = row
    result.mappings.return_value = mappings
    connection.execute.return_value = result
    connection.text = lambda statement: statement
    return connection


def test_write_helper_signatures_remain_compatible():
    assert str(inspect.signature(thesaurus.create_thesaurus)) == (
        "(conn, identifier: 'str', title: 'str', description: 'str' = None, "
        "language: 'str' = 'en') -> 'dict'"
    )
    assert str(inspect.signature(thesaurus.add_keyword)) == (
        "(conn, thesaurus_id: 'str', keyword_about: 'str', alt_label: 'str' = None, "
        "parent_keyword_id: 'str' = None) -> 'dict'"
    )
    assert str(inspect.signature(thesaurus.add_keyword_label)) == (
        "(conn, keyword_id: 'str', label: 'str', language: 'str' = 'en') -> 'dict'"
    )
    assert str(inspect.signature(thesaurus.delete_keyword)) == "(conn, keyword_id: 'str') -> 'bool'"


def test_create_thesaurus_calls_bounded_function_and_preserves_result():
    connection = _connection({"id": "thesaurus-id"})

    result = thesaurus.create_thesaurus(
        connection, "activity_type", "Activity", "Description", "es"
    )

    statement, parameters = connection.execute.call_args.args
    assert "kokonut_security.create_thesaurus" in statement
    assert parameters == {
        "id": "activity_type",
        "title": "Activity",
        "desc": "Description",
        "lang": "es",
    }
    assert result == {"id": "thesaurus-id", "identifier": "activity_type"}


def test_add_keyword_calls_bounded_function_with_parent_and_preserves_result():
    connection = _connection({"id": "keyword-id"})

    result = thesaurus.add_keyword(
        connection, "thesaurus-id", "agroforestry", "forest farming", "parent-id"
    )

    statement, parameters = connection.execute.call_args.args
    assert "kokonut_security.add_thesaurus_keyword" in statement
    assert parameters == {
        "tid": "thesaurus-id",
        "about": "agroforestry",
        "alt": "forest farming",
        "parent": "parent-id",
    }
    assert result == {"id": "keyword-id", "keyword_about": "agroforestry"}


def test_add_keyword_label_calls_bounded_upsert_and_preserves_result():
    connection = _connection({"id": "label-id"})

    result = thesaurus.add_keyword_label(
        connection, "keyword-id", "Agroforestry", "en"
    )

    statement, parameters = connection.execute.call_args.args
    assert "kokonut_security.upsert_thesaurus_keyword_label" in statement
    assert parameters == {"kid": "keyword-id", "label": "Agroforestry", "lang": "en"}
    assert result == {
        "id": "label-id",
        "label": "Agroforestry",
        "language": "en",
    }


def test_delete_keyword_returns_bounded_function_result():
    connection = _connection({"deleted": True})

    assert thesaurus.delete_keyword(connection, "keyword-id") is True
    statement, parameters = connection.execute.call_args.args
    assert "kokonut_security.delete_thesaurus_keyword" in statement
    assert parameters == {"id": "keyword-id"}


def test_delete_keyword_missing_result_is_false():
    assert thesaurus.delete_keyword(_connection(None), "missing-id") is False

