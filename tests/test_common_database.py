"""Tests for the lightweight named-parameter database adapter."""

from unittest.mock import MagicMock, patch

from services.common.cli import get_connection as cli_get_connection
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


def test_connection_exposes_raw_transaction_mode():
    raw = MagicMock()
    raw.autocommit = False
    assert DatabaseConnection(raw).autocommit is False
    raw.autocommit = True
    assert DatabaseConnection(raw).autocommit is True


def test_connection_can_default_all_transactions_to_read_only():
    raw = MagicMock()
    DatabaseConnection(raw, readonly=True)

    raw.set_session.assert_called_once_with(readonly=True)


def test_connection_rejects_non_boolean_readonly_option():
    try:
        DatabaseConnection(MagicMock(), readonly="yes")
    except TypeError as exc:
        assert str(exc) == "readonly must be a boolean"
    else:
        raise AssertionError("non-boolean readonly value was accepted")


def test_cli_connection_helper_forwards_readonly_setting_lazily():
    expected = object()
    with patch("services.common.database.get_connection", return_value=expected) as get_connection:
        assert cli_get_connection(readonly=True) is expected

    get_connection.assert_called_once_with(connect_timeout=None, readonly=True)
