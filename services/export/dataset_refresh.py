#!/usr/bin/env python3
"""
Dataset Refresh Engine — Execute registered dashboard_dataset queries

Reads stable query IDs and exact-location scope from dashboard_dataset,
executes reviewed source-controlled SQL contracts, and updates refresh metadata.

Usage:
    python3 -m services.export.dataset_refresh
    python3 -m services.export.dataset_refresh --dataset-id UUID
    python3 -m services.export.dataset_refresh --list
"""

import argparse
import json
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from services.analytics.reporting_reader import (
    count_registered_reporting_rows,
    resolve_registered_reporting_query,
    safe_query_error,
)
from services.core.features import require_feature


def _dataset_failure_summary(exc: Exception, *, operation: str = "refresh") -> str:
    """Return an operator-safe dataset failure without private error contents."""
    name = type(exc).__name__
    if not name.isascii() or not name.isidentifier() or len(name) > 64:
        name = "Exception"
    return f"dataset {operation} failed ({name})"


def get_pg():
    from services.common.database import get_db

    return get_db()


def list_datasets(conn, dataset_id: str = None):
    """List existing dashboard datasets."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if dataset_id:
            cur.execute(
                "SELECT id, name, dataset_type, query_id, location_id, status, refresh_interval_minutes, last_refreshed_at, created_at FROM dashboard_dataset WHERE id = %s",
                (dataset_id,),
            )
        else:
            cur.execute(
                "SELECT id, name, dataset_type, query_id, location_id, status, refresh_interval_minutes, last_refreshed_at, created_at FROM dashboard_dataset WHERE status = 'active' ORDER BY name"
            )
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()


def refresh_dataset(conn, dataset_id: str) -> dict:
    """Run an active registered query as the reporting role; update metadata as app."""
    require_feature("legacy_dataset_sql")
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        # Fetch dataset definition
        cur.execute(
            "SELECT id, name, dataset_type, query_id, location_id, refresh_interval_minutes "
            "FROM dashboard_dataset WHERE id = %s AND status = 'active'",
            (dataset_id,),
        )
        dataset = cur.fetchone()
    finally:
        cur.close()

    if not dataset:
        raise ValueError(f"Active dataset {dataset_id} not found")

    query_id = dataset.get("query_id")
    location_id = dataset.get("location_id")
    # Configuration errors are rejected before either opening the reporting
    # connection or writing a misleading refresh-failure record.
    resolve_registered_reporting_query(query_id, location_id)

    start_time = datetime.now(timezone.utc)
    try:
        # Query execution uses a separate, credential- and ACL-verified
        # connection. Only a source-controlled query ID and its exact location
        # reach the reader; legacy query_sql text is never selected or executed.
        row_count = count_registered_reporting_rows(query_id, location_id)
        status = "active"
        error_message = None
    except Exception as exc:
        row_count = 0
        status = "error"
        error_message = safe_query_error(exc)
        print(f"  [Dataset] Read-only reporting query failed for {dataset['name']} ({error_message})")

    end_time = datetime.now(timezone.utc)
    duration_ms = int((end_time - start_time).total_seconds() * 1000)

    # Update dataset metadata
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE dashboard_dataset
            SET last_refreshed_at = NOW(),
                metadata = jsonb_set(
                    COALESCE(metadata, '{}'),
                    '{last_refresh}',
                    %s::jsonb
                )
            WHERE id = %s AND status = 'active'
              AND query_id IS NOT DISTINCT FROM %s
              AND location_id IS NOT DISTINCT FROM %s
            """,
            (
                json.dumps(
                    {
                        "row_count": row_count,
                        "duration_ms": duration_ms,
                        "status": status,
                        "error": error_message,
                        "refreshed_at": end_time.isoformat(),
                    }
                ),
                dataset_id,
                query_id,
                location_id,
            ),
        )
        if cur.rowcount != 1:
            raise RuntimeError("Active dataset changed while its reporting query ran")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()

    return {
        "dataset_id": dataset_id,
        "name": dataset["name"],
        "row_count": row_count,
        "duration_ms": duration_ms,
        "status": status,
        "error": error_message,
    }


