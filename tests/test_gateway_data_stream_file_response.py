"""Strict, tenant-bound response contract for Data Stream attachment metadata."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
POST_ID = "33333333-3333-4333-8333-333333333333"
OTHER_POST_ID = "44444444-4444-4444-8444-444444444444"
FILE_ID = "22222222-2222-4222-8222-222222222222"


def _file_row():
    timestamp = datetime(2026, 10, 29, 12, 30, tzinfo=timezone.utc)
    return {
        "id": UUID(FILE_ID),
        "post_id": UUID(POST_ID),
        "file_name": "field-note.jpg",
        "file_description": "Cover crop observation",
        "file_credit": None,
        "media_type": "image",
        "file_size_bytes": 1024,
        "mime_type": "image/jpeg",
        "latitude": Decimal("18.5000000"),
        "longitude": Decimal("-69.9000000"),
        "sort_order": 0,
        "status": "verified",
        "visibility": "private",
        "created_at": timestamp,
        "created_by": None,
        "updated_at": timestamp,
        "updated_by": None,
    }


def _client(monkeypatch, rows):
    monkeypatch.setenv("KOKONUT_API_KEYS", "reader-key:reader")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES",
        f"reader:data_stream_file:read:{LOCATION_ID}",
    )
    calls = []

    def service(*args, **kwargs):
        calls.append((args, kwargs))
        return rows

    monkeypatch.setattr("services.gateway.data_stream.list_gateway_data_stream_files", service)
    return TestClient(create_app()), calls


def _get(client, post_id=POST_ID):
    return client.get(
        f"/api/data-stream/posts/{post_id}/files",
        headers={"x-api-key": "reader-key"},
        params={"location_id": LOCATION_ID},
    )


def test_file_list_openapi_documents_exact_strict_envelope(monkeypatch):
    client, _calls = _client(monkeypatch, [_file_row()])
    schema = client.app.openapi()
    operation = schema["paths"]["/api/data-stream/posts/{post_id}/files"]["get"]
    envelope_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    envelope = schema["components"]["schemas"][envelope_ref.rsplit("/", 1)[-1]]
    record_ref = envelope["properties"]["data"]["items"]["$ref"]
    record = schema["components"]["schemas"][record_ref.rsplit("/", 1)[-1]]

    assert envelope["additionalProperties"] is False
    assert record["additionalProperties"] is False
    assert len(record["properties"]) == 17
    assert set(record["properties"]) == set(_file_row())
    file_size_schema = record["properties"]["file_size_bytes"]["anyOf"][0]
    latitude_schema = record["properties"]["latitude"]["anyOf"][0]
    assert file_size_schema["minimum"] == 0
    assert latitude_schema["type"] == "number"
    assert latitude_schema["minimum"] == -90


def test_file_list_returns_only_validated_private_projection_and_binds_post(monkeypatch):
    row = _file_row()
    client, calls = _client(monkeypatch, [row])

    response = _get(client)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "data": [
            {
                **{key: value for key, value in row.items() if key not in {"latitude", "longitude"}},
                "latitude": 18.5,
                "longitude": -69.9,
                "id": FILE_ID,
                "post_id": POST_ID,
                "created_at": "2026-10-29T12:30:00+00:00",
                "updated_at": "2026-10-29T12:30:00+00:00",
            }
        ]
    }
    assert calls[0][0][:2] == (POST_ID, LOCATION_ID)
    assert calls[0][1] == {"limit": 50, "offset": 0}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda row: row.pop("status"),
        lambda row: row.update(file_url="https://private.example/media.jpg"),
        lambda row: row.update(directus_file_id=UUID("55555555-5555-4555-8555-555555555555")),
        lambda row: row.update(status="archived"),
        lambda row: row.update(visibility="unlisted"),
        lambda row: row.update(latitude=Decimal("91")),
        lambda row: row.update(longitude=None),
    ],
)
def test_malformed_or_sensitive_file_rows_fail_closed(monkeypatch, mutate):
    row = _file_row()
    mutate(row)
    client, _calls = _client(monkeypatch, [row])

    response = _get(client)

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Data Stream attachments unavailable"}
    assert "file_url" not in response.text
    assert "directus_file_id" not in response.text


def test_attachment_rows_for_a_different_post_fail_closed(monkeypatch):
    row = _file_row()
    row["post_id"] = UUID(OTHER_POST_ID)
    client, _calls = _client(monkeypatch, [row])

    response = _get(client)

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Data Stream attachments unavailable"}


def test_malformed_post_id_is_rejected_before_the_reader(monkeypatch):
    client, calls = _client(monkeypatch, [_file_row()])

    response = _get(client, "not-a-uuid")

    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert calls == []
