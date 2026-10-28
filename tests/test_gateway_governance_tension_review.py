"""Tenant-scoped CAP-024 reviewer reads expose bounded, non-identifying views."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway import governance_tension_review as review  # noqa: E402
from services.gateway.app import create_app  # noqa: E402
from services.gateway.operator_auth import auth_route_policy  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
TENSION_ID = str(uuid4())
CURSOR_ID = str(uuid4())
CREATED_AT = datetime(2026, 10, 18, tzinfo=timezone.utc)


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
        if "SELECT tension.id, tension.title, tension.tension_type" in self.query:
            names = (
                "id", "title", "tension_type", "severity", "urgency", "status",
                "created_at", "review_due_at",
            )
            self.description = [SimpleNamespace(name=name) for name in names]
        elif "SELECT tension.id, tension.title, tension.description" in self.query:
            names = (
                "id", "title", "description", "tension_type", "severity", "urgency",
                "status", "review_due_at", "deferred_until", "created_at", "updated_at",
            )
            self.description = [SimpleNamespace(name=name) for name in names]
        elif "SELECT event.from_status" in self.query:
            names = ("from_status", "to_status", "action", "created_at")
            self.description = [SimpleNamespace(name=name) for name in names]

    def fetchone(self):
        if "SELECT created_at" in self.query:
            return self.connection.cursor_timestamp
        if "SELECT tension.id, tension.title, tension.description" in self.query:
            if self.connection.detail_row is None:
                return None
            if self.connection.detail_row[6] not in review._QUEUE_STATUSES:
                return None
            return self.connection.detail_row
        return None

    def fetchall(self):
        if "SELECT tension.id, tension.title, tension.tension_type" in self.query:
            return self.connection.queue_rows
        if "SELECT event.from_status" in self.query:
            return self.connection.event_rows
        return []


class _Connection:
    def __init__(self):
        self.operations = []
        self.queue_rows = [
            (CURSOR_ID, "Harvest accountability", "unclear_accountability", 3, 2,
             "submitted", CREATED_AT, None),
            (TENSION_ID, "Consent follow-up", "consent_gap", 2, 1,
             "submitted", CREATED_AT.replace(day=17), None),
        ]
        self.cursor_timestamp = (CREATED_AT,)
        self.detail_row = (
            TENSION_ID, "Consent follow-up", "A reviewer should inspect the approved policy.",
            "consent_gap", 2, 1, "submitted", None, None, CREATED_AT, CREATED_AT,
        )
        self.event_rows = [("draft", "submitted", "submitted", CREATED_AT)]
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_queue_uses_read_only_signed_context_and_bounded_projection(monkeypatch):
    connection = _Connection()
    context_calls = []

    def set_context(conn, **kwargs):
        context_calls.append((conn, kwargs))
        conn.operations.append(("context", kwargs))

    monkeypatch.setattr(review, "set_operator_tenant_context", set_context)
    result = review.list_location_governance_tensions(
        OPERATOR_ID,
        LOCATION_ID,
        limit=1,
        connection_factory=lambda: connection,
    )

    assert result["location_id"] == LOCATION_ID
    assert result["items"][0]["id"] == CURSOR_ID
    assert result["next_cursor"] == CURSOR_ID
    assert set(result["items"][0]) == {
        "id", "title", "tension_type", "severity", "urgency", "status",
        "created_at", "review_due_at",
    }
    operations = connection.operations
    assert operations[0][1] == "SET TRANSACTION READ ONLY"
    context_index = next(i for i, operation in enumerate(operations) if operation[0] == "context")
    queue_index = next(
        i for i, operation in enumerate(operations)
        if operation[0] == "sql" and "ORDER BY tension.created_at DESC" in operation[1]
    )
    assert context_index < queue_index
    assert context_calls == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_tension",
        "action": "read",
    })]
    assert "tension.scope_type = 'location'" in operations[queue_index][1]
    assert operations[queue_index][2][1] == ["submitted", "triaged", "in_progress", "deferred"]
    assert connection.rolled_back and connection.closed


def test_cursor_is_resolved_inside_location_and_invalid_cursor_does_not_list(monkeypatch):
    connection = _Connection()
    connection.cursor_timestamp = None
    monkeypatch.setattr(review, "set_operator_tenant_context", lambda *_args, **_kwargs: None)

    with pytest.raises(review.GovernanceTensionReviewInvalid, match="cursor is not available"):
        review.list_location_governance_tensions(
            OPERATOR_ID,
            LOCATION_ID,
            cursor=CURSOR_ID,
            connection_factory=lambda: connection,
        )

    sql = [operation[1] for operation in connection.operations if operation[0] == "sql"]
    assert len(sql) == 4  # Read-only setup and the location-qualified cursor lookup.
    assert "scope_type = 'location'" in sql[-1]
    assert "scope_id = %s::uuid" in sql[-1]
    assert not any("ORDER BY tension.created_at DESC" in query for query in sql)
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"status": "draft"}, "status is not available"),
        ({"limit": 0}, "limit must be an integer"),
        ({"limit": "1e2"}, "limit must be an integer"),
        ({"cursor": "not-a-uuid"}, "Invalid cursor"),
    ],
)
def test_invalid_queue_options_fail_before_connection(kwargs, message):
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid options must fail before opening PostgreSQL")

    with pytest.raises(review.GovernanceTensionReviewInvalid, match=message):
        review.list_location_governance_tensions(
            OPERATOR_ID, LOCATION_ID, connection_factory=connection_factory, **kwargs
        )
    assert not opened


def test_detail_returns_bounded_lifecycle_without_party_notes_or_payloads(monkeypatch):
    connection = _Connection()
    context_calls = []
    monkeypatch.setattr(
        review,
        "set_operator_tenant_context",
        lambda conn, **kwargs: context_calls.append((conn, kwargs)),
    )

    result = review.get_location_governance_tension(
        OPERATOR_ID,
        LOCATION_ID,
        TENSION_ID,
        connection_factory=lambda: connection,
    )
    detail = result["tension"]
    assert detail["id"] == TENSION_ID
    assert detail["description"].startswith("A reviewer")
    assert set(detail) == {
        "id", "title", "description", "tension_type", "severity", "urgency",
        "status", "review_due_at", "deferred_until", "created_at", "updated_at",
    }
    assert result["events"] == [{
        "from_status": "draft",
        "to_status": "submitted",
        "action": "submitted",
        "created_at": CREATED_AT,
    }]
    assert result["events_truncated"] is False
    assert context_calls[0][1]["action"] == "read"
    all_sql = " ".join(operation[1] for operation in connection.operations if operation[0] == "sql")
    assert "scope_type = 'location'" in all_sql
    detail_query = next(
        operation for operation in connection.operations
        if operation[0] == "sql" and "tension.description" in operation[1]
    )
    assert "tension.status = ANY(%s::text[])" in detail_query[1]
    assert detail_query[2][2] == ["submitted", "triaged", "in_progress", "deferred"]
    assert "event.note" not in all_sql
    assert "reported_by_party_id" not in all_sql
    assert connection.rolled_back and connection.closed


def test_detail_hides_absent_and_cross_location_rows_as_not_found(monkeypatch):
    connection = _Connection()
    connection.detail_row = None
    monkeypatch.setattr(review, "set_operator_tenant_context", lambda *_args, **_kwargs: None)

    with pytest.raises(review.GovernanceTensionReviewNotFound):
        review.get_location_governance_tension(
            OPERATOR_ID,
            LOCATION_ID,
            TENSION_ID,
            connection_factory=lambda: connection,
        )
    assert not any("governance_tension_event" in operation[1] for operation in connection.operations)
    assert connection.rolled_back and connection.closed


def test_detail_does_not_expose_unsubmitted_draft(monkeypatch):
    connection = _Connection()
    connection.detail_row = (*connection.detail_row[:6], "draft", *connection.detail_row[7:])
    monkeypatch.setattr(review, "set_operator_tenant_context", lambda *_args, **_kwargs: None)

    with pytest.raises(review.GovernanceTensionReviewNotFound):
        review.get_location_governance_tension(
            OPERATOR_ID,
            LOCATION_ID,
            TENSION_ID,
            connection_factory=lambda: connection,
        )
    assert not any("governance_tension_event" in operation[1] for operation in connection.operations)


def test_review_routes_apply_exact_read_scope_and_no_store(monkeypatch):
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
            return object()

        def release_mutation(self, _reservation):
            return None

    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="d" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def csrf_valid(self, *_args):
            return True

        def has_scope(self, operator_id, resource, action, location_id):
            return (operator_id, resource, action, location_id) == (
                OPERATOR_ID, "governance_tension", "read", LOCATION_ID
            )

        def list_scopes(self, _operator_id):
            return []

        def revoke_session(self, _session_id):
            return None

    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    queue = {"location_id": LOCATION_ID, "items": [], "next_cursor": None}
    detail = {"location_id": LOCATION_ID, "tension": {"id": TENSION_ID}, "events": []}
    with (
        patch(
            "services.gateway.governance_tension_review.list_location_governance_tensions",
            return_value=queue,
        ) as queue_call,
        patch(
            "services.gateway.governance_tension_review.get_location_governance_tension",
            return_value=detail,
        ) as detail_call,
    ):
        with TestClient(create_app(), base_url="https://operator.example") as client:
            client.cookies.set("kokonut_operator_session", "synthetic-session", path="/operator")
            queue_response = client.get(
                f"/operator/api/governance/{LOCATION_ID}/tensions?status=submitted&limit=10"
            )
            detail_response = client.get(
                f"/operator/api/governance/{LOCATION_ID}/tensions/{TENSION_ID}"
            )

    assert queue_response.status_code == 200
    assert queue_response.json() == queue
    assert queue_response.headers["cache-control"] == "no-store"
    assert detail_response.status_code == 200
    assert detail_response.json() == detail
    assert detail_response.headers["cache-control"] == "no-store"
    queue_call.assert_called_once_with(
        OPERATOR_ID, LOCATION_ID, status="submitted", limit=10, cursor=None
    )
    detail_call.assert_called_once_with(OPERATOR_ID, LOCATION_ID, TENSION_ID)


def test_queue_route_publishes_strict_success_contract(monkeypatch):
    class InMemoryAudit:
        def __init__(self):
            pass

        def replay_pending(self, _limit=100):
            return 0

        def log(self, **_event):
            return None

        def capture_status(self):
            return "ok"

    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="e" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, *_scope):
            return True

        def list_scopes(self, _operator_id):
            return []

        def revoke_session(self, _session_id):
            return None

    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    with TestClient(create_app(), base_url="https://operator.example") as client:
        schema = client.app.openapi()

    operation = schema["paths"]["/operator/api/governance/{location_id}/tensions"]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/GovernanceTensionReviewQueueResponse"
    }
    response_schema = schema["components"]["schemas"]["GovernanceTensionReviewQueueResponse"]
    assert response_schema["additionalProperties"] is False
    assert set(response_schema["required"]) == {"location_id", "items", "next_cursor"}


def test_queue_route_sanitizes_invalid_success_projection(monkeypatch):
    class InMemoryAudit:
        def __init__(self):
            pass

        def replay_pending(self, _limit=100):
            return 0

        def log(self, **_event):
            return None

        def capture_status(self):
            return "ok"

    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="f" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, *_scope):
            return True

        def list_scopes(self, _operator_id):
            return []

        def revoke_session(self, _session_id):
            return None

    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    invalid = {
        "location_id": LOCATION_ID,
        "items": [],
        "next_cursor": None,
        "private_internal_field": "must not escape",
    }
    with patch(
        "services.gateway.governance_tension_review.list_location_governance_tensions",
        return_value=invalid,
    ):
        with TestClient(create_app(), base_url="https://operator.example") as client:
            client.cookies.set("kokonut_operator_session", "synthetic-session", path="/operator")
            response = client.get(f"/operator/api/governance/{LOCATION_ID}/tensions")

    assert response.status_code == 500
    assert response.json() == {"error": "Governance tension review unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "must not escape" not in response.text


def test_review_route_policy_matches_only_exact_location_reads():
    queue_path = f"/operator/api/governance/{LOCATION_ID}/tensions"
    detail_path = f"{queue_path}/{TENSION_ID}"
    expected = {
        "resource": "governance_tension",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", queue_path, enabled=True) == expected
    assert auth_route_policy("GET", detail_path, enabled=True) == expected
    assert auth_route_policy("POST", queue_path, enabled=True)["action"] == "create"
    assert auth_route_policy("GET", detail_path + "/events", enabled=True) is None
    assert auth_route_policy("GET", queue_path, enabled=False) is None
