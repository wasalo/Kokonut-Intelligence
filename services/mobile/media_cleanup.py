"""Expire unconsumed Field Collector media objects safely.

The command is dry-run by default. Apply mode handles only registered uploads
that have expired and remain unattached to a collection. Attached media remains
available for governed retention or erasure workflows.
"""

from __future__ import annotations

import argparse

from services.common.cli import get_connection, print_json, run
from services.mobile.media_storage import create_media_store

_MAX_BATCH_SIZE = 500

_COUNT_SQL = """
SELECT COUNT(*) AS eligible_count
FROM mobile_media_upload
WHERE status = 'uploaded'
  AND attached_collection_id IS NULL
  AND expires_at <= NOW()
"""

_CLAIM_SQL = """
SELECT media_id::text AS media_id, object_key
FROM mobile_media_upload
WHERE status = 'uploaded'
  AND attached_collection_id IS NULL
  AND expires_at <= NOW()
ORDER BY expires_at, media_id
LIMIT 1
FOR UPDATE SKIP LOCKED
"""

_EXPIRE_SQL = """
UPDATE mobile_media_upload
SET status = 'expired'
WHERE media_id = :media_id::uuid
  AND status = 'uploaded'
  AND attached_collection_id IS NULL
  AND expires_at <= NOW()
"""


class PrivateMediaCleanupError(RuntimeError):
    """Raised when one expired upload cannot be safely finalized."""


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_BATCH_SIZE:
        raise ValueError(f"limit must be between 1 and {_MAX_BATCH_SIZE}")


def expire_uploaded_media(
    *,
    apply: bool = False,
    limit: int = 100,
    connection_factory=None,
    media_store_factory=None,
) -> dict[str, int | str]:
    """Preview or expire a bounded set of overdue, unattached uploads.

    The object is deleted while its row is locked, then the row is marked
    expired in the same database transaction. If deletion or commit fails, the
    row stays eligible for an idempotent retry; attached rows are never selected.
    """
    _validate_limit(limit)
    connect = connection_factory or get_connection
    make_store = media_store_factory or create_media_store

    with connect() as conn:
        eligible = conn.execute(_COUNT_SQL).all()[0]["eligible_count"]

    result: dict[str, int | str] = {
        "mode": "apply" if apply else "dry-run",
        "eligible_count": eligible,
        "limit": limit,
        "expired_count": 0,
    }
    if not apply or not eligible:
        return result

    store = make_store()
    for _ in range(min(eligible, limit)):
        with connect() as conn:
            rows = conn.execute(_CLAIM_SQL).all()
            if not rows:
                break
            media = rows[0]
            try:
                store.delete_private(media["object_key"])
            except Exception as exc:  # noqa: BLE001 - provider errors can include private object keys
                raise PrivateMediaCleanupError(
                    f"Private object deletion failed ({type(exc).__name__}); upload remains eligible for retry"
                ) from None

            updated = conn.execute(_EXPIRE_SQL, {"media_id": media["media_id"]})
            if updated.rowcount != 1:
                raise PrivateMediaCleanupError("Upload state changed while cleanup was in progress")
        result["expired_count"] += 1

    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Expire unattached Field Collector media uploads")
    parser.add_argument("--apply", action="store_true", help="delete expired private objects and mark upload rows expired")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help=f"maximum uploads to expire per invocation (1-{_MAX_BATCH_SIZE}; default 100)",
    )
    args = parser.parse_args(argv)
    print_json(expire_uploaded_media(apply=args.apply, limit=args.limit))


if __name__ == "__main__":
    run(main)
