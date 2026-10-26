"""Safe inventory and orphan handling for private Field Collector media."""

import hashlib
import os
from datetime import datetime, timedelta, timezone

import pytest

from services.mobile.local_media import LocalMediaStore
from services.mobile.media_reconcile import (
    PrivateMediaReconcileError,
    _validate_age,
    _validate_limit,
    reconcile_private_media,
)
from services.mobile.media_storage import (
    MediaStorageNotConfigured,
    PrivateMediaObject,
    S3CompatibleMediaStore,
)

NOW = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class FakeConnection:
    def __init__(self, keys):
        self.keys = keys

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql):
        assert "select object_key from mobile_media_upload" in " ".join(sql.lower().split())
        return FakeResult([{"object_key": key} for key in self.keys])


class FakeStore:
    def __init__(self, objects):
        self.objects = objects
        self.deleted = []
        self.fail_list = None

    def object_id_for_key(self, key):
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def list_private_objects(self):
        if self.fail_list:
            raise self.fail_list
        return list(self.objects)

    def delete_orphan(self, item):
        self.deleted.append(item.object_id)


def _object(key, modified, *, kind="object", handle=None):
    object_id = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return PrivateMediaObject(object_id, modified, kind, handle or key)


def _run(store, keys, **kwargs):
    return reconcile_private_media(
        connection_factory=lambda: FakeConnection(keys),
        media_store_factory=lambda: store,
        now=NOW,
        **kwargs,
    )


def test_dry_run_reports_only_old_unregistered_objects_without_deleting():
    registered = "private/field-collector/location/device/registered.jpg"
    orphan = "private/field-collector/location/device/orphan.jpg"
    young = "private/field-collector/location/device/young.jpg"
    temporary = PrivateMediaObject("temporary:deadbeef", NOW - timedelta(days=3), "temporary", ".upload-dead")
    store = FakeStore(
        [
            _object(registered, NOW - timedelta(days=3)),
            _object(orphan, NOW - timedelta(days=2)),
            _object(young, NOW - timedelta(hours=2)),
            temporary,
        ]
    )

    result = _run(store, [registered])

    assert result == {
        "mode": "dry-run",
        "provider_object_count": 4,
        "registered_object_count": 1,
        "unregistered_object_count": 3,
        "eligible_count": 2,
        "too_young_count": 1,
        "limit": 100,
        "older_than_hours": 24,
        "deleted_count": 0,
        "skipped_registered_count": 0,
        "skipped_changed_count": 0,
    }
    assert store.deleted == []
    assert orphan not in str(result)


def test_apply_is_bounded_and_rechecks_registration_before_deletion():
    first = "private/field-collector/location/device/first.jpg"
    second = "private/field-collector/location/device/second.jpg"
    store = FakeStore(
        [
            _object(first, NOW - timedelta(days=2)),
            _object(second, NOW - timedelta(days=3)),
        ]
    )
    reads = 0

    def connect():
        nonlocal reads
        reads += 1
        # The second object becomes registered after the initial inventory.
        keys = [second] if reads > 1 else []
        return FakeConnection(keys)

    result = reconcile_private_media(
        apply=True,
        limit=1,
        connection_factory=connect,
        media_store_factory=lambda: store,
        now=NOW,
    )

    assert result["eligible_count"] == 2
    assert result["deleted_count"] == 0
    assert result["skipped_registered_count"] == 1
    assert store.deleted == []


def test_apply_removes_only_aged_candidates_and_reports_no_private_handles():
    old = "private/field-collector/location/device/old.jpg"
    recent = "private/field-collector/location/device/recent.jpg"
    store = FakeStore(
        [
            _object(old, NOW - timedelta(days=4)),
            _object(recent, NOW - timedelta(hours=1)),
        ]
    )

    result = _run(store, [], apply=True, limit=1)

    assert result["deleted_count"] == 1
    assert store.deleted == [store.object_id_for_key(old)]
    assert old not in str(result)


