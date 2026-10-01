"""Focused tests for the field collector companion app and API surface."""

from pathlib import Path
import json
from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi")

from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.router import get_route_policy  # noqa: E402
from services.mobile.api import APP_PATH, CollectionRequest  # noqa: E402
from services.mobile import api as mobile_api  # noqa: E402


def _client(monkeypatch):
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda self, **kwargs: None,
    )
    return TestClient(create_app())


def test_mobile_routes_are_explicitly_public_for_device_auth():
    assert get_route_policy("GET", "/mobile")["public"] is True
    assert get_route_policy("GET", "/api/mobile/forms")["public"] is True
    assert get_route_policy("POST", "/api/mobile/sync")["public"] is True


def test_media_upload_route_is_public_for_its_own_device_token_auth():
    policy = get_route_policy("POST", "/api/mobile/media/uploads")

    assert policy["public"] is True
    assert policy["resource"] == "mobile_media"
    assert policy["action"] == "upload"


def test_media_upload_is_device_authenticated_and_stores_private_jpeg(monkeypatch):
    connection = MagicMock()
    store = MagicMock()
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)
    monkeypatch.setattr(
        mobile_api,
        "_device_for_token",
        lambda token: ("device-1", "worker-1", "11111111-1111-4111-8111-111111111111"),
    )
    monkeypatch.setattr(mobile_api, "get_media_store", lambda: store, raising=False)

    with _client(monkeypatch) as client:
        response = client.post(
            "/api/mobile/media/uploads",
            headers={
                "x-device-token": "opaque-device-token",
                "x-collection-client-id": "client-1",
                "content-type": "image/jpeg",
            },
            content=b"\xff\xd8\xff\xdbjpeg-data",
        )

    assert response.status_code == 201
    media_id = response.json()["media_id"]
    assert len(media_id) == 36
    store.put_private.assert_called_once()
    args = store.put_private.call_args.args
    assert args[1] == b"\xff\xd8\xff\xdbjpeg-data"
    assert args[2] == "image/jpeg"
    execute_args = connection.cursor.return_value.execute.call_args.args
    sql = execute_args[0].lower()
    assert "insert into mobile_media_upload" in sql
    assert "collection_client_id" in sql
    assert "client-1" in execute_args[1]
    assert "private/field-collector/" in args[0]


def test_media_upload_rejects_invalid_jpeg_signature_before_storage(monkeypatch):
    store = MagicMock()
    database = MagicMock()
    monkeypatch.setattr(mobile_api, "get_db", lambda: database)
    monkeypatch.setattr(mobile_api, "get_media_store", lambda: store, raising=False)
    monkeypatch.setattr(
        mobile_api,
        "_device_for_token",
        lambda token: ("device-1", "worker-1", "11111111-1111-4111-8111-111111111111"),
    )

    with _client(monkeypatch) as client:
        response = client.post(
            "/api/mobile/media/uploads",
            headers={
                "x-device-token": "opaque-device-token",
                "x-collection-client-id": "client-1",
                "content-type": "image/jpeg",
            },
            content=b"not-a-jpeg",
        )

    assert response.status_code == 415
    store.put_private.assert_not_called()
    database.cursor.assert_not_called()


def test_media_upload_keeps_committed_object_when_cursor_close_fails(monkeypatch):
    class Cursor:
        def execute(self, sql, params=None):
            pass

        def close(self):
            raise RuntimeError("cursor close failed")

    class Connection:
        committed = False

        def cursor(self):
            return Cursor()

        def commit(self):
            self.committed = True

        def rollback(self):
            raise AssertionError("committed upload must not be rolled back")

        def close(self):
            pass

    connection = Connection()
    store = MagicMock()
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)
    monkeypatch.setattr(mobile_api, "get_media_store", lambda: store, raising=False)
    monkeypatch.setattr(
        mobile_api,
        "_device_for_token",
        lambda token: ("device-1", "worker-1", "11111111-1111-4111-8111-111111111111"),
    )

    with _client(monkeypatch) as client:
        response = client.post(
            "/api/mobile/media/uploads",
            headers={
                "x-device-token": "opaque-device-token",
                "x-collection-client-id": "client-1",
                "content-type": "image/jpeg",
            },
            content=b"\xff\xd8\xff\xdbjpeg-data",
        )

    assert response.status_code == 201
    assert connection.committed is True
    store.delete_private.assert_not_called()


