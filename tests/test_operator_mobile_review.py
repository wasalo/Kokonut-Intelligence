from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from services.gateway.operator_mobile_review import (
    MobileCollectionPayloadTooLarge,
    MobileReviewEventInvalid,
    get_mobile_collection,
    list_mobile_collections,
    record_mobile_review_event,
)

OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
LOCATION_ID = "11111111-1111-4111-8111-111111111111"
COLLECTION_ID = "22222222-2222-4222-8222-222222222222"
REVISION_ID = "33333333-3333-4333-8333-333333333333"
COLLECTED_AT = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)


class FakeCursor:
    def __init__(self, rows, event_rows=()):
        self.rows = rows
        self.event_rows = list(event_rows)
        self.result_rows = []
        self.description = None
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=()):
        self.statements.append((sql, params))
        if "FROM mobile_collection_review_event AS event" in sql:
            self.result_rows = self.event_rows
            self.description = [SimpleNamespace(name=name) for name in self.event_rows[0]] if self.event_rows else []
        elif "SELECT oc.id" in sql:
            self.result_rows = self.rows
            self.description = [SimpleNamespace(name=name) for name in self.rows[0]] if self.rows else []

    def fetchall(self):
        return [tuple(row.values()) for row in self.result_rows]


class FakeConnection:
    def __init__(self, rows):
        self.cursor_instance = FakeCursor(rows)
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _row(**overrides):
    row = {
        "id": UUID(COLLECTION_ID),
        "location_id": UUID(LOCATION_ID),
        "form_id": "field_note_v1",
        "form_version": "1.1.0",
        "collection_type": "field_note",
        "collected_at": COLLECTED_AT,
        "synced_at": COLLECTED_AT,
        "form_validation_status": "retired_review",
        "consent_validation_status": "not_required",
        "form_review_required": True,
        "form_revision_id": UUID(REVISION_ID),
        "form_name": "Field Note",
        "form_revision_status": "retired",
        "eligible_for_use": False,
        "eligibility_reason": "review_required",
        "review_state": "pending_review",
    }
    row.update(overrides)
    return row


def test_mobile_collection_list_is_bounded_scoped_and_minimized():
    connection = FakeConnection([_row()])
    rows = list_mobile_collections(
        OPERATOR_ID,
        LOCATION_ID,
        connection_factory=lambda: connection,
    )

    assert rows[0]["id"] == COLLECTION_ID
    assert rows[0]["form_revision_id"] == REVISION_ID
    assert rows[0]["collected_at"] == COLLECTED_AT.isoformat()
    assert "payload" not in rows[0]
    assert "participant_link_id" not in rows[0]
    assert "device_id" not in rows[0]
    query = connection.cursor_instance.statements[-1]
    assert "sync_status = 'synced'" in query[0]
    assert "NOT eligibility.eligible_for_use" in query[0]
    assert "mobile_collection_review" in query[0]
    assert "grant_row.action = 'read'" in query[0]
    assert query[1] == (LOCATION_ID, OPERATOR_ID, 50)
    assert connection.rolled_back and connection.closed
    assert any("SET TRANSACTION READ ONLY" in sql for sql, _params in connection.cursor_instance.statements)


def test_mobile_collection_list_rejects_invalid_bounds_before_connection():
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("database should not be opened")

    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        list_mobile_collections(
            OPERATOR_ID,
            LOCATION_ID,
            101,
            connection_factory=connection_factory,
        )
    assert not opened


def test_mobile_collection_detail_requires_distinct_detail_grant_and_hides_identity():
    connection = FakeConnection(
        [
            _row(
                consent_policy_status="required",
                photo_count=2,
                payload={"observation": "private note"},
                payload_size=32,
            )
        ]
    )

    result = get_mobile_collection(
        OPERATOR_ID,
        COLLECTION_ID,
        LOCATION_ID,
        connection_factory=lambda: connection,
    )

    assert result["payload"] == {"observation": "private note"}
    assert result["photo_count"] == 2
    assert result["consent_policy_status"] == "required"
    assert "participant_link_id" not in result
    assert "device_id" not in result
    assert result["review_events"] == []
    query = connection.cursor_instance.statements[-2]
    assert "grant_row.action = 'read_detail'" in query[0]
    assert "oc.sync_status = 'synced'" in query[0]
    assert "oc.user_id" not in query[0]
    assert "oc.device_id" not in query[0]
    assert "participant_link_id" not in query[0]
    assert query[1] == (COLLECTION_ID, LOCATION_ID, OPERATOR_ID)
    assert connection.rolled_back and connection.closed


