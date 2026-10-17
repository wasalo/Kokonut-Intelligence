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
from uuid import UUID

from services.common.cli import get_connection, print_json, run


def main():
    parser = argparse.ArgumentParser(description="Kokonut Metric Computation Engine")
    parser.add_argument("--compute", action="store_true", help="Compute metrics")
    parser.add_argument("--metric", help="Specific metric_key to compute")
    parser.add_argument("--all", action="store_true", help="Compute all active metrics")
    location_scope = parser.add_mutually_exclusive_group()
    location_scope.add_argument(
        "--all-locations",
        action="store_true",
        help="Explicitly compute/reconcile across all locations (manual operation)",
    )
    parser.add_argument("--list", action="store_true", help="List all metric definitions")
    location_scope.add_argument("--location-id", help="Location UUID")
    parser.add_argument("--period-start", help="Period start date (YYYY-MM-DD)")
    parser.add_argument("--period-end", help="Period end date (YYYY-MM-DD)")
    parser.add_argument("--verify-value", help="Metric value UUID to verify")
    parser.add_argument("--verified-by", help="Human reviewer UUID (required with --verify-value)")
    parser.add_argument("--verification-notes", help="Reviewer notes")
    parser.add_argument(
        "--reconcile-noi-snapshots",
        action="store_true",
        help="Refresh eligible crop-cycle NOI snapshots from v_crop_cycle_noi",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.reconcile_noi_snapshots:
        if args.location_id is None and not args.all_locations:
            parser.error(
                "--reconcile-noi-snapshots requires --location-id or --all-locations"
            )
        if any((
            args.compute,
            args.metric,
            args.all,
            args.list,
            args.period_start,
            args.period_end,
            args.verify_value,
            args.verified_by,
            args.verification_notes,
        )):
            parser.error("--reconcile-noi-snapshots is a standalone operation")
        location_id = None
        if args.location_id is not None:
            try:
                location_id = str(UUID(str(args.location_id)))
            except (TypeError, ValueError, AttributeError):
                parser.error("--location-id must be a UUID")

        location_filter = ""
        parameters = {}
        if location_id is not None:
            location_filter = (
                " AND v.location_id = :location_id"
                " AND cc.location_id = :location_id"
            )
            parameters["location_id"] = location_id
        with get_connection() as conn:
            result = conn.execute(f"""
                INSERT INTO noi_snapshot (
                    crop_cycle_id, location_id, period_start, period_end,
                    gross_revenue, returns_and_discounts, net_revenue,
                    direct_crop_costs, allocated_shared_costs, total_costs,
                    noi, operating_margin_pct, loss_rate_pct,
                    calculation_version, calculated_at, inputs
                )
                SELECT
                    v.crop_cycle_id, v.location_id,
                    COALESCE(v.period_start, CURRENT_DATE),
                    COALESCE(v.period_end, v.period_start, CURRENT_DATE),
                    v.gross_revenue, v.returns_discounts, v.net_revenue,
                    v.direct_crop_costs, v.allocated_shared_costs,
                    v.total_costs, v.noi, v.operating_margin_pct,
                    v.loss_rate_pct, '1.0', NOW(),
                    jsonb_build_object(
                        'source_view', 'v_crop_cycle_noi',
                        'formula_version', '1.0'
                    )
                FROM v_crop_cycle_noi AS v
                JOIN crop_cycle AS cc ON cc.id = v.crop_cycle_id
                WHERE cc.status IN (
                    'active', 'flowering', 'harvesting', 'harvested', 'completed'
                )
                {location_filter}
                ON CONFLICT (crop_cycle_id) DO UPDATE SET
                    location_id = EXCLUDED.location_id,
                    period_start = EXCLUDED.period_start,
                    period_end = EXCLUDED.period_end,
                    gross_revenue = EXCLUDED.gross_revenue,
                    returns_and_discounts = EXCLUDED.returns_and_discounts,
                    net_revenue = EXCLUDED.net_revenue,
                    direct_crop_costs = EXCLUDED.direct_crop_costs,
                    allocated_shared_costs = EXCLUDED.allocated_shared_costs,
                    total_costs = EXCLUDED.total_costs,
                    noi = EXCLUDED.noi,
                    operating_margin_pct = EXCLUDED.operating_margin_pct,
                    loss_rate_pct = EXCLUDED.loss_rate_pct,
                    calculation_version = EXCLUDED.calculation_version,
                    calculated_at = EXCLUDED.calculated_at,
                    inputs = EXCLUDED.inputs
                RETURNING crop_cycle_id
            """, parameters)
        print_json({
            "status": "success",
            "reconciled": result.rowcount,
            "source": "v_crop_cycle_noi",
            "scope": "location" if location_id is not None else "all_locations",
            **({"location_id": location_id} if location_id is not None else {}),
        })
        return

    from ..ingestion.base import get_db

    if args.verify_value:
        if not args.verified_by:
            parser.error("--verify-value requires --verified-by")
        conn = get_db()
        try:
            from .engine import verify_metric_value
            result = verify_metric_value(
                conn, args.verify_value, args.verified_by, args.verification_notes
            )
        finally:
            conn.close()
        print_json(result)
        return

    if args.list:
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT metric_key, display_name, description, formula, unit,
                           data_type, update_frequency, active, version
                    FROM metric_definition
                    ORDER BY metric_key
                """)
                rows = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
        if args.json:
            print_json(rows)
        else:
            print(f"{'Key':<30} {'Display Name':<30} {'Unit':<10} {'Freq':<12} {'Active'}")
            print("-" * 100)
            for r in rows:
                print(f"{r['metric_key']:<30} {r['display_name']:<30} {r['unit'] or '':<10} {r['update_frequency'] or '':<12} {r['active']}")
        return

    if args.compute:
        conn = get_db()
        try:
            from .engine import compute_all, compute_metric

            if args.all_locations:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, name FROM location ORDER BY name")
                    locations = cur.fetchall()
                if not locations:
                    print("No locations found")
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
                if args.json:
                    print_json(all_results)
                if any(result.get("total_errors", 0) for result in all_results.values()):
                    raise SystemExit(1)
                return

            if not args.location_id:
                parser.error("--compute requires --location-id (or use --all-locations)")
            if args.all:
                result = compute_all(conn, args.location_id, args.period_start, args.period_end)
            elif args.metric:
                result = compute_metric(conn, args.metric, args.location_id, args.period_start, args.period_end)
            else:
                parser.error("--compute requires --metric, --all, or --all-locations")
            print_json(result)
            if result.get("total_errors", 0) or result.get("error"):
                raise SystemExit(1)
        finally:
            conn.close()
        return

    parser.print_help()


if __name__ == "__main__":
    run(main)
