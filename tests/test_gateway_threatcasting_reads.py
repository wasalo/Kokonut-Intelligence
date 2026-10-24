"""Tests for the location-scoped Kernel threatcasting read surface."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import threatcasting_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
PLAN_ID = str(uuid4())
NARRATIVE_ID = str(uuid4())
THREAT_ID = str(uuid4())
MILESTONE_ID = str(uuid4())
CREATED_AT = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)

LIST_COLUMNS = (
    "id", "plan_name", "future_state_description", "current_gap_analysis",
    "created_at", "updated_at", "narrative_id", "narrative_type",
    "narrative_title", "threat_id", "threat_name", "milestone_count",
    "completed_milestone_count", "blocked_milestone_count",
)
DETAIL_COLUMNS = (
    "id", "location_id", "plan_name", "future_state_description",
    "current_gap_analysis", "created_at", "updated_at", "narrative_id",
    "narrative_type", "narrative_title", "threat_id", "threat_name",
)
MILESTONE_COLUMNS = (
    "id", "milestone_order", "milestone_description", "milestone_target_date",
    "milestone_status", "dependencies", "responsible_party", "resource_requirements",
    "completion_evidence", "created_at", "updated_at",
)


class _Connection:
    def __init__(self, result_sets):
        self.result_sets = result_sets
        self.select_count = 0
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
        self.result_set = ((), ())

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        self.connection.operations.append((normalized, params))
        if normalized.startswith("SELECT"):
            self.result_set = self.connection.result_sets[self.connection.select_count]
            self.connection.select_count += 1
            columns, _rows = self.result_set
            self.description = [SimpleNamespace(name=column) for column in columns]

    def fetchone(self):
        rows = self.result_set[1]
        return rows[0] if rows else None

    def fetchall(self):
        return self.result_set[1]


def _list_result_rows(count=1):
    rows = []
    for index in range(count):
        rows.append((
            PLAN_ID if index == 0 else str(uuid4()),
            "Drought resilience path",
            "A future state with resilient water systems",
            "Current water storage and governance gaps",
            CREATED_AT,
            CREATED_AT,
            NARRATIVE_ID,
            "desirable",
            "Resilient watershed",
            THREAT_ID,
            "Drought",
            2,
            1,
            0,
        ))
    return LIST_COLUMNS, rows


def test_list_is_bounded_signed_location_read_and_advisory_only():
    conn = _Connection([_list_result_rows(count=2)])
    contexts = []

    def set_context(connection, **kwargs):
        assert connection is conn
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_backcast_plans(
            OPERATOR_ID,
            LOCATION_ID,
            limit="1",
            connection_factory=lambda: conn,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "threatcasting",
        "action": "read",
    }]
    assert [query for query, _ in conn.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    select_query, params = conn.operations[-1]
    assert "plan.location_id = %s::uuid" in select_query
    assert params == (LOCATION_ID, None, None, None, 2)
    assert result["advisory_only"] is True
    assert len(result["items"]) == 1
    assert result["next_cursor"] == {
        "created_at": CREATED_AT.isoformat(),
        "plan_id": PLAN_ID,
    }
    assert conn.rolled_back and conn.closed


@pytest.mark.parametrize("kwargs", [
    {"limit": "0"},
    {"limit": "101"},
    {"limit": "many"},
    {"limit": True},
    {"cursor_plan_id": PLAN_ID},
    {"cursor_created_at": "2026-10-19T12:00:00"},
])
def test_invalid_page_and_cursor_inputs_fail_before_database_access(kwargs):
    with pytest.raises(reads.ThreatcastingReadInvalid):
        reads.list_location_backcast_plans(
            OPERATOR_ID,
            LOCATION_ID,
            connection_factory=lambda: pytest.fail("invalid input must fail before DB access"),
            **kwargs,
        )


def test_tenant_denial_does_not_read_and_cleans_up_transaction():
    conn = _Connection([_list_result_rows(count=0)])

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_backcast_plans(
                OPERATOR_ID,
                LOCATION_ID,
                connection_factory=lambda: conn,
            )

    assert conn.select_count == 0
    assert conn.rolled_back and conn.closed


def test_plan_detail_returns_only_scoped_plan_and_milestone_evidence():
    plan_row = (
        PLAN_ID, LOCATION_ID, "Drought resilience path",
        "A future state with resilient water systems",
        "Current water storage and governance gaps",
        CREATED_AT, CREATED_AT,
        NARRATIVE_ID, "desirable", "Resilient watershed", THREAT_ID, "Drought",
    )
    milestone_row = (
        MILESTONE_ID, 1, "Map community water sources", None, "completed", [],
        "Water committee", "Mapping time", "Survey notes reviewed",
        CREATED_AT, CREATED_AT,
    )
    conn = _Connection([(DETAIL_COLUMNS, [plan_row]), (MILESTONE_COLUMNS, [milestone_row])])
    contexts = []

    with patch.object(
        reads,
        "set_operator_tenant_context",
        lambda connection, **kwargs: contexts.append((connection, kwargs)),
    ):
        result = reads.get_location_backcast_plan(
            OPERATOR_ID,
            LOCATION_ID,
            PLAN_ID,
            connection_factory=lambda: conn,
        )

    assert contexts == [(conn, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "threatcasting",
        "action": "read",
    })]
    first_select, first_params = conn.operations[-2]
    second_select, second_params = conn.operations[-1]
    assert "plan.id = %s::uuid" in first_select
    assert "plan.location_id = %s::uuid" in first_select
    assert first_params == (PLAN_ID, LOCATION_ID)
    assert "plan.location_id = %s::uuid" in second_select
    assert "milestone.plan_id = %s::uuid" in second_select
    assert second_params == (LOCATION_ID, PLAN_ID, 501)
    assert result["advisory_only"] is True
    assert result["milestones"][0]["completion_evidence"] == "Survey notes reviewed"
    assert conn.rolled_back and conn.closed


def test_plan_detail_rejects_response_over_one_mib_and_closes_connection():
    plan_row = (
        PLAN_ID, LOCATION_ID, "Drought resilience path",
        "A future state with resilient water systems",
        "Current water storage and governance gaps",
        CREATED_AT, CREATED_AT,
        NARRATIVE_ID, "desirable", "Resilient watershed", THREAT_ID, "Drought",
    )
    oversized_milestone = (
        MILESTONE_ID, 1, "x" * reads._MAX_DETAIL_RESPONSE_BYTES, None, "completed", [],
        None, None, None, CREATED_AT, CREATED_AT,
    )
    conn = _Connection([(DETAIL_COLUMNS, [plan_row]), (MILESTONE_COLUMNS, [oversized_milestone])])

    with patch.object(reads, "set_operator_tenant_context", lambda *_args, **_kwargs: None):
        with pytest.raises(reads.ThreatcastingReadTooLarge):
            reads.get_location_backcast_plan(
                OPERATOR_ID,
                LOCATION_ID,
                PLAN_ID,
                connection_factory=lambda: conn,
            )

    assert conn.rolled_back and conn.closed


def test_detail_missing_from_location_returns_not_found_shape():
    conn = _Connection([(DETAIL_COLUMNS, [])])
    with patch.object(reads, "set_operator_tenant_context", lambda *_args, **_kwargs: None):
        result = reads.get_location_backcast_plan(
            OPERATOR_ID,
            LOCATION_ID,
            PLAN_ID,
            connection_factory=lambda: conn,
        )
    assert result is None
    assert conn.select_count == 1
    assert conn.rolled_back and conn.closed


def test_route_policy_is_exact_location_read_and_has_no_write_policy():
    list_path = f"/operator/api/threatcasting/{LOCATION_ID}/backcast-plans"
    detail_path = f"{list_path}/{PLAN_ID}"
    expected = {
        "resource": "threatcasting",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", list_path, enabled=True) == expected
    assert auth_route_policy("GET", detail_path, enabled=True) == expected
    assert auth_route_policy("POST", list_path, enabled=True) is None
    assert auth_route_policy("PATCH", detail_path, enabled=True) is None
    assert auth_route_policy("GET", list_path + "/extra", enabled=True) is None


def test_http_read_returns_no_store_and_advisory_response(monkeypatch):
    from services.gateway.threatcasting_routes import register_threatcasting_routes

    provider = object()
    router_app = FastAPI()
    from fastapi import APIRouter

    monkeypatch.setattr(
        "services.gateway.threatcasting_reads.list_location_backcast_plans",
        lambda *_args, **_kwargs: {"location_id": LOCATION_ID, "advisory_only": True, "items": []},
    )

    def oversized_detail(*_args, **_kwargs):
        raise reads.ThreatcastingReadTooLarge("oversized")

    monkeypatch.setattr(
        "services.gateway.threatcasting_reads.get_location_backcast_plan",
        oversized_detail,
    )

    router = APIRouter()
    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_threatcasting_routes(router, provider, run_in_threadpool, SimpleNamespace(Error=Exception))
    router_app.include_router(router)

    @router_app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(router_app) as client:
        response = client.get(f"/operator/api/threatcasting/{LOCATION_ID}/backcast-plans")
        detail_response = client.get(
            f"/operator/api/threatcasting/{LOCATION_ID}/backcast-plans/{PLAN_ID}"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["advisory_only"] is True
    assert detail_response.status_code == 413
    assert detail_response.headers["cache-control"] == "no-store"
