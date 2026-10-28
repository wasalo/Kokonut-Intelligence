"""Strict private response contract for the Delphi participant workspace."""

import json

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.delphi_participant_routes import (  # noqa: E402
    _DelphiParticipantWorkspaceResponse,
)

SESSION = "11" * 32
STUDY_ID = "44444444-4444-4444-8444-444444444444"


def _item(item_id="33333333-3333-4333-8333-333333333333"):
    return {
        "item_id": item_id,
        "label": "Water resilience",
        "description": None,
        "item_type": "issue",
        "scale": "desirability",
        "minimum": -1,
        "maximum": 1,
        "my_score": 0.5,
        "my_reasoning": "A private participant answer",
        "my_updated_at": "2026-10-28T12:00:00+00:00",
    }


def _workspace(*, limit=2, offset=0, items=None, has_more=False):
    return {
        "study": {
            "study_id": STUDY_ID,
            "title": "Water resilience",
            "status": "open",
            "opened_at": "2026-10-20T12:00:00+00:00",
            "closed_at": None,
        },
        "items": [_item()] if items is None else items,
        "has_more": has_more,
        "limit": limit,
        "offset": offset,
        "collection_scopes": ["questionnaire_responses", "minority_reports"],
    }


def _app(payload, calls):
    from services.gateway.delphi_participant_routes import register_delphi_participant_routes

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return payload

    app = FastAPI()
    router = APIRouter()
    register_delphi_participant_routes(router, run_in_threadpool, __import__("psycopg2"))
    app.include_router(router, prefix="/api")
    return app


def _client(payload, calls):
    client = TestClient(_app(payload, calls), base_url="https://testserver")
    client.cookies.set(
        "kokonut_delphi_participant_session",
        SESSION,
        path="/api/participation/delphi",
    )
    return client


def test_workspace_openapi_documents_strict_source_projection():
    app = _app(_workspace(), [])
    operation = app.openapi()["paths"]["/api/participation/delphi/workspace"]["get"]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("DelphiParticipantWorkspaceResponse")
    assert {parameter["name"] for parameter in operation["parameters"]} >= {"limit", "offset"}


def test_workspace_response_preserves_shape_and_binds_requested_page():
    calls = []
    payload = _workspace(limit=20, offset=40)

    response = _client(payload, calls).get(
        "/api/participation/delphi/workspace?limit=20&offset=40"
    )

    assert response.status_code == 200
    assert response.json() == payload
    assert response.headers["cache-control"] == "no-store"
    assert calls[0][1] == (SESSION,)
    assert calls[0][2] == {"limit": 20, "offset": 40}


@pytest.mark.parametrize(
    "scopes",
    [
        [],
        ["questionnaire_responses"],
        ["minority_reports"],
        ["questionnaire_responses", "minority_reports"],
    ],
)
def test_workspace_accepts_only_migration_641_consent_scopes(scopes):
    calls = []
    payload = _workspace(limit=2, offset=0, items=[], has_more=False)
    payload["collection_scopes"] = scopes

    response = _client(payload, calls).get("/api/participation/delphi/workspace?limit=2")

    assert response.status_code == 200
    assert response.json()["collection_scopes"] == scopes


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.pop("collection_scopes"),
        lambda payload: payload.update(unexpected=True),
        lambda payload: payload.update(limit=1),
        lambda payload: payload.update(offset=1),
        lambda payload: payload.update(collection_scopes=["network_identity"]),
        lambda payload: payload.update(collection_scopes=["minority_reports"] * 2),
        lambda payload: payload.update(study={**payload["study"], "status": "published"}),
        lambda payload: payload.update(items=[{**payload["items"][0], "item_type": "text"}]),
        lambda payload: payload.update(items=[{**payload["items"][0], "my_score": float("nan")}]),
        lambda payload: payload.update(items=[{**payload["items"][0], "minimum": 1, "maximum": 1}]),
        lambda payload: payload.update(has_more=True),
    ],
)
def test_invalid_or_request_mismatched_projection_fails_closed(mutate):
    calls = []
    payload = _workspace(limit=2, offset=5)
    mutate(payload)

    response = _client(payload, calls).get(
        "/api/participation/delphi/workspace?limit=2&offset=5"
    )

    assert response.status_code == 503
    assert response.json() == {"error": "Delphi participant service unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["retry-after"] == "30"
    assert len(calls) == 1


def test_workspace_page_item_count_cannot_exceed_requested_limit():
    calls = []
    payload = _workspace(limit=1, offset=0, items=[_item(), _item("55555555-5555-4555-8555-555555555555")])

    response = _client(payload, calls).get("/api/participation/delphi/workspace?limit=1")

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"


def test_terminal_page_disables_unrequestable_continuation():
    calls = []
    payload = _workspace(
        limit=50,
        offset=10_000,
        items=[_item(f"{index:08x}-4444-4444-8444-444444444444") for index in range(1, 51)],
        has_more=True,
    )

    response = _client(payload, calls).get(
        "/api/participation/delphi/workspace?limit=50&offset=10000"
    )

    assert response.status_code == 200
    assert response.json()["has_more"] is False
    assert response.json()["offset"] == 10_000


def test_response_model_exposes_only_contract_fields():
    payload = _workspace()
    validated = _DelphiParticipantWorkspaceResponse.model_validate_json(
        json.dumps(payload), strict=True
    )

    assert set(validated.model_dump()) == {
        "study", "items", "has_more", "limit", "offset", "collection_scopes"
    }
