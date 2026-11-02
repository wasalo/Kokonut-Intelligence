"""Location-scoped Gateway work opportunity and self-claim contracts."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from services.common.tenant_context import TenantContextDenied
from services.gateway import operating_pilot_reads, operating_pilot_writes
from services.gateway.operating_pilot_routes import register_operating_pilot_routes
from services.gateway.operator_auth import auth_route_policy

OPERATOR_ID = "a0000000-0000-4000-8000-000000000001"
LOCATION_ID = "b0000000-0000-4000-8000-000000000001"
WORK_ITEM_ID = "d0000000-0000-4000-8000-000000000001"
REQUEST_ID = "c0000000-0000-4000-8000-000000000001"
CLAIM_ID = "e0000000-0000-4000-8000-000000000001"


def _connection_with_result(result):
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = (result,)
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = False
    return connection, cursor


def test_opportunity_read_sets_claim_own_context_and_uses_read_only_transaction(monkeypatch):
    page = {"items": [], "limit": 20, "offset": 40, "has_more": False}
    connection, cursor = _connection_with_result(page)
    contexts = []
    monkeypatch.setattr(
        operating_pilot_reads,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_reads.get_location_operating_pilot_work_opportunities(
        OPERATOR_ID,
        LOCATION_ID,
        limit=20,
        offset=40,
        connection_factory=lambda: connection,
    )

    assert result == {"location_id": LOCATION_ID, **page}
    assert contexts == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "operating_pilot",
                "action": "claim_own",
            },
        )
    ]
    assert "SET TRANSACTION READ ONLY" in cursor.execute.call_args_list[0].args[0]
    assert "location_operating_pilot_work_opportunities" in cursor.execute.call_args_list[3].args[0]
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize("field,value", [("limit", 0), ("offset", -1), ("offset", 10001)])
def test_opportunity_read_rejects_invalid_page_before_database(field, value):
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))
    kwargs = {field: value}

    with pytest.raises(operating_pilot_reads.OperatingPilotReadInvalid):
        operating_pilot_reads.get_location_operating_pilot_work_opportunities(
            OPERATOR_ID, LOCATION_ID, connection_factory=factory, **kwargs
        )

    factory.assert_not_called()


def test_work_claim_sets_exact_context_and_commits_bounded_function_result(monkeypatch):
    connection, cursor = _connection_with_result(
        {"work_item_id": WORK_ITEM_ID, "claim_id": CLAIM_ID, "status": "proposed", "replayed": False}
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.claim_location_operating_pilot_work(
        OPERATOR_ID,
        LOCATION_ID,
        WORK_ITEM_ID,
        REQUEST_ID,
        {"proposed_effort_hours": "6.25"},
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "work_item_id": WORK_ITEM_ID,
        "claim_id": CLAIM_ID,
        "status": "proposed",
        "replayed": False,
    }
    assert contexts == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "operating_pilot",
                "action": "claim_own",
            },
        )
    ]
    assert "SET LOCAL statement_timeout" in cursor.execute.call_args_list[0].args[0]
    assert "claim_location_operating_pilot_work" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        WORK_ITEM_ID,
        REQUEST_ID,
        operating_pilot_writes.Decimal("6.25"),
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "body must be an object"),
        ({"proposed_effort_hours": True}, "non-negative decimal"),
        ({"proposed_effort_hours": "NaN"}, "non-negative, at most 100000"),
        ({"proposed_effort_hours": "1.001"}, "non-negative, at most 100000"),
        ({"proposed_effort_hours": "100001"}, "non-negative, at most 100000"),
        ({"capability_evidence": ["unreviewed"]}, "unsupported fields"),
    ],
)
def test_invalid_work_claim_is_rejected_before_database_access(payload, message):
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match=message):
        operating_pilot_writes.claim_location_operating_pilot_work(
            OPERATOR_ID, LOCATION_ID, WORK_ITEM_ID, REQUEST_ID, payload, connection_factory=factory
        )

    factory.assert_not_called()


def _route_app(monkeypatch, read_action, claim_action):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(operating_pilot_reads, "get_location_operating_pilot_work_opportunities", read_action)
    monkeypatch.setattr(operating_pilot_writes, "claim_location_operating_pilot_work", claim_action)
    router = APIRouter()
    register_operating_pilot_routes(router, object(), run_inline, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    return TestClient(app)


def test_work_opportunity_and_claim_routes_are_protected_no_store_contracts(monkeypatch):
    read_action = MagicMock(
        return_value={
            "location_id": LOCATION_ID,
            "scope_configured": True,
            "items": [],
            "limit": 10,
            "offset": 5,
            "has_more": False,
            "next_offset": None,
        }
    )
    claim_action = MagicMock(
        return_value={"work_item_id": WORK_ITEM_ID, "claim_id": CLAIM_ID, "status": "proposed", "replayed": False}
    )
    client = _route_app(monkeypatch, read_action, claim_action)

    response = client.get(f"/operator/api/operating-pilot/{LOCATION_ID}/work-opportunities?limit=10&offset=5")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    read_action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, limit=10, offset=5)

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/work-opportunities/{WORK_ITEM_ID}/claims",
        json={"request_id": REQUEST_ID, "proposed_effort_hours": "6.25"},
    )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    claim_action.assert_called_once_with(
        OPERATOR_ID,
        LOCATION_ID,
        WORK_ITEM_ID,
        REQUEST_ID,
        {"proposed_effort_hours": "6.25"},
    )


def test_work_claim_route_denies_missing_scope_and_rejects_unknown_fields(monkeypatch):
    denied = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _route_app(monkeypatch, MagicMock(return_value={"items": []}), denied)
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/work-opportunities/{WORK_ITEM_ID}/claims"

    response = client.post(path, json={"request_id": REQUEST_ID})
    assert response.status_code == 403

    response = client.post(path, json={"request_id": REQUEST_ID, "private_text": "not accepted"})
    assert response.status_code == 400
    denied.assert_called_once()


def test_work_opportunity_routes_require_exact_claim_own_grant():
    expected = {
        "resource": "operating_pilot",
        "action": "claim_own",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy(
        "GET", f"/operator/api/operating-pilot/{LOCATION_ID}/work-opportunities", enabled=True
    ) == expected
    assert auth_route_policy(
        "POST",
        f"/operator/api/operating-pilot/{LOCATION_ID}/work-opportunities/{WORK_ITEM_ID}/claims",
        enabled=True,
    ) == expected
    assert auth_route_policy(
        "PATCH", f"/operator/api/operating-pilot/{LOCATION_ID}/work-opportunities", enabled=True
    ) is None
