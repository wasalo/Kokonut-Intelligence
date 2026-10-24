"""Validation of Field Collector payloads against immutable form revisions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jsonschema import FormatChecker
from jsonschema.validators import validator_for


class FormSchemaUnavailable(ValueError):
    """The stored form schema is invalid or uses unsupported external refs."""


class FormPayloadInvalid(ValueError):
    """The submitted payload does not match the selected immutable form schema."""


def _reject_remote_refs(value: Any) -> None:
    if isinstance(value, Mapping):
        ref = value.get("$ref")
        if ref is not None and (not isinstance(ref, str) or not ref.startswith("#")):
            raise FormSchemaUnavailable("Form schemas may only use local references")
        for nested in value.values():
            _reject_remote_refs(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_remote_refs(nested)


def _validator_for_schema(schema: Any):
    """Return a locally constrained validator for a stored form schema."""
    if not isinstance(schema, Mapping):
        raise FormSchemaUnavailable("Stored form schema must be an object")

    _reject_remote_refs(schema)
    try:
        validator_type = validator_for(schema)
        validator_type.check_schema(schema)
        return validator_type
    except FormSchemaUnavailable:
        raise
    except Exception as exc:
        raise FormSchemaUnavailable("Stored form schema could not be evaluated") from exc


def validate_form_schema(schema: Any) -> None:
    """Validate a form schema without evaluating or exposing collection data.

    A form revision's ``properties`` define its accepted fields. The built-in
    schemas set ``additionalProperties`` to false, so unknown keys fail closed.
    Local references are supported; remote schema retrieval is deliberately
    disabled so collection requests never cause network access.
    """
    _validator_for_schema(schema)


def validate_form_payload(schema: Any, payload: Any) -> None:
    """Validate data without echoing submitted values in errors or logs.

    A form revision's ``properties`` define its accepted fields. The built-in
    schemas set ``additionalProperties`` to false, so unknown keys fail closed.
    Local references are supported; remote schema retrieval is deliberately
    disabled so collection requests never cause network access.
    """
    if not isinstance(schema, Mapping):
        raise FormSchemaUnavailable("Stored form schema must be an object")
    if not isinstance(payload, Mapping):
        raise FormPayloadInvalid("Collection payload must be an object")

    validator_type = _validator_for_schema(schema)
    try:
        validator = validator_type(schema, format_checker=FormatChecker())
        invalid = next(validator.iter_errors(payload), None)
    except FormSchemaUnavailable:
        raise
    except Exception as exc:
        raise FormSchemaUnavailable("Stored form schema could not be evaluated") from exc

    if invalid is not None:
        raise FormPayloadInvalid("Collection payload does not match its form revision")
