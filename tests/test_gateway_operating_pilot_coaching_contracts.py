"""Strict private response contracts for operating-pilot coaching reads."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from services.gateway.operating_pilot_routes import (
    OperatingPilotOwnCoachingSessionsPage,
    register_operating_pilot_routes,
)
from services.gateway.operator_auth import auth_route_policy

LOCATION_ID = "b0000000-0000-4000-8000-000000000001"
OPERATOR_ID = "b0000000-0000-4000-8000-000000000002"
PARTICIPANT_A = "b0000000-0000-4000-8000-000000000010"
PARTICIPANT_B = "b0000000-0000-4000-8000-000000000011"
SESSION_A = "b0000000-0000-4000-8000-000000000020"
SESSION_B = "b0000000-0000-4000-8000-000000000021"
OTHER_LOCATION = "b0000000-0000-4000-8000-000000000099"

PARTICIPANTS_PATH = "/operator/api/operating-pilot/{location_id}/coaching-participants"
SESSIONS_PATH = "/operator/api/operating-pilot/{location_id}/my-coaching-sessions"


def _participant_page(*, items=None, **updates):
    page = {
        "location_id": LOCATION_ID,
        "items": [
            {"participant_id": PARTICIPANT_A, "display_name": "Ana Rivera"},
            {"participant_id": PARTICIPANT_B, "display_name": "Bea Sol"},
        ] if items is None else items,
        "has_more": True,
        "next_offset": 6,
    }
    page.update(updates)
    return page


def _session_item(session_id=SESSION_A, *, session_date="2026-10-29", **updates):
    item = {
        "session_id": session_id,
        "coachee_name": "Consented participant",
        "session_date": session_date,
        "focus": "Soil observation",
        "commitments": ["Check the cover crop"],
        "wellbeing_check": None,
        "notes": "Private synthetic note",
        "status": "completed",
        "created_at": "2026-10-29T12:00:00+00:00",
    }
    item.update(updates)
    return item


def _sessions_page(*, items=None, **updates):
    page = {
        "location_id": LOCATION_ID,
        "items": [
            _session_item(SESSION_B),
            _session_item(SESSION_A, session_date="2026-10-28"),
        ] if items is None else items,
        "limit": 2,
        "offset": 14,
        "has_more": True,
        "next_offset": 16,
    }
    page.update(updates)
    return page


def _route_app(monkeypatch, reader_name, result):
    calls = []

    def reader(*args, **kwargs):
        calls.append((args, kwargs))
        return deepcopy(result)

    if reader_name is not None:
        monkeypatch.setattr(
            f"services.gateway.operating_pilot_reads.{reader_name}", reader
        )
    app = FastAPI()
    router = APIRouter()

    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(
        router, object(), run_inline, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app, calls


@pytest.mark.parametrize(
    ("path", "item_schema", "page_schema", "item_fields", "page_fields"),
    [
        (
            PARTICIPANTS_PATH,
            "OperatingPilotCoachingParticipantItem",
            "OperatingPilotCoachingParticipantsPage",
            {"participant_id", "display_name"},
            {"location_id", "items", "has_more", "next_offset"},
        ),
        (
            SESSIONS_PATH,
            "OperatingPilotOwnCoachingSessionItem",
            "OperatingPilotOwnCoachingSessionsPage",
            {
                "session_id", "coachee_name", "session_date", "focus",
                "commitments", "wellbeing_check", "notes", "status", "created_at",
            },
            {"location_id", "items", "limit", "offset", "has_more", "next_offset"},
        ),
    ],
)
def test_coaching_read_openapi_publishes_exact_models(
    monkeypatch, path, item_schema, page_schema, item_fields, page_fields
):
    app, _calls = _route_app(monkeypatch, None, {})
    operation = app.openapi()["paths"][path]["get"]
    page_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert page_ref == {"$ref": f"#/components/schemas/{page_schema}"}
    schemas = app.openapi()["components"]["schemas"]
    page = schemas[page_schema]
    item = schemas[item_schema]
    assert set(page["properties"]) == page_fields
    assert set(page["required"]) == page_fields
    assert page["additionalProperties"] is False
    assert set(item["properties"]) == item_fields
    assert set(item["required"]) == item_fields
    assert item["additionalProperties"] is False


def test_coaching_participant_page_binds_location_and_requested_page(monkeypatch):
    page = _participant_page()
    app, calls = _route_app(
        monkeypatch, "get_location_operating_pilot_coaching_participants", page
    )
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/coaching-participants"
            "?q=ana&limit=2&offset=4"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"search": "ana", "limit": 2, "offset": 4})]
    policy = auth_route_policy("GET", f"/operator/api/operating-pilot/{LOCATION_ID}/coaching-participants", enabled=True)
    assert policy == {
        "resource": "operating_pilot", "action": "coach", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }


def test_coaching_participant_source_keeps_deterministic_sql_order():
    migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/612_location_operating_pilot_coaching_participants.sql"
    ).read_text(encoding="utf-8")
    assert "ORDER BY pg_catalog.lower(eligible.display_name), eligible.id" in migration
    assert ") ORDER BY page.page_row" in migration


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(lambda page: page.update(location_id=OTHER_LOCATION), id="wrong-location"),
        pytest.param(lambda page: page.update(private_data="should-not-leak"), id="extra-page-field"),
        pytest.param(lambda page: page.pop("next_offset"), id="missing-page-field"),
        pytest.param(lambda page: page.update(next_offset=5), id="wrong-next-offset"),
        pytest.param(lambda page: page.update(has_more=False), id="terminal-with-offset"),
        pytest.param(lambda page: page.update(items=page["items"][:1]), id="short-continuation"),
        pytest.param(lambda page: page.update(items=page["items"] + [page["items"][1]]), id="duplicate-id"),
        pytest.param(lambda page: page["items"][0].update(display_name=" " * 4), id="blank-name"),
        pytest.param(lambda page: page["items"][0].update(display_name="x" * 256), id="long-name"),
        pytest.param(lambda page: page["items"][0].update(participant_id="not-a-uuid"), id="invalid-id"),
        pytest.param(lambda page: page["items"][0].update(party_id=PARTICIPANT_A), id="identity-leak-field"),
    ],
)
def test_malformed_coaching_participant_response_is_sanitized(monkeypatch, mutation):
    page = _participant_page()
    mutation(page)
    app, _calls = _route_app(
        monkeypatch, "get_location_operating_pilot_coaching_participants", page
    )
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/coaching-participants"
            "?limit=2&offset=4"
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Coaching participant lookup unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "should-not-leak" not in response.text


def test_own_coaching_page_binds_location_page_and_private_projection(monkeypatch):
    page = _sessions_page()
    app, calls = _route_app(
        monkeypatch, "get_location_operating_pilot_own_coaching_sessions", page
    )
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-coaching-sessions"
            "?limit=2&offset=14"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == OperatingPilotOwnCoachingSessionsPage.model_validate(
        page
    ).model_dump(mode="json")
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 2, "offset": 14})]
    assert "coachee_party_id" not in response.json()["items"][0]
    policy = auth_route_policy("GET", f"/operator/api/operating-pilot/{LOCATION_ID}/my-coaching-sessions", enabled=True)
    assert policy == {
        "resource": "operating_pilot", "action": "coach", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(lambda page: page.update(location_id=OTHER_LOCATION), id="wrong-location"),
        pytest.param(lambda page: page.update(limit=3), id="wrong-limit"),
        pytest.param(lambda page: page.update(offset=13), id="wrong-offset"),
        pytest.param(lambda page: page.update(private_data="should-not-leak"), id="extra-page-field"),
        pytest.param(lambda page: page["items"][0].update(coachee_party_id=PARTICIPANT_A), id="party-id-leak-field"),
        pytest.param(lambda page: page["items"][0].update(status="draft"), id="non-completed-status"),
        pytest.param(lambda page: page["items"][0].update(session_id="not-a-uuid"), id="invalid-session-id"),
        pytest.param(lambda page: page["items"][0].update(focus=""), id="empty-focus"),
        pytest.param(lambda page: page["items"][0].update(notes="x" * 4001), id="notes-too-long"),
        pytest.param(lambda page: page["items"][0].update(wellbeing_check="x" * 1001), id="wellbeing-too-long"),
        pytest.param(lambda page: page["items"][0].update(commitments=["ok"] * 21), id="too-many-commitments"),
        pytest.param(lambda page: page["items"][0].update(commitments=["x" * 501]), id="commitment-too-long"),
        pytest.param(lambda page: page["items"][0].update(created_at="2026-10-29T12:00:00"), id="naive-created-at"),
        pytest.param(lambda page: page.update(next_offset=15), id="wrong-next-offset"),
        pytest.param(lambda page: page.update(items=page["items"][:1]), id="short-continuation"),
        pytest.param(lambda page: page["items"].reverse(), id="wrong-session-order"),
        pytest.param(lambda page: page["items"][1].update(session_id=page["items"][0]["session_id"]), id="duplicate-session-id"),
    ],
)
def test_malformed_own_coaching_response_is_sanitized(monkeypatch, mutation):
    page = _sessions_page()
    mutation(page)
    app, _calls = _route_app(
        monkeypatch, "get_location_operating_pilot_own_coaching_sessions", page
    )
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-coaching-sessions"
            "?limit=2&offset=14"
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Own coaching-session history unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "Private synthetic note" not in response.text
