"""Emergency-response Gateway reads are private, scoped, and aggregate-only."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway.app import create_app  # noqa: E402
from services.gateway.emergency_response import (  # noqa: E402
    get_emergency_response_summary,
)
from services.gateway.emergency_response_routes import (  # noqa: E402
    register_emergency_response_routes,
)
from services.gateway.operator_auth import auth_route_policy  # noqa: E402


def _emergency_summary_payload(location_id):
    return {
        "location_id": location_id,
        "total_incidents": 2,
        "resolved_incidents": 1,
        "escalated_incidents": 1,
        "recovered_incidents": 1,
        "avg_response_time_days": 4.0,
        "deadline_assessed_incidents": 2,
        "deadline_met_incidents": 1,
        "deadline_compliance_pct": 50.0,
        "financial_impact_usd": -700.0,
        "avg_affected_area_pct": 18.5,
        "by_type": [{
            "incident_type": "drought",
            "count": 2,
            "resolved_count": 1,
            "escalated_count": 1,
            "avg_affected_area_pct": 25.0,
            "financial_impact_usd": -100.0,
        }],
        "by_severity": [{
            "severity": "high",
            "count": 2,
            "resolved_count": 1,
            "escalated_count": 1,
            "avg_affected_area_pct": 18.5,
            "financial_impact_usd": -700.0,
        }],
    }


def _emergency_route_app(provider, database_error_type):
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_emergency_response_routes(
        router, provider, run_in_threadpool, SimpleNamespace(Error=database_error_type)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=str(uuid4()))
        )
        return await call_next(request)

    return app


def test_emergency_summary_policy_requires_exact_location_read_scope():
    location_id = str(uuid4())
    path = f"/operator/api/emergency-response/{location_id}/summary"

    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "emergency_response",
        "action": "read",
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", f"{path}/details", enabled=True) is None
    assert auth_route_policy("GET", path, enabled=False) is None


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.single = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        if "AS total_incidents" in query:
            self.single = (5, 2, 1, 3, 4.333, 2, 1, 1234.555, 18.25)
            self.connection.events.append("aggregate")
        elif "GROUP BY incident_type" in query:
            self.rows = [("drought", 3, 1, 1, 25.0, 1000.125)]
            self.connection.events.append("by_type")
        elif "GROUP BY severity" in query:
            self.rows = [("high", 4, 2, 1, 18.25, 1234.555)]
            self.connection.events.append("by_severity")

    def fetchone(self):
        return self.single

    def fetchall(self):
        return self.rows


class _Connection:
    autocommit = False

    def __init__(self):
        self.queries = []
        self.events = []
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_emergency_summary_sets_signed_context_before_scoped_aggregate_queries():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "emergency_response",
            "action": "read",
        }
        connection.events.append("tenant_context")

    with patch(
        "services.gateway.emergency_response.set_operator_tenant_context", set_context
    ):
        result = get_emergency_response_summary(
            operator_id, location_id, connection_factory=lambda: conn
        )

    assert conn.events == ["tenant_context", "aggregate", "by_type", "by_severity"]
    assert [query for query, _params in conn.queries[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert all(
        params == (location_id,)
        for _query, params in conn.queries[3:]
    )
    assert result == {
        "location_id": location_id,
        "total_incidents": 5,
        "resolved_incidents": 2,
        "escalated_incidents": 1,
        "recovered_incidents": 3,
        "avg_response_time_days": 4.3,
        "deadline_assessed_incidents": 2,
        "deadline_met_incidents": 1,
        "deadline_compliance_pct": 50.0,
        "financial_impact_usd": 1234.56,
        "avg_affected_area_pct": 18.2,
        "by_type": [
            {
                "incident_type": "drought",
                "count": 3,
                "resolved_count": 1,
                "escalated_count": 1,
                "avg_affected_area_pct": 25.0,
                "financial_impact_usd": 1000.12,
            }
        ],
        "by_severity": [
            {
                "severity": "high",
                "count": 4,
                "resolved_count": 2,
                "escalated_count": 1,
                "avg_affected_area_pct": 18.2,
                "financial_impact_usd": 1234.56,
            }
        ],
    }
    assert "incidents" not in result
    assert conn.rolled_back and conn.closed


def test_invalid_emergency_scope_fails_before_connection():
    requested = False

    def connection_factory():
        nonlocal requested
        requested = True
        raise AssertionError("invalid scope must not open PostgreSQL")

    with pytest.raises(ValueError, match="Invalid operator or location"):
        get_emergency_response_summary(
            "not-an-operator", str(uuid4()), connection_factory=connection_factory
        )

    assert requested is False


def test_emergency_tenant_denial_rolls_back_and_closes_connection():
    conn = _Connection()
    with patch(
        "services.gateway.emergency_response.set_operator_tenant_context",
        side_effect=TenantContextDenied("synthetic revoked grant"),
    ):
        with pytest.raises(TenantContextDenied):
            get_emergency_response_summary(
                str(uuid4()), str(uuid4()), connection_factory=lambda: conn
            )

    assert len(conn.queries) == 3
    assert conn.rolled_back and conn.closed


@pytest.fixture
def isolated_audit(monkeypatch):
    class InMemoryAudit:
        def __init__(self):
            pass

        def replay_pending(self, _limit=100):
            return 0

        def log(self, **_event):
            return None

        def capture_status(self):
            return "ok"

    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)


def test_emergency_summary_http_route_checks_scope_before_calling_service(
    monkeypatch, isolated_audit
):
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="d" * 64,
        operator=SimpleNamespace(operator_id=str(uuid4())),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, *_scope):
            return False

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    service_called = False

    def unexpected_service(*_args):
        nonlocal service_called
        service_called = True
        raise AssertionError("authorization denial must precede service access")

    monkeypatch.setattr(
        "services.gateway.emergency_response.get_emergency_response_summary",
        unexpected_service,
    )
    location_id = str(uuid4())

    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(
            f"/operator/api/emergency-response/{location_id}/summary"
        )

    assert response.status_code == 403
    assert service_called is False


def test_emergency_summary_http_route_returns_no_store_aggregate(monkeypatch, isolated_audit):
    operator_id, location_id = str(uuid4()), str(uuid4())
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="e" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, scoped_operator, resource, action, scoped_location):
            return (
                scoped_operator == operator_id
                and resource == "emergency_response"
                and action == "read"
                and scoped_location == location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr(
        "services.gateway.emergency_response.get_emergency_response_summary",
        lambda _scoped_operator, scoped_location: _emergency_summary_payload(
            scoped_location
        ),
    )

    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(
            f"/operator/api/emergency-response/{location_id}/summary"
        )

    assert response.status_code == 200
    assert response.json() == _emergency_summary_payload(location_id)
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {
        value.strip().lower() for value in response.headers["vary"].split(",")
    }


def test_emergency_summary_response_schema_is_published_and_strict():
    app = _emergency_route_app(object(), Exception)
    openapi = app.openapi()
    response_schema = openapi["paths"][
        "/operator/api/emergency-response/{location_id}/summary"
    ]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema == {"$ref": "#/components/schemas/EmergencyResponseSummary"}

    schemas = openapi["components"]["schemas"]
    for name in (
        "EmergencyResponseSummary",
        "EmergencyIncidentTypeSummary",
        "EmergencySeveritySummary",
    ):
        assert schemas[name]["additionalProperties"] is False

    summary = schemas["EmergencyResponseSummary"]["properties"]
    assert summary["by_type"]["maxItems"] == 10
    assert summary["by_severity"]["maxItems"] == 4
    assert summary["avg_affected_area_pct"]["maximum"] == 100
    assert summary["avg_affected_area_pct"]["minimum"] == 0
    deadline_pct = summary["deadline_compliance_pct"]
    deadline_number_schema = next(
        item for item in deadline_pct["anyOf"] if item.get("type") == "number"
    )
    assert deadline_number_schema["maximum"] == 100
    assert deadline_number_schema["minimum"] == 0
    incident = schemas["EmergencyIncidentTypeSummary"]["properties"]
    assert set(incident["incident_type"]["enum"]) == {
        "drought", "flood", "pest_outbreak", "extreme_heat", "frost", "fire",
        "disease_epidemic", "soil_degradation", "water_crisis", "other",
    }
    severity = schemas["EmergencySeveritySummary"]["properties"]["severity"]["enum"]
    assert set(severity) == {"low", "medium", "high", "critical"}


@pytest.mark.parametrize(
    "invalid_field",
    [
        "extra",
        "nested_extra",
        "invalid_incident_type",
        "negative_count",
        "percentage",
        "type_group_limit",
        "severity_group_limit",
    ],
)
def test_emergency_summary_rejects_invalid_projection_with_private_error(
    monkeypatch, invalid_field
):
    location_id = str(uuid4())
    payload = _emergency_summary_payload(location_id)
    if invalid_field == "extra":
        payload["incident_records"] = [{"id": str(uuid4())}]
    elif invalid_field == "nested_extra":
        payload["by_type"][0]["source_id"] = str(uuid4())
    elif invalid_field == "invalid_incident_type":
        payload["by_type"][0]["incident_type"] = "unknown"
    elif invalid_field == "negative_count":
        payload["total_incidents"] = -1
    elif invalid_field == "percentage":
        payload["avg_affected_area_pct"] = 101.0
    elif invalid_field == "type_group_limit":
        payload["by_type"] = [dict(payload["by_type"][0]) for _ in range(11)]
    else:
        payload["by_severity"] = [dict(payload["by_severity"][0]) for _ in range(5)]
    monkeypatch.setattr(
        "services.gateway.emergency_response.get_emergency_response_summary",
        lambda *_args: payload,
    )
    app = _emergency_route_app(object(), Exception)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/emergency-response/{location_id}/summary"
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Emergency response summary unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


class _SyntheticDatabaseError(Exception):
    pass


@pytest.mark.parametrize(
    ("provider", "error", "status_code", "body", "retry_after"),
    [
        (None, None, 404, {"error": "Operator OIDC is disabled"}, None),
        (
            object(), TenantContextDenied("revoked"), 403,
            {"error": "Tenant-qualified operator access is required"}, None,
        ),
        (
            object(), ValueError("Invalid operator or location identifier"), 400,
            {"error": "Invalid operator or location identifier"}, None,
        ),
        (
            object(), _SyntheticDatabaseError("synthetic failure"), 503,
            {"error": "Emergency response summary unavailable"}, "30",
        ),
    ],
)
def test_emergency_summary_preserves_error_and_cache_contracts(
    monkeypatch, provider, error, status_code, body, retry_after
):
    if error is not None:
        def fail_summary(*_args):
            raise error

        monkeypatch.setattr(
            "services.gateway.emergency_response.get_emergency_response_summary",
            fail_summary,
        )
    app = _emergency_route_app(provider, _SyntheticDatabaseError)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/emergency-response/{uuid4()}/summary")

    assert response.status_code == status_code
    assert response.json() == body
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    if retry_after is None:
        assert "retry-after" not in response.headers
    else:
        assert response.headers["retry-after"] == retry_after
