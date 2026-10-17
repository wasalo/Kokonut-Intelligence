"""Find and optionally remove old private media objects absent from PostgreSQL."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from services.common.cli import get_connection, print_json, run
from services.mobile.media_storage import PrivateMediaObject, create_media_store

_MAX_BATCH_SIZE = 500
_MIN_AGE_HOURS = 24
_MAX_AGE_HOURS = 24 * 365
_REGISTERED_KEYS_SQL = "SELECT object_key FROM mobile_media_upload"


class PrivateMediaReconcileError(RuntimeError):
    """Raised when inventory or deletion cannot be completed safely."""


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_BATCH_SIZE:
        raise ValueError(f"limit must be between 1 and {_MAX_BATCH_SIZE}")


def _validate_age(older_than_hours: int) -> None:
    if (
        isinstance(older_than_hours, bool)
        or not isinstance(older_than_hours, int)
        or not _MIN_AGE_HOURS <= older_than_hours <= _MAX_AGE_HOURS
    ):
        raise ValueError(f"older_than_hours must be between {_MIN_AGE_HOURS} and {_MAX_AGE_HOURS}")


def _registered_object_ids(connection_factory, store) -> set[str]:
    try:
        with connection_factory() as conn:
            rows = conn.execute(_REGISTERED_KEYS_SQL).all()
        return {store.object_id_for_key(row["object_key"]) for row in rows}
    except Exception as exc:  # noqa: BLE001 - DB errors may contain private values
        raise PrivateMediaReconcileError(
            f"Could not read registered media inventory ({type(exc).__name__})"
        ) from None


def _list_private_objects(store) -> list[PrivateMediaObject]:
    try:
        objects = list(store.list_private_objects())
    except Exception as exc:  # noqa: BLE001 - provider errors may contain bucket/key details
        raise PrivateMediaReconcileError(
            f"Could not list private media objects ({type(exc).__name__})"
        ) from None
    if len({item.object_id for item in objects}) != len(objects):
        raise PrivateMediaReconcileError("Provider inventory contains duplicate object identities")
    return objects


def reconcile_private_media(
    *,
    apply: bool = False,
    older_than_hours: int = _MIN_AGE_HOURS,
    limit: int = 100,
    connection_factory=None,
    media_store_factory=None,
    now: datetime | None = None,
) -> dict[str, int | str]:
    """Preview or delete a bounded set of aged objects with no upload row.

    The minimum age protects the upload-to-database commit window. Deletion is
    opt-in and never changes database records; object names and provider handles
    are intentionally excluded from the returned report.
    """
    _validate_limit(limit)
    _validate_age(older_than_hours)
    connect = connection_factory or get_connection
    make_store = media_store_factory or create_media_store
    inventory_time = now or datetime.now(timezone.utc)
    if inventory_time.tzinfo is None:
        inventory_time = inventory_time.replace(tzinfo=timezone.utc)
    inventory_time = inventory_time.astimezone(timezone.utc)
    cutoff = inventory_time - timedelta(hours=older_than_hours)

    try:
        store = make_store()
    except Exception as exc:  # noqa: BLE001 - provider errors may contain credentials/configuration
        raise PrivateMediaReconcileError(
            f"Could not configure private media inventory ({type(exc).__name__})"
        ) from None
    objects = _list_private_objects(store)
    registered_ids = _registered_object_ids(connect, store)
    unregistered = [item for item in objects if item.kind == "temporary" or item.object_id not in registered_ids]
    eligible = sorted(
        (item for item in unregistered if item.last_modified <= cutoff),
        key=lambda item: (item.last_modified, item.object_id),
    )
    result: dict[str, int | str] = {
        "mode": "apply" if apply else "dry-run",
        "provider_object_count": len(objects),
        "registered_object_count": len(registered_ids),
        "unregistered_object_count": len(unregistered),
        "eligible_count": len(eligible),
        "too_young_count": len(unregistered) - len(eligible),
        "limit": limit,
        "older_than_hours": older_than_hours,
        "deleted_count": 0,
        "skipped_registered_count": 0,
        "skipped_changed_count": 0,
    }
    if not apply:
        return result

    for item in eligible[:limit]:
        # Recheck immediately before deletion in case registration completed
        # after the first inventory snapshot.
        if item.kind == "object" and item.object_id in _registered_object_ids(connect, store):
            result["skipped_registered_count"] += 1
            continue
        current_objects = _list_private_objects(store)
        current = next((candidate for candidate in current_objects if candidate.object_id == item.object_id), None)
        if current is None or current.kind != item.kind or current.last_modified > cutoff:
            result["skipped_changed_count"] += 1
            continue
        try:
            store.delete_orphan(current)
        except Exception as exc:  # noqa: BLE001 - provider errors may contain private handles
            raise PrivateMediaReconcileError(
                f"Private media orphan deletion failed ({type(exc).__name__}); rerun the dry-run"
            ) from None
        result["deleted_count"] += 1

    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Reconcile unregistered Field Collector media objects")
    parser.add_argument("--apply", action="store_true", help="delete aged unregistered objects")
    parser.add_argument(
        "--older-than-hours",
        type=int,
        default=_MIN_AGE_HOURS,
        help=f"minimum object age in hours ({_MIN_AGE_HOURS}-{_MAX_AGE_HOURS}; default {_MIN_AGE_HOURS})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help=f"maximum objects to delete per invocation (1-{_MAX_BATCH_SIZE}; default 100)",
    )
    args = parser.parse_args(argv)
    print_json(
        reconcile_private_media(
            apply=args.apply,
            older_than_hours=args.older_than_hours,
            limit=args.limit,
        )
    )


if __name__ == "__main__":
    run(main)
