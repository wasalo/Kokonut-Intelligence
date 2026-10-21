"""Successful offline legacy command parity through the unified CLI."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment["KOKONUT_ENV"] = "development"
    environment["KOKONUT_DATABASE_URL"] = "postgresql://invalid:invalid@127.0.0.1:1/unused"
    environment["DATABASE_URL"] = "postgresql://invalid:invalid@127.0.0.1:1/unused"
    environment["SOPS_AGE_KEY_FILE"] = "/__codex_no_sops_key__"
    environment.pop("KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT", None)
    environment.pop("KOKONUT_ALLOW_PLAINTEXT_ENV", None)
    environment.pop("SOPS_AGE_KEY", None)
    return environment


def _run(module_or_unified: list[str], environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *module_or_unified],
        capture_output=True,
        text=True,
        timeout=20,
        env=environment,
    )


def _manifest() -> dict[str, object]:
    return {
        "form_id": "cli_parity_fixture",
        "version": "1.0.0",
        "name": "CLI parity fixture",
        "description": "Offline acceptance fixture.",
        "form_schema": {
            "type": "object",
            "required": ["note"],
            "properties": {"note": {"type": "string"}},
            "additionalProperties": False,
        },
        "ui_schema": {},
        "collection_type": "field_note",
        "location_id": None,
        "is_public": False,
        "status": "active",
        "consent_policy": {
            "status": "not_required",
            "data_category": "field_observation",
            "purpose": "CLI parity acceptance.",
            "scope_type": "location",
            "scope_id": None,
            "recipient_type": "location_operator",
            "recipient_party_id": None,
            "recipient_name": None,
            "version": None,
        },
        "review": {
            "reviewed_by": "fixture-reviewer",
            "reviewed_at": "2026-10-20T12:00:00Z",
            "evidence": [{"source": "test-fixture", "basis": "Synthetic acceptance fixture."}],
        },
    }


@pytest.mark.parametrize("group", ["agents", "ingestion"])
def test_offline_catalogue_output_matches_standalone_cli(group: str) -> None:
    args = ["list"] if group == "agents" else ["--list"]
    module = "services.agents.cli" if group == "agents" else "services.ingestion.cli"
    environment = _environment()

    standalone = _run(["-m", module, *args], environment)
    unified = _run(["-m", "services.cli", group, "--", *args], environment)

    assert standalone.returncode == unified.returncode == 0
    assert unified.stdout == standalone.stdout
    assert unified.stderr == standalone.stderr == ""


def test_offline_form_validation_output_matches_standalone_cli(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    args = ["validate", "--manifest", str(manifest_path)]
    environment = _environment()

    standalone = _run(["-m", "services.mobile.forms_cli", *args], environment)
    unified = _run(["-m", "services.cli", "mobile-forms", "--", *args], environment)

    assert standalone.returncode == unified.returncode == 0
    assert json.loads(unified.stdout) == json.loads(standalone.stdout)
    assert json.loads(unified.stdout)["manifest"]["database_write"] is False
    assert unified.stderr == standalone.stderr == ""


def test_offline_form_preview_output_matches_standalone_cli(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    args = ["preview", "--manifest", str(manifest_path)]
    environment = _environment()

    standalone = _run(["-m", "services.mobile.forms_cli", *args], environment)
    unified = _run(["-m", "services.cli", "mobile-forms", "--", *args], environment)

    assert standalone.returncode == unified.returncode == 0
    standalone_output = json.loads(standalone.stdout)
    unified_output = json.loads(unified.stdout)
    assert unified_output == standalone_output
    assert unified_output["publication"] == "not applied"
    assert unified_output["change"] == "version_comparison_not_supplied"
    assert unified.stderr == standalone.stderr == ""


def test_audit_spool_missing_file_status_matches_standalone_without_creating_it(tmp_path: Path) -> None:
    journal = tmp_path / "journal.sqlite3"
    args = ["status", "--path", str(journal)]
    environment = _environment()

    standalone = _run(["-m", "services.gateway.audit_spool_cli", *args], environment)
    unified = _run(["-m", "services.cli", "audit-spool", "--", *args], environment)

    assert standalone.returncode == unified.returncode == 0
    assert json.loads(unified.stdout) == json.loads(standalone.stdout)
    assert json.loads(unified.stdout)["exists"] is False
    assert not journal.exists()
    assert unified.stderr == standalone.stderr == ""


def test_systems_module_catalogue_output_matches_standalone_cli() -> None:
    environment = _environment()

    standalone = _run(["-m", "services.systems.cli", "--list-modules"], environment)
    unified = _run(["-m", "services.cli", "systems", "--", "--list-modules"], environment)

    assert standalone.returncode == unified.returncode == 0
    assert unified.stdout == standalone.stdout
    assert "causal_loops" in unified.stdout
    assert unified.stderr == standalone.stderr == ""


def test_offline_attestation_schema_catalogue_output_matches_standalone() -> None:
    environment = _environment()

    standalone = _run(
        ["-m", "services.attestation.cli", "schema", "list"],
        environment,
    )
    unified = _run(
        ["-m", "services.cli", "attestation", "--", "schema", "list"],
        environment,
    )

    assert standalone.returncode == unified.returncode == 0
    assert unified.stdout == standalone.stdout
    assert "kokonut-mrv" in unified.stdout
    assert unified.stderr == standalone.stderr == ""


def test_offline_migration_source_validation_matches_standalone() -> None:
    environment = _environment()
    args = ["validate", "--schemas-only"]

    standalone = _run(["-m", "services.migration.cli", *args], environment)
    unified = _run(["-m", "services.cli", "migration", "--", *args], environment)

    assert standalone.returncode == unified.returncode == 0
    assert unified.stdout == standalone.stdout
    assert unified.stdout.startswith("Validated ")
    assert " migration source files.\n" in unified.stdout
    assert unified.stderr == standalone.stderr == ""


def test_database_backed_mobile_tenant_preflight_output_matches_with_stubbed_inventory(
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.mobile import tenant_preflight

    location_id = "12345678-1234-5678-1234-567812345678"
    report = {
        "scope": "read_only_organization_ownership_and_known_lineage_preflight",
        "inventory_status": "complete",
        "location_filter_applied": True,
        "location_count": 1,
        "ownership_review_status_counts": {"assigned_owner_matches_relationship": 1},
        "locations": [{"location_ref": "location:synthetic-reference"}],
        "identifiers_emitted": False,
    }
    calls = []

    def fake_collect_inventory(requested_location_id=None):
        calls.append(requested_location_id)
        return report

    monkeypatch.setattr(tenant_preflight, "collect_inventory", fake_collect_inventory)
    arguments = ["--location-id", location_id]
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.mobile.tenant_preflight", *arguments]
        tenant_preflight.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(
        unified_cli.app,
        ["mobile-tenant-preflight", "--", *arguments],
    )

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert json.loads(unified.output) == report
    assert location_id not in unified.output
    assert calls == [location_id, location_id]
    assert unified.stderr == ""


def test_database_backed_mobile_media_cleanup_dry_run_matches_without_loading_provider(
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.mobile import media_cleanup

    connections = []
    provider_calls = []

    class FakeResult:
        def all(self):
            return [{"eligible_count": 3}]

    class FakeConnection:
        closed = False
        queries = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True
            return False

        def execute(self, sql, _params=None):
            self.queries.append(" ".join(sql.lower().split()))
            return FakeResult()

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    def unexpected_provider_call():
        provider_calls.append(True)
        raise AssertionError("dry-run must not configure private object storage")

    monkeypatch.setattr(media_cleanup, "get_connection", make_connection)
    monkeypatch.setattr(media_cleanup, "create_media_store", unexpected_provider_call)
    arguments = ["--limit", "17"]
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.mobile.media_cleanup", *arguments]
        media_cleanup.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(
        unified_cli.app,
        ["mobile-media-cleanup", "--", *arguments],
    )

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert json.loads(unified.output) == {
        "mode": "dry-run",
        "eligible_count": 3,
        "limit": 17,
        "expired_count": 0,
    }
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    assert all("mobile_media_upload" in connection.queries[0] for connection in connections)
    assert provider_calls == []
    assert unified.stderr == ""


def test_database_and_provider_backed_mobile_media_reconcile_dry_run_matches_without_deleting(
    monkeypatch,
    capsys,
) -> None:
    from datetime import datetime, timedelta, timezone

    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.mobile import media_reconcile
    from services.mobile.media_storage import PrivateMediaObject

    registered_key = "private/field-collector/synthetic/device/registered.jpg"
    orphan_key = "private/field-collector/synthetic/device/orphan.jpg"
    now = datetime.now(timezone.utc)
    modified = now - timedelta(days=3)
    connections = []
    stores = []

    class FakeResult:
        def all(self):
            return [{"object_key": registered_key}]

    class FakeConnection:
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True
            return False

        def execute(self, sql, _params=None):
            assert "select object_key from mobile_media_upload" in " ".join(sql.lower().split())
            return FakeResult()

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    class FakeStore:
        def __init__(self):
            self.objects = [
                PrivateMediaObject("registered-id", modified, "object", registered_key),
                PrivateMediaObject("orphan-id", modified, "object", orphan_key),
            ]
            self.deleted = []

        def list_private_objects(self):
            return list(self.objects)

        def object_id_for_key(self, key):
            return "registered-id" if key == registered_key else "orphan-id"

        def delete_orphan(self, item):
            self.deleted.append(item.object_id)

    def make_store():
        store = FakeStore()
        stores.append(store)
        return store

    monkeypatch.setattr(media_reconcile, "get_connection", make_connection)
    monkeypatch.setattr(media_reconcile, "create_media_store", make_store)
    arguments = ["--older-than-hours", "48", "--limit", "9"]
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.mobile.media_reconcile", *arguments]
        media_reconcile.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(
        unified_cli.app,
        ["mobile-media-reconcile", "--", *arguments],
    )

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    report = json.loads(unified.output)
    assert report == {
        "mode": "dry-run",
        "provider_object_count": 2,
        "registered_object_count": 1,
        "unregistered_object_count": 1,
        "eligible_count": 1,
        "too_young_count": 0,
        "limit": 9,
        "older_than_hours": 48,
        "deleted_count": 0,
        "skipped_registered_count": 0,
        "skipped_changed_count": 0,
    }
    assert len(connections) == len(stores) == 2
    assert all(connection.closed for connection in connections)
    assert all(store.deleted == [] for store in stores)
    assert registered_key not in unified.output
    assert orphan_key not in unified.output
    assert unified.stderr == ""


def test_offline_operator_role_templates_output_matches_standalone() -> None:
    environment = _environment()
    arguments = ["farm-activity-role", "templates"]

    standalone = _run(["-m", "services.gateway.operator_cli", *arguments], environment)
    unified = _run(["-m", "services.cli", "operator", "--", *arguments], environment)

    assert standalone.returncode == unified.returncode == 0
    assert unified.stdout == standalone.stdout
    report = json.loads(unified.stdout)
    assert report["roles"]
    assert all(
        isinstance(scope, dict) and set(scope) == {"resource", "action"}
        for scopes in report["roles"].values()
        for scope in scopes
    )
    assert unified.stderr == standalone.stderr == ""


def test_operator_grant_revocation_cli_matches_and_persists_audit_fields(
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.gateway import operator_cli

    grant_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    report = {
        "id": grant_id,
        "operator_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "resource": "farm_activity",
        "action": "read",
        "location_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        "revoked_by": "local-admin",
        "revocation_reason": "operator access ended",
    }
    connections = []

    class FakeResult:
        def first(self):
            return report

    class FakeConnection:
        closed = False
        query = ""
        parameters = None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True
            return False

        def execute(self, query, parameters):
            self.query = " ".join(query.lower().split())
            self.parameters = parameters
            return FakeResult()

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(operator_cli, "get_connection", make_connection)
    arguments = [
        "revoke-grant",
        "--grant-id", grant_id,
        "--revoked-by", "local-admin",
        "--reason", "operator access ended",
    ]
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.gateway.operator_cli", *arguments]
        operator_cli.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(unified_cli.app, ["operator", "--", *arguments])

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert json.loads(unified.output) == report
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    assert all("revoked_by = :revoked_by" in connection.query for connection in connections)
    assert all("revocation_reason = :reason" in connection.query for connection in connections)
    assert all(
        connection.parameters == {
            "grant_id": grant_id,
            "revoked_by": "local-admin",
            "reason": "operator access ended",
        }
        for connection in connections
    )
    assert unified.stderr == ""


def test_operator_identity_provision_cli_matches_without_reenabling_disabled_identity(
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.gateway import operator_cli

    identity = {
        "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "issuer": "https://identity.example.test",
        "subject": "subject-123",
        "display_name": "Operator One",
        "enabled": True,
    }
    connections = []

    class FakeResult:
        def first(self):
            return identity

    class FakeConnection:
        closed = False
        query = ""

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True
            return False

        def execute(self, query, _parameters):
            self.query = " ".join(query.lower().split())
            return FakeResult()

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(operator_cli, "get_connection", make_connection)
    arguments = [
        "identity", "provision",
        "--issuer", "https://identity.example.test",
        "--subject", "subject-123",
        "--display-name", "Operator One",
    ]
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.gateway.operator_cli", *arguments]
        operator_cli.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(unified_cli.app, ["operator", "--", *arguments])

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert json.loads(unified.output) == identity
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    for connection in connections:
        update = connection.query.split("do update set", maxsplit=1)[1].split("where", maxsplit=1)[0]
        assert "enabled" not in update
        assert "where operator_identity.enabled = true" in connection.query
    assert unified.stderr == ""


def test_operator_list_cli_matches_with_synthetic_rows_and_closes_connections(
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.gateway import operator_cli

    rows_by_table = {
        "operator_identity": [{"id": "synthetic-operator", "subject": "synthetic-subject"}],
        "operator_scope_grant": [{"id": "synthetic-grant", "resource": "farm_activity"}],
        "operator_organization_membership": [{"id": "synthetic-membership", "membership_role": "operator"}],
        "location_organization_share": [{"id": "synthetic-share", "reason": "fixture"}],
        "location_tenant_transfer": [{"id": "synthetic-transfer", "status": "pending"}],
    }
    expected = {
        "identities": rows_by_table["operator_identity"],
        "grants": rows_by_table["operator_scope_grant"],
        "memberships": rows_by_table["operator_organization_membership"],
        "shares": rows_by_table["location_organization_share"],
        "tenant_transfers": rows_by_table["location_tenant_transfer"],
    }
    connections = []

    class FakeResult:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

    class FakeConnection:
        def __init__(self):
            self.closed = False
            self.queries = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True
            return False

        def execute(self, query):
            normalized = " ".join(query.lower().split())
            self.queries.append(normalized)
            for table, rows in rows_by_table.items():
                if f"from {table}" in normalized:
                    return FakeResult(rows)
            raise AssertionError(f"unexpected operator-list query: {normalized}")

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(operator_cli, "get_connection", make_connection)
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.gateway.operator_cli", "list"]
        operator_cli.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(unified_cli.app, ["operator", "--", "list"])

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert json.loads(unified.output) == expected
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    assert all(len(connection.queries) == 5 for connection in connections)
    assert all(
        all("operator_session" not in query for query in connection.queries)
        for connection in connections
    )
    assert unified.stderr == ""


def test_operator_identity_disable_cli_matches_and_revokes_sessions(monkeypatch, capsys) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.gateway import operator_cli

    operator_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    identity = {"id": operator_id, "issuer": "https://identity.example.test", "enabled": False}
    connections = []

    class FakeResult:
        def __init__(self, row=None):
            self.row = row

        def first(self):
            return self.row

    class FakeConnection:
        def __init__(self):
            self.closed = False
            self.statements = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True
            return False

        def execute(self, query, parameters):
            normalized = " ".join(query.lower().split())
            self.statements.append((normalized, parameters))
            if normalized.startswith("update operator_identity"):
                return FakeResult(identity)
            if normalized.startswith("update operator_session"):
                return FakeResult()
            raise AssertionError(f"unexpected operator identity SQL: {normalized}")

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(operator_cli, "get_connection", make_connection)
    arguments = ["identity", "disable", "--operator-id", operator_id]
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.gateway.operator_cli", *arguments]
        operator_cli.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(unified_cli.app, ["operator", "--", *arguments])

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert json.loads(unified.output) == identity
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    for connection in connections:
        assert len(connection.statements) == 2
        assert connection.statements[0][0].startswith("update operator_identity")
        assert connection.statements[1][0].startswith("update operator_session")
        assert all(params == {"operator_id": operator_id} for _query, params in connection.statements)
    assert unified.stderr == ""


def test_database_backed_metrics_catalogue_output_matches_with_stubbed_cursor(
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.ingestion import base as ingestion_base
    from services.metrics import cli as metrics_cli

    rows = [{
        "metric_key": "soil_carbon",
        "display_name": "Soil carbon",
        "description": "Synthetic metric.",
        "formula": "fixture",
        "unit": "t/ha",
        "data_type": "numeric",
        "update_frequency": "annual",
        "active": True,
        "version": "1.0",
    }]
    connections = []

    class FakeCursor:
        query = ""

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query):
            self.query = query

        def fetchall(self):
            return rows

    class FakeConnection:
        closed = False

        def __init__(self):
            self.fake_cursor = FakeCursor()

        def cursor(self):
            return self.fake_cursor

        def close(self):
            self.closed = True

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(ingestion_base, "get_db", make_connection)
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.metrics.cli", "--list", "--json"]
        metrics_cli.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(unified_cli.app, ["metrics", "--", "--list", "--json"])

    assert unified.exit_code == 0, unified.output
    assert json.loads(unified.output) == json.loads(standalone_output) == rows
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    assert all("FROM metric_definition" in connection.fake_cursor.query for connection in connections)
    assert all("ORDER BY metric_key" in connection.fake_cursor.query for connection in connections)
    assert unified.stderr == ""


def test_database_backed_forecast_catalogue_output_matches_with_stubbed_cursor(
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.forecast import cli as forecast_cli
    from services.ingestion import base as ingestion_base

    rows = [("synthetic-scenario", "Baseline fixture", "farm", "active", "synthetic-location")]
    connections = []

    class FakeCursor:
        query = ""

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query):
            self.query = query

        def fetchall(self):
            return rows

    class FakeConnection:
        closed = False

        def __init__(self):
            self.fake_cursor = FakeCursor()

        def cursor(self):
            return self.fake_cursor

        def close(self):
            self.closed = True

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(ingestion_base, "get_db", make_connection)
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.forecast.cli", "--list"]
        forecast_cli.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(unified_cli.app, ["forecast", "--", "--list"])

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert "Baseline fixture" in unified.output
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    assert all("FROM forecast_scenario" in connection.fake_cursor.query for connection in connections)
    assert unified.stderr == ""


def test_forecast_catalogue_closes_connection_when_query_fails(monkeypatch) -> None:
    from services.forecast import cli as forecast_cli
    from services.ingestion import base as ingestion_base

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _query):
            raise RuntimeError("synthetic forecast catalogue failure")

    class FakeConnection:
        closed = False

        def cursor(self):
            return FakeCursor()

        def close(self):
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr(ingestion_base, "get_db", lambda: connection)
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.forecast.cli", "--list"]
        with pytest.raises(RuntimeError, match="synthetic forecast catalogue failure"):
            forecast_cli.main()
    finally:
        sys.argv = original_argv

    assert connection.closed is True


def test_database_backed_analytics_emission_factor_output_matches_with_stubbed_query(
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.analytics import carbon_balance
    from services.analytics import cli as analytics_cli

    rows = [{"factor_key": "synthetic_factor", "value": 1.25, "unit": "kg_co2e"}]
    query_connections = []
    connections = []

    class FakeConnection:
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True
            return False

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    def fake_list_emission_factors(connection):
        query_connections.append(connection)
        return rows

    monkeypatch.setattr(analytics_cli, "get_connection", make_connection)
    monkeypatch.setattr(carbon_balance, "list_emission_factors", fake_list_emission_factors)
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.analytics.cli", "--emission-factors"]
        analytics_cli.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(unified_cli.app, ["analytics", "--", "--emission-factors"])

    assert unified.exit_code == 0, unified.output
    assert json.loads(unified.output) == json.loads(standalone_output) == rows
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    assert query_connections == connections
    assert unified.stderr == ""


def test_database_backed_crisp_weights_output_matches_with_stubbed_query(
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.crisp import scoring_engine

    crisp_cli = importlib.import_module("services.crisp.cli")
    weights = {"climate": 0.3, "soil": 0.7}
    query_calls = []
    connections = []

    class FakeConnection:
        closed = False

        def close(self):
            self.closed = True

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    def fake_query_location_weights(connection, location_id):
        query_calls.append((connection, location_id))
        return weights

    monkeypatch.setattr(crisp_cli, "get_db", make_connection)
    monkeypatch.setattr(scoring_engine, "_query_location_weights", fake_query_location_weights)
    arguments = ["--weights", "--location-id", "synthetic-location"]
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.crisp.cli", *arguments]
        crisp_cli.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(unified_cli.app, ["crisp", "--", *arguments])

    assert unified.exit_code == 0, unified.output
    expected = {"location_id": "synthetic-location", "weights": weights}
    assert json.loads(unified.output) == json.loads(standalone_output) == expected
    assert query_calls == [
        (connections[0], "synthetic-location"),
        (connections[1], "synthetic-location"),
    ]
    assert all(connection.closed for connection in connections)
    assert unified.stderr == ""


def test_crisp_weights_closes_connection_when_query_fails(monkeypatch) -> None:
    from services.crisp import scoring_engine

    crisp_cli = importlib.import_module("services.crisp.cli")

    class FakeConnection:
        closed = False

        def close(self):
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr(crisp_cli, "get_db", lambda: connection)

    def fail_query(*_args, **_kwargs):
        raise RuntimeError("synthetic CRISP weight failure")

    monkeypatch.setattr(scoring_engine, "_query_location_weights", fail_query)
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.crisp.cli", "--weights", "--location-id", "synthetic-location"]
        with pytest.raises(RuntimeError, match="synthetic CRISP weight failure"):
            crisp_cli.main()
    finally:
        sys.argv = original_argv

    assert connection.closed is True


def test_database_backed_delphi_study_list_matches_and_closes_connection(
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.delphi import cli as delphi_cli

    rows = [("synthetic-study", "Delphi fixture", "open")]
    connections = []

    class FakeCursor:
        description = [("id",), ("title",), ("status",)]
        query = ""
        closed = False

        def execute(self, query):
            self.query = query

        def fetchall(self):
            return rows

        def close(self):
            self.closed = True

    class FakeConnection:
        closed = False

        def __init__(self):
            self.fake_cursor = FakeCursor()

        def cursor(self):
            return self.fake_cursor

        def close(self):
            self.closed = True

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(delphi_cli, "_get_conn", make_connection)
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.delphi.cli", "list-studies"]
        delphi_cli.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(unified_cli.app, ["delphi", "--", "list-studies"])

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert json.loads(unified.output) == {"id": "synthetic-study", "title": "Delphi fixture", "status": "open"}
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    assert all(connection.fake_cursor.closed for connection in connections)
    assert all("FROM delphi_study" in connection.fake_cursor.query for connection in connections)
    assert unified.stderr == ""


def test_delphi_study_list_closes_cursor_and_connection_when_query_fails(monkeypatch) -> None:
    from services.delphi import cli as delphi_cli

    class FakeCursor:
        closed = False

        def execute(self, _query):
            raise RuntimeError("synthetic Delphi study query failure")

        def close(self):
            self.closed = True

    class FakeConnection:
        closed = False

        def __init__(self):
            self.fake_cursor = FakeCursor()

        def cursor(self):
            return self.fake_cursor

        def close(self):
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr(delphi_cli, "_get_conn", lambda: connection)
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.delphi.cli", "list-studies"]
        with pytest.raises(RuntimeError, match="synthetic Delphi study query failure"):
            delphi_cli.main()
    finally:
        sys.argv = original_argv

    assert connection.fake_cursor.closed is True
    assert connection.closed is True


def test_database_backed_capability_list_output_matches_with_stubbed_query(monkeypatch, capsys) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.analytics import cli_capability_map

    calls: list[dict[str, object]] = []
    result_rows = [{"id": "synthetic-capability", "name": "Soil monitoring", "status": "active"}]

    def fake_list_capabilities(*, guild_key, capability_type, status):
        calls.append({"guild_key": guild_key, "capability_type": capability_type, "status": status})
        return result_rows

    monkeypatch.setattr(cli_capability_map, "list_capabilities", fake_list_capabilities)
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.analytics.cli_capability_map", "list", "--status", "active"]
        cli_capability_map.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(
        unified_cli.app,
        ["capability-map", "--", "list", "--status", "active"],
    )

    assert unified.exit_code == 0, unified.output
    assert json.loads(unified.output) == json.loads(standalone_output)
    assert json.loads(unified.output) == result_rows
    assert calls == [
        {"guild_key": None, "capability_type": None, "status": "active"},
        {"guild_key": None, "capability_type": None, "status": "active"},
    ]
    assert unified.stderr == ""


@pytest.mark.parametrize(
    ("group", "module_path", "arguments", "query_name", "expected_kwargs"),
    [
        (
            "stakeholders",
            "services.analytics.cli_stakeholders",
            ["list", "--party-type", "organization"],
            "list_parties",
            {"party_type": "organization", "status": None},
        ),
        (
            "strategy-map",
            "services.analytics.cli_strategy_map",
            ["list", "--perspective", "financial"],
            "list_strategy_entries",
            {"perspective": "financial", "strategic_theme": None, "status": None},
        ),
        (
            "value-stream-defs",
            "services.analytics.cli_value_stream_defs",
            ["list", "--stakeholder", "farmer"],
            "list_streams",
            {"stakeholder_type": "farmer", "status": "active"},
        ),
        (
            "vision-mission",
            "services.analytics.cli_vision_mission",
            ["current", "--entity-type", "organization"],
            "get_current_statements",
            {"entity_type": "organization"},
        ),
        (
            "technology-roadmap",
            "services.analytics.cli_technology_roadmap",
            ["list", "--entity-type", "location"],
            "list_roadmaps",
            {"status": None, "entity_type": "location"},
        ),
    ],
)
def test_database_backed_read_cli_output_matches_with_stubbed_query(
    group: str,
    module_path: str,
    arguments: list[str],
    query_name: str,
    expected_kwargs: dict[str, object],
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli

    cli_module = importlib.import_module(module_path)
    query_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    rows = [{"id": "synthetic-row", "label": "Parity fixture"}]

    def fake_query(*args, **kwargs):
        query_calls.append((args, kwargs))
        return rows

    monkeypatch.setattr(cli_module, query_name, fake_query)
    connection = None
    if group == "stakeholders":
        class FakeConnection:
            closed = False

            def close(self) -> None:
                self.closed = True

        connection = FakeConnection()
        monkeypatch.setattr(cli_module, "get_db", lambda: connection)

    original_argv = list(sys.argv)
    try:
        sys.argv = [module_path, *arguments]
        cli_module.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(unified_cli.app, [group, "--", *arguments])

    assert unified.exit_code == 0, unified.output
    assert json.loads(unified.output) == json.loads(standalone_output) == rows
    assert len(query_calls) == 2
    if connection is not None:
        assert query_calls[0][0] == (connection,)
        assert connection.closed is True
    else:
        assert query_calls[0][0] == ()
    assert query_calls[0][1] == query_calls[1][1] == expected_kwargs
    assert unified.stderr == ""


@pytest.mark.parametrize(
    (
        "group",
        "module_path",
        "arguments",
        "query_path",
        "connection_factory_name",
        "expected_query_args",
        "expected_kwargs",
    ),
    [
        (
            "consent",
            "services.analytics.cli_consent",
            ["list", "--party-id", "synthetic-party", "--status", "active"],
            "list_effective_consent",
            "get_db",
            ("<connection>", "synthetic-party"),
            {"effective_status": "active"},
        ),
        (
            "coordination",
            "services.analytics.cli_coordination",
            ["list", "--status", "approved", "--type", "alliance"],
            "list_alliances",
            None,
            (),
            {"status": "approved", "coordination_type": "alliance"},
        ),
        (
            "governance-proposals",
            "services.analytics.cli_governance_proposals",
            ["list", "--circle-id", "synthetic-circle", "--status", "submitted"],
            "list_proposals",
            "_connection",
            ("<connection>",),
            {"circle_id": "synthetic-circle", "status": "submitted"},
        ),
        (
            "stakeholder-decisions",
            "services.analytics.cli_stakeholder_decisions",
            ["list", "--status", "approved", "--scope-id", "synthetic-scope"],
            "decisions.list_decisions",
            "get_db",
            ("<connection>",),
            {"status": "approved", "scope_id": "synthetic-scope"},
        ),
        (
            "stakeholder-engagement",
            "services.analytics.cli_stakeholder_engagement",
            ["list-plans", "--stakeholder-party-id", "synthetic-party", "--status", "active"],
            "list_plans",
            "get_db",
            ("<connection>",),
            {"stakeholder_party_id": "synthetic-party", "status": "active"},
        ),
        (
            "governance",
            "services.analytics.cli_governance_roles",
            ["circle-list", "--status", "active", "--scope-type", "location"],
            "list_circles",
            "_connection",
            ("<connection>",),
            {"status": "active", "scope_type": "location"},
        ),
        (
            "governance-links",
            "services.analytics.cli_governance_links",
            ["list", "--source-circle-id", "synthetic-source", "--status", "active"],
            "list_links",
            "_connection",
            ("<connection>",),
            {
                "source_circle_id": "synthetic-source",
                "target_circle_id": None,
                "party_id": None,
                "status": "active",
            },
        ),
        (
            "governance-tactical",
            "services.analytics.cli_governance_tactical",
            ["session-list", "--circle-id", "synthetic-circle", "--status", "active"],
            "list_sessions",
            "_connection",
            ("<connection>",),
            {"circle_id": "synthetic-circle", "status": "active"},
        ),
        (
            "governance-tensions",
            "services.analytics.cli_governance_tensions",
            ["list", "--circle-id", "synthetic-circle", "--status", "submitted", "--overdue-only"],
            "list_tensions",
            "_connection",
            ("<connection>",),
            {"circle_id": "synthetic-circle", "status": "submitted", "overdue_only": True},
        ),
        (
            "stakeholder-grievances",
            "services.analytics.cli_stakeholder_grievances",
            ["health", "--status", "submitted", "--overdue-only"],
            "list_case_health",
            "get_db",
            ("<connection>",),
            {"status": "submitted", "overdue_only": True},
        ),
        (
            "stakeholder-identity",
            "services.analytics.cli_stakeholder_identity",
            ["queue"],
            "identity.resolution_queue",
            "get_db",
            ("<connection>",),
            {},
        ),
        (
            "stakeholder-representation",
            "services.analytics.cli_stakeholder_representation",
            ["distribution-summary", "--scope-type", "location", "--scope-id", "synthetic-location"],
            "list_distribution_summary",
            "get_db",
            ("<connection>",),
            {"scope_type": "location", "scope_id": "synthetic-location"},
        ),
        (
            "stakeholder-trust",
            "services.analytics.cli_stakeholder_trust",
            ["timeline", "synthetic-party"],
            "trust.evidence_timeline",
            "get_db",
            ("<connection>", "synthetic-party"),
            {},
        ),
    ],
)
def test_database_backed_read_cli_output_matches_and_closes_connections(
    group: str,
    module_path: str,
    arguments: list[str],
    query_path: str,
    connection_factory_name: str | None,
    expected_query_args: tuple[object, ...],
    expected_kwargs: dict[str, object],
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli

    cli_module = importlib.import_module(module_path)
    rows = [{"id": "synthetic-governance-row", "status": "active"}]
    query_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    connections = []

    class FakeConnection:
        closed = False

        def close(self) -> None:
            self.closed = True

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    def fake_query(*args, **kwargs):
        query_calls.append((args, kwargs))
        return rows

    query_owner = cli_module
    query_name = query_path
    if "." in query_path:
        owner_path, query_name = query_path.rsplit(".", maxsplit=1)
        query_owner = getattr(cli_module, owner_path)
    monkeypatch.setattr(query_owner, query_name, fake_query)
    if connection_factory_name:
        monkeypatch.setattr(cli_module, connection_factory_name, make_connection)

    original_argv = list(sys.argv)
    try:
        sys.argv = [module_path, *arguments]
        cli_module.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(unified_cli.app, [group, "--", *arguments])

    assert unified.exit_code == 0, unified.output
    assert json.loads(unified.output) == json.loads(standalone_output) == rows
    assert len(query_calls) == 2
    for index, call in enumerate(query_calls):
        expected_args = tuple(
            connections[index] if value == "<connection>" else value
            for value in expected_query_args
        )
        assert call[0] == expected_args
    assert query_calls[0][1] == query_calls[1][1] == expected_kwargs
    if connection_factory_name:
        assert len(connections) == 2
        assert all(connection.closed for connection in connections)
    assert unified.stderr == ""


def test_governance_proposal_cli_closes_connection_when_query_fails(monkeypatch) -> None:
    from services.analytics import cli_governance_proposals

    class FakeConnection:
        closed = False

        def close(self) -> None:
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr(cli_governance_proposals, "_connection", lambda: connection)

    def fail_query(*_args, **_kwargs):
        raise RuntimeError("synthetic read failure")

    monkeypatch.setattr(cli_governance_proposals, "list_proposals", fail_query)
    original_argv = list(sys.argv)
    try:
        sys.argv = [
            "services.analytics.cli_governance_proposals",
            "list",
            "--status",
            "submitted",
        ]
        with pytest.raises(RuntimeError, match="synthetic read failure"):
            cli_governance_proposals.main()
    finally:
        sys.argv = original_argv

    assert connection.closed is True


@pytest.mark.parametrize(
    ("module_path", "arguments", "query_name"),
    [
        (
            "services.analytics.cli_governance_roles",
            ["circle-list", "--status", "active"],
            "list_circles",
        ),
        (
            "services.analytics.cli_governance_links",
            ["list", "--status", "active"],
            "list_links",
        ),
        (
            "services.analytics.cli_governance_tactical",
            ["session-list", "--status", "active"],
            "list_sessions",
        ),
        (
            "services.analytics.cli_governance_tensions",
            ["list", "--status", "submitted"],
            "list_tensions",
        ),
    ],
)
def test_governance_cli_closes_connection_when_read_fails(
    module_path: str,
    arguments: list[str],
    query_name: str,
    monkeypatch,
) -> None:
    cli_module = importlib.import_module(module_path)

    class FakeConnection:
        closed = False

        def close(self) -> None:
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr(cli_module, "_connection", lambda: connection)

    def fail_query(*_args, **_kwargs):
        raise RuntimeError("synthetic read failure")

    monkeypatch.setattr(cli_module, query_name, fail_query)
    original_argv = list(sys.argv)
    try:
        sys.argv = [module_path, *arguments]
        with pytest.raises(RuntimeError, match="synthetic read failure"):
            cli_module.main()
    finally:
        sys.argv = original_argv

    assert connection.closed is True


def test_database_backed_threatcasting_list_output_matches_and_closes_resources(
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.threatcasting import cli as threatcasting_cli

    columns = [("id",), ("threat_name",), ("threat_type",), ("is_active",)]
    rows = [("synthetic-threat", "Drought", "climate", True)]
    connections = []

    class FakeCursor:
        description = columns
        query = ""
        parameters = None
        closed = False

        def execute(self, query, parameters):
            self.query = query
            self.parameters = parameters

        def fetchall(self):
            return rows

        def close(self):
            self.closed = True

    class FakeConnection:
        closed = False

        def __init__(self):
            self.fake_cursor = FakeCursor()

        def cursor(self):
            return self.fake_cursor

        def close(self):
            self.closed = True

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(threatcasting_cli, "_get_conn", make_connection)
    arguments = [
        "list-threats",
        "--location-id",
        "synthetic-location",
        "--type",
        "climate",
    ]
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.threatcasting.cli", *arguments]
        threatcasting_cli.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(unified_cli.app, ["threatcasting", "--", *arguments])

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert json.loads(unified.output) == {
        "id": "synthetic-threat",
        "threat_name": "Drought",
        "threat_type": "climate",
        "is_active": True,
    }
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    assert all(connection.fake_cursor.closed for connection in connections)
    assert all("location_id = %s" in connection.fake_cursor.query for connection in connections)
    assert all("threat_type = %s" in connection.fake_cursor.query for connection in connections)
    assert all(
        connection.fake_cursor.parameters == ["synthetic-location", "climate"]
        for connection in connections
    )
    assert unified.stderr == ""


def test_threatcasting_list_closes_cursor_and_connection_when_query_fails(monkeypatch) -> None:
    from services.threatcasting import cli as threatcasting_cli

    class FakeCursor:
        closed = False

        def execute(self, *_args):
            raise RuntimeError("synthetic threat query failure")

        def close(self):
            self.closed = True

    class FakeConnection:
        closed = False

        def __init__(self):
            self.fake_cursor = FakeCursor()

        def cursor(self):
            return self.fake_cursor

        def close(self):
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr(threatcasting_cli, "_get_conn", lambda: connection)
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.threatcasting.cli", "list-threats"]
        with pytest.raises(RuntimeError, match="synthetic threat query failure"):
            threatcasting_cli.main()
    finally:
        sys.argv = original_argv

    assert connection.fake_cursor.closed is True
    assert connection.closed is True


def test_database_backed_export_snapshot_list_matches_and_closes_connection(
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.export import report_generator

    location_id = "12345678-1234-5678-1234-567812345678"
    snapshots = [{
        "id": "synthetic-snapshot",
        "report_type": "climate_impact",
        "status": "draft",
        "created_at": "2026-10-20",
        "snapshot_hash": "a" * 64,
    }]
    calls = []
    connections = []

    class FakeConnection:
        closed = False

        def close(self):
            self.closed = True

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    def fake_list_snapshots(connection, requested_location_id):
        calls.append((connection, requested_location_id))
        return snapshots

    monkeypatch.setattr(report_generator, "get_pg", make_connection)
    monkeypatch.setattr(report_generator, "list_snapshots", fake_list_snapshots)
    arguments = ["--list", "--location-id", location_id]
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.export.report_generator", *arguments]
        report_generator.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(unified_cli.app, ["export", "--", *arguments])

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert "climate_impact" in unified.output
    assert len(connections) == 2
    assert calls == [(connections[0], location_id), (connections[1], location_id)]
    assert all(connection.closed for connection in connections)
    assert unified.stderr == ""


def test_export_auto_closes_connection_if_run_creation_fails(
    monkeypatch,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.export import report_generator

    location_id = "12345678-1234-5678-1234-567812345678"
    secret_detail = "database password=synthetic-secret"
    connections = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, *_args):
            raise RuntimeError(secret_detail)

    class FakeConnection:
        closed = False

        def cursor(self):
            return FakeCursor()

        def close(self):
            self.closed = True

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(report_generator, "get_pg", make_connection)
    arguments = ["--auto", "--location-id", location_id]
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.export.report_generator", *arguments]
        with pytest.raises(RuntimeError, match="report generation failed \\(RuntimeError\\)") as error:
            report_generator.main()
    finally:
        sys.argv = original_argv
    assert secret_detail not in str(error.value)

    unified = CliRunner().invoke(unified_cli.app, ["export", "--", *arguments])

    assert isinstance(unified.exception, SystemExit)
    assert unified.exception.code == 1
    assert "Error: report generation failed (RuntimeError)" in unified.stderr
    assert secret_detail not in unified.stderr
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)


@pytest.mark.parametrize(
    ("arguments", "failure_point"),
    [
        (["--list"], "list"),
        (["--verify", "synthetic-hash"], "verify"),
        (["--list"], "connect"),
    ],
)
def test_export_cli_redacts_database_connection_and_read_failures(
    arguments: list[str],
    failure_point: str,
    monkeypatch,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.export import report_generator

    secret_detail = "database password=synthetic-secret"
    connections = []

    class FakeConnection:
        closed = False

        def close(self):
            self.closed = True

    def make_connection():
        if failure_point == "connect":
            raise RuntimeError(secret_detail)
        connection = FakeConnection()
        connections.append(connection)
        return connection

    def fail_query(*_args, **_kwargs):
        raise RuntimeError(secret_detail)

    monkeypatch.setattr(report_generator, "get_pg", make_connection)
    if failure_point == "list":
        monkeypatch.setattr(report_generator, "list_snapshots", fail_query)
    elif failure_point == "verify":
        monkeypatch.setattr(report_generator, "_verify_snapshot", fail_query)

    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.export.report_generator", *arguments]
        with pytest.raises(
            RuntimeError,
            match="report generation failed \\(RuntimeError\\)",
        ) as error:
            report_generator.main()
    finally:
        sys.argv = original_argv

    assert secret_detail not in str(error.value)
    unified = CliRunner().invoke(unified_cli.app, ["export", "--", *arguments])

    assert isinstance(unified.exception, SystemExit)
    assert unified.exception.code == 1
    assert "Error: report generation failed (RuntimeError)" in unified.stderr
    assert secret_detail not in unified.stderr
    expected_connections = 0 if failure_point == "connect" else 2
    assert len(connections) == expected_connections
    assert all(connection.closed for connection in connections)


def test_export_snapshot_verify_matches_standalone_and_unified_cli(
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.export import report_generator

    calls = []
    connections = []

    class FakeConnection:
        closed = False

        def close(self):
            self.closed = True

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    def fake_verify(connection, snapshot_hash):
        calls.append((connection, snapshot_hash))
        print("Result: PASS -- hash matches, report is intact")

    monkeypatch.setattr(report_generator, "get_pg", make_connection)
    monkeypatch.setattr(report_generator, "_verify_snapshot", fake_verify)
    arguments = ["--verify", "synthetic-snapshot-hash"]
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.export.report_generator", *arguments]
        report_generator.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(unified_cli.app, ["export", "--", *arguments])

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert unified.output.strip() == "Result: PASS -- hash matches, report is intact"
    assert calls == [
        (connections[0], "synthetic-snapshot-hash"),
        (connections[1], "synthetic-snapshot-hash"),
    ]
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    assert unified.stderr == ""


def test_export_report_generation_matches_standalone_and_unified_cli(
    monkeypatch,
    capsys,
) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.export import report_generator

    location_id = "11111111-1111-4111-8111-111111111111"
    report_data = {"report_type": "farm_summary", "rows": [{"count": 3}]}
    connections = []
    calculations = []
    snapshots = []

    class FakeConnection:
        def __init__(self):
            self.autocommit = False
            self.read_only = False
            self.session_modes = []
            self.rollbacks = 0
            self.commits = 0
            self.closed = False

        def set_session(self, *, readonly):
            self.read_only = readonly
            self.session_modes.append(readonly)

        def rollback(self):
            self.rollbacks += 1
            self.read_only = False

        def commit(self):
            self.commits += 1

        def close(self):
            self.closed = True

    def make_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    def generate_report(connection, selected_location, period_start, period_end):
        calculations.append(
            (connection.read_only, selected_location, period_start, period_end)
        )
        return report_data

    def store_snapshot(connection, data, selected_location, period_start, period_end):
        snapshots.append(
            (connection.read_only, data, selected_location, period_start, period_end)
        )
        connection.commit()
        return "synthetic-snapshot-id"

    monkeypatch.setattr(report_generator, "get_pg", make_connection)
    monkeypatch.setattr(report_generator, "REPORT_GENERATORS", {"farm_summary": generate_report})
    monkeypatch.setattr(report_generator, "store_snapshot", store_snapshot)
    monkeypatch.setattr(report_generator, "compute_hash", lambda _data: "synthetic-hash")
    arguments = ["--type", "farm_summary", "--location-id", location_id]
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.export.report_generator", *arguments]
        report_generator.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(unified_cli.app, ["export", "--", *arguments])

    assert unified.exit_code == 0, unified.output
    assert unified.output == standalone_output
    assert standalone_output.splitlines() == [
        f"Generating farm_summary report for {location_id}...",
        "Snapshot stored: synthetic-snapshot-id",
        "Hash: synthetic-hash",
        "Report type: farm_summary",
    ]
    assert calculations == [
        (True, location_id, None, None),
        (True, location_id, None, None),
    ]
    assert snapshots == [
        (False, report_data, location_id, None, None),
        (False, report_data, location_id, None, None),
    ]
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    assert all(connection.rollbacks == 1 for connection in connections)
    assert all(connection.session_modes == [True, False] for connection in connections)
    assert all(connection.commits == 1 for connection in connections)
    assert unified.stderr == ""
