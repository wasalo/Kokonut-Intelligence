from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from services.gateway.farm_activity_workflow import (
    FarmActivityIntakeInvalid,
    FarmActivityPayloadTooLarge,
    create_farm_activity_draft,
    get_farm_activity_intake,
    list_farm_activity_intake,
)

OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
LOCATION_ID = "11111111-1111-4111-8111-111111111111"
COLLECTION_ID = "22222222-2222-4222-8222-222222222222"
ACTIVITY_ID = "33333333-3333-4333-8333-333333333333"
COLLECTED_AT = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)

PAYLOAD = {
    "activity_type": "weeding",
    "activity_date": "2026-10-10",
    "description": "Removed weeds in the north field.",
    "labor_hours": 2.5,
    "notes": "No worker names included.",
}
SCHEMA = {
    "type": "object",
    "required": ["activity_type", "activity_date"],
    "properties": {
        "activity_type": {"type": "string", "enum": ["weeding"]},
        "activity_date": {"type": "string", "format": "date"},
        "description": {"type": "string"},
        "labor_hours": {"type": "number", "minimum": 0},
        "notes": {"type": "string"},
    },
    "additionalProperties": False,
}


class ReadCursor:
    def __init__(self, rows):
        self.rows = rows
        self.result_rows = []
        self.description = []
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=()):
        self.statements.append((sql, params))
        if sql.lstrip().upper().startswith("SELECT OC.ID"):
            self.result_rows = self.rows
            self.description = [SimpleNamespace(name=name) for name in self.rows[0]] if self.rows else []

    def fetchall(self):
        return [tuple(row.values()) for row in self.result_rows]


class ReadConnection:
    def __init__(self, rows):
        self.cursor_instance = ReadCursor(rows)
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _read_row(**overrides):
    row = {
        "id": UUID(COLLECTION_ID),
        "location_id": UUID(LOCATION_ID),
        "form_id": "farm_activity_v1",
        "form_version": "1.2.0",
        "collection_type": "farm_activity",
        "collected_at": COLLECTED_AT,
        "synced_at": COLLECTED_AT,
        "activity_type": "weeding",
        "activity_date": "2026-10-10",
        "eligible_for_use": True,
        "payload": PAYLOAD,
        "payload_size": 180,
        "photo_count": 0,
    }
    row.update(overrides)
    return row


def test_intake_queue_is_scoped_and_does_not_return_free_text():
    queue_row = _read_row()
    for private_column in ("payload", "payload_size", "photo_count", "collection_type"):
        queue_row.pop(private_column)
    connection = ReadConnection([queue_row])
    rows = list_farm_activity_intake(
        OPERATOR_ID,
        LOCATION_ID,
        connection_factory=lambda: connection,
    )

    assert rows[0]["id"] == COLLECTION_ID
    assert rows[0]["activity_type"] == "weeding"
    assert "payload" not in rows[0]
    query, params = connection.cursor_instance.statements[-1]
    assert "JOIN mobile_form_version AS revision" in query
    assert "revision.status = 'active'" in query
    assert "eligibility.eligible_for_use = TRUE" in query
    assert "NOT EXISTS" in query and "farm_activity" in query
    assert "grant_row.action = 'read'" in query
    assert "payload->>'activity_type'" in query
    assert "description" not in query and "notes" not in query
    assert params == (LOCATION_ID, OPERATOR_ID, 50)
    assert connection.rolled_back and connection.closed


def test_intake_detail_requires_two_location_grants_and_bounds_private_payload():
    connection = ReadConnection([_read_row()])
    result = get_farm_activity_intake(
        OPERATOR_ID,
        COLLECTION_ID,
        LOCATION_ID,
        connection_factory=lambda: connection,
    )
    query = connection.cursor_instance.statements[-1][0]
    assert result["payload"] == PAYLOAD
    assert "JOIN mobile_form_version AS revision" in query
    assert "revision.status = 'active'" in query
    assert "grant_row.action = 'read_detail'" in query
    assert "detail_grant.action = 'read_detail'" in query
    assert "CASE WHEN octet_length(oc.payload::text) <= 524288" in query
    assert connection.rolled_back and connection.closed

    too_large = ReadConnection([_read_row(payload=None, payload_size=524_289)])
    with pytest.raises(FarmActivityPayloadTooLarge):
        get_farm_activity_intake(
            OPERATOR_ID,
            COLLECTION_ID,
            LOCATION_ID,
            connection_factory=lambda: too_large,
        )
    assert too_large.rolled_back and too_large.closed