def main():
    parser = argparse.ArgumentParser(description="Dashboard Dataset Refresh Engine")
    parser.add_argument("--dataset-id", help="Specific dataset UUID to refresh")
    parser.add_argument("--list", action="store_true", help="List existing datasets")
    parser.add_argument("--all", action="store_true", help="Refresh all active datasets")
    args = parser.parse_args()

    if args.all and args.list:
        parser.error("--all cannot be combined with --list")
    if args.all and args.dataset_id:
        parser.error("--all cannot be combined with --dataset-id")

    # Listing is a read-only inventory operation and remains available while
    # the legacy SQL runner is disabled. Reject refresh requests before opening
    # the application database so an off feature has no connection side effect.
    if not args.list and (args.all or args.dataset_id):
        require_feature("legacy_dataset_sql")

    if not (args.list or args.all or args.dataset_id):
        parser.print_help()
        return

    conn = get_pg()

    if args.list:
        try:
            datasets = list_datasets(conn, args.dataset_id)
            if not datasets:
                print("No active datasets found.")
            else:
                print(
                    f"{'ID':<38} {'Name':<30} {'Type':<15} {'Query ID':<42} "
                    f"{'Location':<38} {'Status':<10} {'Interval':<10} {'Last Refreshed'}"
                )
                print("-" * 140)
                for d in datasets:
                    interval = f"{d['refresh_interval_minutes']}min" if d["refresh_interval_minutes"] else "manual"
                    last = str(d["last_refreshed_at"] or "never")[:19]
                    print(
                        f"{str(d['id']):<38} {d['name']:<30} {d['dataset_type'] or '':<15} "
                        f"{d['query_id'] or '':<42} {str(d['location_id'] or ''):<38} "
                        f"{d['status']:<10} {interval:<10} {last}"
                    )
        except Exception as exc:
            safe_error = _dataset_failure_summary(exc, operation="inventory")
            print(f"  ✗ {safe_error}")
            raise RuntimeError(safe_error) from None
        finally:
            conn.close()
        return

    if args.dataset_id:
        # Refresh single dataset
        print(f"Refreshing dataset {args.dataset_id}...")
        try:
            result = refresh_dataset(conn, args.dataset_id)
            if result["status"] == "active":
                print(
                    f"  ✓ {result['name']}: {result['row_count']} rows "
                    f"in {result['duration_ms']}ms"
                )
            else:
                print("  ✗ dataset refresh failed (reported query error)")
        except Exception as exc:
            safe_error = _dataset_failure_summary(exc)
            print(f"  ✗ {safe_error}")
            raise RuntimeError(safe_error) from None
        finally:
            conn.close()
        return

    if args.all:
        try:
            # Inventory all active datasets, but execute only contracts that
            # have a registered ID and a valid exact-location scope.
            try:
                datasets = list_datasets(conn)
            except Exception as exc:
                safe_error = _dataset_failure_summary(exc, operation="inventory")
                print(f"  ✗ {safe_error}")
                raise RuntimeError(safe_error) from None
            if not datasets:
                print("No active datasets found.")
                return

            eligible_datasets = []
            skipped = 0
            for dataset in datasets:
                try:
                    resolve_registered_reporting_query(
                        dataset.get("query_id"), dataset.get("location_id")
                    )
                except ValueError:
                    skipped += 1
                else:
                    eligible_datasets.append(dataset)

            if skipped:
                print(f"  - Skipped {skipped} active dataset(s) without a registered exact-location query")
            if not eligible_datasets:
                print("No registered datasets are eligible for refresh.")
                return

            print(f"Refreshing {len(eligible_datasets)} datasets...")
            success = 0
            failed = 0
            for d in eligible_datasets:
                try:
                    result = refresh_dataset(conn, str(d["id"]))
                    status_icon = "✓" if result["status"] == "active" else "✗"
                    if result["status"] == "active":
                        print(f"  {status_icon} {result['name']}: {result['row_count']} rows in {result['duration_ms']}ms")
                        success += 1
                    else:
                        print("  ✗ dataset refresh failed (reported query error)")
                        failed += 1
                except Exception as exc:
                    print(f"  ✗ {_dataset_failure_summary(exc)}")
                    failed += 1

            print(f"\nDone: {success} refreshed, {failed} failed, {skipped} skipped")
        finally:
            conn.close()
        return

if __name__ == "__main__":
    main()
