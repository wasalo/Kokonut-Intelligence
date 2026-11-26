"""Unit tests for the provider-neutral private object-storage adapter."""

import re
from pathlib import Path

import pytest

from services.mobile.media_encryption import (
    MediaEnvelopeError,
    decrypt_media_envelope,
    encrypt_media_envelope,
    parse_media_encryption_key,
)
from services.mobile.media_storage import (
    MediaStorageNotConfigured,
    S3CompatibleMediaStore,
    create_media_store,
)


class FakeS3Client:
    def __init__(self):
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(("put_object", kwargs))

    def head_object(self, **kwargs):
        self.calls.append(("head_object", kwargs))
        return {
            "ContentLength": 36,
            "ContentType": "application/octet-stream",
            "Metadata": {
                "kokonut-media-format": "KKM1",
                "kokonut-media-content-type": "image/jpeg",
                "kokonut-media-size": "4",
            },
        }

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
        "MOBILE_MEDIA_ENCRYPTION_KEY": "11" * 32,
    }
    store = create_media_store(config, client_factory=client_factory)
    key = "private/field-collector/location/device/item-1.jpg"
    store.put_private(key, b"jpeg", "image/jpeg")
    head = store.head_private(key)
    store.delete_private(key)

    assert factory_calls[0]["endpoint_url"] == config["MOBILE_MEDIA_S3_ENDPOINT"]
    assert factory_calls[0]["region_name"] == "test-region"
    assert head["ContentLength"] == 4
    put = client.calls[0][1]
    assert put["Bucket"] == "private-media"
    assert put["Key"] == key
    assert put["Body"] != b"jpeg"
    assert decrypt_media_envelope(
        put["Body"], parse_media_encryption_key(config["MOBILE_MEDIA_ENCRYPTION_KEY"]), key
    ) == b"jpeg"
    assert put["Body"].startswith(b"KKM1")
    assert put["ContentType"] == "application/octet-stream"
    assert put["Metadata"] == {
        "kokonut-media-format": "KKM1",
        "kokonut-media-content-type": "image/jpeg",
        "kokonut-media-size": "4",
    }
    assert "ACL" not in put
    assert "PublicRead" not in str(put)


def test_s3_media_requires_a_valid_application_encryption_key():
    config = {
        "MOBILE_MEDIA_PROVIDER": "s3",
        "MOBILE_MEDIA_S3_ENDPOINT": "https://objects.example.test",
        "MOBILE_MEDIA_S3_BUCKET": "private-media",
        "MOBILE_MEDIA_S3_ACCESS_KEY_ID": "fake-access-key",
        "MOBILE_MEDIA_S3_SECRET_ACCESS_KEY": "fake-secret-key",
        "MOBILE_MEDIA_S3_REGION": "test-region",
    }
    with pytest.raises(MediaStorageNotConfigured, match="not configured"):
        create_media_store(config, client_factory=lambda **_: pytest.fail("client must not be created"))

    config["MOBILE_MEDIA_ENCRYPTION_KEY"] = "not-a-key"
    with pytest.raises(MediaStorageNotConfigured, match="32-byte hexadecimal"):
        create_media_store(config, client_factory=lambda **_: pytest.fail("client must not be created"))


@pytest.mark.parametrize(
    "overrides",
    [
        {"ContentLength": 35},
        {"ContentType": "image/jpeg"},
        {"Metadata": {"kokonut-media-format": "unknown"}},
        {
            "Metadata": {
                "kokonut-media-format": "KKM1",
                "kokonut-media-content-type": "text/plain",
                "kokonut-media-size": "4",
            }
        },
    ],
)
def test_s3_head_rejects_inconsistent_or_untrusted_envelope_metadata(overrides):
    client = FakeS3Client()
    result = {
        "ContentLength": 36,
        "ContentType": "application/octet-stream",
        "Metadata": {
            "kokonut-media-format": "KKM1",
            "kokonut-media-content-type": "image/jpeg",
            "kokonut-media-size": "4",
        },
    }
    result.update(overrides)
    client.head_object = lambda **_: result
    store = S3CompatibleMediaStore(client, "private-media", "42" * 32)

    with pytest.raises(MediaStorageNotConfigured, match="envelope"):
        store.head_private("private/field-collector/location/device/item.jpg")


def test_media_envelope_authenticates_ciphertext_and_object_key():
    key = parse_media_encryption_key("42" * 32)
    object_key = "private/field-collector/location/device/item.jpg"
    plaintext = b"\xff\xd8\xffsynthetic-jpeg"
    envelope = encrypt_media_envelope(
        plaintext,
        key,
        object_key,
        random_bytes=lambda length: b"\x01" * length,
    )

    assert decrypt_media_envelope(envelope, key, object_key) == plaintext
    with pytest.raises(MediaEnvelopeError):
        decrypt_media_envelope(envelope, key, object_key + ".moved")
    with pytest.raises(MediaEnvelopeError):
        decrypt_media_envelope(envelope, bytes.fromhex("24" * 32), object_key)
    corrupted = bytearray(envelope)
    corrupted[-1] ^= 0x01
    with pytest.raises(MediaEnvelopeError):
        decrypt_media_envelope(bytes(corrupted), key, object_key)


@pytest.mark.parametrize("operation", ["put", "head", "delete"])
@pytest.mark.parametrize(
    "key",
    [
        "field-collector/item.jpg",
        "private/other/item.jpg",
        "private/field-collector/../outside.jpg",
        "private/field-collector/location//item.jpg",
        "private/field-collector/location/./item.jpg",
        "private/field-collector/location/",
    ],
)
def test_s3_operations_reject_keys_outside_the_private_prefix(operation, key):
    client = FakeS3Client()
    store = S3CompatibleMediaStore(client, "private-media", "42" * 32)

    with pytest.raises(ValueError, match="Invalid private media key"):
        if operation == "put":
            store.put_private(key, b"\xff\xd8\xffsynthetic", "image/jpeg")
        elif operation == "head":
            store.head_private(key)
        else:
            store.delete_private(key)

    assert client.calls == []


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
