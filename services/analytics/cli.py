"""
Ecology Analytics CLI

Command-line interface for soil carbon, biodiversity, scenario comparison,
NDVI trends, water resilience, crop diversity, intervention impact,
soil health, water access, environmental baseline, carbon balance,
GHG emissions, and regenerative practice scoring.

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
    python3 -m services.analytics.cli --carbon-balance --location-id UUID
    python3 -m services.analytics.cli --ghg-emissions --location-id UUID
    python3 -m services.analytics.cli --tree-carbon --location-id UUID
    python3 -m services.analytics.cli --regenerative-score --location-id UUID
    python3 -m services.analytics.cli --emission-factors
    python3 -m services.analytics.cli --carbon-benchmarks
"""

import argparse

from services.common.cli import get_connection, print_json

# (argparse_attr, module, function) — all take (conn, location_id).
_DB_LOCATION_COMMANDS = [
    ("soil_carbon", "ecology", "compare_soil_carbon"),
    ("biodiversity", "ecology", "compute_biodiversity"),
    ("ndvi_trends", "ecology", "ndvi_trends"),
    ("water_resilience", "ecology", "water_resilience"),
    ("crop_diversity", "ecology", "crop_diversity"),
    ("intervention_impact", "ecology", "intervention_impact"),
    ("soil_health", "ecology", "soil_health"),
    ("water_access", "ecology", "water_access_summary"),
    ("environmental_baseline", "ecology", "environmental_baseline"),
    ("carbon_balance", "carbon_balance", "compute_carbon_balance"),
    ("ghg_emissions", "carbon_balance", "compute_ghg_emissions"),
    ("tree_carbon", "carbon_balance", "compute_tree_carbon"),
    ("regenerative_score", "carbon_balance", "compute_regenerative_score"),
]


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
    parser.add_argument("--carbon-balance", action="store_true", help="Compute carbon balance (sequestration vs emissions)")
    parser.add_argument("--ghg-emissions", action="store_true", help="Compute GHG emissions breakdown by category")
    parser.add_argument("--tree-carbon", action="store_true", help="Compute above-ground carbon from tree inventory")
    parser.add_argument("--regenerative-score", action="store_true", help="Compute regenerative practice score (0-25)")
    parser.add_argument("--emission-factors", action="store_true", help="List available GHG emission factors")
    parser.add_argument("--carbon-benchmarks", action="store_true", help="List carbon benchmarks for tree systems")
    parser.add_argument("--portfolio-summary", action="store_true", help="Summarize portfolio impact by theme with confidence labels")
    parser.add_argument("--ebf-portfolio-summary", action="store_true", help="Summarize EBF portfolio pillars as a messy roll-up without farm ranking")
    parser.add_argument("--location-id", help="Location UUID (required for most flags)")
    parser.add_argument("--scenario-id", help="Scenario UUID (required for sensitivity)")
    parser.add_argument("--variable", choices=["price", "yield", "cost"], default="price", help="Variable for sensitivity analysis")
    parser.add_argument("--range-pct", type=float, default=20.0, help="Percentage range for sensitivity (default: 20)")
    parser.add_argument("--steps", type=int, default=5, help="Number of steps for sensitivity (default: 5)")
    parser.add_argument("--pin-dependency", action="store_true", help="Detect governed records pinned by an unverified upstream")
    parser.add_argument("--propose-pin", action="store_true", help="Write DRAFT tactical_opportunity rows for pin blocks")
    parser.add_argument("--promotion-ladder", action="store_true", help="Show per-location regenerative value-chain promotion funnel")
    parser.add_argument("--zwischenzug", action="store_true", help="Detect high-priority feedback counter-threats (zwischenzug)")
    parser.add_argument("--propose-zwischenzug", action="store_true", help="Write DRAFT tactical_opportunity rows for zwischenzug signals")
    parser.add_argument("--tactical-layer", action="store_true", help="Composite tactical-layer report (fork, double-check, pin, zwischenzug, promotion)")
    args = parser.parse_args()

    # --- Standard (conn, location_id) commands via dispatch table ----------
    for attr, module_name, func_name in _DB_LOCATION_COMMANDS:
        if getattr(args, attr):
            if not args.location_id:
                parser.error(f"--{attr.replace('_', '-')} requires --location-id")
            from importlib import import_module

            mod = import_module(f"services.analytics.{module_name}")
            with get_connection() as conn:
                result = getattr(mod, func_name)(conn, args.location_id)
            print_json(result)
            return

    # --- No-connection commands ---------------------------------------------
    if args.compare_scenarios:
        from .ecology import compare_scenarios

        print_json(compare_scenarios(args.compare_scenarios))
        return

    if args.sensitivity:
        if not args.scenario_id:
            parser.error("--sensitivity requires --scenario-id")
        from .ecology import sensitivity_analysis

        result = sensitivity_analysis(args.scenario_id, args.variable, args.range_pct, args.steps)
        print_json(result)
        return

    # --- Connection-only commands (no location_id required) -----------------
    if args.emission_factors:
        from .carbon_balance import list_emission_factors

        with get_connection() as conn:
            print_json(list_emission_factors(conn))
        return

    if args.carbon_benchmarks:
        from .carbon_balance import list_carbon_benchmarks

        with get_connection() as conn:
            print_json(list_carbon_benchmarks(conn))
        return

    if args.portfolio_summary:
        from .portfolio import portfolio_theme_summary

        with get_connection() as conn:
            print_json(portfolio_theme_summary(conn))
        return

    if args.ebf_portfolio_summary:
        from .portfolio import ebf_portfolio_summary

        with get_connection() as conn:
            print_json(ebf_portfolio_summary(conn))
        return

    # --- Custom-argument commands -------------------------------------------
    if args.pin_dependency:
        if not args.location_id:
            parser.error("--pin-dependency requires --location-id")
        from .pin_dependency import detect_pin_blocks

        with get_connection() as conn:
            print_json(detect_pin_blocks(conn, location_id=args.location_id))
        return

    if args.propose_pin:
        if not args.location_id:
            parser.error("--propose-pin requires --location-id")
        from .pin_dependency import propose_pin_blocks

        with get_connection() as conn:
            print_json(propose_pin_blocks(conn, location_id=args.location_id, actor="cli"))
        return

    if args.promotion_ladder:
        from .promotion_ladder import compute_promotion_ladder

        with get_connection() as conn:
            print_json(compute_promotion_ladder(conn, location_id=args.location_id))
        return

    if args.zwischenzug:
        from . import automation

        with get_connection() as conn:
            print_json(automation.detect_zwischenzug(conn, location_id=args.location_id))
        return

    if args.propose_zwischenzug:
        from . import automation

        with get_connection() as conn:
            print_json(automation.propose_zwischenzug(conn, location_id=args.location_id, actor="cli"))
        return

    if args.tactical_layer:
        from ..export.report_generator import generate_tactical_layer

        with get_connection() as conn:
            print_json(generate_tactical_layer(conn, location_id=args.location_id))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
