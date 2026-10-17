#!/usr/bin/env python3
"""
Dataset Refresh Engine — Execute stored dashboard_dataset queries

Reads dashboard_dataset rows with embedded SQL queries, executes them
against PostgreSQL, and updates the last_refreshed_at timestamp.

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

from services.analytics.reporting_reader import count_reporting_rows, safe_query_error
from services.core.features import require_feature


def get_pg():
    from services.common.database import get_db

    return get_db()


def list_datasets(conn, dataset_id: str = None):
    """List existing dashboard datasets."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if dataset_id:
        cur.execute(
            "SELECT id, name, dataset_type, status, refresh_interval_minutes, last_refreshed_at, created_at FROM dashboard_dataset WHERE id = %s",
            (dataset_id,),
        )
    else:
        cur.execute(
            "SELECT id, name, dataset_type, status, refresh_interval_minutes, last_refreshed_at, created_at FROM dashboard_dataset WHERE status = 'active' ORDER BY name"
        )
    try:
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()


def refresh_dataset(conn, dataset_id: str) -> dict:
    """Run an active saved query as the reporting role; update metadata as app."""
    require_feature("legacy_dataset_sql")
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Fetch dataset definition
    cur.execute(
        "SELECT id, name, dataset_type, query_sql, refresh_interval_minutes "
        "FROM dashboard_dataset WHERE id = %s AND status = 'active'",
        (dataset_id,),
    )
    dataset = cur.fetchone()
    if not dataset:
        cur.close()
        raise ValueError(f"Active dataset {dataset_id} not found")

    query_sql = dataset["query_sql"]
    if not query_sql:
        cur.close()
        raise ValueError(f"Dataset {dataset['name']} has no query_sql defined")

    cur.close()
    start_time = datetime.now(timezone.utc)
    try:
        # Query execution uses a separate, credential- and ACL-verified
        # connection. The application connection never executes saved SQL.
        row_count = count_reporting_rows(query_sql)
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
            WHERE id = %s AND status = 'active' AND query_sql = %s
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
                query_sql,
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
        datasets = list_datasets(conn, args.dataset_id)
        if not datasets:
            print("No active datasets found.")
        else:
            print(f"{'ID':<38} {'Name':<30} {'Type':<15} {'Status':<10} {'Interval':<10} {'Last Refreshed'}")
            print("-" * 140)
            for d in datasets:
                interval = f"{d['refresh_interval_minutes']}min" if d["refresh_interval_minutes"] else "manual"
                last = str(d["last_refreshed_at"] or "never")[:19]
                print(
                    f"{str(d['id']):<38} {d['name']:<30} {d['dataset_type'] or '':<15} {d['status']:<10} {interval:<10} {last}"
                )
        conn.close()
        return

    if args.dataset_id:
        # Refresh single dataset
        print(f"Refreshing dataset {args.dataset_id}...")
        result = refresh_dataset(conn, args.dataset_id)
        status_icon = "✓" if result["status"] == "active" else "✗"
        print(f"  {status_icon} {result['name']}: {result['row_count']} rows in {result['duration_ms']}ms")
        if result["error"]:
            print(f"    Error: {result['error']}")
        conn.close()
        return

    if args.all:
        # Refresh all active datasets
        datasets = list_datasets(conn)
        if not datasets:
            print("No active datasets found.")
            conn.close()
            return

        print(f"Refreshing {len(datasets)} datasets...")
        success = 0
        failed = 0
        for d in datasets:
            try:
                result = refresh_dataset(conn, str(d["id"]))
                status_icon = "✓" if result["status"] == "active" else "✗"
                print(f"  {status_icon} {result['name']}: {result['row_count']} rows in {result['duration_ms']}ms")
                if result["status"] == "active":
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"  ✗ {d['name']}: {e}")
                failed += 1

        print(f"\nDone: {success} refreshed, {failed} failed")
        conn.close()
        return

if __name__ == "__main__":
    main()
