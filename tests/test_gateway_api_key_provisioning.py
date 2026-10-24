"""Source-level safety contract for tenant-scoped API-key provisioning."""

from contextlib import AbstractContextManager
from datetime import datetime, timezone

import pytest

from services.gateway.api_key_provisioning import (
    ApiKeyProvisioningConflict,
    build_api_key_manifest,
    provision_api_key_manifest,
)

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
SECRET = "local-test-key-" + ("x" * 48)


class FakeResult:
    def __init__(self, row=None):
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row


class FakeConnection(AbstractContextManager):
    def __init__(self, existing=None, *, simulate_concurrent_insert=False):
        self.existing = existing
        self.simulate_concurrent_insert = simulate_concurrent_insert
        self.events = []

    def __enter__(self):
        self.events.append("open")
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.events.append("rollback" if exc_type else "commit")
        return False

    def execute(self, sql, params):
        compact_sql = " ".join(sql.split())
        self.events.append((compact_sql, params))
        if compact_sql.startswith("SELECT name, key_prefix"):
            if self.existing and self.existing.get("key_hash") == params["key_hash"]:
                return FakeResult(self.existing)
            return FakeResult()
        if compact_sql.startswith("INSERT INTO public.api_key"):
            if self.simulate_concurrent_insert:
                self.simulate_concurrent_insert = False
                self.existing = {
                    **params,
                    "is_active": True,
                    "expires_at": None,
                }
                return FakeResult()
            self.existing = {**params, "id": "synthetic-id"}
            return FakeResult({"id": "synthetic-id"})
        return FakeResult()


def test_manifest_hashes_keys_and_keeps_only_exact_location_scopes():
    manifest, ignored_scopes, excluded_keys = build_api_key_manifest(
        f"{SECRET}:reader,unscoped-key-" + ("y" * 40) + ":legacy",
        ",".join(
            [
                f"reader:data_stream_post:read:{LOCATION_ID}",
                "reader:data_stream_post:create:*",
                "reader:data_stream_post:read",
                "legacy:metric:read:*",
            ]
        ),
    )

    assert len(manifest) == 1
    assert manifest[0].name == "reader"
    assert manifest[0].key_hash != SECRET
    assert manifest[0].key_prefix == SECRET[:8]
    assert manifest[0].scopes == (f"data_stream_post:read:{LOCATION_ID}",)
    assert SECRET not in repr(manifest[0])
    assert ignored_scopes == 3
    assert excluded_keys == 1


@pytest.mark.parametrize(
    ("api_keys", "error"),
    [
        ("short:reader", "at least 32 characters"),
        (f"{SECRET}", "malformed key entry"),
        (f"{SECRET}:reader,{SECRET}:reader", "duplicate key"),
    ],
)
def test_manifest_rejects_weak_or_malformed_api_key_config(api_keys, error):
    with pytest.raises(ValueError, match=error):
        build_api_key_manifest(
            api_keys,
            f"reader:data_stream_post:read:{LOCATION_ID}",
        )


def test_dry_run_never_inserts_or_locks_api_key_rows():
    manifest, _, _ = build_api_key_manifest(
        f"{SECRET}:reader",
        f"reader:data_stream_post:read:{LOCATION_ID}",
    )
    connection = FakeConnection()

    summary = provision_api_key_manifest(connection, manifest)

    assert summary["planned_inserts"] == 1
    assert summary["inserted"] == 0
    assert len(connection.events) == 1
    sql, params = connection.events[0]
    assert sql.startswith("SELECT name, key_prefix")
    assert "FOR UPDATE" not in sql
    assert SECRET not in repr(params)


def test_apply_inserts_hash_and_exact_scopes_without_raw_secret():
    manifest, _, _ = build_api_key_manifest(
        f"{SECRET}:reader",
        f"reader:data_stream_post:read:{LOCATION_ID}",
    )
    connection = FakeConnection()

    summary = provision_api_key_manifest(connection, manifest, apply=True)

    assert summary["inserted"] == 1
    assert summary["planned_inserts"] == 0
    select_sql, select_params = connection.events[0]
    insert_sql, insert_params = connection.events[1]
    assert "FOR UPDATE" not in select_sql
    assert select_params["key_hash"] == manifest[0].key_hash
    assert insert_sql.startswith("INSERT INTO public.api_key")
    assert "ON CONFLICT (key_hash) DO NOTHING" in insert_sql
    assert insert_params["key_hash"] == manifest[0].key_hash
    assert insert_params["scopes"] == [f"data_stream_post:read:{LOCATION_ID}"]
    assert SECRET not in repr(connection.events)


def test_concurrent_insert_race_rechecks_the_matching_credential():
    manifest, _, _ = build_api_key_manifest(
        f"{SECRET}:reader",
        f"reader:data_stream_post:read:{LOCATION_ID}",
    )
    connection = FakeConnection(simulate_concurrent_insert=True)

    summary = provision_api_key_manifest(connection, manifest, apply=True)

    assert summary["inserted"] == 0
    assert summary["already_matching"] == 1
    assert len(connection.events) == 3


def test_matching_database_credential_is_idempotent():
    manifest, _, _ = build_api_key_manifest(
        f"{SECRET}:reader",
        f"reader:data_stream_post:read:{LOCATION_ID}",
    )
    key = manifest[0]
    connection = FakeConnection(
        existing={
            "name": key.name,
            "key_hash": key.key_hash,
            "key_prefix": key.key_prefix,
            "scopes": list(key.scopes),
            "expires_at": None,
            "is_active": True,
        }
    )

    summary = provision_api_key_manifest(connection, manifest, apply=True)

    assert summary["already_matching"] == 1
    assert summary["inserted"] == 0
    assert len(connection.events) == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("scopes", ["data_stream_post:read:*"]),
        ("is_active", False),
        ("expires_at", datetime.now(timezone.utc)),
        ("name", "different-label"),
    ],
)
def test_existing_conflict_fails_without_mutating_credential(field, value):
    manifest, _, _ = build_api_key_manifest(
        f"{SECRET}:reader",
        f"reader:data_stream_post:read:{LOCATION_ID}",
    )
    key = manifest[0]
    existing = {
        "name": key.name,
        "key_hash": key.key_hash,
        "key_prefix": key.key_prefix,
        "scopes": list(key.scopes),
        "expires_at": None,
        "is_active": True,
    }
    existing[field] = value
    connection = FakeConnection(existing)

    with pytest.raises(ApiKeyProvisioningConflict, match="reconcile or rotate"):
        provision_api_key_manifest(connection, manifest, apply=True)

    assert len(connection.events) == 1
    assert "UPDATE public.api_key" not in connection.events[0][0]
