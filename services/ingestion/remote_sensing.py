#!/usr/bin/env python3
"""
Remote Sensing Ingestion — CSV Upload

Imports NDVI/NDRE data from CSV files into remote_sensing_observation.
Supports manual upload of pre-processed satellite/drone data.

Expected CSV columns:
    plot_id, observation_date, source, ndvi, ndre, evi, canopy_cover_pct,
    bbox_west, bbox_south, bbox_east, bbox_north, cloud_cover_pct

Usage:
    python -m services.ingestion.remote_sensing --file data.csv
    python -m services.ingestion.remote_sensing --file data.csv --location-id <uuid>
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone

from ..common.logging import get_logger
from .base import get_db, log_ingestion, hash_payload

logger = get_logger("ingestion.remote_sensing")


REQUIRED_COLUMNS = {"plot_id", "observation_date"}
VALID_SOURCES = {"sentinel-2", "landsat", "drone", "planet", "modis", "naip", "manual"}


def validate_row(row: dict) -> list:
    """Validate a CSV row. Returns list of errors."""
    errors = []
    if not row.get("plot_id"):
        errors.append("missing plot_id")
    if not row.get("observation_date"):
        errors.append("missing observation_date")
    return errors


def parse_row(row: dict, location_id: str = None) -> dict:
    """Parse CSV row into remote_sensing_observation format."""
    return {
        "plot_id": row["plot_id"],
        "location_id": location_id or row.get("location_id"),
        "observation_date": row["observation_date"],
        "source": row.get("source", "manual"),
        "ndvi": float(row["ndvi"]) if row.get("ndvi") else None,
        "ndre": float(row["ndre"]) if row.get("ndre") else None,
        "evi": float(row["evi"]) if row.get("evi") else None,
        "savi": float(row["savi"]) if row.get("savi") else None,
        "canopy_cover_pct": float(row["canopy_cover_pct"]) if row.get("canopy_cover_pct") else None,
        "ndwi": float(row["ndwi"]) if row.get("ndwi") else None,
        "cloud_cover_pct": float(row["cloud_cover_pct"]) if row.get("cloud_cover_pct") else None,
        "bbox": None,
        "metadata": {},
    }


def build_bbox(row: dict):
    """Build GeoJSON bbox from CSV columns."""
    try:
        west = float(row.get("bbox_west", 0))
        south = float(row.get("bbox_south", 0))
        east = float(row.get("bbox_east", 0))
        north = float(row.get("bbox_north", 0))
        if west or south or east or north:
            return json.dumps([west, south, east, north])
    except (ValueError, TypeError):
        pass
    return None


def insert_observation(db, record: dict) -> str:
    """Insert remote sensing observation. Returns record ID."""
    bbox = build_bbox(record)
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO remote_sensing_observation
                (plot_id, location_id, observation_date, source,
                 ndvi, ndre, evi, savi, canopy_cover_pct, ndwi,
                 cloud_cover_pct, bbox, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                record["plot_id"], record.get("location_id"),
                record["observation_date"], record["source"],
                record.get("ndvi"), record.get("ndre"),
                record.get("evi"), record.get("savi"),
                record.get("canopy_cover_pct"), record.get("ndwi"),
                record.get("cloud_cover_pct"), bbox,
                json.dumps(record.get("metadata", {})),
            ),
        )
        return str(cur.fetchone()[0])


def run(file_path: str, location_id: str = None):
    """Main ingestion entry point."""
    db = get_db()
    success = 0
    errors = 0

    # If no location_id provided, build lookup from plot → farm → location
    plot_location_map = {}
    if not location_id:
        with db.cursor() as cur:
            cur.execute("""
                SELECT p.id, f.location_id
                FROM plot p
                JOIN farm f ON p.farm_id = f.id
                WHERE f.location_id IS NOT NULL
            """)
            for row in cur.fetchall():
                plot_location_map[str(row[0])] = str(row[1])

    with open(file_path, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info("Processing %d rows from %s...", len(rows), file_path)

    for i, row in enumerate(rows):
        validation_errors = validate_row(row)
        if validation_errors:
            errors += 1
            logger.warning("  ✗ Row %d: %s", i + 1, ', '.join(validation_errors))
            continue

        try:
            record = parse_row(row, location_id or plot_location_map.get(row.get("plot_id", "")))
            pg_id = insert_observation(db, record)

            log_ingestion(
                source_system="csv_upload",
                source_table="remote_sensing_csv",
                source_id=f"row_{i + 1}",
                target_table="remote_sensing_observation",
                target_id=pg_id,
                operation="insert",
                payload_hash=hash_payload(row),
                status="success",
                rows_affected=1,
            )
            success += 1

        except Exception as e:
            errors += 1
            log_ingestion(
                source_system="csv_upload",
                source_table="remote_sensing_csv",
                source_id=f"row_{i + 1}",
                target_table="remote_sensing_observation",
                target_id=None,
                operation="insert",
                payload_hash=hash_payload(row),
                status="failed",
                error_message=str(e),
            )
            logger.error("  ✗ Row %d: %s", i + 1, e)

    db.commit()
    db.close()
    logger.info("Done: %d success, %d errors", success, errors)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remote sensing CSV ingestion")
    parser.add_argument("--file", required=True, help="Path to CSV file")
    parser.add_argument("--location-id", help="Default location UUID for all records")
    args = parser.parse_args()
    run(file_path=args.file, location_id=args.location_id)
