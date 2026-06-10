#!/usr/bin/env python3
"""
Baserow to PostgreSQL Migration Script

Migrates data from Baserow API into the Kokonut Intelligence Platform
PostgreSQL schema via Directus REST API.

Usage:
    python migrate.py --config config.json --dry-run
    python migrate.py --config config.json --execute

Requires: pip install requests
"""

import argparse
import hashlib
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("baserow-migrate")


class BaserowClient:
    """Client for Baserow REST API."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Token {token}"}

    def list_tables(self) -> list[dict]:
        """List all tables across all databases."""
        resp = requests.get(
            f"{self.base_url}/api/database/tables/all-tables/",
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def get_fields(self, table_id: int) -> list[dict]:
        """Get field definitions for a table."""
        resp = requests.get(
            f"{self.base_url}/api/database/fields/table/{table_id}/",
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def get_rows(self, table_id: int, page: int = 1, size: int = 200) -> dict:
        """Get paginated rows from a table."""
        resp = requests.get(
            f"{self.base_url}/api/database/rows/table/{table_id}/",
            headers=self.headers,
            params={
                "user_field_names": "true",
                "page": page,
                "size": size,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def get_all_rows(self, table_id: int) -> list[dict]:
        """Fetch all rows with automatic pagination."""
        all_rows = []
        page = 1
        while True:
            data = self.get_rows(table_id, page=page)
            all_rows.extend(data.get("results", []))
            if not data.get("next"):
                break
            page += 1
            time.sleep(0.1)  # Rate limit courtesy
        return all_rows


class DirectusClient:
    """Client for Directus REST API."""

    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.token = None
        self._login(email, password)

    def _login(self, email: str, password: str):
        resp = requests.post(
            f"{self.base_url}/auth/login",
            json={"email": email, "password": password},
        )
        resp.raise_for_status()
        self.token = resp.json()["data"]["access_token"]
        logger.info("Authenticated with Directus")

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def create_item(self, collection: str, data: dict) -> dict:
        resp = requests.post(
            f"{self.base_url}/items/{collection}",
            headers=self.headers,
            json=data,
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def create_items(self, collection: str, items: list[dict]) -> list[dict]:
        resp = requests.post(
            f"{self.base_url}/items/{collection}",
            headers=self.headers,
            json=items,
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def log_ingestion(self, data: dict):
        """Log migration event to ingestion_log table."""
        try:
            self.create_item("ingestion_log", data)
        except Exception as e:
            logger.warning(f"Failed to log ingestion: {e}")


class FieldMapper:
    """Maps Baserow fields to canonical schema columns."""

    def __init__(self, mapping_config: dict):
        self.mappings = mapping_config

    def map_table(self, baserow_table_name: str) -> dict | None:
        return self.mappings.get("tables", {}).get(baserow_table_name)

    def transform_row(
        self, row: dict, field_defs: list[dict], table_mapping: dict
    ) -> dict:
        """Transform a Baserow row to canonical schema format."""
        result = {}

        for baserow_field, target_col in table_mapping.get("field_map", {}).items():
            value = row.get(baserow_field)
            if value is not None:
                # Apply type transformations
                transform = table_mapping.get("transforms", {}).get(baserow_field)
                if transform:
                    value = self._apply_transform(value, transform)
                result[target_col] = value

        # Add source lineage
        result["source_system"] = "baserow"
        result["source_id"] = str(row.get("id", ""))

        return result

    def _apply_transform(self, value: Any, transform: str) -> Any:
        """Apply a named transform to a value."""
        transforms = {
            "date_to_iso": lambda v: v if v else None,
            "number": lambda v: float(v) if v else None,
            "string": lambda v: str(v) if v else None,
            "bool": lambda v: v if isinstance(v, bool) else str(v).lower() in ("true", "yes", "1"),
        }
        fn = transforms.get(transform, lambda v: v)
        return fn(value)


def load_config(config_path: str) -> dict:
    """Load migration configuration."""
    with open(config_path) as f:
        return json.load(f)


def compute_hash(data: Any) -> str:
    """Compute SHA-256 hash of data for lineage tracking."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def run_migration(config: dict, dry_run: bool = True):
    """Execute the migration."""
    baserow = BaserowClient(
        config["baserow"]["url"],
        config["baserow"]["token"],
    )

    if not dry_run:
        directus = DirectusClient(
            config["directus"]["url"],
            config["directus"]["email"],
            config["directus"]["password"],
        )

    mapper = FieldMapper(config.get("field_mappings", {}))

    # Discover tables
    tables = baserow.list_tables()
    logger.info(f"Found {len(tables)} Baserow tables")

    table_map = config.get("table_map", {})
    total_rows_migrated = 0

    for table in tables:
        table_name = table.get("name", "")
        table_id = table.get("id")

        target_collection = table_map.get(table_name)
        if not target_collection:
            logger.info(f"Skipping unmapped table: {table_name} (id={table_id})")
            continue

        table_mapping = mapper.map_table(table_name)
        if not table_mapping:
            logger.warning(f"No field mapping for table: {table_name}")
            continue

        logger.info(f"Migrating: {table_name} → {target_collection}")

        # Get fields and rows
        fields = baserow.get_fields(table_id)
        rows = baserow.get_all_rows(table_id)
        logger.info(f"  Fetched {len(rows)} rows from {table_name}")

        # Transform rows
        transformed = []
        for row in rows:
            mapped = mapper.transform_row(row, fields, table_mapping)
            if mapped:
                transformed.append(mapped)

        if dry_run:
            logger.info(f"  [DRY RUN] Would insert {len(transformed)} rows into {target_collection}")
            if transformed:
                logger.info(f"  Sample: {json.dumps(transformed[0], indent=2, default=str)[:500]}")
        else:
            # Batch insert (50 at a time)
            batch_size = 50
            for i in range(0, len(transformed), batch_size):
                batch = transformed[i : i + batch_size]
                try:
                    directus.create_items(target_collection, batch)
                    logger.info(f"  Inserted batch {i // batch_size + 1}: {len(batch)} rows")
                except Exception as e:
                    logger.error(f"  Failed batch {i // batch_size + 1}: {e}")

            # Log ingestion
            directus.log_ingestion({
                "source_system": "baserow",
                "source_table": table_name,
                "target_table": target_collection,
                "operation": "insert",
                "payload_hash": compute_hash(transformed),
                "status": "success",
                "rows_affected": len(transformed),
            })

        total_rows_migrated += len(transformed)

    logger.info(f"Migration complete. Total rows: {total_rows_migrated}")


def main():
    parser = argparse.ArgumentParser(description="Baserow to PostgreSQL migration")
    parser.add_argument("--config", required=True, help="Path to config JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without inserting")
    parser.add_argument("--execute", action="store_true", help="Execute migration")
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        logger.error("Must specify either --dry-run or --execute")
        sys.exit(1)

    config = load_config(args.config)
    run_migration(config, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
