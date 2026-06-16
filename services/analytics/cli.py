"""
Ecology Analytics CLI

Command-line interface for soil carbon, biodiversity, scenario comparison,
NDVI trends, water resilience, crop diversity, intervention impact,
soil health, water access, and environmental baseline.

Usage:
    python3 -m services.analytics.cli --soil-carbon --location-id UUID
    python3 -m services.analytics.cli --biodiversity --location-id UUID
    python3 -m services.analytics.cli --compare-scenarios ID1 ID2
    python3 -m services.analytics.cli --sensitivity --scenario-id UUID --variable price
    python3 -m services.analytics.cli --ndvi-trends --location-id UUID
    python3 -m services.analytics.cli --water-resilience --location-id UUID
    python3 -m services.analytics.cli --crop-diversity --location-id UUID
    python3 -m services.analytics.cli --intervention-impact --location-id UUID
    python3 -m services.analytics.cli --soil-health --location-id UUID
    python3 -m services.analytics.cli --water-access --location-id UUID
    python3 -m services.analytics.cli --environmental-baseline --location-id UUID
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
    parser.add_argument("--ndvi-trends", action="store_true", help="Compute NDVI vegetation index trends")
    parser.add_argument("--water-resilience", action="store_true", help="Compute water resilience metrics")
    parser.add_argument("--crop-diversity", action="store_true", help="Compute crop diversity index")
    parser.add_argument("--intervention-impact", action="store_true", help="Analyze intervention impact")
    parser.add_argument("--soil-health", action="store_true", help="Analyze soil health (pH, NPK, organic matter)")
    parser.add_argument("--water-access", action="store_true", help="Summarize water access infrastructure")
    parser.add_argument("--environmental-baseline", action="store_true", help="Show environmental baselines and latest comparisons")
    parser.add_argument("--location-id", help="Location UUID (required for most flags)")
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

    if args.ndvi_trends:
        if not args.location_id:
            parser.error("--ndvi-trends requires --location-id")
        from .ecology import ndvi_trends
        conn = get_db()
        result = ndvi_trends(conn, args.location_id)
        conn.close()
        print(json.dumps(result, indent=2, default=str))
        return

    if args.water_resilience:
        if not args.location_id:
            parser.error("--water-resilience requires --location-id")
        from .ecology import water_resilience
        conn = get_db()
        result = water_resilience(conn, args.location_id)
        conn.close()
        print(json.dumps(result, indent=2, default=str))
        return

    if args.crop_diversity:
        if not args.location_id:
            parser.error("--crop-diversity requires --location-id")
        from .ecology import crop_diversity
        conn = get_db()
        result = crop_diversity(conn, args.location_id)
        conn.close()
        print(json.dumps(result, indent=2, default=str))
        return

    if args.intervention_impact:
        if not args.location_id:
            parser.error("--intervention-impact requires --location-id")
        from .ecology import intervention_impact
        conn = get_db()
        result = intervention_impact(conn, args.location_id)
        conn.close()
        print(json.dumps(result, indent=2, default=str))
        return

    if args.soil_health:
        if not args.location_id:
            parser.error("--soil-health requires --location-id")
        from .ecology import soil_health
        conn = get_db()
        result = soil_health(conn, args.location_id)
        conn.close()
        print(json.dumps(result, indent=2, default=str))
        return

    if args.water_access:
        if not args.location_id:
            parser.error("--water-access requires --location-id")
        from .ecology import water_access_summary
        conn = get_db()
        result = water_access_summary(conn, args.location_id)
        conn.close()
        print(json.dumps(result, indent=2, default=str))
        return

    if args.environmental_baseline:
        if not args.location_id:
            parser.error("--environmental-baseline requires --location-id")
        from .ecology import environmental_baseline
        conn = get_db()
        result = environmental_baseline(conn, args.location_id)
        conn.close()
        print(json.dumps(result, indent=2, default=str))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
