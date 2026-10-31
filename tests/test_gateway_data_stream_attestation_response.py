"""Strict tenant-bound response contract for Data Stream attestation reads."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi.encoders import jsonable_encoder  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402

LOCATION_ID = str(uuid4())
POST_ID = str(uuid4())
TX_HASH = "0x" + "a" * 64
UID = "0x" + "b" * 64


def _row():
    timestamp = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    return {
        "post_id": UUID(POST_ID),
        "location_id": UUID(LOCATION_ID),
        "post_content_hash": "c" * 64,
        "is_anchored": True,
        "attestation_uid": UID,
        "chain": "celo",
        "anchored_at": timestamp,
        "request_status": "confirmed",
        "tx_hash": TX_HASH,
        "block_number": 123456,
        "confirmed_at": timestamp,
        "request_created_at": timestamp,
    }


def _client(monkeypatch, row, *, service_error=None):
    monkeypatch.setenv("KOKONUT_API_KEYS", "reader-key:reader")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES",
        f"reader:data_stream_proof:read:{LOCATION_ID}",
    )
    calls = []

    def service(*args, **kwargs):
        calls.append((args, kwargs))
        if service_error is not None:
            raise service_error
        return row

    monkeypatch.setattr(
        "services.gateway.data_stream.get_gateway_data_stream_attestation", service
    )
    return TestClient(create_app()), calls


def test_attestation_openapi_documents_exact_strict_envelope(monkeypatch):
    client, _calls = _client(monkeypatch, _row())
    schema = client.app.openapi()
    operation = schema["paths"][
        "/api/data-stream/posts/{post_id}/attestation"
    ]["get"]
    response_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    envelope_name = response_ref.rsplit("/", 1)[-1]
    envelope = schema["components"]["schemas"][envelope_name]
    record_ref = envelope["properties"]["data"]["$ref"]
    record = schema["components"]["schemas"][record_ref.rsplit("/", 1)[-1]]

    assert envelope["additionalProperties"] is False
    assert record["additionalProperties"] is False
    assert len(record["properties"]) == 12
    assert set(record["properties"]) == {
        "post_id", "location_id", "post_content_hash", "is_anchored",
        "attestation_uid", "chain", "anchored_at", "request_status", "tx_hash",
        "block_number", "confirmed_at", "request_created_at",
    }
    assert record["properties"]["request_status"]["anyOf"][0]["enum"] == [
        "pending", "submitted", "confirmed", "failed", "cancelled"
    ]


def test_attestation_response_preserves_envelope_and_binds_post_and_location(monkeypatch):
    row = _row()
    client, calls = _client(monkeypatch, row)

    response = client.get(
        f"/api/data-stream/posts/{POST_ID}/attestation",
        headers={"x-api-key": "reader-key"},
        params={"location_id": LOCATION_ID},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"data": jsonable_encoder(row)}
    assert calls[0][0][0] == POST_ID
    assert calls[0][0][1] == LOCATION_ID
    authorization = calls[0][0][2]
    assert authorization["resource"] == "data_stream_proof"
    assert authorization["action"] == "read"
    assert authorization["location_id"] == LOCATION_ID


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: row.update(unexpected="private metadata"),
        lambda row: row.update(post_id=UUID(str(uuid4()))),
        lambda row: row.update(location_id=UUID(str(uuid4()))),
        lambda row: row.pop("block_number"),
        lambda row: row.update(request_status="unknown"),
        lambda row: row.update(is_anchored="true"),
    ],
)
def test_invalid_or_mismatched_attestation_projection_fails_closed(monkeypatch, mutation):
    row = _row()
    mutation(row)
    client, calls = _client(monkeypatch, row)

    response = client.get(
        f"/api/data-stream/posts/{POST_ID}/attestation",
        headers={"x-api-key": "reader-key"},
        params={"location_id": LOCATION_ID},
    )

    assert response.status_code == 500
    assert response.json() == {"error": "Data Stream attestation unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert len(calls) == 1


def test_attestation_not_found_remains_404_and_uncached(monkeypatch):
    client, _calls = _client(monkeypatch, None)

    response = client.get(
        f"/api/data-stream/posts/{POST_ID}/attestation",
        headers={"x-api-key": "reader-key"},
        params={"location_id": LOCATION_ID},
    )

    assert response.status_code == 404
    assert response.json() == {"error": "Data Stream post not found"}
    assert response.headers["cache-control"] == "no-store"


def test_service_value_error_keeps_400_status(monkeypatch):
    client, _calls = _client(monkeypatch, None, service_error=ValueError("invalid scope"))

    response = client.get(
        f"/api/data-stream/posts/{POST_ID}/attestation",
        headers={"x-api-key": "reader-key"},
        params={"location_id": LOCATION_ID},
    )

    assert response.status_code == 400
    assert response.json() == {"error": "invalid scope"}
    assert response.headers["cache-control"] == "no-store"
