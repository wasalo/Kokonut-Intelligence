"""Gateway contracts for independent operating-pilot work-claim review."""

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


def _connection_with_result(result):
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = (result,)
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = False
    return connection, cursor


def test_review_queue_sets_exact_context_and_uses_read_only_transaction(monkeypatch):
    page = {"items": [], "limit": 20, "offset": 40, "has_more": False}
    connection, cursor = _connection_with_result(page)
    contexts = []
    monkeypatch.setattr(
        operating_pilot_reads,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_reads.get_location_operating_pilot_work_claim_review_queue(
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
                "action": "review",
            },
        )
    ]
    assert "SET TRANSACTION READ ONLY" in cursor.execute.call_args_list[0].args[0]
    assert "location_operating_pilot_work_claim_review_queue" in cursor.execute.call_args_list[3].args[0]
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), (25, -1), (25, 10001)])
def test_review_queue_rejects_invalid_page_before_database(limit, offset):
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_reads.OperatingPilotReadInvalid):
        operating_pilot_reads.get_location_operating_pilot_work_claim_review_queue(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset, connection_factory=factory
        )

    factory.assert_not_called()


def test_review_write_sets_exact_context_calls_bounded_function_and_commits(monkeypatch):
    result_payload = {"claim_id": CLAIM_ID, "status": "accepted", "replayed": False}
    connection, cursor = _connection_with_result(result_payload)
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.review_location_operating_pilot_work_claim(
        OPERATOR_ID,
        LOCATION_ID,
        CLAIM_ID,
        REQUEST_ID,
        {"decision": "accepted"},
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
                "action": "review",
            },
        )
    ]
    assert "review_location_operating_pilot_work_claim" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        CLAIM_ID,
        REQUEST_ID,
        "accepted",
        None,
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "body must be an object"),
        ({}, "Decision must be accepted or rejected"),
        ({"decision": "approved"}, "Decision must be accepted or rejected"),
        ({"decision": "rejected"}, "reason is required"),
        ({"decision": "accepted", "reason": "x" * 2001}, "at most 2000"),
        ({"decision": "accepted", "reason": "bad\x00reason"}, "at most 2000"),
        ({"decision": "accepted", "actor_id": OPERATOR_ID}, "unsupported fields"),
    ],
)
def test_invalid_review_payload_fails_before_database(payload, message):
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match=message):
        operating_pilot_writes.review_location_operating_pilot_work_claim(
            OPERATOR_ID, LOCATION_ID, CLAIM_ID, REQUEST_ID, payload, connection_factory=factory
        )

    factory.assert_not_called()


def _route_app(monkeypatch, read_action, write_action):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(
        operating_pilot_reads,
        "get_location_operating_pilot_work_claim_review_queue",
        read_action,
    )
    monkeypatch.setattr(
        operating_pilot_writes,
        "review_location_operating_pilot_work_claim",
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


def test_review_routes_are_protected_no_store_and_use_expected_arguments(monkeypatch):
    read_action = MagicMock(return_value={"items": [], "limit": 25, "offset": 0})
    write_action = MagicMock(
        return_value={"claim_id": CLAIM_ID, "status": "accepted", "replayed": False}
    )
    client = _route_app(monkeypatch, read_action, write_action)

    response = client.get(
        f"/operator/api/operating-pilot/{LOCATION_ID}/work-claim-review-queue?limit=10&offset=5"
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    read_action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, limit=10, offset=5)

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/work-claims/{CLAIM_ID}/review",
        json={"request_id": REQUEST_ID, "decision": "rejected", "reason": "Insufficient details"},
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    write_action.assert_called_once_with(
        OPERATOR_ID,
        LOCATION_ID,
        CLAIM_ID,
        REQUEST_ID,
        {"decision": "rejected", "reason": "Insufficient details"},
    )


def test_review_route_rejects_unknown_fields_and_returns_scope_denial(monkeypatch):
    denied = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _route_app(monkeypatch, MagicMock(return_value={"items": []}), denied)
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/work-claims/{CLAIM_ID}/review"

    response = client.post(path, json={"request_id": REQUEST_ID, "decision": "accepted", "claimant": "x"})
    assert response.status_code == 400
    denied.assert_not_called()

    response = client.post(path, json={"request_id": REQUEST_ID, "decision": "accepted"})
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    denied.assert_called_once()