class WriteCursor:
    def __init__(
        self,
        *,
        intake=None,
        activity=None,
        existing=None,
        participant_link=("active",),
        active_grants=(
            ("farm_activity", "create_draft"),
            ("mobile_collection_review", "read_detail"),
        ),
    ):
        self.intake = intake
        self.activity = activity
        self.existing = existing
        self.participant_link = participant_link
        self.active_grants = set(active_grants)
        self.statements = []
        self.description = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=()):
        self.statements.append((sql, params))
        if "FROM offline_collection AS oc" in sql and "FOR UPDATE OF oc" in sql:
            self.result = self.intake
        elif "FROM mobile_participant_link" in sql and "FOR SHARE" in sql:
            self.result = self.participant_link
        elif "FROM operator_scope_grant" in sql and "FOR SHARE" in sql:
            self.result = ("grant-id",) if (params[1], params[2]) in self.active_grants else None
        elif "INSERT INTO farm_activity (" in sql:
            self.result = self.activity
        elif "FROM farm_activity" in sql and "FOR UPDATE" in sql:
            self.result = self.existing
        else:
            self.result = None

    def fetchone(self):
        return self.result


class WriteConnection:
    def __init__(
        self,
        *,
        intake=None,
        activity=None,
        existing=None,
        participant_link=("active",),
        active_grants=(
            ("farm_activity", "create_draft"),
            ("mobile_collection_review", "read_detail"),
        ),
    ):
        self.cursor_instance = WriteCursor(
            intake=intake,
            activity=activity,
            existing=existing,
            participant_link=participant_link,
            active_grants=active_grants,
        )
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _intake_tuple(payload=PAYLOAD, schema=SCHEMA, participant_link_id=None):
    return (
        COLLECTION_ID,
        LOCATION_ID,
        "farm_activity_v1",
        "1.2.0",
        "farm_activity",
        "synced",
        "active",
        "not_required",
        False,
        payload,
        schema,
        "active",
        "not_required",
        participant_link_id,
    )


def _activity_tuple():
    return (
        ACTIVITY_ID,
        LOCATION_ID,
        "weeding",
        "2026-10-10",
        "draft",
        "field_collector",
        COLLECTION_ID,
    )


