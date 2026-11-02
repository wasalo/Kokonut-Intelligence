"""Private S3-compatible report artifact behavior using a synthetic client."""

from __future__ import annotations

import io
from uuid import uuid4

import pytest

from services.export.artifact_storage import (
    MAX_PRIVATE_EXPORT_BYTES,
    ArtifactStorageError,
    LocalPrivateArtifactStore,
    S3PrivateArtifactStore,
    create_private_artifact_store,
)


class FakeBody(io.BytesIO):
    read_sizes: list[int]

    def __init__(self, content: bytes):
        super().__init__(content)
        self.read_sizes = []
        self.closed_by_store = False

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)

    def close(self):
        self.closed_by_store = True
        super().close()


class FakeS3:
    def __init__(self, *, content=b"report", content_length=None):
        self.content = content
        self.content_length = len(content) if content_length is None else content_length
        self.calls = []
        self.body = None
        self.error = None

    def put_object(self, **kwargs):
        self.calls.append(("put_object", kwargs))
        if self.error:
            raise self.error

    def get_object(self, **kwargs):
        self.calls.append(("get_object", kwargs))
        if self.error:
            raise self.error
        self.body = FakeBody(self.content)
        return {"Body": self.body, "ContentLength": self.content_length}

    def delete_object(self, **kwargs):
        self.calls.append(("delete_object", kwargs))
        if self.error:
            raise self.error


def _s3_env(**overrides):
    values = {
        "KOKONUT_PRIVATE_EXPORT_PROVIDER": "s3",
        "KOKONUT_PRIVATE_EXPORT_S3_ENDPOINT": "https://account.r2.cloudflarestorage.com",
        "KOKONUT_PRIVATE_EXPORT_S3_BUCKET": "private-reports",
        "KOKONUT_PRIVATE_EXPORT_S3_REGION": "auto",
        "KOKONUT_PRIVATE_EXPORT_S3_READER_ACCESS_KEY_ID": "reader-key",
        "KOKONUT_PRIVATE_EXPORT_S3_READER_SECRET_ACCESS_KEY": "reader-secret",
        "KOKONUT_PRIVATE_EXPORT_S3_WORKER_ACCESS_KEY_ID": "worker-key",
        "KOKONUT_PRIVATE_EXPORT_S3_WORKER_SECRET_ACCESS_KEY": "worker-secret",
    }
    return {**values, **overrides}


def test_write_uses_private_uuid_key_and_json_content_type():
    client = FakeS3()
    store = S3PrivateArtifactStore(client, "private-reports")
    artifact_id = uuid4()

    store.write(artifact_id, b'{"report":true}')

    method, request = client.calls[0]
    assert method == "put_object"
    assert request == {
        "Bucket": "private-reports",
        "Key": f"private/report-snapshot-exports/{artifact_id}.artifact",
        "Body": b'{"report":true}',
        "ContentType": "application/json",
    }
    assert "ACL" not in request
    assert "private-reports" not in repr(store)


def test_write_rejects_empty_and_oversized_artifacts_before_provider_call():
    client = FakeS3()
    store = S3PrivateArtifactStore(client, "private-reports")

    with pytest.raises(ArtifactStorageError, match="size"):
        store.write(uuid4(), b"")
    with pytest.raises(ArtifactStorageError, match="size"):
        store.write(uuid4(), b"x" * (MAX_PRIVATE_EXPORT_BYTES + 1))

    assert not client.calls


def test_read_is_streamed_bounded_and_closes_provider_body():
    client = FakeS3(content=b"12345678")
    store = S3PrivateArtifactStore(client, "private-reports")
    artifact_id = uuid4()

    assert store.read(artifact_id, max_bytes=8) == b"12345678"

    method, request = client.calls[0]
    assert method == "get_object"
    assert request["Key"] == f"private/report-snapshot-exports/{artifact_id}.artifact"
    assert max(client.body.read_sizes) <= 64 * 1024
    assert client.body.closed_by_store


def test_s3_read_requires_a_memory_bound():
    client = FakeS3()
    store = S3PrivateArtifactStore(client, "private-reports")

    with pytest.raises(ValueError, match="require a byte limit"):
        store.read(uuid4())
    assert not client.calls


