from __future__ import annotations

import json
from argparse import Namespace
from copy import deepcopy

import pytest

from services.mobile import forms_cli
from services.mobile.forms_cli import FormManifestInvalid, preview_manifests, publish_manifest, validate_manifest


def manifest() -> dict:
    return {
        "form_id": "field_note_custom",
        "version": "1.0.0",
        "name": "Field Note",
        "description": "Record an ecological observation.",
        "form_schema": {
            "type": "object",
            "required": ["note"],
            "properties": {"note": {"type": "string", "title": "Observation"}},
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
            "purpose": "Location-scoped ecological observation.",
            "scope_type": "location",
            "scope_id": None,
            "recipient_type": "location_operator",
            "recipient_party_id": None,
            "recipient_name": None,
            "version": None,
        },
        "review": {
            "reviewed_by": "reviewer-1",
            "reviewed_at": "2026-10-12T12:00:00Z",
            "evidence": [{"source": "pilot-policy", "basis": "Operational observation only."}],
        },
    }


def test_manifest_validation_returns_safe_summary_without_database_write():
    summary = validate_manifest(manifest())

    assert summary == {
        "form_id": "field_note_custom",
        "version": "1.0.0",
        "name": "Field Note",
        "collection_type": "field_note",
        "status": "active",
        "location_id": None,
        "consent_policy_status": "not_required",
        "reviewed_by": "reviewer-1",
        "field_count": 1,
        "evidence_count": 1,
        "database_write": False,
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["form_schema"].update({"additionalProperties": True}),
        lambda value: value["form_schema"]["properties"].update({"remote": {"$ref": "https://example.invalid/schema.json"}}),
        lambda value: value.update({"unexpected": "value"}),
        lambda value: value["consent_policy"].update({"status": "unclassified"}),
        lambda value: value["review"].update({"evidence": []}),
        lambda value: value["consent_policy"].update({"scope_id": "not-a-uuid"}),
    ],
)
def test_manifest_fails_closed_on_unsafe_or_incomplete_policy(mutate):
    candidate = manifest()
    mutate(candidate)

    with pytest.raises(FormManifestInvalid):
        validate_manifest(candidate)


def test_preview_accepts_unchanged_manifest_and_new_revision():
    current = manifest()

    unchanged = preview_manifests(deepcopy(current), deepcopy(current))
    assert unchanged["change"] == "unchanged"

    proposed = deepcopy(current)
    proposed["version"] = "1.1.0"
    proposed["name"] = "Updated Field Note"
    revision = preview_manifests(proposed, current)
    assert revision["change"] == "new_immutable_revision"
    assert revision["publication"] == "not applied"


@pytest.mark.parametrize(
    "change",
    [
        lambda proposed, current: proposed["form_schema"]["properties"].update({"extra": {"type": "string"}}),
        lambda proposed, current: proposed.update({"version": "0.9.0"}),
        lambda proposed, current: proposed.update({"form_id": "another_form"}),
    ],
)
def test_preview_rejects_version_reuse_downgrade_and_form_id_changes(change):
    current = manifest()
    proposed = deepcopy(current)
    change(proposed, current)

    with pytest.raises(FormManifestInvalid):
        preview_manifests(proposed, current)


class FakeResult:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class FakeConnection:
    def __init__(self, current=None, history=()):
        self.current = current
        self.history = set(history)
        self.statements = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _exc, _traceback):
        self.committed = exc_type is None
        self.rolled_back = exc_type is not None
        self.closed = True
        return False

    def execute(self, sql, params=None):
        params = params or {}
        self.statements.append((sql, params))
        if "FROM mobile_form WHERE form_id" in sql:
            return FakeResult([self.current] if self.current is not None else [])
        if "FROM mobile_form_version" in sql:
            version = params["version"]
            return FakeResult([{"version": version}] if version in self.history else [])
        return FakeResult()


def _publish(candidate, connection, **kwargs):
    return publish_manifest(
        candidate,
        actor="operator-1",
        expected_current_version=kwargs.get("expected_current_version"),
        expect_absent=kwargs.get("expect_absent", False),
        connection_factory=lambda: connection,
    )


