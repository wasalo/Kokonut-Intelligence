"""Tests for location-scoped coordination governance summaries."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import coordination_reads as reads
from services.gateway.coordination_reads import CoordinationReadInvalid
from services.gateway.coordination_routes import register_coordination_routes
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
COLUMNS = (
    "alliance_count", "draft_alliance_count", "proposed_alliance_count",
    "approved_alliance_count", "active_alliance_count", "paused_alliance_count",
    "completed_alliance_count", "dissolved_alliance_count", "rejected_alliance_count",
    "overdue_review_count", "open_conflict_declaration_count",
    "unreviewed_harm_analysis_count", "open_appeal_count", "open_remedy_count",
    "preserved_minority_view_count", "completed_knowledge_exchange_count",
    "open_learning_link_count", "draft_metric_observation_count",
    "rejected_metric_observation_count",
)
ROW = (3, 1, 0, 0, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1)


def _summary_payload():
    return {"location_id": LOCATION_ID, **dict(zip(COLUMNS, ROW))}


def _route_test_app(provider, psycopg2):
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_coordination_routes(router, provider, run_in_threadpool, psycopg2)
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


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


def test_summary_sets_exact_context_and_reads_only_bounded_function():
    connection = _Connection(ROW)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_coordination_governance_summary(
            OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "coordination",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "kokonut_security.location_coordination_governance_summary" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID,)
    assert result == {"location_id": LOCATION_ID, **dict(zip(COLUMNS, ROW))}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("operator_id,location_id", [
    ("not-a-uuid", LOCATION_ID), (OPERATOR_ID, "not-a-uuid"),
])
def test_invalid_identity_fails_before_database_access(operator_id, location_id):
    with pytest.raises(reads.CoordinationReadInvalid):
        reads.get_location_coordination_governance_summary(
            operator_id, location_id,
            connection_factory=lambda: pytest.fail("invalid identity must fail before DB access"),
        )


def test_tenant_denial_rolls_back_without_projection_call():
    connection = _Connection(ROW)

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_coordination_governance_summary(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("location_coordination_governance_summary" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_summary_output_schema_contains_only_aggregate_governance_fields():
    assert "alliance_count" in COLUMNS
    assert "open_conflict_declaration_count" in COLUMNS
    assert "unreviewed_harm_analysis_count" in COLUMNS
    assert "open_remedy_count" in COLUMNS
    assert "party_id" not in COLUMNS
    assert "description" not in COLUMNS
    assert "evidence" not in COLUMNS


def test_route_policy_requires_exact_location_coordination_read_grant():
    path = f"/operator/api/coordination/{LOCATION_ID}/summary"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "coordination",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_http_projection_is_no_store_and_operator_authenticated(monkeypatch):
    monkeypatch.setattr(
        "services.gateway.coordination_reads.get_location_coordination_governance_summary",
        lambda *_args, **_kwargs: _summary_payload(),
    )
    app = _route_test_app(object(), SimpleNamespace(Error=Exception))
    with TestClient(app) as client:
        response = client.get(f"/operator/api/coordination/{LOCATION_ID}/summary")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == _summary_payload()


def test_coordination_summary_response_model_is_published_and_strict():
    app = _route_test_app(object(), SimpleNamespace(Error=Exception))
    openapi = app.openapi()

    response_schema = openapi["paths"][
        "/operator/api/coordination/{location_id}/summary"
    ]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema == {
        "$ref": "#/components/schemas/CoordinationGovernanceSummaryResponse"
    }
    schema = openapi["components"]["schemas"]["CoordinationGovernanceSummaryResponse"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"location_id", *COLUMNS}
    for field in COLUMNS:
        assert schema["properties"][field]["type"] == "integer"
        assert schema["properties"][field]["minimum"] == 0


@pytest.mark.parametrize("invalid_field", ["extra", "negative_count", "string_count"])
def test_coordination_summary_rejects_invalid_projection(monkeypatch, invalid_field):
    result = _summary_payload()
    if invalid_field == "extra":
        result["party_id"] = str(uuid4())
    elif invalid_field == "negative_count":
        result["alliance_count"] = -1
    else:
        result["alliance_count"] = "3"
    monkeypatch.setattr(
        "services.gateway.coordination_reads.get_location_coordination_governance_summary",
        lambda *_args, **_kwargs: result,
    )
    app = _route_test_app(object(), SimpleNamespace(Error=Exception))

    with TestClient(app) as client:
        response = client.get(f"/operator/api/coordination/{LOCATION_ID}/summary")

    assert response.status_code == 500
    assert response.json() == {"error": "Coordination summary unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


class _SyntheticDatabaseError(Exception):
    def __init__(self, message, pgcode=None):
        super().__init__(message)
        self.pgcode = pgcode


@pytest.mark.parametrize(
    ("provider", "error", "status_code", "body", "retry_after"),
    [
        (None, None, 404, {"error": "Operator OIDC is disabled"}, None),
        (
            object(), TenantContextDenied("denied"), 403,
            {"error": "Tenant-qualified coordination access is required"}, None,
        ),
        (
            object(), CoordinationReadInvalid("Invalid location identifier"), 400,
            {"error": "Invalid location identifier"}, None,
        ),
        (
            object(), _SyntheticDatabaseError("denied", pgcode="42501"), 403,
            {"error": "A current location coordination read grant is required"}, None,
        ),
        (
            object(), _SyntheticDatabaseError("database failure"), 503,
            {"error": "Coordination summary unavailable"}, "30",
        ),
    ],
)
def test_coordination_summary_preserves_error_and_cache_contracts(
    monkeypatch, provider, error, status_code, body, retry_after
):
    if error is not None:
        def fail_summary(*_args, **_kwargs):
            raise error

        monkeypatch.setattr(
            "services.gateway.coordination_reads.get_location_coordination_governance_summary",
            fail_summary,
        )
    app = _route_test_app(provider, SimpleNamespace(Error=_SyntheticDatabaseError))

    with TestClient(app) as client:
        response = client.get(f"/operator/api/coordination/{LOCATION_ID}/summary")

    assert response.status_code == status_code
    assert response.json() == body
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    if retry_after is None:
        assert "retry-after" not in response.headers
    else:
        assert response.headers["retry-after"] == retry_after
