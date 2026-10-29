"""Tenant-scoped independent human review for governance role nominations."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import governance_assignment_review as review
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
ROLE_ID = str(uuid4())
ASSIGNMENT_ID = str(uuid4())
REQUEST_ID = str(uuid4())
DECISION_ID = str(uuid4())
REVIEWER_PARTY_ID = str(uuid4())
CREATED_AT = datetime(2026, 10, 18, tzinfo=timezone.utc)


def _review_item(assignment_id, created_at):
    return {
        "assignment_id": assignment_id,
        "request_id": REQUEST_ID,
        "role_id": ROLE_ID,
        "role_key": "field_coordinator",
        "role_name": "Field Coordinator",
        "nominee_party_id": REVIEWER_PARTY_ID,
        "nominee_name": "Nominee",
        "nominee_status": "active",
        "submitted_by_party_id": str(uuid4()),
        "submitted_by_name": "Submitter",
        "assignment_type": "primary",
        "mandate": None,
        "role_status": "active",
        "created_at": created_at,
    }


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))
        if "list_governance_role_assignment_review_queue" in query:
            self.description = [SimpleNamespace(name=name) for name in (
                "assignment_id", "request_id", "role_id", "role_key", "role_name",
                "nominee_party_id", "nominee_name", "nominee_status",
                "submitted_by_party_id", "submitted_by_name", "assignment_type",
                "mandate", "role_status", "created_at",
            )]
        elif "decide_governance_role_assignment" in query:
            self.description = [SimpleNamespace(name=name) for name in (
                "decision_id", "assignment_id", "decision", "assignment_status",
                "reviewer_party_id", "created_at",
            )]

    def fetchall(self):
        return self.connection.rows

    def fetchone(self):
        return self.connection.row


class _Connection:
    def __init__(self, *, rows=None, row=None):
        self.operations = []
        self.rows = rows or []
        self.row = row
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


def _payload(**overrides):
    value = {"decision_request_id": REQUEST_ID, "reason": "Reviewed the active mandate"}
    value.update(overrides)
    return value


def test_review_queue_sets_signed_context_before_query_and_cleans_up():
    conn = _Connection(rows=[(
        ASSIGNMENT_ID, REQUEST_ID, ROLE_ID, "field_coordinator", "Field Coordinator",
        str(uuid4()), "Nominee", "active", str(uuid4()), "Submitter", "primary",
        None, "active", CREATED_AT,
    )])
    context_events = []

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "governance_roles",
            "action": "review",
        }
        context_events.append("context")

    with patch.object(review, "set_operator_tenant_context", set_context):
        result = review.list_governance_assignment_reviews(
            OPERATOR_ID, LOCATION_ID, connection_factory=lambda: conn
        )

    assert context_events == ["context"]
    assert "SET TRANSACTION READ ONLY" in conn.operations[0][0]
    assert conn.operations[1][0] == "SET LOCAL statement_timeout = '8s'"
    assert "list_governance_role_assignment_review_queue" in conn.operations[3][0]
    assert conn.operations[3][1] == (LOCATION_ID, 51, None, None)
    assert result["location_id"] == LOCATION_ID
    assert result["items"][0]["nominee_name"] == "Nominee"
    assert conn.rolled_back and conn.closed and not conn.committed


@pytest.mark.parametrize(
    ("operator_id", "location_id", "limit", "cursor_created_at", "cursor_assignment_id"),
    [
        ("bad", LOCATION_ID, 50, None, None),
        (OPERATOR_ID, LOCATION_ID, 0, None, None),
        (OPERATOR_ID, LOCATION_ID, 50, None, str(uuid4())),
    ],
)
def test_invalid_review_query_fails_before_database(
    operator_id, location_id, limit, cursor_created_at, cursor_assignment_id
):
    with pytest.raises(review.GovernanceAssignmentReviewInvalid):
        review.list_governance_assignment_reviews(
            operator_id,
            location_id,
            limit=limit,
            cursor_created_at=cursor_created_at,
            cursor_assignment_id=cursor_assignment_id,
            connection_factory=lambda: pytest.fail("database must not open"),
        )


def test_decision_sets_action_context_before_function_and_commits():
    conn = _Connection(row=(DECISION_ID, ASSIGNMENT_ID, "approve", "active", REVIEWER_PARTY_ID, CREATED_AT))
    events = []

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "governance_roles",
            "action": "approve",
        }
        events.append("context")

    class RecordingCursor(_Cursor):
        def execute(self, query, params=None):
            super().execute(query, params)
            if "decide_governance_role_assignment" in query:
                events.append("decision")

    conn.cursor = lambda: RecordingCursor(conn)
    with patch.object(review, "set_operator_tenant_context", set_context):
        result = review.decide_governance_assignment(
            OPERATOR_ID,
            LOCATION_ID,
            ROLE_ID,
            ASSIGNMENT_ID,
            "approve",
            _payload(),
            connection_factory=lambda: conn,
        )

    assert events == ["context", "decision"]
    assert conn.operations[-1][1] == (
        LOCATION_ID, ROLE_ID, ASSIGNMENT_ID, REQUEST_ID, "approve", "Reviewed the active mandate"
    )
    assert result == {
        "decision_id": DECISION_ID,
        "assignment_id": ASSIGNMENT_ID,
        "decision": "approve",
        "assignment_status": "active",
        "reviewer_party_id": REVIEWER_PARTY_ID,
        "created_at": CREATED_AT,
    }
    assert conn.committed and not conn.rolled_back and conn.closed


@pytest.mark.parametrize(
    ("decision", "payload", "message"),
    [
        ("approve; DELETE", _payload(), "not supported"),
        ([], _payload(), "not supported"),
        ("approve", {**_payload(), "extra": 1}, "must contain"),
        ("reject", _payload(reason="  "), "reason must contain"),
    ],
)
def test_invalid_decision_fails_before_opening_database(decision, payload, message):
    with pytest.raises(review.GovernanceAssignmentReviewInvalid, match=message):
        review.decide_governance_assignment(
            OPERATOR_ID,
            LOCATION_ID,
            ROLE_ID,
            ASSIGNMENT_ID,
            decision,
            payload,
            connection_factory=lambda: pytest.fail("database must not open"),
        )


def test_context_denial_rolls_back_decision_without_calling_function():
    conn = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(review, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            review.decide_governance_assignment(
                OPERATOR_ID, LOCATION_ID, ROLE_ID, ASSIGNMENT_ID,
                "reject", _payload(), connection_factory=lambda: conn,
            )

    assert not any("decide_governance_role_assignment" in query for query, _ in conn.operations)
    assert conn.rolled_back and conn.closed and not conn.committed


def test_route_policies_use_exact_review_and_decision_actions():
    queue = f"/operator/api/governance/{LOCATION_ID}/assignment-review-queue"
    approve = f"/operator/api/governance/{LOCATION_ID}/roles/{ROLE_ID}/assignments/{ASSIGNMENT_ID}/approve"
    reject = f"/operator/api/governance/{LOCATION_ID}/roles/{ROLE_ID}/assignments/{ASSIGNMENT_ID}/reject"
    assert auth_route_policy("GET", queue, enabled=True)["action"] == "review"
    assert auth_route_policy("POST", approve, enabled=True)["action"] == "approve"
    assert auth_route_policy("POST", reject, enabled=True)["action"] == "reject"
    assert auth_route_policy("POST", queue, enabled=True) is None
    assert auth_route_policy("GET", approve, enabled=True) is None
    assert auth_route_policy("POST", approve, enabled=False) is None


class _InMemoryAudit:
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


def _client(monkeypatch, allowed_actions):
    monkeypatch.setattr("services.gateway.audit.GatewayAudit", _InMemoryAudit)
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="f" * 64,
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
                OPERATOR_ID, "governance_roles", action, LOCATION_ID
            ) and action in allowed_actions

        def list_scopes(self, _operator_id):
            return []

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    client = TestClient(create_app(), base_url="https://operator.example")
    client.cookies.set("kokonut_operator_session", "synthetic-session", path="/operator")
    client.cookies.set("kokonut_operator_csrf", "synthetic-csrf", path="/operator")
    return client


def test_http_review_and_decision_routes_require_scopes_csrf_and_no_store(monkeypatch):
    queue_result = {"location_id": LOCATION_ID, "items": [], "next_cursor": None}
    decision_result = {
        "decision_id": DECISION_ID,
        "assignment_id": ASSIGNMENT_ID,
        "decision": "approve",
        "assignment_status": "active",
    }
    with patch(
        "services.gateway.governance_assignment_review.list_governance_assignment_reviews",
        return_value=queue_result,
    ) as list_call, patch(
        "services.gateway.governance_assignment_review.decide_governance_assignment",
        return_value=decision_result,
    ) as decide_call:
        with _client(monkeypatch, {"review", "approve"}) as client:
            response = client.get(
                f"/operator/api/governance/{LOCATION_ID}/assignment-review-queue"
            )
            decision = client.post(
                f"/operator/api/governance/{LOCATION_ID}/roles/{ROLE_ID}/assignments/{ASSIGNMENT_ID}/approve",
                json=_payload(),
                headers={"x-csrf-token": "synthetic-csrf"},
            )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert response.json() == queue_result
    assert decision.status_code == 200
    assert decision.headers["cache-control"] == "no-store"
    assert decision.json() == decision_result
    list_call.assert_called_once()
    decide_call.assert_called_once_with(
        OPERATOR_ID, LOCATION_ID, ROLE_ID, ASSIGNMENT_ID, "approve", _payload()
    )


def test_http_review_route_denies_missing_grant_before_service(monkeypatch):
    with patch(
        "services.gateway.governance_assignment_review.list_governance_assignment_reviews",
        side_effect=AssertionError("missing review grant must not reach the service"),
    ):
        with _client(monkeypatch, set()) as client:
            response = client.get(
                f"/operator/api/governance/{LOCATION_ID}/assignment-review-queue"
            )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_http_review_queue_validates_exact_location_bound_page_and_cursor(monkeypatch):
    item = _review_item(ASSIGNMENT_ID, "2026-10-18T00:00:00+00:00")
    queue_result = {
        "location_id": LOCATION_ID,
        "items": [item],
        "next_cursor": {"created_at": item["created_at"], "assignment_id": ASSIGNMENT_ID},
    }
    with patch(
        "services.gateway.governance_assignment_review.list_governance_assignment_reviews",
        return_value=queue_result,
    ):
        with _client(monkeypatch, {"review"}) as client:
            response = client.get(
                f"/operator/api/governance/{LOCATION_ID}/assignment-review-queue?limit=1"
            )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["location_id"] == LOCATION_ID
    assert response.json()["items"] == [{
        **item,
        "created_at": "2026-10-18T00:00:00Z",
    }]
    assert response.json()["next_cursor"]["assignment_id"] == ASSIGNMENT_ID


@pytest.mark.parametrize(
    "result",
    [
        {"location_id": str(uuid4()), "items": [], "next_cursor": None},
        {"location_id": LOCATION_ID, "items": [{"unexpected": True}], "next_cursor": None},
        {
            "location_id": LOCATION_ID,
            "items": [],
            "next_cursor": {"created_at": CREATED_AT.isoformat(), "assignment_id": ASSIGNMENT_ID},
        },
    ],
)
def test_http_review_queue_rejects_malformed_service_page_no_store(monkeypatch, result):
    with patch(
        "services.gateway.governance_assignment_review.list_governance_assignment_reviews",
        return_value=result,
    ):
        with _client(monkeypatch, {"review"}) as client:
            response = client.get(
                f"/operator/api/governance/{LOCATION_ID}/assignment-review-queue"
            )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Governance assignment review queue unavailable"}


@pytest.mark.parametrize(
    ("items", "query"),
    [
        (
            [
                _review_item(ASSIGNMENT_ID, "2026-10-18T00:00:00+00:00"),
                _review_item(str(uuid4()), "2026-10-19T00:00:00+00:00"),
            ],
            "limit=2",
        ),
        (
            [_review_item(ASSIGNMENT_ID, "2026-10-18T00:00:00+00:00")],
            f"limit=1&cursor_created_at=2026-10-18T00%3A00%3A00%2B00%3A00&cursor_assignment_id={ASSIGNMENT_ID}",
        ),
        (
            [
                _review_item(ASSIGNMENT_ID, "2026-10-18T00:00:00+00:00"),
                _review_item(str(uuid4()), "2026-10-17T00:00:00+00:00"),
            ],
            "limit=1",
        ),
    ],
)
def test_http_review_queue_rejects_order_cursor_and_page_bound_violations(monkeypatch, items, query):
    result = {"location_id": LOCATION_ID, "items": items, "next_cursor": None}
    with patch(
        "services.gateway.governance_assignment_review.list_governance_assignment_reviews",
        return_value=result,
    ):
        with _client(monkeypatch, {"review"}) as client:
            response = client.get(
                f"/operator/api/governance/{LOCATION_ID}/assignment-review-queue?{query}"
            )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Governance assignment review queue unavailable"}