def test_publish_new_form_uses_trigger_boundary_and_transaction_local_actor():
    candidate = manifest()
    connection = FakeConnection()

    result = _publish(candidate, connection, expect_absent=True)

    assert result["operation"] == "form_created"
    assert connection.committed and connection.closed and not connection.rolled_back
    assert connection.statements[0][0].startswith("SELECT set_config('kokonut.actor'")
    writes = [sql for sql, _params in connection.statements if sql.lstrip().startswith(("INSERT", "UPDATE"))]
    assert len(writes) == 1
    assert "INSERT INTO mobile_form (" in writes[0]
    assert "mobile_form_version" not in writes[0]
    insert_params = connection.statements[-1][1]
    assert insert_params["form_schema"] == json.dumps(candidate["form_schema"])


def test_publish_revision_checks_current_version_and_location_before_update():
    candidate = manifest()
    candidate["version"] = "1.1.0"
    connection = FakeConnection(
        current={"form_id": candidate["form_id"], "version": "1.0.0", "location_id": None},
        history={"1.0.0"},
    )

    result = _publish(candidate, connection, expected_current_version="1.0.0")

    assert result["operation"] == "revision_published"
    writes = [sql for sql, _params in connection.statements if sql.lstrip().startswith(("INSERT", "UPDATE"))]
    assert len(writes) == 1
    assert writes[0].lstrip().startswith("UPDATE mobile_form SET")
    assert "mobile_form_version" not in writes[0]


def test_publish_rejects_non_monotonic_revision_even_if_history_is_incomplete():
    candidate = manifest()
    candidate["version"] = "1.0.0"
    connection = FakeConnection(
        current={"form_id": candidate["form_id"], "version": "1.1.0", "location_id": None}
    )

    with pytest.raises(FormManifestInvalid, match="greater than the current version"):
        _publish(candidate, connection, expected_current_version="1.1.0")

    assert connection.rolled_back and connection.closed
    assert not any(sql.lstrip().startswith(("INSERT", "UPDATE")) for sql, _params in connection.statements)


@pytest.mark.parametrize(
    ("candidate_version", "current_version", "expected_version", "current_location", "history", "message"),
    [
        ("1.1.0", "1.0.0", "0.9.0", None, {"1.0.0"}, "current form version changed"),
        ("1.0.0", "1.0.0", "1.0.0", None, {"1.0.0"}, "already exists in immutable form history"),
        ("1.1.0", "1.0.0", "1.0.0", "b7b2a58a-3b9b-4f43-8113-1b2a85b14f91", {"1.0.0"}, "reassigned to another location"),
    ],
)
def test_publish_rejects_stale_reused_or_reassigned_revision(
    candidate_version, current_version, expected_version, current_location, history, message
):
    candidate = manifest()
    candidate["version"] = candidate_version
    connection = FakeConnection(
        current={"form_id": candidate["form_id"], "version": current_version, "location_id": current_location},
        history=history,
    )

    with pytest.raises(FormManifestInvalid, match=message):
        _publish(candidate, connection, expected_current_version=expected_version)

    assert connection.rolled_back and connection.closed
    assert not any(sql.lstrip().startswith(("INSERT", "UPDATE")) for sql, _params in connection.statements)


def test_publish_requires_independent_operator_before_opening_database():
    candidate = manifest()
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("database should not be opened")

    with pytest.raises(FormManifestInvalid, match="different from the manifest reviewer"):
        publish_manifest(
            candidate,
            actor="Reviewer-1",
            expected_current_version=None,
            expect_absent=True,
            connection_factory=connection_factory,
        )

    assert not opened


def test_publish_preview_command_never_opens_database(monkeypatch):
    candidate = manifest()
    monkeypatch.setattr(forms_cli, "_load_manifest", lambda _path: candidate)
    monkeypatch.setattr(
        "services.common.cli.get_connection",
        lambda: (_ for _ in ()).throw(AssertionError("preview opened the database")),
    )
    captured = []
    monkeypatch.setattr(forms_cli, "print_json", captured.append)

    forms_cli.publish_command(
        Namespace(manifest="manifest.json", current=None, actor=None, apply=False,
                  expected_current_version=None, expect_absent=False)
    )

    assert captured[0]["mode"] == "preview"
    assert captured[0]["publication"] == "not applied"
