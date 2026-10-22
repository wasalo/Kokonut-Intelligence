"""Exact-location, draft-only operating-pilot Gateway writes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from services.common.tenant_context import TenantContextDenied
from services.gateway import operating_pilot_writes
from services.gateway.operating_pilot_routes import register_operating_pilot_routes
from services.gateway.operator_auth import auth_route_policy

OPERATOR_ID = "a0000000-0000-4000-8000-000000000001"
LOCATION_ID = "b0000000-0000-4000-8000-000000000001"
REQUEST_ID = "c0000000-0000-4000-8000-000000000001"
PAYLOAD = {
    "work_type": "soil preparation",
    "period_start": "2026-11-01",
    "period_end": "2026-11-30",
    "required_hours": "18.50",
    "priority": "high",
    "description": "Private synthetic planning note",
}


def _connection_with_result(result):
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = (result,)
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = False
    return connection, cursor


def test_demand_draft_sets_exact_create_context_and_commits_function_result(monkeypatch):
    connection, cursor = _connection_with_result({"signal_id": REQUEST_ID, "status": "draft", "replayed": False})
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.create_location_operating_pilot_demand_draft(
        OPERATOR_ID,
        LOCATION_ID,
        REQUEST_ID,
        PAYLOAD,
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "signal_id": REQUEST_ID,
        "status": "draft",
        "replayed": False,
    }
    assert contexts == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "operating_pilot",
                "action": "create",
            },
        )
    ]
    assert "SET LOCAL statement_timeout" in cursor.execute.call_args_list[0].args[0]
    assert "create_location_operating_pilot_demand_draft" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        REQUEST_ID,
        "soil preparation",
        operating_pilot_writes.date(2026, 11, 1),
        operating_pilot_writes.date(2026, 11, 30),
        operating_pilot_writes.Decimal("18.50"),
        "high",
        "Private synthetic planning note",
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"work_type": " "}, "Work type"),
        ({"period_start": "2026-02-30"}, "period_start"),
        ({"period_start": "2026-12-01", "period_end": "2026-11-30"}, "period must be ordered"),
        ({"period_end": "2027-12-02"}, "no longer than 367 days"),
        ({"required_hours": True}, "positive decimal"),
        ({"required_hours": "NaN"}, "positive, at most 100000"),
        ({"required_hours": "1.001"}, "positive, at most 100000"),
        ({"priority": "urgent"}, "Priority"),
        ({"description": "x" * 2001}, "Description"),
        ({"actor_party_id": OPERATOR_ID}, "unsupported fields"),
    ],
)
def test_invalid_demand_draft_is_rejected_before_database_access(changes, message):
    payload = {**PAYLOAD, **changes}
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match=message):
        operating_pilot_writes.create_location_operating_pilot_demand_draft(
            OPERATOR_ID, LOCATION_ID, REQUEST_ID, payload, connection_factory=factory
        )

    factory.assert_not_called()


def test_demand_draft_failure_rolls_back_and_closes_connection(monkeypatch):
    connection, cursor = _connection_with_result(None)
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(RuntimeError, match="returned no result"):
        operating_pilot_writes.create_location_operating_pilot_demand_draft(
            OPERATOR_ID,
            LOCATION_ID,
            REQUEST_ID,
            PAYLOAD,
            connection_factory=lambda: connection,
        )

    connection.commit.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def _route_app(monkeypatch, action):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(operating_pilot_writes, "create_location_operating_pilot_demand_draft", action)
    router = APIRouter()
    register_operating_pilot_routes(router, object(), run_inline, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    return TestClient(app)


def test_demand_draft_http_route_passes_request_id_and_uses_no_store(monkeypatch):
    action = MagicMock(return_value={"signal_id": REQUEST_ID, "status": "draft", "replayed": False})
    client = _route_app(monkeypatch, action)

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals",
        json={**PAYLOAD, "request_id": REQUEST_ID},
    )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["status"] == "draft"
    action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, REQUEST_ID, PAYLOAD)


def test_demand_draft_http_route_returns_403_when_signed_context_is_denied(monkeypatch):
    action = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _route_app(monkeypatch, action)

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals",
        json={**PAYLOAD, "request_id": REQUEST_ID},
    )

    assert response.status_code == 403
    assert "create access" in response.json()["error"]


def test_demand_draft_route_policy_requires_exact_location_create_grant():
    assert auth_route_policy(
        "POST",
        f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals",
        enabled=True,
    ) == {
        "resource": "operating_pilot",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert (
        auth_route_policy(
            "POST",
            f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals",
            enabled=False,
        )
        is None
    )
