"""Safe expiry behavior for private Field Collector media uploads."""

import pytest

from services.mobile.media_cleanup import (
    PrivateMediaCleanupError,
    _validate_limit,
    expire_uploaded_media,
)


class FakeResult:
    def __init__(self, rows=None, rowcount=0):
        self._rows = rows or []
        self.rowcount = rowcount

    def all(self):
        return list(self._rows)


class FakeDatabase:
    def __init__(self, rows, events):
        self.rows = rows
        self.events = events

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.events.append("rollback" if exc_type else "commit")
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.lower().split())
        if "count(*) as eligible_count" in normalized:
            count = sum(_eligible(row) for row in self.rows)
            return FakeResult([{"eligible_count": count}])
        if normalized.startswith("select media_id::text as media_id"):
            assert "for update skip locked" in normalized
            candidates = sorted(
                (row for row in self.rows if _eligible(row)),
                key=lambda row: row["expires_at"],
            )
            return FakeResult(candidates[:1])
        if normalized.startswith("update mobile_media_upload"):
            self.events.append("update")
            for row in self.rows:
                if row["media_id"] == params["media_id"] and _eligible(row):
                    row["status"] = "expired"
                    return FakeResult(rowcount=1)
            return FakeResult(rowcount=0)
        raise AssertionError(f"unexpected SQL: {normalized}")


def _eligible(row):
    return row["status"] == "uploaded" and row["attached_collection_id"] is None and row["expired"]


class FakeStore:
    def __init__(self, events, *, fail=False):
        self.events = events
        self.fail = fail

    def delete_private(self, object_key):
        self.events.append(("delete", object_key))
        if self.fail:
            raise RuntimeError("synthetic provider failure includes private object details")


def _fixture_rows():
    return [
        {
            "media_id": "expired-unattached",
            "object_key": "private/field-collector/synthetic/expired.jpg",
            "status": "uploaded",
            "attached_collection_id": None,
            "expired": True,
            "expires_at": 1,
        },
        {
            "media_id": "expired-attached",
            "object_key": "private/field-collector/synthetic/attached.jpg",
            "status": "attached",
            "attached_collection_id": "collection-1",
            "expired": True,
            "expires_at": 2,
        },
        {
            "media_id": "still-live",
            "object_key": "private/field-collector/synthetic/live.jpg",
            "status": "uploaded",
            "attached_collection_id": None,
            "expired": False,
            "expires_at": 3,
        },
    ]


def _factories(rows, events, store=None, store_creations=None):
    def connection_factory():
        return FakeDatabase(rows, events)

    def media_store_factory():
        if store_creations is not None:
            store_creations.append(True)
        return store or FakeStore(events)

    return connection_factory, media_store_factory


def test_dry_run_counts_only_expired_unattached_uploads_without_loading_provider():
    rows = _fixture_rows()
    events = []
    created = []
    connect, make_store = _factories(rows, events, store_creations=created)

    result = expire_uploaded_media(connection_factory=connect, media_store_factory=make_store)

    assert result == {"mode": "dry-run", "eligible_count": 1, "limit": 100, "expired_count": 0}
    assert created == []
    assert not any(isinstance(event, tuple) and event[0] == "delete" for event in events)


def test_apply_deletes_object_before_marking_row_expired_and_respects_limit():
    rows = _fixture_rows()
    events = []
    connect, make_store = _factories(rows, events)

    result = expire_uploaded_media(apply=True, limit=1, connection_factory=connect, media_store_factory=make_store)

    assert result == {"mode": "apply", "eligible_count": 1, "limit": 1, "expired_count": 1}
    assert rows[0]["status"] == "expired"
    assert rows[1]["status"] == "attached"
    assert rows[2]["status"] == "uploaded"
    assert events.index(("delete", rows[0]["object_key"])) < events.index("update")


def test_provider_failure_does_not_mark_upload_expired_and_hides_provider_message():
    rows = _fixture_rows()
    events = []
    connect, make_store = _factories(rows, events, store=FakeStore(events, fail=True))

    with pytest.raises(PrivateMediaCleanupError, match="remains eligible for retry") as error:
        expire_uploaded_media(apply=True, connection_factory=connect, media_store_factory=make_store)

    assert "synthetic provider failure" not in str(error.value)
    assert rows[0]["status"] == "uploaded"
    assert "update" not in events
    assert "rollback" in events


@pytest.mark.parametrize("limit", [0, -1, 501, True, 1.5])
def test_batch_limit_is_bounded(limit):
    with pytest.raises(ValueError, match="limit must be between"):
        _validate_limit(limit)
