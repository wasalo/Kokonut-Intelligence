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
import json
import sys

from .engine import run_forecast, run_all_scenarios, load_scenario, load_scenario_by_name


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
    print(json.dumps(scenario.get("assumptions", {}), indent=2))
    print(f"\nPrice Assumptions:")
    print(json.dumps(scenario.get("price_assumptions", {}), indent=2))
    print(f"\nYield Assumptions:")
    print(json.dumps(scenario.get("yield_assumptions", {}), indent=2))
    print(f"\nCost Assumptions:")
    print(json.dumps(scenario.get("cost_assumptions", {}), indent=2))
    print(f"\nGrowth Assumptions:")
    print(json.dumps(scenario.get("growth_assumptions", {}), indent=2))

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
        print(json.dumps(result, indent=2))
        return

    if args.name:
        sc = load_scenario_by_name(args.name)
        if not sc:
            print(f"Scenario '{args.name}' not found.")
            sys.exit(1)
        result = run_forecast(str(sc["id"]))
        print(json.dumps(result, indent=2))
        return

    if args.all:
        print("Running all scenarios...")
        results = run_all_scenarios(args.location_id)
        print(f"\nCompleted {len(results)} scenarios.")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
