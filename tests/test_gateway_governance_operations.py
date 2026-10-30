"""Scoped, bounded governance role and tactical reads are privacy preserving."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import governance_operations as operations

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
ROLE_ID = str(uuid4())
CIRCLE_ID = str(uuid4())
ITEM_ID = str(uuid4())
TACTICAL_SESSION_ID = str(uuid4())
TACTICAL_CURSOR_ID = str(uuid4())
CREATED_AT = datetime(2026, 10, 18, tzinfo=timezone.utc)


def _tactical_session_item(**updates):
    item = {
        "id": TACTICAL_SESSION_ID,
        "session_type": "weekly_review",
        "title": "Weekly review",
        "scheduled_at": CREATED_AT,
        "status": "planned",
        "created_at": CREATED_AT,
        "circle_key": "adelphi-stewardship",
        "circle_name": "Adelphi Stewardship",
        "item_count": 3,
        "open_item_count": 2,
        "disposed_item_count": 1,
        "overdue_item_count": 1,
    }
    item.update(updates)
    return item


def _valid_tactical_session_page(location_id=LOCATION_ID, *, items=None, next_cursor=None):
    return {
        "location_id": location_id,
        "items": [_tactical_session_item()] if items is None else items,
        "next_cursor": next_cursor,
    }


def _valid_tactical_session_create_request(**updates):
    request = {
        "request_id": str(uuid4()),
        "reason": "Plan the location governance review",
        "circle_id": CIRCLE_ID,
        "session_type": "weekly_review",
        "title": "Weekly governance review",
    }
    request.update(updates)
    return request


def _valid_tactical_session_create_result(**updates):
    result = {
        "event_id": str(uuid4()),
        "session_id": TACTICAL_SESSION_ID,
        "actor_party_id": str(uuid4()),
        "status": "planned",
        "created_at": CREATED_AT,
    }
    result.update(updates)
    return result


def _authorized_governance_client(
    monkeypatch,
    service_result,
    *,
    location_id=LOCATION_ID,
    scope_action="read",
):
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="c" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="synthetic-test-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, scoped_operator, resource, action, scoped_location):
            return (
                scoped_operator == OPERATOR_ID
                and resource == "governance_tactical"
                and action == scope_action
                and scoped_location == location_id
            )

        def csrf_valid(self, _request, _operator_session):
            return True

    class InMemoryAudit:
        def __init__(self):
            pass

        def replay_pending(self, _limit=100):
            return 0

        def log(self, **_event):
            return None

        def capture_status(self):
            return "ok"

        def reserve_mutation(self):
            return "synthetic-mutation-reservation"

        def release_mutation(self, _reservation):
            return None

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    monkeypatch.setattr(
        "services.gateway.governance_operations.list_location_governance_tactical_sessions",
        lambda *_args, **_kwargs: service_result,
    )
    return TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    )


def test_role_registry_covers_all_governance_lifecycle_states():
    assert operations._ROLE_STATUSES == (
        "draft", "submitted", "approved", "active", "suspended", "rejected", "retired"
    )
    assert operations._CIRCLE_STATUSES == (
        "draft", "submitted", "active", "suspended", "rejected", "retired"
    )


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = None
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.query = " ".join(query.split())
        self.connection.operations.append(("sql", self.query, params))
        if "FROM public.governance_role AS role" in self.query and "COUNT(DISTINCT" in self.query:
            self.description = [
                SimpleNamespace(name=name)
                for name in (
                    "id", "role_key", "name", "purpose", "status", "effective_from",
                    "effective_until", "review_due_at", "created_at", "circle_key",
                    "circle_name", "circle_status", "active_accountability_count",
                    "current_assignment_count", "applicable_authority_domain_count",
                )
            ]
        elif "FROM public.governance_role AS role" in self.query:
            self.description = [
                SimpleNamespace(name=name)
                for name in (
                    "id", "role_key", "name", "purpose", "status", "effective_from",
                    "effective_until", "review_due_at", "created_at", "circle_key",
                    "circle_name", "circle_status",
                )
            ]
        elif "FROM public.governance_role_accountability AS accountability" in self.query:
            self.description = [
                SimpleNamespace(name=name)
                for name in ("accountability", "priority", "required")
            ]
        elif "FROM public.governance_role_domain AS domain" in self.query:
            self.description = [
                SimpleNamespace(name=name)
                for name in (
                    "domain_type", "domain_key", "scope_type", "authority_level",
                    "requires_human_approval",
                )
            ]
        elif (
            "FROM public.governance_circle AS circle" in self.query
            and "circle.description" in self.query
        ):
            self.description = [
                SimpleNamespace(name=name)
                for name in (
                    "id", "circle_key", "name", "purpose", "description",
                    "parent_circle_id", "status",
                )
            ]
        elif "FROM public.governance_tactical_item AS item" in self.query and "requested_next_action" in self.query:
            self.description = [
                SimpleNamespace(name=name)
                for name in (
                    "id", "requested_next_action", "priority", "due_at", "status",
                    "created_at", "session_type", "session_title", "scheduled_at",
                    "session_status", "owner_role_key",
                )
            ]
        elif "FROM public.governance_tactical_session AS session" in self.query and "COUNT(item.id)" in self.query:
            self.description = [
                SimpleNamespace(name=name)
                for name in (
                    "id", "session_type", "title", "scheduled_at", "status", "created_at",
                    "circle_key", "circle_name", "item_count", "open_item_count",
                    "disposed_item_count", "overdue_item_count",
                )
            ]

    def fetchone(self):
        if "SELECT role.created_at" in self.query or "SELECT item.created_at" in self.query:
            return self.connection.cursor_timestamp
        if "SELECT session.created_at" in self.query:
            return self.connection.cursor_timestamp
        if "FROM public.governance_circle AS circle" in self.query and "circle.description" in self.query:
            return self.connection.circle_detail_row
        if "FROM public.governance_role AS role" in self.query and "COUNT(DISTINCT" not in self.query:
            return self.connection.role_detail_row
        return None

    def fetchall(self):
        if "FROM public.governance_role AS role" in self.query and "COUNT(DISTINCT" in self.query:
            return self.connection.role_rows
        if "FROM public.governance_role_accountability AS accountability" in self.query:
            return self.connection.accountability_rows
        if "FROM public.governance_role_domain AS domain" in self.query:
            return self.connection.domain_rows
        if "FROM public.governance_tactical_item AS item" in self.query and "requested_next_action" in self.query:
            return self.connection.tactical_rows
        if "FROM public.governance_tactical_session AS session" in self.query and "COUNT(item.id)" in self.query:
            return self.connection.tactical_session_rows
        return []


class _Connection:
    autocommit = False

    def __init__(self):
        self.operations = []
        self.cursor_timestamp = (CREATED_AT,)
        self.role_rows = [(
            ROLE_ID, "steward", "Farm steward", "Coordinate location stewardship.",
            "active", CREATED_AT, None, None, CREATED_AT, "adelphi-stewardship",
            "Adelphi Stewardship", "active", 4, 1, 2,
        )]
        self.role_detail_row = (
            ROLE_ID, "steward", "Farm steward", "Coordinate location stewardship.",
            "active", CREATED_AT, None, None, CREATED_AT, "adelphi-stewardship",
            "Adelphi Stewardship", "active",
        )
        self.circle_detail_row = (
            CIRCLE_ID, "adelphi-stewardship", "Adelphi Stewardship",
            "Coordinate farm stewardship.", "Location governance circle.", None, "draft",
        )
        self.accountability_rows = [("Maintain seasonal field plans.", 2, True)]
        self.domain_rows = [("farm_operations", "field_plan", "location", "recommend", True)]
        self.tactical_rows = [(
            ITEM_ID, "Review the irrigation schedule.", 2, None, "open", CREATED_AT,
            "weekly_review", "Weekly review", CREATED_AT, "active", "steward",
        )]
        self.tactical_session_rows = [(
            str(uuid4()), "weekly_review", "Weekly review", CREATED_AT, "planned",
            CREATED_AT, "adelphi-stewardship", "Adelphi Stewardship", 3, 2, 1, 1,
        )]
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_role_registry_uses_signed_read_context_and_omits_party_and_policy_fields(monkeypatch):
    connection = _Connection()
    contexts = []

    def set_context(conn, **kwargs):
        contexts.append((conn, kwargs))
        conn.operations.append(("context", kwargs))

    monkeypatch.setattr(operations, "set_operator_tenant_context", set_context)
    result = operations.list_location_governance_roles(
        OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection
    )

    assert result["items"][0]["role_key"] == "steward"
    assert set(result["items"][0]) == {
        "id", "role_key", "name", "purpose", "status", "effective_from",
        "effective_until", "review_due_at", "created_at", "circle_key",
        "circle_name", "circle_status", "active_accountability_count",
        "current_assignment_count", "applicable_authority_domain_count",
    }
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_roles",
        "action": "read",
    })]
    operations_list = connection.operations
    context_index = next(i for i, item in enumerate(operations_list) if item[0] == "context")
    query_index = next(
        i for i, item in enumerate(operations_list)
        if item[0] == "sql" and "COUNT(DISTINCT" in item[1]
    )
    assert context_index < query_index
    query = operations_list[query_index][1]
    assert "circle.scope_type = 'location'" in query
    assert "circle.scope_id = %s::uuid" in query
    assert "display_name" not in query
    assert "policy_text" not in query
    assert "metadata" not in query
    assert "party_id" not in query
    assert connection.rolled_back and connection.closed


def test_role_detail_returns_bounded_responsibilities_without_private_fields(monkeypatch):
    connection = _Connection()
    contexts = []

    def set_context(conn, **kwargs):
        contexts.append((conn, kwargs))
        conn.operations.append(("context", kwargs))

    monkeypatch.setattr(
        operations,
        "set_operator_tenant_context",
        set_context,
    )

    result = operations.get_location_governance_role_detail(
        OPERATOR_ID, LOCATION_ID, ROLE_ID, connection_factory=lambda: connection
    )

    assert result["role"]["role_key"] == "steward"
    assert result["accountabilities"] == [{
        "accountability": "Maintain seasonal field plans.",
        "priority": 2,
        "required": True,
    }]
    assert result["authority_domains"] == [{
        "domain_type": "farm_operations",
        "domain_key": "field_plan",
        "scope_type": "location",
        "authority_level": "recommend",
        "requires_human_approval": True,
    }]
    assert result["accountabilities_truncated"] is False
    assert result["authority_domains_truncated"] is False
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_roles",
        "action": "read",
    })]
    operations_log = connection.operations
    context_index = next(i for i, item in enumerate(operations_log) if item[0] == "context")
    query_indexes = [i for i, item in enumerate(operations_log) if item[0] == "sql" and item[1].startswith("SELECT")]
    assert context_index < min(query_indexes)
    sql = " ".join(item[1] for item in operations_log if item[0] == "sql")
    assert "circle.scope_id = %s::uuid" in sql
    for private_field in (
        "party_id", "policy_text", "evidence_expectation", "constraints", "metadata",
    ):
        assert private_field not in sql
    assert connection.rolled_back and connection.closed


def test_role_detail_hides_unknown_or_cross_location_role(monkeypatch):
    connection = _Connection()
    connection.role_detail_row = None
    monkeypatch.setattr(operations, "set_operator_tenant_context", lambda *_args, **_kwargs: None)

    result = operations.get_location_governance_role_detail(
        OPERATOR_ID, LOCATION_ID, ROLE_ID, connection_factory=lambda: connection
    )

    assert result is None
    assert not any(
        "governance_role_accountability" in item[1] or "governance_role_domain" in item[1]
        for item in connection.operations if item[0] == "sql"
    )
    assert connection.rolled_back and connection.closed


def test_circle_detail_returns_edit_fields_only_after_signed_location_context(monkeypatch):
    connection = _Connection()
    contexts = []
    monkeypatch.setattr(
        operations,
        "set_operator_tenant_context",
        lambda conn, **kwargs: (
            contexts.append((conn, kwargs)),
            conn.operations.append(("context", kwargs)),
        ),
    )

    result = operations.get_location_governance_circle_detail(
        OPERATOR_ID, LOCATION_ID, CIRCLE_ID, connection_factory=lambda: connection
    )

    assert result == {
        "location_id": LOCATION_ID,
        "circle": {
            "id": CIRCLE_ID,
            "circle_key": "adelphi-stewardship",
            "name": "Adelphi Stewardship",
            "purpose": "Coordinate farm stewardship.",
            "description": "Location governance circle.",
            "parent_circle_id": None,
            "status": "draft",
        },
    }
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_roles",
        "action": "read",
    })]
    sql_entry = next(item for item in connection.operations if item[0] == "sql" and "circle.description" in item[1])
    context_index = next(i for i, item in enumerate(connection.operations) if item[0] == "context")
    sql_index = connection.operations.index(sql_entry)
    assert context_index < sql_index
    assert "circle.scope_id = %s::uuid" in sql_entry[1]
    assert "circle.status = ANY(%s::text[])" in sql_entry[1]
    assert connection.rolled_back and connection.closed


def test_circle_detail_hides_unknown_or_cross_location_circle(monkeypatch):
    connection = _Connection()
    connection.circle_detail_row = None
    monkeypatch.setattr(operations, "set_operator_tenant_context", lambda *_args, **_kwargs: None)

    assert operations.get_location_governance_circle_detail(
        OPERATOR_ID, LOCATION_ID, CIRCLE_ID, connection_factory=lambda: connection
    ) is None
    assert connection.rolled_back and connection.closed


def test_role_detail_caps_accountability_and_authority_domain_lists(monkeypatch):
    connection = _Connection()
    connection.accountability_rows = [
        (f"Accountability {index}", 3, True) for index in range(101)
    ]
    connection.domain_rows = [
        ("farm_operations", f"domain_{index}", "location", "recommend", True)
        for index in range(101)
    ]
    monkeypatch.setattr(operations, "set_operator_tenant_context", lambda *_args, **_kwargs: None)

    result = operations.get_location_governance_role_detail(
        OPERATOR_ID, LOCATION_ID, ROLE_ID, connection_factory=lambda: connection
    )

    assert len(result["accountabilities"]) == 100
    assert result["accountabilities_truncated"] is True
    assert len(result["authority_domains"]) == 100
    assert result["authority_domains_truncated"] is True
    assert connection.rolled_back and connection.closed


def test_tactical_queue_uses_its_own_scope_and_omits_party_and_private_disposition(monkeypatch):
    connection = _Connection()
    contexts = []
    monkeypatch.setattr(
        operations,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )
    result = operations.list_location_governance_tactical_items(
        OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection
    )

    assert result["items"][0]["requested_next_action"] == "Review the irrigation schedule."
    assert set(result["items"][0]) == {
        "id", "requested_next_action", "priority", "due_at", "status", "created_at",
        "session_type", "session_title", "scheduled_at", "session_status", "owner_role_key",
    }
    assert contexts[0][1] == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_tactical",
        "action": "read",
    }
    sql = " ".join(item[1] for item in connection.operations if item[0] == "sql")
    assert "circle.scope_type = 'location'" in sql
    assert "item.status = ANY(%s::text[])" in sql
    assert "disposition_summary" not in sql
    assert "proposer_party_id" not in sql
    assert "owner_party_id" not in sql
    assert "agenda_scope" not in sql
    assert connection.rolled_back and connection.closed


def test_tactical_session_registry_is_location_scoped_and_aggregate_only(monkeypatch):
    connection = _Connection()
    contexts = []
    monkeypatch.setattr(
        operations,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operations.list_location_governance_tactical_sessions(
        OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection
    )

    session = result["items"][0]
    assert session["title"] == "Weekly review"
    assert session["open_item_count"] == 2
    assert set(session) == {
        "id", "session_type", "title", "scheduled_at", "status", "created_at",
        "circle_key", "circle_name", "item_count", "open_item_count",
        "disposed_item_count", "overdue_item_count",
    }
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_tactical",
        "action": "read",
    })]
    sql = " ".join(item[1] for item in connection.operations if item[0] == "sql")
    assert "SET TRANSACTION READ ONLY" in sql
    assert "circle.scope_type = 'location'" in sql
    assert "circle.scope_id = %s::uuid" in sql
    assert "session.status = ANY(%s::text[])" in sql
    for private_field in ("agenda_scope", "session.notes", "outcome_summary", "created_by_party_id"):
        assert private_field not in sql
    assert connection.rolled_back and connection.closed


def test_tactical_session_http_route_returns_exact_scoped_page(monkeypatch):
    page = _valid_tactical_session_page()
    with _authorized_governance_client(monkeypatch, page) as client:
        response = client.get(f"/operator/api/governance/{LOCATION_ID}/tactical-sessions")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {
        value.strip().lower() for value in response.headers["vary"].split(",")
    }
    assert response.json() == {
        "location_id": LOCATION_ID,
        "items": [
            {
                **_tactical_session_item(),
                "scheduled_at": "2026-10-18T00:00:00+00:00",
                "created_at": "2026-10-18T00:00:00+00:00",
            }
        ],
        "next_cursor": None,
    }


@pytest.mark.parametrize(
    ("page", "params"),
    [
        (
            _valid_tactical_session_page(
                items=[_tactical_session_item(extra="not in the SQL projection")]
            ),
            {},
        ),
        (
            _valid_tactical_session_page(
                items=[_tactical_session_item(status="draft")]
            ),
            {},
        ),
        (
            _valid_tactical_session_page(
                items=[_tactical_session_item(), _tactical_session_item(id=str(uuid4()))]
            ),
            {"limit": 1},
        ),
        (
            _valid_tactical_session_page(
                items=[_tactical_session_item()], next_cursor=TACTICAL_CURSOR_ID
            ),
            {"limit": 1},
        ),
        (
            _valid_tactical_session_page(
                items=[_tactical_session_item(id=TACTICAL_CURSOR_ID)],
                next_cursor=TACTICAL_CURSOR_ID,
            ),
            {"limit": 1, "cursor": TACTICAL_CURSOR_ID},
        ),
    ],
)
def test_tactical_session_http_route_rejects_invalid_page(monkeypatch, page, params):
    with _authorized_governance_client(monkeypatch, page) as client:
        response = client.get(
            f"/operator/api/governance/{LOCATION_ID}/tactical-sessions", params=params
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Governance tactical sessions unavailable"}
    assert response.headers["cache-control"] == "no-store"


def test_tactical_session_http_route_rejects_wrong_location(monkeypatch):
    page = _valid_tactical_session_page(location_id=str(uuid4()))
    with _authorized_governance_client(monkeypatch, page) as client:
        response = client.get(f"/operator/api/governance/{LOCATION_ID}/tactical-sessions")

    assert response.status_code == 500
    assert response.json() == {"error": "Governance tactical sessions unavailable"}
    assert response.headers["cache-control"] == "no-store"


def test_tactical_session_create_route_documents_strict_contract_and_auth_policy(monkeypatch):
    with _authorized_governance_client(
        monkeypatch, None, scope_action="create"
    ) as client:
        schema = client.app.openapi()

    operation = schema["paths"][
        "/operator/api/governance/{location_id}/tactical-sessions"
    ]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    expected_request_fields = {
        "request_id", "reason", "circle_id", "session_type", "title",
        "scheduled_at", "facilitator_role_id", "recorder_role_id", "agenda_scope",
    }
    assert set(request_schema["properties"]) == expected_request_fields
    assert request_schema["additionalProperties"] is False
    assert set(request_schema["required"]) == {
        "request_id", "reason", "circle_id", "session_type", "title",
    }
    assert request_schema["properties"]["scheduled_at"]["format"] == "date-time"

    response_schema = operation["responses"]["201"]["content"][
        "application/json"
    ]["schema"]
    component_name = response_schema["$ref"].rsplit("/", 1)[1]
    response_schema = schema["components"]["schemas"][component_name]
    assert set(response_schema["properties"]) == {
        "event_id", "session_id", "status", "created_at",
    }
    assert "actor_party_id" not in response_schema["properties"]
    assert response_schema["additionalProperties"] is False
    assert operation["responses"]["201"]["headers"]["Cache-Control"]["schema"]["example"] == "no-store"
    assert operation["responses"]["201"]["headers"]["Vary"]["schema"]["example"] == "Cookie"
    assert operation["responses"]["400"]["headers"]["Cache-Control"]["schema"]["example"] == "no-store"

    from services.gateway.operator_auth import auth_route_policy

    assert auth_route_policy(
        "POST",
        f"/operator/api/governance/{LOCATION_ID}/tactical-sessions",
        enabled=True,
    ) == {
        "resource": "governance_tactical",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }


def test_tactical_session_create_returns_identity_minimized_receipt_and_replays(monkeypatch):
    calls = []
    action_result = _valid_tactical_session_create_result()

    def create(operator_id, location_id, payload):
        calls.append((operator_id, location_id, payload))
        return action_result

    monkeypatch.setattr(
        "services.gateway.governance_tactical_session_mutations.create_governance_tactical_session",
        create,
    )
    payload = _valid_tactical_session_create_request(
        scheduled_at="2026-11-01T10:00:00-04:00",
        facilitator_role_id=ROLE_ID,
        agenda_scope="Review field evidence and open decisions",
    )
    with _authorized_governance_client(
        monkeypatch, None, scope_action="create"
    ) as client:
        first = client.post(
            f"/operator/api/governance/{LOCATION_ID}/tactical-sessions", json=payload
        )
        replay = client.post(
            f"/operator/api/governance/{LOCATION_ID}/tactical-sessions", json=payload
        )

    expected = {
        "event_id": action_result["event_id"],
        "session_id": action_result["session_id"],
        "status": "planned",
        "created_at": "2026-10-18T00:00:00+00:00",
    }
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json() == expected
    assert "actor_party_id" not in first.json()
    assert first.headers["cache-control"] == replay.headers["cache-control"] == "no-store"
    for response in (first, replay):
        assert "cookie" in {
            value.strip().lower() for value in response.headers["vary"].split(",")
        }
    assert calls == [
        (OPERATOR_ID, LOCATION_ID, {
            **payload,
            "circle_id": CIRCLE_ID,
            "facilitator_role_id": ROLE_ID,
        }),
        (OPERATOR_ID, LOCATION_ID, {
            **payload,
            "circle_id": CIRCLE_ID,
            "facilitator_role_id": ROLE_ID,
        }),
    ]


@pytest.mark.parametrize(
    "overrides",
    [
        {"actor_party_id": str(uuid4())},
        {"request_id": "not-a-uuid"},
        {"scheduled_at": "2026-11-01T10:00:00"},
        {"title": " "},
        {"agenda_scope": "x" * 10_001},
    ],
)
def test_tactical_session_create_rejects_invalid_request_before_service(monkeypatch, overrides):
    calls = []
    monkeypatch.setattr(
        "services.gateway.governance_tactical_session_mutations.create_governance_tactical_session",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    with _authorized_governance_client(
        monkeypatch, None, scope_action="create"
    ) as client:
        response = client.post(
            f"/operator/api/governance/{LOCATION_ID}/tactical-sessions",
            json=_valid_tactical_session_create_request(**overrides),
        )

    assert response.status_code == 400
    assert response.json() == {"error": "Tactical session request is invalid"}
    assert response.headers["cache-control"] == "no-store"
    assert calls == []


@pytest.mark.parametrize(
    "result",
    [
        {**_valid_tactical_session_create_result(), "extra": "private"},
        _valid_tactical_session_create_result(status="completed"),
        _valid_tactical_session_create_result(created_at="2026-10-18T00:00:00"),
    ],
)
def test_tactical_session_create_sanitizes_malformed_action_results(monkeypatch, result):
    monkeypatch.setattr(
        "services.gateway.governance_tactical_session_mutations.create_governance_tactical_session",
        lambda *_args, **_kwargs: result,
    )
    with _authorized_governance_client(
        monkeypatch, None, scope_action="create"
    ) as client:
        response = client.post(
            f"/operator/api/governance/{LOCATION_ID}/tactical-sessions",
            json=_valid_tactical_session_create_request(),
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": "Governance tactical session creation unavailable"
    }
    assert "actor_party_id" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_tactical_session_create_requires_create_grant(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "services.gateway.governance_tactical_session_mutations.create_governance_tactical_session",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    with _authorized_governance_client(
        monkeypatch, None, scope_action="read"
    ) as client:
        response = client.post(
            f"/operator/api/governance/{LOCATION_ID}/tactical-sessions",
            json=_valid_tactical_session_create_request(),
        )

    assert response.status_code == 403
    assert calls == []
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("reader", "kwargs", "message"),
    [
        (operations.list_location_governance_roles, {"status": "archived"}, "status is not available"),
        (operations.list_location_governance_roles, {"limit": "1e2"}, "limit must be an integer"),
        (operations.list_location_governance_tactical_items, {"limit": 101}, "limit must be an integer"),
        (operations.list_location_governance_tactical_items, {"cursor": "invalid"}, "Invalid cursor"),
        (operations.list_location_governance_tactical_sessions, {"limit": "1e2"}, "limit must be an integer"),
        (operations.list_location_governance_tactical_sessions, {"cursor": "invalid"}, "Invalid cursor"),
        (operations.get_location_governance_role_detail, {"role_id": "invalid"}, "Invalid role identifier"),
        (operations.get_location_governance_circle_detail, {"circle_id": "invalid"}, "Invalid circle identifier"),
    ],
)
def test_invalid_selectors_fail_before_connecting(reader, kwargs, message):
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid selectors must be rejected before database access")

    with pytest.raises(operations.GovernanceOperationsInvalid, match=message):
        reader(OPERATOR_ID, LOCATION_ID, connection_factory=connection_factory, **kwargs)
    assert not opened


def test_role_cursor_is_location_and_status_qualified(monkeypatch):
    connection = _Connection()
    connection.cursor_timestamp = None
    monkeypatch.setattr(operations, "set_operator_tenant_context", lambda *_args, **_kwargs: None)

    with pytest.raises(operations.GovernanceOperationsInvalid, match="cursor is not available"):
        operations.list_location_governance_roles(
            OPERATOR_ID,
            LOCATION_ID,
            status="active",
            cursor=ROLE_ID,
            connection_factory=lambda: connection,
        )
    sql = [item[1] for item in connection.operations if item[0] == "sql"]
    assert "circle.scope_id = %s::uuid" in sql[-1]
    assert "role.status = ANY(%s::text[])" in sql[-1]
    assert not any("COUNT(DISTINCT" in query for query in sql)
    assert connection.rolled_back and connection.closed


def test_tenant_denial_rolls_back_role_query(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(
        operations,
        "set_operator_tenant_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TenantContextDenied("revoked")),
    )
    with pytest.raises(TenantContextDenied):
        operations.list_location_governance_roles(
            OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection
        )
    assert not any("COUNT(DISTINCT" in item[1] for item in connection.operations if item[0] == "sql")
    assert connection.rolled_back and connection.closed


def test_role_and_tactical_routes_deny_missing_exact_grants_before_service(monkeypatch):
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="a" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="synthetic-test-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, *_scope):
            return False

    class InMemoryAudit:
        def __init__(self):
            pass

        def replay_pending(self, _limit=100):
            return 0

        def log(self, **_event):
            return None

        def capture_status(self):
            return "ok"

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    monkeypatch.setattr(
        "services.gateway.governance_operations.list_location_governance_roles",
        lambda *_args, **_kwargs: pytest.fail("missing role grant reached data service"),
    )
    monkeypatch.setattr(
        "services.gateway.governance_operations.get_location_governance_role_detail",
        lambda *_args, **_kwargs: pytest.fail("missing role grant reached detail service"),
    )
    monkeypatch.setattr(
        "services.gateway.governance_operations.get_location_governance_circle_detail",
        lambda *_args, **_kwargs: pytest.fail("missing circle grant reached detail service"),
    )
    monkeypatch.setattr(
        "services.gateway.governance_operations.list_location_governance_tactical_items",
        lambda *_args, **_kwargs: pytest.fail("missing tactical grant reached data service"),
    )
    monkeypatch.setattr(
        "services.gateway.governance_operations.list_location_governance_tactical_sessions",
        lambda *_args, **_kwargs: pytest.fail("missing tactical grant reached session service"),
    )
    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        role_response = client.get(f"/operator/api/governance/{LOCATION_ID}/roles")
        role_detail_response = client.get(
            f"/operator/api/governance/{LOCATION_ID}/roles/{ROLE_ID}"
        )
        circle_detail_response = client.get(
            f"/operator/api/governance/{LOCATION_ID}/circles/{CIRCLE_ID}"
        )
        tactical_response = client.get(
            f"/operator/api/governance/{LOCATION_ID}/tactical-items"
        )
        tactical_sessions_response = client.get(
            f"/operator/api/governance/{LOCATION_ID}/tactical-sessions"
        )

    assert role_response.status_code == role_detail_response.status_code == circle_detail_response.status_code == tactical_response.status_code == tactical_sessions_response.status_code == 403
    assert role_response.headers["cache-control"] == "no-store"
    assert role_detail_response.headers["cache-control"] == "no-store"
    assert circle_detail_response.headers["cache-control"] == "no-store"
    assert tactical_response.headers["cache-control"] == "no-store"
    assert tactical_sessions_response.headers["cache-control"] == "no-store"
