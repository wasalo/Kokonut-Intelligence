"""CRISP Risk Scoring CLI

Command-line interface for CRISP risk assessment and scoring.

Usage:
    python3 -m services.crisp --composite --location-id UUID --period-start 2025-01-01 --period-end 2025-12-31
    python3 -m services.crisp --carbon-yield --location-id UUID
    python3 -m services.crisp --climate --location-id UUID
    python3 -m services.crisp --policy --location-id UUID
    python3 -m services.crisp --financial --location-id UUID
    python3 -m services.crisp --implementation --location-id UUID
    python3 -m services.crisp --rate --location-id UUID --period-start 2025-01-01 --period-end 2025-12-31
    python3 -m services.crisp --weights --location-id UUID
"""

from __future__ import annotations

import argparse
import json
import sys

from ..ingestion.base import get_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokonut Intelligence CRISP Risk Scoring")
    parser.add_argument("--carbon-yield", action="store_true", help="Compute carbon yield risk")
    parser.add_argument("--climate", action="store_true", help="Compute climate catastrophe risk")
    parser.add_argument("--policy", action="store_true", help="Compute policy & legal risk")
    parser.add_argument("--financial", action="store_true", help="Compute financial viability risk")
    parser.add_argument("--implementation", action="store_true", help="Compute implementation risk")
    parser.add_argument("--composite", action="store_true", help="Compute composite CRISP rating")
    parser.add_argument("--rate", action="store_true", help="Compute and persist CRISP assessment")
    parser.add_argument("--weights", action="store_true", help="Show effective weights for a location")
    parser.add_argument("--location-id", help="Location UUID (required)")
    parser.add_argument("--period-start", help="Assessment period start (YYYY-MM-DD)")
    parser.add_argument("--period-end", help="Assessment period end (YYYY-MM-DD)")
    parser.add_argument("--ssp", choices=["SSP1", "SSP2", "SSP5"], default="SSP2", help="SSP climate scenario (default: SSP2)")
    parser.add_argument("--ex-ante", type=float, help="Ex-ante carbon yield estimate for yield risk")
    parser.add_argument("--methodology-version", help="Override methodology version")
    args = parser.parse_args()

    if args.carbon_yield:
        if not args.location_id:
            parser.error("--carbon-yield requires --location-id")
        from .carbon_yield import compute_carbon_yield_risk
        conn = get_db()
        result = compute_carbon_yield_risk(conn, args.location_id, ex_ante_estimate=args.ex_ante)
        conn.close()
        print(json.dumps(result.__dict__, indent=2, default=str))
        return

    if args.climate:
        if not args.location_id:
            parser.error("--climate requires --location-id")
        from .climate_risk import compute_climate_risk
        conn = get_db()
        result = compute_climate_risk(conn, args.location_id, ssp_scenario=args.ssp)
        conn.close()
        print(json.dumps(result.__dict__, indent=2, default=str))
        return

    if args.policy:
        if not args.location_id:
            parser.error("--policy requires --location-id")
        from .policy_risk import compute_policy_risk
        conn = get_db()
        result = compute_policy_risk(conn, args.location_id)
        conn.close()
        print(json.dumps(result.__dict__, indent=2, default=str))
        return

    if args.financial:
        if not args.location_id:
            parser.error("--financial requires --location-id")
        from .financial_risk import compute_financial_risk
        conn = get_db()
        result = compute_financial_risk(conn, args.location_id)
        conn.close()
        print(json.dumps(result.__dict__, indent=2, default=str))
        return

    if args.implementation:
        if not args.location_id:
            parser.error("--implementation requires --location-id")
        from .implementation_risk import compute_implementation_risk
        conn = get_db()
        result = compute_implementation_risk(conn, args.location_id)
        conn.close()
        print(json.dumps(result.__dict__, indent=2, default=str))
        return

    if args.composite:
        if not args.location_id:
            parser.error("--composite requires --location-id")
        if not args.period_start or not args.period_end:
            parser.error("--composite requires --period-start and --period-end")
        from .scoring_engine import compute_composite_rating
        conn = get_db()
        result = compute_composite_rating(
            conn, args.location_id, args.period_start, args.period_end,
            methodology_version=args.methodology_version,
            ssp_scenario=args.ssp,
        )
        conn.close()
        print(json.dumps(result.to_dict(), indent=2, default=str))
        return

    if args.rate:
        if not args.location_id:
            parser.error("--rate requires --location-id")
        if not args.period_start or not args.period_end:
            parser.error("--rate requires --period-start and --period-end")
        from .scoring_engine import compute_composite_rating, persist_assessment
        conn = get_db()
        try:
            result = compute_composite_rating(
                conn, args.location_id, args.period_start, args.period_end,
                methodology_version=args.methodology_version,
                ssp_scenario=args.ssp,
            )
            assessment_id = persist_assessment(conn, result)
            output = result.to_dict()
            output["assessment_id"] = assessment_id
            output["persisted"] = True
            print(json.dumps(output, indent=2, default=str))
        finally:
            conn.close()
        return

    if args.weights:
        if not args.location_id:
            parser.error("--weights requires --location-id")
        from .scoring_engine import _query_location_weights
        conn = get_db()
        weights = _query_location_weights(conn, args.location_id)
        conn.close()
        print(json.dumps({"location_id": args.location_id, "weights": weights}, indent=2))
        return

    parser.print_help()