def test_inventory_failure_is_sanitized_and_never_deletes():
    store = FakeStore([])
    store.fail_list = RuntimeError("secret bucket key=private/field-collector/private.jpg")

    with pytest.raises(PrivateMediaReconcileError, match="Could not list private media objects") as error:
        _run(store, [], apply=True)

    assert "private.jpg" not in str(error.value)
    assert store.deleted == []


def test_duplicate_provider_identities_fail_closed():
    key = "private/field-collector/location/device/item.jpg"
    item = _object(key, NOW - timedelta(days=2))
    store = FakeStore([item, item])

    with pytest.raises(PrivateMediaReconcileError, match="duplicate object identities"):
        _run(store, [], apply=True)

    assert store.deleted == []


@pytest.mark.parametrize("value", [23, 0, -1, 8761, True, 24.5])
def test_minimum_age_is_enforced(value):
    with pytest.raises(ValueError, match="older_than_hours must be between"):
        _validate_age(value)


@pytest.mark.parametrize("value", [0, -1, 501, True, 1.5])
def test_batch_limit_is_bounded(value):
    with pytest.raises(ValueError, match="limit must be between"):
        _validate_limit(value)


def test_local_inventory_matches_registered_key_and_removes_stale_temp_file(tmp_path):
    root = tmp_path / "private-media"
    root.mkdir(mode=0o700)
    store = LocalMediaStore(str(root), "42" * 32)
    key = "private/field-collector/location/device/item.jpg"
    store.put_private(key, b"\xff\xd8\xffsynthetic", "image/jpeg")
    temp_path = root / ".upload-crashed-process"
    temp_path.write_bytes(b"partial")
    old = NOW - timedelta(days=3)
    os.utime(temp_path, (old.timestamp(), old.timestamp()))

    inventory = store.list_private_objects()
    registered_id = store.object_id_for_key(key)
    temp_item = next(item for item in inventory if item.kind == "temporary")

    assert any(item.object_id == registered_id and item.kind == "object" for item in inventory)
    assert temp_item.last_modified <= NOW - timedelta(hours=24)
    store.delete_orphan(temp_item)
    assert not temp_path.exists()
    assert store.head_private(key)["ContentLength"] == len(b"\xff\xd8\xffsynthetic")


def test_local_inventory_fails_closed_on_symlink(tmp_path):
    root = tmp_path / "private-media"
    root.mkdir(mode=0o700)
    store = LocalMediaStore(str(root), "24" * 32)
    outside = tmp_path / "outside"
    outside.write_text("keep")
    (root / ("a" * 64 + ".bin")).symlink_to(outside)

    with pytest.raises(MediaStorageNotConfigured, match="unsafe entry"):
        store.list_private_objects()

    assert outside.read_text() == "keep"


class FakePaginator:
    def __init__(self, client):
        self.client = client

    def paginate(self, **kwargs):
        self.client.list_calls.append(kwargs)
        return self.client.pages


class FakeS3Client:
    def __init__(self, pages):
        self.pages = pages
        self.list_calls = []
        self.delete_calls = []

    def get_paginator(self, operation):
        assert operation == "list_objects_v2"
        return FakePaginator(self)

    def delete_object(self, **kwargs):
        self.delete_calls.append(kwargs)


def test_s3_inventory_is_prefix_scoped_and_hides_delete_handle():
    key = "private/field-collector/location/device/item.jpg"
    modified = NOW - timedelta(days=2)
    client = FakeS3Client([{"Contents": [{"Key": key, "LastModified": modified}]}])
    store = S3CompatibleMediaStore(client, "private-media")

    items = store.list_private_objects()
    store.delete_orphan(items[0])

    assert client.list_calls == [{"Bucket": "private-media", "Prefix": "private/field-collector/"}]
    assert items[0].object_id == store.object_id_for_key(key)
    assert key not in repr(items[0])
    assert client.delete_calls == [{"Bucket": "private-media", "Key": key}]


def test_s3_inventory_rejects_objects_outside_private_prefix():
    client = FakeS3Client([{"Contents": [{"Key": "public/image.jpg", "LastModified": NOW}]}])
    store = S3CompatibleMediaStore(client, "private-media")

    with pytest.raises(ValueError, match="Invalid private media key"):
        store.list_private_objects()
