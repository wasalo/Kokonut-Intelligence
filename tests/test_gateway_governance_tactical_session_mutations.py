"""Tactical session creation is one exact-scope tenant transaction."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import governance_tactical_session_mutations as mutations

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
CIRCLE_ID = str(uuid4())
ROLE_ID = str(uuid4())
REQUEST_ID = str(uuid4())
SESSION_ID = str(uuid4())
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
        if "create_governance_tactical_session" in query:
            self.description = [
                SimpleNamespace(name=name)
                for name in ("event_id", "session_id", "actor_party_id", "status", "created_at")
            ]

    def fetchone(self):
        return EVENT_ID, SESSION_ID, ACTOR_ID, "planned", datetime(2026, 10, 19, tzinfo=timezone.utc)


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
        "reason": "Schedule a location-scoped governance review.",
        "circle_id": CIRCLE_ID,
        "session_type": "weekly_review",
        "title": "Weekly operations review",
    }
    payload.update(changes)
    return payload


def test_session_create_sets_exact_context_and_audited_function(monkeypatch):
    connection = _Connection()
    contexts = []

    def set_context(conn, **kwargs):
        contexts.append(kwargs)
        conn.operations.append(("context", kwargs))

    monkeypatch.setattr(mutations, "set_operator_tenant_context", set_context)
    result = mutations.create_governance_tactical_session(
        OPERATOR_ID,
        LOCATION_ID,
        _payload(
            scheduled_at="2026-10-20T10:30:00-04:00",
            facilitator_role_id=ROLE_ID.upper(),
            agenda_scope="Review field actions and stakeholder follow-up.",
        ),
        connection_factory=lambda: connection,
    )

    assert result["event_id"] == EVENT_ID
    assert result["session_id"] == SESSION_ID
    assert result["status"] == "planned"
    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_tactical",
        "action": "create",
    }]
    context_index = next(i for i, item in enumerate(connection.operations) if item[0] == "context")
    function_index = next(
        i for i, item in enumerate(connection.operations)
        if item[0] == "sql" and "create_governance_tactical_session" in item[1]
    )
    assert context_index < function_index
    params = connection.operations[function_index][2]
    assert params[:2] == (LOCATION_ID, REQUEST_ID)
    assert json.loads(params[2]) == {
        "circle_id": CIRCLE_ID,
        "session_type": "weekly_review",
        "title": "Weekly operations review",
        "scheduled_at": "2026-10-20T10:30:00-04:00",
        "facilitator_role_id": ROLE_ID,
        "agenda_scope": "Review field actions and stakeholder follow-up.",
    }
    assert params[3] == "Schedule a location-scoped governance review."
    assert connection.committed and not connection.rolled_back and connection.closed


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "active"},
        {"notes": "private notes"},
        {"outcome_summary": "outcome"},
        {"session_type": "unsupported"},
        {"scheduled_at": "2026-10-20T10:00:00"},
        {"facilitator_role_id": "not-a-uuid"},
        {"title": " "},
    ],
)
def test_invalid_session_fields_fail_before_database_open(changes):
    opened = []
    with pytest.raises(mutations.GovernanceTacticalSessionInvalid):
        mutations.create_governance_tactical_session(
            OPERATOR_ID, LOCATION_ID, _payload(**changes),
            connection_factory=lambda: opened.append(True),
        )
    assert opened == []


def test_extra_payload_and_invalid_location_fail_before_database_open():
    opened = []
    with pytest.raises(mutations.GovernanceTacticalSessionInvalid):
        mutations.create_governance_tactical_session(
            OPERATOR_ID, LOCATION_ID, _payload(extra="unsupported"),
            connection_factory=lambda: opened.append(True),
        )
    with pytest.raises(mutations.GovernanceTacticalSessionInvalid):
        mutations.create_governance_tactical_session(
            OPERATOR_ID, "invalid", _payload(), connection_factory=lambda: opened.append(True)
        )
    assert opened == []


def test_tenant_denial_rolls_back_and_closes(monkeypatch):
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    monkeypatch.setattr(mutations, "set_operator_tenant_context", deny)
    with pytest.raises(TenantContextDenied):
        mutations.create_governance_tactical_session(
            OPERATOR_ID, LOCATION_ID, _payload(), connection_factory=lambda: connection
        )
    assert connection.rolled_back and connection.closed and not connection.committed
