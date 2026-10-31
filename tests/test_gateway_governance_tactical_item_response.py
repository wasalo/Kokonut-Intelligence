"""Strict private response contract for the governance tactical-item queue."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402

LOCATION_ID = str(uuid4())
OPERATOR_ID = str(uuid4())
CURSOR_ID = str(uuid4())
ITEM_IDS = (str(uuid4()), str(uuid4()))


def _item(item_id, *, requested_next_action="Review the irrigation schedule."):
    return {
        "id": UUID(item_id),
        "requested_next_action": requested_next_action,
        "priority": 3,
        "due_at": None,
        "status": "open",
        "created_at": datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
        "session_type": "weekly_review",
        "session_title": "Weekly review",
        "scheduled_at": datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc),
        "session_status": "active",
        "owner_role_key": None,
    }


def _page(*, location_id=LOCATION_ID, items=None, next_cursor=ITEM_IDS[-1]):
    return {
        "location_id": location_id,
        "items": [_item(item_id) for item_id in ITEM_IDS] if items is None else items,
        "next_cursor": next_cursor,
    }


def _client(monkeypatch, payload, *, service_error=None):
    class InMemoryAudit:
        def __init__(self):
            pass

        def replay_pending(self, _limit=100):
            return 0

        def log(self, **_event):
            return None

        def capture_status(self):
            return "ok"

    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="b" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, *_scope):
            return True

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    calls = []

    def service(operator_id, location_id, **kwargs):
        calls.append((operator_id, location_id, kwargs))
        if service_error is not None:
            raise service_error
        return payload

    monkeypatch.setattr(
        "services.gateway.governance_operations.list_location_governance_tactical_items",
        service,
    )
    client = TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    )
    return client, calls


def test_tactical_item_queue_openapi_documents_strict_projection(monkeypatch):
    client, _calls = _client(monkeypatch, _page())
    schema = client.app.openapi()
    operation = schema["paths"][
        "/operator/api/governance/{location_id}/tactical-items"
    ]["get"]
    response_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    page_name = response_ref.rsplit("/", 1)[-1]
    page_schema = schema["components"]["schemas"][page_name]
    item_ref = page_schema["properties"]["items"]["items"]["$ref"]
    item_schema = schema["components"]["schemas"][item_ref.rsplit("/", 1)[-1]]

    assert page_schema["additionalProperties"] is False
    assert item_schema["additionalProperties"] is False
    assert set(item_schema["properties"]) == {
        "id", "requested_next_action", "priority", "due_at", "status", "created_at",
        "session_type", "session_title", "scheduled_at", "session_status", "owner_role_key",
    }
    assert item_schema["properties"]["priority"]["maximum"] == 5
    assert item_schema["properties"]["priority"]["minimum"] == 1
    assert item_schema["properties"]["requested_next_action"]["minLength"] == 1
    assert item_schema["properties"]["requested_next_action"]["maxLength"] == 4000


def test_tactical_item_queue_preserves_wire_shape_and_binds_location_and_cursor(
    monkeypatch,
):
    payload = _page()
    client, calls = _client(monkeypatch, payload)

    response = client.get(
        f"/operator/api/governance/{LOCATION_ID}/tactical-items",
        params={"limit": 2, "cursor": CURSOR_ID},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["location_id"] == LOCATION_ID
    assert response.json()["next_cursor"] == ITEM_IDS[-1]
    assert len(response.json()["items"]) == 2
    assert calls == [(OPERATOR_ID, LOCATION_ID, {"limit": 2, "cursor": CURSOR_ID})]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(unexpected="private notes"),
        lambda payload: payload.update(location_id=str(uuid4())),
        lambda payload: payload.update(items=[_item(ITEM_IDS[0], requested_next_action=None)]),
        lambda payload: payload.update(items=[_item(ITEM_IDS[0], requested_next_action="")]),
        lambda payload: payload.update(items=[_item(ITEM_IDS[0], requested_next_action="  ")]),
        lambda payload: payload.update(
            items=[_item(ITEM_IDS[0], requested_next_action="x" * 4001)]
        ),
        lambda payload: payload.update(items=[{**payload["items"][0], "priority": 6}]),
        lambda payload: payload.update(items=[{**payload["items"][0], "status": "disposed"}]),
        lambda payload: payload.update(next_cursor=str(uuid4())),
        lambda payload: payload.update(items=[_item(ITEM_IDS[0])], next_cursor=ITEM_IDS[0]),
        lambda payload: payload.update(next_cursor=CURSOR_ID),
        lambda payload: payload.update(items=[_item(CURSOR_ID)], next_cursor=None),
    ],
)
def test_invalid_or_mismatched_tactical_projection_fails_closed(monkeypatch, mutation):
    payload = _page(items=[_item(ITEM_IDS[0])], next_cursor=None)
    mutation(payload)
    client, calls = _client(monkeypatch, payload)

    response = client.get(
        f"/operator/api/governance/{LOCATION_ID}/tactical-items",
        params={"limit": 2, "cursor": CURSOR_ID},
    )

    assert response.status_code == 500
    assert response.json() == {"error": "Governance tactical queue unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert len(calls) == 1


def test_tactical_item_queue_rejects_pages_larger_than_requested_limit(monkeypatch):
    payload = _page(items=[_item(ITEM_IDS[0]), _item(ITEM_IDS[1])], next_cursor=None)
    client, _calls = _client(monkeypatch, payload)

    response = client.get(
        f"/operator/api/governance/{LOCATION_ID}/tactical-items",
        params={"limit": 1, "cursor": CURSOR_ID},
    )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"


def test_tactical_item_queue_preserves_database_error_status_and_retry_header(monkeypatch):
    psycopg2 = pytest.importorskip("psycopg2")
    client, _calls = _client(monkeypatch, None, service_error=psycopg2.Error("synthetic"))

    response = client.get(f"/operator/api/governance/{LOCATION_ID}/tactical-items")

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["retry-after"] == "30"
