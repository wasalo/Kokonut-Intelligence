"""Gateway tactical content mutations keep scope and audit in one transaction."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import governance_tactical_mutations as mutations

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
SESSION_ID = str(uuid4())
ITEM_ID = str(uuid4())
REQUEST_ID = str(uuid4())
ROLE_ID = str(uuid4())
PERSON_ID = str(uuid4())
EVENT_ID = str(uuid4())


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        self.connection.operations.append(("sql", normalized, params))
        if "mutate_governance_tactical_content" in normalized:
            self.description = [
                SimpleNamespace(name=name)
                for name in (
                    "event_id", "operation", "session_id", "item_id", "actor_party_id", "created_at"
                )
            ]

    def fetchone(self):
        return EVENT_ID, "create_item", SESSION_ID, ITEM_ID, PERSON_ID, datetime(
            2026, 10, 19, tzinfo=timezone.utc
        )


class _Connection:
    autocommit = False

    def __init__(self):
        self.operations = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _payload(**changes):
    payload = {
        "request_id": REQUEST_ID,
        "reason": "Capture the next action from this location review.",
        "session_id": SESSION_ID,
        "requested_next_action": "Review irrigation repair quotes.",
        "priority": 4,
        "owner_role_id": ROLE_ID,
        "due_at": "2026-10-25T12:00:00Z",
    }
    payload.update(changes)
    return payload


def test_create_item_sets_create_context_and_calls_audited_database_function(monkeypatch):
    connection = _Connection()
    contexts = []

    def set_context(conn, **kwargs):
        contexts.append(kwargs)
        conn.operations.append(("context", kwargs))

    monkeypatch.setattr(mutations, "set_operator_tenant_context", set_context)
    result = mutations.mutate_governance_tactical_content(
        OPERATOR_ID,
        LOCATION_ID,
        "create_item",
        None,
        _payload(),
        connection_factory=lambda: connection,
    )

    assert result["event_id"] == EVENT_ID
    assert result["item_id"] == ITEM_ID
    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_tactical",
        "action": "create",
    }]
    context_index = next(i for i, item in enumerate(connection.operations) if item[0] == "context")
    function_index = next(
        i for i, item in enumerate(connection.operations)
        if item[0] == "sql" and "mutate_governance_tactical_content" in item[1]
    )
    assert context_index < function_index
    params = connection.operations[function_index][2]
    assert params[:4] == (LOCATION_ID, "create_item", None, REQUEST_ID)
    assert json.loads(params[4]) == {
        "session_id": SESSION_ID,
        "requested_next_action": "Review irrigation repair quotes.",
        "priority": 4,
        "owner_role_id": ROLE_ID,
        "due_at": "2026-10-25T12:00:00+00:00",
    }
    assert params[5] == "Capture the next action from this location review."
    assert connection.committed and not connection.rolled_back and connection.closed


@pytest.mark.parametrize(
    ("operation", "target_id", "payload"),
    [
        ("create_item", None, _payload(status="disposed")),
        ("create_item", None, _payload(session_id="not-a-uuid")),
        ("create_item", None, _payload(priority=True)),
        ("create_item", None, _payload(due_at="2026-10-25T12:00:00")),
        ("create_item", None, _payload(extra="unsupported")),
        ("update_item", ITEM_ID, {"request_id": REQUEST_ID, "reason": "Edit", "status": "in_progress"}),
        ("update_item", ITEM_ID, {"request_id": REQUEST_ID, "reason": "Edit"}),
        ("update_session", SESSION_ID, {
            "request_id": REQUEST_ID, "reason": "Edit", "outcome_summary": "Approve",
        }),
        ("update_session", SESSION_ID, {
            "request_id": REQUEST_ID, "reason": "Edit", "session_type": "unsupported",
        }),
    ],
)
def test_invalid_mutation_is_rejected_before_database_open(operation, target_id, payload):
    opened = []
    with pytest.raises(mutations.GovernanceTacticalMutationInvalid):
        mutations.mutate_governance_tactical_content(
            OPERATOR_ID,
            LOCATION_ID,
            operation,
            target_id,
            payload,
            connection_factory=lambda: opened.append(True),
        )
    assert opened == []


@pytest.mark.parametrize(
    ("operation", "target_id", "payload", "expected_action"),
    [
        ("update_item", ITEM_ID, {
            "request_id": REQUEST_ID,
            "reason": "Correct the target date.",
            "due_at": None,
            "priority": 2,
        }, "update"),
        ("update_session", SESSION_ID, {
            "request_id": REQUEST_ID,
            "reason": "Move the planned review.",
            "scheduled_at": "2026-10-22T08:30:00-04:00",
            "title": "Updated review",
        }, "update"),
    ],
)
def test_updates_use_exact_update_context_and_normalize_content(
    monkeypatch, operation, target_id, payload, expected_action
):
    connection = _Connection()
    contexts = []
    monkeypatch.setattr(
        mutations,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append(kwargs),
    )
    mutations.mutate_governance_tactical_content(
        OPERATOR_ID,
        LOCATION_ID,
        operation,
        target_id,
        payload,
        connection_factory=lambda: connection,
    )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_tactical",
        "action": expected_action,
    }]
    call = next(
        item for item in connection.operations
        if item[0] == "sql" and "mutate_governance_tactical_content" in item[1]
    )
    normalized = json.loads(call[2][4])
    if operation == "update_item":
        assert normalized == {"due_at": None, "priority": 2}
    else:
        assert normalized == {
            "scheduled_at": "2026-10-22T08:30:00-04:00",
            "title": "Updated review",
        }
    assert connection.committed and connection.closed


def test_tenant_context_denial_rolls_back_and_closes(monkeypatch):
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    monkeypatch.setattr(mutations, "set_operator_tenant_context", deny)
    with pytest.raises(TenantContextDenied):
        mutations.mutate_governance_tactical_content(
            OPERATOR_ID,
            LOCATION_ID,
            "create_item",
            None,
            _payload(),
            connection_factory=lambda: connection,
        )
    assert connection.rolled_back and connection.closed and not connection.committed