def test_sync_rejects_inline_photo_data_urls_before_database_write(monkeypatch):
    connection = MagicMock()
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)
    monkeypatch.setattr(
        mobile_api,
        "_device_for_token",
        lambda token: ("device-1", "worker-1", "11111111-1111-4111-8111-111111111111"),
    )

    with _client(monkeypatch) as client:
        response = client.post(
            "/api/mobile/sync",
            headers={"x-device-token": "opaque-device-token"},
            json={
                "device_id": "device-1",
                "collections": [{
                    "client_id": "client-1",
                    "collection_type": "field_note",
                    "payload": {"content": "note", "photos": ["data:image/jpeg;base64,ZmFrZQ=="]},
                }],
            },
        )

    assert response.status_code == 422
    assert connection.cursor.called is False


def test_sync_rejects_reused_client_id_when_payload_differs(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = (
        "device-1", "worker-1", "11111111-1111-4111-8111-111111111111",
        "field_note", None, None, {"content": "original"}, [], None, None, None, None,
    )
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)
    monkeypatch.setattr(
        mobile_api,
        "_device_for_token",
        lambda token: ("device-1", "worker-1", "11111111-1111-4111-8111-111111111111"),
    )

    with _client(monkeypatch) as client:
        response = client.post(
            "/api/mobile/sync",
            headers={"x-device-token": "opaque-device-token"},
            json={
                "device_id": "device-1",
                "collections": [{
                    "client_id": "client-1",
                    "collection_type": "field_note",
                    "payload": {"content": "changed after the original upload"},
                }],
            },
        )

    assert response.status_code == 409


def test_sync_accepts_an_identical_retry_for_an_existing_client_id(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = (
        "device-1", "worker-1", "11111111-1111-4111-8111-111111111111",
        "field_note", None, None, {"content": "same"}, [], None, None, None, None,
    )
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)
    monkeypatch.setattr(
        mobile_api,
        "_device_for_token",
        lambda token: ("device-1", "worker-1", "11111111-1111-4111-8111-111111111111"),
    )

    with _client(monkeypatch) as client:
        response = client.post(
            "/api/mobile/sync",
            headers={"x-device-token": "opaque-device-token"},
            json={
                "device_id": "device-1",
                "collections": [{
                    "client_id": "client-1",
                    "collection_type": "field_note",
                    "payload": {"content": "same"},
                }],
            },
        )

    assert response.status_code == 200
    assert response.json()["duplicate_client_ids"] == ["client-1"]
    assert not any("insert into offline_collection" in call.args[0].lower() for call in cursor.execute.call_args_list)


def test_sync_rejects_unowned_photo_reference(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = None
    cursor.fetchall.return_value = []
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)
    monkeypatch.setattr(
        mobile_api,
        "_device_for_token",
        lambda token: ("device-1", "worker-1", "11111111-1111-4111-8111-111111111111"),
    )

    with _client(monkeypatch) as client:
        response = client.post(
            "/api/mobile/sync",
            headers={"x-device-token": "opaque-device-token"},
            json={
                "device_id": "device-1",
                "collections": [{
                    "client_id": "client-1",
                    "collection_type": "field_note",
                    "payload": {"content": "note"},
                    "photo_refs": ["44444444-4444-4444-8444-444444444444"],
                }],
            },
        )

    assert response.status_code == 403
    assert connection.commit.called is False


