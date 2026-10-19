"""Governance circle and role lifecycle mutations stay bounded and attributed."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import governance_definition_actions as actions

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
DEFINITION_ID = str(uuid4())
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
                "event_id", "entity_type", "entity_id", "action", "prior_status",
                "resulting_status", "actor_party_id", "created_at",
            )
        ]

    def fetchone(self):
        return (
            EVENT_ID, self.connection.entity_type, DEFINITION_ID, self.connection.action,
            self.connection.prior_status, self.connection.resulting_status,
            ACTOR_ID, "2026-10-18T00:00:00Z",
        )


class _Connection:
    autocommit = False

    def __init__(self, entity_type="role", action="submit", prior_status="draft", resulting_status="submitted"):
        self.entity_type = entity_type
        self.action = action
        self.prior_status = prior_status
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


def _payload():
    return {"request_id": REQUEST_ID, "reason": "The governance record is ready for review."}


def test_definition_transition_sets_exact_context_before_function_and_commits(monkeypatch):
    connection = _Connection(action="approve", prior_status="submitted", resulting_status="approved")
    contexts = []

    def set_context(conn, **kwargs):
        contexts.append(kwargs)
        conn.operations.append(("context", kwargs))

    monkeypatch.setattr(actions, "set_operator_tenant_context", set_context)
    result = actions.transition_governance_definition(
        OPERATOR_ID, LOCATION_ID, "role", DEFINITION_ID, "approve", _payload(),
        connection_factory=lambda: connection,
    )

    assert result["event_id"] == EVENT_ID
    assert result["resulting_status"] == "approved"
    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_roles",
        "action": "approve",
    }]
    context_index = next(index for index, item in enumerate(connection.operations) if item[0] == "context")
    function_index = next(
        index for index, item in enumerate(connection.operations)
        if item[0] == "sql" and "transition_governance_definition" in item[1]
    )
    assert context_index < function_index
    assert connection.operations[function_index][2] == (
        LOCATION_ID, "role", DEFINITION_ID, REQUEST_ID, "approve", _payload()["reason"],
    )
    assert connection.committed and not connection.rolled_back and connection.closed


@pytest.mark.parametrize(
    ("entity_type", "action"),
    [("circle", "approve"), ("assignment", "submit"), ("role", "publish")],
)
def test_unsupported_definition_actions_fail_before_database_open(entity_type, action):
    opened = []
    with pytest.raises(actions.GovernanceDefinitionActionInvalid):
        actions.transition_governance_definition(
            OPERATOR_ID, LOCATION_ID, entity_type, DEFINITION_ID, action, _payload(),
            connection_factory=lambda: opened.append(True),
        )
    assert opened == []


@pytest.mark.parametrize(
    "payload",
    [None, {}, {"request_id": REQUEST_ID, "reason": " "},
     {"request_id": REQUEST_ID, "reason": "valid", "extra": "no"}],
)
def test_invalid_definition_payload_fails_before_database_open(payload):
    opened = []
    with pytest.raises(actions.GovernanceDefinitionActionInvalid):
        actions.transition_governance_definition(
            OPERATOR_ID, LOCATION_ID, "circle", DEFINITION_ID, "submit", payload,
            connection_factory=lambda: opened.append(True),
        )
    assert opened == []


def test_tenant_denial_rolls_back_and_closes(monkeypatch):
    connection = _Connection(entity_type="circle")

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    monkeypatch.setattr(actions, "set_operator_tenant_context", deny)
    with pytest.raises(TenantContextDenied):
        actions.transition_governance_definition(
            OPERATOR_ID, LOCATION_ID, "circle", DEFINITION_ID, "submit", _payload(),
            connection_factory=lambda: connection,
        )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_database_failure_rolls_back_and_closes(monkeypatch):
    connection = _Connection()

    def fail_execute(_query, _params=None):
        raise RuntimeError("synthetic SQL failure")

    class _FailingCursor(_Cursor):
        def execute(self, query, params=None):
            connection.operations.append(("sql", " ".join(query.split()), params))
            if "transition_governance_definition" in query:
                fail_execute(query, params)

    connection.cursor = lambda: _FailingCursor(connection)
    monkeypatch.setattr(actions, "set_operator_tenant_context", lambda *_args, **_kwargs: None)
    with pytest.raises(RuntimeError, match="synthetic SQL failure"):
        actions.transition_governance_definition(
            OPERATOR_ID, LOCATION_ID, "role", DEFINITION_ID, "submit", _payload(),
            connection_factory=lambda: connection,
        )
    assert connection.rolled_back and connection.closed and not connection.committed
