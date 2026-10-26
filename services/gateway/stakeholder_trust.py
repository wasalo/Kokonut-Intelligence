"""Location-scoped trust projections derived from approved identity reviews."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_PAGE_SIZE = 50


class StakeholderTrustInvalid(ValueError):
    """A trust projection identifier, limit, or cursor is invalid."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise StakeholderTrustInvalid(f"Invalid {field} identifier") from exc


def _normalize_limit(value: str | int) -> int:
    if isinstance(value, str):
        if not value.isdecimal():
            raise StakeholderTrustInvalid("limit must be an integer between 1 and 50")
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= _MAX_PAGE_SIZE:
        raise StakeholderTrustInvalid("limit must be an integer between 1 and 50")
    return value


def _normalize_cursor_time(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError) as exc:
        raise StakeholderTrustInvalid("Invalid trust evidence cursor timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StakeholderTrustInvalid("Trust evidence cursor timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _mapping(cursor, row) -> dict:
    return dict(zip((column.name for column in (cursor.description or ())), row))


def list_location_identity_trust_evidence(
    operator_id: str,
    location_id: str,
    party_id: str,
    *,
    limit: str | int = 50,
    cursor_reviewed_at: str | datetime | None = None,
    cursor_evidence_id: str | None = None,
    connection_factory: Callable | None = None,
) -> dict:
    """Return only reviewed identity evidence scoped to a location and current consent.

    This is deliberately not a network-wide trust score. Legacy trust evidence,
    participant identifiers, raw feedback, and reviewer identities are not returned.
    """
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    party_id = _normalize_uuid(party_id, "party")
    page_size = _normalize_limit(limit)
    before_reviewed_at = _normalize_cursor_time(cursor_reviewed_at)
    before_evidence_id = (
        _normalize_uuid(cursor_evidence_id, "cursor evidence") if cursor_evidence_id else None
    )
    if (before_reviewed_at is None) != (before_evidence_id is None):
        raise StakeholderTrustInvalid(
            "cursor_reviewed_at and cursor_evidence_id must be provided together"
        )

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        # Signed context acquires row locks to serialize against grant revocation
        # and ownership changes. PostgreSQL forbids those locks in READ ONLY
        # transactions. The SQL projection is declared STABLE and this handler
        # executes only its fixed SELECT after context is established.
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="stakeholder_trust",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_party_identity_trust_evidence(
                           %s::uuid, %s::uuid, %s::integer, %s::timestamptz, %s::uuid
                       )""",
                (location_id, party_id, page_size + 1, before_reviewed_at, before_evidence_id),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]
        has_more = len(rows) > page_size
        items = rows[:page_size]
        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = {
                "reviewed_at": last["reviewed_at"].isoformat(),
                "evidence_id": str(last["evidence_id"]),
            }
        return {
            "location_id": location_id,
            "party_id": party_id,
            "evidence": items,
            "next_cursor": next_cursor,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
