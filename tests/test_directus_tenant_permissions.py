"""Regression checks for Directus tenant-scoped permission repair."""

import importlib.util
import json
from pathlib import Path

PERMISSIONS = Path("config/directus/permissions.sql")
PARITY_CHECK = Path("scripts/fixtures/directus-api-parity-check.py")


def test_staff_permission_repair_adds_location_scope() -> None:
    text = PERMISSIONS.read_text()
    assert "Tenant-scope correction" in text
    assert "'$CURRENT_USER.location_id'" in text
    assert "FOREACH policy_id" in text


def test_create_permissions_validate_location_scope() -> None:
    text = PERMISSIONS.read_text()
    assert "SET validation = '{\"location_id\":{\"_eq\":\"$CURRENT_USER.location_id\"}}'::json" in text


def test_directus_probe_stops_before_creating_users_without_location_attribute() -> None:
    text = PARITY_CHECK.read_text()
    guard = text.index("if not location_column_present:")
    skipped = text.index('evidence["probe_skipped"]', guard)
    mutations = (
        '"/users"',
        '"UPDATE public.directus_users SET location_id',
        '"""INSERT INTO public.farm_activity',
    )
    assert guard < skipped
    assert all(text.index(mutation, guard) > skipped for mutation in mutations)
    assert '"synthetic Directus user creation"' in text[skipped : text.index(mutations[0], guard)]
    assert '"synthetic farm-activity row insertion"' in text[skipped : text.index(mutations[0], guard)]


def test_missing_directus_location_field_blocks_before_fixture_writes(monkeypatch, capsys) -> None:
    spec = importlib.util.spec_from_file_location("directus_parity_fixture", PARITY_CHECK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Cursor:
        def __init__(self, connection):
            self.connection = connection

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, _params=None):
            self.connection.queries.append(query)

        def fetchone(self):
            return (False,)

    class Connection:
        def __init__(self):
            self.queries = []
            self.commits = 0
            self.closed = False

        def cursor(self):
            return Cursor(self)

        def commit(self):
            self.commits += 1

        def rollback(self):
            raise AssertionError("preflight must not need rollback")

        def close(self):
            self.closed = True

    connection = Connection()
    api_calls = []

    def fake_api_request(method, path, **_kwargs):
        api_calls.append((method, path))
        if path == "/server/ping":
            return 200, None
        if path == "/auth/login":
            return 200, {"data": {"access_token": "synthetic-test-token"}}
        raise AssertionError(f"unexpected Directus API request: {method} {path}")

    monkeypatch.setattr(module, "ADMIN_EMAIL", "fixture@example.invalid")
    monkeypatch.setattr(module, "ADMIN_PASSWORD", "synthetic-test-password")
    monkeypatch.setattr(module, "PG_PASSWORD", "synthetic-test-password")
    monkeypatch.setattr(module, "api_request", fake_api_request)
    monkeypatch.setattr(module, "connect_db", lambda: connection)

    assert module.main() == 2

    result = json.loads(capsys.readouterr().out)
    assert result["result"] == "blocked"
    assert result["directus_user_location_column"] is False
    assert result["cleanup_complete"] is True
    assert result["probe_skipped"] == [
        "synthetic Directus user creation",
        "synthetic farm-activity row insertion",
        "user-scoped API reads and writes",
    ]
    assert api_calls == [("GET", "/server/ping"), ("POST", "/auth/login")]
    assert len(connection.queries) == 1
    assert connection.queries[0].lstrip().startswith("SELECT")
    assert connection.commits == 1
    assert connection.closed