def test_mobile_collection_detail_rejects_large_payload_and_returns_no_content():
    large = FakeConnection([_row(payload=None, payload_size=524289)])
    with pytest.raises(MobileCollectionPayloadTooLarge, match="512 KiB"):
        get_mobile_collection(
            OPERATOR_ID,
            COLLECTION_ID,
            LOCATION_ID,
            connection_factory=lambda: large,
        )
    assert large.rolled_back and large.closed

    missing = FakeConnection([])
    assert get_mobile_collection(
        OPERATOR_ID,
        COLLECTION_ID,
        LOCATION_ID,
        connection_factory=lambda: missing,
    ) is None


class FakeWriteCursor:
    def __init__(self, row=None, error=None):
        self.row = row
        self.error = error
        self.description = None
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=()):
        self.statements.append((sql, params))
        if self.error:
            raise self.error
        if "INSERT INTO mobile_collection_review_event" in sql and self.row:
            self.description = [SimpleNamespace(name=name) for name in self.row]

    def fetchone(self):
        return tuple(self.row.values()) if self.row else None


class FakeWriteConnection:
    def __init__(self, row=None, error=None):
        self.cursor_instance = FakeWriteCursor(row, error)
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


def event_body():
    return {
        "decision": "needs_follow_up",
        "reason": "The observation needs an independent semantic review.",
        "evidence": [{"source": "field-review", "basis": "The reviewer recorded an unresolved issue."}],
    }


def test_review_event_is_append_only_scoped_and_does_not_update_collection():
    event = {
        "id": UUID("44444444-4444-4444-8444-444444444444"),
        "collection_id": UUID(COLLECTION_ID),
        "location_id": UUID(LOCATION_ID),
        "actor_operator_id": UUID(OPERATOR_ID),
        "decision": "needs_follow_up",
        "reason": "Needs independent review.",
        "evidence": [{"source": "field-review", "basis": "Open question."}],
        "created_at": COLLECTED_AT,
    }
    connection = FakeWriteConnection(row=event)

    result = record_mobile_review_event(
        OPERATOR_ID,
        COLLECTION_ID,
        LOCATION_ID,
        event_body(),
        connection_factory=lambda: connection,
    )

    assert result["id"] == str(event["id"])
    assert result["actor_operator_id"] == OPERATOR_ID
    assert result["created_at"] == COLLECTED_AT.isoformat()
    assert connection.committed and connection.closed and not connection.rolled_back
    insert = next(
        statement
        for statement in connection.cursor_instance.statements
        if "INSERT INTO mobile_collection_review_event" in statement[0]
    )
    sql, params = insert
    assert "INSERT INTO mobile_collection_review_event" in sql
    assert "grant_row.action = 'review'" in sql
    assert "detail_grant.action = 'read_detail'" in sql
    assert "v_mobile_collection_use_eligibility" in sql
    assert "UPDATE offline_collection" not in sql
    assert "UPDATE mobile_form_version" not in sql
    assert params[0] == "needs_follow_up"
    assert json.loads(params[2]) == event_body()["evidence"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda body: body.update({"status": "verified"}),
        lambda body: body.update({"decision": "published"}),
        lambda body: body.update({"reason": "   "}),
        lambda body: body.update({"evidence": []}),
        lambda body: body["evidence"][0].update({"private_payload": "must not be accepted"}),
    ],
)
def test_review_event_rejects_lifecycle_or_unbounded_fields_before_database(mutate):
    body = event_body()
    mutate(body)
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("database should not be opened")

    with pytest.raises(MobileReviewEventInvalid):
        record_mobile_review_event(
            OPERATOR_ID,
            COLLECTION_ID,
            LOCATION_ID,
            body,
            connection_factory=connection_factory,
        )
    assert not opened


def test_review_event_rolls_back_when_collection_is_not_reviewable():
    connection = FakeWriteConnection(row=None)
    result = record_mobile_review_event(
        OPERATOR_ID,
        COLLECTION_ID,
        LOCATION_ID,
        event_body(),
        connection_factory=lambda: connection,
    )
    assert result is None
    assert connection.rolled_back and connection.closed and not connection.committed