def test_sync_attaches_device_owned_media_after_storage_head_check(monkeypatch):
    media_id = "33333333-3333-4333-8333-333333333333"
    media_key = "private/field-collector/location/device/media.jpg"

    class Cursor:
        def __init__(self):
            self.one = None
            self.many = []
            self.rowcount = 0
            self.executed = []

        def execute(self, sql, params=None):
            self.executed.append((sql, params))
            normalized = sql.lower()
            if "from offline_collection where client_id" in normalized:
                self.one = None
            elif "select media_id::text, object_key" in normalized:
                self.many = [(media_id, media_key, "image/jpeg", 12)]
            elif "insert into offline_collection" in normalized:
                self.one = ("collection-1",)
            elif "update mobile_media_upload" in normalized:
                self.rowcount = 1

        def fetchone(self):
            value, self.one = self.one, None
            return value

        def fetchall(self):
            value, self.many = self.many, []
            return value

        def close(self):
            pass

    class Connection:
        def __init__(self):
            self.cur = Cursor()
            self.committed = False
            self.rolled_back = False
            self.closed = False

        def cursor(self):
            return self.cur

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

    connection = Connection()
    store = MagicMock()
    store.head_private.return_value = {"ContentLength": 12, "ContentType": "image/jpeg"}
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)
    monkeypatch.setattr(mobile_api, "get_media_store", lambda: store, raising=False)
    monkeypatch.setattr(
        mobile_api,
        "_device_for_token",
        lambda token: ("device-1", "worker-1", "11111111-1111-4111-8111-111111111111"),
    )

    with _client(monkeypatch) as client:
        response = client.post(
            "/api/mobile/sync",
            headers={"x-device-token": "opaque-device-token"},
            json={
                "device_id": "device-1",
                "collections": [{
                    "client_id": "client-1",
                    "collection_type": "field_note",
                    "payload": {"content": "note"},
                    "photo_refs": [media_id],
                }],
            },
        )

    assert response.status_code == 200
    assert response.json()["accepted_client_ids"] == ["client-1"]
    store.head_private.assert_called_once_with(media_key)
    insert = next(call for call in connection.cur.executed if "insert into offline_collection" in call[0].lower())
    assert json.loads(insert[1][7]) == [media_id]
    attachment = next(call for call in connection.cur.executed if "update mobile_media_upload" in call[0].lower())
    assert "status = 'attached'" in attachment[0].lower()
    assert connection.committed is True


def test_mobile_device_token_is_not_written_to_gateway_audit(monkeypatch):
    secret_token = "sensitive-device-token-not-for-logs"
    records = []
    connection = MagicMock()
    connection.cursor.return_value.fetchone.side_effect = [(0, 0, 0), (None,)]
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)
    monkeypatch.setattr(
        mobile_api,
        "_device_for_token",
        lambda token: ("device-1", "worker-1", "11111111-1111-4111-8111-111111111111"),
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda self, **record: records.append(record),
    )

    with TestClient(create_app()) as client:
        response = client.get(
            "/api/mobile/sync/status",
            headers={"x-device-token": secret_token},
        )

    assert response.status_code == 200
    assert records and records[0]["status_code"] == 200
    assert secret_token not in repr(records)


def test_gateway_serves_field_collector():
    with TestClient(create_app()) as client:
        response = client.get("/mobile")
        api_response = client.get("/api/mobile/app")
        root_vault_script = client.get("/field-collector-vault.js")
        slash_vault_script = client.get("/mobile/field-collector-vault.js")

    assert response.status_code == 200
    assert api_response.status_code == 200
    assert root_vault_script.status_code == 200
    assert slash_vault_script.status_code == 200
    assert "Kokonut Field Collector" in response.text
    assert "localStorage" in response.text


def test_field_collector_is_directly_openable():
    assert APP_PATH == Path(__file__).parents[1] / "services/mobile/field-collector.html"
    assert APP_PATH.read_text().startswith("<!doctype html>")


def test_collection_request_rejects_invalid_coordinates():
    with pytest.raises(ValueError):
        CollectionRequest(
            client_id="client-1",
            collection_type="field_note",
            latitude=91,
        )