def test_draft_promotion_maps_allowlisted_fields_and_records_digest():
    connection = WriteConnection(intake=_intake_tuple(), activity=_activity_tuple())
    result = create_farm_activity_draft(
        OPERATOR_ID,
        COLLECTION_ID,
        LOCATION_ID,
        content_reviewed=True,
        connection_factory=lambda: connection,
    )

    assert result == {
        "id": ACTIVITY_ID,
        "location_id": LOCATION_ID,
        "activity_type": "weeding",
        "activity_date": "2026-10-10",
        "status": "draft",
        "source_system": "field_collector",
        "source_id": COLLECTION_ID,
        "created": True,
    }
    insert_sql, insert_params = next(
        (sql, params)
        for sql, params in connection.cursor_instance.statements
        if "INSERT INTO farm_activity (" in sql
    )
    assert "status, schema_version, source_system" in insert_sql
    assert insert_params[:7] == (
        LOCATION_ID,
        "weeding",
        "2026-10-10",
        "Removed weeds in the north field.",
        2.5,
        "No worker names included.",
        COLLECTION_ID,
    )
    source_raw = json.loads(insert_params[7])
    digest = hashlib.sha256(
        json.dumps(PAYLOAD, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    assert source_raw == {
        "form_id": "farm_activity_v1",
        "form_version": "1.2.0",
        "offline_collection_id": COLLECTION_ID,
        "payload_sha256": digest,
    }
    event_sql, event_params = next(
        (sql, params)
        for sql, params in connection.cursor_instance.statements
        if "INSERT INTO farm_activity_workflow_event" in sql
    )
    assert "draft_created" in event_sql
    assert event_params[:4] == (ACTIVITY_ID, LOCATION_ID, COLLECTION_ID, OPERATOR_ID)
    assert json.loads(event_params[4]) == {"content_reviewed": True, "payload_sha256": digest}
    lock_queries = [
        sql for sql, _params in connection.cursor_instance.statements if "FOR SHARE" in sql
    ]
    assert len(lock_queries) == 2
    assert any("resource = %s" in sql and "action = %s" in sql for sql in lock_queries)
    assert connection.committed and connection.closed and not connection.rolled_back


def test_draft_promotion_requires_content_review_and_rolls_back_invalid_payload():
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("database should not be opened")

    with pytest.raises(FarmActivityIntakeInvalid, match="content review"):
        create_farm_activity_draft(
            OPERATOR_ID,
            COLLECTION_ID,
            LOCATION_ID,
            content_reviewed=False,
            connection_factory=connection_factory,
        )
    assert not opened

    connection = WriteConnection(intake=_intake_tuple(payload={"unexpected": "private"}))
    with pytest.raises(FarmActivityIntakeInvalid, match="immutable form revision"):
        create_farm_activity_draft(
            OPERATOR_ID,
            COLLECTION_ID,
            LOCATION_ID,
            content_reviewed=True,
            connection_factory=lambda: connection,
        )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_draft_promotion_returns_no_row_when_scope_or_eligibility_disappears():
    connection = WriteConnection(intake=None)
    result = create_farm_activity_draft(
        OPERATOR_ID,
        COLLECTION_ID,
        LOCATION_ID,
        content_reviewed=True,
        connection_factory=lambda: connection,
    )
    assert result is None
    assert connection.rolled_back and connection.closed and not connection.committed


def test_draft_promotion_holds_both_grants_and_rejects_revoked_participant_link():
    missing_detail_grant = WriteConnection(
        intake=_intake_tuple(),
        active_grants={("farm_activity", "create_draft")},
    )
    result = create_farm_activity_draft(
        OPERATOR_ID,
        COLLECTION_ID,
        LOCATION_ID,
        content_reviewed=True,
        connection_factory=lambda: missing_detail_grant,
    )
    assert result is None
    assert missing_detail_grant.rolled_back and not missing_detail_grant.committed
    assert not any(
        "INSERT INTO farm_activity (" in sql
        for sql, _params in missing_detail_grant.cursor_instance.statements
    )

    revoked_participant = WriteConnection(
        intake=_intake_tuple(participant_link_id="44444444-4444-4444-8444-444444444444"),
        participant_link=None,
    )
    result = create_farm_activity_draft(
        OPERATOR_ID,
        COLLECTION_ID,
        LOCATION_ID,
        content_reviewed=True,
        connection_factory=lambda: revoked_participant,
    )
    assert result is None
    assert revoked_participant.rolled_back and not revoked_participant.committed
    assert any(
        "mobile_participant_link" in sql and "FOR SHARE" in sql
        for sql, _params in revoked_participant.cursor_instance.statements
    )


def test_draft_promotion_retry_returns_existing_matching_source_without_new_event():
    digest = hashlib.sha256(
        json.dumps(PAYLOAD, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    existing = _activity_tuple() + (digest,)
    connection = WriteConnection(intake=_intake_tuple(), activity=None, existing=existing)
    result = create_farm_activity_draft(
        OPERATOR_ID,
        COLLECTION_ID,
        LOCATION_ID,
        content_reviewed=True,
        connection_factory=lambda: connection,
    )
    assert result["id"] == ACTIVITY_ID
    assert result["created"] is False
    assert not any(
        "INSERT INTO farm_activity_workflow_event" in sql
        for sql, _params in connection.cursor_instance.statements
    )
    assert connection.committed and connection.closed
