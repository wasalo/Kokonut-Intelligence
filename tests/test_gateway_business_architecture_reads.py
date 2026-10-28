"""Tests for location-scoped business architecture Kernel projections."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import business_architecture_reads as reads
from services.gateway.business_architecture_routes import register_business_architecture_routes
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from fastapi.encoders import jsonable_encoder  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
ROADMAP_ID = str(uuid4())
REQUIREMENT_ID = str(uuid4())
MAPPING_COLUMNS = (
    "roadmap_id", "roadmap_name", "roadmap_status", "planning_horizon_start",
    "planning_horizon_end", "requirement_id", "requirement_title", "need_type",
    "priority", "requirement_status", "capability_name", "value_stream_name",
    "strategy_perspective",
)
MISSION_COLUMNS = ("statement_type", "statement_text", "effective_date", "review_date")


def _summary_payload(location_id=LOCATION_ID, *, offset=0, limit=25, has_more=False):
    mapping = dict(zip(MAPPING_COLUMNS, _mapping_row()))
    mission = dict(zip(
        MISSION_COLUMNS,
        ("mission", "Restore living soils with our community.", date(2026, 1, 1), date(2027, 1, 1)),
    ))
    return {
        "location_id": location_id,
        "offset": offset,
        "missions": [mission],
        "mappings": [mapping],
        "has_more": has_more,
        "next_offset": offset + limit if has_more else None,
    }


def _route_test_app(provider=object(), database_error=Exception):
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_business_architecture_routes(
        router, provider, run_in_threadpool, SimpleNamespace(Error=database_error)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


class _Connection:
    def __init__(self, missions, mappings):
        self.rows = {"missions": missions, "mappings": mappings}
        self.operations = []
        self.result_key = None
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
        if "list_location_business_architecture_missions" in normalized:
            self.connection.result_key = "missions"
            columns = MISSION_COLUMNS
        elif "list_location_business_architecture_mappings" in normalized:
            self.connection.result_key = "mappings"
            columns = MAPPING_COLUMNS
        else:
            self.connection.result_key = None
            columns = ()
        if self.connection.result_key:
            self.description = [SimpleNamespace(name=column) for column in columns]

    def fetchall(self):
        return self.connection.rows[self.connection.result_key]


def _mapping_row(roadmap_id=ROADMAP_ID, requirement_id=REQUIREMENT_ID):
    return (
        roadmap_id, "Farm operating model", "active", date(2026, 1, 1),
        date(2026, 12, 31), requirement_id, "Protect soil and water", "sustainability",
        1, "validated", "Soil stewardship", "Regenerative production", "internal_process",
    )


def test_summary_uses_signed_context_and_bounded_read_functions():
    mission = ("mission", "Restore living soils with our community.", date(2026, 1, 1), date(2027, 1, 1))
    connection = _Connection([mission], [_mapping_row(), _mapping_row(str(uuid4()), str(uuid4()))])
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_business_architecture_summary(
            OPERATOR_ID, LOCATION_ID, limit="1", offset="5",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "business_architecture",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "list_location_business_architecture_missions" in connection.operations[-2][0]
    assert "list_location_business_architecture_mappings" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 5)
    assert result == {
        "location_id": LOCATION_ID,
        "offset": 5,
        "missions": [dict(zip(MISSION_COLUMNS, mission))],
        "mappings": [dict(zip(MAPPING_COLUMNS, _mapping_row()))],
        "has_more": True,
        "next_offset": 6,
    }
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("kwargs", [
    {"limit": "0"}, {"limit": "51"}, {"limit": "many"}, {"limit": True},
    {"offset": "-1"}, {"offset": "10001"}, {"offset": "1.2"},
])
def test_invalid_page_input_fails_before_database_access(kwargs):
    with pytest.raises(reads.BusinessArchitectureReadInvalid):
        reads.get_location_business_architecture_summary(
            OPERATOR_ID, LOCATION_ID,
            connection_factory=lambda: pytest.fail("invalid input must fail before DB access"),
            **kwargs,
        )


@pytest.mark.parametrize("operator_id,location_id", [
    ("not-a-uuid", LOCATION_ID), (OPERATOR_ID, "not-a-uuid"),
])
def test_invalid_identity_fails_before_database_access(operator_id, location_id):
    with pytest.raises(reads.BusinessArchitectureReadInvalid):
        reads.get_location_business_architecture_summary(
            operator_id, location_id,
            connection_factory=lambda: pytest.fail("invalid identity must fail before DB access"),
        )


def test_tenant_denial_rolls_back_without_projection_calls():
    connection = _Connection([], [])

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_business_architecture_summary(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("kokonut_security.list_location_business_architecture_" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_route_policy_requires_exact_location_business_architecture_read_grant():
    path = f"/operator/api/business-architecture/{LOCATION_ID}/summary"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "business_architecture",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_http_projection_is_no_store_and_requires_operator_session(monkeypatch):
    monkeypatch.setattr(
        "services.gateway.business_architecture_reads.get_location_business_architecture_summary",
        lambda *_args, **_kwargs: _summary_payload(),
    )
    app = _route_test_app()
    with TestClient(app) as client:
        response = client.get(f"/operator/api/business-architecture/{LOCATION_ID}/summary")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == jsonable_encoder(_summary_payload())


def test_business_architecture_response_schema_is_published_and_strict():
    schema = _route_test_app().openapi()
    operation = schema["paths"][
        "/operator/api/business-architecture/{location_id}/summary"
    ]["get"]
    response = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response == {"$ref": "#/components/schemas/BusinessArchitectureSummaryResponse"}
    components = schema["components"]["schemas"]
    for name in (
        "BusinessArchitectureSummaryResponse",
        "BusinessArchitectureMissionResponse",
        "BusinessArchitectureMappingResponse",
    ):
        assert components[name]["additionalProperties"] is False
    assert components["BusinessArchitectureSummaryResponse"]["properties"]["mappings"]["maxItems"] == 50
    assert components["BusinessArchitectureSummaryResponse"]["properties"]["missions"]["maxItems"] == 3


@pytest.mark.parametrize(
    "invalid_field",
    [
        "extra",
        "nested_extra",
        "invalid_mission_type",
        "negative_priority",
        "too_many_mappings",
        "wrong_location",
        "wrong_offset",
        "wrong_next_offset",
    ],
)
def test_business_architecture_route_rejects_invalid_projection(monkeypatch, invalid_field):
    payload = _summary_payload()
    if invalid_field == "extra":
        payload["source_ids"] = [str(uuid4())]
    elif invalid_field == "nested_extra":
        payload["missions"][0]["approved_by"] = "private"
    elif invalid_field == "invalid_mission_type":
        payload["missions"][0]["statement_type"] = "platform"
    elif invalid_field == "negative_priority":
        payload["mappings"][0]["priority"] = 0
    elif invalid_field == "too_many_mappings":
        payload["mappings"] = [payload["mappings"][0]] * 51
    elif invalid_field == "wrong_location":
        payload["location_id"] = str(uuid4())
    elif invalid_field == "wrong_offset":
        payload["offset"] = 1
    else:
        payload["has_more"] = True
        payload["next_offset"] = 50
    monkeypatch.setattr(
        "services.gateway.business_architecture_reads.get_location_business_architecture_summary",
        lambda *_args, **_kwargs: payload,
    )

    with TestClient(_route_test_app()) as client:
        response = client.get(f"/operator/api/business-architecture/{LOCATION_ID}/summary")

    assert response.status_code == 500
    assert response.json() == {"error": "Business architecture read unavailable"}
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
            {"error": "Tenant-qualified business architecture access is required"}, None,
        ),
        (
            object(), reads.BusinessArchitectureReadInvalid("Invalid location identifier"),
            400, {"error": "Invalid location identifier"}, None,
        ),
        (
            object(), _SyntheticDatabaseError("database error"), 503,
            {"error": "Business architecture read unavailable"}, "30",
        ),
    ],
)
def test_business_architecture_route_preserves_error_contract(
    monkeypatch, provider, error, status_code, body, retry_after
):
    if error is not None:
        def fail(*_args, **_kwargs):
            raise error

        monkeypatch.setattr(
            "services.gateway.business_architecture_reads.get_location_business_architecture_summary",
            fail,
        )
    with TestClient(_route_test_app(provider, _SyntheticDatabaseError)) as client:
        response = client.get(f"/operator/api/business-architecture/{LOCATION_ID}/summary")

    assert response.status_code == status_code
    assert response.json() == body
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    if retry_after is None:
        assert "retry-after" not in response.headers
    else:
        assert response.headers["retry-after"] == retry_after
