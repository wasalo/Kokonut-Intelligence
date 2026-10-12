"""Offline validation and preview for reviewed Field Collector form manifests.

This CLI does not modify PostgreSQL. Publication is a separate, explicit
operation implemented through the mutable ``mobile_form`` source row so the
migration 381 trigger can create an immutable revision.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from services.common.cli import print_json, run
from services.mobile.form_validation import FormSchemaUnavailable, validate_form_schema

_FORM_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,99}$")
_POLICY_STATES = {"required", "not_required"}
_SCOPE_TYPES = {
    "network", "organization", "location", "farm", "cooperative",
    "value_stream", "initiative", "decision",
}


class FormManifestInvalid(ValueError):
    """Raised when a form manifest is unsafe or incomplete."""


def _object(value: Any, label: str, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FormManifestInvalid(f"{label} must be an object")
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        raise FormManifestInvalid(f"{label} contains unsupported fields")
    if missing:
        raise FormManifestInvalid(f"{label} is missing required fields")
    return value


def _text(value: Any, label: str, *, maximum: int, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise FormManifestInvalid(f"{label} must be a non-empty string no longer than {maximum} characters")
    if value != value.strip():
        raise FormManifestInvalid(f"{label} must not have leading or trailing whitespace")
    return value


def _uuid(value: Any, label: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str):
        raise FormManifestInvalid(f"{label} must be a UUID")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise FormManifestInvalid(f"{label} must be a UUID") from exc


def _validate_policy(policy_value: Any, review_value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = _object(
        policy_value,
        "consent_policy",
        {
            "status", "data_category", "purpose", "scope_type", "scope_id",
            "recipient_type", "recipient_party_id", "recipient_name", "version",
        },
        {"status", "data_category", "purpose", "scope_type", "scope_id", "recipient_type"},
    )
    status = policy["status"]
    if not isinstance(status, str) or status not in _POLICY_STATES:
        raise FormManifestInvalid("consent_policy.status must be required or not_required")
    _text(policy["data_category"], "consent_policy.data_category", maximum=200)
    _text(policy["purpose"], "consent_policy.purpose", maximum=2000)
    scope_type = policy["scope_type"]
    if not isinstance(scope_type, str) or scope_type not in _SCOPE_TYPES:
        raise FormManifestInvalid("consent_policy.scope_type is unsupported")
    scope_id = _uuid(policy["scope_id"], "consent_policy.scope_id", optional=True)
    if (scope_type in {"network", "location"}) != (scope_id is None):
        raise FormManifestInvalid("consent_policy.scope_id does not match its scope_type")
    _text(policy["recipient_type"], "consent_policy.recipient_type", maximum=100)
    _uuid(policy.get("recipient_party_id"), "consent_policy.recipient_party_id", optional=True)
    _text(policy.get("recipient_name"), "consent_policy.recipient_name", maximum=300, optional=True)
    if status == "required":
        _text(policy.get("version"), "consent_policy.version", maximum=100)
    elif policy.get("version") is not None:
        _text(policy["version"], "consent_policy.version", maximum=100)

    review = _object(
        review_value,
        "review",
        {"reviewed_by", "reviewed_at", "evidence"},
        {"reviewed_by", "reviewed_at", "evidence"},
    )
    _text(review["reviewed_by"], "review.reviewed_by", maximum=200)
    reviewed_at = review["reviewed_at"]
    if not isinstance(reviewed_at, str):
        raise FormManifestInvalid("review.reviewed_at must be an ISO-8601 timestamp with timezone")
    try:
        parsed = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FormManifestInvalid("review.reviewed_at must be an ISO-8601 timestamp with timezone") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FormManifestInvalid("review.reviewed_at must include a timezone")
    evidence = review["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise FormManifestInvalid("review.evidence must be a non-empty array")
    for item in evidence:
        entry = _object(item, "review.evidence item", {"source", "basis"}, {"source", "basis"})
        _text(entry["source"], "review.evidence.source", maximum=1000)
        _text(entry["basis"], "review.evidence.basis", maximum=2000)
    return policy, review


def validate_manifest(value: Any) -> dict[str, Any]:
    """Validate a reviewed JSON manifest and return a safe summary."""
    manifest = _object(
        value,
        "manifest",
        {
            "form_id", "version", "name", "description", "form_schema", "ui_schema",
            "collection_type", "location_id", "is_public", "min_app_version", "status",
            "consent_policy", "review",
        },
        {
            "form_id", "version", "name", "description", "form_schema",
            "collection_type", "consent_policy", "review",
        },
    )
    form_id = _text(manifest["form_id"], "form_id", maximum=200)
    if not _FORM_ID.fullmatch(form_id):
        raise FormManifestInvalid("form_id contains unsupported characters")
    version = _text(manifest["version"], "version", maximum=50)
    if not _VERSION.fullmatch(version):
        raise FormManifestInvalid("version must use numeric semantic versioning (MAJOR.MINOR.PATCH)")
    name = _text(manifest["name"], "name", maximum=300)
    _text(manifest["description"], "description", maximum=10000, optional=True)
    collection_type = _text(manifest["collection_type"], "collection_type", maximum=100)
    if not _IDENTIFIER.fullmatch(collection_type):
        raise FormManifestInvalid("collection_type must be a lowercase identifier")
    status = manifest.get("status", "active")
    if not isinstance(status, str) or status not in {"active", "inactive"}:
        raise FormManifestInvalid("status must be active or inactive; retire a revision through its lifecycle")
    is_public = manifest.get("is_public", False)
    if not isinstance(is_public, bool):
        raise FormManifestInvalid("is_public must be a boolean")
    location_id = _uuid(manifest.get("location_id"), "location_id", optional=True)
    _text(manifest.get("min_app_version"), "min_app_version", maximum=50, optional=True)
    ui_schema = manifest.get("ui_schema", {})
    if not isinstance(ui_schema, dict):
        raise FormManifestInvalid("ui_schema must be an object")

    schema = manifest["form_schema"]
    try:
        validate_form_schema(schema)
    except FormSchemaUnavailable as exc:
        raise FormManifestInvalid("form_schema is invalid or contains a non-local reference") from exc
    if schema.get("additionalProperties") is not False:
        raise FormManifestInvalid("form_schema must reject undeclared root properties")
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise FormManifestInvalid("form_schema must define at least one property")
    if any(not _IDENTIFIER.fullmatch(key) for key in properties):
        raise FormManifestInvalid("form_schema property names must be lowercase identifiers")

    policy, review = _validate_policy(manifest["consent_policy"], manifest["review"])
    return {
        "form_id": form_id,
        "version": version,
        "name": name,
        "collection_type": collection_type,
        "status": status,
        "location_id": location_id,
        "consent_policy_status": policy["status"],
        "reviewed_by": review["reviewed_by"],
        "field_count": len(properties),
        "evidence_count": len(review["evidence"]),
        "database_write": False,
    }


def _load_manifest(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise FormManifestInvalid("manifest file could not be read") from exc
    except json.JSONDecodeError as exc:
        raise FormManifestInvalid(f"manifest is not valid JSON at line {exc.lineno}, column {exc.colno}") from exc
    if not isinstance(value, dict):
        raise FormManifestInvalid("manifest must be a JSON object")
    return value


def validate_command(args: argparse.Namespace) -> None:
    summary = validate_manifest(_load_manifest(args.manifest))
    print_json({"valid": True, "manifest": summary})


def preview_manifests(proposed_value: Any, current_value: Any | None = None) -> dict[str, Any]:
    """Return a safe offline preview and reject immutable-version reuse."""
    proposed = _object(
        proposed_value,
        "manifest",
        {
            "form_id", "version", "name", "description", "form_schema", "ui_schema",
            "collection_type", "location_id", "is_public", "min_app_version", "status",
            "consent_policy", "review",
        },
        {
            "form_id", "version", "name", "description", "form_schema",
            "collection_type", "consent_policy", "review",
        },
    )
    summary = validate_manifest(proposed)
    result: dict[str, Any] = {"valid": True, "publication": "not applied", "manifest": summary}
    if current_value is not None:
        current = _object(
            current_value,
            "current manifest",
            {
                "form_id", "version", "name", "description", "form_schema", "ui_schema",
                "collection_type", "location_id", "is_public", "min_app_version", "status",
                "consent_policy", "review",
            },
            {
                "form_id", "version", "name", "description", "form_schema",
                "collection_type", "consent_policy", "review",
            },
        )
        current_summary = validate_manifest(current)
        if current_summary["form_id"] != summary["form_id"]:
            raise FormManifestInvalid("current and proposed form_id values must match")
        current_version = tuple(int(part) for part in current_summary["version"].split("."))
        proposed_version = tuple(int(part) for part in summary["version"].split("."))
        if proposed_version < current_version:
            raise FormManifestInvalid("proposed version must be greater than the current version")
        if proposed_version == current_version:
            if proposed != current:
                raise FormManifestInvalid("content or review metadata changed without a new version")
            change = "unchanged"
        else:
            change = "new_immutable_revision"
        result["current"] = current_summary
        result["change"] = change
    else:
        result["change"] = "version_comparison_not_supplied"
    return result


def preview_command(args: argparse.Namespace) -> None:
    proposed = _load_manifest(args.manifest)
    current = _load_manifest(args.current) if args.current else None
    result = preview_manifests(proposed, current)
    print_json(result)


def _location_key(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise FormManifestInvalid("stored form location is invalid; refusing publication") from exc


def publish_manifest(
    manifest: dict[str, Any],
    *,
    actor: str,
    expected_current_version: str | None,
    expect_absent: bool,
    connection_factory=None,
) -> dict[str, Any]:
    """Publish one reviewed revision through ``mobile_form`` in one transaction.

    The database trigger on ``mobile_form`` owns immutable snapshot creation and
    retirement of the previous revision. The CLI never writes
    ``mobile_form_version`` directly.
    """
    summary = validate_manifest(manifest)
    actor = _text(actor, "actor", maximum=200)
    if any(ord(character) < 32 or ord(character) == 127 for character in actor):
        raise FormManifestInvalid("actor contains unsupported control characters")
    if actor.casefold() == summary["reviewed_by"].casefold():
        raise FormManifestInvalid("publisher must be different from the manifest reviewer")
    if expect_absent == (expected_current_version is not None):
        raise FormManifestInvalid("specify exactly one expected-current-version or expect-absent condition")
    if expected_current_version is not None and not _VERSION.fullmatch(expected_current_version):
        raise FormManifestInvalid("expected current version must use numeric semantic versioning")

    if connection_factory is None:
        from services.common.cli import get_connection

        connection_factory = get_connection

    policy = manifest["consent_policy"]
    review = manifest["review"]
    params = {
        "form_id": summary["form_id"],
        "name": manifest["name"],
        "description": manifest.get("description"),
        "form_schema": json.dumps(manifest["form_schema"]),
        "ui_schema": json.dumps(manifest.get("ui_schema", {})),
        "version": summary["version"],
        "collection_type": manifest["collection_type"],
        "status": manifest.get("status", "active"),
        "location_id": summary["location_id"],
        "is_public": manifest.get("is_public", False),
        "min_app_version": manifest.get("min_app_version"),
        "consent_policy_status": policy["status"],
        "consent_data_category": policy["data_category"],
        "consent_purpose": policy["purpose"],
        "consent_scope_type": policy["scope_type"],
        "consent_scope_id": policy["scope_id"],
        "consent_recipient_type": policy["recipient_type"],
        "consent_recipient_party_id": policy.get("recipient_party_id"),
        "consent_recipient_name": policy.get("recipient_name"),
        "consent_version": policy.get("version"),
        "consent_policy_reviewed_by": review["reviewed_by"],
        "consent_policy_reviewed_at": review["reviewed_at"],
        "consent_policy_evidence": json.dumps(review["evidence"]),
    }
    insert_sql = """
        INSERT INTO mobile_form (
            form_id, name, description, form_schema, ui_schema, version,
            collection_type, status, location_id, is_public, min_app_version,
            consent_policy_status, consent_data_category, consent_purpose,
            consent_scope_type, consent_scope_id, consent_recipient_type,
            consent_recipient_party_id, consent_recipient_name, consent_version,
            consent_policy_reviewed_by, consent_policy_reviewed_at,
            consent_policy_evidence
        ) VALUES (
            :form_id, :name, :description, :form_schema::jsonb,
            :ui_schema::jsonb, :version, :collection_type, :status,
            :location_id, :is_public, :min_app_version,
            :consent_policy_status, :consent_data_category, :consent_purpose,
            :consent_scope_type, :consent_scope_id, :consent_recipient_type,
            :consent_recipient_party_id, :consent_recipient_name, :consent_version,
            :consent_policy_reviewed_by, :consent_policy_reviewed_at,
            :consent_policy_evidence::jsonb
        )
    """
    update_sql = """
        UPDATE mobile_form SET
            name = :name, description = :description,
            form_schema = :form_schema::jsonb, ui_schema = :ui_schema::jsonb,
            version = :version, collection_type = :collection_type,
            status = :status, is_public = :is_public,
            min_app_version = :min_app_version,
            consent_policy_status = :consent_policy_status,
            consent_data_category = :consent_data_category,
            consent_purpose = :consent_purpose,
            consent_scope_type = :consent_scope_type,
            consent_scope_id = :consent_scope_id,
            consent_recipient_type = :consent_recipient_type,
            consent_recipient_party_id = :consent_recipient_party_id,
            consent_recipient_name = :consent_recipient_name,
            consent_version = :consent_version,
            consent_policy_reviewed_by = :consent_policy_reviewed_by,
            consent_policy_reviewed_at = :consent_policy_reviewed_at,
            consent_policy_evidence = :consent_policy_evidence::jsonb,
            updated_at = NOW()
        WHERE form_id = :form_id
    """

    with connection_factory() as conn:
        conn.execute(
            "SELECT set_config('kokonut.actor', :actor, true) AS actor",
            {"actor": actor},
        )
        current_rows = conn.execute(
            """SELECT form_id, version, location_id
                 FROM mobile_form WHERE form_id = :form_id FOR UPDATE""",
            {"form_id": summary["form_id"]},
        ).all()
        current = current_rows[0] if current_rows else None

        if expect_absent:
            if current is not None:
                raise FormManifestInvalid("form already exists; refresh the preview before publishing")
        elif current is None or current["version"] != expected_current_version:
            raise FormManifestInvalid("current form version changed; refresh the preview before publishing")

        historical = conn.execute(
            """SELECT version FROM mobile_form_version
                 WHERE form_id = :form_id AND version = :version LIMIT 1""",
            {"form_id": summary["form_id"], "version": summary["version"]},
        ).first()
        if historical:
            raise FormManifestInvalid("proposed version already exists in immutable form history")

        proposed_version = tuple(int(part) for part in summary["version"].split("."))
        if current is not None:
            current_version = current["version"]
            if not isinstance(current_version, str) or not _VERSION.fullmatch(current_version):
                raise FormManifestInvalid("current form version is invalid; refusing publication")
            if proposed_version <= tuple(int(part) for part in current_version.split(".")):
                raise FormManifestInvalid("proposed version must be greater than the current version")
            if _location_key(current["location_id"]) != summary["location_id"]:
                raise FormManifestInvalid("a published form cannot be reassigned to another location")
            conn.execute(update_sql, params)
            operation = "revision_published"
        else:
            conn.execute(insert_sql, params)
            operation = "form_created"

    return {
        "published": True,
        "operation": operation,
        "form_id": summary["form_id"],
        "version": summary["version"],
        "status": summary["status"],
        "actor": actor,
        "snapshot": "created_by_mobile_form_trigger",
    }


def publish_command(args: argparse.Namespace) -> None:
    proposed = _load_manifest(args.manifest)
    current = _load_manifest(args.current) if args.current else None
    preview = preview_manifests(proposed, current)
    if not args.apply:
        preview["mode"] = "preview"
        print_json(preview)
        return
    if not args.actor:
        raise FormManifestInvalid("--actor is required with --apply")
    if args.expect_absent == (args.expected_current_version is not None):
        raise FormManifestInvalid(
            "--apply requires exactly one of --expected-current-version or --expect-absent"
        )
    result = publish_manifest(
        proposed,
        actor=args.actor,
        expected_current_version=args.expected_current_version,
        expect_absent=args.expect_absent,
    )
    print_json(result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate one reviewed JSON form manifest offline")
    validate.add_argument("--manifest", required=True)
    validate.set_defaults(func=validate_command)
    preview = commands.add_parser("preview", help="Validate and preview a form revision without database writes")
    preview.add_argument("--manifest", required=True)
    preview.add_argument("--current", help="Optional prior manifest used for version comparison")
    preview.set_defaults(func=preview_command)
    publish = commands.add_parser("publish", help="Preview a publication or apply a reviewed revision transactionally")
    publish.add_argument("--manifest", required=True)
    publish.add_argument("--current", help="Optional prior manifest for an offline preview comparison")
    publish.add_argument("--actor", help="Operator identity recorded by the revision snapshot trigger")
    publish.add_argument("--apply", action="store_true", help="Apply the publication in one database transaction")
    expected = publish.add_mutually_exclusive_group()
    expected.add_argument("--expected-current-version", help="Current database revision reviewed for this update")
    expected.add_argument("--expect-absent", action="store_true", help="Assert that this form_id is not yet published")
    publish.set_defaults(func=publish_command)
    args = parser.parse_args()
    run(args.func, args)


if __name__ == "__main__":
    main()
