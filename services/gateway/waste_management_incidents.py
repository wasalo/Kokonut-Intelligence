"""Tenant-scoped pollution incident capture, review, and resolution."""

from __future__ import annotations

import json
import re
from datetime import date
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_INCIDENT_TYPES = {
    "chemical_spill", "runoff", "air_emission", "water_contamination",
    "waste_dumping", "other",
}
_INCIDENT_SEVERITIES = {"low", "medium", "high", "critical"}
_CONTROL_CHARACTER = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class PollutionIncidentInvalid(ValueError):
    """An incident capture or resolution request is invalid or outside its bounds."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _identifier(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise PollutionIncidentInvalid(f"Invalid {field} identifier") from exc


def _text(value, field: str, maximum: int, *, required: bool = False):
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise PollutionIncidentInvalid(f"Invalid {field}")
    normalized = value.strip()
    if (
        (required and not normalized)
        or len(normalized) > maximum
        or _CONTROL_CHARACTER.search(value)
    ):
        raise PollutionIncidentInvalid(f"Invalid {field}")
    return normalized or None


def _date_value(value, field: str) -> date:
    if not isinstance(value, str):
        raise PollutionIncidentInvalid(f"{field} must use YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise PollutionIncidentInvalid(f"{field} must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value or parsed > date.today():
        raise PollutionIncidentInvalid(f"{field} must be today or earlier")
    return parsed


def _normalize_capture(payload: dict) -> tuple:
    if not isinstance(payload, dict):
        raise PollutionIncidentInvalid("Incident body must be an object")
    allowed = {
        "request_id", "incident_date", "incident_type", "severity",
        "description", "affected_area", "reported_by", "notes",
    }
    if set(payload) != allowed:
        raise PollutionIncidentInvalid("Incident fields do not match the supported contract")

    request_id = _identifier(payload["request_id"], "request")
    incident_date = _date_value(payload["incident_date"], "Incident date")
    source_type = _text(payload["incident_type"], "incident type", 100, required=True)
    type_key = re.sub(r"[\s-]+", "_", source_type.lower())
    aliases = {"air_pollution": "air_emission"}
    incident_type = aliases.get(type_key, type_key)
    if incident_type not in _INCIDENT_TYPES:
        incident_type = "other"
    original_type = source_type if type_key != incident_type else None
    severity = payload["severity"]
    if not isinstance(severity, str) or severity not in _INCIDENT_SEVERITIES:
        raise PollutionIncidentInvalid("Unsupported incident severity")
    description = _text(payload["description"], "description", 2500, required=True)
    affected_area = _text(payload["affected_area"], "affected area", 200)
    reported_by = _text(payload["reported_by"], "reported by", 200)
    notes = _text(payload["notes"], "notes", 1000)
    return (
        request_id, incident_date, incident_type, original_type, severity,
        description, affected_area, reported_by, notes,
    )


def create_location_pollution_incident(
    operator_id: str,
    location_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create an open incident under the exact location waste-create grant."""
    operator_id = _identifier(operator_id, "operator")
    location_id = _identifier(location_id, "location")
    normalized = _normalize_capture(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="waste_management",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.create_location_pollution_incident("
                "%s::uuid, %s::uuid, %s::date, %s::text, %s::text, "
                "%s::text, %s::text, %s::text, %s::text, %s::text)",
                (location_id, *normalized),
            )
            row = cursor.fetchone()
            result = row[0] if row else None
            if isinstance(result, str):
                result = json.loads(result)
            if (
                not isinstance(result, dict)
                or result.get("location_id") != location_id
                or not isinstance(result.get("incident_id"), str)
                or result.get("status") != "open"
                or not isinstance(result.get("replayed"), bool)
            ):
                raise RuntimeError("Incident capture returned an invalid result")
            connection.commit()
            return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def list_location_pollution_incidents(
    operator_id: str,
    location_id: str,
    *,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return a bounded open-incident review queue for one granted location."""
    operator_id = _identifier(operator_id, "operator")
    location_id = _identifier(location_id, "location")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0 or offset > 1_000_000:
        raise PollutionIncidentInvalid("Incident queue offset is outside its bounds")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="waste_management",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.list_location_pollution_incident_review_queue("
                "%s::uuid, %s::integer)",
                (location_id, offset),
            )
            row = cursor.fetchone()
            result = row[0] if row else None
            if isinstance(result, str):
                result = json.loads(result)
            expected = {"location_id", "offset", "incidents", "has_more"}
            if (
                not isinstance(result, dict)
                or set(result) != expected
                or result.get("location_id") != location_id
                or result.get("offset") != offset
                or not isinstance(result.get("incidents"), list)
                or len(result["incidents"]) > 100
                or not isinstance(result.get("has_more"), bool)
            ):
                raise RuntimeError("Incident review queue returned an invalid result")
            expected_incident = {
                "incident_id", "incident_date", "incident_type", "severity",
                "description", "affected_area", "status",
            }
            for incident in result["incidents"]:
                if (
                    not isinstance(incident, dict)
                    or set(incident) != expected_incident
                    or not isinstance(incident.get("incident_id"), str)
                    or not isinstance(incident.get("incident_date"), str)
                    or not isinstance(incident.get("incident_type"), str)
                    or not isinstance(incident.get("severity"), str)
                    or incident.get("severity") not in _INCIDENT_SEVERITIES
                    or not isinstance(incident.get("description"), str)
                    or not isinstance(incident.get("status"), str)
                    or incident.get("status") not in {
                        "open", "investigating", "remediation",
                    }
                    or incident.get("affected_area") is not None
                    and not isinstance(incident.get("affected_area"), str)
                ):
                    raise RuntimeError("Incident review queue returned an invalid incident")
        return result
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def _normalize_resolution(payload: dict) -> tuple:
    if not isinstance(payload, dict):
        raise PollutionIncidentInvalid("Resolution body must be an object")
    if set(payload) != {"request_id", "resolution_date", "remedial_action"}:
        raise PollutionIncidentInvalid("Resolution fields do not match the supported contract")
    return (
        _identifier(payload["request_id"], "request"),
        _date_value(payload["resolution_date"], "Resolution date"),
        _text(payload["remedial_action"], "remedial action", 2000, required=True),
    )


def resolve_location_pollution_incident(
    operator_id: str,
    location_id: str,
    incident_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Resolve one unresolved incident under the exact location review grant."""
    operator_id = _identifier(operator_id, "operator")
    location_id = _identifier(location_id, "location")
    incident_id = _identifier(incident_id, "incident")
    request_id, resolution_date, remedial_action = _normalize_resolution(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="waste_management",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.resolve_location_pollution_incident("
                "%s::uuid, %s::uuid, %s::uuid, %s::date, %s::text)",
                (location_id, incident_id, request_id, resolution_date, remedial_action),
            )
            row = cursor.fetchone()
            result = row[0] if row else None
            if isinstance(result, str):
                result = json.loads(result)
            if (
                not isinstance(result, dict)
                or result.get("location_id") != location_id
                or result.get("incident_id") != incident_id
                or result.get("status") != "resolved"
                or not isinstance(result.get("replayed"), bool)
            ):
                raise RuntimeError("Incident resolution returned an invalid result")
            connection.commit()
            return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