def test_anonymous_registration_requires_enrollment_code(monkeypatch):
    connection = MagicMock()
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)

    with _client(monkeypatch) as client:
        response = client.post(
            "/api/mobile/register",
            json={"device_id": "browser-1"},
        )

    assert response.status_code == 422
    connection.cursor.assert_not_called()


def test_existing_device_id_cannot_be_reassigned_by_registration(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [
        ("claim-1", "worker-1", "11111111-1111-4111-8111-111111111111"),
        None,
    ]
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)

    with _client(monkeypatch) as client:
        response = client.post(
            "/api/mobile/register",
            json={
                "device_id": "known-device",
                "enrollment_code": "E" * 43,
                "device_name": "Field phone",
            },
        )

    assert response.status_code == 409
    sql = "\n".join(call.args[0] for call in cursor.execute.call_args_list)
    assert "ON CONFLICT (device_id) DO UPDATE" not in sql
    connection.commit.assert_not_called()
    connection.rollback.assert_called()


def test_enrollment_creation_requires_scoped_gateway_auth(monkeypatch):
    location_id = "11111111-1111-4111-8111-111111111111"
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = ("claim-1", "2030-01-01T00:00:00+00:00")
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)
    monkeypatch.setenv("KOKONUT_API_KEYS", "enroller-secret:field-enroller")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES",
        f"field-enroller:mobile_device:enroll:{location_id}",
    )

    with _client(monkeypatch) as client:
        denied = client.post(
            f"/api/mobile/locations/{location_id}/enrollments",
            json={"user_id": "worker-1"},
        )
        allowed = client.post(
            f"/api/mobile/locations/{location_id}/enrollments",
            headers={"x-api-key": "enroller-secret"},
            json={"user_id": "worker-1"},
        )

    assert denied.status_code == 401
    assert allowed.status_code == 201
    body = allowed.json()
    assert len(body["enrollment_code"]) >= 32
    assert "enrollment_code" not in str(cursor.execute.call_args_list)
    assert f"{location_id}" in str(cursor.execute.call_args_list)


def test_location_specific_forms_require_a_registered_device(monkeypatch):
    connection = MagicMock()
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)
    location_id = "11111111-1111-4111-8111-111111111111"

    with _client(monkeypatch) as client:
        response = client.get(f"/api/mobile/forms?location_id={location_id}")

    assert response.status_code == 401
    connection.cursor.assert_not_called()


def test_anonymous_forms_query_only_approved_global_definitions(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.description = []
    cursor.fetchall.return_value = []
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)

    with _client(monkeypatch) as client:
        response = client.get("/api/mobile/forms")

    assert response.status_code == 200
    sql = cursor.execute.call_args.args[0].lower()
    assert "is_public" in sql
    assert "location_id is null" in sql


def test_device_forms_use_registered_location_not_query_location(monkeypatch):
    registered_location = "11111111-1111-4111-8111-111111111111"
    other_location = "22222222-2222-4222-8222-222222222222"
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.description = []
    cursor.fetchall.return_value = []
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)
    monkeypatch.setattr(
        mobile_api,
        "_device_for_token",
        lambda token: ("device-1", "worker-1", registered_location),
    )

    with _client(monkeypatch) as client:
        denied = client.get(
            f"/api/mobile/forms?location_id={other_location}",
            headers={"x-device-token": "opaque-device-token"},
        )
        allowed = client.get(
            "/api/mobile/forms",
            headers={"x-device-token": "opaque-device-token"},
        )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert registered_location in str(cursor.execute.call_args_list)


