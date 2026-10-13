"""Tests for explicit operator-controlled farm activity transitions."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from services.gateway.farm_activity_lifecycle import (
    FarmActivityDraftEditConflict,
    FarmActivityDraftEditInvalid,
    FarmActivityTransitionConflict,
    FarmActivityTransitionInvalid,
    edit_farm_activity_draft,
    transition_farm_activity,
)

OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
LOCATION_ID = "11111111-1111-4111-8111-111111111111"
ACTIVITY_ID = "33333333-3333-4333-8333-333333333333"
COLLECTION_ID = "44444444-4444-4444-8444-444444444444"

TRANSITIONS = [
    ("submit", "draft", "submitted", "submitted", "submit", None),
    ("verify", "submitted", "verified", "verified", "verify", None),
    ("reject", "submitted", "rejected", "rejected", "reject", "Incorrect date"),
    ("reject", "verified", "rejected", "rejected", "reject", "Needs correction"),
    ("request-rework", "rejected", "draft", "rework_requested", "rework", "Correct the date"),
    ("publish", "verified", "published", "published", "publish", None),
    ("close-exception", "rejected", "rejected", "exception_closed", "close_exception", "Outside retention scope"),
]


class TransitionCursor:
    def __init__(self, *, current_status, grant=True, event=True, eligible=True):
        self.current_status = current_status
        self.grant = grant
        self.event = event
        self.eligible = eligible
        self.result = None
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=()):
        statement = " ".join(sql.split())
        self.statements.append((statement, params))
        lowered = statement.lower()
        if "from farm_activity" in lowered and "for update" in lowered:
            self.result = (
                ACTIVITY_ID,
                LOCATION_ID,
                self.current_status,
                "field_collector",
                self.eligible,
            )
        elif "from operator_scope_grant" in lowered:
            self.result = ("grant-id",) if self.grant else None
        elif lowered.startswith("update farm_activity set status"):
            self.current_status = params[0]
            self.result = None
        elif "from farm_activity_workflow_event" in lowered:
            self.result = (
                "event-id",
                params[2],
                params[3],
                params[4],
                None,
                datetime(2026, 10, 12, tzinfo=timezone.utc),
            ) if self.event else None
        else:
            self.result = None

    def fetchone(self):
        return self.result


class TransitionConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor
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


FORM_SCHEMA = {
    "type": "object",
    "properties": {
        "activity_type": {"type": "string", "enum": ["weeding", "planting"]},
        "activity_date": {"type": "string", "format": "date"},
        "description": {"type": "string"},
        "labor_hours": {"type": "number", "minimum": 0},
        "notes": {"type": "string"},
    },
    "required": ["activity_type", "activity_date"],
    "additionalProperties": False,
}


class DraftEditCursor:
    def __init__(
        self, *, grants=None, activity=None, schema=FORM_SCHEMA, event=True, eligible=True
    ):
        self.grants = grants if grants is not None else [
            ("farm_activity", "edit_draft"),
            ("farm_activity", "read_detail"),
            ("mobile_collection_review", "read_detail"),
        ]
        self.activity = activity if activity is not None else (
            ACTIVITY_ID,
            COLLECTION_ID,
            LOCATION_ID,
            "draft",
            "field_collector",
            "farm_activity_v1",
            "1.2.0",
            "weeding",
            date(2026, 10, 12),
            "Initial description",
            Decimal("1.00"),
            "Initial notes",
            eligible,
        )
        self.schema = schema
        self.event = event
        self.result = None
        self.results = []
        self.statements = []
        self.update_params = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=()):
        statement = " ".join(sql.split())
        self.statements.append((statement, params))
        lowered = statement.lower()
        self.results = []
        if "from farm_activity" in lowered and "for update" in lowered:
            self.result = self.activity
        elif "from operator_scope_grant" in lowered:
            self.results = self.grants
            self.result = None
        elif "from offline_collection" in lowered:
            self.result = (self.schema,)
        elif lowered.startswith("update farm_activity set"):
            self.update_params = params
            self.result = None
        elif "from farm_activity_workflow_event" in lowered:
            self.result = (
                "event-id",
                "draft_edited",
                "draft",
                "draft",
                "Corrected the activity details",
                ["activity_type", "notes"],
                datetime(2026, 10, 13, tzinfo=timezone.utc),
            ) if self.event else None
        else:
            self.result = None

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.results


class DraftEditConnection(TransitionConnection):
    pass


def _run_draft_edit(cursor, *, content_patch=None, reason="Corrected the activity details"):
    connection = DraftEditConnection(cursor)
    result = edit_farm_activity_draft(
        OPERATOR_ID,
        ACTIVITY_ID,
        LOCATION_ID,
        content_patch or {"activity_type": "planting", "notes": "Updated notes"},
        reason,
        connection_factory=lambda: connection,
    )
    return connection, result


def test_draft_edit_validates_exact_revision_locks_all_grants_and_records_event():
    cursor = DraftEditCursor()
    connection, result = _run_draft_edit(cursor)

    assert result == {
        "event_id": "event-id",
        "activity_id": ACTIVITY_ID,
        "location_id": LOCATION_ID,
        "action": "draft_edited",
        "from_status": "draft",
        "to_status": "draft",
        "reason": "Corrected the activity details",
        "changed_fields": ["activity_type", "notes"],
        "created_at": "2026-10-13T00:00:00+00:00",
    }
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True
    assert any(
        "FROM farm_activity" in sql
        and "FOR UPDATE" in sql
        and params == (ACTIVITY_ID, LOCATION_ID)
        for sql, params in cursor.statements
    )
    assert any(
        "FROM operator_scope_grant" in sql
        and "FOR SHARE" in sql
        and params == (OPERATOR_ID, LOCATION_ID)
        for sql, params in cursor.statements
    )
    revision_query = next(
        (sql, params) for sql, params in cursor.statements if "FROM offline_collection" in sql
    )
    assert "collection.form_version = '1.2.0'" in revision_query[0]
    assert "revision.version = '1.2.0'" in revision_query[0]
    assert "FOR SHARE OF collection, revision" in revision_query[0]
    assert revision_query[1] == (COLLECTION_ID, LOCATION_ID)
    assert cursor.update_params == (
        "planting",
        date(2026, 10, 12),
        "Initial description",
        Decimal("1.00"),
        "Updated notes",
        ACTIVITY_ID,
    )
    update_sql = next(sql for sql, _ in cursor.statements if sql.startswith("UPDATE farm_activity SET"))
    assert "source_raw" not in update_sql
    assert "source_id" not in update_sql
    assert any(
        "set_config('kokonut.actor_id'" in sql
        and params == (OPERATOR_ID, "Corrected the activity details")
        for sql, params in cursor.statements
    )


def test_draft_edit_requires_all_three_current_location_grants():
    cursor = DraftEditCursor(grants=[("farm_activity", "edit_draft")])
    connection, result = _run_draft_edit(cursor)

    assert result is None
    assert connection.rolled_back is True
    assert connection.committed is False
    assert cursor.update_params is None


def test_draft_edit_rejects_values_outside_the_immutable_form_revision():
    cursor = DraftEditCursor()
    connection = DraftEditConnection(cursor)

    with pytest.raises(FarmActivityDraftEditInvalid, match="immutable farm activity form revision"):
        edit_farm_activity_draft(
            OPERATOR_ID,
            ACTIVITY_ID,
            LOCATION_ID,
            {"activity_type": "harvesting"},
            "Corrected the activity details",
            connection_factory=lambda: connection,
        )

    assert connection.rolled_back is True
    assert connection.committed is False
    assert cursor.update_params is None


def test_draft_edit_rolls_back_when_append_only_event_is_missing():
    cursor = DraftEditCursor(event=False)
    connection = DraftEditConnection(cursor)

    with pytest.raises(FarmActivityDraftEditConflict, match="evidence was not recorded"):
        edit_farm_activity_draft(
            OPERATOR_ID,
            ACTIVITY_ID,
            LOCATION_ID,
            {"activity_type": "planting"},
            "Corrected the activity details",
            connection_factory=lambda: connection,
        )

    assert cursor.update_params is not None
    assert connection.rolled_back is True
    assert connection.committed is False


def test_draft_edit_rejects_non_draft_rows_without_writing():
    activity = list(DraftEditCursor().activity)
    activity[3] = "submitted"
    cursor = DraftEditCursor(activity=tuple(activity))
    connection = DraftEditConnection(cursor)

    with pytest.raises(FarmActivityDraftEditConflict, match="Only a draft"):
        edit_farm_activity_draft(
            OPERATOR_ID,
            ACTIVITY_ID,
            LOCATION_ID,
            {"activity_type": "planting"},
            "Corrected the activity details",
            connection_factory=lambda: connection,
        )

    assert cursor.update_params is None
    assert connection.rolled_back is True
    assert connection.committed is False


def test_draft_edit_is_blocked_when_source_is_not_currently_eligible():
    cursor = DraftEditCursor(eligible=False)
    connection = DraftEditConnection(cursor)

    with pytest.raises(FarmActivityDraftEditConflict, match="blocks further use"):
        edit_farm_activity_draft(
            OPERATOR_ID,
            ACTIVITY_ID,
            LOCATION_ID,
            {"activity_type": "planting"},
            "Corrected the activity details",
            connection_factory=lambda: connection,
        )

    assert cursor.update_params is None
    assert connection.rolled_back is True
    assert connection.committed is False


@pytest.mark.parametrize(
    ("content_patch", "reason", "message"),
    [
        ({"unknown": "value"}, "reason", "only fields"),
        ({"activity_type": "planting"}, "  ", "reason is required"),
        ({"activity_type": "planting"}, "x" * 2001, "exceeds 2000"),
    ],
)
def test_draft_edit_rejects_malformed_request_before_opening_database(
    content_patch, reason, message
):
    with pytest.raises(FarmActivityDraftEditInvalid, match=message):
        edit_farm_activity_draft(
            OPERATOR_ID,
            ACTIVITY_ID,
            LOCATION_ID,
            content_patch,
            reason,
            connection_factory=lambda: pytest.fail("connection must not open"),
        )


@pytest.mark.parametrize(
    ("action", "from_status", "to_status", "event_action", "grant_action", "reason"),
    TRANSITIONS,
)
def test_transition_records_the_authorized_human_decision(
    action, from_status, to_status, event_action, grant_action, reason
):
    cursor = TransitionCursor(current_status=from_status)
    connection = TransitionConnection(cursor)

    result = transition_farm_activity(
        OPERATOR_ID,
        ACTIVITY_ID,
        LOCATION_ID,
        action,
        reason,
        connection_factory=lambda: connection,
    )

    assert result["action"] == event_action
    assert result["from_status"] == from_status
    assert result["to_status"] == to_status
    assert result["event_id"] == "event-id"
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True
    assert any(
        "FOR UPDATE" in sql and params == (ACTIVITY_ID, LOCATION_ID)
        for sql, params in cursor.statements
    )
    assert any(
        "FOR SHARE" in sql and params == (OPERATOR_ID, grant_action, LOCATION_ID)
        for sql, params in cursor.statements
    )
    assert any(
        "set_config('kokonut.workflow_action'" in sql
        and params == (OPERATOR_ID, event_action, reason or "")
        for sql, params in cursor.statements
    )


def test_transition_rejects_missing_reason_before_opening_database_connection():
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("validation should happen before opening the database")

    with pytest.raises(FarmActivityTransitionInvalid, match="reason is required"):
        transition_farm_activity(
            OPERATOR_ID,
            ACTIVITY_ID,
            LOCATION_ID,
            "reject",
            "  ",
            connection_factory=connection_factory,
        )
    assert opened is False


def test_transition_rejects_long_reason_before_opening_database_connection():
    with pytest.raises(FarmActivityTransitionInvalid, match="exceeds 2000"):
        transition_farm_activity(
            OPERATOR_ID,
            ACTIVITY_ID,
            LOCATION_ID,
            "submit",
            "x" * 2001,
            connection_factory=lambda: pytest.fail("connection must not open"),
        )


def test_transition_conflicts_when_activity_is_not_in_expected_state():
    cursor = TransitionCursor(current_status="verified")
    connection = TransitionConnection(cursor)

    with pytest.raises(FarmActivityTransitionConflict, match="not in a state"):
        transition_farm_activity(
            OPERATOR_ID,
            ACTIVITY_ID,
            LOCATION_ID,
            "submit",
            connection_factory=lambda: connection,
        )

    assert connection.rolled_back is True
    assert connection.committed is False
    assert not any(sql.startswith("UPDATE farm_activity SET status") for sql, _ in cursor.statements)


@pytest.mark.parametrize(
    ("action", "status"),
    [("submit", "draft"), ("verify", "submitted"), ("request-rework", "rejected"), ("publish", "verified")],
)
def test_productive_transition_is_blocked_when_source_is_not_currently_eligible(action, status):
    cursor = TransitionCursor(current_status=status, eligible=False)
    connection = TransitionConnection(cursor)

    with pytest.raises(FarmActivityTransitionConflict, match="blocks further use"):
        transition_farm_activity(
            OPERATOR_ID,
            ACTIVITY_ID,
            LOCATION_ID,
            action,
            "Review the source evidence",
            connection_factory=lambda: connection,
        )

    assert connection.rolled_back is True
    assert connection.committed is False
    assert not any(sql.startswith("UPDATE farm_activity SET status") for sql, _ in cursor.statements)


@pytest.mark.parametrize(
    ("action", "status"),
    [("reject", "submitted"), ("close-exception", "rejected")],
)
def test_disposition_transition_remains_available_when_source_is_ineligible(action, status):
    cursor = TransitionCursor(current_status=status, eligible=False)
    connection = TransitionConnection(cursor)

    result = transition_farm_activity(
        OPERATOR_ID,
        ACTIVITY_ID,
        LOCATION_ID,
        action,
        "Source is no longer eligible for use",
        connection_factory=lambda: connection,
    )

    assert result["action"] in {"rejected", "exception_closed"}
    assert connection.committed is True
    assert connection.rolled_back is False


def test_transition_returns_not_found_when_action_grant_is_missing():
    cursor = TransitionCursor(current_status="draft", grant=False)
    connection = TransitionConnection(cursor)

    result = transition_farm_activity(
        OPERATOR_ID,
        ACTIVITY_ID,
        LOCATION_ID,
        "submit",
        connection_factory=lambda: connection,
    )

    assert result is None
    assert connection.rolled_back is True
    assert connection.committed is False
    assert not any(sql.startswith("UPDATE farm_activity SET status") for sql, _ in cursor.statements)


def test_transition_rolls_back_when_database_did_not_record_event():
    cursor = TransitionCursor(current_status="draft", event=False)
    connection = TransitionConnection(cursor)

    with pytest.raises(FarmActivityTransitionConflict, match="evidence was not recorded"):
        transition_farm_activity(
            OPERATOR_ID,
            ACTIVITY_ID,
            LOCATION_ID,
            "submit",
            connection_factory=lambda: connection,
        )

    assert connection.rolled_back is True
    assert connection.committed is False


def test_transition_rejects_unknown_action_before_opening_connection():
    with pytest.raises(FarmActivityTransitionInvalid, match="Unsupported"):
        transition_farm_activity(
            OPERATOR_ID,
            ACTIVITY_ID,
            LOCATION_ID,
            "archive",
            connection_factory=lambda: pytest.fail("connection must not open"),
        )


def test_transition_rejects_invalid_identifiers_before_opening_connection():
    with pytest.raises(ValueError, match="identifier"):
        transition_farm_activity(
            OPERATOR_ID,
            "not-a-uuid",
            LOCATION_ID,
            "submit",
            connection_factory=lambda: pytest.fail("connection must not open"),
        )
