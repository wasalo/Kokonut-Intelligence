#!/usr/bin/env python3
"""Compatibility entry point for the retired mobile-offline CLI.

This CLI predates the consent-aware Field Collector and has no authenticated
tenant identity. Its former database helpers could read and mutate records
across tenant boundaries, so every operation now fails before touching a
connection. Use the Gateway Field Collector API and the operator console for
enrollment, device management, capture, and sync.
"""

from __future__ import annotations

from typing import NoReturn

from services.common.commands import CommandLine

_DISABLED_MESSAGE = (
    "The legacy mobile-offline CLI is disabled because it has no authenticated "
    "tenant identity. Use the consent-aware Field Collector Gateway and "
    "operator console."
)


def _reject_legacy_access(operation: str) -> NoReturn:
    """Fail closed before an old CLI path can access tenant records."""
    raise RuntimeError(f"{operation}: {_DISABLED_MESSAGE}")


def register_device(
    conn,
    device_id: str,
    device_name: str = None,
    device_type: str = "phone",
    os: str = None,
    os_version: str = None,
    app_version: str = None,
    user_id: str = None,
    location_id: str = None,
    push_token: str = None,
    has_camera: bool = True,
    has_gps: bool = True,
    has_offline: bool = True,
) -> dict:
    """Reject legacy registration; device enrollment must be owner-issued."""
    _reject_legacy_access("register device")


def list_devices(conn, user_id: str = None, location_id: str = None) -> list:
    """Reject unscoped device inventory reads."""
    _reject_legacy_access("list devices")


def queue_collection(
    conn,
    device_id: str,
    collection_type: str,
    payload: dict,
    user_id: str = None,
    location_id: str = None,
    latitude: float = None,
    longitude: float = None,
    accuracy_m: float = None,
    photo_refs: list = None,
    form_id: str = None,
    form_version: str = None,
    client_id: str = None,
) -> dict:
    """Reject legacy intake that bypasses immutable forms and consent."""
    _reject_legacy_access("queue collection")


def get_pending_collections(conn, device_id: str = None, limit: int = 100) -> list:
    """Reject pending-collection reads without a verified device context."""
    _reject_legacy_access("read pending collections")


def sync_collections(conn, device_id: str) -> dict:
    """Reject legacy sync; only the authenticated Field Collector may sync."""
    _reject_legacy_access("sync collections")


def resolve_conflict(
    conn,
    collection_id: str,
    resolution: str = "keep_server",
    resolved_by: str = None,
) -> dict:
    """Reject conflict writes without a tenant-qualified reviewer identity."""
    _reject_legacy_access("resolve collection conflict")


def get_sync_status(conn) -> dict:
    """Reject cross-tenant aggregate statistics through this legacy CLI."""
    _reject_legacy_access("read sync status")


def _disabled(_db, _args):
    _reject_legacy_access("run command")


cli = CommandLine(
    "mobile_offline",
    "Retired legacy CLI; use the consent-aware Field Collector Gateway",
)

# Keep the historic syntax discoverable for a clean migration error, but do
# not open a database connection for any legacy command.
cli.subcommand("register", "Disabled; use owner-issued Field Collector enrollment") \
    .add("--device-id", required=True) \
    .add("--name") \
    .add("--type", default="phone") \
    .add("--user") \
    .add("--location-id") \
    .add("--json", action="store_true") \
    .run(_disabled, needs_db=False)

cli.subcommand("queue", "Disabled; submit through the Field Collector") \
    .add("--device-id", required=True) \
    .add("--type", required=True, help="Collection type") \
    .add("--location-id") \
    .add("--payload", default="{}", help="JSON payload") \
    .add("--latitude", type=float) \
    .add("--longitude", type=float) \
    .add("--json", action="store_true") \
    .run(_disabled, needs_db=False)

cli.subcommand("sync", "Disabled; sync through the authenticated Field Collector") \
    .add("--device-id", required=True) \
    .add("--json", action="store_true") \
    .run(_disabled, needs_db=False)

cli.subcommand("status", "Disabled; use authenticated device sync status") \
    .add("--json", action="store_true") \
    .run(_disabled, needs_db=False)

cli.subcommand("devices", "Disabled; use the operator console") \
    .add("--user") \
    .add("--location-id") \
    .add("--json", action="store_true") \
    .run(_disabled, needs_db=False)


def main(argv=None):
    cli.run(argv)


if __name__ == "__main__":
    main()
