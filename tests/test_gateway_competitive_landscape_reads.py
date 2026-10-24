"""Tests for location-scoped competitive landscape Kernel summaries."""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import competitive_landscape_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
LANDSCAPE_ID = str(uuid4())
PLAN_ID = str(uuid4())
UPDATED_AT = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
COLUMNS = (
    "landscape_id", "strategy_plan_id", "industry", "geography", "period_start",
    "period_end", "landscape_status", "confidence", "updated_at", "actor_count",
    "high_or_critical_actor_count", "force_observation_count", "average_force_pressure",
    "worsening_force_count", "signal_count", "unreviewed_critical_signal_count",
    "verified_advantage_count", "average_verified_defensibility",
    "verified_advantage_outcome_count", "latest_verified_outcome_period_end",
)


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

    def fetchall(self):
        return self.connection.rows


def _row(landscape_id=LANDSCAPE_ID):
    return (
        landscape_id, PLAN_ID, "Regenerative agriculture", "Dominican Republic",
        date(2026, 1, 1), date(2026, 12, 31), "verified", "moderate", UPDATED_AT,
        4, 1, 5, 61.25, 2, 3, 1, 2, 72.5, 1, date(2026, 9, 30),
    )


def test_summary_read_sets_exact_signed_context_and_uses_bounded_projection():
    connection = _Connection([_row(), _row(str(uuid4()))])
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_competitive_landscape_summaries(
            OPERATOR_ID,
            LOCATION_ID,
            limit="1",
            offset="7",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "competitive_landscape",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    query, params = connection.operations[-1]
    assert "kokonut_security.list_location_competitive_landscape_summaries" in query
    assert params == (LOCATION_ID, 2, 7)
    assert result == {
        "location_id": LOCATION_ID,
        "offset": 7,
        "landscapes": [dict(zip(COLUMNS, _row()))],
        "has_more": True,
        "next_offset": 8,
    }
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("kwargs", [
    {"limit": "0"},
    {"limit": "51"},
    {"limit": "many"},
    {"limit": True},
    {"offset": "-1"},
    {"offset": "10001"},
    {"offset": "1.2"},
])
def test_invalid_page_inputs_fail_before_database_access(kwargs):
    with pytest.raises(reads.CompetitiveLandscapeReadInvalid):
        reads.list_location_competitive_landscape_summaries(
            OPERATOR_ID,
            LOCATION_ID,
            connection_factory=lambda: pytest.fail("invalid input must fail before DB access"),
            **kwargs,
        )


@pytest.mark.parametrize("operator_id,location_id", [
    ("not-a-uuid", LOCATION_ID),
    (OPERATOR_ID, "not-a-uuid"),
])
def test_invalid_identity_fails_before_database_access(operator_id, location_id):
    with pytest.raises(reads.CompetitiveLandscapeReadInvalid):
        reads.list_location_competitive_landscape_summaries(
            operator_id,
            location_id,
            connection_factory=lambda: pytest.fail("invalid identity must fail before DB access"),
        )


def test_tenant_denial_rolls_back_and_never_calls_projection():
    connection = _Connection([])

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_competitive_landscape_summaries(
                OPERATOR_ID,
                LOCATION_ID,
                connection_factory=lambda: connection,
            )

    assert not any(
        "list_location_competitive_landscape_summaries" in query
        for query, _ in connection.operations
    )
    assert connection.rolled_back and connection.closed


def test_projection_allowlist_excludes_actor_identity_evidence_and_outcome_values():
    forbidden = {
        "party_id", "created_by_party_id", "verified_by_party_id", "actor_names",
        "position_summary", "rationale", "evidence", "content", "source_ref",
        "baseline_value", "target_value", "actual_value", "comparator_value",
        "statement", "owner_party_id", "assessed_by_party_id",
    }
    assert not forbidden.intersection(COLUMNS)
    assert "high_or_critical_actor_count" in COLUMNS
    assert "average_force_pressure" in COLUMNS
    assert "verified_advantage_outcome_count" in COLUMNS


def test_route_policy_requires_exact_location_competitive_read_grant():
    path = f"/operator/api/competitive-landscape/{LOCATION_ID}/summaries"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "competitive_landscape",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_http_projection_is_no_store_and_requires_operator_session(monkeypatch):
    from services.gateway.competitive_landscape_routes import (
        register_competitive_landscape_routes,
    )

    monkeypatch.setattr(
        "services.gateway.competitive_landscape_reads.list_location_competitive_landscape_summaries",
        lambda *_args, **_kwargs: {
            "location_id": LOCATION_ID,
            "landscapes": [],
            "has_more": False,
        },
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_competitive_landscape_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/competitive-landscape/{LOCATION_ID}/summaries"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["location_id"] == LOCATION_ID
