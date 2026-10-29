from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.gateway.router import router

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
POST_ID = "22222222-2222-4222-8222-222222222222"
CREATOR_ID = "33333333-3333-4333-8333-333333333333"
CREATED_AT = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def _post_record(**updates):
    record = {
        "id": UUID(POST_ID),
        "location_id": UUID(LOCATION_ID),
        "post_type": "monitoring_report",
        "title": "Soil cover observation",
        "content": "Observed continuous soil cover in the north plot.",
        "visibility": "internal",
        "status": "verified",
        "is_anchored": False,
        "attestation_uid": None,
        "chain": "celo",
        "anchored_at": None,
        "content_hash": "a" * 64,
        "created_at": CREATED_AT,
        "created_by": UUID(CREATOR_ID),
        "expires_at": None,
        "search_rank": 0.375,
    }
    record.update(updates)
    return record


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def set_gateway_authorization(request, call_next):
        request.state.gateway_authorization = {"synthetic": True}
        return await call_next(request)

    return app


def test_data_stream_post_list_openapi_declares_page_bounds():
    schema = _app().openapi()
    operation = schema["paths"]["/data-stream/posts"]["get"]
    parameters = {item["name"]: item for item in operation["parameters"]}

    assert parameters["limit"]["schema"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 100,
        "default": 20,
        "title": "Limit",
    }
    assert parameters["offset"]["schema"] == {
        "type": "integer",
        "minimum": 0,
        "maximum": 5000,
        "default": 0,
        "title": "Offset",
    }
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    envelope_name = response_schema["$ref"].rsplit("/", 1)[-1]
    envelope = schema["components"]["schemas"][envelope_name]
    assert set(envelope["properties"]) == {"data"}
    record_ref = envelope["properties"]["data"]["items"]["$ref"]
    record_name = record_ref.rsplit("/", 1)[-1]
    assert set(schema["components"]["schemas"][record_name]["properties"]) == set(
        _post_record()
    )


def test_data_stream_post_list_forwards_explicit_page(monkeypatch):
    calls = []

    def list_posts(location_id, authorization, **kwargs):
        calls.append((location_id, authorization, kwargs))
        return [_post_record()]

    monkeypatch.setattr(
        "services.gateway.data_stream.list_gateway_data_stream_posts",
        list_posts,
    )
    response = TestClient(_app()).get(
        "/data-stream/posts",
        params={
            "location_id": LOCATION_ID,
            "q": "soil",
            "limit": 75,
            "offset": 125,
        },
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "data": [
            {
                "id": POST_ID,
                "location_id": LOCATION_ID,
                "post_type": "monitoring_report",
                "title": "Soil cover observation",
                "content": "Observed continuous soil cover in the north plot.",
                "visibility": "internal",
                "status": "verified",
                "is_anchored": False,
                "attestation_uid": None,
                "chain": "celo",
                "anchored_at": None,
                "content_hash": "a" * 64,
                "created_at": "2026-10-28T12:00:00+00:00",
                "created_by": CREATOR_ID,
                "expires_at": None,
                "search_rank": 0.375,
            }
        ]
    }
    assert calls == [
        (
            LOCATION_ID,
            {"synthetic": True},
            {"query_text": "soil", "limit": 75, "offset": 125},
        )
    ]


@pytest.mark.parametrize(
    "updates",
    [
        {"unexpected": "not part of the SQL projection"},
        {"status": "pending"},
        {"search_rank": float("nan")},
    ],
)
def test_data_stream_post_list_rejects_malformed_or_extra_fields(monkeypatch, updates):
    monkeypatch.setattr(
        "services.gateway.data_stream.list_gateway_data_stream_posts",
        lambda *_args, **_kwargs: [_post_record(**updates)],
    )

    response = TestClient(_app()).get(
        "/data-stream/posts", params={"location_id": LOCATION_ID}
    )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Data Stream posts unavailable"}


def test_data_stream_post_list_rejects_rows_from_another_location(monkeypatch):
    other_location = UUID("44444444-4444-4444-8444-444444444444")
    monkeypatch.setattr(
        "services.gateway.data_stream.list_gateway_data_stream_posts",
        lambda *_args, **_kwargs: [_post_record(location_id=other_location)],
    )

    response = TestClient(_app()).get(
        "/data-stream/posts", params={"location_id": LOCATION_ID}
    )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Data Stream posts unavailable"}


def test_invalid_data_stream_post_page_is_rejected_before_reader(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("reader must not run for invalid page parameters")

    monkeypatch.setattr(
        "services.gateway.data_stream.list_gateway_data_stream_posts",
        fail_if_called,
    )
    client = TestClient(_app())

    for params in (
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"offset": 5001},
        {"limit": "not-an-integer"},
    ):
        response = client.get(
            "/data-stream/posts",
            params={"location_id": LOCATION_ID, **params},
        )
        assert response.status_code == 422
