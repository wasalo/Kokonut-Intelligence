"""
Forecast Engine CLI

Command-line interface for running forecasts and inspecting results.

Usage:
    python3 -m services.forecast.cli --list
    python3 -m services.forecast.cli --scenario-id <uuid>
    python3 -m services.forecast.cli --name "Baseline Forecast 2026"
    python3 -m services.forecast.cli --all
    python3 -m services.forecast.cli --location-id <uuid> --all
"""

import argparse
import sys

from .engine import run_forecast, run_all_scenarios, load_scenario, load_scenario_by_name
from services.common.cli import print_json

def list_scenarios():
    """List all forecast scenarios."""
    from ..ingestion.base import get_db
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT id, name, scenario_type, status, location_id
            FROM forecast_scenario
            ORDER BY created_at
        """)
        rows = cur.fetchall()
    db.close()

    if not rows:
        print("No forecast scenarios found.")
        return

    print(f"\n{'ID':<38} {'Name':<35} {'Type':<15} {'Status':<12}")
    print("-" * 100)
    for row in rows:
        print(f"{row[0]:<38} {row[1]:<35} {row[2]:<15} {row[3]:<12}")
    print()


def show_scenario_details(scenario_id: str):
    """Show detailed scenario assumptions and latest outputs."""
    scenario = load_scenario(scenario_id)
    if not scenario:
        print(f"Scenario {scenario_id} not found.")
        return

    print(f"\n{'='*60}")
    print(f"Scenario: {scenario['name']}")
    print(f"Type: {scenario.get('scenario_type', 'N/A')}")
    print(f"Status: {scenario.get('status', 'N/A')}")
    print(f"{'='*60}")

    print(f"\nAssumptions:")
    print_json(scenario.get("assumptions", {}))
    print(f"\nPrice Assumptions:")
    print_json(scenario.get("price_assumptions", {}))
    print(f"\nYield Assumptions:")
    print_json(scenario.get("yield_assumptions", {}))
    print(f"\nCost Assumptions:")
    print_json(scenario.get("cost_assumptions", {}))
    print(f"\nGrowth Assumptions:")
    print_json(scenario.get("growth_assumptions", {}))

    # Show outputs
    from ..ingestion.base import get_db
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT metric_name, value, unit, confidence_low, confidence_high
            FROM forecast_output
            WHERE scenario_id = %s
            ORDER BY metric_name
        """, (scenario_id,))
        rows = cur.fetchall()
    db.close()

    if rows:
        print(f"\nForecast Outputs:")
        print(f"{'Metric':<35} {'Value':>12} {'Unit':<10} {'Low':>12} {'High':>12}")
        print("-" * 83)
        for row in rows:
            print(f"{row[0]:<35} {row[1]:>12,.2f} {row[2]:<10} {row[3]:>12,.2f} {row[4]:>12,.2f}")
    else:
        print("\nNo forecast outputs calculated yet.")


def main():
    parser = argparse.ArgumentParser(description="Kokonut Intelligence Forecast Engine")
    parser.add_argument("--list", action="store_true", help="List all scenarios")
    parser.add_argument("--scenario-id", help="Run forecast for a specific scenario UUID")
    parser.add_argument("--name", help="Run forecast by scenario name")
    parser.add_argument("--all", action="store_true", help="Run all scenarios")
    parser.add_argument("--location-id", help="Filter by location UUID")
    parser.add_argument("--details", action="store_true", help="Show detailed scenario info (requires --scenario-id or --name)")
    parser.add_argument("--compare", nargs="+", metavar="ID", help="Compare scenarios side-by-side")
    parser.add_argument("--sensitivity", action="store_true", help="Run sensitivity analysis (requires --scenario-id)")
    parser.add_argument("--variable", choices=["price", "yield", "cost"], default="price", help="Variable for sensitivity")
    parser.add_argument("--range-pct", type=float, default=20.0, help="Range pct for sensitivity")
    parser.add_argument("--sensitivity-steps", type=int, default=5, help="Steps for sensitivity")
    parser.add_argument("--reference-class", action="store_true", help="Apply reference-class dampening to a location projection")
    parser.add_argument("--rc-metric", default="crop_noi", help="Metric for reference-class blend")
    parser.add_argument("--rc-alpha", type=float, default=0.5, help="Weight on self-projection (0-1)")
    args = parser.parse_args()

    if args.list:
        list_scenarios()
        return

    if args.details:
        scenario_id = args.scenario_id
        if not scenario_id and args.name:
            sc = load_scenario_by_name(args.name)
            scenario_id = str(sc["id"]) if sc else None
        if scenario_id:
            show_scenario_details(scenario_id)
        else:
            print("Error: --details requires --scenario-id or --name")
        return

    if args.scenario_id:
        result = run_forecast(args.scenario_id)
        print_json(result)
        return

    if args.name:
        sc = load_scenario_by_name(args.name)
        if not sc:
            print(f"Scenario '{args.name}' not found.")
            sys.exit(1)
        result = run_forecast(str(sc["id"]))
        print_json(result)
        return

    if args.all:
        print("Running all scenarios...")
        results = run_all_scenarios(args.location_id)
        print(f"\nCompleted {len(results)} scenarios.")
        return

    if args.compare:
        from ..analytics.ecology import compare_scenarios
        result = compare_scenarios(args.compare)
        print_json(result)
        return

    if args.sensitivity:
        if not args.scenario_id:
            parser.error("--sensitivity requires --scenario-id")
        from ..analytics.ecology import sensitivity_analysis
        result = sensitivity_analysis(args.scenario_id, args.variable, args.range_pct, args.sensitivity_steps)
        print_json(result)
        return

    if args.reference_class:
        if not args.location_id:
            parser.error("--reference-class requires --location-id")
        from ..ingestion.base import get_db
        from .reference_class import apply_reference_class
        conn = get_db()
        try:
            result = apply_reference_class(conn, args.location_id, args.rc_metric, args.rc_alpha)
        finally:
            conn.close()
        print_json(result)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
