#!/usr/bin/env python3
"""
Financial Sustainability Calculator

Computes financial health from raw revenue/expense data and writes
results to the financial_sustainability_plan table.

Usage:
    python3 -m services.analytics.financial_sustainability compute --location-id UUID
"""

import argparse
import json
import uuid
from datetime import datetime, date, timedelta, timezone
from typing import Optional

from ..common.logging import get_logger
from services.common.cli import print_json
logger = get_logger("analytics.financial_sustainability")


# ============================================================
# Data Queries
# ============================================================

def _query_revenue_events(conn, location_id: str) -> list:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT revenue_date, revenue_type, amount, amount_usd, currency,
               payment_status
        FROM revenue_event
        WHERE location_id = %s
          AND status IN ('verified', 'published')
        ORDER BY revenue_date
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    return rows


def _query_expense_events(conn, location_id: str) -> list:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT expense_date, category, amount, currency, is_capex
        FROM expense_event
        WHERE location_id = %s
          AND status IN ('verified', 'published')
        ORDER BY expense_date
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    return rows


def _query_unit_economics(conn, location_id: str) -> Optional[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT cost_per_hectare_usd, cost_per_farm_usd,
               roi_pct, payback_months, break_even_month
        FROM farm_launch_unit_economics
        WHERE location_id = %s
        ORDER BY created_at DESC NULLS LAST
        LIMIT 1
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    cur.close()
    return dict(zip(cols, row)) if row else None


def _query_existing_plan(conn, location_id: str) -> Optional[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, plan_name, farm_model, plan_period_start, plan_period_end,
               revenue_streams, grant_dependency_pct, reinvestment_pct,
               public_goods_allocation_pct, break_even_month, runway_months,
               projected_annual_revenue_usd, projected_annual_operating_cost_usd,
               projected_annual_noi_usd, sustainability_status, strategy_summary,
               status, metadata
        FROM financial_sustainability_plan
        WHERE location_id = %s
        ORDER BY created_at DESC NULLS LAST
        LIMIT 1
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    cur.close()
    return dict(zip(cols, row)) if row else None


# ============================================================
# Calculators
# ============================================================

def _month_key(d):
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m")
    return str(d)[:7]


def compute_break_even_month(revenues, expenses):
    if not revenues or not expenses:
        return None

    rev_by_month = {}
    for r in revenues:
        k = _month_key(r["revenue_date"])
        rev_by_month[k] = rev_by_month.get(k, 0) + float(r.get("amount") or r.get("amount_usd") or 0)

    exp_by_month = {}
    for e in expenses:
        k = _month_key(e["expense_date"])
        exp_by_month[k] = exp_by_month.get(k, 0) + float(e.get("amount") or 0)

    all_months = sorted(set(rev_by_month.keys()) | set(exp_by_month.keys()))
    if not all_months:
        return None

    cumulative_rev = 0.0
    cumulative_exp = 0.0
    for i, mk in enumerate(all_months, start=1):
        cumulative_rev += rev_by_month.get(mk, 0)
        cumulative_exp += exp_by_month.get(mk, 0)
        if cumulative_rev >= cumulative_exp and cumulative_rev > 0:
            return i

    return None


def compute_revenue_sustainability_index(revenues):
    if len(revenues) < 2:
        return {
            "trend": "insufficient_data",
            "slope_per_month": 0.0,
            "r_squared": 0.0,
            "sustainability_index": 50.0,
            "data_points": len(revenues),
        }

    rev_by_month = {}
    for r in revenues:
        k = _month_key(r["revenue_date"])
        rev_by_month[k] = rev_by_month.get(k, 0) + float(r.get("amount") or r.get("amount_usd") or 0)

    months = sorted(rev_by_month.keys())
    if len(months) < 2:
        return {
            "trend": "insufficient_data",
            "slope_per_month": 0.0,
            "r_squared": 0.0,
            "sustainability_index": 50.0,
            "data_points": len(months),
        }

    n = len(months)
    x = list(range(n))
    y = [rev_by_month[m] for m in months]
    x_mean = sum(x) / n
    y_mean = sum(y) / n

    ss_xx = sum((xi - x_mean) ** 2 for xi in x)
    ss_xy = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
    slope = ss_xy / ss_xx if ss_xx != 0 else 0.0
    intercept = y_mean - slope * x_mean

    y_pred = [slope * xi + intercept for xi in x]
    ss_res = sum((yi - yp) ** 2 for yi, yp in zip(y, y_pred))
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    avg_rev = y_mean if y_mean > 0 else 1.0
    normalized_slope = slope / avg_rev if avg_rev != 0 else 0
    sustainability_index = 50.0 + normalized_slope * 200 + r_squared * 10
    sustainability_index = max(0.0, min(100.0, sustainability_index))

    if abs(normalized_slope) < 0.001:
        trend = "stable"
    elif normalized_slope > 0:
        trend = "growing"
    else:
        trend = "declining"

    return {
        "trend": trend,
        "slope_per_month": round(slope, 2),
        "normalized_slope": round(normalized_slope, 4),
        "r_squared": round(r_squared, 4),
        "sustainability_index": round(sustainability_index, 1),
        "avg_monthly_revenue": round(y_mean, 2),
        "data_points": n,
    }


def compute_cost_efficiency_ratio(revenues, expenses):
    total_rev = sum(float(r.get("amount") or r.get("amount_usd") or 0) for r in revenues)
    total_exp = sum(float(e.get("amount") or 0) for e in expenses)

    cat_totals = {}
    for e in expenses:
        cat = e.get("category", "other") or "other"
        cat_totals[cat] = cat_totals.get(cat, 0) + float(e.get("amount") or 0)

    opex = sum(float(e.get("amount") or 0) for e in expenses if not e.get("is_capex", False))

    efficiency_ratio = total_rev / total_exp if total_exp > 0 else None
    operating_ratio = total_rev / opex if opex > 0 else None

    if efficiency_ratio is None:
        assessment = "no_data"
    elif efficiency_ratio >= 2.0:
        assessment = "highly_efficient"
    elif efficiency_ratio >= 1.5:
        assessment = "efficient"
    elif efficiency_ratio >= 1.0:
        assessment = "break_even"
    elif efficiency_ratio >= 0.8:
        assessment = "below_break_even"
    else:
        assessment = "inefficient"

    return {
        "total_revenue": round(total_rev, 2),
        "total_expenses": round(total_exp, 2),
        "operating_expenses": round(opex, 2),
        "efficiency_ratio": round(efficiency_ratio, 4) if efficiency_ratio is not None else None,
        "operating_ratio": round(operating_ratio, 4) if operating_ratio is not None else None,
        "cost_categories": {k: round(v, 2) for k, v in cat_totals.items()},
        "assessment": assessment,
    }


def compute_cash_flow_projection(revenues, expenses, months_ahead=12):
    rev_by_month = {}
    for r in revenues:
        k = _month_key(r["revenue_date"])
        rev_by_month[k] = rev_by_month.get(k, 0) + float(r.get("amount") or r.get("amount_usd") or 0)

    exp_by_month = {}
    for e in expenses:
        k = _month_key(e["expense_date"])
        exp_by_month[k] = exp_by_month.get(k, 0) + float(e.get("amount") or 0)

    all_months = sorted(set(rev_by_month.keys()) | set(exp_by_month.keys()))
    recent_months = all_months[-6:] if len(all_months) >= 6 else all_months

    if not recent_months:
        return {
            "avg_monthly_revenue": 0,
            "avg_monthly_expenses": 0,
            "avg_monthly_net": 0,
            "projected_runway_months": None,
            "projections": [],
        }

    avg_rev = sum(rev_by_month.get(m, 0) for m in recent_months) / len(recent_months)
    avg_exp = sum(exp_by_month.get(m, 0) for m in recent_months) / len(recent_months)
    avg_net = avg_rev - avg_exp

    cumulative_rev = sum(rev_by_month.get(m, 0) for m in all_months)
    cumulative_exp = sum(exp_by_month.get(m, 0) for m in all_months)
    current_position = cumulative_rev - cumulative_exp

    if avg_net < 0 and current_position > 0:
        runway = current_position / abs(avg_net)
    elif avg_net < 0:
        runway = 0.0
    else:
        runway = None

    projections = []
    cum_position = current_position
    for i in range(1, months_ahead + 1):
        cum_position += avg_net
        projections.append({
            "month": i,
            "projected_revenue": round(avg_rev, 2),
            "projected_expenses": round(avg_exp, 2),
            "projected_net": round(avg_net, 2),
            "cumulative_position": round(cum_position, 2),
        })

    return {
        "avg_monthly_revenue": round(avg_rev, 2),
        "avg_monthly_expenses": round(avg_exp, 2),
        "avg_monthly_net": round(avg_net, 2),
        "current_position": round(current_position, 2),
        "projected_runway_months": round(runway, 1) if runway is not None else None,
        "projection_months": months_ahead,
        "projections": projections,
    }


def classify_sustainability_status(break_even_month, efficiency_ratio, sustainability_index):
    if efficiency_ratio is None:
        return "draft"
    if efficiency_ratio >= 1.5 and sustainability_index >= 60:
        return "self_sustaining"
    if efficiency_ratio >= 1.0 and sustainability_index >= 50:
        return "transitioning"
    if efficiency_ratio >= 0.8:
        return "grant_dependent"
    if efficiency_ratio < 0.5:
        return "needs_rework"
    return "draft"


# ============================================================
# Main Compute
# ============================================================

def compute_financial_sustainability(
    conn,
    location_id,
    plan_name=None,
    farm_model="blended",
    plan_months=12,
    dry_run=False,
):
    revenues = _query_revenue_events(conn, location_id)
    expenses = _query_expense_events(conn, location_id)
    unit_economics = _query_unit_economics(conn, location_id)
    existing_plan = _query_existing_plan(conn, location_id)

    break_even = compute_break_even_month(revenues, expenses)
    rev_sustainability = compute_revenue_sustainability_index(revenues)
    cost_efficiency = compute_cost_efficiency_ratio(revenues, expenses)
    cash_flow = compute_cash_flow_projection(revenues, expenses, months_ahead=plan_months)

    efficiency_ratio = cost_efficiency.get("efficiency_ratio")
    sustainability_index = rev_sustainability.get("sustainability_index", 50.0)
    sustainability_status = classify_sustainability_status(
        break_even, efficiency_ratio, sustainability_index
    )

    revenue_streams = list(set(
        r.get("revenue_type", "other") for r in revenues if r.get("revenue_type")
    ))

    if existing_plan:
        farm_model = existing_plan.get("farm_model") or farm_model
        plan_name = plan_name or existing_plan.get("plan_name")

    all_dates = []
    for r in revenues:
        d = r.get("revenue_date")
        if d:
            all_dates.append(d)
    for e in expenses:
        d = e.get("expense_date")
        if d:
            all_dates.append(d)

    plan_start = min(all_dates) if all_dates else date.today()
    plan_end = None
    if all_dates:
        plan_end = max(all_dates) + timedelta(days=30 * plan_months)

    avg_monthly_rev = cash_flow["avg_monthly_revenue"]
    avg_monthly_exp = cash_flow["avg_monthly_expenses"]
    projected_annual_rev = avg_monthly_rev * 12
    projected_annual_cost = avg_monthly_exp * 12
    projected_annual_noi = projected_annual_rev - projected_annual_cost

    strategy_parts = []
    if break_even is not None:
        strategy_parts.append(f"Projected break-even at month {break_even}")
    if sustainability_status == "self_sustaining":
        strategy_parts.append("Currently self-sustaining with revenue exceeding costs")
    elif sustainability_status == "transitioning":
        strategy_parts.append("Transitioning toward self-sustainability")
    elif sustainability_status == "grant_dependent":
        strategy_parts.append("Grant-dependent; revenue insufficient to cover costs")
    elif sustainability_status == "needs_rework":
        strategy_parts.append("Financial model requires rework; significant cost-revenue gap")
    if revenue_streams:
        strategy_parts.append(f"Revenue streams: {', '.join(revenue_streams)}")
    strategy_summary = "; ".join(strategy_parts) if strategy_parts else "Computed from financial data"

    result = {
        "location_id": location_id,
        "plan_name": plan_name or f"Auto-generated plan for {location_id[:8]}",
        "farm_model": farm_model,
        "plan_period_start": plan_start.isoformat() if hasattr(plan_start, "isoformat") else str(plan_start),
        "plan_period_end": plan_end.isoformat() if plan_end else None,
        "revenue_streams": revenue_streams,
        "break_even_month": break_even,
        "runway_months": cash_flow["projected_runway_months"],
        "projected_annual_revenue_usd": round(projected_annual_rev, 2),
        "projected_annual_operating_cost_usd": round(projected_annual_cost, 2),
        "projected_annual_noi_usd": round(projected_annual_noi, 2),
        "sustainability_status": sustainability_status,
        "strategy_summary": strategy_summary,
        "revenue_sustainability": rev_sustainability,
        "cost_efficiency": cost_efficiency,
        "cash_flow_projection": cash_flow,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    if not dry_run:
        _upsert_plan(conn, location_id, result, existing_plan)

    return result


def _upsert_plan(conn, location_id, result, existing_plan):
    cur = conn.cursor()

    plan_id = existing_plan["id"] if existing_plan else str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO financial_sustainability_plan
            (id, location_id, plan_name, farm_model, plan_period_start, plan_period_end,
             revenue_streams, break_even_month, runway_months,
             projected_annual_revenue_usd, projected_annual_operating_cost_usd,
             projected_annual_noi_usd, sustainability_status, strategy_summary,
             status, source_system, metadata, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft',
                'financial_sustainability_calculator', %s::jsonb, NOW(), NOW())
        ON CONFLICT (id) DO UPDATE SET
            plan_name = EXCLUDED.plan_name,
            farm_model = EXCLUDED.farm_model,
            plan_period_start = EXCLUDED.plan_period_start,
            plan_period_end = EXCLUDED.plan_period_end,
            revenue_streams = EXCLUDED.revenue_streams,
            break_even_month = EXCLUDED.break_even_month,
            runway_months = EXCLUDED.runway_months,
            projected_annual_revenue_usd = EXCLUDED.projected_annual_revenue_usd,
            projected_annual_operating_cost_usd = EXCLUDED.projected_annual_operating_cost_usd,
            projected_annual_noi_usd = EXCLUDED.projected_annual_noi_usd,
            sustainability_status = EXCLUDED.sustainability_status,
            strategy_summary = EXCLUDED.strategy_summary,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        """,
        (
            plan_id,
            location_id,
            result["plan_name"],
            result["farm_model"],
            result["plan_period_start"],
            result["plan_period_end"],
            result["revenue_streams"],
            result["break_even_month"],
            result["runway_months"],
            result["projected_annual_revenue_usd"],
            result["projected_annual_operating_cost_usd"],
            result["projected_annual_noi_usd"],
            result["sustainability_status"],
            result["strategy_summary"],
            json.dumps({
                "revenue_sustainability": result["revenue_sustainability"],
                "cost_efficiency": result["cost_efficiency"],
                "cash_flow_projection": result["cash_flow_projection"],
                "computed_at": result["computed_at"],
            }),
        ),
    )
    conn.commit()
    cur.close()


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Financial sustainability calculator")
    sub = parser.add_subparsers(dest="command")

    comp = sub.add_parser("compute", help="Compute financial sustainability")
    comp.add_argument("--location-id", required=True)
    comp.add_argument("--plan-name")
    comp.add_argument("--farm-model", default="blended",
                      choices=["public_good_optimized", "blended", "for_profit",
                               "cooperative", "research_pilot", "other"])
    comp.add_argument("--plan-months", type=int, default=12)
    comp.add_argument("--dry-run", action="store_true")
    comp.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command != "compute":
        parser.print_help()
        return

    from ..ingestion.base import get_db
    db = get_db()

    try:
        result = compute_financial_sustainability(
            db, args.location_id,
            plan_name=args.plan_name,
            farm_model=args.farm_model,
            plan_months=args.plan_months,
            dry_run=args.dry_run,
        )
        if args.json:
            print_json(result)
        else:
            _print_result(result)
    finally:
        db.close()


def _print_result(r):
    print(f"Financial Sustainability Plan — {r['location_id'][:8]}...")
    print(f"  Status: {r['sustainability_status']}")
    print(f"  Farm model: {r['farm_model']}")
    ce = r["cost_efficiency"]
    print(f"  Cost efficiency ratio: {ce['efficiency_ratio'] or 'N/A'} ({ce['assessment']})")
    rs = r["revenue_sustainability"]
    print(f"  Revenue trend: {rs['trend']} (index={rs['sustainability_index']})")
    if r["break_even_month"] is not None:
        print(f"  Break-even month: {r['break_even_month']}")
    cf = r["cash_flow_projection"]
    print(f"  Avg monthly net: ${cf['avg_monthly_net']:,.2f}")
    if cf["projected_runway_months"] is not None:
        print(f"  Runway: {cf['projected_runway_months']:.1f} months")
    print(f"  Projected annual NOI: ${r['projected_annual_noi_usd']:,.2f}")
    print(f"  Strategy: {r['strategy_summary']}")


if __name__ == "__main__":
    main()
