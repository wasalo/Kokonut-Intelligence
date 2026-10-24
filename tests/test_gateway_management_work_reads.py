"""Tests for the location-scoped management workflow summary."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import management_work_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
EVENT_AT = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
COLUMNS = (
    "work_item_count", "open_work_item_count", "draft_count", "assigned_count",
    "in_progress_count", "blocked_count", "done_count", "cancelled_count",
    "high_priority_open_count", "critical_priority_open_count", "overdue_count",
    "sla_breached_count", "pending_claim_count", "accepted_claim_count",
    "open_escalation_count", "resolved_escalation_count", "latest_work_event_at",
)


class _Connection:
    def __init__(self, row):
        self.row = row
        self.operations = []
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


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
        self.connection.operations.append((normalized, params))
        if normalized.startswith("SELECT"):
            self.description = [SimpleNamespace(name=column) for column in COLUMNS]

    def fetchone(self):
        return self.connection.row


def _row():
    return (6, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, EVENT_AT)


def test_summary_sets_exact_context_and_reads_one_bounded_projection_row():
    connection = _Connection(_row())
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.location_management_work_summary(
            OPERATOR_ID,
            LOCATION_ID,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "management_workflow",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert connection.operations[-1] == (
        "SELECT * FROM kokonut_security.location_management_work_summary(%s::uuid)",
        (LOCATION_ID,),
    )
    assert result == {"location_id": LOCATION_ID, **dict(zip(COLUMNS, _row()))}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("operator_id,location_id", [
    ("not-a-uuid", LOCATION_ID),
    (OPERATOR_ID, "not-a-uuid"),
])
def test_invalid_identity_fails_before_database_access(operator_id, location_id):
    with pytest.raises(reads.ManagementWorkReadInvalid):
        reads.location_management_work_summary(
            operator_id,
            location_id,
            connection_factory=lambda: pytest.fail("invalid identity must fail before DB access"),
        )


def test_tenant_denial_rolls_back_and_never_calls_summary_function():
    connection = _Connection(_row())

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.location_management_work_summary(
                OPERATOR_ID,
                LOCATION_ID,
                connection_factory=lambda: connection,
            )

    assert not any("location_management_work_summary" in query for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_projection_contract_excludes_task_content_and_personal_identifiers():
    forbidden = {
        "title", "description", "note", "assignee_id", "assignee_party_id",
        "created_by_id", "actor_id", "claimant_party_id", "decision_reason",
        "estimated_effort_hours", "skill_requirements",
    }
    assert not forbidden.intersection(COLUMNS)
    assert "overdue_count" in COLUMNS
    assert "sla_breached_count" in COLUMNS
    assert "open_escalation_count" in COLUMNS


def test_route_policy_requires_exact_location_management_read_grant():
    path = f"/operator/api/management/{LOCATION_ID}/summary"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "management_workflow",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_http_summary_is_no_store_and_returns_only_projection(monkeypatch):
    from services.gateway.management_work_routes import register_management_work_routes

    monkeypatch.setattr(
        "services.gateway.management_work_reads.location_management_work_summary",
        lambda *_args, **_kwargs: {"location_id": LOCATION_ID, "work_item_count": 2},
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_management_work_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/management/{LOCATION_ID}/summary")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == {"location_id": LOCATION_ID, "work_item_count": 2}
