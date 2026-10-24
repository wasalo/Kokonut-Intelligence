"""One-shot provisioning of exact, tenant-scoped Gateway API-key records.

The Gateway runtime authenticates raw keys from its environment, while
PostgreSQL revalidates a SHA-256 digest and exact location grants. This module
bridges those stores only from an explicitly supplied maintenance connection;
it is not called by the runtime app.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterable
from uuid import UUID

_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_KEY_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_MINIMUM_KEY_LENGTH = 32


@dataclass(frozen=True)
class ProvisionableApiKey:
    """A DB-safe key manifest entry; the raw secret is never retained."""

    name: str
    key_hash: str = field(repr=False)
    key_prefix: str = field(repr=False)
    scopes: tuple[str, ...]


class ApiKeyProvisioningConflict(RuntimeError):
    """An existing database credential differs from the reviewed manifest."""


def build_api_key_manifest(
    api_keys_value: str,
    scopes_value: str,
) -> tuple[list[ProvisionableApiKey], int, int]:
    """Parse environment keys into exact location-scoped rows.

    Returns ``(manifest, ignored_scope_count, excluded_key_count)``. Broad,
    wildcard, malformed, and location-free scopes are ignored because they
    cannot establish the signed Gateway tenant context.
    """
    keys_by_name: dict[str, list[tuple[str, str]]] = {}
    seen_hashes: set[str] = set()
    for entry in (api_keys_value or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        raw_key, separator, raw_name = entry.partition(":")
        raw_key = raw_key.strip()
        name = raw_name.strip()
        if not separator or not raw_key or not _KEY_NAME_RE.fullmatch(name):
            raise ValueError("KOKONUT_API_KEYS contains a malformed key entry")
        if len(raw_key) < _MINIMUM_KEY_LENGTH:
            raise ValueError("configured Gateway API keys must contain at least 32 characters")
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        if key_hash in seen_hashes:
            raise ValueError("KOKONUT_API_KEYS contains a duplicate key")
        seen_hashes.add(key_hash)
        keys_by_name.setdefault(name, []).append((raw_key[:8], key_hash))

    scopes_by_name: dict[str, set[str]] = {name: set() for name in keys_by_name}
    ignored_scope_count = 0
    for entry in (scopes_value or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        name = parts[0].strip() if parts else ""
        if name not in keys_by_name:
            continue
        if len(parts) != 4:
            ignored_scope_count += 1
            continue
        resource, action = parts[1].strip(), parts[2].strip()
        if not _IDENTIFIER_RE.fullmatch(resource) or not _IDENTIFIER_RE.fullmatch(action):
            ignored_scope_count += 1
            continue
        try:
            location_id = str(UUID(parts[3].strip()))
        except (TypeError, ValueError, AttributeError):
            ignored_scope_count += 1
            continue
        scopes_by_name[name].add(f"{resource}:{action}:{location_id}")

    manifest: list[ProvisionableApiKey] = []
    excluded_key_count = 0
    for name, configured_keys in keys_by_name.items():
        scopes = tuple(sorted(scopes_by_name[name]))
        if not scopes:
            excluded_key_count += len(configured_keys)
            continue
        for key_prefix, key_hash in configured_keys:
            manifest.append(
                ProvisionableApiKey(
                    name=name,
                    key_hash=key_hash,
                    key_prefix=key_prefix,
                    scopes=scopes,
                )
            )
    return manifest, ignored_scope_count, excluded_key_count


def _existing_key(connection: Any, key_hash: str) -> dict[str, Any] | None:
    result = connection.execute(
        """
        SELECT name, key_prefix, scopes, expires_at, is_active
          FROM public.api_key
         WHERE key_hash = :key_hash
        """,
        {"key_hash": key_hash},
    )
    row = result.mappings().first()
    return dict(row) if row else None


def _matches_manifest_row(existing: dict[str, Any], key: ProvisionableApiKey) -> bool:
    stored_scopes = tuple(sorted(existing.get("scopes") or ()))
    return (
        existing.get("name") == key.name
        and existing.get("key_prefix") == key.key_prefix
        and stored_scopes == key.scopes
        and existing.get("expires_at") is None
        and existing.get("is_active") is True
    )


def provision_api_key_manifest(
    connection: Any,
    manifest: Iterable[ProvisionableApiKey],
    *,
    apply: bool = False,
    ignored_scope_count: int = 0,
    excluded_key_count: int = 0,
) -> dict[str, int | bool]:
    """Review or insert missing rows, refusing all credential mutation.

    Existing records are accepted only when they already match the manifest,
    are active, and have no database expiry. Conflicts raise before any caller
    commits; the transaction-owning caller must roll back on error.
    """
    summary: dict[str, int | bool] = {
        "apply": apply,
        "configured_keys": 0,
        "planned_inserts": 0,
        "inserted": 0,
        "already_matching": 0,
        "ignored_scope_entries": ignored_scope_count,
        "excluded_unscoped_keys": excluded_key_count,
    }
    for key in manifest:
        summary["configured_keys"] = int(summary["configured_keys"]) + 1
        existing = _existing_key(connection, key.key_hash)
        if existing is None:
            if apply:
                inserted = connection.execute(
                    """
                    INSERT INTO public.api_key
                        (name, key_hash, key_prefix, scopes, is_active)
                    VALUES
                        (:name, :key_hash, :key_prefix, :scopes, TRUE)
                    ON CONFLICT (key_hash) DO NOTHING
                    RETURNING id
                    """,
                    {
                        "name": key.name,
                        "key_hash": key.key_hash,
                        "key_prefix": key.key_prefix,
                        "scopes": list(key.scopes),
                    },
                )
                if inserted.mappings().first() is not None:
                    summary["inserted"] = int(summary["inserted"]) + 1
                    continue
                # Another provisioner may have inserted this hash after our
                # initial read. Reconcile it without acquiring UPDATE rights.
                existing = _existing_key(connection, key.key_hash)
                if existing is not None and _matches_manifest_row(existing, key):
                    summary["already_matching"] = int(summary["already_matching"]) + 1
                    continue
                raise ApiKeyProvisioningConflict(
                    f"database credential '{key.name}' differs from the reviewed manifest; "
                    "reconcile or rotate it explicitly"
                )
            else:
                summary["planned_inserts"] = int(summary["planned_inserts"]) + 1
            continue

        if not _matches_manifest_row(existing, key):
            raise ApiKeyProvisioningConflict(
                f"database credential '{key.name}' differs from the reviewed manifest; "
                "reconcile or rotate it explicitly"
            )
        summary["already_matching"] = int(summary["already_matching"]) + 1

    return summary


def main(argv: list[str] | None = None) -> int:
    """Run a dry-run review or explicitly insert missing API-key rows."""
    from services.common.cli import print_json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="insert missing rows; never update or reactivate existing credentials",
    )
    args = parser.parse_args(argv)

    manifest, ignored_scopes, excluded_keys = build_api_key_manifest(
        os.environ.get("KOKONUT_API_KEYS", ""),
        os.environ.get("KOKONUT_API_KEY_SCOPES", ""),
    )
    if not manifest:
        print_json(
            {
                "apply": args.apply,
                "configured_keys": 0,
                "planned_inserts": 0,
                "inserted": 0,
                "already_matching": 0,
                "ignored_scope_entries": ignored_scopes,
                "excluded_unscoped_keys": excluded_keys,
                "database_connected": False,
            }
        )
        return 0

    dsn = os.environ.get("KOKONUT_API_KEY_PROVISIONER_DSN", "")
    if not dsn:
        raise ValueError(
            "KOKONUT_API_KEY_PROVISIONER_DSN is required; use a separate maintenance connection"
        )
    try:
        import psycopg2

        from services.common.database import DatabaseConnection

        raw_connection = psycopg2.connect(
            dsn,
            connect_timeout=8,
            application_name="kokonut-api-key-provisioner",
        )
    except Exception:
        raise RuntimeError("Gateway API-key maintenance connection failed; details suppressed") from None

    try:
        with DatabaseConnection(raw_connection, readonly=not args.apply) as connection:
            summary = provision_api_key_manifest(
                connection,
                manifest,
                apply=args.apply,
                ignored_scope_count=ignored_scopes,
                excluded_key_count=excluded_keys,
            )
    except ApiKeyProvisioningConflict:
        raise
    except Exception:
        raise RuntimeError(
            "Gateway API-key provisioning failed; transaction rolled back and details suppressed"
        ) from None
    print_json({**summary, "database_connected": True})
    return 0


if __name__ == "__main__":
    from services.common.cli import run

    run(main)
