"""
Ecology Analytics CLI

Command-line interface for soil carbon, biodiversity, and scenario comparison.

Usage:
    python3 -m services.analytics.cli --soil-carbon --location-id UUID
    python3 -m services.analytics.cli --biodiversity --location-id UUID
    python3 -m services.analytics.cli --compare-scenarios ID1 ID2
    python3 -m services.analytics.cli --sensitivity --scenario-id UUID --variable price
"""

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="Kokonut Intelligence Ecology Analytics")
    parser.add_argument("--soil-carbon", action="store_true", help="Compare soil carbon before/after")
    parser.add_argument("--biodiversity", action="store_true", help="Compute biodiversity metrics")
    parser.add_argument("--compare-scenarios", nargs="+", metavar="ID", help="Compare forecast scenarios side-by-side")
    parser.add_argument("--sensitivity", action="store_true", help="Run sensitivity analysis")
    parser.add_argument("--location-id", help="Location UUID (required for soil-carbon, biodiversity)")
    parser.add_argument("--scenario-id", help="Scenario UUID (required for sensitivity)")
    parser.add_argument("--variable", choices=["price", "yield", "cost"], default="price", help="Variable for sensitivity analysis")
    parser.add_argument("--range-pct", type=float, default=20.0, help="Percentage range for sensitivity (default: 20)")
    parser.add_argument("--steps", type=int, default=5, help="Number of steps for sensitivity (default: 5)")
    args = parser.parse_args()

    from ..ingestion.base import get_db

    if args.soil_carbon:
        if not args.location_id:
            parser.error("--soil-carbon requires --location-id")
        from .ecology import compare_soil_carbon
        conn = get_db()
        result = compare_soil_carbon(conn, args.location_id)
        conn.close()
        print(json.dumps(result, indent=2, default=str))
        return

    if args.biodiversity:
        if not args.location_id:
            parser.error("--biodiversity requires --location-id")
        from .ecology import compute_biodiversity
        conn = get_db()
        result = compute_biodiversity(conn, args.location_id)
        conn.close()
        print(json.dumps(result, indent=2, default=str))
        return

    if args.compare_scenarios:
        from .ecology import compare_scenarios
        result = compare_scenarios(args.compare_scenarios)
        print(json.dumps(result, indent=2, default=str))
        return

    if args.sensitivity:
        if not args.scenario_id:
            parser.error("--sensitivity requires --scenario-id")
        from .ecology import sensitivity_analysis
        result = sensitivity_analysis(args.scenario_id, args.variable, args.range_pct, args.steps)
        print(json.dumps(result, indent=2, default=str))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
