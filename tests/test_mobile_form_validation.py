from __future__ import annotations

import pytest

from services.mobile.form_validation import (
    FormPayloadInvalid,
    FormSchemaUnavailable,
    validate_form_payload,
)

FORM_SCHEMA = {
    "type": "object",
    "required": ["activity_date", "activity_type"],
    "properties": {
        "activity_date": {"type": "string", "format": "date"},
        "activity_type": {"type": "string", "enum": ["planting", "weeding"]},
        "labor_hours": {"type": "number", "minimum": 0},
    },
    "additionalProperties": False,
}


def test_valid_form_payload_passes_declared_schema():
    validate_form_payload(
        FORM_SCHEMA,
        {"activity_date": "2026-10-12", "activity_type": "weeding", "labor_hours": 1.5},
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"activity_date": "2026-10-12", "activity_type": "weeding", "worker_name": "Ada"},
        {"activity_date": "not-a-date", "activity_type": "weeding"},
        {"activity_date": "2026-10-12", "activity_type": "unknown"},
        {"activity_date": "2026-10-12", "activity_type": "weeding", "labor_hours": -1},
        {"activity_date": "2026-10-12"},
    ],
)
def test_invalid_payload_is_rejected(payload):
    with pytest.raises(FormPayloadInvalid):
        validate_form_payload(FORM_SCHEMA, payload)


def test_remote_schema_reference_is_rejected_without_fetching():
    with pytest.raises(FormSchemaUnavailable):
        validate_form_payload({"$ref": "https://example.invalid/schema.json"}, {})


def test_invalid_stored_schema_fails_closed():
    with pytest.raises(FormSchemaUnavailable):
        validate_form_payload({"type": "not-a-json-schema-type"}, {})
