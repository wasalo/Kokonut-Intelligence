"""Narrow CLI entry point for the isolated sensor-anomaly ML worker."""

from __future__ import annotations

import argparse
import json
import uuid


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Location-scoped sensor anomaly ML")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--ml-check", action="store_true", help="Analyze one location")
    operation.add_argument("--ml-train", action="store_true", help="Train models for one location")
    parser.add_argument("--location-id", required=True, help="Location UUID")
    parser.add_argument("--sensor", help="Limit a check to one sensor UUID")
    args = parser.parse_args(argv)

    try:
        location_id = str(uuid.UUID(args.location_id))
    except (TypeError, ValueError, AttributeError):
        parser.error("--location-id must be a valid UUID")
    sensor_id = None
    if args.sensor is not None:
        if args.ml_train:
            parser.error("--ml-train saves location/type models and does not accept --sensor")
        try:
            sensor_id = str(uuid.UUID(args.sensor))
        except (TypeError, ValueError, AttributeError):
            parser.error("--sensor must be a valid UUID for ML checks")

    from services.ingestion.sensor_anomaly_ml_worker import run_sensor_anomaly_ml

    result = run_sensor_anomaly_ml(
        location_id,
        sensor_id=sensor_id,
        train=args.ml_train,
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
