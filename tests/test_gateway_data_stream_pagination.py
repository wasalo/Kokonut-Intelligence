from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.gateway.router import router

LOCATION_ID = "11111111-1111-4111-8111-111111111111"


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def set_gateway_authorization(request, call_next):
        request.state.gateway_authorization = {"synthetic": True}
        return await call_next(request)

    return app


def test_data_stream_post_list_openapi_declares_page_bounds():
    operation = _app().openapi()["paths"]["/data-stream/posts"]["get"]
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


def test_data_stream_post_list_forwards_explicit_page(monkeypatch):
    calls = []

    def list_posts(location_id, authorization, **kwargs):
        calls.append((location_id, authorization, kwargs))
        return [{"id": "post-1"}]

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
    assert calls == [
        (
            LOCATION_ID,
            {"synthetic": True},
            {"query_text": "soil", "limit": 75, "offset": 125},
        )
    ]


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
