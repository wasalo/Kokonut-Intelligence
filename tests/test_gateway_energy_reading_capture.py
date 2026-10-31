"""Energy-reading capture uses signed location scope and a strict private receipt."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway.energy_monitoring_capture_routes import (  # noqa: E402
    register_energy_monitoring_capture_routes,
)
from services.gateway.energy_monitoring_writes import (  # noqa: E402
    EnergyReadingCaptureInvalid,
    record_location_energy_reading,
)
from services.gateway.operator_auth import auth_route_policy  # noqa: E402

LOCATION = "71100000-0000-4000-8000-000000000001"
OPERATOR = "71100000-0000-4000-8000-000000000002"
SOURCE = "71100000-0000-4000-8000-000000000003"
REQUEST = "71100000-0000-4000-8000-000000000004"
READING = "71100000-0000-4000-8000-000000000005"


def _payload(**updates):
    result = {
        "request_id": REQUEST,
        "source_id": SOURCE,
        "reading_date": "2026-10-30",
        "reading_type": "consumption",
        "kwh": 10.25,
        "cost_per_kwh": 0.15,
        "cost_currency_code": "usd",
        "activity_type": "irrigation",
        "equipment_id": None,
        "notes": "Meter read",
        "metadata": {"meter": "M-1"},
        "reason": "Monthly meter entry",
    }
    result.update(updates)
    return result


def _response(**updates):
    result = {
        "request_id": REQUEST,
        "reading_id": READING,
        "location_id": LOCATION,
        "source_id": SOURCE,
        "reading_date": "2026-10-30",
        "reading_type": "consumption",
        "kwh": 10.25,
        "cost_per_kwh": 0.15,
        "total_cost": 1.54,
        "cost_currency_code": "USD",
        "activity_type": "irrigation",
        "status": "recorded",
        "replayed": False,
        "created_at": "2026-10-30T12:00:00+00:00",
    }
    result.update(updates)
    return result


class _Cursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.events.append(("query", query, params))

    def fetchone(self):
        return (self.connection.response,)


class _Connection:
    def __init__(self, response):
        self.response = response
        self.events = []
        self.rolled_back = False
        self.committed = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_capture_route_policy_is_exact_location_create_only():
    expected = {
        "resource": "energy_monitoring",
        "action": "create",
        "public": False,
        "location_id": LOCATION,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy(
        "POST", f"/operator/api/energy/{LOCATION}/readings", enabled=True
    ) == expected
    assert auth_route_policy(
        "GET", f"/operator/api/energy/{LOCATION}/readings", enabled=True
    ) is None
    assert auth_route_policy(
        "POST", f"/operator/api/energy/{LOCATION}/readings/extra", enabled=True
    ) is None


def test_write_helper_sets_signed_scope_before_function_call_and_commits_receipt():
    conn = _Connection(_response())
    context_events = []

    def set_context(connection, **kwargs):
        assert connection is conn
        context_events.append(kwargs)
        conn.events.append(("context",))

    with patch(
        "services.gateway.energy_monitoring_writes.set_operator_tenant_context",
        set_context,
    ):
        result = record_location_energy_reading(
            OPERATOR, LOCATION, _payload(), connection_factory=lambda: conn
        )

    assert result["status"] == "recorded"
    assert context_events == [{
        "operator_id": OPERATOR,
        "location_id": LOCATION,
        "resource": "energy_monitoring",
        "action": "create",
    }]
    function_query = next(event for event in conn.events if event[0] == "query" and "record_location_energy_reading" in event[1])
    assert conn.events.index(("context",)) < conn.events.index(function_query)
    assert function_query[2] == (
        LOCATION, SOURCE, REQUEST, date(2026, 10, 30), "consumption",
        Decimal("10.25"), Decimal("0.15"), "USD", "irrigation", None,
        "Meter read", '{"meter":"M-1"}', "Monthly meter entry",
    )
    assert conn.committed and not conn.rolled_back and conn.closed


@pytest.mark.parametrize(
    "payload",
    [
        _payload(kwh=True),
        _payload(kwh=float("nan")),
        _payload(reading_date="2026-02-30"),
        _payload(cost_currency_code="US"),
        _payload(cost_per_kwh=0.15, cost_currency_code=None),
        _payload(metadata=["not", "an", "object"]),
        _payload(metadata={"bad\x00key": "value"}),
        _payload(reason="  "),
    ],
)
def test_invalid_write_inputs_fail_before_connection(payload):
    connection_factory = Mock()
    with pytest.raises(EnergyReadingCaptureInvalid):
        record_location_energy_reading(
            OPERATOR, LOCATION, payload, connection_factory=connection_factory
        )
    connection_factory.assert_not_called()


def test_transaction_rolls_back_and_closes_when_receipt_is_invalid():
    conn = _Connection({"unexpected": "shape"})
    with patch(
        "services.gateway.energy_monitoring_writes.set_operator_tenant_context"
    ):
        with pytest.raises(RuntimeError, match="receipt"):
            record_location_energy_reading(
                OPERATOR, LOCATION, _payload(), connection_factory=lambda: conn
            )
    assert conn.rolled_back and not conn.committed and conn.closed


def test_malformed_function_receipt_is_server_contract_failure_not_input_error():
    conn = _Connection(_response(reading_id="not-a-uuid"))
    with patch(
        "services.gateway.energy_monitoring_writes.set_operator_tenant_context"
    ):
        with pytest.raises(RuntimeError, match="invalid reading ID"):
            record_location_energy_reading(
                OPERATOR, LOCATION, _payload(), connection_factory=lambda: conn
            )
    assert conn.rolled_back and not conn.committed and conn.closed


def _capture_app(provider, runner):
    app = FastAPI()
    router = APIRouter()

    async def async_runner(function, *args, **kwargs):
        return runner(function, *args, **kwargs)

    register_energy_monitoring_capture_routes(
        router,
        provider,
        async_runner,
        SimpleNamespace(Error=type("PsycopgError", (Exception,), {})),
    )
    app.include_router(router)

    @app.middleware("http")
    async def bind_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR)
        )
        return await call_next(request)

    return app


def test_capture_route_returns_strict_created_receipt_no_store_and_openapi():
    result = _response(created_at="2026-10-30T12:00:00Z")
    app = _capture_app(object(), lambda function, *args, **kwargs: result)
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/energy/{LOCATION}/readings", json=_payload()
        )

    assert response.status_code == 201
    assert response.json() == result
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}

    operation = app.openapi()["paths"][
        "/operator/api/energy/{location_id}/readings"
    ]["post"]
    assert operation["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/EnergyReadingCaptureResponse"
    }
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/EnergyReadingCaptureResponse"
    }
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert request_schema["additionalProperties"] is False
    assert set(request_schema["required"]) == {
        "request_id", "source_id", "reading_type", "kwh", "reason"
    }


@pytest.mark.parametrize(
    ("response_payload", "status"),
    [
        (_response(replayed=True), 200),
        (_response(location_id=str(uuid4())), 500),
        (_response(reading_id="malformed"), 500),
        ({"bad": True}, 500),
    ],
)
def test_capture_route_replay_and_invalid_database_response_are_private(
    response_payload, status
):
    app = _capture_app(object(), lambda function, *args, **kwargs: response_payload)
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/energy/{LOCATION}/readings", json=_payload()
        )
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in response.headers["vary"].lower()
    if status == 500:
        assert response.json() == {"error": "Energy reading capture unavailable"}


def test_capture_route_rejects_extra_fields_before_service_access():
    service = Mock(return_value=_response())
    app = _capture_app(object(), service)
    payload = _payload(spoofed_operator_id=OPERATOR)
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/energy/{LOCATION}/readings", json=payload
        )
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    service.assert_not_called()


def test_capture_route_requires_oidc_and_maps_tenant_denial():
    app = _capture_app(None, lambda *_args: pytest.fail("must not call writer"))
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/energy/{LOCATION}/readings", json=_payload()
        )
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"

    def denied(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    app = _capture_app(object(), denied)
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/energy/{LOCATION}/readings", json=_payload()
        )
    assert response.status_code == 403
    assert response.json() == {
        "error": "A current exact-location energy create grant is required"
    }
    assert response.headers["cache-control"] == "no-store"
