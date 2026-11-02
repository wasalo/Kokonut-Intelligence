"""Waste-capture Gateway responses match their migration contracts."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway import waste_management_incidents as incidents
from services.gateway import waste_management_routes
from services.gateway import waste_management_writes as writes

_OPERATOR = "11111111-1111-4111-8111-111111111111"
_LOCATION = "22222222-2222-4222-8222-222222222222"
_OTHER_LOCATION = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_RECORD = "33333333-3333-4333-8333-333333333333"

_CAPTURES = (
    {
        "path": "records",
        "module": writes,
        "function": "create_location_waste_stream_record",
        "id_field": "record_id",
        "date_field": "record_date",
        "status": "recorded",
        "name": "Waste",
    },
    {
        "path": "composting",
        "module": writes,
        "function": "create_location_composting_record",
        "id_field": "record_id",
        "date_field": "compost_date",
        "status": "recorded",
        "name": "Composting",
    },
    {
        "path": "recycling",
        "module": writes,
        "function": "create_location_recycling_record",
        "id_field": "record_id",
        "date_field": "record_date",
        "status": "recorded",
        "name": "Recycling",
    },
    {
        "path": "incidents",
        "module": incidents,
        "function": "create_location_pollution_incident",
        "id_field": "incident_id",
        "date_field": "incident_date",
        "status": "open",
        "name": "Incident",
    },
)


def _response(case, *, location_id=_LOCATION, replayed=False):
    return {
        case["id_field"]: _RECORD,
        "location_id": location_id,
        case["date_field"]: "2026-10-29",
        "status": case["status"],
        "replayed": replayed,
    }


def _client(monkeypatch, case, result):
    monkeypatch.setattr(
        case["module"],
        case["function"],
        lambda *_args, **_kwargs: result["value"],
        raising=False,
    )

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    app = FastAPI()
    router = APIRouter()
    waste_management_routes.register_waste_management_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=_OPERATOR)
        )
        return await call_next(request)

    return TestClient(app)


@pytest.mark.parametrize("case", _CAPTURES, ids=lambda case: case["path"])
def test_capture_routes_return_exact_new_and_replayed_contract(monkeypatch, case):
    result = {"value": _response(case)}
    client = _client(monkeypatch, case, result)
    path = f"/operator/api/waste/{_LOCATION}/{case['path']}"

    created = client.post(path, json={})
    assert created.status_code == 201
    assert created.json() == _response(case)
    assert created.headers["cache-control"] == "no-store"
    assert created.headers["vary"] == "Cookie"

    result["value"] = _response(case, replayed=True)
    replayed = client.post(path, json={})
    assert replayed.status_code == 200
    assert replayed.json() == _response(case, replayed=True)
    assert replayed.headers["cache-control"] == "no-store"


def test_capture_routes_publish_exact_openapi_response_fields(monkeypatch):
    client = _client(monkeypatch, _CAPTURES[0], {"value": _response(_CAPTURES[0])})
    openapi = client.app.openapi()

    for case in _CAPTURES:
        route = f"/operator/api/waste/{{location_id}}/{case['path']}"
        operation = openapi["paths"][route]["post"]
        expected_fields = {
            case["id_field"],
            "location_id",
            case["date_field"],
            "status",
            "replayed",
        }
        for status_code in ("200", "201"):
            schema_ref = operation["responses"][status_code]["content"][
                "application/json"
            ]["schema"]["$ref"]
            schema_name = schema_ref.rsplit("/", 1)[-1]
            schema = openapi["components"]["schemas"][schema_name]
            assert set(schema["properties"]) == expected_fields
            assert set(schema["required"]) == expected_fields
            assert schema["additionalProperties"] is False


@pytest.mark.parametrize("case", _CAPTURES, ids=lambda case: case["path"])
@pytest.mark.parametrize(
    "malformation",
    ("missing_date", "extra_field", "wrong_location", "non_boolean_replay"),
)
def test_capture_routes_reject_malformed_or_cross_location_output_without_store(
    monkeypatch, case, malformation
):
    response_body = _response(case)
    if malformation == "missing_date":
        response_body.pop(case["date_field"])
    elif malformation == "extra_field":
        response_body["unexpected"] = "must not escape"
    elif malformation == "wrong_location":
        response_body["location_id"] = _OTHER_LOCATION
    else:
        response_body["replayed"] = "false"

    client = _client(monkeypatch, case, {"value": response_body})
    response = client.post(
        f"/operator/api/waste/{_LOCATION}/{case['path']}", json={}
    )

    assert response.status_code == 500
    assert response.json() == {"error": f"{case['name']} capture unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
