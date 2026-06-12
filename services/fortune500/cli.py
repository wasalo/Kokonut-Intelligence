"""
Fortune 500 Calculator CLI

Usage:
    python3 -m services.fortune500.cli --farm <location-id>
    python3 -m services.fortune500.cli --all
    python3 -m services.fortune500.cli --all --json
"""

import argparse
import json
import sys

from .calculator import calculate_all_farms, get_farm_metrics, calculate_score


def print_score_table(results):
    """Print formatted score table."""
    print(f"\n{'='*90}")
    print(f"  KOKONUT INTELLIGENCE — FORTUNE 500 FARM RANKINGS")
    print(f"{'='*90}")
    print(f"\n{'Rank':<6} {'Farm':<35} {'Financial':>10} {'Ecology':>10} {'Governance':>11} {'Growth':>8} {'TOTAL':>8} {'Tier':<10}")
    print("-" * 90)

    for r in results:
        print(
            f"{r['rank']:<6} "
            f"{r['location_name']:<35} "
            f"{r['financial_score']:>10.1f} "
            f"{r['ecological_score']:>10.1f} "
            f"{r['governance_score']:>11.1f} "
            f"{r['growth_score']:>8.1f} "
            f"{r['composite_score']:>8.1f} "
            f"{r['tier']:<10}"
        )

    print(f"\n{'='*90}")
    print(f"  Scores: 0-1000 | Tiers: Platinum (800+) | Gold (600+) | Silver (400+) | Bronze (200+) | Developing")
    print(f"  Weights: Financial 45% | Ecological 25% | Governance 15% | Growth 15%")
    print(f"{'='*90}\n")


def print_detailed(result):
    """Print detailed score breakdown."""
    print(f"\n{'='*60}")
    print(f"  FARM SCORECARD: {result['location_name']}")
    print(f"{'='*60}")
    print(f"\n  Composite Score: {result['composite_score']:.1f} / 1000 ({result['tier']})")
    print(f"  Rank: #{result['rank']} | Percentile: {result['percentile']}%")

    print(f"\n  Score Breakdown:")
    print(f"  {'Financial:':<25} {result['financial_score']:>6.1f} / 1000  (weight: 45%)")
    print(f"  {'Ecological:':<25} {result['ecological_score']:>6.1f} / 1000  (weight: 25%)")
    print(f"  {'Governance:':<25} {result['governance_score']:>6.1f} / 1000  (weight: 15%)")
    print(f"  {'Growth:':<25} {result['growth_score']:>6.1f} / 1000  (weight: 15%)")

    inputs = result.get("breakdown", {}).get("inputs", {})
    if inputs:
        print(f"\n  Key Inputs:")
        print(f"  {'Revenue/ha:':<25} ${inputs.get('revenue_per_ha', 0):>10,.2f}")
        print(f"  {'Operating Margin:':<25} {inputs.get('operating_margin_pct', 0):>10.1f}%")
        print(f"  {'Loss Rate:':<25} {inputs.get('loss_rate_pct', 0):>10.1f}%")
        print(f"  {'Avg NDVI:':<25} {inputs.get('avg_ndvi', 0):>10.4f}")
        print(f"  {'Soil Organic Matter:':<25} {inputs.get('soil_organic_matter_pct', 0):>10.1f}%")
        print(f"  {'Data Completeness:':<25} {inputs.get('data_completeness_pct', 0):>10.1f}%")
        print(f"  {'Attestations:':<25} {inputs.get('attestation_count', 0):>10}")

    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Kokonut Fortune 500 Calculator")
    parser.add_argument("--farm", help="Calculate score for a specific farm (location UUID)")
    parser.add_argument("--all", action="store_true", help="Calculate and rank all farms")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.farm:
        metrics = get_farm_metrics(args.farm)
        score = calculate_score(metrics)
        result = {
            "location_id": args.farm,
            "location_name": metrics.location_name,
            "financial_score": score.financial_score,
            "ecological_score": score.ecological_score,
            "governance_score": score.governance_score,
            "growth_score": score.growth_score,
            "composite_score": score.composite_score,
            "tier": score.tier,
            "rank": 1,
            "percentile": 100.0,
            "breakdown": score.breakdown,
        }
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print_detailed(result)
        return

    if args.all:
        results = calculate_all_farms()
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            print_score_table(results)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
