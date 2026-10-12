from __future__ import annotations

from copy import deepcopy

import pytest

from services.mobile.forms_cli import FormManifestInvalid, preview_manifests, validate_manifest


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
