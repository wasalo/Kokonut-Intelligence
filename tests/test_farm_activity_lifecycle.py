"""Tests for explicit operator-controlled farm activity transitions."""

from datetime import datetime, timezone

import pytest

from services.gateway.farm_activity_lifecycle import (
    FarmActivityTransitionConflict,
    FarmActivityTransitionInvalid,
    transition_farm_activity,
)

OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
LOCATION_ID = "11111111-1111-4111-8111-111111111111"
ACTIVITY_ID = "33333333-3333-4333-8333-333333333333"

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
    def __init__(self, *, current_status, grant=True, event=True):
        self.current_status = current_status
        self.grant = grant
        self.event = event
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
            self.result = (ACTIVITY_ID, LOCATION_ID, self.current_status, "field_collector")
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
