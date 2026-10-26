"""Focused tests for the location-scoped Kernel identity review path."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.gateway import stakeholder_identity as identity
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
OTHER_OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
PROFILE_ID = str(uuid4())
PARTY_ID = str(uuid4())
CASE_ID = str(uuid4())
REQUEST_ID = str(uuid4())
CREATED_AT = datetime(2026, 10, 19, 10, 0, tzinfo=timezone.utc)


class _Connection:
    def __init__(self, rows=()):
        self.rows = list(rows)
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


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = None
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        self.connection.operations.append((normalized, params))
        if "propose_location_party_identity" in normalized:
            columns = ("case_id", "case_status", "created_at")
            self.result = (columns, (CASE_ID, "proposed", CREATED_AT))
        elif "list_location_party_identity_cases" in normalized:
            self.result = self.connection.rows.pop(0)
        elif "decide_location_party_identity" in normalized:
            columns = ("case_id", "case_status", "reviewer_operator_id", "created_at")
            self.result = (columns, (CASE_ID, "approved", OTHER_OPERATOR_ID, CREATED_AT))
        else:
            self.result = ((), None)
        if self.result is not None:
            columns = self.result[0]
            self.description = [SimpleNamespace(name=column) for column in columns]

    def fetchone(self):
        return self.result[1] if self.result else None

    def fetchall(self):
        return self.result[1] if self.result else []


def test_proposal_sets_signed_create_scope_before_bounded_function_and_commits():
    conn = _Connection()
    contexts = []

    def set_context(connection, **kwargs):
        assert connection is conn
        contexts.append(kwargs)

    with patch.object(identity, "set_operator_tenant_context", set_context):
        result = identity.propose_location_party_identity(
            OPERATOR_ID,
            LOCATION_ID,
            PROFILE_ID,
            PARTY_ID,
            REQUEST_ID,
            "verified_document",
            "document_review",
            "0.85",
            connection_factory=lambda: conn,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "stakeholder_identity",
        "action": "create",
    }]
    call_index = next(
        index for index, (query, _params) in enumerate(conn.operations)
        if "propose_location_party_identity" in query
    )
    assert call_index > 0
    assert conn.operations[call_index][1][0:4] == (LOCATION_ID, PROFILE_ID, PARTY_ID, REQUEST_ID)
    assert conn.committed and conn.closed
    assert not conn.rolled_back
    assert result["case_status"] == "proposed"


@pytest.mark.parametrize(
    "overrides",
    [
        {"match_method": "unsupported"},
        {"evidence_code": "free_text"},
        {"confidence": 1.1},
        {"confidence": 0.00001},
        {"confidence": True},
        {"match_method": []},
    ],
)
def test_invalid_proposal_fails_before_opening_database(overrides):
    values = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "source_profile_id": PROFILE_ID,
        "candidate_party_id": PARTY_ID,
        "request_id": REQUEST_ID,
        "match_method": "manual",
        "evidence_code": "participant_confirmation",
        "confidence": 0.7,
    }
    values.update(overrides)
    with pytest.raises(identity.StakeholderIdentityInvalid):
        identity.propose_location_party_identity(
            **values,
            connection_factory=lambda: pytest.fail("invalid input opened a database connection"),
        )


def test_review_queue_is_bounded_location_context_and_withholds_raw_source_id():
    columns = (
        "case_id", "candidate_party_id", "candidate_name", "source_label",
        "match_method", "evidence_code", "confidence", "created_at",
    )
    rows = [
        (str(uuid4()), PARTY_ID, "Canonical Name", "Alex Farmer", "manual", "document_review", 0.8, CREATED_AT),
        (str(uuid4()), PARTY_ID, "Canonical Name", "Sam Farmer", "manual", "community_review", 0.7, CREATED_AT),
    ]
    conn = _Connection([(columns, rows)])
    contexts = []

    def set_context(connection, **kwargs):
        assert connection is conn
        contexts.append(kwargs)

    with patch.object(identity, "set_operator_tenant_context", set_context):
        result = identity.list_location_party_identity_cases(
            OTHER_OPERATOR_ID,
            LOCATION_ID,
            limit=1,
            connection_factory=lambda: conn,
        )

    assert contexts == [{
        "operator_id": OTHER_OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "stakeholder_identity",
        "action": "review",
    }]
    query = next(query for query, _params in conn.operations if "list_location_party_identity_cases" in query)
    assert "SET TRANSACTION READ ONLY" in conn.operations[0][0]
    assert "list_location_party_identity_cases" in query
    assert len(result["items"]) == 1
    assert result["items"][0]["source_label"] == "Alex Farmer"
    assert "source_profile_id" not in result["items"][0]
    assert result["next_cursor"]["case_id"] == result["items"][0]["case_id"]
    assert conn.rolled_back and conn.closed


def test_review_queue_invalid_cursor_fails_before_database_access():
    with pytest.raises(identity.StakeholderIdentityInvalid, match="provided together"):
        identity.list_location_party_identity_cases(
            OPERATOR_ID,
            LOCATION_ID,
            cursor_case_id=CASE_ID,
            connection_factory=lambda: pytest.fail("invalid cursor opened a database connection"),
        )


def test_decision_requires_signed_review_scope_and_commits_one_function_call():
    conn = _Connection()
    contexts = []

    def set_context(connection, **kwargs):
        assert connection is conn
        contexts.append(kwargs)

    with patch.object(identity, "set_operator_tenant_context", set_context):
        result = identity.decide_location_party_identity(
            OTHER_OPERATOR_ID,
            LOCATION_ID,
            CASE_ID,
            REQUEST_ID,
            "approve",
            "match_confirmed",
            connection_factory=lambda: conn,
        )

    assert contexts == [{
        "operator_id": OTHER_OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "stakeholder_identity",
        "action": "review",
    }]
    assert len([query for query, _params in conn.operations if "decide_location_party_identity" in query]) == 1
    assert conn.committed and conn.closed
    assert result["reviewer_operator_id"] == OTHER_OPERATOR_ID


def test_exact_oidc_policy_covers_identity_paths_and_rejects_wrong_methods():
    base = f"/operator/api/stakeholder-identity/{LOCATION_ID}/cases"
    assert auth_route_policy("GET", base, enabled=True)["action"] == "review"
    assert auth_route_policy("POST", base, enabled=True)["action"] == "create"
    decision_path = f"{base}/{CASE_ID}/decision"
    policy = auth_route_policy("POST", decision_path, enabled=True)
    assert policy["resource"] == "stakeholder_identity"
    assert policy["action"] == "review"
    assert policy["location_id"] == LOCATION_ID
    assert policy["scope_required"] is True
    assert auth_route_policy("GET", decision_path, enabled=True) is None


def test_http_route_rejects_raw_feedback_fields_before_database_call():
    from services.gateway.stakeholder_identity_routes import register_stakeholder_identity_routes

    router_app = FastAPI()
    from fastapi import APIRouter

    router = APIRouter()
    provider = object()

    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    import psycopg2

    register_stakeholder_identity_routes(router, provider, run_inline, psycopg2)
    router_app.include_router(router)
    operator = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
    async def install_session(request, call_next):
        request.state.operator_session = operator
        return await call_next(request)

    router_app.middleware("http")(install_session)
    with TestClient(router_app) as client, patch.object(
        identity,
        "propose_location_party_identity",
        side_effect=AssertionError("unsupported raw feedback payload reached the service"),
    ):
        response = client.post(
            f"/operator/api/stakeholder-identity/{LOCATION_ID}/cases",
            json={
                "source_profile_id": PROFILE_ID,
                "candidate_party_id": PARTY_ID,
                "request_id": REQUEST_ID,
                "match_method": "manual",
                "evidence_code": "participant_confirmation",
                "confidence": 0.7,
                "raw_feedback": "private participant statement",
            },
        )
    assert response.status_code == 400
