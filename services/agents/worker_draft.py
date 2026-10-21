"""Persist an agent-generated summary through its signed worker identity.

This module is a write adapter only. Summary generation and its source reads
remain with the caller; PostgreSQL rechecks worker identity, exact location,
and the ``ai_summary:draft`` grant before storing the result.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

from services.common.tenant_context import set_worker_tenant_context
from services.common.worker_database import get_worker_credential, get_worker_db

_WORKER_KEY = "agent_summary_draft"
_SUMMARY_TYPE = re.compile(r"^[a-z][a-z0-9_]{0,99}$")
_SOURCE_TABLE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_SOURCE_REFERENCE_TABLES = frozenset(
    {
        "harvest_event",
        "sales_event",
        "crop_cycle",
        "sensor_reading",
        "expense_event",
        "noi_snapshot",
        "soil_carbon_measurement",
        "species_observation",
        "remote_sensing_observation",
        "weather_observation",
        "crop",
        "expense_category",
        "capital_efficiency_scenario",
        "regenerative_efficiency_observation",
        "governance_throughput_observation",
        "capital_provider_utility_scenario",
        "bio_factory_batch",
        "bio_input_provenance",
        "bio_recipe_library",
        "bio_factory_quality_test",
        "regenerative_outcome_summary",
        "community_governance_mechanism",
        "replication_readiness_assessment",
        "adaptive_stewardship_review",
        "time_liberation_observation",
        "capital_alignment_assessment",
        "governance_inclusion_observation",
        "land_stewardship_commitment",
        "gnh_alignment_assessment",
        "cultural_preservation_plan",
        "renewable_energy_plan",
        "vulnerable_group_access_plan",
        "foundational_wellbeing_observation",
        "financial_sustainability_plan",
        "risk_mitigation_register",
        "scaling_roadmap_milestone",
        "farm_launch_unit_economics",
        "adoption_barrier_assessment",
        "perpetual_value_stress_test",
        "cultural_context_record",
        "wellbeing_metric_observation",
        "participatory_action_record",
        "stakeholder_feedback",
    }
)


class AgentDraftInvalid(ValueError):
    """Raised when an agent draft request fails local payload validation."""


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AgentDraftInvalid(f"{label} must be a UUID") from exc


def _validate_source_references(
    value: Any, source_tables: list[str]
) -> tuple[dict[str, dict[str, Any]], str]:
    if value is None:
        value = {}
    if not isinstance(value, Mapping) or len(value) > 10:
        raise AgentDraftInvalid("source_references must be an object with at most 10 source tables")
    normalized: dict[str, dict[str, Any]] = {}
    for table, entry in value.items():
        if (
            not isinstance(table, str)
            or not _SOURCE_TABLE.fullmatch(table)
            or table not in _SOURCE_REFERENCE_TABLES
            or table not in source_tables
            or not isinstance(entry, Mapping)
            or set(entry) != {"record_ids", "row_count", "truncated"}
        ):
            raise AgentDraftInvalid("source_references must match declared supported source tables")
        record_ids = entry["record_ids"]
        row_count = entry["row_count"]
        truncated = entry["truncated"]
        if not isinstance(record_ids, list) or len(record_ids) > 50:
            raise AgentDraftInvalid("source reference record_ids must contain at most 50 UUIDs")
        try:
            normalized_ids = [_uuid(record_id, "source reference record_id") for record_id in record_ids]
        except AgentDraftInvalid as exc:
            raise AgentDraftInvalid("source reference record_ids must contain UUIDs") from exc
        if len(set(normalized_ids)) != len(normalized_ids):
            raise AgentDraftInvalid("source reference record_ids must be unique")
        if (
            not isinstance(row_count, int)
            or isinstance(row_count, bool)
            or row_count < len(normalized_ids)
            or not isinstance(truncated, bool)
            or truncated != (row_count > len(normalized_ids))
        ):
            raise AgentDraftInvalid("source reference counts and truncation flag are inconsistent")
        normalized[table] = {
            "record_ids": normalized_ids,
            "row_count": row_count,
            "truncated": truncated,
        }
    try:
        encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise AgentDraftInvalid("source_references must contain JSON-compatible values") from exc
    if len(encoded.encode("utf-8")) > 64000:
        raise AgentDraftInvalid("source_references exceeds the 64000-byte limit")
    return normalized, encoded


def _validate_payload(
    summary_type: str, summary: Mapping[str, Any]
) -> tuple[str, list[str], str, dict[str, dict[str, Any]], str]:
    if not isinstance(summary_type, str) or not _SUMMARY_TYPE.fullmatch(summary_type):
        raise AgentDraftInvalid("summary_type is invalid")
    if not isinstance(summary, Mapping):
        raise AgentDraftInvalid("summary must be an object")
    content = summary.get("content") or summary.get("synthesis")
    if not isinstance(content, str) or not content.strip() or len(content) > 20000:
        raise AgentDraftInvalid("summary content must contain 1 to 20000 characters")
    source_tables = summary.get("source_tables")
    if (
        not isinstance(source_tables, list)
        or not 1 <= len(source_tables) <= 20
        or any(not isinstance(table, str) or not _SOURCE_TABLE.fullmatch(table) for table in source_tables)
        or len(set(source_tables)) != len(source_tables)
    ):
        raise AgentDraftInvalid("source_tables must contain 1 to 20 unique table identifiers")
    model_version = summary.get("model_version", "agent-worker-v1")
    if (
        not isinstance(model_version, str)
        or not model_version.strip()
        or len(model_version) > 100
    ):
        raise AgentDraftInvalid("model_version must contain 1 to 100 characters")
    source_references, source_references_json = _validate_source_references(
        summary.get("source_references"), source_tables
    )
    return content, source_tables, model_version, source_references, source_references_json


def _set_context(connection: Any, *, credential: str, location_id: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL statement_timeout = '15s'")
        cursor.execute("SET LOCAL lock_timeout = '3s'")
    set_worker_tenant_context(
        connection,
        credential=credential,
        location_id=location_id,
        resource="ai_summary",
        action="draft",
    )


def _read_row(row: tuple[Any, ...] | None, *, replayed: bool) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "summary_id": str(row[0]),
        "content": row[1],
        "source_tables": list(row[2] or []),
        "model_version": row[3],
        "created_at": row[4],
        "resulting_status": row[5],
        "replayed": replayed,
        "source_references": {},
    }


def _read_source_references(
    connection: Any, *, location_id: str, summary_id: str, request_id: str
) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT kokonut_security.get_location_ai_summary_worker_source_references(
                       %s::uuid, %s::uuid, %s::uuid
                   )""",
            (location_id, summary_id, request_id),
        )
        row = cursor.fetchone()
    return row[0] if row and isinstance(row[0], dict) else {}