def test_read_rejects_oversized_content_length_before_stream_read():
    client = FakeS3(content=b"0123456789", content_length=10)
    store = S3PrivateArtifactStore(client, "private-reports")

    with pytest.raises(ArtifactStorageError, match="exceeds read limit"):
        store.read(uuid4(), max_bytes=4)

    assert client.body.closed_by_store
    assert client.body.read_sizes == []


def test_read_detects_stream_growth_beyond_declared_size():
    client = FakeS3(content=b"abc", content_length=2)
    store = S3PrivateArtifactStore(client, "private-reports")

    with pytest.raises(ArtifactStorageError, match="exceeds read limit"):
        store.read(uuid4(), max_bytes=2)

    assert client.body.closed_by_store


def test_provider_failures_are_redacted_and_explicit_delete_is_scoped():
    client = FakeS3()
    store = S3PrivateArtifactStore(client, "secret-bucket-name")
    client.error = RuntimeError("secret-bucket-name private/report-snapshot-exports/key")

    with pytest.raises(ArtifactStorageError, match="write failed") as error:
        store.write(uuid4(), b"x")
    assert "secret-bucket-name" not in str(error.value)

    client.error = None
    artifact_id = uuid4()
    store.delete(artifact_id)
    assert client.calls[-1] == (
        "delete_object",
        {
            "Bucket": "secret-bucket-name",
            "Key": f"private/report-snapshot-exports/{artifact_id}.artifact",
        },
    )


def test_reader_credentials_are_separate_and_store_cannot_mutate():
    client = FakeS3()
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        return client

    store = create_private_artifact_store(
        _s3_env(), client_factory=factory, access="reader"
    )

    assert isinstance(store, S3PrivateArtifactStore)
    assert calls[0]["aws_access_key_id"] == "reader-key"
    assert calls[0]["aws_secret_access_key"] == "reader-secret"
    store.read(uuid4(), max_bytes=10)
    with pytest.raises(ArtifactStorageError, match="read-only"):
        store.write(uuid4(), b"blocked")
    with pytest.raises(ArtifactStorageError, match="read-only"):
        store.delete(uuid4())
    assert [method for method, _ in client.calls] == ["get_object"]


def test_worker_uses_distinct_write_credentials():
    client = FakeS3()
    calls = []

    store = create_private_artifact_store(
        _s3_env(), client_factory=lambda **kwargs: calls.append(kwargs) or client
    )
    store.write(uuid4(), b"artifact")

    assert calls[0]["aws_access_key_id"] == "worker-key"
    assert calls[0]["aws_secret_access_key"] == "worker-secret"
    assert [method for method, _ in client.calls] == ["put_object"]


def test_local_provider_remains_default_and_requires_explicit_directory(tmp_path):
    store = create_private_artifact_store(
        {"KOKONUT_PRIVATE_EXPORT_DIR": str(tmp_path / "private")}
    )
    assert isinstance(store, LocalPrivateArtifactStore)

    with pytest.raises(ArtifactStorageError, match="not configured"):
        create_private_artifact_store({})


def test_gateway_and_worker_factories_select_separate_storage_access_roles(monkeypatch):
    observed = []

    def factory(environ=None, *, access, **_kwargs):
        observed.append(access)
        return object()

    from services.export import report_snapshot_export_worker
    from services.gateway import report_exports

    monkeypatch.setattr(report_exports, "create_private_artifact_store", factory)
    monkeypatch.setattr(report_snapshot_export_worker, "create_private_artifact_store", factory)
    report_exports._artifact_store()
    report_snapshot_export_worker._artifact_store_from_environment({})

    assert observed == ["reader", "worker"]


def test_factory_rejects_public_http_and_unknown_providers():
    with pytest.raises(ArtifactStorageError, match="HTTPS"):
        create_private_artifact_store(
            _s3_env(KOKONUT_PRIVATE_EXPORT_S3_ENDPOINT="http://storage.example"),
            client_factory=lambda **_kwargs: FakeS3(),
        )
    with pytest.raises(ArtifactStorageError, match="unknown"):
        create_private_artifact_store({"KOKONUT_PRIVATE_EXPORT_PROVIDER": "other"})
