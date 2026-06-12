"""
Revenue Multiplier CLI

Usage:
    python3 -m services.revenue_multiplier.cli --location-id UUID
    python3 -m services.revenue_multiplier.cli --location-id UUID --dimension crop_mix_optimization
    python3 -m services.revenue_multiplier.cli --location-id UUID --json
    python3 -m services.revenue_multiplier.cli --list-dimensions
"""

import argparse
import json
import sys


DIMENSIONS = [
    ("crop_mix_optimization", "Crop Mix Optimization"),
    ("loss_rate_reduction", "Loss-Rate Reduction"),
    ("buyer_channel_selection", "Buyer/Channel Selection"),
    ("value_added_processing", "Value-Added Processing"),
    ("web3_funded_replication", "Web3-Funded Replication"),
    ("bioinput_production", "Bioinput Production"),
    ("public_goods_funding", "Public-Goods Funding Loops"),
    ("ecological_verification", "Ecological Verification Monetization"),
    ("partner_sponsorship", "Partner Sponsorship"),
    ("regional_farm_clusters", "Regional Farm Clusters"),
]


def main():
    parser = argparse.ArgumentParser(description="Kokonut Revenue Multiplier Opportunity Map")
    parser.add_argument("--location-id", help="Location UUID to analyze")
    parser.add_argument("--dimension", choices=[d[0] for d in DIMENSIONS], help="Run a single dimension")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--list-dimensions", action="store_true", help="List all dimensions")
    args = parser.parse_args()

    if args.list_dimensions:
        print(f"\n{'ID':<35} {'Name'}")
        print("-" * 65)
        for dim_id, dim_name in DIMENSIONS:
            print(f"{dim_id:<35} {dim_name}")
        print()
        return

    if not args.location_id:
        parser.error("--location-id is required")

    if args.dimension:
        import importlib
        # Map dimension IDs to module names
        module_map = {
            "crop_mix_optimization": "crop_mix",
            "loss_rate_reduction": "loss_reduction",
            "buyer_channel_selection": "buyer_channel",
            "value_added_processing": "value_added",
            "web3_funded_replication": "web3_replication",
            "bioinput_production": "bioinput",
            "public_goods_funding": "public_goods",
            "ecological_verification": "ecological_verification",
            "partner_sponsorship": "partner_sponsorship",
            "regional_farm_clusters": "regional_clusters",
        }
        module_name = module_map.get(args.dimension, args.dimension)
        mod = importlib.import_module(f".dimensions.{module_name}", package="services.revenue_multiplier")
        from services.ingestion.base import get_db
        conn = get_db()
        result = mod.analyze(conn, args.location_id)
        conn.close()
        if args.json:
            from dataclasses import asdict
            print(json.dumps(asdict(result), indent=2, default=str))
        else:
            _print_dimension(result)
        return

    from .analyzer import analyze_location
    result = analyze_location(args.location_id)

    if args.json:
        from dataclasses import asdict
        print(json.dumps(asdict(result), indent=2, default=str))
    else:
        _print_report(result)


def _print_report(result):
    print(f"\n{'='*70}")
    print(f"  REVENUE MULTIPLIER OPPORTUNITY MAP")
    print(f"  Location: {result.location_name}")
    print(f"  Overall Score: {result.overall_score}/100")
    print(f"  Total Opportunity: ${result.total_opportunity_usd:,.2f}/year")
    print(f"{'='*70}\n")

    print(f"{'#':<3} {'Dimension':<40} {'Score':>6} {'Impact':>12} {'Conf':>8}")
    print("-" * 70)

    sorted_dims = sorted(result.dimensions, key=lambda d: d.impact_usd, reverse=True)
    for i, dim in enumerate(sorted_dims, 1):
        print(f"{i:<3} {dim.dimension_name:<40} {dim.score:>5.0f} {dim.impact_usd:>11,.0f} {dim.confidence:>8}")

    print(f"\n{'='*70}")
    print("  TOP RECOMMENDATIONS")
    print(f"{'='*70}\n")

    for dim in sorted_dims[:5]:
        if dim.score > 0:
            print(f"  {dim.dimension_name}")
            print(f"    Current: {dim.current_state}")
            print(f"    Action:  {dim.recommendation}")
            print(f"    Impact:  ${dim.impact_usd:,.0f}/year")
            print()


def _print_dimension(result):
    print(f"\n{result.dimension_name}")
    print(f"  Score: {result.score}/100")
    print(f"  Impact: ${result.impact_usd:,.2f}/year")
    print(f"  Confidence: {result.confidence}")
    print(f"  Current: {result.current_state}")
    print(f"  Recommendation: {result.recommendation}")
    if result.details:
        print(f"  Details:")
        for k, v in result.details.items():
            print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