def get_worker_ai_summary_draft(
    location_id: str,
    summary_type: str,
    request_id: str,
    *,
    connection_factory: Callable[[], Any] | None = None,
) -> dict[str, Any] | None:
    """Return a prior exact worker request before an agent recomputes output."""
    location_id = _uuid(location_id, "location_id")
    request_id = _uuid(request_id, "request_id")
    if not isinstance(summary_type, str) or not _SUMMARY_TYPE.fullmatch(summary_type):
        raise AgentDraftInvalid("summary_type is invalid")
    credential = get_worker_credential(_WORKER_KEY)
    connection = (connection_factory or (lambda: get_worker_db(_WORKER_KEY)))()
    try:
        _set_context(connection, credential=credential, location_id=location_id)
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.get_location_ai_summary_worker_draft_request(
                           %s::uuid, %s::text, %s::uuid
                       )""",
                (location_id, summary_type, request_id),
            )
            result = _read_row(cursor.fetchone(), replayed=True)
        if result is not None:
            result["source_references"] = _read_source_references(
                connection,
                location_id=location_id,
                summary_id=result["summary_id"],
                request_id=request_id,
            )
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_worker_ai_summary_draft(
    location_id: str,
    summary_type: str,
    request_id: str,
    summary: Mapping[str, Any],
    *,
    connection_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Create or replay one draft under the exact signed worker scope.

    Call :func:`get_worker_ai_summary_draft` before expensive generation when
    possible. This write function remains idempotent if concurrent workers race
    after that lookup.
    """
    location_id = _uuid(location_id, "location_id")
    request_id = _uuid(request_id, "request_id")
    (
        content,
        source_tables,
        model_version,
        source_references,
        source_references_json,
    ) = _validate_payload(summary_type, summary)
    credential = get_worker_credential(_WORKER_KEY)
    connection = (connection_factory or (lambda: get_worker_db(_WORKER_KEY)))()
    try:
        _set_context(connection, credential=credential, location_id=location_id)
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.create_location_ai_summary_worker_draft(
                           %s::uuid, %s::text, %s::text, %s::text[], %s::text, %s::uuid
                       )""",
                (location_id, summary_type, content, source_tables, model_version, request_id),
            )
            row = cursor.fetchone()
        result = _read_row(row[:6], replayed=bool(row[6])) if row is not None else None
        if result is None:
            raise RuntimeError("AI summary worker draft function returned no result")
        if source_references:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT kokonut_security.set_location_ai_summary_source_references(
                               %s::uuid, %s::uuid, %s::uuid, %s::jsonb
                           )""",
                    (
                        location_id,
                        result["summary_id"],
                        request_id,
                        source_references_json,
                    ),
                )
                cursor.fetchone()
        result["source_references"] = _read_source_references(
            connection,
            location_id=location_id,
            summary_id=result["summary_id"],
            request_id=request_id,
        )
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
