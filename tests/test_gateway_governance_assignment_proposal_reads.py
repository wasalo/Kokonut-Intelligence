"""Bounded, own-operator readback for governance role nominations."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import governance_assignment_proposal_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
ASSIGNMENT_ID = str(uuid4())
ROLE_ID = str(uuid4())
REQUEST_ID = str(uuid4())
CREATED_AT = datetime(2026, 10, 18, tzinfo=timezone.utc)


class _Cursor:
    description = [
        SimpleNamespace(name="request_id"),
        SimpleNamespace(name="assignment_id"),
        SimpleNamespace(name="role_id"),
        SimpleNamespace(name="role_key"),
        SimpleNamespace(name="role_name"),
        SimpleNamespace(name="assignment_type"),
        SimpleNamespace(name="status"),
        SimpleNamespace(name="created_at"),
    ]

    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))

    def fetchall(self):
        return self.connection.rows


class _Connection:
    def __init__(self, rows):
        self.rows = rows
        self.operations = []
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _row(request_id=REQUEST_ID, assignment_id=ASSIGNMENT_ID, created_at=CREATED_AT):
    return (
        request_id,
        assignment_id,
        ROLE_ID,
        "field_coordinator",
        "Field Coordinator",
        "primary",
        "proposed",
        created_at,
    )


def test_readback_sets_signed_context_and_returns_only_bounded_status_projection():
    conn = _Connection([_row(), _row(str(uuid4()), str(uuid4()), CREATED_AT.replace(day=17))])
    context = []

    def set_context(connection, **kwargs):
        assert connection is conn
        context.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_own_governance_assignment_proposals(
            OPERATOR_ID,
            LOCATION_ID,
            limit="1",
            connection_factory=lambda: conn,
        )

    assert context == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_roles",
        "action": "read",
    }]
    assert [operation[0] for operation in conn.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert conn.operations[3][1] == (LOCATION_ID, 2, None, None)
    assert result["items"] == [{
        "request_id": REQUEST_ID,
        "assignment_id": ASSIGNMENT_ID,
        "role_id": ROLE_ID,
        "role_key": "field_coordinator",
        "role_name": "Field Coordinator",
        "assignment_type": "primary",
        "status": "proposed",
        "created_at": CREATED_AT,
    }]
    assert result["next_cursor"] == {
        "created_at": CREATED_AT.isoformat(),
        "assignment_id": ASSIGNMENT_ID,
    }
    assert "party_id" not in result["items"][0]
    assert conn.rolled_back and conn.closed


def test_cursor_is_timezone_aware_and_both_cursor_parts_are_required():
    for kwargs, message in (
        ({"cursor_created_at": "2026-10-18T00:00:00"}, "timezone"),
        ({"cursor_assignment_id": ASSIGNMENT_ID}, "provided together"),
        ({"cursor_created_at": CREATED_AT}, "provided together"),
    ):
        with pytest.raises(reads.GovernanceAssignmentProposalReadInvalid, match=message):
            reads.list_own_governance_assignment_proposals(
                OPERATOR_ID,
                LOCATION_ID,
                connection_factory=lambda: pytest.fail("invalid cursor must fail before DB"),
                **kwargs,
            )


@pytest.mark.parametrize("limit", ["0", "101", "many", True])
def test_invalid_limit_fails_before_database_access(limit):
    with pytest.raises(reads.GovernanceAssignmentProposalReadInvalid):
        reads.list_own_governance_assignment_proposals(
            OPERATOR_ID,
            LOCATION_ID,
            limit=limit,
            connection_factory=lambda: pytest.fail("invalid limit must fail before DB"),
        )


def test_tenant_denial_rolls_back_and_closes_read_only_transaction():
    conn = _Connection([])

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_own_governance_assignment_proposals(
                OPERATOR_ID,
                LOCATION_ID,
                connection_factory=lambda: conn,
            )

    assert not any("list_my_governance_role_assignment_proposals" in query for query, _ in conn.operations)
    assert conn.rolled_back and conn.closed


def test_route_policy_is_exact_location_read_only_scope():
    path = f"/operator/api/governance/{LOCATION_ID}/assignment-proposals"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "governance_roles",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_http_readback_requires_exact_scope_and_returns_no_store(monkeypatch):
    class InMemoryAudit:
        def replay_pending(self, _limit=100):
            return 0

        def log(self, **_event):
            return None

        def capture_status(self):
            return "ok"

    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="f" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, operator_id, resource, action, location_id):
            return (operator_id, resource, action, location_id) == (
                OPERATOR_ID, "governance_roles", "read", LOCATION_ID
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    result = {"location_id": LOCATION_ID, "items": [], "next_cursor": None}
    with patch(
        "services.gateway.governance_assignment_proposal_reads.list_own_governance_assignment_proposals",
        return_value=result,
    ) as list_call:
        with TestClient(create_app(), base_url="https://operator.example") as client:
            client.cookies.set("kokonut_operator_session", "synthetic-session", path="/operator")
            response = client.get(f"/operator/api/governance/{LOCATION_ID}/assignment-proposals")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == result
    list_call.assert_called_once_with(
        OPERATOR_ID,
        LOCATION_ID,
        limit=50,
        cursor_created_at=None,
        cursor_assignment_id=None,
    )


def _valid_response_item(*, assignment_id=ASSIGNMENT_ID, created_at=CREATED_AT):
    return {
        "request_id": REQUEST_ID,
        "assignment_id": assignment_id,
        "role_id": ROLE_ID,
        "role_key": "field_coordinator",
        "role_name": "Field Coordinator",
        "assignment_type": "primary",
        "status": "proposed",
        "created_at": created_at.isoformat(),
    }


def _operator_client(monkeypatch):
    class InMemoryAudit:
        def replay_pending(self, _limit=100):
            return 0

        def log(self, **_event):
            return None

        def capture_status(self):
            return "ok"

    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="f" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, operator_id, resource, action, location_id):
            return (operator_id, resource, action, location_id) == (
                OPERATOR_ID, "governance_roles", "read", LOCATION_ID
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    client = TestClient(create_app(), base_url="https://operator.example")
    client.cookies.set("kokonut_operator_session", "synthetic-session", path="/operator")
    return client


def test_http_assignment_proposal_page_enforces_exact_item_and_cursor_contract(monkeypatch):
    older_id = str(uuid4())
    older_item = _valid_response_item(
        assignment_id=older_id,
        created_at=CREATED_AT.replace(day=17),
    )
    result = {
        "location_id": LOCATION_ID,
        "items": [older_item],
        "next_cursor": {"created_at": older_item["created_at"], "assignment_id": older_id},
    }
    cursor_timestamp = "2026-10-19T00:00:00+00:00"
    cursor_assignment = str(uuid4())

    with patch(
        "services.gateway.governance_assignment_proposal_reads.list_own_governance_assignment_proposals",
        return_value=result,
    ) as list_call, _operator_client(monkeypatch) as client:
        response = client.get(
            f"/operator/api/governance/{LOCATION_ID}/assignment-proposals",
            params={
                "limit": "1",
                "cursor_created_at": cursor_timestamp,
                "cursor_assignment_id": cursor_assignment,
            },
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    normalized_timestamp = "2026-10-17T00:00:00Z"
    assert response.json() == {
        **result,
        "items": [{**older_item, "created_at": normalized_timestamp}],
        "next_cursor": {"created_at": normalized_timestamp, "assignment_id": older_id},
    }
    assert set(response.json()["items"][0]) == set(_valid_response_item())
    list_call.assert_called_once_with(
        OPERATOR_ID,
        LOCATION_ID,
        limit=1,
        cursor_created_at=cursor_timestamp,
        cursor_assignment_id=cursor_assignment,
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda result: result["items"][0].update(unreviewed_person_id=str(uuid4())),
        lambda result: result.update(location_id=str(uuid4())),
        lambda result: result["items"].append(_valid_response_item(assignment_id=str(uuid4()))),
        lambda result: result["items"].append(result["items"][0].copy()),
        lambda result: result["items"][0].update(created_at="not-a-timestamp"),
        lambda result: result["next_cursor"].update(assignment_id=str(uuid4())),
        lambda result: result.update(next_cursor={"created_at": "bad", "assignment_id": str(uuid4())}),
    ],
    ids=["extra-sensitive-field", "wrong-location", "over-limit", "duplicate-item", "bad-item-time", "cursor-mismatch", "bad-cursor"],
)
def test_http_assignment_proposal_rejects_malformed_pages_without_store(monkeypatch, mutate):
    result = {
        "location_id": LOCATION_ID,
        "items": [_valid_response_item()],
        "next_cursor": {
            "created_at": CREATED_AT.isoformat(),
            "assignment_id": ASSIGNMENT_ID,
        },
    }
    mutate(result)

    with patch(
        "services.gateway.governance_assignment_proposal_reads.list_own_governance_assignment_proposals",
        return_value=result,
    ), _operator_client(monkeypatch) as client:
        response = client.get(
            f"/operator/api/governance/{LOCATION_ID}/assignment-proposals",
            params={"limit": "1"},
        )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Governance role proposal readback unavailable"}


@pytest.mark.parametrize(
    "items",
    [
        [_valid_response_item(), _valid_response_item()],
        [
            _valid_response_item(
                assignment_id=str(uuid4()), created_at=CREATED_AT.replace(day=17)
            ),
            _valid_response_item(
                assignment_id=str(uuid4()), created_at=CREATED_AT.replace(day=18)
            ),
        ],
    ],
    ids=["duplicate-assignment", "ascending-order"],
)
def test_http_assignment_proposal_rejects_duplicate_or_unordered_rows(monkeypatch, items):
    result = {
        "location_id": LOCATION_ID,
        "items": items,
        "next_cursor": {
            "created_at": items[-1]["created_at"],
            "assignment_id": items[-1]["assignment_id"],
        },
    }

    with patch(
        "services.gateway.governance_assignment_proposal_reads.list_own_governance_assignment_proposals",
        return_value=result,
    ), _operator_client(monkeypatch) as client:
        response = client.get(
            f"/operator/api/governance/{LOCATION_ID}/assignment-proposals",
            params={"limit": "2"},
        )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Governance role proposal readback unavailable"}
