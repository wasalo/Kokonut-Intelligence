"""
Ingestion Status CLI

Query ingestion_log and chain_indexer_status for monitoring.
"""

import argparse
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from ingestion.base import get_db


def query_ingestion_log(args):
    """Query recent ingestion log entries."""
    db = get_db()
    with db.cursor() as cur:
        conditions = []
        params = []

        if args.source:
            conditions.append("source_system = %s")
            params.append(args.source)
        if args.status_filter:
            conditions.append("status = %s")
            params.append(args.status_filter)
        if args.errors_only:
            conditions.append("status = 'failed'")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cur.execute(f"""
            SELECT source_system, target_table, status, error_message,
                   rows_affected, processing_time_ms, created_at
            FROM ingestion_log
            {where}
            ORDER BY created_at DESC
            LIMIT %s
        """, params + [args.limit])

        rows = cur.fetchall()

    db.close()

    if not rows:
        print("No ingestion records found.")
        return

    print(f"{'Source':<20} {'Target':<25} {'Status':<10} {'Rows':<6} {'Time(ms)':<10} {'Created':<20} Error")
    print("-" * 120)
    for r in rows:
        error = (r[3] or "")[:40]
        print(f"{r[0]:<20} {r[1]:<25} {r[2]:<10} {r[4] or 0:<6} {r[5] or 0:<10} {str(r[6])[:19]:<20} {error}")


def query_indexer_status(args):
    """Query chain indexer status."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT chain, indexer_type, last_synced_block, status,
                   error_message, last_synced_at
            FROM chain_indexer_status
            ORDER BY chain, indexer_type
        """)
        rows = cur.fetchall()
    db.close()

    if not rows:
        print("No indexer status records found.")
        return

    print(f"{'Chain':<15} {'Type':<12} {'Last Block':<12} {'Status':<12} {'Last Sync':<20} Error")
    print("-" * 90)
    for r in rows:
        error = (r[4] or "")[:40]
        print(f"{r[0]:<15} {r[1]:<12} {r[2] or 'N/A':<12} {r[3]:<12} {str(r[5])[:19] if r[5] else 'N/A':<20} {error}")


def show_summary(args):
    """Show ingestion summary statistics."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT source_system, status, COUNT(*) as cnt,
                   SUM(rows_affected) as total_rows
            FROM ingestion_log
            GROUP BY source_system, status
            ORDER BY source_system, status
        """)
        rows = cur.fetchall()
    db.close()

    if not rows:
        print("No ingestion records found.")
        return

    print(f"{'Source':<20} {'Status':<10} {'Count':<8} {'Total Rows':<12}")
    print("-" * 50)
    for r in rows:
        print(f"{r[0]:<20} {r[1]:<10} {r[2]:<8} {r[3] or 0:<12}")


def main():
    parser = argparse.ArgumentParser(description="Ingestion status monitoring")
    sub = parser.add_subparsers(dest="command")

    log_p = sub.add_parser("log", help="Query ingestion log")
    log_p.add_argument("--source", help="Filter by source system")
    log_p.add_argument("--status", dest="status_filter", help="Filter by status (success/failed/partial)")
    log_p.add_argument("--errors-only", action="store_true", help="Show only failed records")
    log_p.add_argument("--limit", type=int, default=20, help="Max rows (default: 20)")

    sub.add_parser("indexers", help="Show chain indexer status")
    sub.add_parser("summary", help="Show ingestion summary statistics")

    args = parser.parse_args()

    if args.command == "log":
        query_ingestion_log(args)
    elif args.command == "indexers":
        query_indexer_status(args)
    elif args.command == "summary":
        show_summary(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
