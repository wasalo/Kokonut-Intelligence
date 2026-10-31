"""Strict response contracts for private nutrient soil-test and event reads."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
OPERATOR_ID = "22222222-2222-4222-8222-222222222222"
SOIL_TEST_ID = "33333333-3333-4333-8333-333333333333"
EVENT_ID = "44444444-4444-4444-8444-444444444444"
PLOT_ID = "55555555-5555-4555-8555-555555555555"


def _soil_projection(location_id=LOCATION_ID, *, limit=3, offset=2):
    return {
        "location_id": location_id,
        "total_tests": 3,
        "limit": limit,
        "offset": offset,
        "has_more": False,
        "soil_tests": [{
            "test_id": SOIL_TEST_ID,
            "plot_id": PLOT_ID,
            "test_date": "2026-10-24",
            "status": "verified",
            "measurements": {
                "soil_ph": 6.2,
                "organic_matter_pct": 4.5,
                "nitrogen_ppm": 18.0,
                "phosphorus_ppm": 12.0,
                "potassium_ppm": 95.0,
                "cec": 7.1,
            },
            "recommendations_kg_ha": {
                "nitrogen": 42.0,
                "phosphorus": 18.0,
                "potassium": 30.0,
            },
        }],
    }


def _event_projection(event_type, location_id=LOCATION_ID, *, limit=3, offset=2):
    event = {
        "event_id": EVENT_ID,
        "plot_id": PLOT_ID,
        "season": "2026-wet",
        "budget_crop_name": "maize",
        "budget_status": "draft",
        "event_status": "verified",
        "nutrients_kg": {"nitrogen": 24.0, "phosphorus": 8.0, "potassium": 17.0},
    }
    if event_type == "inputs":
        event.update({
            "input_date": "2026-10-24",
            "input_type": "compost",
            "product_name": "mature compost",
            "application_rate": 120.0,
            "rate_unit": "kg/ha",
            "cost": {"amount": 14.25, "currency_code": "USD"},
            "cost_status": "classified",
        })
    else:
        event.update({
            "harvest_date": "2026-10-24",
            "crop_name": "maize",
            "yield_amount": 1.25,
            "yield_unit": "tonne",
        })
    return {
        "location_id": location_id,
        "event_type": event_type,
        "total_events": 3,
        "limit": limit,
        "offset": offset,
        "has_more": False,
        "events": [event],
    }


def _app(monkeypatch, *, soil=None, events=None):
    from services.gateway import nutrient_balance_routes, nutrient_events, nutrient_soil_tests

    monkeypatch.setattr(
        nutrient_soil_tests,
        "get_location_soil_tests",
        soil or (lambda *_args, **_kwargs: None),
    )
    monkeypatch.setattr(
        nutrient_events,
        "get_location_nutrient_events",
        events or (lambda *_args, **_kwargs: None),
    )

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    app = FastAPI()
    router = APIRouter()
    nutrient_balance_routes.register_nutrient_balance_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


@pytest.mark.parametrize(
    ("path", "reader_name", "projection", "model_name", "response_key"),
    [
        (
            f"/operator/api/nutrients/{LOCATION_ID}/soil-tests",
            "soil",
            _soil_projection(),
            "SoilTestsResponse",
            "soil_tests",
        ),
        (
            f"/operator/api/nutrients/{LOCATION_ID}/events/inputs",
            "events",
            _event_projection("inputs"),
            "NutrientEventsResponse",
            "events",
        ),
        (
            f"/operator/api/nutrients/{LOCATION_ID}/events/removals",
            "events",
            _event_projection("removals"),
            "NutrientEventsResponse",
            "events",
        ),
    ],
)
def test_nutrient_detail_gets_publish_strict_models_and_validate_projection(
    monkeypatch, path, reader_name, projection, model_name, response_key
):
    if reader_name == "soil":
        app = _app(monkeypatch, soil=lambda *_args, **_kwargs: projection)
    else:
        app = _app(monkeypatch, events=lambda *_args, **_kwargs: projection)

    route = path.replace(LOCATION_ID, "{location_id}")
    if "/events/" in path:
        route = route.replace("inputs", "{event_type}").replace("removals", "{event_type}")
    schema = app.openapi()["paths"][route]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith(model_name)

    with TestClient(app) as client:
        response = client.get(path, params={"limit": 3, "offset": 2})

    assert response.status_code == 200
    assert response.json()["location_id"] == LOCATION_ID
    assert response.json()[response_key]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


@pytest.mark.parametrize(
    ("reader_name", "projection", "path", "error"),
    [
        (
            "soil",
            {**_soil_projection(), "soil_tests": [{**_soil_projection()["soil_tests"][0], "notes": "private"}]},
            f"/operator/api/nutrients/{LOCATION_ID}/soil-tests",
            "Nutrient soil tests unavailable",
        ),
        (
            "events",
            {**_event_projection("inputs"), "events": [{**_event_projection("inputs")["events"][0], "private_id": "secret"}]},
            f"/operator/api/nutrients/{LOCATION_ID}/events/inputs",
            "Nutrient events unavailable",
        ),
        (
            "events",
            _event_projection("removals"),
            f"/operator/api/nutrients/{LOCATION_ID}/events/inputs",
            "Nutrient events unavailable",
        ),
    ],
)
def test_nutrient_detail_gets_reject_malformed_or_mismatched_projection(
    monkeypatch, reader_name, projection, path, error
):
    if reader_name == "soil":
        app = _app(monkeypatch, soil=lambda *_args, **_kwargs: projection)
    else:
        app = _app(monkeypatch, events=lambda *_args, **_kwargs: projection)
    with TestClient(app) as client:
        response = client.get(path, params={"limit": 3, "offset": 2})
    assert response.status_code == 500
    assert response.json() == {"error": error}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


@pytest.mark.parametrize("reader_name", ["soil", "events"])
def test_nutrient_detail_pages_stop_continuing_past_offset_ceiling(monkeypatch, reader_name):
    if reader_name == "soil":
        projection = _soil_projection(limit=25, offset=9_976)
        projection["has_more"] = True
        model = "SoilTestsResponse"
        path = f"/operator/api/nutrients/{LOCATION_ID}/soil-tests"
        app = _app(monkeypatch, soil=lambda *_args, **_kwargs: projection)
    else:
        projection = _event_projection("inputs", limit=25, offset=9_976)
        projection["has_more"] = True
        model = "NutrientEventsResponse"
        path = f"/operator/api/nutrients/{LOCATION_ID}/events/inputs"
        app = _app(monkeypatch, events=lambda *_args, **_kwargs: projection)

    with TestClient(app) as client:
        response = client.get(path, params={"limit": 25, "offset": 9_976})
    assert response.status_code == 500
    assert response.json() == {
        "error": "Nutrient soil tests unavailable"
        if model == "SoilTestsResponse"
        else "Nutrient events unavailable"
    }
