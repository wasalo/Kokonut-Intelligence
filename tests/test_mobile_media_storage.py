"""Unit tests for the provider-neutral private object-storage adapter."""

import re
from pathlib import Path

from services.mobile.media_storage import (
    MediaStorageNotConfigured,
    create_media_store,
)


class FakeS3Client:
    def __init__(self):
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(("put_object", kwargs))

    def head_object(self, **kwargs):
        self.calls.append(("head_object", kwargs))
        return {"ContentLength": 4, "ContentType": "image/jpeg"}

    def delete_object(self, **kwargs):
        self.calls.append(("delete_object", kwargs))


def test_missing_storage_configuration_fails_closed():
    try:
        create_media_store({})
    except MediaStorageNotConfigured:
        return
    raise AssertionError("storage adapter should reject missing private-bucket configuration")


def test_s3_compatible_adapter_keeps_objects_private_and_supports_validation():
    client = FakeS3Client()
    factory_calls = []

    def client_factory(**kwargs):
        factory_calls.append(kwargs)
        return client

    config = {
        "MOBILE_MEDIA_S3_ENDPOINT": "https://objects.example.test",
        "MOBILE_MEDIA_S3_BUCKET": "private-media",
        "MOBILE_MEDIA_S3_ACCESS_KEY_ID": "fake-access-key",
        "MOBILE_MEDIA_S3_SECRET_ACCESS_KEY": "fake-secret-key",
        "MOBILE_MEDIA_S3_REGION": "test-region",
    }
    store = create_media_store(config, client_factory=client_factory)
    store.put_private("field-collector/item-1.jpg", b"jpeg", "image/jpeg")
    head = store.head_private("field-collector/item-1.jpg")
    store.delete_private("field-collector/item-1.jpg")

    assert factory_calls[0]["endpoint_url"] == config["MOBILE_MEDIA_S3_ENDPOINT"]
    assert factory_calls[0]["region_name"] == "test-region"
    assert head["ContentLength"] == 4
    put = client.calls[0][1]
    assert put["Bucket"] == "private-media"
    assert put["Key"] == "field-collector/item-1.jpg"
    assert put["Body"] == b"jpeg"
    assert put["ContentType"] == "image/jpeg"
    assert "ACL" not in put
    assert "PublicRead" not in str(put)


def test_private_media_migration_tracks_scope_size_and_attachment():
    migration = Path(__file__).parents[1] / "schemas/postgres/358_mobile_private_media.sql"
    sql = migration.read_text().lower()

    assert "create table if not exists mobile_media_upload" in sql
    assert "references mobile_device(device_id)" in sql
    assert "references location(id)" in sql
    assert re.search(r"collection_client_id\s+varchar\(200\)\s+not null", sql)
    assert "size_bytes <= 2000000" in sql
    assert "references offline_collection(id)" in sql
    assert re.search(r"object_key\s+text\s+not null unique", sql)
