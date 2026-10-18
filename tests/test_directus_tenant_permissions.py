"""Regression checks for Directus tenant-scoped permission repair."""

import importlib.util
import json
from pathlib import Path

PERMISSIONS = Path("config/directus/permissions.sql")
PARITY_CHECK = Path("scripts/fixtures/directus-api-parity-check.py")


def test_permission_repair_replaces_user_location_with_grant_hooks() -> None:
    text = PERMISSIONS.read_text()
    repair = text.index("Replace the legacy per-user location filter")
    repair_block = text[repair : text.index("-- Farm activity is operated", repair)]
    seed_definitions = text[:repair]

    assert "$CURRENT_USER.location_id" not in seed_definitions
    assert "jsonb_array_elements(legacy_permission.permission_filter->'_and')" in repair_block
    assert "term <> legacy_location_clause" in repair_block
    assert "term <> '{}'::JSONB" in repair_block
    assert "Unexpected legacy Directus location permission filter shape" in repair_block
    assert "operator_scope_grant_allows" not in text  # tenant filtering lives in the required hook


def test_directus_seed_keeps_farm_activity_operations_on_gateway() -> None:
    text = PERMISSIONS.read_text()
    lower = text.lower()

    assert "('farm_activity'," not in lower
    cleanup = lower[lower.index("-- farm activity is operated through the kokonut gateway") :]
    assert "delete from directus_permissions" in cleanup
    assert "where collection = 'farm_activity'" in cleanup
    for policy_id in range(1, 10):
        assert f"b1000000-0000-0000-0000-{policy_id:012d}" in cleanup
    assert "unrecognized custom policies remain subject to operator" in cleanup


def test_directus_fixture_uses_verified_organization_location_grants() -> None:
    text = PARITY_CHECK.read_text()
    assert "directus_users" in text
    assert "external_identifier" in text
    assert "location_tenant_owner_verification" in text
    assert "operator_organization_membership" in text
    assert "operator_scope_grant" in text
    assert "operator_scope_grant_allows" in text
    assert "directus_user_role_matches_field_worker" in text
    assert "effective_permissions_collection_count" in text
    assert "directus_api_user_role_matches_field_worker" in text
    assert "field_worker_self_role_matches" in text
    assert "admin_farm_activity_collection_registered" in text
    assert "field_worker_farm_activity_has_custom_permission_rules" in text
    assert "permission_row.fields <> '*'" in text
    assert "effective_permissions_collection_names" in text
    assert "field_worker_effective_collection_present" in text
    assert 'evidence["farm_activity_gateway_only"]' in text
    assert 'evidence["farm_activity_own_read_denied"]' in text
    assert 'evidence["farm_activity_cross_read_denied"]' in text
    assert 'evidence["farm_activity_cross_patch_denied"]' in text
    assert 'evidence["own_location_create_denied"]' in text
    assert 'evidence["farm_activity_api_writes_left_rows_unchanged"]' in text
    assert 'evidence["field_note_own_location_read"]' in text
    assert 'evidence["field_note_cross_location_read_hidden"]' in text
    assert "directus_user_location_column" not in text
    assert "UPDATE public.directus_users SET location_id" not in text
    assert '"/items/field_note"' in text
    assert "field_note_cross_location_read_hidden" in text
    assert "field_worker_farm_activity_has_custom_permission_rules" in text


def test_directus_fixture_falls_back_to_owned_synthetic_locations_and_cleans_them() -> None:
    text = PARITY_CHECK.read_text()
    assert "A recovered candidate checkpoint may intentionally contain" in text
    assert "Synthetic Directus parity organization" in text
    assert "Synthetic Directus parity location" in text
    assert "isolated Directus parity fixture" in text
    assert "DELETE FROM public.location_tenant_owner_verification" in text
    assert "DELETE FROM public.organization_member" in text
    assert "DELETE FROM public.location WHERE id = ANY(%s::uuid[])" in text
    assert "DELETE FROM public.organization WHERE id = %s::uuid" in text
    assert "DELETE FROM public.farm_activity WHERE id = ANY(%s::uuid[])" in text
    assert "DELETE FROM public.field_note WHERE id = ANY(%s::uuid[])" in text


def test_directus_fixture_preflights_tenant_schema_before_synthetic_writes() -> None:
    text = PARITY_CHECK.read_text()
    guard = text.index("if not tenant_schema_available:")
    skipped = text.index('evidence["probe_skipped"]', guard)
    mutations = (
        '"INSERT INTO public.operator_identity',
        '"POST",\n            "/users"',
        '"""INSERT INTO public.farm_activity',
    )
    assert guard < skipped
    assert all(text.index(mutation, guard) > skipped for mutation in mutations)
    assert '"synthetic operator and Directus user creation"' in text[skipped : text.index(mutations[0], guard)]


def test_missing_grant_schema_blocks_before_fixture_writes(monkeypatch, capsys) -> None:
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
            return (True, False, True, True, True)

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
            raise AssertionError("read-only preflight must not need rollback")

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
        if path == "/collections/farm_activity":
            return 200, {"data": {"collection": "farm_activity"}}
        raise AssertionError(f"unexpected Directus API request: {method} {path}")

    monkeypatch.setattr(module, "ADMIN_EMAIL", "fixture@example.invalid")
    monkeypatch.setattr(module, "ADMIN_PASSWORD", "synthetic-test-password")
    monkeypatch.setattr(module, "PG_PASSWORD", "synthetic-test-password")
    monkeypatch.setattr(module, "api_request", fake_api_request)
    monkeypatch.setattr(module, "connect_db", lambda: connection)

    assert module.main() == 2

    result = json.loads(capsys.readouterr().out)
    assert result["result"] == "blocked"
    assert result["tenant_grant_schema_available"] is False
    assert result["cleanup_complete"] is True
    assert result["probe_skipped"] == [
        "synthetic operator and Directus user creation",
        "synthetic farm-activity row insertion",
        "user-scoped API reads and writes",
    ]
    assert api_calls == [
        ("GET", "/server/ping"),
        ("POST", "/auth/login"),
        ("GET", "/collections/farm_activity"),
    ]
    assert len(connection.queries) == 1
    assert connection.queries[0].lstrip().startswith("SELECT")
    assert connection.commits == 2
    assert connection.closed


def test_directus_fixture_requires_denial_status_without_returned_data() -> None:
    spec = importlib.util.spec_from_file_location("directus_parity_denial", PARITY_CHECK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.permission_denied(403, {"errors": [{"message": "Forbidden"}]})
    assert module.permission_denied(404, {"data": []})
    assert not module.permission_denied(200, {"data": []})
    assert not module.permission_denied(403, {"data": {"id": "synthetic"}})
