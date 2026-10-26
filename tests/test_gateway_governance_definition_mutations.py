"""Governance circle/role draft mutations use one bounded tenant transaction."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import governance_definition_mutations as mutations

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
DEFINITION_ID = str(uuid4())
REQUEST_ID = str(uuid4())
EVENT_ID = str(uuid4())
ACTOR_ID = str(uuid4())
CIRCLE_ID = str(uuid4())


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
        if "mutate_governance_definition" in query:
            self.description = [
                SimpleNamespace(name=name)
                for name in (
                    "event_id", "entity_type", "entity_id", "action",
                    "actor_party_id", "created_at", "result",
                )
            ]

    def fetchone(self):
        return (
            EVENT_ID,
            self.connection.entity_type,
            self.connection.entity_id,
            self.connection.action,
            ACTOR_ID,
            "2026-10-18T00:00:00Z",
            {"id": self.connection.entity_id, "status": "draft"},
        )


class _Connection:
    autocommit = False

    def __init__(self, entity_type="circle", action="create", entity_id=DEFINITION_ID):
        self.entity_type = entity_type
        self.action = action
        self.entity_id = entity_id
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


def _circle_payload(**changes):
    payload = {
        "request_id": REQUEST_ID,
        "reason": "Creating a location governance circle for review.",
        "circle_key": "field_operations",
        "name": "Field Operations",
        "purpose": "Coordinate field operations and review decisions.",
    }
    payload.update(changes)
    return payload


def test_circle_create_sets_exact_context_before_database_function_and_commits(monkeypatch):
    connection = _Connection(entity_type="circle", action="create")
    contexts = []

    def set_context(conn, **kwargs):
        contexts.append(kwargs)
        conn.operations.append(("context", kwargs))

    monkeypatch.setattr(mutations, "set_operator_tenant_context", set_context)
    result = mutations.mutate_governance_definition(
        OPERATOR_ID,
        LOCATION_ID,
        "circle",
        "create",
        None,
        _circle_payload(description="A governed operating circle."),
        connection_factory=lambda: connection,
    )

    assert result["event_id"] == EVENT_ID
    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_roles",
        "action": "create",
    }]
    context_index = next(index for index, item in enumerate(connection.operations) if item[0] == "context")
    function_index = next(
        index for index, item in enumerate(connection.operations)
        if item[0] == "sql" and "mutate_governance_definition" in item[1]
    )
    assert context_index < function_index
    params = connection.operations[function_index][2]
    assert params[:5] == (LOCATION_ID, "circle", None, REQUEST_ID, "create")
    assert json.loads(params[5]) == {
        "circle_key": "field_operations",
        "name": "Field Operations",
        "purpose": "Coordinate field operations and review decisions.",
        "description": "A governed operating circle.",
    }
    assert params[6] == "Creating a location governance circle for review."
    assert connection.committed and not connection.rolled_back and connection.closed


def test_role_update_normalizes_target_and_uses_exact_update_grant(monkeypatch):
    connection = _Connection(entity_type="role", action="update", entity_id=DEFINITION_ID)
    contexts = []
    monkeypatch.setattr(
        mutations,
        "set_operator_tenant_context",
        lambda conn, **kwargs: (contexts.append(kwargs), conn.operations.append(("context", kwargs))),
    )
    result = mutations.mutate_governance_definition(
        OPERATOR_ID,
        LOCATION_ID,
        "role",
        "update",
        DEFINITION_ID.upper(),
        {
            "request_id": REQUEST_ID,
            "reason": "Clarify the draft role purpose.",
            "purpose": "Coordinate farm-level operations and reporting.",
        },
        connection_factory=lambda: connection,
    )
    assert result["action"] == "update"
    assert contexts[0]["action"] == "update"
    mutation_call = next(item for item in connection.operations if item[0] == "sql" and "mutate_governance_definition" in item[1])
    assert mutation_call[2][2] == DEFINITION_ID
    assert json.loads(mutation_call[2][5]) == {
        "purpose": "Coordinate farm-level operations and reporting."
    }
    assert connection.committed and connection.closed


@pytest.mark.parametrize(
    ("entity_type", "action", "entity_id", "payload"),
    [
        ("circle", "create", None, None),
        ("circle", "create", None, {"request_id": REQUEST_ID, "reason": "x", "circle_key": "", "name": "Circle", "purpose": "Purpose"}),
        ("circle", "create", None, {**_circle_payload(), "status": "active"}),
        ("circle", "update", DEFINITION_ID, {"request_id": REQUEST_ID, "reason": "x"}),
        ("role", "create", None, {"request_id": REQUEST_ID, "reason": "x", "role_key": "role", "name": "Role", "purpose": "Purpose"}),
        ("role", "update", DEFINITION_ID, {"request_id": REQUEST_ID, "reason": "x", "circle_id": CIRCLE_ID}),
        ("role", "update", DEFINITION_ID, {"request_id": REQUEST_ID, "reason": "x", "name": " "}),
        ("role", "update", DEFINITION_ID, {"request_id": REQUEST_ID, "reason": " ", "name": "Role"}),
        ("circle", "update", "not-a-uuid", {"request_id": REQUEST_ID, "reason": "x", "name": "Circle"}),
    ],
)
def test_invalid_request_fails_before_database_open(entity_type, action, entity_id, payload):
    opened = []
    with pytest.raises(mutations.GovernanceDefinitionMutationInvalid):
        mutations.mutate_governance_definition(
            OPERATOR_ID,
            LOCATION_ID,
            entity_type,
            action,
            entity_id,
            payload,
            connection_factory=lambda: opened.append(True),
        )
    assert opened == []


def test_tenant_denial_rolls_back_and_closes(monkeypatch):
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    monkeypatch.setattr(mutations, "set_operator_tenant_context", deny)
    with pytest.raises(TenantContextDenied):
        mutations.mutate_governance_definition(
            OPERATOR_ID,
            LOCATION_ID,
            "circle",
            "create",
            None,
            _circle_payload(),
            connection_factory=lambda: connection,
        )
    assert connection.rolled_back and connection.closed and not connection.committed
