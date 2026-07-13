"""Tests for the lightweight named-parameter database adapter."""

from unittest.mock import MagicMock

from services.common.database import DatabaseConnection, _to_psycopg2_sql


def test_named_parameter_translation_preserves_postgres_casts():
    sql = "SELECT :value::jsonb, id FROM sample WHERE id = :id"
    assert _to_psycopg2_sql(sql) == (
        "SELECT %(value)s::jsonb, id FROM sample WHERE id = %(id)s"
    )


def test_context_manager_commits_and_closes():
    raw = MagicMock()
    with DatabaseConnection(raw):
        pass
    raw.commit.assert_called_once()
    raw.close.assert_called_once()


def test_context_manager_rolls_back_on_error():
    raw = MagicMock()
    try:
        with DatabaseConnection(raw):
            raise ValueError("boom")
    except ValueError:
        pass
    raw.rollback.assert_called_once()
    raw.close.assert_called_once()
