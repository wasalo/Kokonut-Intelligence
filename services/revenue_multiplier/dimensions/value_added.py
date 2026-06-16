"""
Value-Added Processing — Dimension 4

Evaluates processing, storage, and packaging capacity vs revenue uplift.
Compares raw vs processed revenue, estimates upside from value addition.
"""

import psycopg2.extras
from ..models import OpportunityDimension
from ..config import get_config


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get production capacity
    cur.execute("""
        SELECT * FROM production_capacity WHERE location_id = %s
    """, (location_id,))
    capacity = [dict(r) for r in cur.fetchall()]

    # Get sales breakdown (raw vs processed)
    cur.execute("""
        SELECT
            c.name as crop_name,
            s.product_type,
            COUNT(DISTINCT s.id) as sale_count,
            SUM(s.gross_amount) as total_gross,
            SUM(s.net_amount) as total_net
        FROM sales s
        JOIN crop c ON s.crop_id = c.id
        WHERE s.location_id = %s AND s.status IN ('verified', 'published')
        GROUP BY c.name, s.product_type
    """, (location_id,))
    sales_breakdown = [dict(r) for r in cur.fetchall()]

    # Get processing activities
    cur.execute("""
        SELECT * FROM production_batch WHERE location_id = %s
    """, (location_id,))
    batches = [dict(r) for r in cur.fetchall()]

    # Get forecast: projected revenue by crop
    cur.execute("""
        SELECT metric_name, inputs
        FROM forecast_output
        WHERE location_id = %s
          AND metric_name = 'projected_revenue_usd'
        ORDER BY created_at DESC LIMIT 1
    """, (location_id,))
    forecast_row = cur.fetchone()
    forecast_revenue = {}
    if forecast_row:
        inputs = dict(forecast_row)["inputs"] or {}
        forecast_revenue = inputs.get("revenue_by_crop", {})

    cur.close()

    if not capacity and not sales_breakdown:
        return _empty("value_added_processing", "Value-Added Processing")

    # Calculate raw vs processed revenue
    raw_revenue = 0
    processed_revenue = 0
    for sale in sales_breakdown:
        gross = float(sale["total_gross"] or 0)
        if sale["product_type"] in ("raw", "unprocessed"):
            raw_revenue += gross
        else:
            processed_revenue += gross

    total_revenue = raw_revenue + processed_revenue
    processed_pct = (processed_revenue / max(total_revenue, 1)) * 100

    # Uplift: processed revenue / raw revenue
    uplift = processed_revenue / max(raw_revenue, 1)

    # Get config constants
    value_added_uplift_multiplier = float(get_config(conn, 'value_added_uplift_multiplier'))
    value_added_infra_bonus = float(get_config(conn, 'value_added_infra_bonus'))
    value_added_cost_assumption = float(get_config(conn, 'value_added_cost_assumption'))

    # Score: higher if low processed % but high capacity
    score = min(100, max(0, processed_pct))

    # If there's infrastructure but low processing, bonus
    has_storage = any(c.get("storage_capacity") for c in capacity)
    has_processing = any(c.get("processing_capacity") for c in capacity)
    if has_processing and processed_pct < 50:
        score *= value_added_infra_bonus
        score = min(100, score)

    # Impact: revenue uplift if processing increases
    # If we can shift more raw to processed, what's the gain?
    potential_uplift_per_dollar = value_added_uplift_multiplier
    raw_for_processing = raw_revenue * 0.5  # 50% of raw could be processed
    processing_cost = raw_for_processing * value_added_cost_assumption
    impact = raw_for_processing * (value_added_uplift_multiplier - 1) - processing_cost

    # Forecast-adjusted impact
    forecast_impact = 0
    if forecast_revenue:
        total_forecast = sum(float(v or 0) for v in forecast_revenue.values())
        forecast_impact = total_forecast * (1 - processed_pct / 100) * (value_added_uplift_multiplier - 1) * 0.3

    details = {
        "raw_revenue": round(raw_revenue, 2),
        "processed_revenue": round(processed_revenue, 2),
        "processed_pct": round(processed_pct, 1),
        "uplift_ratio": round(uplift, 2),
        "capacity_items": len(capacity),
        "batch_count": len(batches),
        "forecast_impact_usd": round(forecast_impact, 2),
    }

    impact = max(impact, forecast_impact)

    return OpportunityDimension(
        dimension_id="value_added_processing",
        dimension_name="Value-Added Processing",
        score=round(score, 1),
        impact_usd=round(impact, 2),
        confidence="high" if batches and len(batches) > 3 else "medium",
        current_state=f"{processed_pct:.0f}% processed, uplift {uplift:.1f}x",
        recommendation=f"Increase processing to {processed_pct + 20:.0f}% for +${impact:,.0f}/year" if impact > 0 else "Processing at optimal level",
        data_points=len(sales_breakdown) + len(batches),
        details=details,
    )


def _empty(dim_id, dim_name):
    return OpportunityDimension(
        dimension_id=dim_id, dimension_name=dim_name,
        score=0, impact_usd=0, confidence="low",
        current_state="No production data", recommendation="Set up production capacity tracking",
        data_points=0,
    )
