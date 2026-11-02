"""Yield-monitoring Kernel reads stay private, read-only, and tenant-scoped."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.operator_auth import auth_route_policy  # noqa: E402
from services.gateway.yield_monitoring import get_location_yield_summary  # noqa: E402
from services.gateway.yield_monitoring_routes import register_yield_monitoring_routes  # noqa: E402


def _yield_summary_payload(location_id):
    return {
        "location_id": location_id,
        "total_observations": 1,
        "first_harvest": "2026-03-04",
        "last_harvest": "2026-03-04",
        "totals_by_yield_unit": [{
            "yield_unit": "kg/ha",
            "observations": 1,
            "avg_yield": 5.25,
            "total_yield": 13.5,
        }],
        "crops": [{
            "crop_name": "maize",
            "yield_unit": "kg/ha",
            "observations": 1,
            "avg_yield": 5.25,
            "min_yield": 5.25,
            "max_yield": 5.25,
            "stddev_yield": None,
            "total_production": 13.5,
        }],
        "recent_harvests": [{
            "harvest_date": "2026-03-04",
            "crop_name": "maize",
            "yield_amount": 5.25,
            "yield_unit": "kg/ha",
            "area_ha": 1.0,
            "total_yield": 13.5,
            "grade": "A",
        }],
    }


def _yield_operator_provider(operator_id, location_id):
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="c" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, op, resource, action, location):
            return (op, resource, action, location) == (
                operator_id, "yield_monitoring", "read", location_id
            )

    return Provider()


def test_yield_summary_policy_is_exact_location_scoped_read():
    location_id = str(uuid4())
    assert auth_route_policy(
        "GET", f"/operator/api/yield-monitoring/{location_id}/summary", enabled=True
    ) == {
        "resource": "yield_monitoring",
        "action": "read",
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy(
        "POST", f"/operator/api/yield-monitoring/{location_id}/summary", enabled=True
    ) is None
    assert auth_route_policy(
        "GET", f"/operator/api/yield-monitoring/{location_id}/summary/extra", enabled=True
    ) is None


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.description = []
        self._one = None
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.conn.queries.append((query, params))
        self.conn.events.append("sql")
        if query.lstrip().startswith("SELECT COUNT(*)"):
            self._one = (3, date(2025, 1, 2), date(2026, 3, 4))
        elif query.lstrip().startswith("SELECT yield_unit,"):
            self.description = [(name,) for name in (
                "yield_unit", "observations", "avg_yield", "total_yield",
            )]
            self._rows = [
                ("kg/ha", 2, Decimal("5.25"), Decimal("13.5")),
                ("lb/ha", 1, Decimal("8"), Decimal("8")),
            ]
        elif "GROUP BY crop_name" in query:
            self.description = [(name,) for name in (
                "crop_name", "yield_unit", "observations", "avg_yield", "min_yield",
                "max_yield", "stddev_yield", "total_production",
            )]
            self._rows = [
                ("maize", "kg/ha", 2, Decimal("5.25"), Decimal("4.5"), Decimal("6"), Decimal("1.06"), Decimal("13.5")),
                ("maize", "lb/ha", 1, Decimal("8"), Decimal("8"), Decimal("8"), None, Decimal("8")),
            ]
        elif "LIMIT 10" in query:
            self.description = [(name,) for name in (
                "harvest_date", "crop_name", "yield_amount", "yield_unit", "area_ha",
                "total_yield", "grade",
            )]
            self._rows = [(date(2026, 3, 4), "maize", Decimal("8"), "lb/ha", Decimal("1"), Decimal("8"), "A")]

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._rows


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


def test_yield_summary_sets_signed_context_before_location_filtered_read_queries():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()
    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "yield_monitoring",
            "action": "read",
        }
        conn.events.append("tenant_context")

    with patch("services.gateway.yield_monitoring.set_operator_tenant_context", set_context):
        result = get_location_yield_summary(
            operator_id, location_id, connection_factory=lambda: conn
        )

    selects = [(query, params) for query, params in conn.queries if "FROM harvest_yield_observation" in query]
    assert len(selects) == 4
    assert all("location_id = %s::uuid" in query for query, _ in selects)
    assert all("status IN ('verified', 'published')" in query for query, _ in selects)
    assert all(params == (location_id,) for _, params in selects)
    assert conn.queries[:3] == [
        ("SET TRANSACTION READ ONLY", None),
        ("SET LOCAL statement_timeout = '5s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert conn.events == [
        "sql", "sql", "sql", "tenant_context", "sql", "sql", "sql", "sql"
    ]
    assert result == {
        "location_id": location_id,
        "total_observations": 3,
        "first_harvest": "2025-01-02",
        "last_harvest": "2026-03-04",
        "totals_by_yield_unit": [
            {"yield_unit": "kg/ha", "observations": 2, "avg_yield": 5.25, "total_yield": 13.5},
            {"yield_unit": "lb/ha", "observations": 1, "avg_yield": 8.0, "total_yield": 8.0},
        ],
        "crops": [
            {
                "crop_name": "maize", "yield_unit": "kg/ha", "observations": 2, "avg_yield": 5.25,
                "min_yield": 4.5, "max_yield": 6.0, "stddev_yield": 1.06,
                "total_production": 13.5,
            },
            {
                "crop_name": "maize", "yield_unit": "lb/ha", "observations": 1, "avg_yield": 8.0,
                "min_yield": 8.0, "max_yield": 8.0, "stddev_yield": None,
                "total_production": 8.0,
            },
        ],
        "recent_harvests": [{
            "harvest_date": "2026-03-04", "crop_name": "maize", "yield_amount": 8.0,
            "yield_unit": "lb/ha", "area_ha": 1.0, "total_yield": 8.0, "grade": "A",
        }],
    }
    assert conn.rolled_back and conn.closed


def test_invalid_yield_summary_scope_fails_before_database_connection():
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid identifiers must fail before connecting")

    with pytest.raises(ValueError, match="Invalid operator or location"):
        get_location_yield_summary("bad", str(uuid4()), connection_factory=connection_factory)
    assert not opened


@pytest.fixture
def gateway_audit_spool(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_PATH", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_MAX_EVENTS", "1000")
    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_ALERT_THRESHOLD", "0")

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


def test_yield_summary_route_requires_tenant_scope_and_returns_no_store(
    monkeypatch, gateway_audit_spool
):
    operator_id, location_id = str(uuid4()), str(uuid4())
    monkeypatch.setattr(
        "services.gateway.operator_auth.create_provider",
        lambda: _yield_operator_provider(operator_id, location_id),
    )
    payload = _yield_summary_payload(location_id)
    monkeypatch.setattr(
        "services.gateway.yield_monitoring.get_location_yield_summary",
        lambda op, loc: payload,
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/yield-monitoring/{location_id}/summary")

    assert response.status_code == 200
    assert response.json() == payload
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}


def test_yield_summary_response_schema_is_published_and_strict(
    monkeypatch, gateway_audit_spool
):
    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: None)
    openapi = create_app().openapi()

    response_schema = openapi["paths"][
        "/operator/api/yield-monitoring/{location_id}/summary"
    ]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema == {"$ref": "#/components/schemas/YieldSummaryResponse"}
    schemas = openapi["components"]["schemas"]
    for name in (
        "YieldSummaryResponse",
        "YieldUnitSummary",
        "YieldCropSummary",
        "RecentHarvestSummary",
    ):
        assert schemas[name]["additionalProperties"] is False


def test_yield_summary_route_preserves_disabled_oidc_response():
    import asyncio

    from fastapi import APIRouter

    router = APIRouter()
    register_yield_monitoring_routes(router, None, None, None)
    endpoint = router.routes[0].endpoint
    response = asyncio.run(endpoint(SimpleNamespace(), str(uuid4())))

    assert response.status_code == 404
    assert response.body == b'{"error":"Operator OIDC is disabled"}'
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


@pytest.mark.parametrize("invalid_field", ["extra", "negative_count", "invalid_date", "non_finite"])
def test_yield_summary_route_rejects_invalid_projection_with_private_error(
    monkeypatch, gateway_audit_spool, invalid_field
):
    operator_id, location_id = str(uuid4()), str(uuid4())
    monkeypatch.setattr(
        "services.gateway.operator_auth.create_provider",
        lambda: _yield_operator_provider(operator_id, location_id),
    )
    payload = _yield_summary_payload(location_id)
    if invalid_field == "extra":
        payload["source_record_ids"] = [str(uuid4())]
    elif invalid_field == "negative_count":
        payload["total_observations"] = -1
    elif invalid_field == "invalid_date":
        payload["first_harvest"] = "not-a-date"
    else:
        payload["totals_by_yield_unit"][0]["avg_yield"] = float("nan")
    monkeypatch.setattr(
        "services.gateway.yield_monitoring.get_location_yield_summary",
        lambda _operator_id, _location_id: payload,
    )

    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/yield-monitoring/{location_id}/summary")

    assert response.status_code == 500
    assert response.json() == {"error": "Yield summary unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}


@pytest.mark.parametrize(
    ("error_kind", "status_code", "body", "retry_after"),
    [
        ("tenant", 403, {"error": "Tenant-qualified operator access is required"}, None),
        ("invalid", 400, {"error": "Invalid synthetic scope"}, None),
        ("database", 503, {"error": "Yield summary unavailable"}, "30"),
    ],
)
def test_yield_summary_route_preserves_error_and_private_cache_contracts(
    monkeypatch, gateway_audit_spool, error_kind, status_code, body, retry_after
):
    import psycopg2

    from services.common.tenant_context import TenantContextDenied

    operator_id, location_id = str(uuid4()), str(uuid4())
    monkeypatch.setattr(
        "services.gateway.operator_auth.create_provider",
        lambda: _yield_operator_provider(operator_id, location_id),
    )
    errors = {
        "tenant": TenantContextDenied("scope denied"),
        "invalid": ValueError("Invalid synthetic scope"),
        "database": psycopg2.Error("synthetic database failure"),
    }

    def fail_summary(*_args):
        raise errors[error_kind]

    monkeypatch.setattr(
        "services.gateway.yield_monitoring.get_location_yield_summary", fail_summary
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/yield-monitoring/{location_id}/summary")

    assert response.status_code == status_code
    assert response.json() == body
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}
    if retry_after is None:
        assert "retry-after" not in response.headers
    else:
        assert response.headers["retry-after"] == retry_after


def test_yield_summary_route_denies_missing_location_grant_before_handler(
    monkeypatch, gateway_audit_spool
):
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="b" * 64,
        operator=SimpleNamespace(operator_id=str(uuid4())),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, *_scope):
            return False

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    called = False

    def unexpected_summary(*_args):
        nonlocal called
        called = True
        raise AssertionError("a missing grant must deny before entering the handler")

    monkeypatch.setattr(
        "services.gateway.yield_monitoring.get_location_yield_summary", unexpected_summary
    )
    location_id = str(uuid4())
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/yield-monitoring/{location_id}/summary")

    assert response.status_code == 403
    assert called is False
