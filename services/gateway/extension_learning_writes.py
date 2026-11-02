"""Location-scoped Gateway mutations for extension-learning networks.

The location-scoped, identity-minimized operations in this module are peer
network creation and updates to an existing progress row. Global catalog
management and learner-facing operations that accept or expose participant
identities remain on their existing paths until their ownership and consent
contracts are designed.

The forward migration contract for creation is:

``kokonut_security.create_extension_peer_network(
    UUID location_id, UUID request_id, TEXT network_name, TEXT description,
    TEXT network_type, INTEGER max_members, TEXT meeting_cadence,
    TEXT language, JSONB metadata
)``

The function returns exactly one row containing ``peer_network_id UUID``,
``location_id UUID``, ``network_name TEXT``, ``network_type TEXT``,
``status TEXT``, ``created_at TIMESTAMPTZ``, ``request_id UUID``, and
``created BOOLEAN``. It must validate the signed operator context and the
``extension_learning:create_peer_network`` grant, bind the inserted network to
the requested location, serialize duplicate request IDs, and return the
original receipt for an exact retry. Reusing a request ID with different
content must fail without changing the original network.

The progress update contract is
``kokonut_security.update_extension_learning_progress(UUID location_id,
UUID progress_id, UUID request_id, TEXT status, NUMERIC score, NUMERIC
progress_pct, INTEGER time_spent_min_delta, JSONB metadata_patch)``. It returns
the exact fields ``progress_id UUID, location_id UUID, module_id UUID,
progress_pct NUMERIC, score NUMERIC NULL, time_spent_min INTEGER, status TEXT,
completed_at TIMESTAMPTZ NULL, updated_at TIMESTAMPTZ, request_id UUID``. The
function must verify the signed
``extension_learning:update_progress`` context, match the row to the requested
location, preserve the legacy metadata-merge and completion-timestamp
semantics, and atomically store an idempotent receipt. It must not return
``farmer_name`` or other participant details. The database function accepts
the established ``not_started``, ``in_progress``, ``completed``, ``failed``,
and ``expired`` status values; it adds no certification lifecycle.
"""

from __future__ import annotations

import json
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_NETWORK_TYPES = frozenset(
    {
        "learning_group",
        "mentorship",
        "community_of_practice",
        "farmer_field_school",
        "cooperative",
        "other",
    }
)
_MAX_METADATA_BYTES = 8 * 1024


