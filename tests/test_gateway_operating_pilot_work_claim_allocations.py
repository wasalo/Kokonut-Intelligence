"""Gateway contracts for explicit operating-pilot work-claim allocation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from services.common.tenant_context import TenantContextDenied
from services.gateway import operating_pilot_reads, operating_pilot_writes
from services.gateway.operating_pilot_routes import register_operating_pilot_routes

OPERATOR_ID = "a0000000-0000-4000-8000-000000000001"
LOCATION_ID = "b0000000-0000-4000-8000-000000000001"
CLAIM_ID = "e5100000-0000-4000-8000-000000000001"
REQUEST_ID = "c0000000-0000-4000-8000-000000000001"
WORK_ITEM_ID = "f5100000-0000-4000-8000-000000000001"


def _allocation_item(**overrides):
    result = {
        "claim_id": CLAIM_ID,
        "work_item_id": WORK_ITEM_ID,
        "claimant_name": "Ada Operator",
        "title": "Prepare a soil observation",
        "work_type": "monitoring",
        "priority": "high",
        "estimated_effort_hours": 4.0,
        "proposed_effort_hours": 3.5,
        "due_at": "2026-11-01T12:00:00+00:00",
        "accepted_at": "2026-10-28T12:00:00+00:00",
    }
    return {**result, **overrides}


def _allocation_queue(**overrides):
    result = {
        "location_id": LOCATION_ID,
        "scope_configured": True,
        "limit": 25,
        "offset": 0,
        "items": [],
        "has_more": False,
        "next_offset": None,
    }
    return {**result, **overrides}


def _connection_with_result(result):
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = (result,)
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = False
    return connection, cursor


def test_allocation_queue_sets_exact_context_and_uses_read_only_transaction(monkeypatch):
    page = {"items": [], "limit": 20, "offset": 40, "has_more": False}
    connection, cursor = _connection_with_result(page)
    contexts = []
    monkeypatch.setattr(
        operating_pilot_reads,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_reads.get_location_operating_pilot_work_claim_allocation_queue(
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
                "action": "allocate",
            },
        )
    ]
    assert "SET TRANSACTION READ ONLY" in cursor.execute.call_args_list[0].args[0]
    assert "location_operating_pilot_work_claim_allocation_queue" in cursor.execute.call_args_list[3].args[0]
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), (25, -1), (25, 10001)])
def test_allocation_queue_rejects_invalid_page_before_database(limit, offset):
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_reads.OperatingPilotReadInvalid):
        operating_pilot_reads.get_location_operating_pilot_work_claim_allocation_queue(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset, connection_factory=factory
        )

    factory.assert_not_called()


def test_allocation_write_sets_exact_context_calls_bounded_function_and_commits(monkeypatch):
    result_payload = {
        "claim_id": CLAIM_ID,
        "allocation_status": "allocated",
        "replayed": False,
    }
    connection, cursor = _connection_with_result(result_payload)
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.allocate_location_operating_pilot_work_claim(
        OPERATOR_ID,
        LOCATION_ID,
        CLAIM_ID,
        REQUEST_ID,
        connection_factory=lambda: connection,
    )

    assert result == {"location_id": LOCATION_ID, **result_payload}
    assert contexts == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "operating_pilot",
                "action": "allocate",
            },
        )
    ]
    assert "SET LOCAL statement_timeout" in cursor.execute.call_args_list[0].args[0]
    assert "allocate_location_operating_pilot_work_claim" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (LOCATION_ID, CLAIM_ID, REQUEST_ID)
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("claim_id", "request_id"),
    [("bad-claim", REQUEST_ID), (CLAIM_ID, "bad-request")],
)
def test_invalid_allocation_identifiers_fail_before_database(claim_id, request_id):
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid):
        operating_pilot_writes.allocate_location_operating_pilot_work_claim(
            OPERATOR_ID,
            LOCATION_ID,
            claim_id,
            request_id,
            connection_factory=factory,
        )

    factory.assert_not_called()


def _route_app(monkeypatch, read_action, write_action):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(
        operating_pilot_reads,
        "get_location_operating_pilot_work_claim_allocation_queue",
        read_action,
    )
    monkeypatch.setattr(
        operating_pilot_writes,
        "allocate_location_operating_pilot_work_claim",
        write_action,
    )
    router = APIRouter()
    register_operating_pilot_routes(router, object(), run_inline, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return TestClient(app)


def test_allocation_routes_are_protected_no_store_and_use_expected_arguments(monkeypatch):
    read_action = MagicMock(
        return_value=_allocation_queue(items=[_allocation_item()], limit=10, offset=5)
    )
    write_action = MagicMock(
        return_value={
            "location_id": LOCATION_ID,
            "claim_id": CLAIM_ID,
            "work_item_id": WORK_ITEM_ID,
            "allocation_status": "allocated",
            "replayed": False,
        }
    )
    client = _route_app(monkeypatch, read_action, write_action)

    response = client.get(
        f"/operator/api/operating-pilot/{LOCATION_ID}/work-claim-allocation-queue?limit=10&offset=5"
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["items"][0]["claimant_name"] == "Ada Operator"
    read_action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, limit=10, offset=5)

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/work-claims/{CLAIM_ID}/allocate",
        json={"request_id": REQUEST_ID},
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    write_action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, CLAIM_ID, REQUEST_ID)


def test_allocation_route_rejects_unknown_fields_and_returns_scope_denial(monkeypatch):
    denied = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _route_app(monkeypatch, MagicMock(return_value=_allocation_queue()), denied)
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/work-claims/{CLAIM_ID}/allocate"

    response = client.post(path, json={"request_id": REQUEST_ID, "claimant_party_id": OPERATOR_ID})
    assert response.status_code == 400
    denied.assert_not_called()

    response = client.post(path, json={"request_id": REQUEST_ID})
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    denied.assert_called_once()


def test_allocation_queue_scope_denial_is_forbidden_and_uncached(monkeypatch):
    denied = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _route_app(monkeypatch, denied, MagicMock())

    response = client.get(
        f"/operator/api/operating-pilot/{LOCATION_ID}/work-claim-allocation-queue"
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": "Tenant-qualified operating-pilot allocation access is required"
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    denied.assert_called_once()


def test_allocation_queue_publishes_exact_openapi_contract_with_identity_field(monkeypatch):
    client = _route_app(monkeypatch, MagicMock(return_value=_allocation_queue()), MagicMock())
    schema = client.app.openapi()
    operation = schema["paths"][
        "/operator/api/operating-pilot/{location_id}/work-claim-allocation-queue"
    ]["get"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/OperatingPilotWorkClaimAllocationQueueResponse"
    }
    schemas = schema["components"]["schemas"]
    item = schemas["OperatingPilotWorkClaimAllocationQueueItem"]
    assert item["additionalProperties"] is False
    assert set(item["properties"]) == {
        "claim_id",
        "work_item_id",
        "claimant_name",
        "title",
        "work_type",
        "priority",
        "estimated_effort_hours",
        "proposed_effort_hours",
        "due_at",
        "accepted_at",
    }
    assert schemas["OperatingPilotWorkClaimAllocationQueueResponse"][
        "additionalProperties"
    ] is False


@pytest.mark.parametrize(
    "result",
    [
        _allocation_queue(location_id="99999999-9999-4999-8999-999999999999"),
        _allocation_queue(offset=1),
        _allocation_queue(has_more=True, next_offset=25),
        _allocation_queue(items=[_allocation_item(private_contact="secret@example.com")]),
        _allocation_queue(items=[_allocation_item(accepted_at=None)]),
        _allocation_queue(items=[_allocation_item(claimant_name=None)]),
        _allocation_queue(items=[_allocation_item(), _allocation_item()]),
        _allocation_queue(
            items=[
                _allocation_item(),
                _allocation_item(
                    claim_id="e5110000-0000-4000-8000-000000000001",
                    priority="critical",
                ),
            ]
        ),
    ],
)
def test_allocation_route_rejects_malformed_page_and_never_exposes_it(monkeypatch, result):
    route_client = _route_app(monkeypatch, MagicMock(return_value=result), MagicMock())
    with route_client as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/work-claim-allocation-queue?limit=25&offset=0"
        )

    assert response.status_code == 503
    assert response.json() == {"error": "Operating work-claim allocation queue unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.headers["retry-after"] == "30"
    assert "secret@example.com" not in response.text
