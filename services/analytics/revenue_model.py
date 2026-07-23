"""Revenue Model + Cost Structure service.

Defines revenue stream models, pricing, cost structures, cost drivers,
and break-even analysis for business model financial planning.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.database import get_db


# ──────────────────────────────────────────────
# Revenue Stream Definitions
# ──────────────────────────────────────────────

def create_revenue_stream(
    conn, location_id: str, stream_name: str, stream_type: str,
    product_service: Optional[str] = None, description: Optional[str] = None,
    currency: str = "USD", estimated_annual_usd: float = 0,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO revenue_stream_definition (
                location_id, stream_name, stream_type, product_service,
                description, currency, estimated_annual_usd, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, stream_name, stream_type, is_active
            """,
            (
                location_id, stream_name, stream_type, product_service,
                description, currency, estimated_annual_usd, created_by,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def list_revenue_streams(
    conn, location_id: str, active_only: bool = True,
) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        where = "location_id = %s"
        params: list = [location_id]
        if active_only:
            where += " AND is_active = TRUE"
        cur.execute(
            f"""
            SELECT id, stream_name, stream_type, product_service,
                   currency, estimated_annual_usd, is_active, created_at
            FROM revenue_stream_definition
            WHERE {where}
            ORDER BY estimated_annual_usd DESC
            """,
            params,
        )
        return [dict(r) for r in cur.fetchall()]


def get_revenue_stream(conn, stream_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM revenue_stream_definition WHERE id = %s", (stream_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None


# ──────────────────────────────────────────────
# Pricing Models
# ──────────────────────────────────────────────

def create_pricing_model(
    conn, location_id: str, product_name: str, pricing_type: str,
    base_price: float, revenue_stream_id: Optional[str] = None,
    currency: str = "USD", unit: Optional[str] = None,
    min_quantity: float = 0, max_quantity: Optional[float] = None,
    volume_discount_pct: float = 0, tier_name: Optional[str] = None,
    tier_description: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO pricing_model (
                location_id, revenue_stream_id, product_name, pricing_type,
                base_price, currency, unit, min_quantity, max_quantity,
                volume_discount_pct, tier_name, tier_description, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, product_name, pricing_type, base_price
            """,
            (
                location_id, revenue_stream_id, product_name, pricing_type,
                base_price, currency, unit, min_quantity, max_quantity,
                volume_discount_pct, tier_name, tier_description, created_by,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def list_pricing_models(
    conn, location_id: str, active_only: bool = True,
) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        where = "location_id = %s"
        params: list = [location_id]
        if active_only:
            where += " AND is_active = TRUE"
        cur.execute(
            f"""
            SELECT id, product_name, pricing_type, base_price, currency,
                   unit, volume_discount_pct, tier_name, is_active
            FROM pricing_model
            WHERE {where}
            ORDER BY base_price
            """,
            params,
        )
        return [dict(r) for r in cur.fetchall()]


# ──────────────────────────────────────────────
# Cost Structure
# ──────────────────────────────────────────────

def create_cost_structure(
    conn, location_id: str, cost_category: str, cost_type: str,
    amount_usd: float, cost_subcategory: Optional[str] = None,
    frequency: str = "monthly", period_start: Optional[str] = None,
    period_end: Optional[str] = None, description: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO cost_structure (
                location_id, cost_category, cost_subcategory, cost_type,
                amount_usd, frequency, period_start, period_end, description, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, cost_category, cost_type, amount_usd
            """,
            (
                location_id, cost_category, cost_subcategory, cost_type,
                amount_usd, frequency, period_start, period_end, description,
                created_by,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def list_cost_structures(
    conn, location_id: str, active_only: bool = True,
) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        where = "location_id = %s"
        params: list = [location_id]
        if active_only:
            where += " AND is_active = TRUE"
        cur.execute(
            f"""
            SELECT id, cost_category, cost_subcategory, cost_type,
                   amount_usd, frequency, is_active
            FROM cost_structure
            WHERE {where}
            ORDER BY cost_category, amount_usd DESC
            """,
            params,
        )
        return [dict(r) for r in cur.fetchall()]


def create_cost_driver(
    conn, location_id: str, driver_name: str, driver_type: str,
    cost_structure_id: Optional[str] = None, sensitivity_pct: float = 0,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO cost_driver (
                location_id, cost_structure_id, driver_name, driver_type,
                sensitivity_pct, description
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, driver_name, driver_type, sensitivity_pct
            """,
            (
                location_id, cost_structure_id, driver_name, driver_type,
                sensitivity_pct, description,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


# ──────────────────────────────────────────────
# Break-Even Analysis
# ──────────────────────────────────────────────

def create_break_even(
    conn, location_id: str, total_fixed_costs: float,
    variable_cost_per_unit: float, price_per_unit: float,
    analysis_name: str = "Default Analysis",
    assumptions: Optional[Dict] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a break-even analysis with auto-computed metrics."""
    if price_per_unit <= 0:
        raise ValueError("price_per_unit must be > 0")
    contribution_margin = price_per_unit - variable_cost_per_unit
    if contribution_margin <= 0:
        raise ValueError("price_per_unit must exceed variable_cost_per_unit for positive contribution margin")
    contribution_margin_pct = (contribution_margin / price_per_unit) * 100
    break_even_units = total_fixed_costs / contribution_margin
    break_even_revenue = break_even_units * price_per_unit

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO break_even_analysis (
                location_id, analysis_name, total_fixed_costs,
                variable_cost_per_unit, price_per_unit,
                break_even_units, break_even_revenue,
                contribution_margin, assumptions, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, break_even_units, break_even_revenue, contribution_margin
            """,
            (
                location_id, analysis_name, total_fixed_costs,
                variable_cost_per_unit, price_per_unit,
                round(break_even_units, 2), round(break_even_revenue, 2),
                round(contribution_margin_pct, 2),
                json.dumps(assumptions or {}), created_by,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def list_break_even_analyses(
    conn, location_id: str,
) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, analysis_name, total_fixed_costs, variable_cost_per_unit,
                   price_per_unit, break_even_units, break_even_revenue,
                   contribution_margin, analysis_date, status
            FROM break_even_analysis
            WHERE location_id = %s
            ORDER BY analysis_date DESC
            """,
            (location_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def compute_sensitivity(
    conn, break_even_id: str, price_changes: Optional[List[float]] = None,
    cost_changes: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Compute sensitivity analysis for break-even under different scenarios.

    price_changes: list of percentage changes (e.g., [-10, -5, 0, 5, 10])
    cost_changes: list of percentage changes to variable costs
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM break_even_analysis WHERE id = %s", (break_even_id,)
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"break_even {break_even_id} not found")
        bea = dict(row)

    fixed = float(bea["total_fixed_costs"])
    var_cost = float(bea["variable_cost_per_unit"])
    price = float(bea["price_per_unit"])

    price_changes = price_changes or [-10, -5, 0, 5, 10]
    cost_changes = cost_changes or [-10, -5, 0, 5, 10]

    scenarios = []
    for pc in price_changes:
        for cc in cost_changes:
            adj_price = price * (1 + pc / 100)
            adj_var = var_cost * (1 + cc / 100)
            cm = adj_price - adj_var
            if cm > 0:
                beu = fixed / cm
                ber = beu * adj_price
            else:
                beu = None
                ber = None
            scenarios.append({
                "price_change_pct": pc,
                "cost_change_pct": cc,
                "adjusted_price": round(adj_price, 2),
                "adjusted_variable_cost": round(adj_var, 2),
                "break_even_units": round(beu, 2) if beu else None,
                "break_even_revenue": round(ber, 2) if ber else None,
            })

    # Update sensitivity_data on the record
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE break_even_analysis SET sensitivity_data = %s WHERE id = %s",
            (json.dumps(scenarios), break_even_id),
        )
        conn.commit()

    return {"scenarios": scenarios, "count": len(scenarios)}


# ──────────────────────────────────────────────
# Revenue Forecast
# ──────────────────────────────────────────────

def revenue_forecast(
    conn, location_id: str, periods: int = 12,
) -> Dict[str, Any]:
    """Project future revenue from revenue stream definitions."""
    streams = list_revenue_streams(conn, location_id)
    monthly_projections = []
    for i in range(1, periods + 1):
        period_total = 0.0
        stream_details = []
        for s in streams:
            annual = float(s.get("estimated_annual_usd") or 0)
            monthly = annual / 12
            period_total += monthly
            stream_details.append({
                "stream_id": str(s["id"]),
                "stream_name": s["stream_name"],
                "monthly_amount": round(monthly, 2),
            })
        monthly_projections.append({
            "period": i,
            "total": round(period_total, 2),
            "streams": stream_details,
        })

    total_forecast = sum(p["total"] for p in monthly_projections)
    return {
        "location_id": location_id,
        "periods": periods,
        "monthly_projections": monthly_projections,
        "total_forecast": round(total_forecast, 2),
        "stream_count": len(streams),
    }


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def _cmd(args) -> None:
    conn = get_db()
    try:
        if args.command == "create-stream":
            out = create_revenue_stream(
                conn, args.location_id, args.stream_name, args.stream_type,
                product_service=args.product, description=args.description,
                estimated_annual_usd=args.annual_usd, created_by=args.created_by,
            )
        elif args.command == "list-streams":
            out = list_revenue_streams(conn, args.location_id)
        elif args.command == "create-pricing":
            out = create_pricing_model(
                conn, args.location_id, args.product_name, args.pricing_type,
                args.base_price, unit=args.unit,
                volume_discount_pct=args.discount_pct,
                created_by=args.created_by,
            )
        elif args.command == "list-pricing":
            out = list_pricing_models(conn, args.location_id)
        elif args.command == "create-cost":
            out = create_cost_structure(
                conn, args.location_id, args.cost_category, args.cost_type,
                args.amount, frequency=args.frequency,
                description=args.description, created_by=args.created_by,
            )
        elif args.command == "list-costs":
            out = list_cost_structures(conn, args.location_id)
        elif args.command == "create-driver":
            out = create_cost_driver(
                conn, args.location_id, args.driver_name, args.driver_type,
                sensitivity_pct=args.sensitivity, description=args.description,
            )
        elif args.command == "break-even":
            out = create_break_even(
                conn, args.location_id, args.fixed_costs,
                args.variable_cost, args.price,
                analysis_name=args.analysis_name,
                created_by=args.created_by,
            )
        elif args.command == "list-break-even":
            out = list_break_even_analyses(conn, args.location_id)
        elif args.command == "sensitivity":
            out = compute_sensitivity(conn, args.break_even_id)
        elif args.command == "forecast":
            out = revenue_forecast(conn, args.location_id, periods=args.periods)
        else:
            out = {}
        print(json.dumps(out, indent=2, default=str))
    finally:
        conn.close()


def main() -> None:
    p = argparse.ArgumentParser(description="Revenue Model + Cost Structure")
    p.add_argument("--location-id", default=None)
    sub = p.add_subparsers(dest="command", required=True)

    # Revenue streams
    cs = sub.add_parser("create-stream")
    cs.add_argument("--stream-name", required=True)
    cs.add_argument("--stream-type", required=True,
                    choices=["one_time", "recurring", "subscription", "licensing",
                             "brokerage", "advertising", "grant", "carbon_credit", "biodiversity_credit"])
    cs.add_argument("--product", default=None)
    cs.add_argument("--description", default=None)
    cs.add_argument("--annual-usd", type=float, default=0)
    cs.add_argument("--created-by", default=None)

    ls = sub.add_parser("list-streams")

    # Pricing
    cp = sub.add_parser("create-pricing")
    cp.add_argument("--product-name", required=True)
    cp.add_argument("--pricing-type", required=True,
                    choices=["per_unit", "per_kg", "per_hectare", "subscription_tier",
                             "volume_discount", "dynamic", "flat_rate"])
    cp.add_argument("--base-price", type=float, required=True)
    cp.add_argument("--unit", default=None)
    cp.add_argument("--discount-pct", type=float, default=0)
    cp.add_argument("--created-by", default=None)

    lp = sub.add_parser("list-pricing")

    # Cost structure
    cc = sub.add_parser("create-cost")
    cc.add_argument("--cost-category", required=True)
    cc.add_argument("--cost-type", required=True, choices=["fixed", "variable", "semi_variable"])
    cc.add_argument("--amount", type=float, required=True)
    cc.add_argument("--frequency", default="monthly",
                    choices=["one_time", "daily", "weekly", "monthly", "quarterly", "annually"])
    cc.add_argument("--description", default=None)
    cc.add_argument("--created-by", default=None)

    lc = sub.add_parser("list-costs")

    # Cost driver
    cd = sub.add_parser("create-driver")
    cd.add_argument("--driver-name", required=True)
    cd.add_argument("--driver-type", required=True,
                    choices=["volume", "labor", "input_price", "weather", "seasonal", "regulatory", "market"])
    cd.add_argument("--sensitivity", type=float, default=0)
    cd.add_argument("--description", default=None)

    # Break-even
    be = sub.add_parser("break-even")
    be.add_argument("--fixed-costs", type=float, required=True)
    be.add_argument("--variable-cost", type=float, required=True)
    be.add_argument("--price", type=float, required=True)
    be.add_argument("--analysis-name", default="Default Analysis")
    be.add_argument("--created-by", default=None)

    lbe = sub.add_parser("list-break-even")

    se = sub.add_parser("sensitivity")
    se.add_argument("--break-even-id", required=True)

    # Forecast
    f = sub.add_parser("forecast")
    f.add_argument("--periods", type=int, default=12)

    args = p.parse_args()
    _cmd(args)


if __name__ == "__main__":
    main()
