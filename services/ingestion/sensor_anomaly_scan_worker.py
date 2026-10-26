"""Default-off scheduled replay of durable sensor-reading events."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from uuid import UUID

from services.common.cli import print_json
from services.core.features import require_feature
from services.ingestion.sensor_anomaly_worker import replay_recent_sensor_reading_events


def _location(value: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("location_id must be a valid UUID") from exc


def _since(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc) - timedelta(hours=24)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("since must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise ValueError("since must include a timezone")
    return parsed.astimezone(timezone.utc)


def run(
    *, location_id: str, since: datetime | None = None, batch_size: int = 100
) -> dict[str, int]:
    """Run a per-location durable event replay; no shared DB fallback exists."""
    require_feature("isolated_sensor_anomaly_scan_worker")
    stable_location_id = _location(location_id)
    replay_since = since or (datetime.now(timezone.utc) - timedelta(hours=24))
    if replay_since.tzinfo is None:
        raise ValueError("since must include a timezone")
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or not 1 <= batch_size <= 100:
        raise ValueError("batch_size must be between 1 and 100")
    return replay_recent_sensor_reading_events(
        location_id=stable_location_id,
        since=replay_since.astimezone(timezone.utc),
        batch_size=batch_size,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Replay recent sensor anomaly events")
    parser.add_argument("--location-id", required=True)
    parser.add_argument("--since", help="ISO-8601 timestamp with timezone; defaults to 24 hours ago")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args(argv)
    try:
        location_id = _location(args.location_id)
        since = _since(args.since)
        if not 1 <= args.batch_size <= 100:
            parser.error("--batch-size must be between 1 and 100")
    except ValueError as exc:
        parser.error(str(exc))
    print_json(run(location_id=location_id, since=since, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