def test_device_revocation_is_location_scoped_and_clears_token_hash(monkeypatch):
    location_id = "11111111-1111-4111-8111-111111111111"
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = ("device-1",)
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)
    monkeypatch.setenv("KOKONUT_API_KEYS", "revoker-secret:field-revoker")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES",
        f"field-revoker:mobile_device:revoke:{location_id}",
    )

    with _client(monkeypatch) as client:
        response = client.post(
            f"/api/mobile/locations/{location_id}/devices/device-1/revoke",
            headers={"x-api-key": "revoker-secret"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "revoked"
    sql = cursor.execute.call_args.args[0].lower()
    assert "device_token_hash = null" in sql
    assert "status = 'revoked'" in sql
    assert cursor.execute.call_args.args[1] == ("device-1", location_id)
    connection.commit.assert_called_once()


def test_invalid_enrollment_code_cannot_create_a_device(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = None
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)

    with _client(monkeypatch) as client:
        response = client.post(
            "/api/mobile/register",
            json={"device_id": "browser-2", "enrollment_code": "E" * 43},
        )

    assert response.status_code == 401
    assert cursor.execute.call_count == 1
    assert "mobile_device_enrollment" in cursor.execute.call_args.args[0]
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def test_registration_derives_worker_and_location_from_enrollment_claim(monkeypatch):
    location_id = "11111111-1111-4111-8111-111111111111"
    enrollment_code = "E" * 43
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [
        ("claim-1", "server-worker", location_id),
        ("browser-3",),
    ]
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)

    with _client(monkeypatch) as client:
        response = client.post(
            "/api/mobile/register",
            json={"device_id": "browser-3", "enrollment_code": enrollment_code},
        )

    assert response.status_code == 200
    assert response.json()["location_id"] == location_id
    assert response.json()["device_token"] != enrollment_code
    device_insert = cursor.execute.call_args_list[1].args
    assert device_insert[1][6] == "server-worker"
    assert device_insert[1][7] == location_id
    assert "ON CONFLICT (device_id) DO NOTHING" in device_insert[0]
    connection.commit.assert_called_once()


def test_enrollment_revocation_is_scoped_to_location(monkeypatch):
    location_id = "11111111-1111-4111-8111-111111111111"
    enrollment_id = "33333333-3333-4333-8333-333333333333"
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = (enrollment_id,)
    monkeypatch.setattr(mobile_api, "get_db", lambda: connection)
    monkeypatch.setenv("KOKONUT_API_KEYS", "revoker-secret:field-revoker")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES",
        f"field-revoker:mobile_device:revoke:{location_id}",
    )

    with _client(monkeypatch) as client:
        response = client.delete(
            f"/api/mobile/locations/{location_id}/enrollments/{enrollment_id}",
            headers={"x-api-key": "revoker-secret"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "revoked"
    assert cursor.execute.call_args.args[1] == (enrollment_id, location_id)
    sql = cursor.execute.call_args.args[0].lower()
    assert "used_at is null" in sql
    assert "revoked_at is null" in sql
    connection.commit.assert_called_once()


def test_mobile_app_requests_enrollment_code_instead_of_identity_overrides(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get("/api/mobile/app")

    assert response.status_code == 200
    html = response.text
    assert 'name="enrollmentCode"' in html
    assert "user_id:config.userId" not in html
    assert "location_id:config.locationId" not in html


def test_mobile_app_loads_location_forms_with_device_token_not_query_scope(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get("/api/mobile/app")

    html = response.text
    load_forms = html.split("const loadForms =", 1)[1].split("document.getElementById", 1)[0]
    assert "${base}/forms" in load_forms
    assert "X-Device-Token" in load_forms
    assert "location_id=" not in load_forms


def test_vault_script_is_served_from_the_mobile_api(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get("/api/mobile/field-collector-vault.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "class EncryptedVault" in response.text


def test_field_collector_uses_the_encrypted_vault_and_lock_gate(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get("/api/mobile/app")

    html = response.text
    assert 'src="field-collector-vault.js"' in html
    assert "id=\"lockButton\"" in html
    assert "autocomplete=\"current-password\"" in html
    assert "localStorage.setItem" not in html
    assert "offline_photos" in html
    assert "dataURLToBlob" in html
    assert "${base}/media/uploads" in html
    assert "X-Collection-Client-ID" in html
    assert "payload.photos =" not in html
    assert "currentPhotos.length >= 5" in html
    assert "media_review_required" in html
