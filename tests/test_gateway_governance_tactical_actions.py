"""Governance tactical item transitions use exact signed tenant action scopes."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import governance_tactical_actions as actions

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
ITEM_ID = str(uuid4())
REQUEST_ID = str(uuid4())
EVENT_ID = str(uuid4())
ACTOR_ID = str(uuid4())


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append(("sql", " ".join(query.split()), params))
        self.description = [
            SimpleNamespace(name=name)
            for name in (
                "event_id", "item_id", "action", "prior_status", "resulting_status",
                "actor_party_id", "created_at",
            )
        ]

    def fetchone(self):
        return (
            EVENT_ID, ITEM_ID, self.connection.action, "open",
            self.connection.resulting_status, ACTOR_ID, "2026-10-18T00:00:00Z",
        )


class _Connection:
    autocommit = False

    def __init__(self, action="start", resulting_status="in_progress"):
        self.action = action
        self.resulting_status = resulting_status
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


def _payload(action="start"):
    payload = {"request_id": REQUEST_ID, "reason": "The assigned steward is beginning the action."}
    if action == "dispose":
        payload.update({
            "disposition_type": "next_action",
            "disposition_summary": "The action is complete and documented.",
        })
    return payload


def test_tactical_start_sets_exact_context_before_function_and_commits(monkeypatch):
    connection = _Connection()
    context = []

    def set_context(conn, **kwargs):
        context.append(kwargs)
        conn.operations.append(("context", kwargs))

    monkeypatch.setattr(actions, "set_operator_tenant_context", set_context)
    result = actions.transition_governance_tactical_item(
        OPERATOR_ID, LOCATION_ID, ITEM_ID, "start", _payload(),
        connection_factory=lambda: connection,
    )

    assert result["event_id"] == EVENT_ID
    assert result["resulting_status"] == "in_progress"
    assert context == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_tactical",
        "action": "start",
    }]
    context_index = next(index for index, item in enumerate(connection.operations) if item[0] == "context")
    function_index = next(
        index for index, item in enumerate(connection.operations)
        if item[0] == "sql" and "transition_governance_tactical_item" in item[1]
    )
    assert context_index < function_index
    assert connection.operations[function_index][2] == (
        LOCATION_ID, ITEM_ID, REQUEST_ID, "start", _payload()["reason"], None, None,
    )
    assert connection.committed and not connection.rolled_back and connection.closed


def test_tactical_disposition_sends_only_validated_fields(monkeypatch):
    connection = _Connection(action="dispose", resulting_status="disposed")
    monkeypatch.setattr(actions, "set_operator_tenant_context", lambda *_args, **_kwargs: None)

    result = actions.transition_governance_tactical_item(
        OPERATOR_ID, LOCATION_ID, ITEM_ID, "dispose", _payload("dispose"),
        connection_factory=lambda: connection,
    )

    assert result["resulting_status"] == "disposed"
    sql = next(item for item in connection.operations if item[0] == "sql" and "transition_governance" in item[1])
    assert sql[2][-2:] == ("next_action", "The action is complete and documented.")
    assert connection.committed and connection.closed


def test_invalid_actions_and_payloads_fail_before_database_open():
    opened = []

    def factory():
        opened.append(True)
        return _Connection()

    with pytest.raises(actions.GovernanceTacticalActionInvalid):
        actions.transition_governance_tactical_item(
            OPERATOR_ID, LOCATION_ID, ITEM_ID, "approve", _payload(), connection_factory=factory
        )
    with pytest.raises(actions.GovernanceTacticalActionInvalid):
        actions.transition_governance_tactical_item(
            OPERATOR_ID, LOCATION_ID, ITEM_ID, "dispose", _payload(), connection_factory=factory
        )
    with pytest.raises(actions.GovernanceTacticalActionInvalid):
        actions.transition_governance_tactical_item(
            OPERATOR_ID, LOCATION_ID, ITEM_ID, "cancel",
            {**_payload(), "extra": "no"}, connection_factory=factory
        )
    assert opened == []


def test_tenant_denial_rolls_back_and_closes(monkeypatch):
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    monkeypatch.setattr(actions, "set_operator_tenant_context", deny)
    with pytest.raises(TenantContextDenied):
        actions.transition_governance_tactical_item(
            OPERATOR_ID, LOCATION_ID, ITEM_ID, "start", _payload(),
            connection_factory=lambda: connection,
        )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_invalid_disposition_and_missing_reason_fail_before_database_open():
    opened = []

    with pytest.raises(actions.GovernanceTacticalActionInvalid):
        actions.transition_governance_tactical_item(
            OPERATOR_ID, LOCATION_ID, ITEM_ID, "dispose",
            {**_payload("dispose"), "disposition_type": "publish"},
            connection_factory=lambda: opened.append(True),
        )
    with pytest.raises(actions.GovernanceTacticalActionInvalid):
        actions.transition_governance_tactical_item(
            OPERATOR_ID, LOCATION_ID, ITEM_ID, "cancel",
            {"request_id": REQUEST_ID, "reason": "  "},
            connection_factory=lambda: opened.append(True),
        )
    assert opened == []
