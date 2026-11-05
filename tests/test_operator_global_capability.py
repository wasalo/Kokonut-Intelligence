from types import SimpleNamespace

import pytest

import services.gateway.operator_auth as operator_auth


def test_has_global_capability_uses_operator_auth_connection(monkeypatch):
    class Cursor:
        def __init__(self):
            self.query = None
            self.params = None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchone(self):
            return (True,)

    class Connection:
        def __init__(self):
            self.cursor_instance = Cursor()
            self.rolled_back = False
            self.closed = False

        def cursor(self):
            return self.cursor_instance

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(operator_auth, "_get_operator_auth_db", lambda _settings: connection)
    provider = SimpleNamespace(settings=object())
    session_hash = "a" * 64

    result = operator_auth.OIDCOperatorProvider.has_global_capability(
        provider, session_hash, "clickhouse_outbox:read"
    )

    assert result is True
    assert "operator_global_capability_allows" in connection.cursor_instance.query
    assert connection.cursor_instance.params == (session_hash, "clickhouse_outbox:read")
    assert connection.rolled_back is True
    assert connection.closed is True


def test_has_global_capability_rejects_invalid_hash_or_capability(monkeypatch):
    monkeypatch.setattr(
        operator_auth,
        "_get_operator_auth_db",
        lambda _settings: pytest.fail("invalid capability input must not open a connection"),
    )
    provider = SimpleNamespace(settings=object())

    assert operator_auth.OIDCOperatorProvider.has_global_capability(
        provider, "not-a-session-hash", "clickhouse_outbox:read"
    ) is False
    assert operator_auth.OIDCOperatorProvider.has_global_capability(
        provider, "a" * 64, "clickhouse_outbox:admin"
    ) is False
