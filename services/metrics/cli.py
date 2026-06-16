"""
Metric Computation Engine

Reads metric definitions from the metric_definition table, dispatches
to the appropriate calculator, and writes results to metric_value.

Usage:
    python3 -m services.metrics --compute --metric value_flowed --location-id UUID
    python3 -m services.metrics --compute --all --location-id UUID
    python3 -m services.metrics --compute --all-locations
    python3 -m services.metrics --list
"""

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="Kokonut Metric Computation Engine")
    parser.add_argument("--compute", action="store_true", help="Compute metrics")
    parser.add_argument("--metric", help="Specific metric_key to compute")
    parser.add_argument("--all", action="store_true", help="Compute all active metrics")
    parser.add_argument("--all-locations", action="store_true", help="Compute all metrics for all locations")
    parser.add_argument("--list", action="store_true", help="List all metric definitions")
    parser.add_argument("--location-id", help="Location UUID")
    parser.add_argument("--period-start", help="Period start date (YYYY-MM-DD)")
    parser.add_argument("--period-end", help="Period end date (YYYY-MM-DD)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    from ..ingestion.base import get_db

    if args.list:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT metric_key, display_name, description, formula, unit,
                       data_type, update_frequency, active, version
                FROM metric_definition
                ORDER BY metric_key
            """)
            rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        if args.json:
            print(json.dumps(rows, indent=2, default=str))
        else:
            print(f"{'Key':<30} {'Display Name':<30} {'Unit':<10} {'Freq':<12} {'Active'}")
            print("-" * 100)
            for r in rows:
                print(f"{r['metric_key']:<30} {r['display_name']:<30} {r['unit'] or '':<10} {r['update_frequency'] or '':<12} {r['active']}")
        return

    if args.compute:
        conn = get_db()
        from .engine import compute_metric, compute_all

        if args.all_locations:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name FROM location ORDER BY name")
                locations = cur.fetchall()
            if not locations:
                print("No locations found")
                conn.close()
                return
            print(f"Computing metrics for {len(locations)} locations...")
            all_results = {}
            for loc in locations:
                loc_id = str(loc[0])
                loc_name = loc[1]
                result = compute_all(conn, loc_id, args.period_start, args.period_end)
                all_results[loc_name] = result
                computed = result.get("total_computed", 0)
                errors = result.get("total_errors", 0)
                print(f"  ✓ {loc_name}: {computed} computed, {errors} errors")
            conn.close()
            if args.json:
                print(json.dumps(all_results, indent=2, default=str))
            return

        if not args.location_id:
            parser.error("--compute requires --location-id (or use --all-locations)")
        if args.all:
            result = compute_all(conn, args.location_id, args.period_start, args.period_end)
        elif args.metric:
            result = compute_metric(conn, args.metric, args.location_id, args.period_start, args.period_end)
        else:
            parser.error("--compute requires --metric, --all, or --all-locations")
        conn.close()
        print(json.dumps(result, indent=2, default=str))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
