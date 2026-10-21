"""Persist an agent-generated summary through its signed worker identity.

This module is a write adapter only. Summary generation and its source reads
remain with the caller; PostgreSQL rechecks worker identity, exact location,
and the ``ai_summary:draft`` grant before storing the result.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

from services.common.tenant_context import set_worker_tenant_context
from services.common.worker_database import get_worker_credential, get_worker_db

_WORKER_KEY = "agent_summary_draft"
_SUMMARY_TYPE = re.compile(r"^[a-z][a-z0-9_]{0,99}$")
_SOURCE_TABLE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class AgentDraftInvalid(ValueError):
    """Raised when an agent draft request fails local payload validation."""


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AgentDraftInvalid(f"{label} must be a UUID") from exc


def _validate_payload(summary_type: str, summary: Mapping[str, Any]) -> tuple[str, list[str], str]:
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
    return content, source_tables, model_version


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
    }


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
    content, source_tables, model_version = _validate_payload(summary_type, summary)
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
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
