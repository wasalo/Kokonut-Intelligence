"""Strict private response contracts for pollinator detail and review reads."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

LOCATION_ID = "22222222-2222-4222-8222-222222222222"
RECORD_ID = "33333333-3333-4333-8333-333333333333"
OPERATOR_ID = "11111111-1111-4111-8111-111111111111"


def _habitat_page(*, location_id=LOCATION_ID, limit=5, offset=10):
    return {
        "location_id": location_id,
        "limit": limit,
        "offset": offset,
        "habitats": [{
            "id": RECORD_ID,
            "habitat_name": "North buffer",
            "habitat_type": "hedgerow",
            "area_m2": 123.5,
            "condition": "good",
            "status": "active",
            "last_maintenance": "2026-10-20",
            "updated_at": "2026-10-25T12:34:00+00:00",
        }],
        "has_more": False,
        "next_offset": None,
    }


def _hive_page(*, location_id=LOCATION_ID, limit=5, offset=10):
    return {
        "location_id": location_id,
        "limit": limit,
        "offset": offset,
        "hives": [{
            "id": RECORD_ID,
            "hive_id": "Hive-7",
            "hive_type": "langstroth",
            "status": "active",
            "colony_strength": "moderate",
            "colony_strength_score": 6,
            "queen_status": "present",
            "frame_count": 10,
            "inspection_date": "2026-10-20",
            "last_maintenance_date": "2026-10-21",
            "updated_at": "2026-10-25T12:34:00+00:00",
        }],
        "has_more": False,
        "next_offset": None,
    }


def _review_page(*, location_id=LOCATION_ID, limit=5, offset=10):
    return {
        "location_id": location_id,
        "limit": limit,
        "offset": offset,
        "items": [{
            "record_id": RECORD_ID,
            "record_type": "observation",
            "occurred_on": "2026-10-24",
            "status": "recorded",
            "created_at": "2026-10-25T12:34:00+00:00",
            "updated_at": "2026-10-25T12:35:00+00:00",
            "details": {
                "pollinator_type": "wild_bee",
                "count": 10,
                "method": "transect",
                "duration_minutes": 20,
                "species_name": "Native bee",
                "notes": "Field observation",
            },
        }],
        "has_more": False,
        "next_offset": None,
        "total": 11,
    }


def _review_variant(record_type, details):
    page = _review_page()
    page["items"][0]["record_type"] = record_type
    page["items"][0]["details"] = details
    return page


def _app(monkeypatch, *, habitat=None, hive=None, review=None):
    import psycopg2

    from services.gateway import pollinator_health_reads, pollinator_health_routes

    monkeypatch.setattr(
        pollinator_health_reads,
        "get_location_pollinator_habitat_details",
        lambda *_args, **_kwargs: habitat,
    )
    monkeypatch.setattr(
        pollinator_health_reads,
        "get_location_pollinator_hive_details",
        lambda *_args, **_kwargs: hive,
    )
    monkeypatch.setattr(
        pollinator_health_reads,
        "list_location_pollinator_review_queue",
        lambda *_args, **_kwargs: review,
    )

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    router = APIRouter()
    pollinator_health_routes.register_pollinator_health_routes(
        router, object(), run_in_threadpool, psycopg2
    )
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


@pytest.mark.parametrize(
    ("path", "response_key", "model_name", "payload_factory"),
    [
        ("habitats", "habitats", "PollinatorHabitatDetailPage", _habitat_page),
        ("hives", "hives", "PollinatorHiveDetailPage", _hive_page),
        ("review-queue", "items", "PollinatorReviewQueuePage", _review_page),
    ],
)
def test_pollinator_detail_reads_publish_strict_openapi_models(
    monkeypatch, path, response_key, model_name, payload_factory
):
    result = payload_factory()
    app = _app(
        monkeypatch,
        habitat=result if path == "habitats" else None,
        hive=result if path == "hives" else None,
        review=result if path == "review-queue" else None,
    )
    response_schema = app.openapi()["paths"][
        f"/operator/api/pollinators/{{location_id}}/{path}"
    ]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema == {"$ref": f"#/components/schemas/{model_name}"}
    assert app.openapi()["components"]["schemas"][model_name]["additionalProperties"] is False

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/pollinators/{LOCATION_ID}/{path}?limit=5&offset=10"
        )

    assert response.status_code == 200
    assert response.json()[response_key]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


@pytest.mark.parametrize(
    ("path", "payload_factory", "mutate"),
    [
        (
            "habitats", _habitat_page,
            lambda page: page["habitats"][0].update(notes="private"),
        ),
        (
            "habitats", _habitat_page,
            lambda page: page["habitats"][0].update(habitat_type="unknown"),
        ),
        (
            "habitats", _habitat_page,
            lambda page: page.update(next_offset=15),
        ),
        (
            "hives", _hive_page,
            lambda page: page["hives"][0].update(metadata={"secret": True}),
        ),
        (
            "hives", _hive_page,
            lambda page: page["hives"][0].update(status="unknown"),
        ),
        (
            "review-queue", _review_page,
            lambda page: page["items"][0]["details"].update(private_id="secret"),
        ),
        (
            "review-queue", _review_page,
            lambda page: page["items"][0]["details"].update(count=True),
        ),
        (
            "review-queue", _review_page,
            lambda page: page["items"][0].update(record_type="pesticide_impact"),
        ),
    ],
)
def test_pollinator_detail_reads_reject_malformed_service_projection(
    monkeypatch, path, payload_factory, mutate
):
    result = deepcopy(payload_factory())
    mutate(result)
    app = _app(
        monkeypatch,
        habitat=result if path == "habitats" else None,
        hive=result if path == "hives" else None,
        review=result if path == "review-queue" else None,
    )

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/pollinators/{LOCATION_ID}/{path}?limit=5&offset=10"
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "habitats": "Pollinator habitat details unavailable",
            "hives": "Managed-hive details unavailable",
            "review-queue": "Pollinator review queue unavailable",
        }[path]
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_pollinator_detail_routes_reject_request_mismatched_pages(monkeypatch):
    habitat = _habitat_page(offset=9)
    app = _app(monkeypatch, habitat=habitat)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/pollinators/{LOCATION_ID}/habitats?limit=5&offset=10"
        )
    assert response.status_code == 500
    assert response.json() == {"error": "Pollinator habitat details unavailable"}


def test_review_queue_documents_discriminated_detail_shapes(monkeypatch):
    app = _app(monkeypatch, review=_review_page())
    schemas = app.openapi()["components"]["schemas"]
    item_schema = schemas["PollinatorReviewQueuePage"]["properties"]["items"]["items"]
    assert "oneOf" in item_schema
    assert item_schema["discriminator"]["propertyName"] == "record_type"
    for name in (
        "PollinatorObservationReviewDetails",
        "PollinatorPesticideReviewDetails",
        "PollinatorHiveInspectionReviewDetails",
    ):
        assert schemas[name]["additionalProperties"] is False


@pytest.mark.parametrize(
    "page",
    [
        _review_variant("pesticide_impact", {
            "product_name": "Botanical spray",
            "active_ingredient": "Neem",
            "toxicity_class": "low",
            "application_rate": 2,
            "rate_unit": "L/ha",
            "area_treated_m2": 250,
            "bloom_stage_at_application": "post-bloom",
            "pollinator_distance_m": 15,
            "pollinator_safe_period_days": 1,
            "mortality_observed": False,
            "mortality_pct": None,
            "notes": "Report attached",
        }),
        _review_variant("hive_inspection", {
            "hive_id": "Hive-7",
            "colony_strength": "moderate",
            "colony_strength_score": 6,
            "queen_status": "present",
            "queen_seen": True,
            "varroa_count": 2,
            "brood_pattern": "Regular",
            "honey_stores": "Adequate",
            "disease_signs": None,
            "temperament": "Calm",
            "population_estimate": 12000,
            "swarm_cells": False,
            "notes": "Routine inspection",
        }),
    ],
)
def test_review_queue_accepts_each_typed_detail_projection(monkeypatch, page):
    app = _app(monkeypatch, review=page)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/pollinators/{LOCATION_ID}/review-queue?limit=5&offset=10"
        )
    assert response.status_code == 200
    assert response.json()["items"][0]["record_type"] in {
        "pesticide_impact", "hive_inspection"
    }
