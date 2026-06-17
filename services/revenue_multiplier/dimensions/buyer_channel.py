"""
Buyer Channel Optimization — Dimension 3

Optimizes buyer selection for best terms (payment timing, returns, volume).
Compares buyer performance metrics, recommends channel shifts.
"""

import psycopg2.extras
from ..models import OpportunityDimension
from ..config import get_config


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get sales grouped by buyer
    cur.execute("""
        SELECT
            COALESCE(p.name, s.buyer, 'Unknown') as buyer_name,
            COALESCE(p.partner_type, s.buyer_type, 'unknown') as buyer_tier,
            COUNT(DISTINCT s.id) as sale_count,
            SUM(s.total_amount) as total_gross,
            SUM(COALESCE(s.net_amount, s.total_amount - COALESCE(s.return_amount, 0) - COALESCE(s.discount_amount, 0))) as total_net,
            SUM(COALESCE(s.discount_amount, 0)) as total_discounts,
            SUM(COALESCE(s.return_amount, 0)) as total_returns,
            AVG(CASE WHEN s.payment_date IS NOT NULL THEN s.payment_date - s.sale_date ELSE NULL END) as avg_days_to_payment
        FROM sales_event s
        LEFT JOIN partner p ON s.partner_id = p.id
        WHERE s.location_id = %s AND s.status IN ('verified', 'published')
        GROUP BY COALESCE(p.name, s.buyer, 'Unknown'), COALESCE(p.partner_type, s.buyer_type, 'unknown')
    """, (location_id,))
    buyers = [dict(r) for r in cur.fetchall()]

    # Get buyer performance scores
    performance = []

    # Get forecast: projected revenue by buyer
    cur.execute("""
        SELECT metric_name, inputs
        FROM forecast_output
        WHERE location_id = %s
          AND metric_name = 'projected_revenue_usd'
        ORDER BY calculated_at DESC LIMIT 1
    """, (location_id,))
    forecast_row = cur.fetchone()
    forecast_revenue = {}
    if forecast_row:
        inputs = dict(forecast_row)["inputs"] or {}
        forecast_revenue = inputs.get("revenue_by_crop", {})

    cur.close()

    if not buyers:
        return _empty("buyer_channel_selection", "Buyer Channel Optimization")

    # Calculate scores for each buyer
    scores = []
    for buyer in buyers:
        gross = float(buyer["total_gross"] or 0)
        net = float(buyer["total_net"] or 0)
        returns = float(buyer["total_returns"] or 0)
        discounts = float(buyer["total_discounts"] or 0)
        days = float(buyer["avg_days_to_payment"] or 0)

        # Payment rate: lower days = better
        payment_score = max(0, 100 - days) / 100

        # Returns rate: lower returns = better
        returns_score = (1 - returns / max(gross, 1)) if gross > 0 else 0

        # Net-per-sale: higher = better
        net_per_sale = net / max(buyer["sale_count"], 1)

        w_payment = float(get_config(conn, 'buyer_payment_weight'))
        w_returns = float(get_config(conn, 'buyer_returns_weight'))
        w_netsale = float(get_config(conn, 'buyer_netsale_weight'))

        buyer_score = (
            payment_score * w_payment +
            returns_score * w_returns +
            (net_per_sale / float(get_config(conn, 'buyer_netsale_normalizer'))) * w_netsale
        )
        scores.append({
            "buyer": buyer["buyer_name"],
            "tier": buyer["buyer_tier"],
            "sale_count": buyer["sale_count"],
            "avg_days_to_payment": round(days, 1),
            "returns_rate_pct": round(returns / max(gross, 1) * 100, 1),
            "net_per_sale": round(net_per_sale, 2),
            "score": round(buyer_score, 3),
        })

    scores.sort(key=lambda x: x["score"], reverse=True)

    # Best and worst buyers
    best = scores[0]
    worst = scores[-1]

    # Score: difference between best and worst
    gap = best["score"] - worst["score"]
    score = min(100, max(0, gap * 100))

    # Impact: shifting worst buyer's volume to best buyer
    total_net = sum(float(b["total_net"] or 0) for b in buyers)
    worst_net = next((float(b["total_net"] or 0) for b in buyers if b["buyer_name"] == worst["buyer"]), 0)
    impact = worst_net * (best["score"] - worst["score"])

    # Forecast-adjusted impact
    forecast_impact = 0
    if forecast_revenue:
        total_forecast = sum(float(v or 0) for v in forecast_revenue.values())
        forecast_impact = total_forecast * (best["score"] - worst["score"]) * 0.5

    buyer_count_multiplier = float(get_config(conn, 'buyer_count_multiplier'))
    confidence_threshold = int(get_config(conn, 'buyer_confidence_threshold'))
    details = {
        "buyer_count": len(buyers),
        "best_buyer": best,
        "worst_buyer": worst,
        "all_buyers": scores,
        "total_net_sales": round(total_net, 2),
        "forecast_impact_usd": round(forecast_impact, 2),
    }

    impact = max(impact, forecast_impact)

    return OpportunityDimension(
        dimension_id="buyer_channel_selection",
        dimension_name="Buyer Channel Optimization",
        score=round(score, 1),
        impact_usd=round(impact, 2),
        confidence="high" if len(buyers) >= confidence_threshold else "medium",
        current_state=f"{len(buyers)} buyers, best={best['buyer']} (score {best['score']:.2f})",
        recommendation=f"Shift volume from {worst['buyer']} to {best['buyer']} for +${impact:,.0f}/year",
        data_points=len(buyers),
        details=details,
    )


def _empty(dim_id, dim_name):
    return OpportunityDimension(
        dimension_id=dim_id, dimension_name=dim_name,
        score=0, impact_usd=0, confidence="low",
        current_state="No buyer data", recommendation="Record sales with buyer attribution",
        data_points=0,
    )