def _reject_nul(value: object) -> None:
    if isinstance(value, str):
        if "\x00" in value:
            raise ExtensionLearningWriteInvalid("Text values cannot contain null characters")
    elif isinstance(value, dict):
        for key, item in value.items():
            _reject_nul(key)
            _reject_nul(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_nul(item)


class ExtensionLearningWriteInvalid(ValueError):
    """The requested extension-learning mutation is invalid."""


class ExtensionLearningWriteConflict(RuntimeError):
    """The request conflicts with an existing network or idempotency receipt."""


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ExtensionLearningWriteInvalid(f"Invalid {label} identifier") from exc


def _text(value: object, label: str, maximum: int, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or "\x00" in value:
        raise ExtensionLearningWriteInvalid(f"{label} must be text")
    normalized = value.strip()
    if not normalized and nullable:
        return None
    if not normalized or len(normalized) > maximum:
        raise ExtensionLearningWriteInvalid(
            f"{label} must contain 1 to {maximum} characters"
        )
    return normalized


def _metadata(value: object) -> dict:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ExtensionLearningWriteInvalid("metadata must be an object")
    _reject_nul(value)
    try:
        encoded = json.dumps(value, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ExtensionLearningWriteInvalid("metadata must contain JSON values") from exc
    if len(encoded.encode("utf-8")) > _MAX_METADATA_BYTES:
        raise ExtensionLearningWriteInvalid("metadata exceeds 8 KiB")
    return value


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _one_row(cursor) -> dict:
    row = cursor.fetchone()
    if row is None:
        raise ExtensionLearningWriteConflict("Extension operation returned no receipt")
    return dict(zip((column[0] for column in cursor.description), row))


def create_location_extension_peer_network(
    operator_id: str,
    location_id: str,
    request_id: str,
    *,
    network_name: str,
    network_type: str,
    description: str | None = None,
    max_members: int | None = None,
    meeting_cadence: str | None = None,
    language: str = "en",
    metadata: object = None,
    connection_factory: Callable | None = None,
) -> dict:
    """Create a peer network bound to one authorized location.

    The request ID and original result are owned by the database operation so
    a client retry cannot create a duplicate group after a timeout. This
    helper never commits on behalf of another caller; its connection is
    private to the one operation.
    """
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    request_id = _uuid(request_id, "request")
    network_name = _text(network_name, "network_name", 255)
    if not isinstance(network_type, str) or network_type not in _NETWORK_TYPES:
        raise ExtensionLearningWriteInvalid("network_type is not supported")
    description = _text(description, "description", 10_000, nullable=True)
    if max_members is not None and (
        isinstance(max_members, bool)
        or not isinstance(max_members, int)
        or max_members < 1
    ):
        raise ExtensionLearningWriteInvalid("max_members must be a positive integer or null")
    meeting_cadence = _text(meeting_cadence, "meeting_cadence", 100, nullable=True)
    language = _text(language, "language", 50)
    metadata = _metadata(metadata)

    connection = (connection_factory or _connection_factory())()
    committed = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="extension_learning",
            action="create_peer_network",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.create_extension_peer_network(
                           %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s::jsonb
                       )""",
                (
                    location_id,
                    request_id,
                    network_name,
                    description,
                    network_type,
                    max_members,
                    meeting_cadence,
                    language,
                    json.dumps(metadata, separators=(",", ":"), allow_nan=False),
                ),
            )
            result = _one_row(cursor)
        connection.commit()
        committed = True
        return result
    finally:
        if not committed:
            connection.rollback()
        connection.close()


def update_location_extension_learning_progress(
    operator_id: str,
    location_id: str,
    progress_id: str,
    request_id: str,
    *,
    status: str | None = None,
    score: float | None = None,
    progress_pct: float | None = None,
    time_spent_min_delta: int | None = None,
    metadata_patch: object = None,
    connection_factory: Callable | None = None,
) -> dict:
    """Update one existing participant progress row within an authorized farm.

    Participant identity is resolved by the database function but never
    accepted from the request or returned to the operator. Status values match
    the source table's established set; this layer does not invent a new
    competency or certification lifecycle.
    """
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    progress_id = _uuid(progress_id, "progress")
    request_id = _uuid(request_id, "request")
    allowed_statuses = {
        "not_started", "in_progress", "completed", "failed", "expired"
    }
    if status is not None and (
        not isinstance(status, str) or status not in allowed_statuses
    ):
        raise ExtensionLearningWriteInvalid("progress status is not supported")
    for field, value in (("score", score), ("progress_pct", progress_pct)):
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ExtensionLearningWriteInvalid(f"{field} must be numeric")
        if not 0 <= value <= 100:
            raise ExtensionLearningWriteInvalid(f"{field} must be between 0 and 100")
    if time_spent_min_delta is not None and (
        isinstance(time_spent_min_delta, bool)
        or not isinstance(time_spent_min_delta, int)
        or not 1 <= time_spent_min_delta <= 24 * 60
    ):
        raise ExtensionLearningWriteInvalid(
            "time_spent_min_delta must be an integer between 1 and 1440"
        )
    if metadata_patch is None:
        metadata_patch = {}
    metadata_patch = _metadata(metadata_patch)
    if (
        status is None
        and score is None
        and progress_pct is None
        and time_spent_min_delta is None
        and not metadata_patch
    ):
        raise ExtensionLearningWriteInvalid("at least one progress field must change")

    connection = (connection_factory or _connection_factory())()
    committed = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="extension_learning",
            action="update_progress",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.update_extension_learning_progress(
                           %s::uuid, %s::uuid, %s::uuid, %s,
                           %s::numeric, %s::numeric, %s::integer, %s::jsonb
                       )""",
                (
                    location_id,
                    progress_id,
                    request_id,
                    status,
                    score,
                    progress_pct,
                    time_spent_min_delta,
                    json.dumps(metadata_patch, separators=(",", ":"), allow_nan=False),
                ),
            )
            result = _one_row(cursor)
        connection.commit()
        committed = True
        return result
    finally:
        if not committed:
            connection.rollback()
        connection.close()
